"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Hostile NPC typeclass — CombatEntity-mixin-powered enemy spawnable
             through the SPAWNER_REGISTRY and immediately attackable in twitch melee.
"""

from evennia import DefaultObject
from evennia.utils import logger
from evennia.utils.utils import lazy_property

from systems.combat import constants as combat_constants
from typeclasses.mixins import CombatEntity
from typeclasses.objects import ObjectParent

from .spawners import register_spawner


class _NpcSkillsShim:
    """Minimal read-only `skills` facade for HostileNPC.

    The OSRS combat math (combat_calc.effective_level, etc.) is fed by
    `entity.skills.get_level(skill_key)`. Characters have a real
    SkillHandler backed by `db.skills`. NPCs in this batch are *not*
    skill-tracked (no XP gain, no levelling) — they use a flat
    `combat_stats` dict that the spawner stamps once.

    Rather than installing a full SkillHandler (which would allocate the
    full skill registry per NPC), this shim translates `get_level` calls
    into reads against the NPC's flat `combat_stats`:

        strike   -> combat_stats["strike_level"]
        brawn    -> combat_stats["brawn_level"]
        defense  -> combat_stats["defense_level"]
        <other>  -> 1   (best-effort floor; matches the previous fallback
                          branch in ActionAttack.resolve)

    This keeps NPC defense math correct without coupling NPCs to the
    Character progression system.

    The shim must cover every method combat code calls on `.skills`, not
    just the ones NPCs meaningfully implement. Combat duck-types on this
    interface, so a missing method raises inside the tick loop, which the
    tick engine catches by discarding the handler — the NPC would silently
    stop fighting with no error surfaced to the player.
    """

    def __init__(self, npc) -> None:
        self._npc = npc

    def get_level(self, skill_key: str) -> int:
        stats = self._npc.db.combat_stats or {}
        return int(stats.get(f"{skill_key}_level", 1))

    def add_xp(self, skill_key: str, amount: int) -> None:
        """No-op. NPCs are not skill-tracked and never level."""
        return None

    def get_total_xp(self, skill_key: str) -> int:
        """NPCs carry no XP; report zero."""
        return 0

    def meets_prerequisite(self, skill_key: str, required_level: int) -> bool:
        """Compare the NPC's flat stat block against a level requirement."""
        level = self.get_level(skill_key)
        return level >= required_level


