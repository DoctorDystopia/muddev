"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/13/2026
Description: Cases for StatHandler: the two storage shapes, the recorded()
             read the Records band and `stats` sheet share, and the dossier
             mark every write leaves behind.

             Runs against a stand-in object carrying only `db`, because the
             handler touches nothing else -- no database, no Character.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.core.stat_tracker.tests
"""

import unittest
from types import SimpleNamespace
from unittest import mock

from systems.core.stat_tracker import constants as stat_constants
from systems.core.stat_tracker.handler import StatHandler
from systems.core.stat_tracker.registry import STAT_REGISTRY


# ─── Private constant definitions ────────────────────────────────────────────

_COUNTER_KEY: str = stat_constants.CREDITS_SPENT_STAT_KEY
_KEYED_KEY: str = stat_constants.KILLS_PER_HOSTILE_STAT_KEY
_SUB_KEY: str = "mutant_raider"
_OTHER_SUB_KEY: str = "floating_eye"


class _HandlerTest(unittest.TestCase):
    """A fresh handler on a stand-in object, with the feed mark tapped."""

    def setUp(self):
        self.obj = SimpleNamespace(db=SimpleNamespace(stats=None))
        self.handler = StatHandler(self.obj)

        patcher = mock.patch("systems.interface.statefeed.events.refresh_summary")
        self.refresh = patcher.start()
        self.addCleanup(patcher.stop)


class TestStorage(_HandlerTest):

    def test_a_counter_accumulates(self):
        self.handler.increment(_COUNTER_KEY, amount=40)
        self.handler.increment(_COUNTER_KEY, amount=2)

        self.assertEqual(self.handler.get(_COUNTER_KEY), 42)

    def test_a_keyed_counter_accumulates_per_sub_key(self):
        self.handler.increment(_KEYED_KEY, _SUB_KEY)
        self.handler.increment(_KEYED_KEY, _SUB_KEY)
        self.handler.increment(_KEYED_KEY, _OTHER_SUB_KEY)

        self.assertEqual(self.handler.get(_KEYED_KEY, _SUB_KEY), 2)
        self.assertEqual(self.handler.get(_KEYED_KEY), {_SUB_KEY: 2, _OTHER_SUB_KEY: 1})

    def test_every_registered_stat_accepts_a_write(self):
        for stat_key in STAT_REGISTRY:
            with self.subTest(stat=stat_key):
                self.handler.increment(stat_key, _SUB_KEY)

                self.assertTrue(self.handler.get(stat_key))


class TestRecorded(_HandlerTest):

    def test_nothing_recorded_is_an_empty_list(self):
        self.assertEqual(self.handler.recorded(), [])

    def test_only_stats_with_a_record_are_listed(self):
        self.handler.increment(_KEYED_KEY, _SUB_KEY)

        keys = [stat_def.key for stat_def, _value in self.handler.recorded()]

        self.assertEqual(keys, [_KEYED_KEY])

    def test_order_follows_the_registry_not_the_write_order(self):
        for stat_key in reversed(list(STAT_REGISTRY)):
            self.handler.increment(stat_key, _SUB_KEY)

        keys = [stat_def.key for stat_def, _value in self.handler.recorded()]

        self.assertEqual(keys, list(STAT_REGISTRY))

    def test_a_row_the_registry_cannot_describe_is_not_listed(self):
        self.obj.db.stats["retired_stat"] = 7

        self.assertEqual(self.handler.recorded(), [])


class TestDossierMark(_HandlerTest):
    """The Records band follows a tally because the writer marks it."""

    def test_an_increment_marks_the_dossier(self):
        self.handler.increment(_KEYED_KEY, _SUB_KEY)

        self.refresh.assert_called_once_with(self.obj)

    def test_a_refused_write_marks_nothing(self):
        with self.assertRaises(TypeError):
            self.handler.increment(_COUNTER_KEY, amount=1.5)

        self.refresh.assert_not_called()

    def test_a_reset_marks_the_dossier(self):
        self.handler._hard_reset()

        self.refresh.assert_called_once_with(self.obj)
