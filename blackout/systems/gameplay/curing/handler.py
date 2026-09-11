"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: CuringHandler — one character's in-progress cures.

Why the character and not the chamber
-------------------------------------
``systems/gameplay/spawning/teardown.py`` destroys every facility with its room
on a map rebuild, DEPTH-FIRST, so a chamber's contents die before the chamber
does. Meat left in a chamber would be destroyed by
``clean_and_reload_all_maps.ps1`` -- an operator action, not an accident. The
bank reached the same conclusion for the same reason: the terminal on the map is
UI and the vault hangs off the character.

Two further reasons the chamber could not own this even if it survived: a
chamber is shared, so it would need per-player partitioning inside it anyway;
and slot COUNT is a function of the player's Curing level, which the chamber
cannot know.

Why no Script, no tick phase and no sweep
-----------------------------------------
A slot stores an ABSOLUTE ``time.time()`` deadline and readiness is computed on
read. Nothing runs between starting a cure and asking about it.

``systems/gameplay/spawning/respawn.py`` is the same problem shape and DOES run a
sweeping Script, so the difference is worth being precise about: an NPC must
reappear whether or not anyone is watching, because the world changes. A cure
changes nothing until the player collects it. So every argument in that module
-- needing a queue you can query for dedupe, one sweep beating one deferLater
per entry -- stops applying here, and the cheapest correct design is no timer
at all.

It also means a cure that came due while the server was down is simply due,
with no catch-up pass. ``time.monotonic()`` could not be used for that: its
epoch is process-relative and meaningless after a restart.

Persistence shape
-----------------
``character.db._curing_slots`` is a list of plain dicts::

    {"recipe": "mutant raider cured chuck", "due_at": 1757600000.0}

Dicts inside a LIST, never tuples, for the reason respawn.py documents:
Evennia's ``from_pickle`` passes a tuple itself as the saver parent and a tuple
has no ``_save_tree``, so a mutable nested in a tuple raises on the first
in-place edit.

