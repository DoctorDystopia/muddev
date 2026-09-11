"""
Crafting service layer for Blackout.

Provides a clean API for recipe discovery, prerequisite checking, and
crafting execution. This is the sole point of contact for all game code
(menus, commands, NPC dialogues, tests) with the underlying Evennia
crafting contrib.

Usage:
    from systems.gameplay.crafting.crafting_service import (
        get_categories,
        get_recipes_in_category,
        get_recipes_for_facility,
        get_recipe_class,
        check_craftable,
        get_max_craftable,
        get_recipe_display_data,
        get_recipes_for_skill,
        get_material_summary,
        perform_craft,
    )
"""



from collections import Counter

from .constants import (
    CONSUMABLE_TAG_CATEGORY,
    MAX_CRAFT_BATCH_SIZE,
    TOOL_TAG_CATEGORY,
)
from .registry import RECIPE_REGISTRY
from systems.gameplay.quests import constants as quest_constants
from systems.gameplay.quests.hooks import notify_quests
from systems.interface.statefeed import constants as feed_const

# Every line this module sends a player is crafting, so the routing tag is
# bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/interface/statefeed/constants.py.
_MSG_CRAFTING = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_CRAFTING}


def _iter_candidate_items(caller, include_location):
    """
    Purpose: Yield every object that may satisfy a recipe requirement.

    Entry:
        caller is an Evennia Object. It need not have an equipment handler.
        include_location is True to also scan the room (tools only).

    Exit/Returns:
        Yields Evennia Objects. May yield the same object twice only if it
        genuinely occupies two scanned collections.

    Module Globals:
        None

    Methodology:
        Materials must be carried, so they scan carried + equipped only.
        Tools may be furniture (a furnace, an anvil), so they additionally
        scan the room. This is the single definition of "where crafting
        looks" -- it was previously open-coded in three places that had
        already drifted apart.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 07/30/2026
    """
    yield from caller.contents

    equipment = getattr(caller, "equipment", None)
    if equipment is not None:
        yield from equipment.all()

    if include_location and caller.location:
        yield from caller.location.contents


def _has_tag(item, tag_value, tag_category):
    """Return True if item carries tag_value under tag_category."""
    tags = item.tags.get(category=tag_category, return_list=True)
    return tag_value in tags


def _count_tagged_items(caller, tag_value, tag_category):
    """Count units of carried/equipped items carrying tag_value under
    tag_category. A stackable object contributes its quantity, not 1."""
    candidates = _iter_candidate_items(caller, include_location=False)
    matches = [item for item in candidates if _has_tag(item, tag_value, tag_category)]
    return sum(getattr(item, "quantity", 1) for item in matches)


def _has_tool_available(caller, tag_value):
    """Return True if a matching tool is carried, equipped, or in the room."""
    candidates = _iter_candidate_items(caller, include_location=True)
    for item in candidates:
        is_match = _has_tag(item, tag_value, TOOL_TAG_CATEGORY)
        if is_match:
            return True

    return False


def get_categories(facility=None):
    """Discover recipe categories, optionally filtered by facility.

    Args:
        facility: Optional CraftingFacility object with allowed_categories.

    Returns:
        dict mapping category name to list of recipe keys.
    """
    categories = {}

    for recipe_key, recipe_cls in RECIPE_REGISTRY.items():
        cat = getattr(recipe_cls, "category", "Uncategorized")
        if facility is not None:
            allowed = getattr(facility, "allowed_categories", None)
            if allowed is not None and cat not in allowed:
                continue
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(recipe_key)

    return categories


def get_recipes_in_category(category, facility=None):
    """Get all recipes belonging to a category, optionally filtered by facility.

    Args:
        category: Category name to match.
        facility: Optional CraftingFacility object with allowed_categories.

    Returns:
        list of (recipe_key, recipe_cls) tuples.
    """
    allowed = getattr(facility, "allowed_categories", None) if facility is not None else None

    return [
        (key, cls)
        for key, cls in RECIPE_REGISTRY.items()
        if getattr(cls, "category", "Uncategorized") == category
        and (allowed is None or category in allowed)
    ]


