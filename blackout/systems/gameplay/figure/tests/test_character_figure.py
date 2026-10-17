"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/16/2026
Description: Cases for the figure of a player character: the two
             readers, the two writers, and the names that they take from the
             figure files.

             No case needs a database. A small stand-in object gives the
             attribute handler, and _publish is replaced, because
             test_freshness.py owns the proof that a write reaches the feed.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.gameplay.figure.tests.test_character_figure
"""

import json
import os
import unittest
from unittest import mock

from assets.pipeline import paths
from systems.gameplay.figure import character_figure
from systems.gameplay.figure import constants as const
from systems.gameplay.figure import figure_files


# ─── Private helper classes ──────────────────────────────────────────────────

class _Attributes:
    """The two calls of an Evennia attribute handler that character_figure.py makes."""

    def __init__(self):
        self.stored = {}

    def get(self, key, default=None):
        return self.stored.get(key, default)

    def add(self, key, value):
        self.stored[key] = value


class _Character:
    """A stand-in for a Character: a key and an attribute handler."""

    def __init__(self):
        self.key = "Tester"
        self.attributes = _Attributes()


# ─── Test cases ──────────────────────────────────────────────────────────────

class FigureFileNameTests(unittest.TestCase):
    """The names that the server takes from the figure files."""

    def test_the_default_body_type_has_a_rig(self):
        self.assertIn(const.DEFAULT_BODY_TYPE, figure_files.body_types())

    def test_each_body_type_is_the_key_of_its_rig(self):
        for body_type in figure_files.body_types():
            with self.subTest(body_type=body_type):
                path = os.path.join(paths.FIGURE_RIGS_DIR,
                                    body_type + paths.FIGURE_FILE_SUFFIX)

                with open(path, encoding="utf-8") as handle:
                    self.assertEqual(json.load(handle)["key"], body_type)

    def test_each_role_of_a_character_has_a_palette_color(self):
        """A character with no colors of its own still draws each role."""
        with open(paths.FIGURE_PALETTE_PATH, encoding="utf-8") as handle:
            roles = json.load(handle).get("roles", {})

        for role in const.CHARACTER_COLOR_ROLES:
            with self.subTest(role=role):
                self.assertIn(roles.get(role), figure_files.named_colors())


class ReaderTests(unittest.TestCase):
    """body_type_of and figure_colors_of."""

    def test_a_new_character_has_the_default_body_type(self):
        self.assertEqual(character_figure.body_type_of(_Character()), const.DEFAULT_BODY_TYPE)

    def test_a_new_character_has_no_colors_of_its_own(self):
        self.assertEqual(character_figure.figure_colors_of(_Character()), {})

    def test_a_stored_value_that_is_no_text_gives_the_default(self):
        character = _Character()
        character.attributes.add(const.BODY_TYPE_ATTR, 3)

        self.assertEqual(character_figure.body_type_of(character), const.DEFAULT_BODY_TYPE)

    def test_the_colors_hold_only_the_roles_of_a_character(self):
        character = _Character()
        role = const.CHARACTER_COLOR_ROLES[0]
        character.attributes.add(const.FIGURE_COLORS_ATTR,
                                 {role: "skin", "metal": "gold", "hair": 7})

        self.assertEqual(character_figure.figure_colors_of(character), {role: "skin"})


@mock.patch.object(character_figure, "_publish")
class WriterTests(unittest.TestCase):
    """set_body_type and set_figure_color."""

    def test_a_body_type_with_a_rig_is_stored_and_sent(self, publish):
        character = _Character()
        body_type = figure_files.body_types()[-1]

        succeeded, message = character_figure.set_body_type(character, body_type)

        self.assertTrue(succeeded)
        self.assertIn(body_type, message)
        self.assertEqual(character_figure.body_type_of(character), body_type)
        publish.assert_called_once_with(character)

    def test_a_body_type_with_no_rig_is_refused(self, publish):
        character = _Character()

        succeeded, message = character_figure.set_body_type(character, "no_such_body")

        self.assertFalse(succeeded)
        self.assertIn("not a body type", message)
        self.assertEqual(character.attributes.stored, {})
        publish.assert_not_called()

    def test_a_named_color_is_stored_and_sent(self, publish):
        character = _Character()
        role = const.CHARACTER_COLOR_ROLES[0]
        color = figure_files.named_colors()[0]

        succeeded, _message = character_figure.set_figure_color(character, role, color)

        self.assertTrue(succeeded)
        self.assertEqual(character_figure.figure_colors_of(character), {role: color})
        publish.assert_called_once_with(character)

    def test_the_palette_color_takes_the_role_away(self, publish):
        character = _Character()
        role = const.CHARACTER_COLOR_ROLES[0]

        character_figure.set_figure_color(character, role, figure_files.named_colors()[0])
        character_figure.set_figure_color(character, role, const.PALETTE_COLOR)

        self.assertEqual(character_figure.figure_colors_of(character), {})

    def test_a_role_that_a_character_does_not_own_is_refused(self, publish):
        succeeded, message = character_figure.set_figure_color(
            _Character(), "metal", figure_files.named_colors()[0])

        self.assertFalse(succeeded)
        self.assertIn("not a color role", message)
        publish.assert_not_called()

    def test_a_color_that_the_palette_does_not_have_is_refused(self, publish):
        role = const.CHARACTER_COLOR_ROLES[0]

        succeeded, message = character_figure.set_figure_color(_Character(), role, "no_such_color")

        self.assertFalse(succeeded)
        self.assertIn("not a named color", message)
        publish.assert_not_called()