The stored value is a recipe KEY, not a module path -- the same indirection
``notify_quests`` and a blueprint's ``craft:rusty scrap axe`` already rely on.
It is still a string in a database row, so ``collect`` FREES a slot whose
recipe no longer resolves rather than passing the bad key on. EvMenu is the
cautionary tale CLAUDE.md cites: ``mod_import`` returns None for a path that
does not resolve and ``_parse_menudata`` reads ``__dict__`` off it unchecked.
"""



import time

from evennia.utils import logger

from systems.gameplay.progression.skills import constants as skill_constants
from systems.interface.statefeed import constants as feed_const

from . import constants as curing_constants



# Private constant definitions

# Every line this module sends a player is crafting, so the routing tag is
# bound once here rather than repeated at every call site. Copied from
# blackout_recipe.py deliberately: a cure is a craft as far as the player's
# message tabs are concerned, and a cured chuck arriving in a different tab
# from a rendered one would read as a bug.
#
# The SERVER says what a line IS; the client decides which tab shows it.
_MSG_CRAFTING = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_CRAFTING}



class CuringHandler:
    """
    Purpose: Owns one character's curing slots -- starting, reporting, and
    collecting.

    Entry:
        Constructed with the character it belongs to. Attached as
        `character.curing` by typeclasses/characters.py.

    Exit/Returns:
        No conditions.

    Module Globals:
        curing_constants read throughout.

    Methodology:
        The ONE owner of db._curing_slots. Nothing outside this class reads or
        writes that attribute -- the chamber's commands, the skills panel and
        any future statefeed channel all go through the read API below. Three
        modules owning db.active_quests is how the android's dialogue came to
        print "talk:tester: 0/True" at players, and this is the same fact in
        the same shape.

    Notes/References:
        Mirrors systems/gameplay/banking/handler.py's construction and its
        lazy statefeed import.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """

    def __init__(self, obj):
        self.obj = obj


    # ─── Storage ─────────────────────────────────────────────────────────

    def _slots(self) -> list:
        """
        Purpose: The raw stored slot list, created empty on first access.

        Entry:
            No conditions.

        Exit/Returns:
            Returns the live list. Mutating it writes through to the database,
            because Evennia hands back a _SaverList.

        Module Globals:
            curing_constants.CURING_SLOTS_ATTR read.

        Methodology:
            Lazily initialised rather than seeded at character creation, so an
            account that predates Curing needs no migration -- the same reason
            the cooldown handler treats an unknown cooldown as ready.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        attr_name = curing_constants.CURING_SLOTS_ATTR
        stored = self.obj.attributes.get(attr_name, default=None)

        if stored is None:
            self.obj.attributes.add(attr_name, [])
            stored = self.obj.attributes.get(attr_name)

        return stored


    # ─── Reading ─────────────────────────────────────────────────────────

    def slot_total(self) -> int:
        """
        Purpose: How many cures this character may run at once.

        Entry:
            No conditions.

        Exit/Returns:
            Returns an integer of 1 or more.

        Module Globals:
            None.

        Methodology:
            Reads the live Curing level and asks the constants table. Computed
            on every call rather than cached onto the character, so levelling
            Curing opens the slot immediately and no stored count can disagree
            with the skill -- the same reason a class attribute beats an
            Attribute for a typeclass path.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        level = self.obj.skills.get_level(skill_constants.CURING_SKILL_KEY)
        total = curing_constants.slots_for_level(level)

        return total


    def slot_used(self) -> int:
        """
        Purpose: How many slots currently hold a cure, finished or not.

        Entry:
            No conditions.

        Exit/Returns:
            Returns an integer, 0 or more.

        Module Globals:
            None.

        Methodology:
            A FINISHED cure still occupies its slot. That is the design
            decision the stage rests on: slots free on collection, not on
            completion, so coming back to the chamber is what the second slot
            at level 10 is actually worth.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        slots = self._slots()

        return len(slots)


    def has_free_slot(self) -> bool:
        """Whether another cure may be started right now."""
        remaining = self.capacity_remaining()

        return remaining > 0


    def capacity_remaining(self) -> int:
        """
        Purpose: How many more cures may be started right now.

        Entry:
            No conditions.

        Exit/Returns:
            Returns an integer, never below zero.

        Module Globals:
            None.

        Methodology:
            Half of the two-method protocol BlackoutRecipe.deferred_handler
            documents, and the name is generic for that reason -- crafting_service
            asks this without knowing it is talking about curing, which is what
            keeps the craft menu's "craft all" cap and its refusal message
            working for a stage that module knows nothing about.

            Clamped at zero rather than allowed negative: slot_total shrinks if
            a character's Curing level ever drops, and a negative capacity would
            read as "less than full" to a caller doing arithmetic on it.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        free = self.slot_total() - self.slot_used()

        if free < 0:
            return 0

        return free


    def pending(self) -> list:
        """
        Purpose: Every cure in progress, as a readable report.

        Entry:
            No conditions.

        Exit/Returns:
            Returns a list of dicts, one per occupied slot, each carrying
            recipe_key, item_name, state and remaining (seconds, 0 when
            ready). Declaration order, which is start order.

        Module Globals:
            curing_constants read.

        Methodology:
            The read API every other module uses. It resolves the recipe key
            to a display name HERE rather than handing out raw keys, so the
            chamber's commands and the skills panel cannot disagree about what
            a slot is called -- the arrangement detail.py uses beside
            objective_lines.

            A slot whose recipe no longer resolves is reported with its key as
            the name rather than dropped, because a report that silently omits
            a slot the player can see the effects of is worse than one naming
            something odd.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        now = time.time()
        report = []

        for slot in self._slots():
            entry = self._describe_slot(slot, now)
            report.append(entry)

        return report


    def _describe_slot(self, slot: dict, now: float) -> dict:
        """
        Purpose: Turn one stored slot into one report entry.

        Entry:
            slot is a stored slot dict. now is a time.time() reading.

        Exit/Returns:
            Returns a dict with recipe_key, item_name, state and remaining.

        Module Globals:
            curing_constants read.

        Methodology:
            Split out of pending() to keep that routine a loop, and because
            this is the one place a missing recipe is tolerated rather than
            refused.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        recipe_key = slot[curing_constants.SLOT_RECIPE_KEY]
        due_at = slot[curing_constants.SLOT_DUE_AT_KEY]
        recipe_cls = _resolve_recipe(recipe_key)

        if recipe_cls is None:
            item_name = recipe_key
        else:
            item_name = recipe_cls.name

        remaining = due_at - now
        if remaining <= 0:
            remaining = 0
            state = curing_constants.SLOT_STATE_READY
        else:
            state = curing_constants.SLOT_STATE_CURING

        return {
            "recipe_key": recipe_key,
            "item_name": item_name,
            "state": state,
            "remaining": remaining,
        }


    def ready_keys(self) -> list:
        """Recipe keys of every slot whose cure has finished, in start order."""
        ready_state = curing_constants.SLOT_STATE_READY
        finished = [
            entry["recipe_key"]
            for entry in self.pending()
            if entry["state"] == ready_state
        ]

        return finished


    def ready_count(self) -> int:
        """How many cures are finished and waiting to be collected."""
        finished = self.ready_keys()

        return len(finished)


    def status_lines(self) -> list:
        """
        Purpose: The whole slot display, rendered, for any screen that shows it.

        Entry:
            No conditions. Safe with nothing curing.

        Exit/Returns:
            Returns a list of display lines: a header naming how many slots are
            spoken for, then one indented line per occupied slot. Never empty
            -- a player with an idle chamber is told they have room, which is
            the answer to "why can I not start another one" before they ask it.

        Module Globals:
            curing_constants read.

        Methodology:
            The handler renders this, not the screens that show it. Two screens
            already display it -- the chamber's craft menu and the dossier's
            Processing band -- and a third is one caller away; each assembling
            its own would be three owners of one fact, which is how the
            android's dialogue came to print "talk:tester: 0/True" at players.

            What a CALLER owns is whether to show the block at all: the craft
            menu always does because the player is standing at the chamber, the
            dossier only when something is pending because an idle stage is not
            news on a screen every player reads.

            Built from pending(), so a slot the display shows and a slot
            `collect` acts on are the same list read the same way.

        Notes/References:
            The per-slot wording is MSG_SLOT_WORKING / MSG_SLOT_DONE, which
            CmdCollect already prints for a chamber with nothing ready.

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        entries = self.pending()
        ready = self._count_ready(entries)
        header = self._status_header(len(entries), ready)
        lines = [header]

        for entry in entries:
            line = self._slot_line(entry)
            lines.append(curing_constants.SLOT_LINE_INDENT + line)

        return lines


    def _status_header(self, used: int, ready: int) -> str:
        """The "Curing slots: 1/2" line, coloured when something is waiting."""
        total = self.slot_total()

        if ready > 0:
            return curing_constants.MSG_SLOT_HEADER_READY.format(
                used=used, total=total, ready=ready
            )

        return curing_constants.MSG_SLOT_HEADER.format(used=used, total=total)


    def _slot_line(self, entry: dict) -> str:
        """One occupied slot, as either a countdown or a "ready"."""
        is_ready = entry["state"] == curing_constants.SLOT_STATE_READY

        if is_ready:
            return curing_constants.MSG_SLOT_DONE.format(item=entry["item_name"])

        remaining = curing_constants.format_remaining(entry["remaining"])

        return curing_constants.MSG_SLOT_WORKING.format(
            item=entry["item_name"], remaining=remaining
        )


    @staticmethod
    def _count_ready(entries: list) -> int:
        """How many of an already-built pending() report are finished."""
        ready_state = curing_constants.SLOT_STATE_READY
        finished = [
            entry for entry in entries if entry["state"] == ready_state
        ]

        return len(finished)


    # ─── Writing ─────────────────────────────────────────────────────────

    def start(self, recipe_cls) -> bool:
        """
        Purpose: Begin a cure, consuming its input and claiming a slot.

        Entry:
            recipe_cls is a CuringRecipe subclass. The caller has already
            checked the character is at a chamber.

        Exit/Returns:
            Returns True when the cure started. Returns False without changing
            anything when no slot is free -- every other refusal (level, a
            missing input) is raised through the recipe's own validation and
            messaged by it.

        Module Globals:
            curing_constants read.

        Methodology:
            The input is consumed by the RECIPE, through the normal
            pre_craft/_consume_inputs path, so the level gate, the stackable
            unit accounting and the "you aren't carrying" message all stay in
            one place and a cure cannot be started on meat the player does not
            have. What this routine adds is the slot and the deadline.

            Order matters: the slot check comes FIRST, because validating and
            consuming the input before discovering there is nowhere to put it
            would eat the meat for nothing.

        Notes/References:
            systems/gameplay/curing/recipe.py explains why a cure is not a
            craft with a longer timer.

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        if not self.has_free_slot():
            return False

        consumed = self._consume_input(recipe_cls)
        if not consumed:
            return False

        due_at = time.time() + recipe_cls.cure_seconds
        slot = {
            curing_constants.SLOT_RECIPE_KEY: recipe_cls.name,
            curing_constants.SLOT_DUE_AT_KEY: due_at,
        }
        self._slots().append(slot)

        started = curing_constants.MSG_CURE_STARTED.format(item=recipe_cls.name)
        self.obj.msg((started, _MSG_CRAFTING))

        return True


    def _consume_input(self, recipe_cls) -> bool:
        """
        Purpose: Run a recipe's validation and consumption, and nothing else.

        Entry:
            recipe_cls is a CuringRecipe subclass.

        Exit/Returns:
            Returns True when the input was validated and consumed. Returns
            False when validation refused, having already messaged the player.

        Module Globals:
            None.

        Methodology:
            Instantiates the recipe over the character's carried materials,
            then calls pre_craft (which gates on level and matches the input)
            followed by the recipe's own _consume_inputs. It deliberately does
            NOT call craft(): that would spawn the output immediately, which is
            the entire thing a cure is not.

            Tools are passed in as well as consumables even though the chamber
            has already been established, because pre_craft validates
            tool_tags and would refuse a recipe whose chamber it cannot see.

        Notes/References:
            CraftingValidationError is the contrib's own refusal signal and is
            raised AFTER the recipe has messaged the crafter, so it is caught
            and swallowed here rather than reported again.

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        from evennia.contrib.game_systems.crafting.crafting import (
            CraftingValidationError,
        )

        inputs = _craft_inputs(self.obj)
        recipe = recipe_cls(self.obj, *inputs)

        try:
            recipe.pre_craft()
        except CraftingValidationError:
            return False

        recipe._consume_inputs()
        self._publish_state()

        return True


    def collect(self) -> list:
        """
        Purpose: Take every finished cure out of the chamber.

        Entry:
            No conditions. Safe with no slots and with none finished.

        Exit/Returns:
            Returns the list of spawned objects, empty when nothing was ready.
            Slots whose recipe no longer resolves are freed and reported
            through the log, not through this return.

        Module Globals:
            curing_constants read.

        Methodology:
            Walks the stored list BACKWARDS and pops by index. Forwards with a
            pop would skip the entry after each removal, and building a new
            list would replace the _SaverList Evennia hands back and lose the
            write-through.

            XP is paid here rather than at start, because the XP is for the
            cured meat and a player who starts a cure has not made anything
            yet.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        now = time.time()
        slots = self._slots()
        delivered = []

        for index in range(len(slots) - 1, -1, -1):
            slot = slots[index]
            is_due = slot[curing_constants.SLOT_DUE_AT_KEY] <= now

            if not is_due:
                continue

            spawned = self._finish_slot(slot)
            slots.pop(index)

            if spawned:
                delivered.extend(spawned)

        delivered.reverse()

        if delivered:
            self._publish_state()

        return delivered


    def _finish_slot(self, slot: dict) -> list:
        """
        Purpose: Spawn one finished cure's output and pay its XP.

        Entry:
            slot is a stored slot dict whose deadline has passed.

        Exit/Returns:
            Returns the spawned objects, or an empty list when the slot's
            recipe no longer resolves.

        Module Globals:
            curing_constants read.

        Methodology:
            Delivery goes through crafting_service._deliver_output, which is
            what makes the output occupy an inventory slot and fall to the
            ground when the grid is full -- create(location=) does not fire
            at_object_receive, so a hand-rolled delivery would leave cured meat
            in the character's contents with no slot and publish nothing.

            An unresolvable recipe key returns empty having logged. The slot is
            popped by the caller either way, which is the point: a rename must
            cost the player one item, not a slot they can never reuse.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        from systems.gameplay.crafting import crafting_service

        recipe_key = slot[curing_constants.SLOT_RECIPE_KEY]
        recipe_cls = _resolve_recipe(recipe_key)

        if recipe_cls is None:
            logger.log_err(
                f"[CURING] {self.obj.key} holds a slot for unknown recipe "
                f"{recipe_key!r}; freeing it."
            )
            self.obj.msg((curing_constants.MSG_RECIPE_GONE, _MSG_CRAFTING))
            return []

        spawned = _spawn_outputs(recipe_cls)

        for obj in spawned:
            crafting_service._deliver_output(self.obj, obj)

        ready = curing_constants.MSG_CURE_READY.format(item=recipe_cls.name)
        self.obj.msg((ready, _MSG_CRAFTING))

        if recipe_cls.xp_reward > 0:
            self.obj.skills.add_xp(
                recipe_cls.required_skill, recipe_cls.xp_reward
            )

        _notify_craft(self.obj, recipe_key)

        return spawned


    def _publish_state(self) -> None:
        """
        Purpose: Tell a graphical client what a cure just changed.

        Entry:
            No conditions.

        Exit/Returns:
            No conditions. Never raises.

        Module Globals:
            None.

        Methodology:
            Two channels, because starting or collecting a cure changes two
            things a client is already drawing: the INVENTORY, which lost meat
            or gained it, and the DOSSIER, whose Processing band is the only
            place a full chamber is visible away from the chamber. Equipment's
            handler makes the same pair of calls for the same reason -- a band
            reachable only from `score` is one a client shows stale.

            emit_summary gates on the subscriber count itself, so this costs
            nothing on a telnet-only server; and both ends of a cure are paced
            by the player, never by the tick, so there is no rate to bound.

            Imported inside the method, copying BankHandler._publish_inventory
            verbatim and for its stated reason: this module is reached from
            typeclass import time through the character's handlers, and a
            module-scope import of the feed would couple the two systems'
            import order.

        Notes/References:
            systems/gameplay/banking/handler.py, items/equipment/handler.py.

        Author: Nick Hobar
        Creation date: 09/11/2026
        """
        from systems.interface.statefeed import events as feed

        try:
            feed.emit_inventory(self.obj)
            feed.emit_summary(self.obj)
        except Exception:
            logger.log_trace()



