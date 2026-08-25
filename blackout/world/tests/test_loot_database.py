"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/14/2026
Description: Tests for LootTableDef.roll() and the LOOT_DB registry validator.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py world

Every roll case here uses a seeded random.Random or a scripted stub, so the
assertions are exact rather than statistical. roll() touches no database and
spawns nothing, which is what lets these run as plain unittest.TestCase with
no Evennia fixture at all.
"""

import random
import unittest

from world.loot_database import (
    LOOT_DB,
    LootEntry,
    LootTableDef,
    TertiaryDrop,
    validate_loot_tables,
)


# Private constant definitions

# A stand-in item key. The roll layer never resolves keys against ITEM_DB, so
# these need not be real items -- using an obviously fake one keeps that
# independence visible.
_FAKE_KEY = "test_widget"
_OTHER_KEY = "test_gizmo"

# Enough iterations that a weighted pool visits every branch, small enough to
# stay instant.
_SAMPLE_COUNT = 2000


class _ScriptedRandom:
    """A random.Random stand-in that returns a fixed sequence of randint values.

    Seeding a real Random pins the OUTPUT but not the meaning -- a test written
    against seed 0 says nothing about which branch it exercised, and silently
    changes meaning if the number of randint calls in roll() ever shifts. This
    stub instead states the roll values directly, so a case reads as "when the
    weighted pick lands on 41, the second entry is chosen".
    """

    def __init__(self, values):
        self._values = list(values)
        self.calls = 0

    def randint(self, low, high):
        """Return the next scripted value, asserting it is a legal result."""
        if not self._values:
            raise AssertionError("scripted random exhausted; roll() called "
                                 "randint more times than the test expected")

        value = self._values.pop(0)
        self.calls += 1

        if not low <= value <= high:
            raise AssertionError(f"scripted value {value} outside the "
                                 f"[{low}, {high}] range roll() asked for")

        return value


class TestAlwaysStage(unittest.TestCase):
    """The 100% slot drops on every kill, regardless of the rest of the table."""

    def test_always_entry_drops_with_no_main_pool(self):
        table = LootTableDef(
            key="t",
            always=[LootEntry(item_key=_FAKE_KEY)],
        )

        drops = table.roll(rng=_ScriptedRandom([]))

        self.assertEqual(drops, [(_FAKE_KEY, 1)])

    def test_always_entry_drops_even_when_main_rolls_nothing(self):
        table = LootTableDef(
            key="t",
            always=[LootEntry(item_key=_FAKE_KEY)],
            main=[LootEntry(item_key=_OTHER_KEY, weight=1)],
            nothing_weight=99,
        )

        # Total weight 100; a roll of 100 lands in the no-drop tail.
        drops = table.roll(rng=_ScriptedRandom([100]))

        self.assertEqual(drops, [(_FAKE_KEY, 1)])

    def test_always_entries_are_independent_of_each_other(self):
        table = LootTableDef(
            key="t",
            always=[
                LootEntry(item_key=_FAKE_KEY),
                LootEntry(item_key=_OTHER_KEY),
            ],
        )

        drops = table.roll(rng=_ScriptedRandom([]))

        self.assertEqual(drops, [(_FAKE_KEY, 1), (_OTHER_KEY, 1)])


class TestWeightedPick(unittest.TestCase):
    """Cumulative-cursor selection across the main pool."""

    def _two_entry_table(self):
        """A pool of 40 / 20 with a 40 no-drop tail. Total weight 100."""
        return LootTableDef(
            key="t",
            main=[
                LootEntry(item_key=_FAKE_KEY, weight=40),
                LootEntry(item_key=_OTHER_KEY, weight=20),
            ],
            nothing_weight=40,
        )

    def test_first_entry_claims_the_bottom_of_the_range(self):
        table = self._two_entry_table()

        low_edge = table.roll(rng=_ScriptedRandom([1]))
        high_edge = table.roll(rng=_ScriptedRandom([40]))

        self.assertEqual(low_edge, [(_FAKE_KEY, 1)])
        self.assertEqual(high_edge, [(_FAKE_KEY, 1)])

    def test_second_entry_claims_the_next_band(self):
        table = self._two_entry_table()

        low_edge = table.roll(rng=_ScriptedRandom([41]))
        high_edge = table.roll(rng=_ScriptedRandom([60]))

        self.assertEqual(low_edge, [(_OTHER_KEY, 1)])
        self.assertEqual(high_edge, [(_OTHER_KEY, 1)])

    def test_nothing_weight_claims_the_tail(self):
        table = self._two_entry_table()

        first_miss = table.roll(rng=_ScriptedRandom([61]))
        last_miss = table.roll(rng=_ScriptedRandom([100]))

        self.assertEqual(first_miss, [])
        self.assertEqual(last_miss, [])

    def test_observed_distribution_matches_declared_weights(self):
        """The whole point of integer weights: 40/20/40 must come out 40/20/40."""
        table = self._two_entry_table()
        rng = random.Random(20260814)
        counts = {_FAKE_KEY: 0, _OTHER_KEY: 0, None: 0}

        for _ in range(_SAMPLE_COUNT):
            drops = table.roll(rng=rng)

            if not drops:
                counts[None] += 1
            else:
                counts[drops[0][0]] += 1

        self.assertAlmostEqual(counts[_FAKE_KEY] / _SAMPLE_COUNT, 0.40,
                               delta=0.03)
        self.assertAlmostEqual(counts[_OTHER_KEY] / _SAMPLE_COUNT, 0.20,
                               delta=0.03)
        self.assertAlmostEqual(counts[None] / _SAMPLE_COUNT, 0.40, delta=0.03)

    def test_total_main_weight_includes_the_no_drop_share(self):
        table = self._two_entry_table()

        total = table.total_main_weight()

        self.assertEqual(total, 100)


class TestMultipleRolls(unittest.TestCase):
    """rolls > 1 draws independently, so the same entry can come up twice."""

    def _table(self, rolls):
        return LootTableDef(
            key="t",
            main=[LootEntry(item_key=_FAKE_KEY, weight=10)],
            rolls=rolls,
        )

    def test_two_rolls_can_yield_the_same_entry_twice(self):
        table = self._table(rolls=2)

        drops = table.roll(rng=_ScriptedRandom([1, 1]))

        self.assertEqual(drops, [(_FAKE_KEY, 1), (_FAKE_KEY, 1)])

    def test_each_roll_is_taken_against_the_same_pool(self):
        table = LootTableDef(
            key="t",
            main=[LootEntry(item_key=_FAKE_KEY, weight=1)],
            nothing_weight=9,
            rolls=3,
        )

        # Hit, miss, hit -- against a total weight of 10 each time.
        drops = table.roll(rng=_ScriptedRandom([1, 10, 1]))

        self.assertEqual(drops, [(_FAKE_KEY, 1), (_FAKE_KEY, 1)])

    def test_zero_rolls_takes_nothing_from_the_pool(self):
        table = self._table(rolls=0)

        drops = table.roll(rng=_ScriptedRandom([]))

        self.assertEqual(drops, [])


class TestTertiaryDrops(unittest.TestCase):
    """Independent 1/N slots that can land alongside a main-table drop."""

    def _table(self, denominator=128):
        return LootTableDef(
            key="t",
            main=[LootEntry(item_key=_FAKE_KEY, weight=10)],
            tertiary=[
                TertiaryDrop(entry=LootEntry(item_key=_OTHER_KEY),
                             chance_denominator=denominator),
            ],
        )

    def test_tertiary_fires_only_on_the_hit_value(self):
        table = self._table()

        # Main pick hits, tertiary rolls 1 -> both land.
        drops = table.roll(rng=_ScriptedRandom([1, 1]))

        self.assertEqual(drops, [(_FAKE_KEY, 1), (_OTHER_KEY, 1)])

    def test_tertiary_misses_on_any_other_value(self):
        table = self._table()

        drops = table.roll(rng=_ScriptedRandom([1, 2]))

        self.assertEqual(drops, [(_FAKE_KEY, 1)])

    def test_tertiary_can_fire_when_the_main_table_gave_nothing(self):
        table = LootTableDef(
            key="t",
            main=[LootEntry(item_key=_FAKE_KEY, weight=1)],
            nothing_weight=9,
            tertiary=[
                TertiaryDrop(entry=LootEntry(item_key=_OTHER_KEY),
                             chance_denominator=128),
            ],
        )

        drops = table.roll(rng=_ScriptedRandom([10, 1]))

        self.assertEqual(drops, [(_OTHER_KEY, 1)])

    def test_two_tertiary_slots_roll_independently(self):
        table = LootTableDef(
            key="t",
            tertiary=[
                TertiaryDrop(entry=LootEntry(item_key=_FAKE_KEY),
                             chance_denominator=128),
                TertiaryDrop(entry=LootEntry(item_key=_OTHER_KEY),
                             chance_denominator=64),
            ],
        )

        drops = table.roll(rng=_ScriptedRandom([1, 1]))

        self.assertEqual(drops, [(_FAKE_KEY, 1), (_OTHER_KEY, 1)])

    def test_observed_tertiary_rate_matches_the_denominator(self):
        table = LootTableDef(
            key="t",
            tertiary=[
                TertiaryDrop(entry=LootEntry(item_key=_FAKE_KEY),
                             chance_denominator=8),
            ],
        )
        rng = random.Random(20260814)
        hits = 0

        for _ in range(_SAMPLE_COUNT):
            drops = table.roll(rng=rng)
            hits += len(drops)

        self.assertAlmostEqual(hits / _SAMPLE_COUNT, 1 / 8, delta=0.03)


class TestQuantityBounds(unittest.TestCase):
    """Stack sizes stay inside the declared inclusive range."""

    def test_equal_bounds_take_no_roll_at_all(self):
        table = LootTableDef(
            key="t",
            always=[LootEntry(item_key=_FAKE_KEY, min_quantity=7,
                              max_quantity=7)],
        )
        rng = _ScriptedRandom([])

        drops = table.roll(rng=rng)

        self.assertEqual(drops, [(_FAKE_KEY, 7)])
        self.assertEqual(rng.calls, 0)

    def test_a_range_is_rolled_inclusively(self):
        table = LootTableDef(
            key="t",
            always=[LootEntry(item_key=_FAKE_KEY, min_quantity=5,
                              max_quantity=15)],
        )

        low = table.roll(rng=_ScriptedRandom([5]))
        high = table.roll(rng=_ScriptedRandom([15]))

        self.assertEqual(low, [(_FAKE_KEY, 5)])
        self.assertEqual(high, [(_FAKE_KEY, 15)])

    def test_inverted_bounds_fall_back_to_the_minimum(self):
        """A data typo must not let randint raise inside a death handler."""
        table = LootTableDef(
            key="t",
            always=[LootEntry(item_key=_FAKE_KEY, min_quantity=9,
                              max_quantity=2)],
        )

        drops = table.roll(rng=_ScriptedRandom([]))

        self.assertEqual(drops, [(_FAKE_KEY, 9)])

    def test_every_sampled_quantity_is_in_range(self):
        table = LootTableDef(
            key="t",
            always=[LootEntry(item_key=_FAKE_KEY, min_quantity=2,
                              max_quantity=6)],
        )
        rng = random.Random(20260814)

        for _ in range(_SAMPLE_COUNT):
            drops = table.roll(rng=rng)
            quantity = drops[0][1]

            self.assertGreaterEqual(quantity, 2)
            self.assertLessEqual(quantity, 6)


class TestDegenerateTables(unittest.TestCase):
    """Empty and unrollable tables return nothing instead of raising."""

    def test_a_wholly_empty_table_drops_nothing(self):
        table = LootTableDef(key="t")
        rng = _ScriptedRandom([])

        drops = table.roll(rng=rng)

        self.assertEqual(drops, [])
        self.assertEqual(rng.calls, 0)

    def test_a_zero_weight_pool_is_never_rolled(self):
        """Guards against randint(1, 0), which raises."""
        table = LootTableDef(
            key="t",
            main=[LootEntry(item_key=_FAKE_KEY, weight=0)],
        )
        rng = _ScriptedRandom([])

        drops = table.roll(rng=rng)

        self.assertEqual(drops, [])
        self.assertEqual(rng.calls, 0)

    def test_roll_without_an_rng_uses_the_module_random(self):
        """The rng argument is optional at every call site."""
        table = LootTableDef(
            key="t",
            always=[LootEntry(item_key=_FAKE_KEY)],
        )

        drops = table.roll()

        self.assertEqual(drops, [(_FAKE_KEY, 1)])


class TestRegistryValidation(unittest.TestCase):
    """The loud half of the loud-in-tests / soft-at-runtime split."""

    def test_shipped_tables_are_clean(self):
        """Every item_key in LOOT_DB must resolve against ITEM_DB."""
        problems = validate_loot_tables()

        self.assertEqual(problems, [])

    def test_registry_is_not_empty(self):
        """A def module left out of the merge loop contributes silently."""
        self.assertTrue(LOOT_DB)

    def test_every_table_self_reports_its_registry_key(self):
        for table_key, table in LOOT_DB.items():
            self.assertEqual(table.key, table_key)