def recipe_order(pair):
    """Sort key that lists recipes the way the skills sheet lists unlocks.

    Skill first, then required level, then name -- so a facility spanning
    two skills keeps each skill's ladder together and ascending, and a
    single-skill list is a plain level ladder. One owner of "the order
    recipes are listed in", shared by every reader below, because a player
    reading the same recipes on the skills sheet and in the craft menu
    should not have to re-find them.

    Args:
        pair: a (recipe_key, recipe_cls) tuple.

    Returns:
        tuple, suitable for list.sort(key=...).
    """
    _key, recipe_cls = pair

    return (recipe_cls.required_skill, recipe_cls.required_level, recipe_cls.name)


def get_recipes_for_facility(facility):
    """Get every recipe available at a facility, across all its categories.

    Args:
        facility: CraftingFacility object with allowed_categories. If it has
            no allowed_categories (None), every registered recipe is
            returned.

    Returns:
        list of (recipe_key, recipe_cls) tuples, in recipe_order.
    """
    allowed = getattr(facility, "allowed_categories", None)

    if allowed is None:
        matches = list(RECIPE_REGISTRY.items())
    else:
        matches = [
            (key, cls)
            for key, cls in RECIPE_REGISTRY.items()
            if getattr(cls, "category", "Uncategorized") in allowed
        ]

    matches.sort(key=recipe_order)

    return matches


def get_recipe_class(recipe_key):
    """Get the recipe class for a given recipe key, or None if not found."""
    return RECIPE_REGISTRY.get(recipe_key)


def get_deferred_handler_for_facility(caller, facility):
    """The character handler a facility's recipes defer their output to.

    Entry:
        caller is the character standing at the facility. facility is a
        CraftingFacility, or None for the unrestricted menu.

    Exit/Returns:
        Returns the handler object, or None when nothing worked here is
        deferred -- which is every facility but the curing chamber today.

    Methodology:
        Derived from the RECIPES, never from the facility's typeclass. The
        curing chamber is the only facility with a slot display today, and
        writing the test as "is this a chamber" would make a second deferred
        stage a change to every screen that asks. What makes a facility's menu
        show slots is that something workable there does not finish in the call
        that started it, which is exactly what deferred_handler says.

        The FIRST match wins. A facility whose categories mixed a deferred
        recipe with an immediate one would show the deferred stage's slots,
        which is the right answer: the immediate half has no slots to show.
        Nothing in the game mixes them, and allowed_categories is per-facility
        precisely so nothing has to.
    """
    recipes = get_recipes_for_facility(facility)

    for _recipe_key, recipe_cls in recipes:
        if not recipe_cls.deferred_handler:
            continue

        handler = recipe_cls.deferred_handler_for(caller)

        if handler is not None:
            return handler

    return None


def get_deferred_handlers(caller):
    """Every deferred-stage handler this character has, in registry order.

    Entry:
        caller is a character.

    Exit/Returns:
        Returns a list of (stage_name, handler) tuples, one per distinct
        deferred stage the recipe registry names. Empty when the character
        carries none of them.

        The name is the recipe's own deferred_handler string ("curing"), which
        is the stable machine token for the stage -- a structured payload needs
        to say WHICH stage a block of slots belongs to, and the attribute name
        is the one spelling of that the game already has.

    Methodology:
        The registry is the source of truth for which stages exist, so a screen
        showing "everything I have in progress" -- the dossier's Processing
        band -- needs no list of its own and gains a second stage the day a
        recipe declares one.

        Distinct by HANDLER NAME rather than by recipe: forty curing recipes
        are one chamber. A name the character does not carry is skipped rather
        than reported, which is the same failure-closed reading
        deferred_handler_for documents.
    """
    seen = set()
    handlers = []

    for _recipe_key, recipe_cls in RECIPE_REGISTRY.items():
        name = recipe_cls.deferred_handler

        if not name or name in seen:
            continue

        seen.add(name)
        handler = recipe_cls.deferred_handler_for(caller)

        if handler is not None:
            handlers.append((name, handler))

    return handlers


