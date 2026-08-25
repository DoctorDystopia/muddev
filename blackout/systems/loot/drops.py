"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/14/2026
Description: Delivery half of the loot system -- turns the (item_key, quantity)
             pairs a LootTableDef.roll() produces into real objects on the
             ground, and announces them.

             The split with world/loot_database.py is deliberate. Rolling is
             pure and knows only keys and weights; this module is the only part
             that touches ITEM_DB, the object layer, or a room. That is what
             lets the entire probability surface be tested with a seeded
             Random and no Evennia fixture, and it is also why the stackable
             question is answered HERE: roll() cannot merge same-key pairs
             without knowing whether the item stacks, and collapsing two
             non-stackable drops into quantity=2 would silently yield one
             object (ItemDef._get_attrs only stamps `quantity` when
             `stackable` is set).

             Nothing in here raises. A death handler is the wrong place to
             discover a data typo, so an unresolvable table or item is logged
             and skipped -- the same fail-soft posture combat_rules takes.
"""

from evennia.utils import logger

from systems.combat import combat_msg
from world.item_database import ITEM_DB
from world.loot_database import LOOT_DB


# ─── Private helper routines ─────────────────────────────────────────────────

def _spawn_one_drop(item_def, quantity: int, room) -> list:
    """
    Purpose: Put one rolled (item, quantity) pair on the ground.

    Entry:
        item_def - the resolved ItemDef. Must not be None.
        quantity - stack size from the roll. Assumed positive.
        room     - the location to drop into. Must not be None.

    Exit/Returns:
        Returns the list of objects created, which is one object for a
        stackable item and `quantity` objects otherwise.

    Module Globals:
        None.

    Methodology:
        A stackable item takes one create() carrying the whole quantity; a
        non-stackable one takes `quantity` separate creates. ItemDef._get_attrs
        only writes `quantity` when `stackable` is set, so passing quantity=3
        for a non-stackable item would produce a single sword claiming to be
        three -- this branch is the whole reason the roller hands back pairs
        rather than a merged dict.

    Notes/References:
        ItemDef.create() spawns detached and then move_to()s, which is what
        fires at_object_receive. Never replace it with create_object here:
        world/item_database.py:188 documents the stack-merge and slot-
        registration that depends on the hook running.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    created = []

    if item_def.stackable:
        obj = item_def.create(location=room, quantity=quantity)
        created.append(obj)

        return created

    for _ in range(quantity):
        obj = item_def.create(location=room)
        created.append(obj)

    return created


def _merge_stackable_pairs(drops: list) -> list:
    """
    Purpose: Sum same-key pairs that name a stackable item, in first-seen
    order, so `rolls > 1` landing on the same stackable entry twice produces
    one combined pair instead of two.

    Entry:
        drops - list of (item_key, quantity) pairs from LootTableDef.roll().
                May be empty. Unresolvable keys are left untouched here;
                _deliver still logs-and-skips them.

    Exit/Returns:
        Returns a new list of (item_key, quantity) pairs, same length or
        shorter. Non-stackable pairs, and pairs whose key does not resolve in
        ITEM_DB, pass through unmerged and keep their original position.

    Module Globals:
        ITEM_DB read.

    Methodology:
        roll() cannot do this itself -- see this module's header -- because
        merging requires knowing stackability, which only ITEM_DB answers.
        Doing it once here, before delivery, means _spawn_one_drop and the
        announcement both see the combined pair and never learn two separate
        rolls produced it.

    Notes/References:
        Without this, a table with `rolls=2` whose pool favours one stackable
        entry (e.g. credits) would spawn two separate stacks on the ground --
        two objects a player must `get` one at a time instead of one.

    Author: Nick Hobar
    Creation date: 08/16/2026
    """
    merged = []
    index_by_key = {}

    for item_key, quantity in drops:
        item_def = ITEM_DB.get(item_key)

        if item_def is not None and item_def.stackable and item_key in index_by_key:
            existing_index = index_by_key[item_key]
            existing_key, existing_quantity = merged[existing_index]
            merged[existing_index] = (existing_key, existing_quantity + quantity)
            continue

        index_by_key[item_key] = len(merged)
        merged.append((item_key, quantity))

    return merged


