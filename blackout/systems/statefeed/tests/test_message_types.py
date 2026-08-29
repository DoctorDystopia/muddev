"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/28/2026
Description: Drift guards for the text-routing vocabulary.

             `MESSAGE_TYPES` in systems/statefeed/constants.py says what a line
             of game text may claim to be. A client reads the generated copy of
             that set and files each line under a tab. Two things can go wrong
             and neither raises at runtime:

               - A call site names a tag the vocabulary does not hold. The line
                 still reaches the player -- kwargs are opaque to Evennia -- but
                 it lands in the client's fallback tab forever, and the only
                 symptom is "my combat log is missing some lines".
               - A constant is added to constants.py and left out of
                 MESSAGE_TYPES. It then never reaches a client at all, because
                 the generated derived set is what a tab may name.

             THE ASYMMETRY, the same one test_client_constants.py states for
             the room-kind tables:

               - A tag a call site NAMES and the vocabulary does not declare is
                 a bug.
               - A tag the vocabulary declares and nothing sends is FINE. Half
                 of them are Evennia's own -- `say`, `look`, `help` -- declared
                 so a client tab can name them, and this game will never write
                 one.

             Reads the game source as TEXT and never imports it. That is not
             laziness: CLAUDE.md marks blackout/scripts/ import-unsafe because
             importing a module there once deleted 347 grid rooms, and a guard
             that has to exclude a directory to stay safe is one that stops
             guarding it. Reading is safe everywhere.
