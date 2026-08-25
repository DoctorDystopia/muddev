"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: Keeps the action vocabulary honest -- the constants, the markdown
             that documents them, and the targets the shipped quests declare.
"""

import os
import re
import unittest

from systems.quests import constants
from systems.quests.loader import GLOBAL_QUEST_REGISTRY
from systems.quests.quests import split_target



# Private constant definitions

# The prose reference this module holds the code to. It sits beside the
# package it documents.
_DOC_FILENAME = "global_quest_actions.md"
_DOC_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    _DOC_FILENAME,
)

# Each action is documented under a level-3 heading wrapping the verb in
# backticks -- "### `interact`".
_DOC_ACTION_PATTERN = re.compile(r"^###\s+`([a-z_]+)`\s*$", re.MULTILINE)



def _documented_actions() -> set:
    """
    Purpose: Read the action verbs out of the reference document.

    Entry:
        _DOC_PATH names a readable file.

    Exit/Returns:
        Returns the set of verbs it documents.

    Module Globals:
        _DOC_PATH, _DOC_ACTION_PATTERN read.

    Methodology:
        Parses the level-3 headings rather than any hand-maintained list. The
        point of this module is that the document and the code cannot drift,
        so neither may be transcribed into the other.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    with open(_DOC_PATH, encoding="utf-8") as handle:
        text = handle.read()

    found = set(_DOC_ACTION_PATTERN.findall(text))

    return found



class VocabularyDocumentationTests(unittest.TestCase):
    """QUEST_ACTIONS and global_quest_actions.md are one fact, stated twice."""

    def test_the_reference_document_exists(self):
        self.assertTrue(os.path.isfile(_DOC_PATH), _DOC_PATH)


    def test_every_documented_action_is_a_constant(self):
        documented = _documented_actions()

        self.assertTrue(documented, "parsed no actions out of the document")

        for action in sorted(documented):
            with self.subTest(action=action):
                self.assertIn(
                    action, constants.QUEST_ACTIONS,
                    f"'{action}' is documented in {_DOC_FILENAME} but is not "
                    f"in QUEST_ACTIONS, so a blueprint naming it would be "
                    f"refused at import.",
                )


    def test_every_constant_action_is_documented(self):
        documented = _documented_actions()

        for action in sorted(constants.QUEST_ACTIONS):
            with self.subTest(action=action):
                self.assertIn(
                    action, documented,
                    f"'{action}' is in QUEST_ACTIONS but has no '### `{action}`' "
                    f"section in {_DOC_FILENAME}.",
                )


    def test_no_action_contains_the_target_separator(self):
        # An action carrying a colon would make split_target ambiguous.
        for action in sorted(constants.QUEST_ACTIONS):
            with self.subTest(action=action):
                self.assertNotIn(constants.TARGET_SEPARATOR, action)



class ShippedTargetTests(unittest.TestCase):
    """Every target the game actually declares must be well formed."""

    def test_every_target_names_a_documented_action(self):
        for quest_key, blueprint in GLOBAL_QUEST_REGISTRY.all().items():
            for step in blueprint.steps:
                for target_key in step.targets:
                    action, _argument = split_target(target_key)

                    with self.subTest(quest=quest_key, step=step.key,
                                      target=target_key):
                        self.assertIn(action, constants.QUEST_ACTIONS)


    def test_every_target_carries_an_argument(self):
        # The vocabulary permits a bare action, but no shipped objective
        # should be "kill anything" -- an argumentless target almost always
        # means a missing identifier rather than a deliberate wildcard.
        for quest_key, blueprint in GLOBAL_QUEST_REGISTRY.all().items():
            for step in blueprint.steps:
                for target_key in step.targets:
                    _action, argument = split_target(target_key)

                    with self.subTest(quest=quest_key, step=step.key,
                                      target=target_key):
                        self.assertIsNotNone(argument)
                        self.assertTrue(argument.strip())


    def test_no_target_is_declared_on_two_steps_of_one_quest(self):
        """
        Progress is re-seeded from scratch at each step boundary, so the same
        target on two steps means the player must do it twice with no hint
        that the first one counted for a different phase. Almost always a
        copy-paste rather than an intent.
        """
        for quest_key, blueprint in GLOBAL_QUEST_REGISTRY.all().items():
            seen = {}

            for step in blueprint.steps:
                for target_key in step.targets:
                    with self.subTest(quest=quest_key, target=target_key):
                        self.assertNotIn(
                            target_key, seen,
                            f"also declared on step '{seen.get(target_key)}'",
                        )

                    seen[target_key] = step.key
