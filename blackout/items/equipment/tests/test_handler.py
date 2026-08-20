"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Evennia-backed tests for EquipmentHandler.total_combat_stat_bonuses.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py items
"""

from evennia.utils.test_resources import EvenniaTest

from typeclasses.characters import Character as BlackoutCharacter
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


class TestSlotConflicts(EvenniaTest):
    """The two-hand displacement rule, which used to be written twice.

    The two copies disagreed: the one that decided WHAT was displaced left the
    two-hand slot out of its own conflict list, so equipping a two-hander over
    a two-hander orphaned the old one -- its location was already None and
    nothing put it back. One table feeds both steps now.
    """

    character_typeclass = BlackoutCharacter

    def _make(self, key, use_slot):
        """An equippable carrying an explicit slot.

        EquippableItem, not BaseItem: inventory_use_slot is defined on the
        former, and a BaseItem simply has no such attribute, so equip refuses
        it before any slot logic runs.
        """
        from evennia import create_object
        from typeclasses.items import EquippableItem

        item = create_object(EquippableItem, key=key, location=self.char1)
        item.attributes.add("use_slot", use_slot)

        self.assertEqual(item.inventory_use_slot, use_slot)

        return item

    def test_a_two_hander_displaces_both_hands(self):
        from items.equipment.constants import WieldLocation

        main = self._make("blade", WieldLocation.MAIN_HAND)
        off = self._make("buckler", WieldLocation.OFF_HAND)
        self.char1.equipment.equip(main)
        self.char1.equipment.equip(off)

        two_hander = self._make("greatblade", WieldLocation.TWO_HANDS)
        self.char1.equipment.equip(two_hander)

        self.assertIsNone(self.char1.equipment.slots[WieldLocation.MAIN_HAND])
        self.assertIsNone(self.char1.equipment.slots[WieldLocation.OFF_HAND])
        self.assertIn(main, self.char1.contents)
        self.assertIn(off, self.char1.contents)

    def test_a_two_hander_over_a_two_hander_returns_the_old_one(self):
        """The latent item-loss bug the duplicated rule hid. No two-handed
        item exists in ITEM_DB yet, which is the only reason it never fired."""
        from items.equipment.constants import WieldLocation

        first = self._make("greatblade", WieldLocation.TWO_HANDS)
        second = self._make("greataxe", WieldLocation.TWO_HANDS)
        self.char1.equipment.equip(first)

        self.char1.equipment.equip(second)

        self.assertEqual(
            self.char1.equipment.slots[WieldLocation.TWO_HANDS], second
        )
        self.assertIn(first, self.char1.contents)

    def test_a_main_hand_displaces_a_two_hander(self):
        from items.equipment.constants import WieldLocation

        two_hander = self._make("greatblade", WieldLocation.TWO_HANDS)
        self.char1.equipment.equip(two_hander)

        blade = self._make("blade", WieldLocation.MAIN_HAND)
        self.char1.equipment.equip(blade)

        self.assertIsNone(self.char1.equipment.slots[WieldLocation.TWO_HANDS])
        self.assertIn(two_hander, self.char1.contents)

    def test_a_main_hand_over_a_main_hand_returns_the_old_one(self):
        from items.equipment.constants import WieldLocation

        first = self._make("blade", WieldLocation.MAIN_HAND)
        second = self._make("shiv", WieldLocation.MAIN_HAND)
        self.char1.equipment.equip(first)

        self.char1.equipment.equip(second)

        self.assertEqual(
            self.char1.equipment.slots[WieldLocation.MAIN_HAND], second
        )
        self.assertIn(first, self.char1.contents)

    def test_an_unrelated_slot_displaces_nothing_else(self):
        from items.equipment.constants import WieldLocation

        blade = self._make("blade", WieldLocation.MAIN_HAND)
        self.char1.equipment.equip(blade)

        helm = self._make("helm", WieldLocation.HEAD)
        self.char1.equipment.equip(helm)

        self.assertEqual(
            self.char1.equipment.slots[WieldLocation.MAIN_HAND], blade
        )
        self.assertEqual(self.char1.equipment.slots[WieldLocation.HEAD], helm)
