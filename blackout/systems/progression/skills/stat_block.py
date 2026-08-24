"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/23/2026
Description: StatBlockSkills — the SkillSource implementation for entities whose
             levels are authored rather than earned (hostile NPCs).

Why this is not a SkillHandler
------------------------------
A character's level is DERIVED: `db.skills[key]` holds an xp total and a level
that add_xp advances along a curve. A monster's level is AUTHORED: the NpcDef
says Defence 1 and that is the whole truth -- there is no curve behind it, no
xp total, and nothing that could ever advance it.

Modelling monsters with a SkillHandler would mean carrying an xp field that is
structurally meaningless, and would run them through `logic.ensure_skill`,
which WRITES INTO `db.skills` on read for any registered-but-untracked key --
so a rules definition that read `guns` off a goblin would permanently grow that
goblin a Guns skill. This class touches SKILL_REGISTRY not at all.

What it replaces
----------------
`_NpcSkillsShim` (typeclasses/npc_combat.py), a read-only facade over the flat
`db.combat_stats["<key>_level"]` dict. Two things were wrong with it beyond
being a stopgap:

1. It answered `1` for any key the stat block did not name, so every NPC in the
   game reported Fortitude 1 -- `NpcDef.to_combat_block()` never emitted
   `fortitude_level`. That number is combat_level's base term, so the Big
   Mutant's 87 hitpoints computed a combat level off a Fortitude of 1.
   Fabricating a plausible number is worse than reporting the real one: nobody
   sees a bug, they see a monster that is mysteriously easy.

2. It was read-only, so nothing could change an NPC's levels at all. set_level
   and modify_level below supply the PERMANENT half of that -- what a stat
   drain writes. The transient half (a boost that wears off) is
   `combat_calc.effective_level`'s `potion_boost` parameter, which has existed
   since that function was written and still has nothing wired to it on either
   side; see modify_level's Methodology for why it does not belong here.

