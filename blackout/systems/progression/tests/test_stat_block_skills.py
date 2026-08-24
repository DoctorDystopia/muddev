"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/23/2026
Description: StatBlockSkills — the level source for entities that earn nothing.

Regressions guarded
-------------------
The facade this replaced (`_NpcSkillsShim`) answered 1 for any skill key its
stat block did not name. `NpcDef.to_combat_block()` never emitted a
fortitude_level, so every NPC in the game reported Fortitude 1 -- and that is
combat_level's base term, which made the Big Mutant's 87 hitpoints produce the
combat level of a 1-hitpoint monster. A fabricated plausible number does not
look like a bug; it looks like a monster that is mysteriously easy.

It also had no write path, so a stat drain had nowhere to land even though
combat_calc.effective_level has taken a boost parameter since it was written.
"""

from evennia.utils.test_resources import EvenniaTest

from systems.progression.skills import constants as skill_constants
from systems.progression.skills.stat_block import SKILL_LEVELS_ATTR, StatBlockSkills
from world.npc_database import NPC_DB


class TestStatBlockSkillReads(EvenniaTest):

    def setUp(self):
        super().setUp()
        self.skills = StatBlockSkills(self.obj1)
        self.skills.seed({"strike": 20, "brawn": 15, "defense": 10, "fortitude": 50})

    def test_a_declared_level_reads_back(self):
        self.assertEqual(self.skills.get_level("strike"), 20)
        self.assertEqual(self.skills.get_level("fortitude"), 50)

    def test_an_undeclared_skill_reads_the_absent_floor(self):
        """Zero, not one. Zero is what a character who has never trained the
        skill has, so both sides of the combat math agree about what "no level
        in this" means."""
        self.assertEqual(
            self.skills.get_level("guns"), skill_constants.DEFAULT_START_LEVEL
        )

    def test_reading_an_undeclared_skill_does_not_write_one(self):
        """The hazard that ruled out giving NPCs a real SkillHandler:
        logic.ensure_skill writes into db.skills on read, so reading `guns`
        off a goblin would permanently grow that goblin a Guns skill."""
        self.skills.get_level("guns")

        stored = getattr(self.obj1.db, SKILL_LEVELS_ATTR)

        self.assertNotIn("guns", stored)

    def test_reads_survive_a_fresh_handler(self):
        """The handler holds no state of its own -- it is a view on the
        Attribute, so a second one built later sees the same levels."""
        other = StatBlockSkills(self.obj1)

        self.assertEqual(other.get_level("strike"), 20)

    def test_an_entity_that_was_never_seeded_reads_the_floor(self):
        virgin = StatBlockSkills(self.obj2)

        self.assertEqual(
            virgin.get_level("strike"), skill_constants.DEFAULT_START_LEVEL
        )


class TestStatBlockSkillWrites(EvenniaTest):

    def setUp(self):
        super().setUp()
        self.skills = StatBlockSkills(self.obj1)
        self.skills.seed({"strike": 20, "defense": 10})

    def test_set_level_persists(self):
        self.skills.set_level("strike", 33)

        self.assertEqual(StatBlockSkills(self.obj1).get_level("strike"), 33)

    def test_set_level_returns_what_it_stored(self):
        self.assertEqual(self.skills.set_level("strike", 33), 33)

    def test_set_level_clamps_to_the_ceiling(self):
        stored = self.skills.set_level("strike", 9999)

        self.assertEqual(stored, skill_constants.MAX_BASE_SKILL_LEVEL)

    def test_set_level_clamps_to_the_floor(self):
        stored = self.skills.set_level("strike", -5)

        self.assertEqual(stored, skill_constants.MIN_BASE_SKILL_LEVEL)

    def test_modify_level_drains(self):
        """The write path the shim did not have at all."""
        remaining = self.skills.modify_level("defense", -4)

        self.assertEqual(remaining, 6)
        self.assertEqual(self.skills.get_level("defense"), 6)

    def test_modify_level_buffs(self):
        self.assertEqual(self.skills.modify_level("defense", 7), 17)

    def test_a_drain_past_zero_floors_rather_than_going_negative(self):
        """Clamped rather than rejected: this is called from inside the 0.6s
        tick loop, where a raised exception is swallowed by the engine and the
        combatant silently stops acting."""
        self.assertEqual(self.skills.modify_level("defense", -50), 0)

    def test_modifying_an_undeclared_skill_starts_from_the_floor(self):
        self.assertEqual(self.skills.modify_level("guns", 3), 3)

    def test_seed_replaces_rather_than_merges(self):
        self.skills.seed({"brawn": 5})

        self.assertEqual(self.skills.get_level("brawn"), 5)
        self.assertEqual(
            self.skills.get_level("strike"), skill_constants.DEFAULT_START_LEVEL
        )

    def test_seed_drops_a_non_integer_level(self):
        """A string level would otherwise surface much later as a TypeError
        deep inside combat_calc, with nothing pointing back at the NpcDef."""
        self.skills.seed({"strike": "twenty", "brawn": 5})

        self.assertEqual(self.skills.get_level("brawn"), 5)
        self.assertEqual(
            self.skills.get_level("strike"), skill_constants.DEFAULT_START_LEVEL
        )


class TestNpcDefSeeding(EvenniaTest):
    """The end-to-end path: an authored NpcDef reaching combat's level reads."""

    def test_authored_levels_reach_the_stat_block(self):
        npc = NPC_DB["mutant_raider"].create(location=self.room1)

        self.assertEqual(npc.skills.get_level("strike"), 1)
        self.assertEqual(npc.skills.get_level("defense"), 1)

    def test_fortitude_is_derived_from_max_hp(self):
        """The Fortitude bridge. HP_PER_FORTITUDE_LEVEL is 1, so an OSRS
        monster's quoted Hitpoints IS its Fortitude level -- the same 1:1 rule
        logic.sync_max_hp_from_fortitude enforces for characters."""
        npc = NPC_DB["big_mutant"].create(location=self.room1)

        self.assertEqual(npc.skills.get_level("fortitude"), 87)
        self.assertEqual(npc.max_hp, 87)

    def test_an_explicit_fortitude_beats_the_derived_one(self):
        """A monster whose Fortitude axis deliberately differs from its HP
        pool sets the field; max_hp stops being consulted for it."""
        from world.npc_database import NpcDef

        odd = NpcDef(key="test_odd", name="Odd One", max_hp=40, fortitude_level=7)
        npc = odd.create(location=self.room1)

        self.assertEqual(npc.skills.get_level("fortitude"), 7)
        self.assertEqual(npc.max_hp, 40)

    def test_apply_combat_stats_is_idempotent(self):
        """It runs at creation AND again from the spawner, and once more on
        every respawn."""
        npc = NPC_DB["mutant_raider"].create(location=self.room1)
        npc.apply_combat_stats(NPC_DB["mutant_raider"].to_combat_block())

        self.assertEqual(npc.skills.get_level("fortitude"), 5)
        self.assertEqual(npc.skills.get_level("strike"), 1)
