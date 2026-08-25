"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: Every effect a moderator may apply to the live world, as plain
             functions over (actor, target, ...).

             Each returns a (succeeded, message) pair and raises nothing. The
             caller decides what to do with the message -- the egg's menu
             prints it as a node header, a command would msg() it -- so the
             effects stay callable from a test with no EvMenu and no session.

             Nothing here checks permissions. That gate belongs on the ONE
             surface a moderator reaches these through (CmdEgg's lock), for
             the same reason the quest system puts its fan-out in one place: a
             check repeated per effect is a check that will be forgotten on
             the ninth one.
"""

from evennia.contrib.grid.xyzgrid.xyzroom import XYZRoom
from evennia.utils import logger

from items.equipment.constants import MAX_INVENTORY_SLOTS
from systems.progression.skills.registry import SKILL_REGISTRY
from systems.quests.loader import GLOBAL_QUEST_REGISTRY
from world.item_database import ITEM_DB
from world.npc_database import NPC_DB
from world.maps.manifest import ManifestError, load_entries, zcoords_of

from systems.devtools import constants as dev_constants


# ─── Private helper routines ─────────────────────────────────────────────────

def _audit(actor, action: str, target, detail: str) -> None:
    """
    Purpose: Record one moderator action in the server log.

    Entry:
        actor is the moderator's Character. action is a member of
        dev_constants.MODERATOR_ACTIONS. target is the affected object, or
        None for an action that names no object. detail is free text.

    Exit/Returns:
        No return value. Writes one info line to the server log.

    Module Globals:
        dev_constants.AUDIT_LINE_TEMPLATE, AUDIT_LOG_PREFIX, AUDIT_NO_TARGET,
        MODERATOR_ACTIONS read.

    Methodology:
        An unknown verb is logged rather than raised. This runs AFTER the
        effect has already landed, so raising here would report a failure for
        something that succeeded -- exactly the inversion notify_quests avoids
        by dropping an undocumented verb loudly and returning.

    Notes/References:
        Every effect in this module calls this. A moderator tool without an
        audit trail is a tool no incident can be reviewed against.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    known = action in dev_constants.MODERATOR_ACTIONS

    if not known:
        logger.log_err(f"{dev_constants.AUDIT_LOG_PREFIX} unknown action {action!r}")

    actor_name = getattr(actor, "key", repr(actor))
    target_name = dev_constants.AUDIT_NO_TARGET

    if target is not None:
        target_name = getattr(target, "key", repr(target))

    line = dev_constants.AUDIT_LINE_TEMPLATE.format(
        prefix=dev_constants.AUDIT_LOG_PREFIX,
        actor=actor_name,
        action=action,
        target=target_name,
        detail=detail,
    )
    logger.log_info(line)


def _free_slot_count(target) -> int:
    """
    Purpose: Report how many empty inventory slots a target has.

    Entry:
        target is a Character with an `inventory` handler.

    Exit/Returns:
        Returns an integer >= 0. A target with no inventory handler yields 0,
        so a spawn at one refuses rather than raising.

    Module Globals:
        MAX_INVENTORY_SLOTS read.

    Notes/References:
        Read through the handler's own count_used rather than by counting
        contents: an equipped item is in contents but occupies no grid slot.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    handler = getattr(target, "inventory", None)

    if handler is None:
        return 0

    used = handler.count_used()
    free = MAX_INVENTORY_SLOTS - used

    return max(free, 0)


def _grant_stack(target, item_def, count: int) -> int:
    """
    Purpose: Deliver a stackable item as ONE object carrying `count`.

    Entry:
        target is the receiving Character. item_def is a stackable ItemDef.
        count is already clamped into the spawn bounds.

    Exit/Returns:
        Returns the quantity actually delivered: `count`, or 0 when the grid
        had no room for it.

    Module Globals:
        None.

    Methodology:
        Spawn DETACHED, ask the grid whether it would take the object, then
        move. can_accept is the same rule at_pre_object_receive applies, so
        asking it first is what keeps the "inventory full" message on the
        MODERATOR's screen -- letting the move fail instead prints it to the
        target, who did not do anything.

    Notes/References:
        The object is deleted on refusal. A detached, unowned item row is how
        a database fills with things no player can ever see.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    obj = item_def.create(home=target, quantity=count)
    accepted = target.inventory.can_accept(obj)

    if not accepted:
        obj.delete()

        return 0

    obj.move_to(target, quiet=True)

    return count


def _grant_copies(target, item_def, count: int) -> int:
    """
    Purpose: Deliver a non-stackable item as `count` separate objects.

    Entry:
        target is the receiving Character. item_def is a non-stackable
        ItemDef. count is already clamped into the spawn bounds.

    Exit/Returns:
        Returns how many were delivered -- `count`, or the number of free
        slots when that is smaller. Zero when the grid is full.

    Module Globals:
        None.

    Methodology:
        Each copy consumes exactly one slot, so the ceiling is knowable before
        the first spawn. Computing it up front means a partial delivery is
        reported as a clamp rather than discovered as a failed move halfway
        through.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    free = _free_slot_count(target)
    granted = min(count, free)
    made = 0

    while made < granted:
        item_def.create(location=target, home=target)
        made += 1

    return granted


def _map_anchor_room(zcoord: str):
    """
    Purpose: Resolve the room a teleport to `zcoord` should land in.

    Entry:
        zcoord names a map that the manifest lists.

    Exit/Returns:
        Returns a room object, or None when the map has no rooms built.

    Module Globals:
        dev_constants.MAP_ANCHOR_XY read.

    Methodology:
        Prefer the anchor tile, then fall back to the lowest-id room on the
        map. The anchor is a CONVENTION -- both shipped maps put an entrance
        at (0, 0), and world/respawn.py already anchors the death loop there
        -- and the fallback is what keeps it a convention rather than a rule a
        future map has to know about to be reachable.

    Notes/References:
        get_xyz raises rather than returning None: DoesNotExist on a grid that
        was never built, MultipleObjectsReturned when a rebuild left duplicate
        rows. Both mean "not resolvable here", so both fall through.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    anchor_x, anchor_y = dev_constants.MAP_ANCHOR_XY

    try:
        anchor = XYZRoom.objects.get_xyz(xyz=(anchor_x, anchor_y, zcoord))

        return anchor
    except Exception:
        logger.log_info(
            f"{dev_constants.AUDIT_LOG_PREFIX} no anchor tile "
            f"({anchor_x},{anchor_y}) on map '{zcoord}'; using any room."
        )

    rooms = XYZRoom.objects.filter_xyz(xyz=("*", "*", zcoord)).order_by("id")
    fallback = rooms.first()

    return fallback


# ─── Audit ───────────────────────────────────────────────────────────────────

def audit_inspect(actor, target) -> None:
    """
    Purpose: Record that one moderator read another character's dossier.

    Entry:
        actor is the moderator. target is the character that was read.

    Exit/Returns:
        No return value.

    Module Globals:
        dev_constants.ACTION_INSPECT read.

    Methodology:
        The one public door onto _audit, and it exists for exactly one caller:
        systems/devtools/inspect.py, which changes nothing and so has no
        business importing a module of writers for anything else.

    Notes/References:
        A read is audited because "who looked at whom" is what a moderation
        review actually asks. Nothing else in this module audits without also
        acting.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    _audit(actor, dev_constants.ACTION_INSPECT, target, "dossier read")


# ─── God mode ────────────────────────────────────────────────────────────────

def godmode_enabled(target) -> bool:
    """
    Purpose: Report whether a character is currently ignoring damage.

    Entry:
        target is any object. One without db attributes reads as False.

    Exit/Returns:
        Returns True when god mode is on.

    Module Globals:
        dev_constants.GODMODE_ATTR read.

    Notes/References:
        This is the ONE reader of the flag besides CombatEntity.at_damage, and
        both reach it through GODMODE_ATTR rather than naming the attribute.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    attributes = getattr(target, "db", None)

    if attributes is None:
        return False

    stored = getattr(attributes, dev_constants.GODMODE_ATTR, False)

    return bool(stored)


def set_godmode(actor, target, enabled: bool) -> tuple:
    """
    Purpose: Turn a character's damage immunity on or off.

    Entry:
        actor is the moderator. target is the affected Character. enabled is
        the wanted state, not a delta.

    Exit/Returns:
        Returns (True, message). Never fails: writing an attribute on a live
        object has no failure mode this function could report.

    Module Globals:
        dev_constants.GODMODE_ATTR, MSG_GODMODE_ON, MSG_GODMODE_OFF read.

    Methodology:
        Takes the wanted state rather than toggling, so the caller that
        rendered "God mode: ON" and the write that follows cannot disagree
        about what the option does.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    target.attributes.add(dev_constants.GODMODE_ATTR, bool(enabled))
    target_name = target.key

    if enabled:
        message = dev_constants.MSG_GODMODE_ON.format(target=target_name)
    else:
        message = dev_constants.MSG_GODMODE_OFF.format(target=target_name)

    _audit(actor, dev_constants.ACTION_GODMODE, target, f"enabled={bool(enabled)}")

    return True, message


# ─── Restore ─────────────────────────────────────────────────────────────────

def restore(actor, target) -> tuple:
    """
    Purpose: Return a character to full health and out of combat.

    Entry:
        actor is the moderator. target is a Character carrying CombatEntity.

    Exit/Returns:
        Returns (True, message) reporting the HP restored to.

    Module Globals:
        dev_constants.MSG_RESTORE_DONE read.

    Methodology:
        Refresh the cap from Fortitude BEFORE topping up, so a character whose
        Fortitude moved without a level-up hook firing is healed to the right
        number rather than to a stale one.

        Assignment goes through the `hp` property, never db.hp: the setter is
        what clamps and what publishes the vitals event the 3D client's health
        bar reads. Character.respawn documents the same trap.

        HP is the only depletable resource Blackout has. Items carry no
        durability, gathering nodes do not exhaust, auras hold no charge pool.
        When a second one appears, it is restored here.

    Notes/References:
        Every step is guarded. A moderator healing someone mid-fight must not
        be able to strand them by tripping over a missing handler.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    skills = getattr(target, "skills", None)

    if skills is not None:
        try:
            skills.sync_max_hp_from_fortitude()
        except Exception as exc:
            logger.log_err(f"{dev_constants.AUDIT_LOG_PREFIX} hp sync failed: {exc!r}")

    target.hp = target.max_hp

    try:
        target.leave_combat()
    except Exception as exc:
        logger.log_err(f"{dev_constants.AUDIT_LOG_PREFIX} leave_combat failed: {exc!r}")

    message = dev_constants.MSG_RESTORE_DONE.format(
        target=target.key,
        hp=target.hp,
        max_hp=target.max_hp,
    )
    _audit(actor, dev_constants.ACTION_RESTORE, target, f"hp={target.hp}")

    return True, message


# ─── Item spawning ───────────────────────────────────────────────────────────

def item_keys() -> list:
    """
    Purpose: Name every item the spawner can produce, in a stable order.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a sorted list of ITEM_DB keys.

    Module Globals:
        ITEM_DB read.

    Notes/References:
        Derived from the registry, never tabulated. Adding an ItemDef must put
        it in the moderator's list with no edit here -- that is the whole
        contract world/item_database.py exists to provide.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    keys = sorted(ITEM_DB.keys())

    return keys


def grant_item(actor, target, item_key: str, quantity: int) -> tuple:
    """
    Purpose: Spawn one or more of an item straight into a character's grid.

    Entry:
        actor is the moderator. target is the receiving Character. item_key
        names an entry in ITEM_DB. quantity is what was asked for, before
        clamping.

    Exit/Returns:
        Returns (succeeded, message). Failure means the item does not exist,
        or nothing at all could be delivered.

    Module Globals:
        ITEM_DB read. dev_constants MIN_SPAWN_QUANTITY, MAX_SPAWN_QUANTITY,
        MSG_SPAWN_* read.

    Methodology:
        A stackable request becomes one object carrying the count; a
        non-stackable one becomes N objects. The split lives in the two
        private helpers because the failure modes differ: a stack needs one
        slot or an existing pile, N copies need N slots.

        Delivering FEWER than asked is a success with a note, not a failure.
        A moderator who asked for 40 swords and got the 12 that fit has been
        served; refusing outright would just make them ask again for 12.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    item_def = ITEM_DB.get(item_key)

    if item_def is None:
        return False, dev_constants.MSG_SPAWN_UNKNOWN_ITEM.format(item_key=item_key)

    asked = min(quantity, dev_constants.MAX_SPAWN_QUANTITY)
    asked = max(asked, dev_constants.MIN_SPAWN_QUANTITY)

    if item_def.stackable:
        granted = _grant_stack(target, item_def, asked)
    else:
        granted = _grant_copies(target, item_def, asked)

    if granted < dev_constants.MIN_SPAWN_QUANTITY:
        return False, dev_constants.MSG_SPAWN_NO_ROOM.format(target=target.key)

    message = dev_constants.MSG_SPAWN_DONE.format(
        quantity=granted,
        item_name=item_def.name,
        target=target.key,
    )

    if granted < asked:
        clamp_note = dev_constants.MSG_SPAWN_CLAMPED.format(asked=asked, granted=granted)
        message = f"{message}\n{clamp_note}"

    _audit(actor, dev_constants.ACTION_SPAWN, target, f"{granted}x {item_key}")

    return True, message


# ─── NPC spawning ────────────────────────────────────────────────────────────

def npc_keys() -> list:
    """
    Purpose: Name every NPC the spawner can produce, in a stable order.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a sorted list of NPC_DB keys.

    Module Globals:
        NPC_DB read.

    Notes/References:
        Derived from the registry, exactly as item_keys is. Adding an NpcDef
        must reach this menu with no edit here.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    keys = sorted(NPC_DB.keys())

    return keys


def spawn_npc(actor, target, npc_key: str, quantity: int = 1) -> tuple:
    """
    Purpose: Spawn one or more hostiles in the room the target is standing in.

    Entry:
        actor is the moderator. target is the Character whose room receives
        them. npc_key names an entry in NPC_DB. quantity is what was asked
        for, before clamping.

    Exit/Returns:
        Returns (succeeded, message). Failure means an unknown NPC, or a
        target with no location.

    Module Globals:
        NPC_DB read. dev_constants MIN_NPC_SPAWN, MAX_NPC_SPAWN,
        MSG_SPAWN_NPC_* read.

    Methodology:
        Spawns into the TARGET's room, not the moderator's. The two are the
        same when a moderator is testing on themself and different when they
        are reproducing a player's report, and the second is the case worth
        getting right -- "spawn it where they are" is the whole request.

        NpcDef.create does the rest: it applies the combat block, stamps the
        respawn identity and names the AI behaviour, so a spawned raider is
        the same object the map builder would have placed. A hand-rolled
        create_object here would produce something that fights but never
        respawns and answers to no behaviour.

    Notes/References:
        These are LIVE COMBATANTS the moment they land. They join the tick,
        pick targets and swing, which is why MAX_NPC_SPAWN is 20 and not the
        item ceiling's 1000.

        db.spawn_room is stamped by create() to the room they land in, so a
        spawned hostile with a respawn_seconds will come back HERE rather
        than at whatever tile its map placement would have used.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    npc_def = NPC_DB.get(npc_key)

    if npc_def is None:
        return False, dev_constants.MSG_SPAWN_NPC_UNKNOWN.format(npc_key=npc_key)

    room = getattr(target, "location", None)

    if room is None:
        return False, dev_constants.MSG_SPAWN_NPC_NOWHERE.format(target=target.key)

    count = min(quantity, dev_constants.MAX_NPC_SPAWN)
    count = max(count, dev_constants.MIN_NPC_SPAWN)
    made = 0

    while made < count:
        npc_def.create(location=room)
        made += 1

    _audit(actor, dev_constants.ACTION_SPAWN_NPC, target, f"{made}x {npc_key} in {room.key}")
    message = dev_constants.MSG_SPAWN_NPC_DONE.format(
        quantity=made,
        npc_name=npc_def.name,
        room=room.key,
    )

    return True, message


# ─── Destroying belongings ───────────────────────────────────────────────────

def _is_staff_item(item) -> bool:
    """
    Purpose: Whether an item must survive a clear.

    Entry:
        item is a live object.

    Exit/Returns:
        True when the item carries the staff tag category.

    Module Globals:
        dev_constants.DEV_TOOL_TAG_CATEGORY read.

    Methodology:
        Read off the TAG CATEGORY the ItemDef declares, not off the typeclass.
        A tag check needs no import of typeclasses.dev_tools, and it protects
        every future staff item the moment it is defined rather than when
        somebody remembers to extend an isinstance chain here.

    Notes/References:
        This is what stops a moderator emptying their own bag from destroying
        the egg they are holding to do it with.

        `tags.get(category=...)` with no key, NOT `tags.all(category=...)` --
        TagHandler.all takes no category argument at all, so the second spells
        a filter that would never have been applied.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    tagged = item.tags.get(
        category=dev_constants.DEV_TOOL_TAG_CATEGORY,
        return_list=True,
    )

    return bool(tagged)


def clear_inventory(actor, target) -> tuple:
    """
    Purpose: Destroy everything a character is carrying and wearing.

    Entry:
        actor is the moderator. target is the Character to strip.

    Exit/Returns:
        Returns (succeeded, message) reporting the counts destroyed and any
        staff items left alone. Failure means there was nothing to clear.

    Module Globals:
        dev_constants.MSG_CLEAR_* read.

    Methodology:
        Both surfaces, in one action. `purge` already treats carried and
        equipped as one thing, and a moderator resetting a test character who
        found their weapon still wielded would just run it twice.

        An equipped item is removed from its slot BEFORE being deleted.
        EquipmentHandler.remove clears the slot, saves, republishes to the 3D
        client and refreshes the combat profile; deleting the object out from
        under a live slot would leave the handler naming a destroyed row and
        the equipment pane drawing it.

        Staff items are skipped and counted, not silently passed over. A
        moderator who expected an empty bag and got one item needs to be told
        which rule kept it.

    Notes/References:
        The only irreversible thing on the tool. Everything else it does can
        be undone by doing something else; a deleted item is gone.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    equipment = target.equipment
    carried_removed = 0
    equipped_removed = 0
    kept = 0

    for item in list(equipment.all()):
        if _is_staff_item(item):
            kept += 1
            continue

        equipment.remove(item)
        item.delete()
        equipped_removed += 1

    for _slot, item in target.inventory.all_items():
        if _is_staff_item(item):
            kept += 1
            continue

        item.delete()
        carried_removed += 1

    target.inventory.sync()
    total = carried_removed + equipped_removed

    if total < 1:
        return False, dev_constants.MSG_CLEAR_NOTHING.format(target=target.key)

    _audit(actor, dev_constants.ACTION_CLEAR, target,
           f"{carried_removed} carried, {equipped_removed} equipped, {kept} kept")
    message = dev_constants.MSG_CLEAR_DONE.format(
        carried=carried_removed,
        equipped=equipped_removed,
        target=target.key,
    )

    if kept > 0:
        message = f"{message}\n{dev_constants.MSG_CLEAR_KEPT.format(kept=kept)}"

    return True, message


# ─── Teleport ────────────────────────────────────────────────────────────────

def map_zcoords() -> list:
    """
    Purpose: Name every map a teleport may target.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a sorted list of z-coordinate strings, or an empty list when
        the manifest cannot be read.

    Module Globals:
        None.

    Methodology:
        Read from scripts/map_manifest.json through world/maps/manifest.py --
        the one file that decides which maps exist. Adding a map row therefore
        adds a teleport destination with no edit here.

    Notes/References:
        Destinations are whole MAPS today, one arrival tile each. Named
        landmarks (the Bank, the Shopkeeper), a jump to another player and a
        "bring them to me" are the obvious expansions; each is a different
        target vocabulary answering the same question this function answers
        for maps, and _map_anchor_room is where the landing tile is decided.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    try:
        entries = load_entries()
    except ManifestError as exc:
        logger.log_err(f"{dev_constants.AUDIT_LOG_PREFIX} manifest unreadable: {exc!r}")

        return []

    zcoords = zcoords_of(entries)
    ordered = sorted(zcoords)

    return ordered


def teleport_to_map(actor, target, zcoord: str) -> tuple:
    """
    Purpose: Move a character to another map's arrival tile.

    Entry:
        actor is the moderator. target is the Character to move. zcoord names
        a map listed in the manifest.

    Exit/Returns:
        Returns (succeeded, message). Failure means an unknown map, a map with
        no rooms built, or a move the engine refused.

    Module Globals:
        dev_constants.MSG_TELEPORT_* read.

    Methodology:
        Validate the map name against the manifest before touching the
        database, so a typo is a message rather than a query that finds
        nothing and has to guess why.

        The move is quiet, and the arrival is announced to the target alone.
        Default move messaging would tell the destination room that someone
        "arrives from the north", which is false -- there is no direction a
        teleport comes from. Character.respawn makes the same choice.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    known = map_zcoords()
    listed = zcoord in known

    if not listed:
        return False, dev_constants.MSG_TELEPORT_UNKNOWN_MAP.format(zcoord=zcoord)

    room = _map_anchor_room(zcoord)

    if room is None:
        return False, dev_constants.MSG_TELEPORT_NO_ROOM.format(zcoord=zcoord)

    succeeded, message = _move_to_room(actor, target, room, zcoord)

    return succeeded, message


def teleport_to_character(actor, target, other) -> tuple:
    """
    Purpose: Move a character to wherever another character is standing.

    Entry:
        actor is the moderator. target is the Character to move. other is the
        Character whose room is the destination. The three may overlap in any
        combination -- "bring them to me" passes actor as `other`, and "go to
        them" passes actor as `target`.

    Exit/Returns:
        Returns (succeeded, message). Failure means the destination character
        is nowhere, or the move was refused.

    Module Globals:
        dev_constants.MSG_TELEPORT_NO_DESTINATION, MSG_TELEPORT_ALREADY_THERE
        read.

    Methodology:
        Both directions a moderator wants are this one function with the
        arguments swapped, so there is one move path and one set of failure
        modes rather than a `bring_here` that drifts away from a `go_to`.

        Landing in the same room is reported and skipped rather than performed.
        A no-op move still fires the room's at_object_receive and would
        announce an arrival to everyone present, which is a confusing thing to
        broadcast about someone who never left.

    Notes/References:
        A logged-out character has no location; that is normal, not an error,
        and it is the common case for "teleport to <name>" typed from memory.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    room = getattr(other, "location", None)

    if room is None:
        return False, dev_constants.MSG_TELEPORT_NO_DESTINATION.format(
            other=other.key)

    if target.location is room:
        return False, dev_constants.MSG_TELEPORT_ALREADY_THERE.format(
            target=target.key, room=room.key)

    succeeded, message = _move_to_room(actor, target, room, other.key)

    return succeeded, message


def _move_to_room(actor, target, room, detail: str) -> tuple:
    """
    Purpose: Perform one teleport and report it, whatever chose the room.

    Entry:
        actor is the moderator. target is the Character to move. room is a
        resolved destination. detail names what the moderator asked for, for
        the audit line -- a map name, or a character's key.

    Exit/Returns:
        Returns (succeeded, message).

    Module Globals:
        dev_constants.MSG_TELEPORT_FAILED, MSG_TELEPORT_ARRIVAL,
        MSG_TELEPORT_DONE read.

    Methodology:
        The move is quiet and the arrival is announced to the target alone.
        Default move messaging would tell the destination room that someone
        "arrives from the north", which is false -- there is no direction a
        teleport comes from. Character.respawn makes the same choice.

    Notes/References:
        Shared by teleport_to_map and teleport_to_character. Everything that
        differs between them is the choosing of `room`, and everything that is
        the same is here.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    try:
        target.move_to(room, quiet=True, move_type="teleport")
    except Exception as exc:
        logger.log_err(f"{dev_constants.AUDIT_LOG_PREFIX} teleport failed: {exc!r}")

        return False, dev_constants.MSG_TELEPORT_FAILED.format(room=room.key)

    target.msg(dev_constants.MSG_TELEPORT_ARRIVAL)
    _audit(actor, dev_constants.ACTION_TELEPORT, target, f"{detail} -> {room.key}")
    message = dev_constants.MSG_TELEPORT_DONE.format(target=target.key, room=room.key)

    return True, message


# ─── Progression ─────────────────────────────────────────────────────────────

def skill_keys() -> list:
    """
    Purpose: Name every skill XP may be granted to, in a stable order.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a sorted list of SKILL_REGISTRY keys.

    Module Globals:
        SKILL_REGISTRY read.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    keys = sorted(SKILL_REGISTRY.keys())

    return keys


def grant_xp(actor, target, skill_key: str, amount: int) -> tuple:
    """
    Purpose: Add experience to one of a character's skills.

    Entry:
        actor is the moderator. target is the Character. skill_key names an
        entry in SKILL_REGISTRY. amount is what was asked for, before
        clamping.

    Exit/Returns:
        Returns (succeeded, message). Failure means an unknown skill.

    Module Globals:
        SKILL_REGISTRY read. dev_constants MIN_XP_GRANT, MAX_XP_GRANT,
        MSG_UNKNOWN_SKILL, MSG_XP_DONE read.

    Methodology:
        Grants are upward only. Taking progression away is set_skill_level's
        job, which names the level it leaves behind; a negative XP grant names
        a number whose effect on the curve nobody can predict at the prompt.

    Notes/References:
        Routes through SkillHandler.add_xp, so level-up side effects -- the
        Fortitude/max_hp link in particular -- fire exactly as they do when
        the XP is earned.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    known = skill_key in SKILL_REGISTRY

    if not known:
        return False, dev_constants.MSG_UNKNOWN_SKILL.format(skill_key=skill_key)

    granted = min(amount, dev_constants.MAX_XP_GRANT)
    granted = max(granted, dev_constants.MIN_XP_GRANT)

    target.skills.add_xp(skill_key, granted)
    _audit(actor, dev_constants.ACTION_XP, target, f"{granted} xp -> {skill_key}")
    message = dev_constants.MSG_XP_DONE.format(
        amount=granted,
        target=target.key,
        skill_key=skill_key,
    )

    return True, message


def set_skill_level(actor, target, skill_key: str, level: int) -> tuple:
    """
    Purpose: Set one of a character's skills to a level outright.

    Entry:
        actor is the moderator. target is the Character. skill_key names an
        entry in SKILL_REGISTRY. level is the wanted level.

    Exit/Returns:
        Returns (succeeded, message) reporting the level actually stored.

    Module Globals:
        SKILL_REGISTRY read. dev_constants MSG_UNKNOWN_SKILL, MSG_LEVEL_DONE
        read.

    Methodology:
        The clamp into [MIN_BASE_SKILL_LEVEL, MAX_BASE_SKILL_LEVEL] is
        skills.logic.set_level's, not this module's, and the level it RETURNS
        is what gets reported -- so the message cannot claim a level the write
        did not store.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    known = skill_key in SKILL_REGISTRY

    if not known:
        return False, dev_constants.MSG_UNKNOWN_SKILL.format(skill_key=skill_key)

    stored = target.skills.set_level(skill_key, level)
    _audit(actor, dev_constants.ACTION_LEVEL, target, f"{skill_key} = {stored}")
    message = dev_constants.MSG_LEVEL_DONE.format(
        target=target.key,
        skill_key=skill_key,
        level=stored,
    )

    return True, message


# ─── Quests ──────────────────────────────────────────────────────────────────

def quest_keys() -> list:
    """
    Purpose: Name every quest the tool can act on, in a stable order.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a sorted list of GLOBAL_QUEST_REGISTRY keys.

    Module Globals:
        GLOBAL_QUEST_REGISTRY read.

    Notes/References:
        An EMPTY list here is a real signal, not an empty screen to shrug at:
        it means every content module failed to import inside the loader's
        `except`, which is the state the game shipped in until 08/25/2026 and
        whose only in-play symptom was a quest that could not be accepted. The
        menu says so rather than drawing nothing.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    keys = sorted(GLOBAL_QUEST_REGISTRY.keys())

    return keys


def quest_step_keys(quest_key: str) -> list:
    """
    Purpose: Name the steps of one quest, in blueprint order.

    Entry:
        quest_key names a quest in the registry.

    Exit/Returns:
        Returns the ordered step keys, or an empty list for an unknown quest.

    Module Globals:
        GLOBAL_QUEST_REGISTRY read.

    Notes/References:
        Ordered, never sorted. A quest's steps are a sequence, and presenting
        them alphabetically would make "jump back one step" a puzzle.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)

    if blueprint is None:
        return []

    return list(blueprint.step_keys)


def quest_title(quest_key: str) -> str:
    """Give a quest's display title, falling back to its key."""
    blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)
    title = getattr(blueprint, "title", None)

    return title or quest_key