def _resolve_recipe(recipe_key: str):
    """
    Purpose: Look up a stored recipe key, tolerating one that no longer exists.

    Entry:
        recipe_key is a string read out of a stored slot.

    Exit/Returns:
        Returns the recipe class, or None when the key names nothing.

    Module Globals:
        None.

    Methodology:
        Imported inside the function. The registry imports every configured
        recipe module, and those import CuringRecipe out of this package -- a
        module-scope import here would close the ring the quest system's
        loader/quests split exists to prevent.

    Notes/References:
        CLAUDE.md, "The quest system": quests.py must never import loader.py.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    from systems.gameplay.crafting import crafting_service

    recipe_cls = crafting_service.get_recipe_class(recipe_key)

    return recipe_cls



def _craft_inputs(character) -> list:
    """
    Purpose: Everything on or around a character a recipe may consume or use.

    Entry:
        character is an Evennia Character.

    Exit/Returns:
        Returns a list of Objects: tools first, then carried consumables.

    Module Globals:
        None.

    Methodology:
        Reuses crafting_service's own definition of where crafting looks --
        materials carried or equipped, tools additionally in the room -- rather
        than scanning contents here. That module calls itself "the single
        definition of where crafting looks" precisely because three open-coded
        copies had already drifted apart.

    Notes/References:
        systems/gameplay/crafting/crafting_service.py perform_craft.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    from systems.gameplay.crafting import crafting_service
    from systems.gameplay.crafting.constants import (
        CONSUMABLE_TAG_CATEGORY,
        TOOL_TAG_CATEGORY,
    )

    consumables = [
        obj
        for obj in character.contents
        if obj.tags.get(category=CONSUMABLE_TAG_CATEGORY, return_list=True)
    ]

    candidates = crafting_service._iter_candidate_items(
        character, include_location=True
    )
    tools = [
        obj
        for obj in candidates
        if obj.tags.get(category=TOOL_TAG_CATEGORY, return_list=True)
    ]

    return tools + consumables



