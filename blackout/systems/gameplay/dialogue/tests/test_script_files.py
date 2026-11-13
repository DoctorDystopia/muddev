"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/11/2026
Description: Tests of the dialogue script files (DESIGN-0017): each compiled
             script is current, each script of the game passes the content
             check, and the server reads the compiler version of the addon
             in this repository.

             THESE TESTS ARE THE GATE FOR A GENERATED FILE. Python cannot
             run the addon compiler. Thus, a compiled script is in git, and
             the digest in it ties it to its dialogue script. A test that
             fails here names the file and says how to write it again.

             The game tests need the quest registry, so they use
             EvenniaTestCase. The others need no database.
"""

import os
import re
import unittest

from django.conf import settings
from evennia.utils.test_resources import EvenniaTestCase

from systems.gameplay.dialogue import constants as dialogue_const
from systems.gameplay.dialogue import files, loader, vocabulary
from systems.gameplay.dialogue.script import source_digest
from systems.gameplay.dialogue.tests import helpers
from world.npc_database import NPC_DB


# Where the addon declares the version of its compiler.
_ADDON_IMPORTER = os.path.join(
    os.path.dirname(settings.GAME_DIR),
    "godot", "addons", "dialogue_manager", "import_plugin.gd")
_COMPILER_VERSION_PATTERN = re.compile(r"const COMPILER_VERSION: int = (\d+)")

# Where the script export declares the version of its file shape.
_EXPORT_SCRIPT = os.path.join(
    os.path.dirname(settings.GAME_DIR),
    "godot", "addons", "blackout_dialogue", "dialogue_script_export.gd")
_FORMAT_PATTERN = re.compile(r"const FORMAT := (\d+)")


def _number_in(path, pattern):
    """The number that one pattern finds in one GDScript file."""
    with open(path, encoding="utf-8") as handle:
        found = pattern.search(handle.read())

    return int(found.group(1))


# One text and its digest. The Godot test of the script export holds the
# same two (`test_dialogue_script_export.gd`). Thus, the two languages
# cannot give different digests.
_SHARED_TEXT = "~ start\nGuard: Hello.\n"
_SHARED_DIGEST = "b8a8071d9127c2049efa30e76bfb0f8f0220b57034eb29840e4b15aa2dc82f1e"


class DigestTests(unittest.TestCase):
    """The digest that ties a compiled script to its dialogue script."""

    def test_the_digest_is_the_one_that_the_script_export_gives(self):
        self.assertEqual(source_digest(_SHARED_TEXT), _SHARED_DIGEST)

    def test_the_line_ends_do_not_change_the_digest(self):
        self.assertEqual(source_digest("~ start\r\nHello.\r\n"),
                         source_digest("~ start\nHello.\n"))

    def test_a_change_of_the_text_changes_the_digest(self):
        self.assertNotEqual(source_digest("~ start\nHello.\n"),
                            source_digest("~ start\nHello!\n"))


class AddonVersionTests(unittest.TestCase):
    """The two version numbers that the Godot side and the server share."""

    def test_the_server_reads_the_compiler_version_of_the_addon(self):
        addon_version = _number_in(_ADDON_IMPORTER, _COMPILER_VERSION_PATTERN)

        self.assertEqual(
            addon_version, dialogue_const.SUPPORTED_COMPILER_VERSION,
            "The Dialogue Manager addon has a new compiler version. Read "
            "the compiled format again (DESIGN-0017, 'An addon update'), "
            "then change SUPPORTED_COMPILER_VERSION and run the script "
            "export.")

    def test_the_script_export_writes_the_format_that_the_server_reads(self):
        export_format = _number_in(_EXPORT_SCRIPT, _FORMAT_PATTERN)

        self.assertEqual(export_format, dialogue_const.COMPILED_FORMAT)


class FixturePairTests(unittest.TestCase):
    """The fixture scripts of these tests are current."""

    def test_each_fixture_has_a_current_compiled_script(self):
        problems = files.pair_problems(
            helpers.FIXTURE_DIRECTORY, helpers.FIXTURE_DIRECTORY)

        self.assertEqual(problems, [])

    def test_a_changed_source_is_reported(self):
        from unittest import mock

        with mock.patch.object(files, "source_digest", return_value="other"):
            problems = files.pair_problems(
                helpers.FIXTURE_DIRECTORY, helpers.FIXTURE_DIRECTORY)

        self.assertTrue(problems)
        self.assertTrue(all("out of date" in problem for problem in problems))


class GameScriptTests(EvenniaTestCase):
    """Each dialogue script of the game."""

    def test_the_vocabulary_definitions_load(self):
        self.assertEqual(vocabulary.load_errors(), [])

    def test_each_vocabulary_entry_has_a_summary(self):
        for name, entry in vocabulary.vocabulary().items():
            with self.subTest(name=name):
                self.assertTrue(entry.summary)
                self.assertIn(entry.kind, dialogue_const.VOCABULARY_KINDS)

    def test_each_dialogue_script_has_a_current_compiled_script(self):
        problems = files.pair_problems(
            files.source_directory(), loader.compiled_directory())

        self.assertEqual(problems, [])

    def test_each_compiled_script_passes_the_content_check(self):
        for key in loader.script_keys():
            with self.subTest(script=key):
                self.assertEqual(files.content_problems(key), [])

    def test_each_def_names_a_script_that_loads(self):
        for npc_key, npc_def in NPC_DB.items():
            if not npc_def.dialogue_script:
                continue

            with self.subTest(npc=npc_key):
                script = loader.get_script(npc_def.dialogue_script)

                self.assertEqual(script.key, npc_def.dialogue_script)

    def test_no_def_names_a_script_and_a_module(self):
        for npc_key, npc_def in NPC_DB.items():
            with self.subTest(npc=npc_key):
                both = bool(npc_def.dialogue) and bool(npc_def.dialogue_script)

                self.assertFalse(both)
