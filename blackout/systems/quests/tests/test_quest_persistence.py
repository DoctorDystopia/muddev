"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: The engine against a REAL Character -- Evennia's nested saver
             structures, the lazy handler property, and the quest command.
"""

from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from systems.quests import constants
from systems.quests.quests import QuestBlueprint, QuestStep
from systems.quests.tests.stubs import FakeRegistry



# Private constant definitions
_REGISTRY_PATH = "systems.quests.handler.GLOBAL_QUEST_REGISTRY"
_COMMAND_REGISTRY_PATH = "commands.quest_cmds.GLOBAL_QUEST_REGISTRY"



def _sample_quest() -> QuestBlueprint:
    """A two-step quest with one boolean and one counted objective."""
    return QuestBlueprint(
        key="persisted",
        title="A Persisted Quest",
        description="Stored on a real character.",
        steps=[
            QuestStep(
                key="intro",
                description="Speak to the tester.",
                targets={"talk:tester": True},
                objectives={"talk:tester": "Speak to the tester"},
            ),
            QuestStep(
                key="hunt",
                description="Cull three rats.",
                targets={"kill:rat": 3},
                objectives={"kill:rat": "Rats culled"},
            ),
        ],
    )



class QuestPersistenceTests(EvenniaTest):
    """
    Purpose: Prove the engine survives Evennia's Attribute layer.

    Entry:
        self.char1 is a real Character with a quests handler.

    Exit/Returns:
        No conditions.

    Module Globals:
        None

    Methodology:
        The engine tests run against a plain-dict stub, which cannot catch a
        write that fails to reach the database. Progress lives two levels deep
        -- db.active_quests[key]["progress_data"][target] -- and Evennia wraps
        each level in a _SaverDict whose write-through behaviour is the thing
        actually being relied on here.

    Notes/References:
        EvenniaTest rather than EvenniaTestCase because a real Character is
        the whole subject.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """

    def setUp(self):
        super().setUp()
        self.blueprint = _sample_quest()
        self.registry = FakeRegistry([self.blueprint])
        patcher = mock.patch(_REGISTRY_PATH, self.registry)
        patcher.start()
        self.addCleanup(patcher.stop)


    def test_the_handler_is_reachable_as_character_quests(self):
        self.assertIsNotNone(self.char1.quests)
        self.assertEqual(self.char1.quests.active_keys(), [])


    def test_accepted_quest_survives_a_handler_rebuild(self):
        self.char1.quests.accept_quest("persisted")

        # Drop the lazy_property cache the way a @reload would.
        self.char1.__dict__.pop("quests", None)

        self.assertTrue(self.char1.quests.is_active("persisted"))
        self.assertEqual(self.char1.quests.current_step_key("persisted"),
                         "intro")


    def test_counted_progress_writes_through_the_nested_saver_dicts(self):
        quests = self.char1.quests
        quests.accept_quest("persisted")
        quests.notify("talk", "tester")

        quests.notify("kill", "rat")
        quests.notify("kill", "rat")

        self.char1.__dict__.pop("quests", None)

        self.assertEqual(self.char1.quests.progress_for("persisted"),
                         {"kill:rat": 2})


    def test_boolean_progress_writes_through(self):
        quests = self.char1.quests
        quests.accept_quest("persisted")
        quests.notify("talk", "tester")

        self.char1.__dict__.pop("quests", None)

        # Advancing re-seeds progress, so the latch is proved by the step
        # having moved rather than by the old counter.
        self.assertEqual(self.char1.quests.current_step_key("persisted"),
                         "hunt")


    def test_completion_persists(self):
        quests = self.char1.quests
        quests.accept_quest("persisted")
        quests.notify("talk", "tester")
        quests.notify("kill", "rat", amount=3)

        self.char1.__dict__.pop("quests", None)

        self.assertEqual(self.char1.quests.completed_keys(), ["persisted"])
        self.assertEqual(self.char1.db.active_quests, {})


    def test_abandon_persists(self):
        quests = self.char1.quests
        quests.accept_quest("persisted")
        quests.abandon_quest("persisted")

        self.char1.__dict__.pop("quests", None)

        self.assertEqual(self.char1.quests.active_keys(), [])
        self.assertEqual(self.char1.quests.completed_keys(), [])


    def test_two_quests_progress_independently(self):
        other = QuestBlueprint(
            "other", "Other", "desc",
            steps=[QuestStep("only", "Cull one rat",
                             targets={"kill:rat": 1})],
        )
        self.registry._blueprints["other"] = other

        quests = self.char1.quests
        quests.accept_quest("persisted")
        quests.accept_quest("other")

        quests.notify("kill", "rat")

        # "other" wanted the rat and is done; "persisted" is still on its
        # first step, which does not watch kills at all.
        self.assertTrue(quests.is_complete("other"))
        self.assertEqual(quests.current_step_key("persisted"), "intro")



class QuestCommandTests(EvenniaTest):
    """The `quest` command, driven the way a player drives it."""

    def setUp(self):
        super().setUp()
        self.blueprint = _sample_quest()
        self.registry = FakeRegistry([self.blueprint])

        for path in (_REGISTRY_PATH, _COMMAND_REGISTRY_PATH):
            patcher = mock.patch(path, self.registry)
            patcher.start()
            self.addCleanup(patcher.stop)


    def _run(self, args: str = "") -> str:
        """Execute `quest <args>` as char1 and return what it printed."""
        from commands.quest_cmds import CmdQuest

        command = CmdQuest()
        command.caller = self.char1
        command.args = args

        sent = []
        with mock.patch.object(self.char1, "msg",
                               side_effect=lambda text="", **kw: sent.append(str(text))):
            command.func()

        return "\n".join(sent)


    def test_empty_journal_says_so(self):
        output = self._run()

        self.assertIn("no active quests", output.lower())


    def test_journal_lists_an_active_quest_and_its_current_step(self):
        self.char1.quests.accept_quest("persisted")

        output = self._run()

        self.assertIn("A Persisted Quest", output)
        self.assertIn("Speak to the tester", output)


    def test_detail_view_renders_objectives(self):
        self.char1.quests.accept_quest("persisted")
        self.char1.quests.notify("talk", "tester")
        self.char1.quests.notify("kill", "rat")

        output = self._run("a persisted quest")

        self.assertIn("Cull three rats", output)
        self.assertIn("1/3", output)


    def test_detail_view_matches_on_the_quest_key_too(self):
        self.char1.quests.accept_quest("persisted")

        output = self._run("persisted")

        self.assertIn("A Persisted Quest", output)


    def test_an_unheld_quest_is_not_revealed(self):
        # Searching the whole registry would let `quest` confirm content the
        # player has never met.
        output = self._run("persisted")

        self.assertIn("know of no quest", output.lower())


    def test_a_completed_quest_is_listed_as_completed(self):
        quests = self.char1.quests
        quests.accept_quest("persisted")
        quests.notify("talk", "tester")
        quests.notify("kill", "rat", amount=3)

        journal = self._run()
        detail = self._run("persisted")

        self.assertIn("Completed", journal)
        self.assertIn("Completed", detail)