def accept_quest(actor, target, quest_key: str) -> tuple:
    """
    Purpose: Start a quest on a character's behalf.

    Entry:
        actor is the moderator. target is the Character. quest_key names a
        quest in the registry.

    Exit/Returns:
        Returns (succeeded, message). Failure means an unknown quest, or one
        the character cannot currently take.

    Module Globals:
        GLOBAL_QUEST_REGISTRY read. dev_constants MSG_QUEST_* read.

    Methodology:
        Routes through QuestHandler.accept_quest, so the opening step's
        on_enter fires and the progress dict is seeded exactly as it would be
        from the android's dialogue. A moderator-started quest must be
        indistinguishable from a player-started one, or it tests nothing.

    Notes/References:
        accept_quest returns a bare bool and messages the TARGET on an unknown
        key. The registry check here is what lets the MODERATOR see the
        refusal too -- otherwise the only person told is the person who did
        not do anything.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    known = quest_key in GLOBAL_QUEST_REGISTRY

    if not known:
        return False, dev_constants.MSG_QUEST_UNKNOWN.format(quest_key=quest_key)

    started = target.quests.accept_quest(quest_key)

    if not started:
        return False, dev_constants.MSG_QUEST_UNAVAILABLE.format(
            target=target.key, quest_key=quest_key)

    _audit(actor, dev_constants.ACTION_QUEST, target, f"accept {quest_key}")
    message = dev_constants.MSG_QUEST_ACCEPTED.format(
        target=target.key, quest_key=quest_key)

    return True, message


def abandon_quest(actor, target, quest_key: str) -> tuple:
    """
    Purpose: Drop a character's in-progress quest, keeping any completion
        record.

    Entry:
        actor is the moderator. target is the Character. quest_key names an
        active quest.

    Exit/Returns:
        Returns (succeeded, message). Failure means the quest is not active.

    Module Globals:
        dev_constants.MSG_QUEST_NOT_ACTIVE, MSG_QUEST_ABANDONED read.

    Notes/References:
        This is NOT reset. Abandoning leaves a completion record standing, so
        a finished quest stays finished and cannot be taken again. The message
        says so, because the two sit one keystroke apart on the menu.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    dropped = target.quests.abandon_quest(quest_key)

    if not dropped:
        return False, dev_constants.MSG_QUEST_NOT_ACTIVE.format(
            target=target.key, quest_key=quest_key)

    _audit(actor, dev_constants.ACTION_QUEST, target, f"abandon {quest_key}")
    message = dev_constants.MSG_QUEST_ABANDONED.format(
        target=target.key, quest_key=quest_key)

    return True, message