class HostileNPC(CombatEntity, ObjectParent, DefaultObject):
    """
    Purpose: An aggressive NPC enemy for batch 2 melee combat testing.

    Entry (at_object_creation):
        self.db.combat_stats should be populated by the caller spawner
        for stat seeding before init_combat_attrs runs. Minimum keys:
            - strike_level (int)
            - brawn_level (int)
            - defense_level (int)
            - max_hp (optional; falls back to 10 if unset)

    Exit/Returns:
        A fully functional Attackable CombatEntity that also inherits
        Object behaviour (move, give, examine, etc.).

    Methodology:
        Inherits from CombatEntity first, then ObjectParent (a no-ops mixin)
        and finally DefaultObject. This gives us all Object-level hooks
        (content, location, move) plus HP, alive-state, damage, death, and
        disconnect cleanup without subclassing TalkativeNPC.

        Spawn registration borrows the @register_spawner decorator used
        by TalkativeNPC/ShopkeepNPC in npcs.py, so a builder can drop
        a hostile NPC in-room with::

            @register_spawner("Mutant Raider Tile")

    Author: Nick Hobar
    Creation date: 07/26/2026
    """

    @lazy_property
    def skills(self) -> _NpcSkillsShim:
        """Lazy cached shim exposing `npc.skills.get_level(...)` for combat math.

        See _NpcSkillsShim docstring. Previously HostileNPC had no `skills`
        attribute at all, so ActionAttack.resolve always defaulted the NPC's
        defense level to 1, making enemies trivially hittable regardless of
        their intended stats.
        """
        return _NpcSkillsShim(self)


    def at_object_creation(self) -> None:
        """Seed combat state at creation time.

        Note that a spawner cannot have written `db.combat_stats` yet — this
        hook runs *inside* `create_object`, before the spawner gets the object
        back. Spawners must therefore call `apply_combat_stats` themselves once
        they've assigned the stat block; this call only covers the case where
        stats arrived via a prototype/attribute at creation.
        """
        super().at_object_creation()
        self.apply_combat_stats()


    def apply_combat_stats(self, stats: dict = None) -> None:
        """Unpack a combat stat block onto the discrete db attributes.

        Idempotent — safe to call at creation and again from a spawner.

        Entry:
            stats - the stat block to apply. If None, reads db.combat_stats.
                    If given, it is also stored to db.combat_stats so the
                    _NpcSkillsShim can read the skill levels back out.
        """
        if stats is not None:
            self.db.combat_stats = stats

        raw_stats = self.db.combat_stats or {}

        self.init_combat_attrs(max_hp=raw_stats.get("max_hp") or self.db.max_hp or 10)
        self.db.attack_speed = raw_stats.get("attack_speed", combat_constants.UNARMED_ATTACK_SPEED_TICKS)
        self.db.combat_stat_bonuses = raw_stats.get("combat_stat_bonuses", {})
        self.db.combat_styles = raw_stats.get("combat_styles", {})
        self.db.default_combat_style = raw_stats.get(
            "default_combat_style", combat_constants.UNARMED_DEFAULT_COMBAT_STYLE
        )
        # An NPC has no equipment handler, so collect_contributors reads its
        # rules off the NPC itself -- under the same attribute name an item
        # uses, which is what lets one collector serve both.
        self.db.combat_rules = raw_stats.get(combat_constants.COMBAT_RULES_ATTR, [])


    def drop_loot(self, killer=None) -> None:
        """Roll this NPC's loot table onto the floor of the room it died in.

        The table is named by its NpcDef's `loot_table` field and resolved live
        through db.npc_key, so an NPC with no table simply drops nothing --
        every NPC type is opt-in, exactly as respawn_seconds is.

        Wrapped the way at_death wraps its own XP and quest hooks: a broken
        loot table must never block the death itself, because a skipped
        respawn() would leave a 0-hp corpse standing and hang the fight (see
        respawn() below for the full version of that failure).
        """
        try:
            # Local import: systems.loot pulls in world.item_database, and
            # this module is loaded by SPAWNER_MODULES at load_all_spawners()
            # time. Matches the local-import style used throughout this module.
            from systems.loot.drops import award_drops

            award_drops(self, killer)
        except Exception:
            logger.log_trace()


    def respawn(self) -> None:
        """Despawn, and queue a timed comeback if this NpcDef asked for one.

        `db.respawn_seconds is None` keeps the historical behaviour exactly —
        the corpse vanishes and never returns — so every NPC type is opt-in.
        An int enqueues on the global BlackoutRespawnManager and *then*
        deletes; the enqueue has to read `self` while the row still exists,
        which is why this is the last possible moment (it is the final call in
        CombatEntity.at_death).

        No corpse object is left behind; that and kill XP are separate work.
        Drops are handled by drop_loot() above, which at_death runs before this.
        """
        npc_key = self.db.npc_key
        respawn_seconds = self.db.respawn_seconds
        # spawn_room is stamped by NpcDef.create. The location fallback covers
        # NPCs created before that stamp existed, and keeps this correct for
        # anything hand-built with create_object.
        room = self.db.spawn_room or self.location

        if respawn_seconds is not None and npc_key and room is not None:
            try:
                # Local import: avoids a typeclasses <-> systems import cycle
                # at load_all_spawners() time, matching the style below.
                from systems.spawning.respawn import schedule_respawn

                schedule_respawn(npc_key, room, respawn_seconds)
            except Exception:
                # A broken respawn queue must never block the death itself. If
                # delete() were skipped the corpse would linger at 0 hp, the
                # `target.pk is None` guard in ActionAttack.resolve would not
                # fire, and the fight would hang.
                logger.log_trace()

        self.delete()


@register_spawner("Mutant Raider Tile")
def spawn_mutant_raider(room):
    """Spawner entry for the Mutant Raider.

    Stat block lives in world/npc_defs/hostile.py (NpcDef "mutant_raider") and
    is looked up via NPC_DB — the same data-driven shape ItemDef / ITEM_DB
    gives items and ShopDef / SHOP_DB gives shops. Keeping this function lets
    the existing "Mutant Raider Tile" room prototype keep dispatching through
    SPAWNER_REGISTRY unchanged; only its body is now a one-line registry lookup.

    The presence guard mirrors spawn_bank (bank_nodes.py) and spawn_shopkeep
    (npcs.py), which this spawner was the only one missing — so re-running
    `xyzgrid spawn` stacked a fresh raider on the tile every time. It keys on
    db.npc_key rather than is_typeclass because every hostile shares the
    HostileNPC typeclass. Paired with the same guard inside the respawn
    manager, it also closes the grid-rebuild-during-a-dead-window race in both
    interleavings.

    Entry: room (Evennia Room).
    Exit: the created NPC, or None if one was already standing here.
    Module Globals: None.
    """
    from systems.spawning.respawn import npc_present
    from world.npc_database import NPC_DB  # local import: avoids a world<->
    # typeclasses import cycle. npc_combat is imported by SPAWNER_MODULES at
    # load-all-spawners time; world.npc_database is leaf-of-graph (imports only
    # systems.combat.constants + world.npc_defs.hostile, both of which are
    # themselves leaf), so a module-level import is also safe, but matching the
    # existing local-import style in this module's namespace keeps the module
    # importable in isolation (e.g. by the test suite) without forcing world/
    # to be loaded first.
    if npc_present("mutant_raider", room):
        return None
    
    return NPC_DB["mutant_raider"].create(location=room)

