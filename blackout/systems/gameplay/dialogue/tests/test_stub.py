"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/11/2026
Description: Tests of the editor stub of the dialogue vocabulary
             (DESIGN-0017): the generated GDScript file in the Godot project
             is the text that the vocabulary gives now.

             A new vocabulary entry with no new stub fails here. The fix is
             one command, and the failure message names it. The Godot editor
             also runs that command at each save of a dialogue script.
"""

from evennia.utils.test_resources import EvenniaTestCase

from systems.gameplay.dialogue import constants as dialogue_const
from systems.gameplay.dialogue import stub
from systems.gameplay.dialogue.vocabulary import vocabulary


_STALE_HINT = (
    "The editor stub is out of date. Run from blackout/: "
    "python -m systems.gameplay.dialogue --write-stub")


class StubFileTests(EvenniaTestCase):
    """The stub file in git, against a fresh render."""

    def test_the_stub_file_is_current(self):
        with open(stub.stub_path(), encoding="utf-8", newline="") as handle:
            on_disk = handle.read().replace("\r\n", "\n")

        self.assertEqual(on_disk, stub.render_stub(), _STALE_HINT)

    def test_each_vocabulary_name_is_in_the_table_of_the_stub(self):
        rendered = stub.render_stub()

        for name in vocabulary():
            with self.subTest(name=name):
                self.assertIn(f'"{name}":', rendered)

    def test_an_action_only_records(self):
        rendered = stub.render_stub()

        for name, entry in vocabulary().items():
            if entry.kind != dialogue_const.KIND_ACTION:
                continue

            with self.subTest(name=name):
                self.assertIn(f'"{name}": "{stub.STUB_ACTION}"', rendered)

    def test_the_stub_indents_with_tabs(self):
        indented = [line for line in stub.render_stub().split("\n")
                    if line.startswith(" ")]

        self.assertEqual(indented, [])
