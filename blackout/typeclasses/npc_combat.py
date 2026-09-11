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

from systems.gameplay.combat import constants as combat_constants
from systems.gameplay.progression.skills.constants import COMBAT_SKILL_KEYS
from systems.gameplay.progression.skills.stat_block import StatBlockSkills
from typeclasses.mixins import CombatEntity
from typeclasses.objects import ObjectParent, Unpocketable

from .spawners import register_spawner


class HostileNPC(Unpocketable, CombatEntity, ObjectParent, DefaultObject):
    """
    Purpose: An aggressive NPC enemy for batch 2 melee combat testing.

    Entry (at_object_creation):
        self.db.combat_stats should be populated by the caller spawner
        for stat seeding before init_combat_attrs runs. Minimum keys:
            - strike_level (int)
            - brawn_level (int)
            - defense_level (int)
            - fortitude_level (int; NpcDef.to_combat_block derives it from
                               max_hp when the def does not set it)
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

    # Refused by Unpocketable.at_pre_get. A live enemy in your bag never dies
    # in its room, so HostileNPC.respawn never runs and its tile stays empty
    # for good -- see the mixin in typeclasses/objects.py for the full story.
    cannot_get_message = "{name} is still moving. Killing it first is the usual order."


    @lazy_property
    def skills(self) -> StatBlockSkills:
        """Lazy cached level source, exposing `npc.skills.get_level(...)`.

        A StatBlockSkills, not a SkillHandler: an NPC's levels are authored by
        its NpcDef rather than earned, so there is no XP curve behind them and
        nothing that could advance them. It satisfies the SkillSource protocol
        and deliberately NOT XpEarner, which is what stops the killer-XP gate
        in CombatEntity.at_death and the per-hit XP planner in the combat
        handler from paying a monster for hitting a player.

        Before any of this existed HostileNPC had no `skills` attribute at all,
        so ActionAttack.resolve defaulted every NPC's defense level to 1 and
        made enemies trivially hittable regardless of their intended stats.
        """
        return StatBlockSkills(self)


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
                    If given, it is also stored to db.combat_stats, which
                    stays the authored wire shape; the "<skill>_level" keys in
                    it are unpacked below into the dict StatBlockSkills reads.
        """
        if stats is not None:
            self.db.combat_stats = stats

        raw_stats = self.db.combat_stats or {}

        # Unpack the "<skill>_level" keys into the {skill_key: level} dict
        # StatBlockSkills reads. The stat block keeps its flat wire shape --
        # it is what an NpcDef authors and what a prototype can carry -- and
        # this is the one place that translates between the two, exactly as
        # the lines below translate its other keys onto discrete attributes.
        #
        # Going through self.skills is safe on the creation path even though it
        # is a lazy_property: StatBlockSkills holds nothing but a reference to
        # this object, so a handler built here stays correct afterwards.
        #
        # A key the stat block does not name is left out rather than defaulted,
        # so StatBlockSkills answers its own absent-skill floor instead of this
        # method inventing one. That is the shim bug in miniature: the old
        # facade's silent 1 for a missing key is exactly why every NPC read
        # Fortitude 1 for as long as to_combat_block omitted it.
        self.skills.seed(
            {
                skill_key: raw_stats[f"{skill_key}_level"]
                for skill_key in COMBAT_SKILL_KEYS
                if f"{skill_key}_level" in raw_stats
            }
        )

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
            # Local import: systems.gameplay.loot pulls in world.item_database, and
            # this module is loaded by SPAWNER_MODULES at load_all_spawners()
            # time. Matches the local-import style used throughout this module.
            from systems.gameplay.loot.drops import award_drops

            award_drops(self, killer)
        except Exception:
            logger.log_trace()


    def leave_corpse(self, killer=None) -> None:
        """Leave this NpcDef's corpse on the floor of the room it died in.

        The corpse is named by its NpcDef's `corpse_key` and resolved live
        through db.npc_key, so an NPC with no corpse_key simply leaves nothing
        -- opt-in, exactly as loot_table and respawn_seconds are.

        The body carries `corpse_npc_key`, NOT `npc_key`. That is the whole
        reason corpses were dangerous to add: `npc_key` is what
        systems/gameplay/spawning/respawn.py npc_present() matches on, so a
        corpse answering to it reads as a live raider standing on the tile.
        The sweep does not requeue a blocked entry, it DROPS it -- the raider
        would never return, and taking the corpse away afterwards could not
        undo it. The same attribute is also the first branch of the
        statefeed's _asset_identity, which would have drawn a walking raider
        where the body lies.

        Wrapped the way drop_loot is: a broken corpse def must never block the
        death itself, because a skipped respawn() leaves a 0-hp corpse
        standing and hangs the fight.
        """
        try:
            # Local imports: world.item_database and world.npc_database pull
            # in every def module, and this module is loaded by
            # SPAWNER_MODULES at load_all_spawners() time. Matches the
            # local-import style used throughout this module.
            from typeclasses.corpses import CORPSE_NPC_KEY_ATTR
            from world.item_database import ITEM_DB
            from world.npc_database import NPC_DB

            npc_key = self.db.npc_key
            npc_def = NPC_DB.get(npc_key)

            if npc_def is None or not npc_def.corpse_key:
                return

            room = self.location

            if room is None:
                return

            item_def = ITEM_DB.get(npc_def.corpse_key)

            if item_def is None:
                logger.log_err(
                    f"HostileNPC.leave_corpse: {npc_key!r} names unknown "
                    f"corpse item {npc_def.corpse_key!r}."
                )
                return

            corpse = item_def.create(location=room)
            corpse.attributes.add(CORPSE_NPC_KEY_ATTR, npc_key)
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
                from systems.gameplay.spawning.respawn import schedule_respawn

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
    from systems.gameplay.spawning.respawn import npc_present
    from world.npc_database import NPC_DB  # local import: avoids a world<->
    # typeclasses import cycle. npc_combat is imported by SPAWNER_MODULES at
    # load-all-spawners time; world.npc_database is leaf-of-graph (imports only
    # systems.gameplay.combat.constants + world.npc_defs.hostile, both of which are
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
    from systems.gameplay.spawning.respawn import npc_present
    from world.npc_database import NPC_DB  # local import: avoids a world<->
    # typeclasses import cycle. npc_combat is imported by SPAWNER_MODULES at
    # load-all-spawners time; world.npc_database is leaf-of-graph (imports only
    # systems.gameplay.combat.constants + world.npc_defs.hostile, both of which are
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
    from systems.gameplay.spawning.respawn import npc_present
    from world.npc_database import NPC_DB  # local import: avoids a world<->
    # typeclasses import cycle. npc_combat is imported by SPAWNER_MODULES at
    # load-all-spawners time; world.npc_database is leaf-of-graph (imports only
    # systems.gameplay.combat.constants + world.npc_defs.hostile, both of which are
    # themselves leaf), so a module-level import is also safe, but matching the
    # existing local-import style in this module's namespace keeps the module
    # importable in isolation (e.g. by the test suite) without forcing world/
    # to be loaded first.
    if npc_present("floating_eye", room):
        return None
    
    return NPC_DB["floating_eye"].create(location=room)