def complete_quest(actor, target, quest_key: str) -> tuple:
    """
    Purpose: Finish a quest outright, paying its rewards.

    Entry:
        actor is the moderator. target is the Character. quest_key names a
        quest in the registry; it need not be active.

    Exit/Returns:
        Returns (succeeded, message). Failure means an unknown quest or one
        already complete.

    Module Globals:
        GLOBAL_QUEST_REGISTRY read. dev_constants MSG_QUEST_* read.

    Methodology:
        Rewards DO pay out -- see QuestHandler.force_complete_quest. Exercising
        the reward callback is the main reason to force a completion, so a
        version that skipped it would skip the one part not otherwise
        reachable without playing the whole quest.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    known = quest_key in GLOBAL_QUEST_REGISTRY

    if not known:
        return False, dev_constants.MSG_QUEST_UNKNOWN.format(quest_key=quest_key)

    completed = target.quests.force_complete_quest(quest_key)

    if not completed:
        return False, dev_constants.MSG_QUEST_ALREADY_COMPLETE.format(
            target=target.key, quest_key=quest_key)

    _audit(actor, dev_constants.ACTION_QUEST, target, f"complete {quest_key}")
    message = dev_constants.MSG_QUEST_COMPLETED.format(
        target=target.key, quest_key=quest_key)

    return True, message


def reset_quest(actor, target, quest_key: str) -> tuple:
    """
    Purpose: Return a quest to not-started, from active or complete.

    Entry:
        actor is the moderator. target is the Character. quest_key names a
        quest the character has some record of.

    Exit/Returns:
        Returns (succeeded, message). Failure means the character had no
        record of it either way.

    Module Globals:
        dev_constants.MSG_QUEST_NOTHING_TO_RESET, MSG_QUEST_RESET read.

    Notes/References:
        The one operation that makes a finished quest takeable again, which is
        what a tester replaying content actually needs. Rewards already paid
        are not clawed back.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    cleared = target.quests.reset_quest(quest_key)

    if not cleared:
        return False, dev_constants.MSG_QUEST_NOTHING_TO_RESET.format(
            target=target.key, quest_key=quest_key)

    _audit(actor, dev_constants.ACTION_QUEST, target, f"reset {quest_key}")
    message = dev_constants.MSG_QUEST_RESET.format(
        target=target.key, quest_key=quest_key)

    return True, message


