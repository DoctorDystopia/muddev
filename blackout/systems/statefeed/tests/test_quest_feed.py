"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/28/2026
Description: Cases for the char_quests channel.

             Two halves, and they fail differently.

             THE SHAPE. `systems/statefeed/quests.py` turns a quest log into
             numbers rather than into prose, so a client can draw a progress
             bar. A mistake here is visible -- a wrong count, a missing quest.

             THE TRIGGER. `QuestHandler` publishes after every public method
             that writes `db.active_quests`. A mistake THERE is invisible: the
             log is simply stale, and stays stale until the player logs out and
             back in. `_publishes` exists so there is one implementation rather
             than nine, and `PublishMarkerTests` is what stops a seventh writer
             being added without one -- derived from the source, so adding a
             method needs no edit here.

             Uses the quest engine's own doubles. Testing the feed against the
             shipped quests would mean every content edit could break it.
"""

import inspect
import re
import unittest
from unittest import mock

from systems.quests.handler import QuestHandler
from systems.quests.quests import QuestBlueprint, QuestStep
from systems.quests.tests.stubs import FakeCharacter, FakeRegistry
from systems.statefeed import quests as quest_feed


# ─── Private constant definitions ────────────────────────────────────────────

# Where QuestHandler looks the registry up. Patched rather than the loader's
# own module attribute, because handler.py binds the name at import.
_REGISTRY_PATH = "systems.quests.handler.GLOBAL_QUEST_REGISTRY"

# Where the payload builder looks it up. A DIFFERENT binding: quests.py imports
# it inside the function, so the name it resolves is the loader's own.
_LOADER_PATH = "systems.quests.loader.GLOBAL_QUEST_REGISTRY"

# What a WRITE to the quest store looks like in source, as opposed to a read.
#
# Patterns rather than method names, so the rule below stays a relationship: a
# method added tomorrow is classified by what it does, and this file needs no
# edit. Reads are deliberately excluded -- `completed_keys` mentions
# `db.completed_quests` and changes nothing, and marking it would publish the
# whole log every time anything asked the handler a question.
#
# `_complete_quest` is a private mutator reached only through a public one, so
# a call to it counts as a write by the caller.
_WRITE_PATTERNS = (
    re.compile(r"db\.active_quests\[[^\]]+\]\s*="),
    re.compile(r"del\s+self\.obj\.db\.active_quests\["),
    re.compile(r"db\.completed_quests\.(append|remove)\("),
    re.compile(r"self\._complete_quest\("),
)


def _writes(source: str) -> bool:
    """True when this method source changes the quest store."""
    for pattern in _WRITE_PATTERNS:
        if pattern.search(source):
            return True

    return False


def _quest() -> QuestBlueprint:
    """One quest whose first step has both kinds of objective."""
    return QuestBlueprint(
        key="testquest",
        title="Test Quest",
        description="A quest that exists only here.",
        steps=[
            QuestStep(
                key="intro",
                description="Speak to the tester and cull three rats.",
                targets={"talk:tester": True, "kill:rat": 3},
                objectives={
                    "talk:tester": "Speak to the tester",
                    "kill:rat": "Rats culled",
                },
            ),
            QuestStep(
                key="outro",
                description="Report back.",
                targets={"talk:tester": True},
            ),
        ],
    )


class _FeedTestCase(unittest.TestCase):
    """A character holding one hand-built quest, with both registries patched."""

    def setUp(self):
        self.character = FakeCharacter()
        self.blueprint = _quest()
        self.registry = FakeRegistry([self.blueprint])

        for path in (_REGISTRY_PATH, _LOADER_PATH):
            patcher = mock.patch(path, self.registry)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.quests = QuestHandler(self.character)
        self.character.quests = self.quests

    def _objective(self, payload, target_key):
        for row in payload.active[0]["objectives"]:
            if row["key"] == target_key:
                return row

        self.fail("no objective %r in %r" % (target_key, payload.active))


class PayloadShapeTests(_FeedTestCase):
    """What a client is actually handed."""

    def test_a_character_with_no_handler_is_a_no_op(self):
        """Every NPC in the game reaches this path on a resync."""
        payload = quest_feed.build_payload(object())

        self.assertEqual(payload.active, [])
        self.assertEqual(payload.completed, [])

    def test_a_fresh_character_holds_nothing(self):
        payload = quest_feed.build_payload(self.character)

        self.assertEqual(payload.active, [])
        self.assertEqual(payload.completed, [])

    def test_an_accepted_quest_names_itself_and_its_step(self):
        self.quests.accept_quest("testquest")

        payload = quest_feed.build_payload(self.character)

        self.assertEqual(len(payload.active), 1)

        row = payload.active[0]
        self.assertEqual(row["key"], "testquest")
        self.assertEqual(row["title"], "Test Quest")
        self.assertEqual(row["step"], "intro")
        self.assertIn("cull three rats", row["step_description"])

    def test_a_counted_objective_reports_both_numbers(self):
        """The whole reason this channel is structured rather than rendered."""
        self.quests.accept_quest("testquest")
        self.quests.notify("kill", "rat", amount=2)

        objective = self._objective(
            quest_feed.build_payload(self.character), "kill:rat")

        self.assertTrue(objective["counted"])
        self.assertEqual(objective["current"], 2)
        self.assertEqual(objective["required"], 3)
        self.assertFalse(objective["done"])
        self.assertEqual(objective["description"], "Rats culled")

    def test_a_one_shot_objective_still_reports_a_requirement_of_one(self):
        """Normalised rather than left absent, so a client draws the same bar
        for both kinds without a branch. `counted` carries the distinction."""
        self.quests.accept_quest("testquest")

        objective = self._objective(
            quest_feed.build_payload(self.character), "talk:tester")

        self.assertFalse(objective["counted"])
        self.assertEqual(objective["required"], 1)
        self.assertEqual(objective["current"], 0)
        self.assertFalse(objective["done"])

    def test_done_is_asked_of_the_handler_not_recomputed(self):
        """"1 of True" is the comparison this codebase has already got wrong
        once, so there is exactly one implementation of it."""
        self.quests.accept_quest("testquest")
        self.quests.notify("talk", "tester")

        objective = self._objective(
            quest_feed.build_payload(self.character), "talk:tester")

        self.assertTrue(objective["done"])
        self.assertEqual(objective["current"], 1)

    def test_the_payload_follows_the_step_the_player_is_on(self):
        """The CURRENT step only: finished steps are a history the handler does
        not keep, and steps ahead would spoil the quest."""
        self.quests.accept_quest("testquest")
        self.quests.notify("talk", "tester")
        self.quests.notify("kill", "rat", amount=3)

        row = quest_feed.build_payload(self.character).active[0]

        self.assertEqual(row["step"], "outro")
        self.assertEqual(len(row["objectives"]), 1)

    def test_a_finished_quest_moves_to_completed(self):
        self.quests.force_complete_quest("testquest")

        payload = quest_feed.build_payload(self.character)

        self.assertEqual(payload.active, [])
        self.assertEqual(payload.completed,
                         [{"key": "testquest", "title": "Test Quest"}])

    def test_a_quest_nothing_declares_is_skipped_rather_than_sent_blank(self):
        """The loader tolerates a content module that failed to import, so a
        character can hold a key nothing declares any more. A row a client
        cannot label is worse than a row that is not there."""
        self.quests.accept_quest("testquest")
        self.character.db.active_quests["ghost"] = {"step_index": 0,
                                                    "progress": {}}

        payload = quest_feed.build_payload(self.character)

        self.assertEqual([row["key"] for row in payload.active], ["testquest"])


class PublishMarkerTests(unittest.TestCase):
    """Every public writer publishes, and the rule is derived from the source.

    This is the guard that matters. A seventh public writer added without a
    marker does not fail, log, or misbehave -- the client's quest log simply
    stops updating until the player reconnects, which is the kind of bug that
    is reported months later as "the quest tab is flaky".
    """

    def _public_methods(self):
        for name, method in vars(QuestHandler).items():
            if name.startswith("_") or not callable(method):
                continue

            yield name, method

    def test_the_scan_found_the_handler(self):
        """A scan that reads nothing is a guard that has stopped guarding."""
        names = [name for name, _ in self._public_methods()]

        self.assertGreater(len(names), 10, names)
        self.assertIn("accept_quest", names)

    def test_every_public_writer_is_marked(self):
        for name, method in self._public_methods():
            if not _writes(inspect.getsource(method)):
                continue

            with self.subTest(method=name):
                self.assertTrue(
                    hasattr(method, "__wrapped__"),
                    "QuestHandler.%s writes the quest store but carries no "
                    "@_publishes marker, so a client's quest log would go "
                    "stale after it." % name)

    def test_a_marked_method_is_one_that_writes(self):
        """The other direction. A marker on a read would publish the whole log
        every time anything asked a question of the handler."""
        for name, method in self._public_methods():
            if not hasattr(method, "__wrapped__"):
                continue

            with self.subTest(method=name):
                self.assertTrue(
                    _writes(inspect.getsource(method.__wrapped__)),
                    "QuestHandler.%s is marked @_publishes but writes "
                    "nothing." % name)

    def test_the_fan_out_is_not_marked(self):
        """`notify` calls `update_progress` once per active quest. Marking both
        would publish the whole log twice for a single kill."""
        self.assertFalse(hasattr(QuestHandler.notify, "__wrapped__"))
