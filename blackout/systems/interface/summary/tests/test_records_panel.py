"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/13/2026
Description: Tests for the dossier's Records band and the `stats` sheet it
             also draws.

             Three decisions are guarded above the rest:

               1. IT NAMES NO STAT. Every stat in STAT_REGISTRY reaches all
                  three outputs, asserted over the registry rather than over a
                  list written here, so a new stat is covered on arrival.
               2. THE DOSSIER CAPS, THE SHEET AND THE TAB DO NOT. A long kill
                  list is summarised on the band and named in full elsewhere.
               3. THE BAND IS SILENT WHEN NOTHING IS RECORDED.

             A stand-in character carrying only `key`, `db` and a real
             StatHandler, because the panel reads nothing else.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.interface.summary.tests.test_records_panel
"""

import json
import unittest
from types import SimpleNamespace
from unittest import mock

from evennia.utils.ansi import strip_ansi

from systems.core.stat_tracker import constants as stat_constants
from systems.core.stat_tracker.handler import StatHandler
from systems.core.stat_tracker.registry import STAT_REGISTRY, StatKind
from systems.interface.summary import constants as const
from systems.interface.summary.panel_defs import records
from systems.interface.summary.panel_defs.records import RecordsPanel


# ─── Private constant definitions ────────────────────────────────────────────

_KEYED_KEY: str = stat_constants.KILLS_PER_HOSTILE_STAT_KEY
_COUNTER_KEY: str = stat_constants.CREDITS_SPENT_STAT_KEY
_SUB_KEY: str = "mutant_raider"
_SUB_KEY_LABEL: str = "Mutant Raider"


class _RecordsTest(unittest.TestCase):
    """A character with a real stats handler and nothing recorded yet."""

    def setUp(self):
        self.character = SimpleNamespace(key="Tester", db=SimpleNamespace(stats=None))
        self.character.stats = StatHandler(self.character)

        patcher = mock.patch.object(StatHandler, "_mark_dossier_stale")
        patcher.start()
        self.addCleanup(patcher.stop)

    def _band(self) -> str:
        return strip_ansi("\n".join(RecordsPanel.render(self.character)))

    def _sheet(self) -> str:
        return strip_ansi(RecordsPanel.sheet(self.character))

    def _record_many(self, count: int) -> list:
        """Kill `count` hostiles, the i-th one i+1 times. Returns the keys."""
        sub_keys = [f"hostile_{index}" for index in range(count)]

        for index, sub_key in enumerate(sub_keys):
            self.character.stats.increment(_KEYED_KEY, sub_key, amount=index + 1)

        return sub_keys


class TestTheBandKnowsWhenToBeQuiet(_RecordsTest):

    def test_nothing_recorded_draws_nothing(self):
        self.assertEqual(RecordsPanel.render(self.character), [])
        self.assertEqual(RecordsPanel.data(self.character), {})

    def test_the_sheet_says_so_rather_than_drawing_nothing(self):
        self.assertIn(records.EMPTY_SHEET_TEXT, self._sheet())

    def test_a_character_without_a_stats_handler_is_not_an_error(self):
        bare = SimpleNamespace(key="Chair")

        self.assertEqual(RecordsPanel.render(bare), [])
        self.assertEqual(RecordsPanel.data(bare), {})


class TestItNamesNoStat(_RecordsTest):

    def test_every_registered_stat_reaches_every_output(self):
        for stat_key in STAT_REGISTRY:
            self.character.stats.increment(stat_key, _SUB_KEY)

        band = self._band()
        sheet = self._sheet()
        payload = RecordsPanel.data(self.character)

        for stat_key, stat_def in STAT_REGISTRY.items():
            with self.subTest(stat=stat_key):
                self.assertIn(stat_def.label, band)
                self.assertIn(stat_def.name.upper(), sheet)
                self.assertIn(stat_key, payload)

    def test_every_label_fits_the_dossier_label_column(self):
        for stat_key, stat_def in STAT_REGISTRY.items():
            with self.subTest(stat=stat_key):
                self.assertLessEqual(len(stat_def.label), const.FIELD_LABEL_WIDTH)

    def test_payload_shape_follows_the_stat_kind(self):
        for stat_key in STAT_REGISTRY:
            self.character.stats.increment(stat_key, _SUB_KEY)

        payload = RecordsPanel.data(self.character)

        for stat_key, stat_def in STAT_REGISTRY.items():
            with self.subTest(stat=stat_key):
                is_keyed = stat_def.kind == StatKind.KEYED_COUNTER
                self.assertEqual(isinstance(payload[stat_key], dict), is_keyed)

    def test_sub_keys_are_humanised(self):
        self.character.stats.increment(_KEYED_KEY, _SUB_KEY)

        self.assertIn(_SUB_KEY_LABEL, self._band())
        self.assertIn(_SUB_KEY_LABEL, self._sheet())

    def test_payload_is_json_safe(self):
        self._record_many(3)
        self.character.stats.increment(_COUNTER_KEY, amount=900)

        encoded = json.dumps(RecordsPanel.data(self.character))

        self.assertIn(_KEYED_KEY, encoded)


class TestTheDossierCaps(_RecordsTest):

    def test_the_band_summarises_past_the_cap(self):
        extra = 2
        self._record_many(records.MAX_LISTED_ENTRIES + extra)

        expected = records.MORE_ENTRIES_TEMPLATE.format(count=extra)

        self.assertIn(expected, self._band())

    def test_the_sheet_and_the_payload_name_every_entry(self):
        sub_keys = self._record_many(records.MAX_LISTED_ENTRIES + 2)

        sheet = self._sheet().lower()
        payload = RecordsPanel.data(self.character)[_KEYED_KEY]

        for sub_key in sub_keys:
            with self.subTest(sub_key=sub_key):
                self.assertIn(sub_key.replace("_", " "), sheet)
                self.assertIn(sub_key, payload)

    def test_entries_are_ranked_highest_first(self):
        sub_keys = self._record_many(4)

        payload = RecordsPanel.data(self.character)[_KEYED_KEY]

        self.assertEqual(list(payload), list(reversed(sub_keys)))

    def test_the_sheet_totals_a_keyed_stat(self):
        self._record_many(4)
        grand_total = sum(self.character.stats.get(_KEYED_KEY).values())

        total_rows = [
            line for line in self._sheet().split("\n")
            if records.LABEL_TOTAL in line
        ]

        self.assertEqual(len(total_rows), 1)
        self.assertIn(str(grand_total), total_rows[0])

    def test_no_line_exceeds_the_screen_width(self):
        self._record_many(12)
        self.character.stats.increment(_COUNTER_KEY, amount=123456)

        for line in self._band().split("\n") + self._sheet().split("\n"):
            with self.subTest(line=line):
                self.assertLessEqual(len(line), const.SUMMARY_WIDTH)