def _spawn_outputs(recipe_cls) -> list:
    """
    Purpose: Build a finished recipe's output objects, detached.

    Entry:
        recipe_cls is a recipe whose output_item_keys resolved at import.

    Exit/Returns:
        Returns a list of freshly created Objects with no location.

    Module Globals:
        None.

    Methodology:
        Spawns from the recipe's own output_prototypes, which
        BlackoutRecipe.__init_subclass__ rendered from ITEM_DB -- so a cured
        chuck collected from a chamber is the same database row as one the
        craft menu would have produced.

        Created detached and moved by the caller, which is CLAUDE.md gotcha 5:
        create_object(location=) does not fire at_object_receive, and that hook
        is what registers an item in an inventory slot and merges stackables.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    from evennia.prototypes.spawner import spawn

    prototypes = recipe_cls.output_prototypes
    spawned = spawn(*prototypes)

    return list(spawned)


def _notify_craft(character, recipe_key: str) -> None:
    """
    Purpose: Fire the quest system's craft hook for a collected cure.

    Entry:
        character is the collector. recipe_key is the recipe's name, which is
        the stable key a QuestBlueprint spells as `craft:<recipe name>`.

    Exit/Returns:
        No conditions. notify_quests tolerates an actor with no quest handler
        and never raises.

    Module Globals:
        None.

    Methodology:
        Fired on COLLECTION, not on starting the cure. A player who seals meat
        into a chamber has not crafted anything yet, and an objective that
        advanced on the start would count a cure the player never came back
        for. crafting_service._start_deferred_craft deliberately fires nothing
        for the same reason.

        Imported inside the function, like every other cross-system reach in
        this module, so the handler stays importable from typeclass import
        time.

    Notes/References:
        CLAUDE.md: "Game systems call notify_quests, never update_progress."

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    from systems.gameplay.quests import constants as quest_constants
    from systems.gameplay.quests.hooks import notify_quests

    notify_quests(character, quest_constants.ACTION_CRAFT, recipe_key)
