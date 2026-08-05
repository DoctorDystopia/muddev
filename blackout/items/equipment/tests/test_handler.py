"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Evennia-backed tests for EquipmentHandler.total_combat_stat_bonuses.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py items
"""

from evennia.utils.test_resources import EvenniaTest

from world.item_database import ITEM_DB


class TestTotalCombatStatBonuses(EvenniaTest):
    """The aggregate combat.combat_profile() reads to sum bonuses across
    every equipped slot, not just the wielded weapon."""

    def _equip(self, item_key: str, extra_bonuses: dict = None):
        item = ITEM_DB[item_key].create(location=self.char1)
        if extra_bonuses is not None:
            item.db.combat_stat_bonuses = extra_bonuses
        self.char1.equipment.equip(item)

        return item

    def test_nothing_equipped_returns_an_empty_dict(self):
        self.assertEqual(self.char1.equipment.total_combat_stat_bonuses(), {})

    def test_one_equipped_item_returns_its_own_bonuses(self):
        self._equip("rusty_scrap_shortsword")

        totals = self.char1.equipment.total_combat_stat_bonuses()

        self.assertEqual(totals["stab_attack_bonus"], 4)
        self.assertEqual(totals["melee_strength_bonus"], 5)

    def test_two_equipped_items_sum_the_same_key(self):
        self._equip("rusty_scrap_shortsword", {"slash_defense_bonus": 2})
        self._equip("glass_cannon_amulet", {"slash_defense_bonus": 10})

        totals = self.char1.equipment.total_combat_stat_bonuses()

        self.assertEqual(totals["slash_defense_bonus"], 12)

    def test_an_item_with_no_bonuses_attribute_is_skipped_not_zeroed(self):
        self._equip("rusty_scrap_shortsword", {"slash_defense_bonus": 2})
        self._equip("glass_cannon_amulet")  # no combat_stat_bonuses attribute

        totals = self.char1.equipment.total_combat_stat_bonuses()

        self.assertEqual(totals["slash_defense_bonus"], 2)

    def test_unequipping_an_item_removes_its_contribution(self):
        sword = self._equip("rusty_scrap_shortsword")
        self.char1.equipment.unequip(sword)

        self.assertEqual(self.char1.equipment.total_combat_stat_bonuses(), {})
