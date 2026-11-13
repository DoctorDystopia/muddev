"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/11/2026
Description: Tests of the dialogue runner and of the expressions
             (DESIGN-0017), on the compiled flow fixture. The fixture is a
             real output of the addon compiler, so these tests read the
             format that the server reads in a game.

             No database: the fixture calls the test vocabulary.
"""

import unittest

from systems.gameplay.dialogue import constants as dialogue_const
from systems.gameplay.dialogue.script import DialogueScriptError
from systems.gameplay.dialogue.tests import helpers
from systems.interface.ui.colors import dialog, title


class _FlowTest(unittest.TestCase):
    """A conversation from the flow fixture, with a stub talker."""

    def setUp(self):
        helpers.use_test_vocabulary(self)
        self.talker = helpers.StubTalker()
        self.conversation = helpers.fixture_conversation(
            helpers.FIXTURE_FLOW, self.talker)

    def _labels(self):
        return [response.label for response in self.conversation.beat.responses]


class BeatTests(_FlowTest):
    """One beat is the lines up to the next responses."""

    def test_the_first_beat_joins_each_line_before_the_responses(self):
        beat = self.conversation.open()

        self.assertIn("Tester walks up.", beat.text)
        self.assertIn("Halt.", beat.text)
        self.assertEqual(
            beat.text.count(dialogue_const.LINE_SEPARATOR), 1)

    def test_a_line_with_a_speaker_gets_the_speech_look(self):
        beat = self.conversation.open()
        spoken = "\n".join([dialog("Halt."), dialog("Nobody passes.")])
        expected = dialogue_const.SPEECH_TEMPLATE.format(
            speaker=title("Guard"), line=spoken)

        self.assertIn(expected, beat.text)

    def test_a_line_of_the_npc_itself_shows_no_name(self):
        guard = helpers.StubTalker("Guard")
        conversation = helpers.fixture_conversation(
            helpers.FIXTURE_FLOW, self.talker, npc=guard)

        beat = conversation.open()

        self.assertIn(dialog("Halt."), beat.text)
        self.assertNotIn(title("Guard"), beat.text)

    def test_a_line_of_a_different_speaker_keeps_its_name(self):
        somebody = helpers.StubTalker("Somebody")
        conversation = helpers.fixture_conversation(
            helpers.FIXTURE_FLOW, self.talker, npc=somebody)

        beat = conversation.open()

        self.assertIn(title("Guard"), beat.text)

    def test_a_line_with_no_speaker_is_plain(self):
        beat = self.conversation.open()

        self.assertTrue(beat.text.startswith("Tester walks up."))

    def test_a_response_keeps_its_colon(self):
        self.conversation.open()

        self.assertIn("Ask: who are you?", self._labels())

    def test_a_response_with_a_false_condition_is_not_offered(self):
        self.conversation.open()

        self.assertFalse(any("Bribe" in label for label in self._labels()))

    def test_a_response_with_a_true_condition_is_offered(self):
        self.talker.counts["gold"] = 5

        self.conversation.open()

        self.assertTrue(any("Bribe" in label for label in self._labels()))

    def test_a_beat_with_no_response_ends_the_conversation(self):
        self.talker.flags.add("done")

        beat = self.conversation.open()

        self.assertTrue(beat.is_ending())
        self.assertIn("You may pass.", beat.text)

    def test_a_response_that_ends_gives_an_empty_ending(self):
        self.conversation.open()

        beat = helpers.give(self.conversation, "Leave")

        self.assertTrue(beat.is_ending())
        self.assertEqual(beat.text, "")

    def test_an_index_with_no_response_raises(self):
        self.conversation.open()

        with self.assertRaises(DialogueScriptError):
            self.conversation.choose(len(self._labels()))


class RouteTests(_FlowTest):
    """Conditions, jumps, and the return stack."""

    def test_an_elif_takes_the_first_branch_that_holds(self):
        self.talker.flags.add("angry")

        beat = self.conversation.open()

        self.assertIn("Go away, Tester.", beat.text)
        self.assertTrue(beat.is_ending())

    def test_a_not_turns_the_branch_off(self):
        self.talker.flags.update({"angry", "calm"})

        beat = self.conversation.open()

        self.assertIn("Halt.", beat.text)

    def test_a_do_line_under_a_response_runs_when_the_player_gives_it(self):
        self.talker.counts["gold"] = 5
        self.conversation.open()
        self.assertEqual(self.talker.raised, [])

        beat = helpers.give(self.conversation, "Bribe")

        self.assertEqual(self.talker.raised, ["bribed"])
        self.assertIn("Fine.", beat.text)
        self.assertIn("You may pass.", beat.text)

    def test_a_snippet_jump_comes_back_to_the_line_after_it(self):
        self.talker.texts.update({"rank": "private", "guard": "Guard"})
        self.conversation.open()

        beat = helpers.give(self.conversation, "who are you")

        self.assertIn("A soldier.", beat.text)
        self.assertIn("That is all.", beat.text)
        self.assertLess(beat.text.index("A soldier."),
                        beat.text.index("That is all."))

    def test_a_speaker_can_come_from_the_vocabulary(self):
        self.talker.texts.update({"rank": "private", "guard": "Sentry"})
        self.conversation.open()

        beat = helpers.give(self.conversation, "who are you")

        self.assertIn("Sentry", beat.text)

    def test_a_jump_to_a_cue_starts_that_cue_again(self):
        self.talker.texts["rank"] = "private"
        self.conversation.open()
        helpers.give(self.conversation, "who are you")

        beat = helpers.give(self.conversation, "Back")

        self.assertIn("Halt.", beat.text)

    def test_a_jump_in_a_circle_stops_at_the_step_limit(self):
        with self.assertRaises(DialogueScriptError):
            self.conversation.open(cue="circle")

    def test_an_unknown_cue_raises(self):
        with self.assertRaises(DialogueScriptError):
            self.conversation.open(cue="no_such_cue")

    def test_the_farewell_cue_gives_the_parting_line(self):
        self.assertIn("Move along.", self.conversation.farewell())


class MatchTests(_FlowTest):
    """A `match` line and its `when` lines."""

    def _rank_line(self, rank):
        self.talker.texts.update({"rank": rank, "guard": "Guard"})
        self.conversation.open()

        return helpers.give(self.conversation, "who are you").text

    def test_a_when_with_two_values_takes_each_of_them(self):
        for rank in ("captain", "major"):
            with self.subTest(rank=rank):
                self.assertIn("An officer.", self._rank_line(rank))

    def test_a_when_with_one_value_takes_it(self):
        self.assertIn("A soldier.", self._rank_line("private"))

    def test_the_else_takes_each_other_value(self):
        self.assertIn("Nobody.", self._rank_line("cook"))

    def test_a_when_can_start_with_a_comparison(self):
        cases = {0: "No gold.", 250: "Rich.", 7: "Some gold."}

        for gold, expected in cases.items():
            with self.subTest(gold=gold):
                self.talker.counts["gold"] = gold

                beat = self.conversation.open(cue="wealth")

                self.assertEqual(beat.text, expected)


class ExpressionOrderTests(_FlowTest):
    """The order of an expression is the order of the addon."""

    def _logic(self, flags=(), **texts):
        self.talker.flags = set(flags)
        self.talker.texts = dict(texts)

        return self.conversation.open(cue="logic").text

    def test_brackets_group_an_or(self):
        self.assertIn("Group holds.", self._logic(flags=("b", "c")))
        self.assertNotIn("Group holds.", self._logic(flags=("a",)))

    def test_and_or_with_no_brackets_split_at_the_last_one(self):
        # `a or b and c` is `(a or b) and c`, as the addon resolves it. In
        # Python it is `a or (b and c)`, which is true for a alone.
        self.assertNotIn("Flat holds.", self._logic(flags=("a",)))
        self.assertIn("Flat holds.", self._logic(flags=("a", "c")))

    def test_a_comparison_of_two_texts(self):
        self.assertIn("Not a private.", self._logic(rank="captain"))
        self.assertNotIn("Not a private.", self._logic(rank="private"))

    def test_the_in_comparison(self):
        text = self._logic(rank="major", ranks="captain major")

        self.assertIn("Rank is known.", text)

    def test_an_action_cannot_run_in_a_condition(self):
        from systems.gameplay.dialogue import expressions

        tokens = [
            {"type": dialogue_const.TOKEN_VARIABLE, "value": "state"},
            {"type": dialogue_const.TOKEN_DOT},
            {"type": dialogue_const.TOKEN_FUNCTION, "function": "raise",
             "value": [[{"type": dialogue_const.TOKEN_STRING, "value": "x"}]]},
        ]

        with self.assertRaises(DialogueScriptError):
            expressions.evaluate(tokens, self.conversation.context)

        self.assertEqual(self.talker.raised, [])