def set_quest_step(actor, target, quest_key: str, step_key: str) -> tuple:
    """
    Purpose: Move an active quest to a named step, forward or back.

    Entry:
        actor is the moderator. target is the Character. quest_key names an
        active quest; step_key names one of its steps.

    Exit/Returns:
        Returns (succeeded, message). Failure means the quest is not active,
        or the blueprint has no such step.

    Module Globals:
        dev_constants MSG_QUEST_NOT_ACTIVE, MSG_QUEST_UNKNOWN_STEP,
        MSG_QUEST_STEP_SET read.

    Methodology:
        The handler returns one bool for two different refusals, so the two
        are separated HERE by asking which precondition actually failed. A
        moderator told "that did not work" about a quest they can see is
        active will retype it rather than look at the step name.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    active = target.quests.is_active(quest_key)

    if not active:
        return False, dev_constants.MSG_QUEST_NOT_ACTIVE.format(
            target=target.key, quest_key=quest_key)

    moved = target.quests.force_step(quest_key, step_key)

    if not moved:
        return False, dev_constants.MSG_QUEST_UNKNOWN_STEP.format(
            quest_key=quest_key, step_key=step_key)

    _audit(actor, dev_constants.ACTION_QUEST, target,
           f"step {quest_key} -> {step_key}")
    message = dev_constants.MSG_QUEST_STEP_SET.format(
        target=target.key, quest_key=quest_key, step_key=step_key)

    return True, message


# ─── Delegated account commands ──────────────────────────────────────────────

def delegate_account_command(actor, command_key: str, account_name: str,
                             action: str, reason: str = "") -> tuple:
    """
    Purpose: Type one of Evennia's stock account commands on the moderator's
        behalf, and record that it was typed.

    Entry:
        actor is the moderator's Character. command_key is one of
        dev_constants.ACCOUNT_COMMAND_*. account_name is what the moderator
        typed. action is the MODERATOR_ACTIONS member to audit under. reason
        is optional free text.

    Exit/Returns:
        Returns (succeeded, message). Failure means no account was named. A
        success means the command was DISPATCHED, not that it found the
        account -- the stock command reports that itself, on its own terms.

    Module Globals:
        dev_constants.ACCOUNT_REASON_SEPARATOR, MSG_ACCOUNT_NOT_NAMED,
        MSG_DELEGATED read.

    Methodology:
        Dispatch through the ACCOUNT when there is one. `ban` and `boot` live
        on AccountCmdSet, and the account is where their locks are evaluated.
        A puppeted character's merged cmdset would find them too, but routing
        at the object that owns the permission keeps the lock check somewhere
        a reader expects to find it.

        Nothing here re-implements a ban. Evennia owns the `server_bans`
        ServerConfig row that the login path reads, and a second writer of it
        is a second place for a ban to be subtly wrong.

    Notes/References:
        The stock commands' own locks still apply -- `ban` needs Developer,
        `boot` needs Admin -- so an Admin holding the egg can boot but not
        ban, and is told so by the command itself.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    cleaned = (account_name or "").strip()

    if not cleaned:
        return False, dev_constants.MSG_ACCOUNT_NOT_NAMED

    command = f"{command_key} {cleaned}"
    trimmed_reason = (reason or "").strip()

    if trimmed_reason:
        separator = dev_constants.ACCOUNT_REASON_SEPARATOR
        command = f"{command} {separator} {trimmed_reason}"

    executor = getattr(actor, "account", None) or actor
    _audit(actor, action, None, command)
    executor.execute_cmd(command)
    message = dev_constants.MSG_DELEGATED.format(command=command)

    return True, message
