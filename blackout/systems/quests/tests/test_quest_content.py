"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: Cross-checks the shipped quests against the registries they name
             -- recipes, NPCs, items, gatherables and skills.
"""

import unittest

from systems.crafting.registry import RECIPE_REGISTRY
from systems.progression.skills.gatherables import GATHERABLE_REGISTRY
from systems.progression.skills.registry import SKILL_REGISTRY
from systems.quests import constants
from systems.quests.loader import GLOBAL_QUEST_REGISTRY
from systems.quests.quests import split_target
from world.item_database import ITEM_DB
from world.npc_database import NPC_DB



# Private constant definitions

# Which registry owns the argument half of each action's target. A table
# rather than a branch chain, so wiring a new action to its registry is one
# row -- and so an action with no registry yet is simply absent rather than
# being a silently-skipped `elif`.
#
# Actions deliberately NOT listed: talk, interact, visit, use, give, survive,
# mine and harvest_brain. Each names something that has no data registry yet
# (dialogue nodes, world objects, room landmarks), so there is nothing to
# check the argument against. Adding one of those registries means adding a
# row here, and this suite starts guarding those targets too.
_ARGUMENT_REGISTRIES = {
    constants.ACTION_CRAFT: ("RECIPE_REGISTRY", RECIPE_REGISTRY),
    constants.ACTION_KILL: ("NPC_DB", NPC_DB),
    constants.ACTION_GATHER: ("ITEM_DB", ITEM_DB),
    constants.ACTION_CUT: ("GATHERABLE_REGISTRY", GATHERABLE_REGISTRY),
}



class RecordingSkills:
    """Captures every add_xp a reward callback makes."""

    def __init__(self) -> None:
        self.awards = []


    def add_xp(self, skill_key: str, amount: int) -> None:
        self.awards.append((skill_key, amount))



class RewardRecipient:
    """The least a reward callback needs: skills to award and a msg to send."""

    def __init__(self) -> None:
        self.skills = RecordingSkills()
        self.messages = []


    def msg(self, text: str = "", **kwargs) -> None:
        self.messages.append(str(text))



class TargetArgumentTests(unittest.TestCase):
    """A target naming content that does not exist can never be satisfied."""

    def test_every_checkable_target_names_real_content(self):
        for quest_key, blueprint in GLOBAL_QUEST_REGISTRY.all().items():
            for step in blueprint.steps:
                for target_key in step.targets:
                    self._assert_argument_exists(quest_key, step, target_key)


    def _assert_argument_exists(self, quest_key, step, target_key):
        """Check one target against whichever registry owns its action."""
        action, argument = split_target(target_key)
        owner = _ARGUMENT_REGISTRIES.get(action)

        if owner is None:
            return

        registry_name, registry = owner

        with self.subTest(quest=quest_key, step=step.key, target=target_key):
            self.assertIn(
                argument, registry,
                f"{quest_key}/{step.key} targets '{target_key}', but "
                f"'{argument}' is not in {registry_name}. The objective "
                f"could never be satisfied.",
            )


    def test_the_registry_table_only_names_real_actions(self):
        for action in _ARGUMENT_REGISTRIES:
            with self.subTest(action=action):
                self.assertIn(action, constants.QUEST_ACTIONS)


    def test_every_named_registry_is_populated(self):
        # A registry that failed to load would make every check above pass
        # vacuously by finding nothing to compare against.
        for action, (name, registry) in _ARGUMENT_REGISTRIES.items():
            with self.subTest(action=action, registry=name):
                self.assertGreater(len(registry), 0, f"{name} is empty")



class RewardCallbackTests(unittest.TestCase):
    """Rewards must name skills that exist, and must not raise."""

    def test_every_reward_callback_runs_and_awards_real_skills(self):
        """
        Runs each shipped reward callback against a recording stub.

        This is the test that would have caught award_rewards calling
        add_xp("[CRAFTING_SKILL]", 100) -- a literal placeholder that sat in
        the oasis quest and would have raised, or silently awarded XP to a
        skill that does not exist, the first time anyone finished it.
        """
        for quest_key, blueprint in GLOBAL_QUEST_REGISTRY.all().items():
            if blueprint.rewards_callback is None:
                continue

            with self.subTest(quest=quest_key):
                recipient = RewardRecipient()
                blueprint.rewards_callback(recipient)

                for skill_key, amount in recipient.skills.awards:
                    self.assertIn(
                        skill_key, SKILL_REGISTRY,
                        f"{quest_key} awards XP to '{skill_key}', which is "
                        f"not in SKILL_REGISTRY.",
                    )
                    self.assertGreater(amount, 0)


    def test_no_reward_text_carries_an_authoring_placeholder(self):
        # "[QUEST AWARD TEXT]" shipped in the oasis quest. A bracketed
        # all-caps token in player-facing text is always an unfinished draft.
        for quest_key, blueprint in GLOBAL_QUEST_REGISTRY.all().items():
            if blueprint.rewards_callback is None:
                continue

            recipient = RewardRecipient()
            blueprint.rewards_callback(recipient)

            for message in recipient.messages:
                with self.subTest(quest=quest_key, message=message):
                    self.assertNotRegex(message, r"\[[A-Z_ ]{4,}\]")



class QuestTextTests(unittest.TestCase):
    """Player-facing quest text must be finished prose."""

    def _all_text(self, blueprint):
        """Every string a player can read on this blueprint."""
        pieces = [blueprint.title, blueprint.description]

        for step in blueprint.steps:
            pieces.append(step.description)
            pieces.extend(step.objectives.values())

        return pieces


    def test_no_quest_text_carries_an_authoring_placeholder(self):
        for quest_key, blueprint in GLOBAL_QUEST_REGISTRY.all().items():
            for text in self._all_text(blueprint):
                with self.subTest(quest=quest_key, text=text):
                    self.assertNotRegex(str(text), r"\[[A-Z_ ]{4,}\]")


    def test_no_quest_text_is_marked_todo_or_tbd(self):
        for quest_key, blueprint in GLOBAL_QUEST_REGISTRY.all().items():
            for text in self._all_text(blueprint):
                lowered = str(text).lower()

                with self.subTest(quest=quest_key, text=text):
                    self.assertNotIn("todo", lowered)
                    self.assertNotIn("tbd", lowered)
