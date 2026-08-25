"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: Tests for notify_quests -- the guard every progression call site
             sits behind.
"""

import unittest
from unittest import mock

from systems.quests import constants
from systems.quests.hooks import notify_quests



class RecordingQuests:
    """A quest handler that records what it was told."""

    def __init__(self, explode: bool = False) -> None:
        self.calls = []
        self.explode = explode


    def notify(self, action, argument=None, amount=1):
        if self.explode:
            raise RuntimeError("quest bug")

        self.calls.append((action, argument, amount))



class Actor:
    """Anything that might have performed a quest-relevant action."""

    def __init__(self, quests=None) -> None:
        if quests is not None:
            self.quests = quests



class NotifyQuestsTests(unittest.TestCase):
    """Three guards, in order: no handler, bad verb, raising handler."""

    def test_a_valid_action_reaches_the_handler(self):
        quests = RecordingQuests()

        notify_quests(Actor(quests), constants.ACTION_KILL, "mutant_raider")

        self.assertEqual(quests.calls, [("kill", "mutant_raider", 1)])


    def test_amount_is_passed_through(self):
        quests = RecordingQuests()

        notify_quests(Actor(quests), constants.ACTION_GATHER,
                      "rusty_metal_chunk", amount=5)

        self.assertEqual(quests.calls, [("gather", "rusty_metal_chunk", 5)])


    def test_an_actor_with_no_quest_handler_is_ignored_quietly(self):
        # Every hostile NPC can land a killing blow and none carry quests, so
        # the absence is normal and must not be logged.
        with mock.patch("systems.quests.hooks.logger") as fake_logger:
            notify_quests(Actor(), constants.ACTION_KILL, "player")

        self.assertFalse(fake_logger.log_err.called)


    def test_a_none_actor_is_ignored_quietly(self):
        # at_death normalises a self-inflicted death to killer=None, and the
        # call site must not have to pre-check.
        with mock.patch("systems.quests.hooks.logger") as fake_logger:
            notify_quests(None, constants.ACTION_KILL, "mutant_raider")

        self.assertFalse(fake_logger.log_err.called)


    def test_an_undocumented_action_is_dropped_and_logged(self):
        quests = RecordingQuests()

        with mock.patch("systems.quests.hooks.logger") as fake_logger:
            notify_quests(Actor(quests), "interract", "pipe")

        self.assertEqual(quests.calls, [])
        self.assertTrue(fake_logger.log_err.called)


    def test_a_raising_handler_does_not_propagate(self):
        # This sits inside at_death and perform_craft. An exception here would
        # take the kill or the craft down with it.
        quests = RecordingQuests(explode=True)

        with mock.patch("systems.quests.hooks.logger") as fake_logger:
            notify_quests(Actor(quests), constants.ACTION_CRAFT,
                          "rusty scrap axe")

        self.assertTrue(fake_logger.log_err.called)



class CallSiteTests(unittest.TestCase):
    """The hook must actually be wired where progression happens."""

    def test_at_death_reports_kills_on_the_stable_npc_key(self):
        """
        Guards the fix to typeclasses/mixins.py.

        The line this replaces called update_progress("*", "kill", self.key).
        "*" is not a quest key, so the registry lookup on the first line of
        update_progress returned None and the call did nothing -- no kill
        objective in the game could advance. It also passed the display name
        ("Mutant Raider") where the stat line beside it used db.npc_key
        ("mutant_raider").
        """
        import typeclasses.mixins as mixins
        import inspect

        source = inspect.getsource(mixins.CombatEntity.at_death)

        self.assertIn("notify_quests(killer", source)
        self.assertIn("ACTION_KILL, npc_key", source)
        self.assertNotIn('update_progress("*"', source)


    def test_perform_craft_reports_the_recipe_key(self):
        import inspect

        from systems.crafting import crafting_service

        source = inspect.getsource(crafting_service.perform_craft)

        self.assertIn("notify_quests(caller", source)
        self.assertIn("ACTION_CRAFT, recipe_key", source)


    def test_gathering_reports_both_cut_and_gather(self):
        import inspect

        from systems.progression.skills.skill_defs.gathering import cutting

        source = inspect.getsource(cutting.Cutting._execute_gathering)

        self.assertIn("ACTION_CUT, gatherable_key", source)
        self.assertIn("ACTION_GATHER, item_key", source)