Storage
-------
`obj.db.skill_levels`, a flat `{skill_key: level}` dict -- the same *shape* a
character's levels have once the xp is set aside, so a caller that wants "this
combatant's levels" reads one thing from either implementation.
"""

from evennia.utils import logger

from . import constants as skill_constants


# ─── Public constant definitions ────────────────────────────────────────────

# The Attribute StatBlockSkills reads and writes. Named here rather than spelled
# as a literal at each access because HostileNPC.apply_combat_stats populates it
# and the tests assert against it -- three owners of one string.
SKILL_LEVELS_ATTR: str = "skill_levels"


# ─── Private constant definitions ───────────────────────────────────────────

# What get_level answers for a skill the stat block does not declare.
#
# DEFAULT_START_LEVEL (0), not 1. Zero is what a character who has never
# trained a skill has, so an NPC with no Guns line reads the same as a player
# who has never fired one, and `effective_level(0)` floors to the same place
# for both. The shim's 1 was a fabrication chosen to keep a KeyError out of the
# tick loop, and it hid the missing-Fortitude bug for as long as it existed.
_ABSENT_SKILL_LEVEL: int = skill_constants.DEFAULT_START_LEVEL


class StatBlockSkills:
    """
    Purpose: Read and write the authored skill levels of an entity that earns
    no experience. The NPC half of the SkillSource protocol.

    Entry:
        obj - any Evennia object with a `db` handler. Its
              db.<SKILL_LEVELS_ATTR> is created empty on first access if it
              does not exist, so an NPC built by hand rather than by an NpcDef
              is a supported (if unarmed) case.

    Exit/Returns:
        Not applicable -- a handler.

    Module Globals:
        SKILL_LEVELS_ATTR read. _ABSENT_SKILL_LEVEL read.

    Methodology:
        Every read and write goes through _levels(), which is the only place
        that knows the storage shape. Levels are clamped to the same
        [MIN_BASE_SKILL_LEVEL, MAX_BASE_SKILL_LEVEL] band a character's are, so
        a drain cannot push a monster below zero and a buff cannot push it past
        the scale.

        There is no add_xp, get_total_xp or meets_prerequisite. That is the
        point of the XpEarner/SkillSource split in systems/combat/protocols.py:
        an NPC does not implement the XP surface, so a caller asking
        `isinstance(entity, XpEarner)` gets the right answer instead of finding
        a no-op method and believing it.

    Notes/References:
        systems/combat/protocols.py holds the contract this satisfies.

    Author: Nick Hobar
    Creation date: 08/23/2026
    """

    def __init__(self, obj) -> None:
        """Bind to an entity. Does not touch the database."""
        self.obj = obj


    def _levels(self) -> dict:
        """Return the live level dict, seeding an empty one on first use.

        Returns the ACTUAL dict, not a copy: callers below mutate it and then
        reassign the Attribute, which is what Evennia needs to see in order to
        serialise the change (mutating in place alone does not always mark the
        Attribute dirty).
        """
        stored = getattr(self.obj.db, SKILL_LEVELS_ATTR, None)

        if stored is None:
            stored = {}
            setattr(self.obj.db, SKILL_LEVELS_ATTR, stored)

        return stored


    def _store(self, levels: dict) -> None:
        """Write the level dict back, so Evennia serialises the change."""
        setattr(self.obj.db, SKILL_LEVELS_ATTR, levels)


    def _clamped(self, level: int) -> int:
        """Bring a level inside the legal band. Same band a character uses."""
        floor = skill_constants.MIN_BASE_SKILL_LEVEL
        ceiling = skill_constants.MAX_BASE_SKILL_LEVEL

        if level < floor:
            return floor

        if level > ceiling:
            return ceiling

        return level


    # ─── SkillSource ────────────────────────────────────────────────────────

    def get_level(self, skill_key: str) -> int:
        """
        Purpose: Report this entity's level in a skill.

        Entry:
            skill_key - any string. Deliberately NOT validated against
                        SKILL_REGISTRY: a monster is allowed to have no level
                        in a skill that exists, and combat_level already reads
                        keys for Combat Specialties that are still vault stubs.

        Exit/Returns:
            The integer level, or _ABSENT_SKILL_LEVEL for a skill this entity
            does not declare.

        Module Globals:
            _ABSENT_SKILL_LEVEL read.

        Methodology:
            One dict read. Never raises and never writes -- both matter,
            because this is called four times per combatant per action from
            inside the 0.6s tick loop, where an exception is swallowed by the
            engine and a write would be an Attribute round trip.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/23/2026
        """
        levels = self._levels()
        stored = levels.get(skill_key, _ABSENT_SKILL_LEVEL)

        return int(stored)


    def set_level(self, skill_key: str, level: int) -> int:
        """
        Purpose: Set a skill's level directly.

        Entry:
            skill_key - the skill to write.
            level     - the level wanted. Clamped into the legal band rather
                        than rejected, so a drain of 5 against a level-2
                        monster floors at 0 instead of raising inside a tick.

        Exit/Returns:
            The level actually stored, after clamping.

        Module Globals:
            None

        Methodology:
            Read, clamp, write, reassign. Reassignment (rather than in-place
            mutation) is what marks the Attribute dirty.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/23/2026
        """
        levels = self._levels()
        stored = self._clamped(int(level))
        levels[skill_key] = stored

        self._store(levels)

        return stored


    def modify_level(self, skill_key: str, delta: int) -> int:
        """
        Purpose: Shift a skill's level by a signed amount. The drain/buff path.

        Entry:
            skill_key - the skill to shift.
            delta     - signed integer. Negative drains, positive buffs.

        Exit/Returns:
            The new level, after clamping.

        Module Globals:
            None

        Methodology:
            Expressed in terms of get_level and set_level rather than touching
            the dict, so clamping is defined once.

            This writes the PERMANENT level. A drain that wears off needs a
            restore layer that remembers the pre-drain value, and that layer
            belongs above this class -- `combat_calc.effective_level` already
            takes a transient `potion_boost` for exactly that, and routing a
            temporary effect through here instead would make it permanent.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/23/2026
        """
        current = self.get_level(skill_key)
        wanted = current + int(delta)

        return self.set_level(skill_key, wanted)


    # ─── Bulk seeding ───────────────────────────────────────────────────────

    def seed(self, levels: dict) -> None:
        """
        Purpose: Replace the whole level dict in one write. Called by
        HostileNPC.apply_combat_stats when an NpcDef is stamped onto an NPC.

        Entry:
            levels - {skill_key: level}. Values that are not integers are
                     dropped with a logged error rather than stored, because a
                     string level would surface much later as a TypeError deep
                     inside combat_calc.

        Exit/Returns:
            No return value.

        Module Globals:
            None

        Methodology:
            One Attribute write for the whole block rather than one per skill.
            apply_combat_stats is idempotent and re-runs on every respawn, so
            this is on the spawn path of every hostile on the grid.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/23/2026
        """
        cleaned = {}

        for skill_key, level in (levels or {}).items():
            try:
                cleaned[skill_key] = self._clamped(int(level))
            except (TypeError, ValueError):
                logger.log_err(
                    f"StatBlockSkills.seed: {self.obj} declared a non-integer "
                    f"level for {skill_key!r} ({level!r}); skipping it."
                )

        self._store(cleaned)
