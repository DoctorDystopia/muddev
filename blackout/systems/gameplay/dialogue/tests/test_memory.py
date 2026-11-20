"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/19/2026
Description: Tests of the dialogue memory (DESIGN-0017): the store, the
             argument checks of the two `memory.*` names, and the memory
             check of the whole game.

             The two fixtures memory_keeper and memory_reader hold one
             remember and two recalls. Only one recall has a remember.
"""

import unittest

from evennia import create_object
from evennia.objects.objects import DefaultObject
from evennia.utils.test_resources import EvenniaTestCase

from systems.gameplay.dialogue import checks, memory
from systems.gameplay.dialogue import constants as dialogue_const
from systems.gameplay.dialogue.runner import DialogueContext
from systems.gameplay.dialogue.tests import helpers
from systems.gameplay.dialogue.vocabulary import vocabulary


# ─── Private constant definitions ────────────────────────────────────────────

_FIXTURE_KEEPER: str = "memory_keeper"
_FIXTURE_READER: str = "memory_reader"

# The keys of the two fixtures.
_KEPT_KEY: str = "kept_key"
_LOST_KEY: str = "lost_key"

_KEY: str = "human_reading"
_OTHER_KEY: str = "opener"
_DEFAULT: int = 82


class MemoryStoreTests(EvenniaTestCase):
    """One character keeps values by key, between two calls."""

    def setUp(self):
        super().setUp()
        self.talker = create_object(DefaultObject, key="talker")

    def test_a_recall_gives_the_value_that_was_remembered(self):
        memory.remember(self.talker, _KEY, 72)

        self.assertEqual(memory.recall(self.talker, _KEY, _DEFAULT), 72)

    def test_a_recall_with_no_value_gives_the_default(self):
        self.assertEqual(memory.recall(self.talker, _KEY, _DEFAULT), _DEFAULT)

    def test_a_second_remember_replaces_the_value(self):
        memory.remember(self.talker, _KEY, 72)
        memory.remember(self.talker, _KEY, 82)

        self.assertEqual(memory.recall(self.talker, _KEY, 0), 82)

    def test_one_key_does_not_change_a_different_key(self):
        memory.remember(self.talker, _KEY, 72)
        memory.remember(self.talker, _OTHER_KEY, "raider")

        self.assertEqual(memory.recall(self.talker, _KEY, _DEFAULT), 72)
        self.assertEqual(memory.recall(self.talker, _OTHER_KEY, ""), "raider")

    def test_each_literal_type_is_kept(self):
        for value in ("raider", 72, 0.5, True, False):
            with self.subTest(value=value):
                memory.remember(self.talker, _KEY, value)

                self.assertEqual(memory.recall(self.talker, _KEY, None), value)

    def test_a_game_object_is_refused(self):
        with self.assertRaises(TypeError):
            memory.remember(self.talker, _KEY, self.talker)

    def test_the_two_names_call_the_store(self):
        entries = vocabulary()
        context = DialogueContext(caller=self.talker)

        entries[dialogue_const.MEMORY_REMEMBER].handler(context, _KEY, 72)
        recalled = entries[dialogue_const.MEMORY_RECALL].handler(
            context, _KEY, _DEFAULT)

        self.assertEqual(recalled, 72)


class MemoryArgumentTests(EvenniaTestCase):
    """The argument checks of `memory.remember` and `memory.recall`. The
    content check gives each one the literals of a call, and None for an
    argument that is not a literal."""

    def _complaint(self, name, arguments):
        entry = vocabulary()[name]

        return entry.argument_check(arguments)

    def test_a_literal_key_and_a_literal_value_pass(self):
        for name in (dialogue_const.MEMORY_REMEMBER, dialogue_const.MEMORY_RECALL):
            for literal in ("raider", 72, 0.5, False):
                with self.subTest(name=name, literal=literal):
                    self.assertIsNone(self._complaint(name, [_KEY, literal]))

    def test_a_key_that_is_not_a_literal_is_refused(self):
        complaint = self._complaint(dialogue_const.MEMORY_RECALL, [None, 1])

        self.assertIn("literal text", complaint)

    def test_a_key_that_is_not_snake_case_is_refused(self):
        for key in ("Human Reading", "human-reading", "1st_reading"):
            with self.subTest(key=key):
                complaint = self._complaint(
                    dialogue_const.MEMORY_REMEMBER, [key, 1])

                self.assertIn("snake_case", complaint)

    def test_a_value_that_is_not_a_literal_is_refused(self):
        complaint = self._complaint(dialogue_const.MEMORY_REMEMBER, [_KEY, None])

        self.assertIn("value must be a literal", complaint)

    def test_a_default_that_is_not_a_literal_is_refused(self):
        complaint = self._complaint(dialogue_const.MEMORY_RECALL, [_KEY, None])

        self.assertIn("default must be a literal", complaint)


class MemoryCheckTests(unittest.TestCase):
    """The memory check reads each script of the game together."""

    def setUp(self):
        self.keeper = helpers.load_fixture(_FIXTURE_KEEPER)
        self.reader = helpers.load_fixture(_FIXTURE_READER)

    def _lost(self, problems):
        return [problem for _key, problem in problems
                if _LOST_KEY in problem.message]

    def test_the_uses_of_one_script_are_found(self):
        remembered, _recalls = checks.memory_uses(self.keeper)
        _remembered, recalls = checks.memory_uses(self.reader)

        self.assertEqual(remembered, {_KEPT_KEY})
        self.assertEqual([key for _line, key in recalls], [_KEPT_KEY, _LOST_KEY])

    def test_a_key_that_a_different_script_remembers_passes(self):
        problems = checks.memory_problems([self.keeper, self.reader])
        keys = [problem.message for _key, problem in problems]

        self.assertEqual(len(problems), 1, keys)
        self.assertEqual(len(self._lost(problems)), 1, keys)

    def test_a_key_that_no_script_remembers_is_a_problem(self):
        problems = checks.memory_problems([self.reader])

        self.assertEqual(len(problems), 2)

    def test_the_problem_names_the_script_the_line_and_the_rule(self):
        problems = checks.memory_problems([self.keeper, self.reader])
        script_key, problem = problems[0]

        self.assertEqual(script_key, _FIXTURE_READER)
        self.assertEqual(problem.rule, dialogue_const.RULE_MEMORY)
        self.assertIn(problem.rule, dialogue_const.CHECK_RULES)
        self.assertIsNotNone(problem.source_line())