@register_spawner("Big Mutant Tile")
def spawn_big_mutant(room):
    """Spawner entry for the Big Mutant.

    Stat block lives in world/npc_defs/hostile.py (NpcDef "big_mutant") and
    is looked up via NPC_DB — the same data-driven shape ItemDef / ITEM_DB
    gives items and ShopDef / SHOP_DB gives shops. Keeping this function lets
    the existing "Big Mutant Tile" room prototype keep dispatching through
    SPAWNER_REGISTRY unchanged; only its body is now a one-line registry lookup.

    The presence guard mirrors spawn_bank (bank_nodes.py) and spawn_shopkeep
    (npcs.py), which this spawner was the only one missing — so re-running
    `xyzgrid spawn` stacked a fresh raider on the tile every time. It keys on
    db.npc_key rather than is_typeclass because every hostile shares the
    HostileNPC typeclass. Paired with the same guard inside the respawn
    manager, it also closes the grid-rebuild-during-a-dead-window race in both
    interleavings.

    Entry: room (Evennia Room).
    Exit: the created NPC, or None if one was already standing here.
    Module Globals: None.
    """
    from systems.spawning.respawn import npc_present
    from world.npc_database import NPC_DB  # local import: avoids a world<->
    # typeclasses import cycle. npc_combat is imported by SPAWNER_MODULES at
    # load-all-spawners time; world.npc_database is leaf-of-graph (imports only
    # systems.combat.constants + world.npc_defs.hostile, both of which are
    # themselves leaf), so a module-level import is also safe, but matching the
    # existing local-import style in this module's namespace keeps the module
    # importable in isolation (e.g. by the test suite) without forcing world/
    # to be loaded first.
    if npc_present("big_mutant", room):
        return None
    
    return NPC_DB["big_mutant"].create(location=room)

@register_spawner("Floating Eye Tile")
def spawn_floating_eye(room):
    """Spawner entry for the Floating Eye.

    Stat block lives in world/npc_defs/hostile.py (NpcDef "floating_eye") and
    is looked up via NPC_DB — the same data-driven shape ItemDef / ITEM_DB
    gives items and ShopDef / SHOP_DB gives shops. Keeping this function lets
    the existing "Floating Eye Tile" room prototype keep dispatching through
    SPAWNER_REGISTRY unchanged; only its body is now a one-line registry lookup.

    The presence guard mirrors spawn_bank (bank_nodes.py) and spawn_shopkeep
    (npcs.py), which this spawner was the only one missing — so re-running
    `xyzgrid spawn` stacked a fresh raider on the tile every time. It keys on
    db.npc_key rather than is_typeclass because every hostile shares the
    HostileNPC typeclass. Paired with the same guard inside the respawn
    manager, it also closes the grid-rebuild-during-a-dead-window race in both
    interleavings.

    Entry: room (Evennia Room).
    Exit: the created NPC, or None if one was already standing here.
    Module Globals: None.
    """
    from systems.spawning.respawn import npc_present
    from world.npc_database import NPC_DB  # local import: avoids a world<->
    # typeclasses import cycle. npc_combat is imported by SPAWNER_MODULES at
    # load-all-spawners time; world.npc_database is leaf-of-graph (imports only
    # systems.combat.constants + world.npc_defs.hostile, both of which are
    # themselves leaf), so a module-level import is also safe, but matching the
    # existing local-import style in this module's namespace keeps the module
    # importable in isolation (e.g. by the test suite) without forcing world/
    # to be loaded first.
    if npc_present("floating_eye", room):
        return None
    
    return NPC_DB["floating_eye"].create(location=room)