def get_recipes_for_skill(skill_key):
    """Get every recipe that unlocks under a given skill.

    Args:
        skill_key: Skill key to match against required_skill.

    Returns:
        list of (recipe_key, recipe_cls) tuples, in recipe_order -- which for
        one skill is a plain (required_level, name) ladder.
    """
    matches = [
        (key, cls)
        for key, cls in RECIPE_REGISTRY.items()
        if cls.required_skill == skill_key
    ]

    matches.sort(key=recipe_order)

    return matches


def get_material_summary(recipe_cls):
    """Summarize a recipe's consumable requirements, e.g. "2x rusty scrap metal".

    Args:
        recipe_cls: A BlackoutRecipe subclass.

    Returns:
        str. Comma-separated, order preserved from consumable_names, with
        repeated names collapsed into a "Nx" count. Empty string if the
        recipe declares no consumable_names.
    """
    if not recipe_cls.consumable_names:
        return ""

    counts = Counter(recipe_cls.consumable_names)
    seen = set()
    parts = []
    for mat_name in recipe_cls.consumable_names:
        if mat_name in seen:
            continue
        seen.add(mat_name)
        count = counts[mat_name]
        parts.append(f"{count}x {mat_name}" if count > 1 else mat_name)

    return ", ".join(parts)


def check_craftable(caller, recipe_key):
    """Determine if caller can craft the given recipe.

    Returns:
        Tuple of (can_craft: bool, reasons: list[str]). When can_craft is
        False, reasons contains human-readable descriptions of what's
        missing (skill, materials, or tools).
    """
    recipe_cls = get_recipe_class(recipe_key)

    if not recipe_cls:
        return False, ["Recipe not found."]

    reasons = []
    meets_skill = True
    if recipe_cls.required_skill:
        meets_skill = caller.skills.meets_prerequisite(
            recipe_cls.required_skill, recipe_cls.required_level
        )
        if not meets_skill:
            reasons.append(
                f"Requires {recipe_cls.required_skill} Lv.{recipe_cls.required_level}"
            )

    for mat_tag in set(recipe_cls.consumable_tags):
        owned = _count_tagged_items(caller, mat_tag, CONSUMABLE_TAG_CATEGORY)
        required = recipe_cls.consumable_tags.count(mat_tag)
        if owned < required:
            mat_name = (
                recipe_cls.consumable_names[recipe_cls.consumable_tags.index(mat_tag)]
                if recipe_cls.consumable_names
                else mat_tag
            )
            reasons.append(f"Missing {mat_name} ({owned}/{required})")

    for tool_tag in recipe_cls.tool_tags:
        if not _has_tool_available(caller, tool_tag):
            tool_name = (
                recipe_cls.tool_names[recipe_cls.tool_tags.index(tool_tag)]
                if recipe_cls.tool_names
                else tool_tag
            )
            reasons.append(f"Missing tool: {tool_name}")

    capacity_reason = _deferred_capacity_reason(caller, recipe_cls)
    if capacity_reason:
        reasons.append(capacity_reason)

    can_craft = meets_skill and not reasons

    return can_craft, reasons


def _deferred_capacity_reason(caller, recipe_cls):
    """Why a deferred recipe cannot be started right now, or None.

    A curing recipe is refusable for a reason no material count can see: every
    slot the character has is already holding something. Asked here rather than
    only at the moment of starting, because craft_batch re-checks craftability
    between items and a batch that sailed past a full chamber would report
    items crafted that were silently dropped.

    A recipe naming a handler the character does not have is refused too. It
    cannot be allowed to fall through to the immediate path, which would hand
    over a cured chuck with no wait at all.
    """
    if not recipe_cls.deferred_handler:
        return None

    handler = recipe_cls.deferred_handler_for(caller)
    if handler is None:
        return f"Cannot {recipe_cls.deferred_handler} right now."

    remaining = handler.capacity_remaining()
    if remaining <= 0:
        return f"No free {recipe_cls.deferred_handler} slot."

    return None