def _deliver(drops: list, room) -> list:
    """
    Purpose: Spawn every rolled pair, skipping any that names a bad item.

    Entry:
        drops - list of (item_key, quantity) pairs from LootTableDef.roll().
        room  - the location to drop into. Must not be None.

    Exit/Returns:
        Returns a list of (display_name, quantity) pairs for the pairs that
        actually landed, in roll order. Skipped entries appear nowhere, so the
        announcement never names an item the player cannot pick up.

    Module Globals:
        ITEM_DB read.

    Methodology:
        Merges same-key stackable pairs first (see _merge_stackable_pairs),
        then resolves each key against ITEM_DB and logs-and-skips an unknown
        one. validate_loot_tables() is what catches a bad key loudly in the
        test suite; by the time a kill is being resolved the only useful
        behaviour is to drop what is valid and leave a trace for the operator.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    delivered = []

    for item_key, quantity in _merge_stackable_pairs(drops):
        item_def = ITEM_DB.get(item_key)

        if item_def is None:
            logger.log_err(
                f"loot.drops: table names unknown item {item_key!r}; skipped."
            )
            continue

        _spawn_one_drop(item_def, quantity, room)
        delivered.append((item_def.name, quantity))

    return delivered


# ─── Public routines ─────────────────────────────────────────────────────────

def resolve_table(npc):
    """
    Purpose: Find the LootTableDef an NPC should roll on death.

    Entry:
        npc - the dying entity. May carry db.loot_table_key (a per-instance
              override) and/or db.npc_key (the NpcDef identity stamped by
              NpcDef.create).

    Exit/Returns:
        Returns the LootTableDef, or None when this NPC has no table -- which
        is the normal case for anything not opted in, not an error.

    Module Globals:
        LOOT_DB read.

    Methodology:
        db.loot_table_key wins if set, so a builder can give one unique NPC its
        own table without a new NpcDef. Otherwise the def is looked up live
        through db.npc_key, exactly as HostileNPC.respawn looks up its own
        identity. Resolving live rather than reading a stamped attribute means
        editing a table plus `evennia reload` affects NPCs already on the grid.

    Notes/References:
        NPC_DB is imported inside the routine to avoid a systems <-> world
        import cycle at spawner-load time, matching the local-import style
        typeclasses/npc_combat.py documents.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    from world.npc_database import NPC_DB

    table_key = npc.attributes.get("loot_table_key", default=None)

    if not table_key:
        npc_key = npc.attributes.get("npc_key", default=None)
        npc_def = NPC_DB.get(npc_key)

        if npc_def is None:
            return None

        table_key = npc_def.loot_table

    if not table_key:
        return None

    table = LOOT_DB.get(table_key)

    if table is None:
        logger.log_err(
            f"loot.drops: {npc} names unknown loot table {table_key!r}."
        )

    return table


def award_drops(npc, killer=None, rng=None) -> list:
    """
    Purpose: Roll an NPC's loot table and leave the result on the ground.

    Entry:
        npc    - the dying entity. Must still have a location and a live
                 database row; call this BEFORE respawn(), which deletes it.
        killer - the entity that landed the killing blow, or None for an
                 environmental death. Accepted but not yet read: drops go to
                 the floor for everyone, so no ownership question arises. It is
                 in the signature because loot locks and auto-loot both need
                 it, and neither should have to change every call site.
        rng    - optional random.Random for deterministic tests, passed
                 straight through to LootTableDef.roll().

    Exit/Returns:
        Returns the list of (display_name, quantity) pairs that landed, empty
        when this NPC has no table, rolled nothing, or has no location.

    Module Globals:
        None.

    Methodology:
        Resolve table -> roll -> deliver -> announce. The announcement is
        skipped entirely on an empty result rather than printing an empty drop
        line, which is why _deliver returns the delivered pairs instead of the
        rolled ones -- a skipped bad key must not be announced.

    Notes/References:
        Deliberately does NOT catch its own exceptions; HostileNPC.drop_loot
        wraps the call the way at_death already wraps its XP and quest hooks,
        so the guard sits at the same layer as its neighbours rather than being
        duplicated at both.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    room = npc.location

    if room is None:
        return []

    table = resolve_table(npc)

    if table is None:
        return []

    drops = table.roll(rng=rng)
    delivered = _deliver(drops, room)

    if not delivered:
        return []

    line = combat_msg.format_drops(npc, delivered)
    room.msg_contents(line)

    return delivered
