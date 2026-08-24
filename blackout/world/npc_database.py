"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/30/2026
Description: NpcDef dataclass and the NPC_DB registry, mirroring ItemDef /
             ITEM_DB for combatant NPCs.
"""

from dataclasses import dataclass, field

from evennia import create_object

from systems.ai import constants as ai_constants
from systems.combat import constants as combat_constants


@dataclass
class NpcDef:
    """Data-driven definition of a combatant NPC.

    Mirrors the ItemDef / SHOP_DB pattern so enemy stat blocks share the
    same greppable, data-driven shape as items and shops. Concrete entries
    live in per-category modules under world/npc_defs/ and are merged into
    the single NPC_DB registry below.

    Field surface covers what HostileNPC.apply_combat_stats consumes (the
    combat stat block), plus the facts create() stamps onto the spawned object
    so they survive the row being deleted: respawn_seconds and ai_behavior.
    Unprovoked-aggression flags are still a deferred addition on top of this
    base; ai_behavior only decides how an NPC answers a fight it is already in.

    Skill-axis levels are flat ints, unpacked by apply_combat_stats into the
    {skill_key: level} dict StatBlockSkills reads, so the OSRS combat math
    picks the NPC's strike / brawn / defense / fortitude the same way it does
    a Character's. Raw OSRS monster stat values (e.g. Goblin L2's attack -21,
    def -15) transfer directly because combat_calc.py uses the same integer
    keys weapon ItemDefs use.
    """

    key: str
    name: str
    typeclass: str = "typeclasses.npc_combat.HostileNPC"
    desc: str = ""

    # ─── Skill-axis levels (read by StatBlockSkills) ─────────────────
    strike_level: int = 1
    brawn_level: int = 1
    defense_level: int = 1
    max_hp: int = 1

    # fortitude_level — the NPC's Hitpoints axis. None means "derive it from
    #     max_hp", which is what every NpcDef written before this field existed
    #     wants: HP_PER_FORTITUDE_LEVEL is 1, so Fortitude and max HP are the
    #     same number by definition (the vault's rule, and what
    #     logic.sync_max_hp_from_fortitude enforces for characters).
    #
    #     It has to be here at all because combat_level's base term is
    #     (Fortitude + Defense). Before the field existed, to_combat_block
    #     never emitted a Fortitude and the old NPC skill shim answered its
    #     unknown-key default of 1 -- so the Big Mutant's 87 hitpoints computed
    #     a combat level off a Fortitude of 1, and every rules definition that
    #     reads the Brawn-over-Fortitude surplus (the Glass Cannon amulet)
    #     evaluated against a number nobody had written down.
    #
    #     max_hp is still the field an NpcDef is expected to set: an OSRS
    #     monster's stat block is quoted as Hitpoints, and that is what it
    #     transfers to. Setting this explicitly is for a monster whose
    #     Fortitude axis deliberately differs from its HP pool.
    fortitude_level: int | None = None

    # ─── Combat tunables ─────────────────────────────────────────────
    # attack_speed — integer ticks; one tick = TICK_SECONDS (0.6s).
    #     None falls back to UNARMED_ATTACK_SPEED_TICKS at create time.
    attack_speed: int | None = None

    # combat_stat_bonuses — dict[str, int] keyed by per-damage-type stat
    #     (same keys weapon ItemDefs use: stab/slash/crush_attack_bonus,
    #     *_defense_bonus, melee_strength_bonus). The active style's
    #     attack_type selects which *_attack_bonus feeds the accuracy roll.
    combat_stat_bonuses: dict = field(default_factory=dict)

    # combat_styles — dict[style_name, dict]. Sub-dicts contain:
    #     { 'attack_type': 'stab'|'slash'|'crush',
    #       'weapon_style': 'accurate'|'aggressive'|'defensive'|'controlled',
    #       'weapon_style_xp_skill': <str|tuple of str>,
    #       'weapon_style_level_boost': <MELEE_WEAPON_STYLE_LEVEL_BOOST_* ref> }
    # A single skill key or any iterable of them is accepted; the combat
    # handler's _normalize_xp_skills handles both forms.
    combat_styles: dict = field(default_factory=dict)
    default_combat_style: str | None = None

    # combat_rules — list of keys into systems/combat/rules/RULES_REGISTRY,
    #     naming rules definitions that change how this NPC's actions resolve.
    #     An NPC has no equipment handler and carries its stat block on
    #     itself, so this is where a monster with unusual math declares it --
    #     the same field name an ItemDef uses, read by the same collector.
    combat_rules: list = field(default_factory=list)

    # ─── Respawn ─────────────────────────────────────────────────────
    # None  -> despawn permanently on death (the historical behavior; every
    #          NPC type is opt-in).
    # int   -> whole seconds. HostileNPC.respawn() enqueues on the global
    #          BlackoutRespawnManager (systems/spawning/respawn.py), which
    #          re-creates the NPC on its spawn tile once the deadline passes.
    respawn_seconds: int | None = None

    # ─── Loot ────────────────────────────────────────────────────────
    # loot_table — key into world/loot_database.LOOT_DB, or None for an NPC
    #     that drops nothing. Several NpcDefs may name the SAME table; that is
    #     how a shared rare table works without duplicating data.
    #
    #     Deliberately NOT stamped onto the object by create(), unlike
    #     respawn_seconds. Respawn has to survive the row being deleted, so it
    #     must be stamped; loot rolls while the NPC still exists, so
    #     systems/loot/drops.py resolves it live through db.npc_key -> NPC_DB.
    #     That keeps one owner for the fact and means editing a table plus
    #     `evennia reload` affects NPCs already standing on the grid.
    loot_table: str | None = None

    # ─── AI ──────────────────────────────────────────────────────────
    # ai_behavior — key into systems/ai/registry.BEHAVIOR_REGISTRY, naming the
    #     behaviour the combat handler consults when this NPC has no pending
    #     action. None means the NPC never acts on its own, which is what every
    #     hostile did before this field existed.
    #
    #     Defaults to retaliation rather than to None: a hostile that stands
    #     still while being hit is the bug this field exists to fix, so the
    #     safe default is the one that makes a monster behave like one. A
    #     genuinely passive NPC (a training dummy, a quest-giver that can be
    #     attacked) sets this to None explicitly.
    #
    #     Stamped onto the object by create(), alongside npc_key -- NOT part of
    #     to_combat_block. It is not a combat statistic; it decides who is
    #     asked for an action, not how one resolves.
    ai_behavior: str | None = ai_constants.AI_BEHAVIOR_AGGRESSIVE_MELEE


    def to_combat_block(self) -> dict:
        """Assemble the dict shape HostileNPC.apply_combat_stats expects.

        Resolves None attack_speed / default_combat_style to their unarmed
        canonical constants so individual NpcDef entries can omit them
        (an unarmed goblin shouldn't have to repeat UNARMED_* in its def), and
        resolves None fortitude_level to max_hp for the same reason.
        """
        return {
            "strike_level": self.strike_level,
            "brawn_level": self.brawn_level,
            "defense_level": self.defense_level,
            "fortitude_level": (
                self.fortitude_level
                if self.fortitude_level is not None
                else self.max_hp
            ),
            "max_hp": self.max_hp,
            "attack_speed": (
                self.attack_speed
                if self.attack_speed is not None
                else combat_constants.UNARMED_ATTACK_SPEED_TICKS
            ),
            "combat_stat_bonuses": dict(self.combat_stat_bonuses),
            "combat_styles": dict(self.combat_styles),
            "default_combat_style": (
                self.default_combat_style
                if self.default_combat_style is not None
                else combat_constants.UNARMED_DEFAULT_COMBAT_STYLE
            ),
            "combat_rules": list(self.combat_rules),
        }


    def create(self, location=None):
        """Spawn the NPC at `location`, applying this NpcDef's combat block.

        HostileNPC.at_object_creation calls apply_combat_stats() with an
        empty stat block (the spawner cannot have written db.combat_stats
        yet — that hook runs inside create_object before the caller gets
        the object back). We therefore call apply_combat_stats(to_combat_block())
        ourselves immediately after creation, which is idempotent and the
        exact pattern the existing inline spawn_mutant_raider followed.

        Also stamps the respawn identity (npc_key / spawn_room /
        respawn_seconds) that HostileNPC.respawn and the duplicate guards in
        systems/spawning/respawn.py read back.
        """
        obj = create_object(
            self.typeclass,
            key=self.name,
            location=location,
        )

        # apply_combat_stats stores the block to db.combat_stats AND unpacks
        # it into the discrete db attributes the combat handler reads.
        obj.apply_combat_stats(self.to_combat_block())
        if self.desc:
            obj.db.desc = self.desc

        # Identity stamp. The respawn manager has to look this def back up in
        # NPC_DB after the object itself is gone, and the duplicate guards need
        # an identity finer-grained than typeclass (every hostile is a
        # HostileNPC, so is_typeclass cannot tell two enemy types apart).
        obj.db.npc_key = self.key

        # Spawn point, read by HostileNPC.respawn(). Deliberately not `home`:
        # blackout sets no DEFAULT_HOME, so a missed stamp would silently
        # respawn the NPC in Limbo, and Evennia already overloads `home` as the
        # fallback destination for a deleted container's contents.
        obj.db.spawn_room = location

        # None -> permanent despawn on death. int -> HostileNPC.respawn()
        # enqueues on the global BlackoutRespawnManager.
        obj.db.respawn_seconds = self.respawn_seconds

        # Which behaviour the combat handler's controller seam consults for
        # this NPC. Stamped rather than looked up live because the seam runs on
        # every idle combat tick, and an NPC_DB round trip per tick per
        # combatant is the cost this avoids.
        obj.db.ai_behavior = self.ai_behavior

        return obj


from .npc_defs.hostile import NPCS as _HOSTILE

NPC_DB: dict[str, NpcDef] = {}

for _d in [_HOSTILE]:
    NPC_DB.update(_d)
