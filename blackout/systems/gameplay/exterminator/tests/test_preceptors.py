"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: Relation tests for PRECEPTOR_DB and the Preceptor NPCs.

             Every row is well-formed, every creature type that a row names
             exists, and every Preceptor NPC class names a row and a dialogue
             module that imports. No census. DESIGN-0012, Phase 2.
"""

import importlib
import unittest

from systems.gameplay.exterminator.preceptors import PRECEPTOR_DB
from systems.gameplay.progression.skills import constants as skill_constants
from evennia.utils.utils import class_from_module

from typeclasses import npcs
from world.npc_database import NPC_DB
from world.creature_types import CREATURE_TYPES



def _preceptor_npc_defs() -> list:
    """
    Every NpcDef whose role is PreceptorNPC. Until 10/09/2026, each
    Preceptor was a subclass in typeclasses/npcs.py. Now each one is a def.
    """
    defs = []

    for npc_def in NPC_DB.values():
        typeclass = class_from_module(npc_def.resolved_typeclass())

        if issubclass(typeclass, npcs.PreceptorNPC):
            defs.append(npc_def)

    return defs



class PreceptorTableTests(unittest.TestCase):

    def test_every_row_is_well_formed(self):
        for key, preceptor in PRECEPTOR_DB.items():
            with self.subTest(preceptor=key):
                self.assertEqual(preceptor.key, key)
                self.assertTrue(preceptor.name)
                self.assertTrue(preceptor.assignments)
                self.assertGreaterEqual(preceptor.base_points, 0)
                self.assertGreaterEqual(preceptor.required_level, skill_constants.MIN_BASE_SKILL_LEVEL)
                self.assertLessEqual(preceptor.required_level, skill_constants.MAX_BASE_SKILL_LEVEL)

    def test_every_assignment_is_well_formed(self):
        for key, preceptor in PRECEPTOR_DB.items():
            for assignment in preceptor.assignments:
                with self.subTest(preceptor=key, creature_type=assignment.creature_type):
                    self.assertIn(assignment.creature_type, CREATURE_TYPES)
                    self.assertGreater(assignment.weight, 0)
                    self.assertGreater(assignment.min_size, 0)
                    self.assertLessEqual(assignment.min_size, assignment.max_size)

    def test_no_preceptor_names_a_type_twice(self):
        for key, preceptor in PRECEPTOR_DB.items():
            types = [assignment.creature_type for assignment in preceptor.assignments]

            with self.subTest(preceptor=key):
                self.assertEqual(len(types), len(set(types)))



class PreceptorNpcTests(unittest.TestCase):

    def test_there_is_a_preceptor_npc_def(self):
        """The vacuity guard: the loops below check something."""
        self.assertTrue(_preceptor_npc_defs())

    def test_every_preceptor_npc_names_a_row(self):
        for npc_def in _preceptor_npc_defs():
            with self.subTest(npc=npc_def.key):
                self.assertIn(npc_def.preceptor_key, PRECEPTOR_DB)

    def test_every_preceptor_npc_dialogue_imports(self):
        for npc_def in _preceptor_npc_defs():
            with self.subTest(npc=npc_def.key):
                module = importlib.import_module(npc_def.dialogue_module())
                self.assertTrue(callable(getattr(module, "start", None)))
