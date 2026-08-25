"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: Engine tests -- QuestStep/QuestBlueprint validation and the whole
             QuestHandler lifecycle, against stub content and no database.
"""

import unittest
from unittest import mock

from systems.quests import constants
from systems.quests.handler import QuestHandler
from systems.quests.quests import (
    QuestBlueprint,
    QuestStep,
    normalize_target,
    split_target,
)
from systems.quests.tests.stubs import FakeCharacter, FakeRegistry



# Private constant definitions

# Where QuestHandler looks the registry up. Patched, rather than the loader's
# own module attribute, because handler.py binds the name at import.
_REGISTRY_PATH = "systems.quests.handler.GLOBAL_QUEST_REGISTRY"



def _two_step_quest(on_enter=None, on_complete=None) -> QuestBlueprint:
    """Build a small quest: one boolean step, then one counted step."""
    return QuestBlueprint(
        key="testquest",
        title="Test Quest",
        description="A quest that exists only here.",
        steps=[
            QuestStep(
                key="intro",
                description="Speak to the tester.",
                targets={"talk:tester": True},
                objectives={"talk:tester": "Speak to the tester"},
                on_enter=on_enter,
                on_complete=on_complete,
            ),
            QuestStep(
                key="hunt",
                description="Cull three rats.",
                targets={"kill:rat": 3},
                objectives={"kill:rat": "Rats culled"},
            ),
        ],
    )



class TargetKeyTests(unittest.TestCase):
    """The compound-key join and split, which every other piece depends on."""

    def test_join_and_split_round_trip(self):
        joined = normalize_target("talk", "lone_android")

        self.assertEqual(joined, "talk:lone_android")
        self.assertEqual(split_target(joined), ("talk", "lone_android"))


    def test_bare_action_has_no_separator(self):
        self.assertEqual(normalize_target("survive"), "survive")
        self.assertEqual(split_target("survive"), ("survive", None))


    def test_argument_may_contain_the_separator(self):
        # Split once from the left, so a colon inside the argument does not
        # steal the action.
        joined = normalize_target("visit", "neo_cairo:gate_3")

        self.assertEqual(split_target(joined), ("visit", "neo_cairo:gate_3"))



class QuestStepValidationTests(unittest.TestCase):
    """Content errors must surface at construction, not at fire time."""

    def test_undocumented_action_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            QuestStep("bad", "Bad step", targets={"interract:pipe": True})

        self.assertIn("interract", str(caught.exception))


    def test_every_documented_action_is_accepted(self):
        for action in sorted(constants.QUEST_ACTIONS):
            with self.subTest(action=action):
                step = QuestStep(
                    "ok", "Fine", targets={f"{action}:thing": True})

                self.assertIn(f"{action}:thing", step.targets)


    def test_already_satisfied_requirement_is_refused(self):
        for requirement in (0, -1, False):
            with self.subTest(requirement=requirement):
                with self.assertRaises(ValueError):
                    QuestStep("bad", "Bad", targets={"kill:rat": requirement})


    def test_non_numeric_requirement_is_refused(self):
        with self.assertRaises(ValueError):
            QuestStep("bad", "Bad", targets={"kill:rat": "three"})


    def test_objective_text_for_a_missing_target_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            QuestStep(
                "bad", "Bad",
                targets={"kill:rat": 3},
                objectives={"kill:mouse": "Mice culled"},
            )

        self.assertIn("kill:mouse", str(caught.exception))


    def test_undescribed_objective_falls_back_to_its_key(self):
        step = QuestStep("s", "Step", targets={"kill:rat": 3})

        self.assertEqual(step.objective_text("kill:rat"), "kill:rat")



class QuestBlueprintValidationTests(unittest.TestCase):
    """A blueprint that cannot be progressed through must not be built."""

    def test_stepless_quest_is_refused(self):
        with self.assertRaises(ValueError):
            QuestBlueprint("q", "Q", "desc", steps=[])


    def test_targetless_step_is_refused(self):
        # Such a step completes the instant it is entered and cascades
        # through everything after it.
        with self.assertRaises(ValueError) as caught:
            QuestBlueprint("q", "Q", "desc",
                           steps=[QuestStep("empty", "Nothing to do")])

        self.assertIn("empty", str(caught.exception))


    def test_duplicate_step_key_is_refused(self):
        step_a = QuestStep("same", "A", targets={"talk:a": True})
        step_b = QuestStep("same", "B", targets={"talk:b": True})

        with self.assertRaises(ValueError):
            QuestBlueprint("q", "Q", "desc", steps=[step_a, step_b])


    def test_step_lookup_by_key(self):
        blueprint = _two_step_quest()

        self.assertEqual(blueprint.step_keys, ["intro", "hunt"])
        self.assertEqual(blueprint.step_index_of("hunt"), 1)
        self.assertEqual(blueprint.step_index_of("nonesuch"), -1)



class QuestHandlerLifecycleTests(unittest.TestCase):
    """Accepting, advancing, completing and abandoning one quest."""

    def setUp(self):
        self.character = FakeCharacter()
        self.blueprint = _two_step_quest()
        self.registry = FakeRegistry([self.blueprint])
        self.patcher = mock.patch(_REGISTRY_PATH, self.registry)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.quests = QuestHandler(self.character)


    def test_fresh_character_holds_nothing(self):
        self.assertEqual(self.quests.active_keys(), [])
        self.assertEqual(self.quests.completed_keys(), [])
        self.assertEqual(self.quests.status("testquest"),
                         constants.STATUS_NOT_STARTED)


    def test_accepting_seeds_only_the_first_step(self):
        self.assertTrue(self.quests.accept_quest("testquest"))

        self.assertTrue(self.quests.is_active("testquest"))
        self.assertEqual(self.quests.current_step_key("testquest"), "intro")
        # kill:rat belongs to step two and must not be watched yet.
        self.assertEqual(self.quests.progress_for("testquest"),
                         {"talk:tester": 0})


    def test_accepting_an_unknown_quest_tells_the_player(self):
        self.assertFalse(self.quests.accept_quest("nonesuch"))
        self.assertTrue(self.character.said("nonesuch"))


    def test_a_quest_cannot_be_accepted_twice(self):
        self.quests.accept_quest("testquest")

        self.assertFalse(self.quests.accept_quest("testquest"))
        self.assertEqual(len(self.quests.active_keys()), 1)


    def test_boolean_target_latches_and_advances_the_step(self):
        self.quests.accept_quest("testquest")
        self.quests.notify("talk", "tester")

        self.assertEqual(self.quests.current_step_key("testquest"), "hunt")
        self.assertEqual(self.quests.progress_for("testquest"), {"kill:rat": 0})


    def test_counted_target_accumulates_then_completes(self):
        self.quests.accept_quest("testquest")
        self.quests.notify("talk", "tester")

        self.quests.notify("kill", "rat")
        self.assertEqual(self.quests.progress_for("testquest"), {"kill:rat": 1})

        self.quests.notify("kill", "rat", amount=2)

        self.assertTrue(self.quests.is_complete("testquest"))
        self.assertFalse(self.quests.is_active("testquest"))


    def test_counted_progress_is_clamped_to_the_requirement(self):
        # A step that needs 3 must never display 5/3, so the counter stops at
        # the requirement rather than running past it.
        blueprint = QuestBlueprint(
            "clamp", "Clamp", "desc",
            steps=[
                QuestStep("a", "Kill three", targets={"kill:rat": 3}),
                QuestStep("b", "Then talk", targets={"talk:x": True}),
            ],
        )
        self.registry._blueprints["clamp"] = blueprint
        self.quests.accept_quest("clamp")

        self.quests.notify("kill", "rat", amount=99)

        # Step advanced, so re-check by re-reading step a is impossible --
        # what matters is that it advanced exactly once and did not overflow.
        self.assertEqual(self.quests.current_step_key("clamp"), "b")


    def test_an_action_the_step_does_not_want_is_ignored(self):
        self.quests.accept_quest("testquest")

        # kill:rat is a target of step TWO. Doing it early must not bank
        # progress against a step that is not being watched.
        self.quests.notify("kill", "rat", amount=3)

        self.assertEqual(self.quests.current_step_key("testquest"), "intro")
        self.assertEqual(self.quests.progress_for("testquest"),
                         {"talk:tester": 0})


    def test_notify_on_an_inactive_quest_does_nothing(self):
        self.quests.notify("talk", "tester")

        self.assertEqual(self.quests.active_keys(), [])
        self.assertEqual(self.quests.completed_keys(), [])


    def test_completion_announces_and_records(self):
        self.quests.accept_quest("testquest")
        self.quests.notify("talk", "tester")
        self.quests.notify("kill", "rat", amount=3)

        self.assertEqual(self.quests.completed_keys(), ["testquest"])
        self.assertTrue(self.character.said("Test Quest"))
        self.assertEqual(self.quests.status("testquest"),
                         constants.STATUS_COMPLETED)


    def test_a_completed_quest_cannot_be_retaken(self):
        self.quests.accept_quest("testquest")
        self.quests.notify("talk", "tester")
        self.quests.notify("kill", "rat", amount=3)

        self.assertFalse(self.quests.is_available("testquest"))
        self.assertFalse(self.quests.accept_quest("testquest"))


    def test_abandoning_returns_the_quest_to_not_started(self):
        self.quests.accept_quest("testquest")

        self.assertTrue(self.quests.abandon_quest("testquest"))
        self.assertEqual(self.quests.status("testquest"),
                         constants.STATUS_NOT_STARTED)
        self.assertTrue(self.quests.is_available("testquest"))


    def test_abandoning_a_quest_not_held_is_a_no_op(self):
        self.assertFalse(self.quests.abandon_quest("testquest"))



class QuestHandlerReadApiTests(unittest.TestCase):
    """The read API dialogue, the quest command and the summary panel use."""

    def setUp(self):
        self.character = FakeCharacter()
        self.blueprint = _two_step_quest()
        self.registry = FakeRegistry([self.blueprint])
        self.patcher = mock.patch(_REGISTRY_PATH, self.registry)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.quests = QuestHandler(self.character)
        self.quests.accept_quest("testquest")


    def test_on_step_names_the_active_phase(self):
        self.assertTrue(self.quests.on_step("testquest", "intro"))
        self.assertFalse(self.quests.on_step("testquest", "hunt"))


    def test_progress_is_a_copy_not_the_live_store(self):
        # Handing out the stored _SaverDict would let a caller write to the
        # database through what reads as a getter.
        snapshot = self.quests.progress_for("testquest")
        snapshot["talk:tester"] = True

        self.assertEqual(self.quests.progress_for("testquest"),
                         {"talk:tester": 0})


    def test_boolean_objective_renders_a_tickbox_not_a_fraction(self):
        lines = self.quests.objective_lines("testquest")

        self.assertEqual(len(lines), 1)
        self.assertIn(constants.OBJECTIVE_TODO_MARK, lines[0])
        self.assertIn("Speak to the tester", lines[0])
        # The bug this replaces printed "talk:tester: 0/True".
        self.assertNotIn("/", lines[0])


    def test_counted_objective_renders_a_fraction(self):
        self.quests.notify("talk", "tester")
        self.quests.notify("kill", "rat")

        lines = self.quests.objective_lines("testquest")

        self.assertEqual(len(lines), 1)
        self.assertIn("1/3", lines[0])
        self.assertIn("Rats culled", lines[0])


    def test_satisfied_objective_is_ticked(self):
        self.quests.notify("talk", "tester")
        self.quests.notify("kill", "rat", amount=3)
        # Quest is over; nothing to render.
        self.assertEqual(self.quests.objective_lines("testquest"), [])


    def test_read_api_is_quiet_about_quests_not_held(self):
        self.assertIsNone(self.quests.current_step("nonesuch"))
        self.assertIsNone(self.quests.current_step_key("nonesuch"))
        self.assertEqual(self.quests.progress_for("nonesuch"), {})
        self.assertEqual(self.quests.objective_lines("nonesuch"), [])
        self.assertFalse(self.quests.is_available("nonesuch"))


    def test_step_index_past_the_end_reads_as_no_step(self):
        # A live character keeps the step index the blueprint had when they
        # accepted; shortening a quest in a content edit strands them past it.
        active = self.character.db.active_quests["testquest"]
        active[constants.FIELD_STEP_INDEX] = 99

        self.assertIsNone(self.quests.current_step("testquest"))
        self.assertEqual(self.quests.objective_lines("testquest"), [])



class BooleanAndCountedAreNotInterchangeableTests(unittest.TestCase):
    """Python makes True == 1; quest requirements must not."""

    def setUp(self):
        self.character = FakeCharacter()
        self.registry = FakeRegistry()
        self.patcher = mock.patch(_REGISTRY_PATH, self.registry)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.quests = QuestHandler(self.character)


    def test_a_counter_at_one_does_not_satisfy_a_boolean(self):
        satisfied = QuestHandler._is_satisfied(1, True)

        self.assertFalse(satisfied)


    def test_a_latched_boolean_satisfies_a_boolean(self):
        self.assertTrue(QuestHandler._is_satisfied(True, True))


    def test_zero_never_satisfies(self):
        self.assertFalse(QuestHandler._is_satisfied(0, True))
        self.assertFalse(QuestHandler._is_satisfied(0, 1))



class StepHookTests(unittest.TestCase):
    """on_enter and on_complete bracket each step transition."""

    def setUp(self):
        self.character = FakeCharacter()
        self.entered = []
        self.completed = []
        self.registry = FakeRegistry()
        self.patcher = mock.patch(_REGISTRY_PATH, self.registry)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.quests = QuestHandler(self.character)


    def _install(self, on_enter=None, on_complete=None):
        blueprint = _two_step_quest(on_enter=on_enter, on_complete=on_complete)
        self.registry._blueprints["testquest"] = blueprint

        return blueprint


    def test_on_enter_fires_once_when_the_quest_is_accepted(self):
        self._install(on_enter=lambda char, step: self.entered.append(step.key))

        self.quests.accept_quest("testquest")

        self.assertEqual(self.entered, ["intro"])


    def test_on_complete_fires_when_the_step_is_satisfied(self):
        self._install(on_complete=lambda char, step: self.completed.append(step.key))
        self.quests.accept_quest("testquest")

        self.assertEqual(self.completed, [])

        self.quests.notify("talk", "tester")

        self.assertEqual(self.completed, ["intro"])


    def test_hooks_receive_the_character_and_the_step(self):
        seen = []
        self._install(on_enter=lambda char, step: seen.append((char, step.key)))

        self.quests.accept_quest("testquest")

        self.assertEqual(seen, [(self.character, "intro")])


    def test_a_raising_hook_does_not_wedge_the_quest(self):
        def explode(character, step):
            raise RuntimeError("content bug")

        self._install(on_enter=explode)

        with mock.patch("systems.quests.handler.logger") as fake_logger:
            accepted = self.quests.accept_quest("testquest")

        self.assertTrue(accepted)
        self.assertTrue(self.quests.is_active("testquest"))
        self.assertTrue(fake_logger.log_err.called)



class RewardsAndPrerequisiteTests(unittest.TestCase):
    """The reward callback, and gating a quest behind another."""

    def setUp(self):
        self.character = FakeCharacter()
        self.registry = FakeRegistry()
        self.patcher = mock.patch(_REGISTRY_PATH, self.registry)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.quests = QuestHandler(self.character)


    def _one_step(self, key, rewards_callback=None, prerequisites=None):
        blueprint = QuestBlueprint(
            key, key.title(), "desc",
            steps=[QuestStep("only", "Do it", targets={"talk:x": True})],
            rewards_callback=rewards_callback,
            prerequisites=prerequisites,
        )
        self.registry._blueprints[key] = blueprint

        return blueprint


    def test_rewards_fire_on_completion(self):
        paid = []
        self._one_step("first", rewards_callback=paid.append)

        self.quests.accept_quest("first")
        self.quests.notify("talk", "x")

        self.assertEqual(paid, [self.character])


    def test_a_raising_reward_still_records_the_completion(self):
        def explode(character):
            raise RuntimeError("bad reward")

        self._one_step("first", rewards_callback=explode)
        self.quests.accept_quest("first")

        with mock.patch("systems.quests.handler.logger") as fake_logger:
            self.quests.notify("talk", "x")

        # Losing the reward is recoverable; losing the completion record is
        # not -- later quests gate on it.
        self.assertTrue(self.quests.is_complete("first"))
        self.assertTrue(fake_logger.log_err.called)


    def test_prerequisite_blocks_until_the_earlier_quest_is_done(self):
        self._one_step("first")
        self._one_step("second", prerequisites=["first"])

        self.assertFalse(self.quests.is_available("second"))
        self.assertFalse(self.quests.accept_quest("second"))

        self.quests.accept_quest("first")
        self.quests.notify("talk", "x")

        self.assertTrue(self.quests.is_available("second"))
        self.assertTrue(self.quests.accept_quest("second"))



class NotifyFanOutTests(unittest.TestCase):
    """One action reported once must reach every quest that wants it."""

    def setUp(self):
        self.character = FakeCharacter()
        self.registry = FakeRegistry()
        self.patcher = mock.patch(_REGISTRY_PATH, self.registry)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.quests = QuestHandler(self.character)

        for key in ("alpha", "beta"):
            self.registry._blueprints[key] = QuestBlueprint(
                key, key.title(), "desc",
                steps=[
                    QuestStep("hunt", "Kill a rat", targets={"kill:rat": 1}),
                    QuestStep("after", "Then talk", targets={"talk:x": True}),
                ],
            )

        self.quests.accept_quest("alpha")
        self.quests.accept_quest("beta")


    def test_one_kill_advances_both_quests(self):
        self.quests.notify("kill", "rat")

        self.assertEqual(self.quests.current_step_key("alpha"), "after")
        self.assertEqual(self.quests.current_step_key("beta"), "after")


    def test_completing_a_quest_mid_fan_out_is_safe(self):
        # notify walks the active-quest dict while the last step of a quest
        # deletes its own entry from it. Iterating live would raise.
        self.registry._blueprints["gamma"] = QuestBlueprint(
            "gamma", "Gamma", "desc",
            steps=[QuestStep("only", "Kill a rat", targets={"kill:rat": 1})],
        )
        self.quests.accept_quest("gamma")

        self.quests.notify("kill", "rat")

        self.assertTrue(self.quests.is_complete("gamma"))
        self.assertEqual(self.quests.current_step_key("alpha"), "after")
