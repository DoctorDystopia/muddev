"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/30/2026
Description: NpcDef, which defines every NPC, and the NPC_DB registry.

             ONE DEF FOR EVERY NPC (Nick, 10/09/2026). Each NPC is one NpcDef
             entry in a module under world/npc_defs/: a hostile, a shopkeep,
             a Preceptor, or a quest giver. The registry finds each module.
             Thus, a new NPC is one dict entry, and a new group of NPCs is
             one file.

             An NpcDef gives what an NPC IS: its name, its description, its
             model, its dialogue, and its role data. A combatant also has a
             `combat` block (NpcCombat). An NPC with no `combat` block cannot
             fight, and nothing in combat reads it.

             EACH READER READS THE DEF LIVE. Each NPC carries db.npc_key,
             and every reader goes through NPC_DB with that key. Thus, an edit to a def
             reaches the NPCs that already stand in the world, with no
             migration. CLAUDE.md, "An import path belongs in the code, never
             in a database row", gives the reason.
"""

import importlib
import pkgutil
from dataclasses import dataclass, field

from evennia import create_object

from systems.gameplay.ai import constants as ai_constants
from systems.gameplay.combat import constants as combat_constants


# The attribute an NPC carries to name the NpcDef it was spawned from. It is
# the identity every live lookup goes through -- the loot table, the corpse,
# the respawn, the behaviour, the description and the dialogue -- so the
# answer to "what is this thing" stays in this file even for an NPC that
# spawned a month ago.
NPC_KEY_ATTR: str = "npc_key"

# The typeclass of each NPC role. A role is a typeclass, never a subclass for
# each NPC. Two Preceptors differ only in the data of their defs.
NPC_TYPECLASS_HOSTILE: str = "typeclasses.npc_combat.HostileNPC"
NPC_TYPECLASS_TALKATIVE: str = "typeclasses.npcs.TalkativeNPC"
NPC_TYPECLASS_SHOPKEEP: str = "typeclasses.npcs.ShopkeepNPC"
NPC_TYPECLASS_PRECEPTOR: str = "typeclasses.npcs.PreceptorNPC"

# The package that holds the dialogue modules. NpcDef.dialogue names a module
# in it.
DIALOGUE_PACKAGE: str = "world.npc_dialogues"

# The package that holds the def modules, and the dict that each one exports.
_DEFS_PACKAGE: str = "world.npc_defs"
_DEFS_ATTR: str = "NPCS"


@dataclass
class NpcCombat:
    """The combat block of an NPC that can fight.

    Field surface covers what HostileNPC.apply_combat_stats consumes (the
    combat stat block), plus the facts NpcDef.create stamps onto the spawned
    object so they survive the row being deleted: respawn_seconds and
    ai_behavior. Unprovoked-aggression flags are still a deferred addition on
    top of this base; ai_behavior only decides how an NPC answers a fight it
    is already in.

    Skill-axis levels are flat ints, unpacked by apply_combat_stats into the
    {skill_key: level} dict StatBlockSkills reads, so the OSRS combat math
    picks the NPC's strike / brawn / defense / fortitude the same way it does
    a Character's. Raw OSRS monster stat values (e.g. Goblin L2's attack -21,
    def -15) transfer directly because combat_calc.py uses the same integer
    keys weapon ItemDefs use.

    Everything an NPC needs only because it can die lives here too: its
    respawn, its loot, its corpse, and its creature types. An NPC that cannot
    fight cannot die, so it carries none of them.
    """

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
    #     max_hp is still the field a combat block is expected to set: an OSRS
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

    # combat_rules — list of keys into systems/gameplay/combat/rules/RULES_REGISTRY,
    #     naming rules definitions that change how this NPC's actions resolve.
    #     An NPC has no equipment handler and carries its stat block on
    #     itself, so this is where a monster with unusual math declares it --
    #     the same field name an ItemDef uses, read by the same collector.
    combat_rules: list = field(default_factory=list)

    # ─── Respawn ─────────────────────────────────────────────────────
    # None  -> despawn permanently on death (the historical behavior; every
    #          NPC type is opt-in).
    # int   -> whole seconds. HostileNPC.respawn() enqueues on the global
    #          BlackoutRespawnManager (systems/gameplay/spawning/respawn.py), which
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
    #     systems/gameplay/loot/drops.py resolves it live through db.npc_key -> NPC_DB.
    #     That keeps one owner for the fact and means editing a table plus
    #     `evennia reload` affects NPCs already standing on the grid.
    loot_table: str | None = None

    # corpse_key — key into world.item_database.ITEM_DB naming the corpse this
    #     NPC leaves behind, or None for one that leaves nothing. Opt-in, the
    #     way loot_table and respawn_seconds are: an NPC nobody has written a
    #     corpse for simply vanishes on death, as every NPC did before this.
    #
    #     Resolved live through db.npc_key -> NPC_DB for the same reason
    #     loot_table is, and NOT stamped onto the object: the corpse is created
    #     while the NPC still exists (at_death runs leave_corpse before
    #     respawn() deletes the row), so there is nothing for a stamp to
    #     outlive.
    #
    #     The ItemDef it names is what carries the gatherable_key, so what a
    #     corpse YIELDS is not restated here -- this field says only that
    #     there is one.
    corpse_key: str | None = None

    # ─── Exterminator ────────────────────────────────────────────────
    # creature_types — the keys into world/creature_types.CREATURE_TYPES that
    #     this NPC belongs to. An Exterminator task of any of these types
    #     counts a kill of this NPC. An empty tuple means that no task counts
    #     it.
    #
    #     Not stamped onto the object, for the reason that loot_table gives.
    #     creature_types_of below reads it live through db.npc_key. Thus, a
    #     changed type reaches the NPCs that already stand in the world.
    creature_types: tuple = ()

    # ─── AI ──────────────────────────────────────────────────────────
    # ai_behavior — key into systems/gameplay/ai/registry.BEHAVIOR_REGISTRY, naming the
    #     behaviour the combat handler consults when this NPC has no pending
    #     action. None means the NPC never acts on its own, which is what every
    #     hostile did before this field existed.
    #
    #     Defaults to CHASING retaliation rather than to None: a hostile that
    #     stands still while being hit is the bug this field exists to fix, so
    #     the safe default is the one that makes a monster behave like one. A
    #     genuinely passive NPC (a training dummy, a quest-giver that can be
    #     attacked) sets this to None explicitly.
    #
    #     IT CHASES BECAUSE A BOW EXISTS. The default was aggressive_melee
    #     until 09/17/2026, which retaliates only against something standing on
    #     its own tile -- so an archer seven tiles away took no damage ever,
    #     and every balance figure for a projectile weapon was a fiction. The
    #     leash still bounds it; see LEASH_DISTANCE_TILES.
    #
    #     Stamped onto the object by create(), alongside npc_key, but READ
    #     BACK THROUGH THIS DEF rather than off the row -- see
    #     ai/registry.behavior_key_for. A changed default has to reach the
    #     NPCs already standing in the world, and a stamped row is exactly
    #     what stops it. CLAUDE.md, "An import path belongs in the code, never
    #     in a database row", records the same lesson twice already.
    ai_behavior: str | None = ai_constants.AI_BEHAVIOR_CHASING_MELEE


    def to_combat_block(self) -> dict:
        """Assemble the dict shape HostileNPC.apply_combat_stats expects.

        Resolves None attack_speed / default_combat_style to their unarmed
        canonical constants so individual entries can omit them (an unarmed
        goblin shouldn't have to repeat UNARMED_* in its def), and resolves
        None fortitude_level to max_hp for the same reason.
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



@dataclass
class NpcDef:
    """
    Purpose: Define one NPC, of any role.

    Entry:
        key is the stable snake_case identity. NPC_DB files the def under
        it. db.npc_key holds it. A `kill` quest verb names it.
        name is the object key that a player sees.
        typeclass is the role: one of the NPC_TYPECLASS_* paths. None means
        "hostile if it has a combat block, else talkative".
        desc is what `look` shows. The NPC reads it live through its def.
        asset_key names the model record. None means the key itself.
        dialogue names a module in DIALOGUE_PACKAGE. None means that the NPC
        has nothing to say.
        shop_key names a ShopDef in world/shop_defs. A shopkeep needs one.
        preceptor_key names a PreceptorDef. A Preceptor needs one.
        combat is the combat block. None means that the NPC cannot fight.

    Exit/Returns:
        Not applicable. A dataclass.

    Module Globals:
        None.

    Methodology:
        The role data is two plain fields, not a dict, so a grep for
        `shop_key=` finds every shopkeep. A role with no data of its own (a
        quest giver) needs no field.

        A tile room stores no fact about its NPC, and the NPC stores only its
        key. Every other fact is here.

    Notes/References:
        world/tests/test_npc_database.py checks the rules of each entry.

    Author: Nick Hobar
    Creation date: 07/30/2026. One def for every NPC: 10/09/2026.
    """

    key: str
    name: str
    typeclass: str | None = None
    desc: str = ""
    asset_key: str | None = None
    dialogue: str | None = None
    shop_key: str | None = None
    preceptor_key: str | None = None
    combat: NpcCombat | None = None


    def resolved_typeclass(self) -> str:
        """The typeclass path that create() uses. See `typeclass`."""
        if self.typeclass:
            return self.typeclass

        if self.combat is not None:
            return NPC_TYPECLASS_HOSTILE

        return NPC_TYPECLASS_TALKATIVE


    def resolved_asset_key(self) -> str:
        """The model record key that the statefeed sends. See `asset_key`."""
        if self.asset_key:
            return self.asset_key

        return self.key


    def dialogue_module(self) -> str | None:
        """The python path of the dialogue module, or None. See `dialogue`."""
        if not self.dialogue:
            return None

        return f"{DIALOGUE_PACKAGE}.{self.dialogue}"


    def create(self, location=None):
        """Spawn the NPC at `location`, and stamp its identity.

        Stamps db.npc_key on every NPC. The NPC reads every other fact live
        through that key. Thus, a talking NPC needs no other stamp.

        A combatant gets three more stamps. HostileNPC.at_object_creation
        calls apply_combat_stats() with an empty stat block (the spawner
        cannot have written db.combat_stats yet — that hook runs inside
        create_object before the caller gets the object back). We therefore
        call apply_combat_stats(to_combat_block()) ourselves immediately after
        creation, which is idempotent. It also stamps the respawn identity
        (spawn_room / respawn_seconds) that HostileNPC.respawn and the
        duplicate guards in systems/gameplay/spawning/respawn.py read back.
        """
        obj = create_object(
            self.resolved_typeclass(),
            key=self.name,
            location=location,
        )

        # Identity stamp. The respawn manager has to look this def back up in
        # NPC_DB after the object itself is gone, and the duplicate guards need
        # an identity finer-grained than typeclass (every hostile is a
        # HostileNPC, so is_typeclass cannot tell two enemy types apart).
        obj.attributes.add(NPC_KEY_ATTR, self.key)

        if self.combat is not None:
            self._stamp_combat(obj, location)

        return obj


    def _stamp_combat(self, obj, location) -> None:
        """Apply the combat block, and stamp the facts that outlive the row."""
        # apply_combat_stats stores the block to db.combat_stats AND unpacks
        # it into the discrete db attributes the combat handler reads.
        obj.apply_combat_stats(self.combat.to_combat_block())

        # Spawn point, read by HostileNPC.respawn(). Deliberately not `home`:
        # blackout sets no DEFAULT_HOME, so a missed stamp would silently
        # respawn the NPC in Limbo, and Evennia already overloads `home` as the
        # fallback destination for a deleted container's contents.
        obj.db.spawn_room = location

        # None -> permanent despawn on death. int -> HostileNPC.respawn()
        # enqueues on the global BlackoutRespawnManager.
        obj.db.respawn_seconds = self.combat.respawn_seconds

        # Which behaviour the combat handler's controller seam consults for
        # this NPC.
        #
        # STAMPED, BUT NOT AUTHORITATIVE. behavior_key_for reads this def
        # first, through npc_key, and falls back to the row only for an NPC
        # that names no def at all. The row is kept so `examine` answers the
        # question and so a hand-built NPC has somewhere to declare one -- not
        # so the game can read it. Reading it first is what froze every raider
        # already in the world on the behaviour it spawned with.
        obj.db.ai_behavior = self.combat.ai_behavior



def _discover_defs() -> dict:
    """
    Purpose: Build NPC_DB from every module under world/npc_defs/.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a dict of npc key -> NpcDef.

    Module Globals:
        _DEFS_PACKAGE, _DEFS_ATTR read.

    Methodology:
        Each module exports a dict named NPCS. A new module needs no
        registration. Two faults raise at import: a key that two modules
        define, and an entry whose dict key differs from its own `key`.
        Thus, the fault is a failed test, not an NPC that silently takes the
        place of another.

    Notes/References:
        The skill registry and the quest loader walk their packages the same
        way. The modules import NpcDef from this module, so this runs at the
        bottom of the file, after the classes exist.

    Author: Nick Hobar
    Creation date: 10/09/2026
    """
    registry = {}
    package = importlib.import_module(_DEFS_PACKAGE)

    for info in pkgutil.iter_modules(package.__path__):
        module = importlib.import_module(f"{_DEFS_PACKAGE}.{info.name}")
        entries = getattr(module, _DEFS_ATTR, {})

        for key, npc_def in entries.items():
            if key != npc_def.key:
                raise ValueError(
                    f"NPC_DB: {info.name} files {npc_def.key!r} under {key!r}.")

            if key in registry:
                raise ValueError(f"NPC_DB: {key!r} is defined two times.")

            registry[key] = npc_def

    return registry



NPC_DB: dict[str, NpcDef] = _discover_defs()



def combatant_defs() -> dict:
    """
    Purpose: Give the defs of the NPCs that can fight.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a dict of npc key -> NpcDef, in NPC_DB order, with only the
        defs that have a combat block.

    Module Globals:
        NPC_DB read.

    Methodology:
        A balance script or a combat test walks this, not NPC_DB. A
        shopkeep has no stat block to read.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/09/2026
    """
    return {key: npc_def for key, npc_def in NPC_DB.items()
            if npc_def.combat is not None}



def npc_def_of(npc) -> NpcDef | None:
    """
    Purpose: Give the NpcDef of a live NPC.

    Entry:
        npc is an Evennia object. It can carry db.npc_key.

    Exit/Returns:
        Returns the NpcDef that db.npc_key names. Returns None if the object
        has no npc_key, or if the key names no def. None is the normal result
        for a player or an item, not an error.

    Module Globals:
        NPC_DB, NPC_KEY_ATTR read.

    Methodology:
        Reads the def live from NPC_DB, never a stamp on the object.

    Notes/References:
        The NPC typeclasses read their description, model, dialogue and role
        data through this.

    Author: Nick Hobar
    Creation date: 10/09/2026
    """
    npc_key = npc.attributes.get(NPC_KEY_ATTR, default=None)

    if not npc_key:
        return None

    return NPC_DB.get(npc_key)



def creature_types_of(npc) -> tuple:
    """
    Purpose: Give the creature types of an NPC, for an Exterminator task.

    Entry:
        npc is an Evennia object. It can carry db.npc_key.

    Exit/Returns:
        Returns the creature_types tuple of the combat block of the NpcDef
        that db.npc_key names. Returns an empty tuple if the object has no
        npc_key, if the key names no NpcDef, or if the def has no combat
        block. An empty tuple is the normal result for a player or an item,
        not an error.

    Module Globals:
        NPC_DB read.

    Methodology:
        Read the NpcDef live through npc_def_of. Do not read a stamp on the
        object, so a changed def reaches every NPC that already stands in the
        world. `resolve_table` in systems/gameplay/loot/drops.py reads the
        loot table the same way.

    Notes/References:
        This is the one reader of NpcCombat.creature_types. The kill hook and
        the buff check of DESIGN-0012 both call it. Call it before
        HostileNPC.respawn deletes the row.

    Author: Nick Hobar
    Creation date: 10/06/2026
    """
    npc_def = npc_def_of(npc)

    if npc_def is None or npc_def.combat is None:
        return ()

    return npc_def.combat.creature_types
