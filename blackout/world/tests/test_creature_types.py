"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: Tests for the creature type table and its one reader.

             The tests assert relationships, never a census. Every type that
             an NpcDef names is a row of the table. Every row is well-formed.
             The reader gives the types of the NpcDef that db.npc_key names.
             DESIGN-0012, Phase 1.
"""



import unittest

from evennia.utils import create
from evennia.utils.test_resources import EvenniaTestCase

from systems.gameplay.progression.skills import constants as skill_constants
from world import creature_types
from world.creature_types import CREATURE_TYPES
from world.npc_database import NPC_DB, NPC_KEY_ATTR, combatant_defs, creature_types_of



# Private constant definitions

# The NPC that the vault note gives as the example of an NPC with several
# types: "A Mutant Crab counts for a Mutant task and for a Crab task."
_MUTANT_CRAB_KEY: str = "mutant_crab"

# The name prefix of a single creature type key constant.
_KEY_CONSTANT_PREFIX: str = "CREATURE_TYPE_"

# An npc_key that names no NpcDef.
_UNKNOWN_NPC_KEY: str = "no_such_npc"

_PLAIN_OBJECT_TYPECLASS: str = "evennia.objects.objects.DefaultObject"
_PLAIN_OBJECT_KEY: str = "creature type test object"



class CreatureTypeTableTests(unittest.TestCase):
    """The table and the NpcDefs agree. No DB."""

    def test_every_type_on_every_npc_def_is_a_row(self):
        for npc_key, npc_def in combatant_defs().items():
            for type_key in npc_def.combat.creature_types:
                with self.subTest(npc=npc_key, creature_type=type_key):
                    self.assertIn(type_key, CREATURE_TYPES)


    def test_no_npc_def_names_a_type_twice(self):
        for npc_key, npc_def in combatant_defs().items():
            unique_types = set(npc_def.combat.creature_types)

            with self.subTest(npc=npc_key):
                self.assertEqual(len(unique_types), len(npc_def.combat.creature_types))


    def test_every_npc_def_holds_a_tuple(self):
        for npc_key, npc_def in combatant_defs().items():
            with self.subTest(npc=npc_key):
                self.assertIsInstance(npc_def.combat.creature_types, tuple)


    def test_every_row_is_well_formed(self):
        for type_key, row in CREATURE_TYPES.items():
            with self.subTest(creature_type=type_key):
                self.assertEqual(row.key, type_key)
                self.assertTrue(row.name)
                self.assertTrue(row.plural)
                self.assertGreaterEqual(row.required_level, skill_constants.MIN_BASE_SKILL_LEVEL)
                self.assertLessEqual(row.required_level, skill_constants.MAX_BASE_SKILL_LEVEL)


    def test_every_key_constant_names_a_row(self):
        for name, value in vars(creature_types).items():
            if not name.startswith(_KEY_CONSTANT_PREFIX):
                continue

            with self.subTest(constant=name):
                self.assertIn(value, CREATURE_TYPES)


    def test_the_mutant_crab_is_a_mutant_and_a_crab(self):
        crab_types = NPC_DB[_MUTANT_CRAB_KEY].combat.creature_types

        self.assertIn(creature_types.CREATURE_TYPE_MUTANT, crab_types)
        self.assertIn(creature_types.CREATURE_TYPE_CRAB, crab_types)



class CreatureTypesOfTests(EvenniaTestCase):
    """The reader reads db.npc_key, then NPC_DB, live."""

    def setUp(self):
        super().setUp()
        self.obj = create.create_object(_PLAIN_OBJECT_TYPECLASS, key=_PLAIN_OBJECT_KEY)


    def tearDown(self):
        self.obj.delete()
        super().tearDown()


    def test_gives_the_types_of_the_named_def(self):
        self.obj.attributes.add(NPC_KEY_ATTR, _MUTANT_CRAB_KEY)

        found = creature_types_of(self.obj)

        self.assertEqual(found, NPC_DB[_MUTANT_CRAB_KEY].combat.creature_types)
        self.assertIn(creature_types.CREATURE_TYPE_MUTANT, found)
        self.assertIn(creature_types.CREATURE_TYPE_CRAB, found)


    def test_an_object_with_no_npc_key_has_no_types(self):
        self.assertEqual(creature_types_of(self.obj), ())


    def test_an_unknown_npc_key_has_no_types(self):
        self.obj.attributes.add(NPC_KEY_ATTR, _UNKNOWN_NPC_KEY)

        self.assertEqual(creature_types_of(self.obj), ())
