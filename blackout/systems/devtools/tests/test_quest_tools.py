"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: Tests for the quest write path -- QuestHandler's three direct
             writes, and the moderator effects layered over them.

             The handler tests use a HAND-BUILT blueprint rather than shipped
             content. A test that asserts against the oasis quest is a test
             that fails when the oasis quest is edited, which trains everyone
             to change the test instead of reading it. The registry tests
             below cover the shipped content, on relationships only.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py systems.devtools
"""

import unittest
from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from systems.devtools import actions as dev_actions
from systems.quests import constants as quest_constants
from systems.quests.loader import GLOBAL_QUEST_REGISTRY
from systems.quests.quests import QuestBlueprint, QuestStep


# A three-step quest built here, so a content edit cannot move these results.
_QUEST_KEY = "devtools_test_quest"
_STEP_ONE = "step_one"
_STEP_TWO = "step_two"
_STEP_THREE = "step_three"



def _build_blueprint(rewards_callback=None, on_enter=None):
    """Assemble the fixture quest. Steps carry real, distinct targets so that
    re-seeding is observable rather than inferred."""
    steps = [
        QuestStep(
            key=_STEP_ONE,
            description="Talk to the tester.",
            targets={f"{quest_constants.ACTION_TALK}"
                     f"{quest_constants.TARGET_SEPARATOR}tester": True},
            on_enter=on_enter,
        ),
        QuestStep(
            key=_STEP_TWO,
            description="Kill two things.",
            targets={f"{quest_constants.ACTION_KILL}"
                     f"{quest_constants.TARGET_SEPARATOR}thing": 2},
        ),
        QuestStep(
            key=_STEP_THREE,
            description="Go somewhere.",
            targets={f"{quest_constants.ACTION_VISIT}"
                     f"{quest_constants.TARGET_SEPARATOR}somewhere": True},
        ),
    ]

    return QuestBlueprint(
        key=_QUEST_KEY,
        title="Devtools Test Quest",
        description="A quest that exists only in this test module.",
        steps=steps,
        rewards_callback=rewards_callback,
    )



class _QuestFixture(EvenniaTest):
    """Registers the fixture blueprint for the duration of one test.

    Written into the REAL registry and removed in tearDown, rather than
    mocked: the handler resolves blueprints through GLOBAL_QUEST_REGISTRY on
    every call, so a patched lookup would only prove the patch works.

    Reaching into `_blueprints` is deliberate. QuestRegistry exposes no public
    write, and it should not: a mutable catalog is one a content module could
    self-register into, skipping the validation and the load_errors record
    that _load_module performs on the discovery walk. A test installing its
    own fixture is the one caller that legitimately bypasses discovery, and
    paying for it with a private access here is cheaper than opening that door
    for everyone.
    """

    rewards_callback = None
    on_enter = None

    def setUp(self):
        super().setUp()
        self.blueprint = _build_blueprint(
            rewards_callback=self.rewards_callback,
            on_enter=self.on_enter,
        )
        GLOBAL_QUEST_REGISTRY._blueprints[_QUEST_KEY] = self.blueprint

    def tearDown(self):
        GLOBAL_QUEST_REGISTRY._blueprints.pop(_QUEST_KEY, None)
        super().tearDown()



class ForceCompleteTests(_QuestFixture):
    """force_complete_quest -- the write that pays out."""

    def test_completing_an_active_quest_moves_it_to_the_completed_list(self):
        self.char1.quests.accept_quest(_QUEST_KEY)
        completed = self.char1.quests.force_complete_quest(_QUEST_KEY)

        self.assertTrue(completed)
        self.assertTrue(self.char1.quests.is_complete(_QUEST_KEY))
        self.assertNotIn(_QUEST_KEY, self.char1.quests.active_keys())

    def test_a_never_started_quest_can_be_completed_outright(self):
        completed = self.char1.quests.force_complete_quest(_QUEST_KEY)

        self.assertTrue(completed)
        self.assertTrue(self.char1.quests.is_complete(_QUEST_KEY))

    def test_completing_twice_is_refused_so_rewards_pay_once(self):
        self.char1.quests.force_complete_quest(_QUEST_KEY)
        second = self.char1.quests.force_complete_quest(_QUEST_KEY)

        self.assertFalse(second)

    def test_an_unknown_quest_is_refused(self):
        self.assertFalse(self.char1.quests.force_complete_quest("no_such_quest"))


class ForceCompleteRewardTests(_QuestFixture):
    """The reward callback is the main reason to force a completion."""

    rewards_callback = mock.Mock()

    def setUp(self):
        type(self).rewards_callback = mock.Mock()
        super().setUp()

    def test_the_reward_callback_fires(self):
        self.char1.quests.force_complete_quest(_QUEST_KEY)

        type(self).rewards_callback.assert_called_once_with(self.char1)


class ForceStepTests(_QuestFixture):
    """force_step -- forward, backward, and the re-seed that makes it safe."""

    def test_jumping_forward_moves_the_current_step(self):
        self.char1.quests.accept_quest(_QUEST_KEY)
        moved = self.char1.quests.force_step(_QUEST_KEY, _STEP_THREE)

        self.assertTrue(moved)
        self.assertEqual(self.char1.quests.current_step_key(_QUEST_KEY), _STEP_THREE)

    def test_jumping_backward_is_allowed(self):
        """The more useful direction: replaying a step without resetting."""
        self.char1.quests.accept_quest(_QUEST_KEY)
        self.char1.quests.force_step(_QUEST_KEY, _STEP_THREE)
        self.char1.quests.force_step(_QUEST_KEY, _STEP_ONE)

        self.assertEqual(self.char1.quests.current_step_key(_QUEST_KEY), _STEP_ONE)

    def test_progress_is_reseeded_from_the_destination_step(self):
        """
        Carrying the old counters across would leave a target from the
        previous step in the dict, where _step_is_satisfied would read it as
        a requirement that no longer exists.
        """
        self.char1.quests.accept_quest(_QUEST_KEY)
        self.char1.quests.force_step(_QUEST_KEY, _STEP_TWO)
        progress = self.char1.quests.progress_for(_QUEST_KEY)
        expected = set(self.blueprint.steps[1].targets)

        self.assertEqual(set(progress), expected)

    def test_a_jumped_to_step_still_advances_normally_afterwards(self):
        """The end-to-end point of the whole feature: land on step two and
        the quest keeps playing from there."""
        self.char1.quests.accept_quest(_QUEST_KEY)
        self.char1.quests.force_step(_QUEST_KEY, _STEP_TWO)
        self.char1.quests.notify(quest_constants.ACTION_KILL, "thing", amount=2)

        self.assertEqual(self.char1.quests.current_step_key(_QUEST_KEY), _STEP_THREE)

    def test_an_inactive_quest_is_refused(self):
        self.assertFalse(self.char1.quests.force_step(_QUEST_KEY, _STEP_TWO))

    def test_an_unknown_step_is_refused(self):
        self.char1.quests.accept_quest(_QUEST_KEY)
        moved = self.char1.quests.force_step(_QUEST_KEY, "no_such_step")

        self.assertFalse(moved)
        self.assertEqual(self.char1.quests.current_step_key(_QUEST_KEY), _STEP_ONE)


class ForceStepHookTests(_QuestFixture):
    """The destination's on_enter is what makes the step playable."""

    on_enter = mock.Mock()

    def setUp(self):
        type(self).on_enter = mock.Mock()
        super().setUp()

    def test_the_destination_step_on_enter_fires(self):
        self.char1.quests.accept_quest(_QUEST_KEY)
        calls_after_accept = type(self).on_enter.call_count
        self.char1.quests.force_step(_QUEST_KEY, _STEP_TWO)
        self.char1.quests.force_step(_QUEST_KEY, _STEP_ONE)

        self.assertEqual(type(self).on_enter.call_count, calls_after_accept + 1)


