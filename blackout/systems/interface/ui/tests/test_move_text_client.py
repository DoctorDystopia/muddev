"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/22/2026
Description: Every part that the Godot Options pane names must be a part
             that `movetext` knows.

             The pane holds MOVE_TEXT_LABELS: a server key and a client label
             for each row. Its On and Off buttons send `movetext <key> on`. A
             key that names no part gives a button that only ever prints the
             usage. The reverse is not checked: a part with no row is fine,
             because the player can still type the command.

             Plain TestCase. It reads a file and a Python table.
"""

import os
import re
import unittest

from systems.interface.ui import move_text

# The game dir (blackout/), which holds systems/interface/ui/tests/.
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

_OPTIONS_VIEW = os.path.join(
    os.path.dirname(_GAME_DIR), "godot", "scenes", "options", "options_view.gd")

_TABLE_RE = re.compile(
    r"MOVE_TEXT_LABELS\s*:?=\s*\{(.*?)^\}", re.DOTALL | re.MULTILINE)
_TABLE_KEY_RE = re.compile(r'"([^"]+)"\s*:')
_COMMENT_RE = re.compile(r"#.*$", re.MULTILINE)


def _client_part_keys():
    """Give the keys of MOVE_TEXT_LABELS, or None when there is no table."""
    if not os.path.isfile(_OPTIONS_VIEW):
        return None

    with open(_OPTIONS_VIEW, "r", encoding="utf-8") as handle:
        source = _COMMENT_RE.sub("", handle.read())

    match = _TABLE_RE.search(source)

    if not match:
        return None

    return _TABLE_KEY_RE.findall(match.group(1))


class MoveTextClientTests(unittest.TestCase):
    """The Options pane names only parts that exist."""

    def test_the_pane_declares_the_table(self):
        """The guard below skips a file with no table. This makes a renamed
        table fail, not pass while it checks nothing."""
        if not os.path.isfile(_OPTIONS_VIEW):
            self.skipTest("no Godot client in this checkout")

        self.assertTrue(_client_part_keys())

    def test_no_row_names_a_part_that_does_not_exist(self):
        keys = _client_part_keys() or []

        for key in keys:
            with self.subTest(key=key):
                self.assertIn(key, move_text.PART_KEYS)