def get_max_craftable(caller, recipe_key):
    """Determine how many copies of recipe_key caller could craft back to
    back right now, given current materials, tools, and skill.

    Args:
        caller: The would-be crafter.
        recipe_key: Name of the recipe to evaluate.

    Returns:
        int: 0 if the recipe is unknown, the skill requirement isn't met, or
        a required tool is entirely unavailable (tools aren't consumed, so
        once one is present it never limits the count). Otherwise the
        largest N for which N crafts would not run out of any consumable
        material, capped at MAX_CRAFT_BATCH_SIZE.
    """
    recipe_cls = get_recipe_class(recipe_key)

    if not recipe_cls:
        return 0

    if recipe_cls.required_skill:
        meets_skill = caller.skills.meets_prerequisite(
            recipe_cls.required_skill, recipe_cls.required_level
        )
        if not meets_skill:
            return 0

    for tool_tag in recipe_cls.tool_tags:
        if not _has_tool_available(caller, tool_tag):
            return 0

    capacity = _deferred_capacity(caller, recipe_cls)
    if capacity is not None and capacity <= 0:
        return 0

    if not recipe_cls.consumable_tags:
        if capacity is not None:
            return min(capacity, MAX_CRAFT_BATCH_SIZE)
        return MAX_CRAFT_BATCH_SIZE

    per_craft_counts = []
    for mat_tag in set(recipe_cls.consumable_tags):
        required = recipe_cls.consumable_tags.count(mat_tag)
        owned = _count_tagged_items(caller, mat_tag, CONSUMABLE_TAG_CATEGORY)
        per_craft_counts.append(owned // required)

    max_craftable = min(per_craft_counts)

    if capacity is not None:
        max_craftable = min(max_craftable, capacity)

    return max(0, min(max_craftable, MAX_CRAFT_BATCH_SIZE))


def _deferred_capacity(caller, recipe_cls):
    """How many more of a deferred recipe may be started, or None if immediate.

    None and 0 are different answers and the caller must not conflate them:
    None means "this recipe has no capacity limit", 0 means "it has one and it
    is full". Returning 0 for an immediate recipe would make every craft in the
    game impossible.
    """
    if not recipe_cls.deferred_handler:
        return None

    handler = recipe_cls.deferred_handler_for(caller)
    if handler is None:
        return 0

    remaining = handler.capacity_remaining()

    return remaining


def get_recipe_display_data(caller, recipe_key):
    """Get all data needed to render a recipe detail view.

    Returns:
        dict with keys: name, description, category, required_skill,
        required_level, xp_reward, output_names, can_craft,
        meets_skill, material_details, tool_details.
        Returns None if recipe_key is not found.
    """
    recipe_cls = get_recipe_class(recipe_key)

    if not recipe_cls:
        return None

    material_details = []
    # dict.fromkeys, not set(): a set is unordered, so the same recipe could
    # list its materials in two different orders on two opens of the menu.
    # This keeps the order the recipe declares them in, which is the order
    # get_material_summary prints.
    for mat_tag in dict.fromkeys(recipe_cls.consumable_tags):
        mat_name = (
            recipe_cls.consumable_names[recipe_cls.consumable_tags.index(mat_tag)]
            if recipe_cls.consumable_names
            else mat_tag
        )
        owned = _count_tagged_items(caller, mat_tag, CONSUMABLE_TAG_CATEGORY)
        required = recipe_cls.consumable_tags.count(mat_tag)
        material_details.append(
            {
                "name": mat_name,
                "tag": mat_tag,
                "owned": owned,
                "required": required,
                "met": owned >= required,
            }
        )

    tool_details = []
    for tool_tag in recipe_cls.tool_tags:
        tool_name = (
            recipe_cls.tool_names[recipe_cls.tool_tags.index(tool_tag)]
            if recipe_cls.tool_names
            else tool_tag
        )
        available = _has_tool_available(caller, tool_tag)
        tool_details.append(
            {"name": tool_name, "tag": tool_tag, "available": available}
        )

    meets_skill = True
    if recipe_cls.required_skill:
        meets_skill = caller.skills.meets_prerequisite(
            recipe_cls.required_skill, recipe_cls.required_level
        )

    all_materials_met = all(m["met"] for m in material_details)
    all_tools_met = all(t["available"] for t in tool_details)
    can_craft = meets_skill and all_materials_met and all_tools_met

    output_names = (
        recipe_cls.output_names
        if recipe_cls.output_names
        else [prot.get("key", "item") for prot in recipe_cls.output_prototypes]
    )

    return {
        "name": recipe_cls.name,
        "description": getattr(recipe_cls, "description", recipe_cls.__doc__ or ""),
        "category": getattr(recipe_cls, "category", "Uncategorized"),
        "required_skill": recipe_cls.required_skill,
        "required_level": recipe_cls.required_level,
        "xp_reward": recipe_cls.xp_reward,
        "output_names": output_names,
        "can_craft": can_craft,
        "meets_skill": meets_skill,
        "material_details": material_details,
        "tool_details": tool_details,
    }


def _deliver_output(caller, obj):
    """
    Purpose: Hand one freshly crafted object to the crafter, or to the floor
    when it will not fit.

    Entry:
        caller - the crafting Character.
        obj    - one object from a recipe's result list. The contrib spawns
                 its outputs detached, so this is normally at location None.

    Exit/Returns:
        No return value. The object always ends up somewhere: carried, on the
        ground, or -- only when the crafter is nowhere at all -- left detached
        and logged.

    Module Globals:
        None.

    Methodology:
        move_to, not `obj.location = caller`. Direct assignment does not fire
        at_object_receive (CLAUDE.md gotcha 5), so a crafted item landed in
        contents with no inventory slot, merged into no existing stack, and
        published no state-feed snapshot. The 3D client's inventory pane
        therefore sat unchanged through an entire batch craft, and a later
        inventory.sync() -- triggered by some unrelated item movement -- was
        what eventually repaired the grid.

        The full-inventory case only becomes reachable now that the move runs
        the hooks: Character.at_pre_object_receive vetoes at 32/32 and move_to
        returns False, which would strand the object at location None. It goes
        to the room instead, which is where the player can still pick it up
        after clearing space. at_pre_object_receive has already said why.

    Notes/References:
        world/item_database.py ItemDef.create documents the same
        spawn-detached-then-move pattern and the same reason for it.

    Author: Nick Hobar
    Creation date: 08/17/2026
    """
    from evennia.utils import logger

    carried = obj.move_to(caller, quiet=True, move_type="craft")

    if carried:
        return

    room = caller.location

    if room is not None:
        dropped = obj.move_to(room, quiet=True, move_type="drop")

        if dropped:
            caller.msg(
                (f"You have no room for {obj.key}; it falls to the ground.",
                 _MSG_CRAFTING))
            return

    logger.log_err(
        f"perform_craft: could not deliver crafted {obj!r} to {caller!r} "
        f"or to {room!r}; it is left detached."
    )


def _publish_inventory(caller):
    """
    Purpose: Push one inventory snapshot once a craft has fully resolved.

    Entry:
        caller - the crafting Character. Called after outputs are delivered,
                 whether the craft succeeded or not.

    Exit/Returns:
        No return value. Never raises.

    Module Globals:
        None.

    Methodology:
        Delivering an output publishes a snapshot of its own, because move_to
        runs Character.at_object_receive. CONSUMING the inputs publishes
        nothing: BlackoutRecipe._consume_inputs either decrements `quantity`
        on a surviving stack or calls obj.delete(), and delete() assigns
        `self.location = None` directly rather than moving -- so
        at_object_leave never runs and the feed never hears about it. On a
        batch craft that is every single tick, which is why the pane kept
        showing scrap metal that had already been hammered into a chainbody.

        Published from here rather than from _consume_inputs because this is
        the point where the craft is over: inputs gone, outputs delivered, one
        snapshot that is true of both. It also covers a FAILED craft that
        still consumed its inputs (consume_on_fail), which no other hook in
        the path would report.

        Wrapped, because the batch loop calls this from a `delay` callback
        with no command frame around it -- a raise here would kill the
        remainder of the batch over a display concern.

    Notes/References:
        systems/interface/statefeed/events.py emit_inventory pre-checks the
        subscription, so this costs one getattr on a telnet-only server.

    Author: Nick Hobar
    Creation date: 08/17/2026
    """
    from evennia.utils import logger

    from systems.interface.statefeed import events as feed

    try:
        feed.emit_inventory(caller)
    except Exception:
        logger.log_trace()


def perform_craft(caller, recipe_key):
    """Gather all applicable materials and tools and execute the craft.

    This is the execution boundary between game code and the Evennia
    contrib. The contrib's recipe handles all validation, consumption,
    spawning, and messaging internally.

    The recipe class is instantiated and crafted directly rather than going
    through the contrib's craft() helper. craft() exists only to resolve a
    name to a class, and it does so by fuzzy prefix/substring matching -- with
    the registry we already hold the exact class, and the fuzzy path could
    silently resolve to a different recipe. CraftingRecipeBase.craft() is the
    public API craft() itself calls.

    Args:
        caller: The character performing the craft.
        recipe_key: Name of the recipe to execute.

    Returns:
        List of spawned objects on success, or None on failure.
    """
    recipe_cls = get_recipe_class(recipe_key)

    if not recipe_cls:
        return None

    # A deferred recipe does not finish here. Its handler consumes the input,
    # claims a slot and returns; the output is spawned whenever the player
    # comes back for it. Routed on the recipe's own attribute rather than on
    # its type, so this stays the only execution boundary and adding a second
    # deferred stage changes nothing in this module. See
    # BlackoutRecipe.deferred_handler.
    if recipe_cls.deferred_handler:
        return _start_deferred_craft(caller, recipe_cls)

    consumables = [
        obj
        for obj in caller.contents
        if obj.tags.get(category=CONSUMABLE_TAG_CATEGORY, return_list=True)
    ]

    tool_candidates = _iter_candidate_items(caller, include_location=True)
    tools = [
        obj
        for obj in tool_candidates
        if obj.tags.get(category=TOOL_TAG_CATEGORY, return_list=True)
    ]

    recipe_inputs = tools + consumables
    recipe = recipe_cls(caller, *recipe_inputs)
    result = recipe.craft(raise_exception=False)

    if result:
        for obj in result:
            _deliver_output(caller, obj)

        # Reported on the recipe KEY, which is the recipe's `name` and the
        # same string a blueprint declares as `craft:rusty scrap axe`. The
        # spawned object's key is an item name and can differ.
        notify_quests(caller, quest_constants.ACTION_CRAFT, recipe_key)

    _publish_inventory(caller)

    return result


def _start_deferred_craft(caller, recipe_cls):
    """Hand a deferred recipe to its handler and report what happened.

    Returns an empty list when the recipe was successfully STARTED, and None
    when it was refused. Both are falsy, which is deliberate: nothing was
    produced either way, so a caller asking "did I get items" gets the right
    answer without having to know the stage is timed. The distinction is there
    for a caller that does care -- `[] is not None`.

    No quest notification fires here. A player who seals meat into a chamber
    has not crafted anything yet, so ACTION_CRAFT is the handler's to fire when
    the cured meat is actually collected.
    """
    from evennia.utils import logger

    handler = recipe_cls.deferred_handler_for(caller)

    if handler is None:
        logger.log_err(
            f"[CRAFTING] {recipe_cls.name!r} names deferred handler "
            f"{recipe_cls.deferred_handler!r}, which {caller.key} does not "
            f"have; refusing rather than crafting it immediately."
        )
        return None

    started = handler.start(recipe_cls)

    if not started:
        return None

    return []