class ResetTests(_QuestFixture):
    """reset_quest -- the one that makes a finished quest takeable again."""

    def test_resetting_an_active_quest_clears_it(self):
        self.char1.quests.accept_quest(_QUEST_KEY)
        cleared = self.char1.quests.reset_quest(_QUEST_KEY)

        self.assertTrue(cleared)
        self.assertEqual(
            self.char1.quests.status(_QUEST_KEY),
            quest_constants.STATUS_NOT_STARTED,
        )

    def test_resetting_a_completed_quest_makes_it_takeable_again(self):
        """
        The difference from abandon_quest, and the reason both exist.
        Abandon leaves the completion record standing, so a finished quest
        stays finished and a tester replaying content is stuck.
        """
        self.char1.quests.force_complete_quest(_QUEST_KEY)
        self.char1.quests.reset_quest(_QUEST_KEY)

        self.assertTrue(self.char1.quests.is_available(_QUEST_KEY))
        self.assertTrue(self.char1.quests.accept_quest(_QUEST_KEY))

    def test_abandoning_a_completed_quest_does_not_make_it_takeable(self):
        """The contrast, pinned. If this ever passes, reset has no reason to
        exist and one of the two should go."""
        self.char1.quests.force_complete_quest(_QUEST_KEY)
        self.char1.quests.abandon_quest(_QUEST_KEY)

        self.assertTrue(self.char1.quests.is_complete(_QUEST_KEY))

    def test_a_quest_with_no_record_reports_nothing_to_clear(self):
        self.assertFalse(self.char1.quests.reset_quest(_QUEST_KEY))


