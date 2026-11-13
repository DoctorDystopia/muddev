"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/11/2026
Description: Tests of the content rules of a compiled script (DESIGN-0017).

             The refused fixture holds one block for each thing that the
             addon compiler accepts and the server refuses. The flow fixture
             holds only what the server runs, so it must give no problem.

             No database: the fixtures call the test vocabulary.
"""

import unittest

from systems.gameplay.dialogue import checks
from systems.gameplay.dialogue import constants as dialogue_const
from systems.gameplay.dialogue.script import CompiledScript
from systems.gameplay.dialogue.tests import helpers


class _CheckTest(unittest.TestCase):
    """The problems of one fixture, by rule."""

    def setUp(self):
        helpers.use_test_vocabulary(self)

    def _problems(self, key):
        return checks.script_problems(helpers.load_fixture(key))

    def _messages(self, key, rule):
        return [problem.message for problem in self._problems(key)
                if problem.rule == rule]

    def _assert_one_holds(self, messages, keyword):
        self.assertTrue(
            any(keyword in message for message in messages),
            f"no problem holds '{keyword}'. The problems: {messages}")


class AcceptedScriptTests(_CheckTest):
    """A script that uses only what the server runs."""

    def test_the_flow_fixture_has_no_problem(self):
        problems = [problem.describe()
                    for problem in self._problems(helpers.FIXTURE_FLOW)]

        self.assertEqual(problems, [])


class RefusedScriptTests(_CheckTest):
    """Each thing that the compiler accepts and the server refuses."""

    def _refused(self, rule):
        return self._messages(helpers.FIXTURE_REFUSED, rule)

    def test_each_rule_name_is_in_the_exported_list(self):
        for problem in self._problems(helpers.FIXTURE_REFUSED):
            with self.subTest(rule=problem.rule):
                self.assertIn(problem.rule, dialogue_const.CHECK_RULES)

    def test_a_while_line_is_refused(self):
        self._assert_one_holds(
            self._refused(dialogue_const.RULE_LINE_TYPE), "while")

    def test_each_refused_feature_is_found(self):
        messages = self._refused(dialogue_const.RULE_FEATURE)

        for feature in dialogue_const.REFUSED_FIELDS.values():
            with self.subTest(feature=feature):
                self._assert_one_holds(messages, feature)

    def test_each_refused_markup_in_the_fixture_is_found(self):
        messages = self._refused(dialogue_const.RULE_MARKUP)

        for keyword in ("random text", "pause"):
            with self.subTest(keyword=keyword):
                self._assert_one_holds(messages, keyword)

    def test_a_cue_that_runs_into_the_next_cue_is_refused(self):
        self._assert_one_holds(
            self._refused(dialogue_const.RULE_FALL_THROUGH), "rest")

    def test_a_name_outside_the_vocabulary_is_refused(self):
        self._assert_one_holds(
            self._refused(dialogue_const.RULE_NAME), "nobody.home")

    def test_an_action_in_a_condition_is_refused(self):
        self._assert_one_holds(
            self._refused(dialogue_const.RULE_KIND), "state.raise")

    def test_a_query_in_a_do_line_is_refused(self):
        messages = self._refused(dialogue_const.RULE_KIND)
        about_flag = [message for message in messages
                      if "state.flag" in message
                      and dialogue_const.USAGE_MUTATION in message]

        self.assertTrue(about_flag, messages)

    def test_a_value_with_brackets_is_refused(self):
        messages = self._refused(dialogue_const.RULE_KIND)
        about_name = [message for message in messages
                      if "state.name" in message and "no brackets" in message]

        self.assertTrue(about_name, messages)

    def test_a_query_with_no_brackets_is_refused(self):
        messages = self._refused(dialogue_const.RULE_KIND)
        about_flag = [message for message in messages
                      if "state.flag" in message and "with brackets" in message]

        self.assertTrue(about_flag, messages)

    def test_a_wrong_number_of_arguments_is_refused(self):
        self._assert_one_holds(
            self._refused(dialogue_const.RULE_ARITY), "state.flag")

    def test_arithmetic_and_an_assignment_are_refused(self):
        messages = self._refused(dialogue_const.RULE_EXPRESSION)

        for token_type in ("operator", "assignment"):
            with self.subTest(token_type=token_type):
                self._assert_one_holds(messages, token_type)

    def test_a_bare_name_is_refused(self):
        self._assert_one_holds(
            self._refused(dialogue_const.RULE_EXPRESSION), "gold")

    def test_the_argument_check_of_an_entry_runs(self):
        self._assert_one_holds(
            self._refused(dialogue_const.RULE_ARGUMENT),
            helpers.REFUSED_ARGUMENT_TEXT)

    def test_a_problem_names_its_line_in_the_dialogue_script(self):
        source = helpers.fixture_path(
            helpers.FIXTURE_REFUSED, dialogue_const.SOURCE_SUFFIX)

        with open(source, encoding="utf-8") as handle:
            source_lines = handle.read().splitlines()

        problems = [problem for problem in self._problems(helpers.FIXTURE_REFUSED)
                    if problem.rule == dialogue_const.RULE_NAME]
        line_number = problems[0].source_line()

        self.assertIn("nobody.home", source_lines[line_number - 1])


class WholeScriptRuleTests(_CheckTest):
    """The rules about a script as a whole."""

    def test_a_script_with_no_start_cue_is_refused(self):
        rules = [problem.rule
                 for problem in self._problems(helpers.FIXTURE_NO_START)]

        self.assertIn(dialogue_const.RULE_START_CUE, rules)

    def test_a_different_compiler_version_is_refused(self):
        flow = helpers.load_fixture(helpers.FIXTURE_FLOW)
        newer = CompiledScript(
            key=flow.key,
            compiler_version=dialogue_const.SUPPORTED_COMPILER_VERSION + 1,
            cues=flow.cues,
            lines=flow.lines,
        )

        rules = [problem.rule for problem in checks.script_problems(newer)]

        self.assertEqual(rules, [dialogue_const.RULE_VERSION])

    def test_a_jump_to_a_missing_line_is_refused(self):
        lines = {
            "0": {"type": dialogue_const.TYPE_CUE, "next_id": "1"},
            "1": {"type": dialogue_const.TYPE_GOTO, "next_id": "abc@7",
                  "next_id_after": "", "is_snippet": False},
        }
        script = CompiledScript(
            key="broken", cues={dialogue_const.CUE_START: "0"}, lines=lines)

        rules = [problem.rule for problem in checks.script_problems(script)]

        self.assertEqual(rules, [dialogue_const.RULE_TARGET])
