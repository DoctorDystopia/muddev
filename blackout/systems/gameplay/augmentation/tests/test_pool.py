"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The Grit pool (DESIGN-0015, Phase 1). The pool clamps to
             [0, max], a level change moves the maximum, and each write
             reaches the char_vitals channel with both numbers.
Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py systems.gameplay.augmentation
"""

from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.augmentation import constants as aug_const
from systems.gameplay.augmentation import pool
from systems.gameplay.progression.skills import logic
from systems.gameplay.progression.skills.constants import (
    SKILL_KEY_AUGMENTATION,
    SKILL_KEY_STRIKE,
)
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import events as feed_events
from typeclasses.characters import Character as BlackoutCharacter


# A level that is not the start level, so the floor and the level stay
# apart in each assertion.
_A_LEVEL = 12
_A_LOWER_LEVEL = 4
_A_SPEND = 5


class _PoolTest(EvenniaTest):
    """One character with the Augmentation skill at a known level."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.char1.skills.set_level(SKILL_KEY_AUGMENTATION, _A_LEVEL)
        pool.restore(self.char1)


class TestPoolBounds(_PoolTest):

    def test_a_new_character_starts_full(self):
        self.assertEqual(pool.current(self.char1), pool.maximum(self.char1))

    def test_the_maximum_is_the_floor_plus_the_level(self):
        level = self.char1.skills.get_level(SKILL_KEY_AUGMENTATION)

        self.assertEqual(pool.maximum(self.char1), aug_const.AUG_POOL_FLOOR + level)

    def test_a_spend_takes_the_amount(self):
        before = pool.current(self.char1)

        after = pool.spend(self.char1, _A_SPEND)

        self.assertEqual(after, before - _A_SPEND)
        self.assertEqual(pool.current(self.char1), after)

    def test_a_spend_clamps_at_empty(self):
        cap = pool.maximum(self.char1)

        after = pool.spend(self.char1, cap * 2)

        self.assertEqual(after, aug_const.GRIT_EMPTY)

    def test_a_restore_clamps_at_the_maximum(self):
        pool.spend(self.char1, _A_SPEND)

        after = pool.restore(self.char1, _A_SPEND * 3)

        self.assertEqual(after, pool.maximum(self.char1))

    def test_a_full_restore_fills_the_pool(self):
        pool.spend(self.char1, pool.maximum(self.char1))

        after = pool.restore(self.char1)

        self.assertEqual(after, pool.maximum(self.char1))

    def test_a_character_with_no_attribute_reads_full(self):
        """A character from before the pool existed never spent any."""
        self.char1.attributes.remove(aug_const.GRIT_ATTR)

        self.assertEqual(pool.current(self.char1), pool.maximum(self.char1))

    def test_a_read_never_writes(self):
        self.char1.attributes.remove(aug_const.GRIT_ATTR)

        pool.current(self.char1)

        self.assertFalse(self.char1.attributes.has(aug_const.GRIT_ATTR))


class TestPoolFollowsTheLevel(_PoolTest):

    def test_a_level_up_moves_the_maximum(self):
        before_level = self.char1.skills.get_level(SKILL_KEY_AUGMENTATION)
        before_cap = pool.maximum(self.char1)
        needed = logic.calculate_xp_needed(before_level)

        self.char1.skills.add_xp(SKILL_KEY_AUGMENTATION, needed * 2)

        after_level = self.char1.skills.get_level(SKILL_KEY_AUGMENTATION)
        self.assertGreater(after_level, before_level)
        self.assertGreater(pool.maximum(self.char1), before_cap)
        self.assertEqual(pool.maximum(self.char1), aug_const.AUG_POOL_FLOOR + after_level)

    def test_a_raised_maximum_does_not_fill_the_pool(self):
        pool.spend(self.char1, _A_SPEND)
        held = pool.current(self.char1)

        self.char1.skills.set_level(SKILL_KEY_AUGMENTATION, _A_LEVEL * 2)

        self.assertEqual(pool.current(self.char1), held)

    def test_a_lowered_maximum_cuts_the_pool(self):
        self.char1.skills.set_level(SKILL_KEY_AUGMENTATION, _A_LOWER_LEVEL)

        self.assertEqual(pool.current(self.char1), pool.maximum(self.char1))
        self.assertEqual(pool.maximum(self.char1),
                         aug_const.AUG_POOL_FLOOR + _A_LOWER_LEVEL)

    def test_another_skill_does_not_touch_the_pool(self):
        pool.spend(self.char1, _A_SPEND)
        held = pool.current(self.char1)
        cap = pool.maximum(self.char1)
        needed = logic.calculate_xp_needed(0)

        self.char1.skills.add_xp(SKILL_KEY_STRIKE, needed * 3)

        self.assertEqual(pool.current(self.char1), held)
        self.assertEqual(pool.maximum(self.char1), cap)


class TestPoolReachesTheFeed(_PoolTest):
    """Each write hands a char_vitals payload with both numbers to the feed.

    Patches `events.emit`, as test_fortitude_hp.py does. Whether a payload
    then reaches a socket is the contract of emit.py.
    """

    def setUp(self):
        super().setUp()
        self.published = []

        patcher = mock.patch.object(feed_events, "emit", side_effect=self._record)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _record(self, obj, payload, force=False):
        if payload.channel == feed_const.CHANNEL_CHAR_VITALS:
            self.published.append((payload.to_dict(), force))

        return 0

    def test_a_spend_publishes_the_pool(self):
        after = pool.spend(self.char1, _A_SPEND)

        body, _force = self.published[-1]
        self.assertEqual(body["grit"], after)
        self.assertEqual(body["max_grit"], pool.maximum(self.char1))

    def test_a_restore_is_sent_past_the_rate_cap(self):
        pool.spend(self.char1, _A_SPEND)

        pool.restore(self.char1)

        _body, force = self.published[-1]
        self.assertTrue(force)

    def test_a_level_change_is_sent_past_the_rate_cap(self):
        self.char1.skills.set_level(SKILL_KEY_AUGMENTATION, _A_LOWER_LEVEL)

        body, force = self.published[-1]
        self.assertTrue(force)
        self.assertEqual(body["max_grit"], pool.maximum(self.char1))

    def test_the_vitals_payload_carries_hp_beside_grit(self):
        feed_events.emit_vitals(self.char1)

        body, _force = self.published[-1]
        self.assertEqual(body["hp"], self.char1.hp)
        self.assertEqual(body["max_hp"], self.char1.max_hp)
        self.assertEqual(body["grit"], pool.current(self.char1))
        self.assertEqual(body["max_grit"], pool.maximum(self.char1))