class QuestEffectTests(_QuestFixture):
    """The moderator layer over the handler writes."""

    def test_an_unknown_quest_is_refused_by_name(self):
        succeeded, message = dev_actions.accept_quest(
            self.char2, self.char1, "no_such_quest"
        )

        self.assertFalse(succeeded)
        self.assertIn("no_such_quest", message)

    def test_accepting_starts_the_quest_properly(self):
        succeeded, _message = dev_actions.accept_quest(
            self.char2, self.char1, _QUEST_KEY
        )

        self.assertTrue(succeeded)
        self.assertEqual(self.char1.quests.current_step_key(_QUEST_KEY), _STEP_ONE)

    def test_accepting_an_already_active_quest_says_why(self):
        dev_actions.accept_quest(self.char2, self.char1, _QUEST_KEY)
        succeeded, message = dev_actions.accept_quest(
            self.char2, self.char1, _QUEST_KEY
        )

        self.assertFalse(succeeded)
        self.assertIn(_QUEST_KEY, message)

    def test_abandoning_an_inactive_quest_names_the_precondition(self):
        succeeded, message = dev_actions.abandon_quest(
            self.char2, self.char1, _QUEST_KEY
        )

        self.assertFalse(succeeded)
        self.assertIn("not on", message.lower())

    def test_completing_reports_that_rewards_were_paid(self):
        succeeded, message = dev_actions.complete_quest(
            self.char2, self.char1, _QUEST_KEY
        )

        self.assertTrue(succeeded)
        self.assertIn("reward", message.lower())

    def test_resetting_with_no_record_names_the_precondition(self):
        succeeded, message = dev_actions.reset_quest(
            self.char2, self.char1, _QUEST_KEY
        )

        self.assertFalse(succeeded)
        self.assertIn(_QUEST_KEY, message)

    def test_setting_a_step_on_an_inactive_quest_says_accept_it_first(self):
        """
        The handler returns one bool for two different refusals. The effect
        layer is what separates them, and this is the half that would
        otherwise be reported as a bad step name.
        """
        succeeded, message = dev_actions.set_quest_step(
            self.char2, self.char1, _QUEST_KEY, _STEP_TWO
        )

        self.assertFalse(succeeded)
        self.assertIn("accept", message.lower())

    def test_setting_an_unknown_step_names_the_step(self):
        dev_actions.accept_quest(self.char2, self.char1, _QUEST_KEY)
        succeeded, message = dev_actions.set_quest_step(
            self.char2, self.char1, _QUEST_KEY, "no_such_step"
        )

        self.assertFalse(succeeded)
        self.assertIn("no_such_step", message)

    def test_setting_a_valid_step_moves_the_character(self):
        dev_actions.accept_quest(self.char2, self.char1, _QUEST_KEY)
        succeeded, _message = dev_actions.set_quest_step(
            self.char2, self.char1, _QUEST_KEY, _STEP_THREE
        )

        self.assertTrue(succeeded)
        self.assertEqual(self.char1.quests.current_step_key(_QUEST_KEY), _STEP_THREE)

    def test_the_step_list_is_in_blueprint_order_not_sorted(self):
        offered = dev_actions.quest_step_keys(_QUEST_KEY)

        self.assertEqual(offered, [_STEP_ONE, _STEP_TWO, _STEP_THREE])

    def test_an_unknown_quest_offers_no_steps_rather_than_raising(self):
        self.assertEqual(dev_actions.quest_step_keys("no_such_quest"), [])


class QuestRegistryTests(unittest.TestCase):
    """The shipped content, on relationships only."""

    def test_every_registered_quest_is_offered(self):
        offered = dev_actions.quest_keys()

        self.assertEqual(sorted(offered), sorted(GLOBAL_QUEST_REGISTRY.keys()))

    def test_every_offered_quest_has_at_least_one_step_to_jump_to(self):
        for quest_key in dev_actions.quest_keys():
            with self.subTest(quest=quest_key):
                self.assertGreater(len(dev_actions.quest_step_keys(quest_key)), 0)

    def test_a_quest_title_falls_back_to_its_key(self):
        self.assertEqual(dev_actions.quest_title("no_such_quest"), "no_such_quest")