"""

import os
import re
import unittest

from .. import constants as const


# ─── Private constant definitions ────────────────────────────────────────────

# The game dir (blackout/), four levels up from
# systems/statefeed/tests/test_message_types.py.
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

# Directories under the game dir that hold no Python worth scanning. `web` is
# excluded because the generated JavaScript spells the same facts with a
# different prefix and would be read as a Python source file.
_SKIP_DIRS = frozenset(("__pycache__", "web", "migrations"))

# `_MSG_COMBAT = {` -- a module binding its own routing tag once, which is the
# shape every tagged module in the game uses.
_MODULE_TAG = re.compile(r"^_MSG_([A-Z_]+) = \{", re.MULTILINE)

# `feed_const.MESSAGE_TYPE_COMBAT`, `const.MESSAGE_TYPE_MAP`, and the bare form
# used inside statefeed itself.
_CONSTANT_REFERENCE = re.compile(r"\bMESSAGE_TYPE_([A-Z_]+)\b")

# A raw `"type": "combat"` literal. There should be NONE left in the game --
# every call site names a constant -- so this is a tripwire for the next one
# typed rather than a check with work to do today. See
# test_a_raw_type_literal_names_a_real_tag on why it is kept anyway.
_RAW_LITERAL = re.compile(r'"type"\s*:\s*"([a-z_]+)"')

# Names in constants.py that begin MESSAGE_TYPE_ but are not tags.
_NOT_A_TAG = frozenset(("MESSAGE_TYPE_KEY",))


def _tag_constants() -> dict:
    """
    Purpose: Every MESSAGE_TYPE_* constant, by name.

    Entry:
        None.

    Exit/Returns:
        {name: value} for every tag constant in constants.py.

    Module Globals:
        _NOT_A_TAG read; const inspected.

    Methodology:
        Read off the module namespace rather than listed here, so adding a tag
        needs no edit in this file. That is the difference between a
        relationship and a census.

    Notes/References:
        None
    """
    found = {}

    for name in dir(const):
        if not name.startswith("MESSAGE_TYPE_"):
            continue

        if name in _NOT_A_TAG:
            continue

        found[name] = getattr(const, name)

    return found


def _game_sources() -> list:
    """
    Purpose: Every Python file in the game dir, as (relative path, text).

    Entry:
        None.

    Exit/Returns:
        A list of (path, source) pairs. Never imports anything.

    Module Globals:
        _GAME_DIR, _SKIP_DIRS read.

    Methodology:
        Walk and read. Undecodable files are skipped rather than failed: this
        guard is about what the source SAYS, and a file it cannot read is one
        it cannot make a claim about either way.

    Notes/References:
        Reading rather than importing is what makes it safe to include
        blackout/scripts/; see the module docstring.
    """
    found = []

    for root, dirs, files in os.walk(_GAME_DIR):
        dirs[:] = [name for name in dirs if name not in _SKIP_DIRS]

        for name in files:
            if not name.endswith(".py"):
                continue

            path = os.path.join(root, name)

            try:
                with open(path, encoding="utf-8") as handle:
                    found.append((os.path.relpath(path, _GAME_DIR),
                                  handle.read()))
            except (OSError, UnicodeDecodeError):
                continue

    return found


# ─── Test cases ──────────────────────────────────────────────────────────────

class MessageTypeVocabularyTests(unittest.TestCase):
    """The vocabulary agrees with itself."""

    def test_every_tag_constant_is_in_the_set(self):
        """A constant left out of MESSAGE_TYPES never reaches a client."""
        constants = _tag_constants()

        self.assertTrue(constants, "no MESSAGE_TYPE_* constants were found")

        for name, value in sorted(constants.items()):
            with self.subTest(constant=name):
                self.assertIn(
                    value, const.MESSAGE_TYPES,
                    "%s = %r is not in MESSAGE_TYPES, so no client is told "
                    "about it and no tab may name it." % (name, value))

    def test_every_tag_in_the_set_has_a_constant(self):
        """A member with no constant is a value nothing can name."""
        named = set(_tag_constants().values())

        for value in sorted(const.MESSAGE_TYPES):
            with self.subTest(tag=value):
                self.assertIn(
                    value, named,
                    "%r is in MESSAGE_TYPES but no MESSAGE_TYPE_* constant "
                    "holds it, so every call site would have to type the "
                    "string." % value)

    def test_tags_are_lowercase_machine_tokens(self):
        """The wire form, not a display name.

        `Combat` and `combat` are two tabs to a client that compares strings,
        and nothing on the wire would say which was meant.
        """
        for value in sorted(const.MESSAGE_TYPES):
            with self.subTest(tag=value):
                self.assertEqual(value, value.lower(), "not lowercase")
                self.assertTrue(value.isidentifier(),
                                "not a machine token: %r" % value)


class GameSourceTests(unittest.TestCase):
    """The game names only tags that exist."""

    @classmethod
    def setUpClass(cls):
        cls.sources = _game_sources()
        cls.constants = _tag_constants()

    def test_the_scan_found_the_game(self):
        """A scan that reads nothing is a guard that has stopped guarding.

        The three checks below all pass trivially against an empty file list,
        which is exactly how test_client_constants.py describes its own vacuity
        trap. This is the floor under them.
        """
        self.assertGreater(
            len(self.sources), 100,
            "only %d Python files were found under %s; the scan is not "
            "reading the game." % (len(self.sources), _GAME_DIR))

        tagged = [path for path, source in self.sources
                  if _MODULE_TAG.search(source)]

        self.assertGreater(
            len(tagged), 20,
            "only %d modules bind a _MSG_* routing tag; either the tagging "
            "pass was reverted or this scan no longer sees it." % len(tagged))

    def test_every_module_tag_names_a_real_constant(self):
        """`_MSG_TELL = {...}` after a rename is silent until a tab is empty."""
        for path, source in self.sources:
            for suffix in _MODULE_TAG.findall(source):
                with self.subTest(path=path, tag="_MSG_" + suffix):
                    self.assertIn(
                        "MESSAGE_TYPE_" + suffix, self.constants,
                        "%s binds _MSG_%s, but constants.py declares no "
                        "MESSAGE_TYPE_%s." % (path, suffix, suffix))

    def test_every_constant_reference_names_a_real_constant(self):
        """Catches a rename that missed a call site.

        Python would raise AttributeError here at runtime -- but only on the
        line that sends the message, which may be a command nobody runs in a
        test. This finds it without running anything.
        """
        for path, source in self.sources:
            if path.startswith("systems%sstatefeed" % os.sep):
                # constants.py declares them and this file names them in prose;
                # neither is a call site.
                continue

            for suffix in set(_CONSTANT_REFERENCE.findall(source)):
                name = "MESSAGE_TYPE_" + suffix

                if name in _NOT_A_TAG:
                    continue

                with self.subTest(path=path, name=name):
                    self.assertIn(
                        name, self.constants,
                        "%s names %s, which constants.py does not declare."
                        % (path, name))

    def test_a_raw_type_literal_names_a_real_tag(self):
        """A hand-typed tag is the failure this whole vocabulary exists to stop.

        There are none in the game today -- the tagging pass replaced every one
        with a constant -- so this has nothing to check until somebody types the
        next one, which is the point. It is a tripwire, and
        test_the_scan_found_the_game is what stops the tripwire from being
        vacuous for the wrong reason.

        Evennia's own tags are not covered and must not be: `look` and `say` are
        the engine's to spell, this game does not write them, and asserting
        against the installed engine's source would fail on an upgrade that
        renamed one -- which is a thing to find out about, not a test to fail on.
        """
        for path, source in self.sources:
            if path.startswith("systems%sstatefeed" % os.sep):
                continue

            for value in set(_RAW_LITERAL.findall(source)):
                with self.subTest(path=path, tag=value):
                    self.assertIn(
                        value, const.MESSAGE_TYPES,
                        "%s writes the literal \"type\": %r, which is not in "
                        "MESSAGE_TYPES. Name the constant instead."
                        % (path, value))
