"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: Tests for the kill credit: the record of damage dealers, the
             XP shares, and notify_exterminator from a real death.

             Nick, 10/06/2026: each player who did damage gets the kill, and
             the XP (the max HP) is shared by damage. DESIGN-0012, Phase 2.
"""

import unittest

from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.combat import constants as combat_constants
from systems.gameplay.exterminator import constants as ext_const
from systems.gameplay.exterminator.hooks import _shares
from systems.gameplay.exterminator.preceptors import PRECEPTOR_ATTICUS_QUIN
from systems.gameplay.progression.skills import constants as skill_constants
from typeclasses.characters import Character as BlackoutCharacter
from world import creature_types
from world.npc_database import NPC_DB



# Private constant definitions

# The NPC with two types, from the vault note.
_MUTANT_CRAB_KEY: str = "mutant_crab"

_EXTERMINATOR: str = skill_constants.SKILL_KEY_EXTERMINATOR

_LETHAL_DAMAGE: int = 9999

# A hit too small to kill any fixture, and the HP of the fixture character.
_SMALL_HIT: int = 1
_FIXTURE_MAX_HP: int = 50

# A task larger than any test kills, so no test completes it by accident.
_LARGE_TOTAL: int = 1000



def _task(creature_type: str) -> dict:
    """A task dict for a fixture, written straight to the Attribute."""
    return {
        ext_const.FIELD_PRECEPTOR: PRECEPTOR_ATTICUS_QUIN,
        ext_const.FIELD_CREATURE_TYPE: creature_type,
        ext_const.FIELD_TOTAL: _LARGE_TOTAL,
        ext_const.FIELD_KILLS: 0,
        ext_const.FIELD_STARTED_AT: 0.0,
    }



class ShareTests(unittest.TestCase):
    """The XP of one kill, shared by damage, in integer math."""

    def test_a_sole_dealer_gets_all_of_it(self):
        self.assertEqual(_shares({1: 4}, 60), {1: 60})

    def test_shares_follow_damage_and_never_exceed_the_whole(self):
        shares = _shares({1: 30, 2: 10, 3: 20}, 60)

        self.assertEqual(shares, {1: 30, 2: 10, 3: 20})
        self.assertLessEqual(sum(shares.values()), 60)

    def test_a_rounded_share_is_never_more_than_the_exact_share(self):
        record = {1: 1, 2: 2}
        max_hp = 5

        for dealer, share in _shares(record, max_hp).items():
            with self.subTest(dealer=dealer):
                self.assertLessEqual(share, max_hp * record[dealer] / 3)



class KillCreditTests(EvenniaTest):
    """A real death of the Mutant Crab, with two damage dealers."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.crab = NPC_DB[_MUTANT_CRAB_KEY].create(location=self.room1)
        self.max_hp = self.crab.max_hp

        # Enough HP that a small hit does not kill the fixture character.
        self.char1.max_hp = _FIXTURE_MAX_HP
        self.char1.hp = _FIXTURE_MAX_HP

    def _kills(self, character) -> int:
        return character.exterminator.kills()

    def test_the_record_holds_each_dealer_and_its_damage(self):
        self.crab.at_damage(_SMALL_HIT, attacker=self.char1)
        self.crab.at_damage(_SMALL_HIT, attacker=self.char1)
        self.crab.at_damage(_SMALL_HIT, attacker=self.char2)

        record = self.crab.damage_record()

        self.assertEqual(record, {self.char1.id: 2 * _SMALL_HIT, self.char2.id: _SMALL_HIT})

    def test_a_self_hit_is_not_recorded(self):
        self.char1.at_damage(_SMALL_HIT, attacker=self.char1)

        self.assertEqual(self.char1.damage_record(), {})

    def test_every_dealer_gets_the_kill_on_a_task_of_either_type(self):
        self.char1.attributes.add(ext_const.TASK_ATTR, _task(creature_types.CREATURE_TYPE_MUTANT))
        self.char2.attributes.add(ext_const.TASK_ATTR, _task(creature_types.CREATURE_TYPE_CRAB))

        self.crab.at_damage(_SMALL_HIT, attacker=self.char2)
        self.crab.at_damage(_LETHAL_DAMAGE, attacker=self.char1)

        self.assertEqual(self._kills(self.char1), 1)
        self.assertEqual(self._kills(self.char2), 1)

    def test_the_xp_is_shared_by_damage(self):
        self.char1.attributes.add(ext_const.TASK_ATTR, _task(creature_types.CREATURE_TYPE_CRAB))
        self.char2.attributes.add(ext_const.TASK_ATTR, _task(creature_types.CREATURE_TYPE_CRAB))
        xp_one = self.char1.skills.get_total_xp(_EXTERMINATOR)
        xp_two = self.char2.skills.get_total_xp(_EXTERMINATOR)

        self.crab.at_damage(_SMALL_HIT, attacker=self.char2)
        self.crab.at_damage(_LETHAL_DAMAGE, attacker=self.char1)

        record = {self.char1.id: self.max_hp - _SMALL_HIT, self.char2.id: _SMALL_HIT}
        shares = _shares(record, self.max_hp)
        self.assertEqual(self.char1.skills.get_total_xp(_EXTERMINATOR), xp_one + shares[self.char1.id])
        self.assertEqual(self.char2.skills.get_total_xp(_EXTERMINATOR), xp_two + shares[self.char2.id])

    def test_a_bystander_with_a_task_gets_nothing(self):
        self.char2.attributes.add(ext_const.TASK_ATTR, _task(creature_types.CREATURE_TYPE_CRAB))

        self.crab.at_damage(_LETHAL_DAMAGE, attacker=self.char1)

        self.assertEqual(self._kills(self.char2), 0)

    def test_a_task_of_another_type_does_not_count(self):
        self.char1.attributes.add(ext_const.TASK_ATTR, _task(creature_types.CREATURE_TYPE_EYE))

        self.crab.at_damage(_LETHAL_DAMAGE, attacker=self.char1)

        self.assertEqual(self._kills(self.char1), 0)

    def test_a_death_clears_the_record(self):
        self.char1.at_damage(_SMALL_HIT, attacker=self.char2)
        self.assertTrue(self.char1.damage_record())

        self.char1.at_damage(_LETHAL_DAMAGE, attacker=self.char2)

        self.assertIsNone(getattr(self.char1.ndb, combat_constants.DAMAGE_RECORD_ATTR, None))
