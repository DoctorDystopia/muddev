"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/20/2026
Description: Tests for world.maps.gridstate, the readability check behind
             scripts/map_sync.py's map_data repair.

             Run from blackout/:
                 ../evenv/Scripts/evennia.exe test --settings test_settings.py world

             The module touches no database and no grid, so plain
             unittest.TestCase is the right base class. Every case builds the
             value it checks, so nothing here depends on the state of the live
             grid -- which is the state that cannot be reproduced in a test
             anyway.
"""

import unittest

from evennia.utils.dbserialize import _SaverDict

from world.maps.gridstate import (
    describe_unreadable_map_data,
    map_data_is_readable,
)


# ─── Private constant definitions ────────────────────────────────────────────

# What Evennia hands back for a pickle it cannot resolve: the base64 text it
# was given. Shortened here -- the real one was 10,052 characters.
_UNRESOLVED_PICKLE = "gASVaB0AAAAAAAB9lCiMBW9hc2lzlH2UKIwGemNvb3Jk"


class MapDataReadableTest(unittest.TestCase):
    """What counts as readable map data."""

    def test_a_plain_dict_is_readable(self):
        """The shape add_maps writes."""
        self.assertTrue(map_data_is_readable({"oasis": {}}))

    def test_an_empty_dict_is_readable(self):
        """A grid with every map removed is not a broken grid."""
        self.assertTrue(map_data_is_readable({}))

    def test_none_is_readable(self):
        """A grid that never registered a map has nothing to repair."""
        self.assertTrue(map_data_is_readable(None))

    def test_a_saverdict_is_readable(self):
        """
        What a live grid actually returns. _SaverDict is a MutableMapping and
        NOT a dict subclass, so an isinstance(value, dict) check here would
        clear the map data of every healthy grid on every run.
        """
        saver = _SaverDict({"oasis": {}})

        self.assertTrue(map_data_is_readable(saver))

    def test_an_unresolved_pickle_string_is_not_readable(self):
        """The failure this module exists for."""
        self.assertFalse(map_data_is_readable(_UNRESOLVED_PICKLE))

    def test_other_non_mappings_are_not_readable(self):
        """
        The check asks for a mapping rather than refusing `str`, so a value of
        any other wrong type is caught too.
        """
        for value in ("", 0, [], ("oasis",), object()):
            with self.subTest(value=repr(value)):
                self.assertFalse(map_data_is_readable(value))


class UnreadableDescriptionTest(unittest.TestCase):
    """What the operator reads when the row is cleared."""

    def test_the_report_names_the_cause(self):
        """
        A renamed legend class is what the operator has to act on. The
        traceback they got named neither the class nor the map.
        """
        text = describe_unreadable_map_data(_UNRESOLVED_PICKLE)

        self.assertIn("renamed", text.lower())

    def test_the_report_gives_the_type_and_the_size(self):
        """Both tell a reader the row held real data rather than a stray."""
        text = describe_unreadable_map_data(_UNRESOLVED_PICKLE)

        self.assertIn("str", text)
        self.assertIn(str(len(_UNRESOLVED_PICKLE)), text)

    def test_a_dry_run_promises_nothing(self):
        """
        A dry run changes nothing, so its report must not say it cleared the
        row. The live report must.
        """
        dry = describe_unreadable_map_data(_UNRESOLVED_PICKLE, dry_run=True)
        live = describe_unreadable_map_data(_UNRESOLVED_PICKLE)

        self.assertNotIn("Clearing it", dry)
        self.assertIn("Clearing it", live)

    def test_it_never_raises_on_an_odd_value(self):
        """
        It runs on a value whose type is already a surprise, so it must not be
        the thing that raises.
        """
        for value in (0, [], object()):
            with self.subTest(value=repr(value)):
                self.assertTrue(describe_unreadable_map_data(value))
