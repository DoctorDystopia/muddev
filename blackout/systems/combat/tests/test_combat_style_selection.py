"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Tests for the combat-options menu's backing API — picking which
             combat style is active on the wielded weapon.

Run with the Evennia/Django test runner from the game dir:

    evennia test --settings settings.py systems.combat
"""

from evennia.utils.test_resources import EvenniaTest

from systems.combat.combat import (
    active_combat_style_key,
    available_combat_styles,
    ensure_combat_handler,
    set_combat_style,
)
from world.item_database import ITEM_DB


class TestAvailableCombatStyles(EvenniaTest):
    """Reading a weapon's style table and its currently active key."""

    def _equip_shortsword(self):
        item = ITEM_DB["rusty_scrap_shortsword"].create(location=self.char1)
        self.char1.equipment.equip(item)
        return item

    def test_available_styles_are_exactly_the_itemdefs_styles(self):
        """The reader surfaces the definition's table, whatever is in it.

        Asserting a literal style set instead couples this test to one
        weapon's design data: adding a fifth shortsword style would fail a
        test about the reader, not about the styles.
        """
        item_def = ITEM_DB["rusty_scrap_shortsword"]
        weapon = self._equip_shortsword()

        styles = available_combat_styles(weapon)

        self.assertTrue(item_def.combat_styles, "fixture weapon declares no styles")
        self.assertEqual(set(styles), set(item_def.combat_styles))

    def test_active_style_key_is_the_itemdefs_declared_default(self):
        item_def = ITEM_DB["rusty_scrap_shortsword"]
        weapon = self._equip_shortsword()

        self.assertEqual(
            active_combat_style_key(weapon), item_def.default_combat_style
        )

    def test_active_style_key_falls_back_when_default_is_unset(self):
        """An unset default_combat_style still resolves to *some* valid key
        rather than None, mirroring _resolve_style_and_speed's fallback."""
        weapon = self._equip_shortsword()
        weapon.db.default_combat_style = None

        self.assertIn(active_combat_style_key(weapon), available_combat_styles(weapon))

    def test_no_styles_returns_none(self):
        item = ITEM_DB["glass_cannon_amulet"].create(location=self.char1)

        self.assertIsNone(active_combat_style_key(item))
        self.assertEqual(available_combat_styles(item), {})


class TestSetCombatStyle(EvenniaTest):
    """Writing a new active style, with and without a live combat handler."""

    def _equip_shortsword(self):
        item = ITEM_DB["rusty_scrap_shortsword"].create(location=self.char1)
        self.char1.equipment.equip(item)
        return item

    def test_valid_style_key_updates_the_weapon_and_returns_true(self):
        weapon = self._equip_shortsword()

        result = set_combat_style(weapon, "guard")

        self.assertTrue(result)
        self.assertEqual(weapon.db.default_combat_style, "guard")

    def test_invalid_style_key_is_rejected_and_leaves_style_unchanged(self):
        weapon = self._equip_shortsword()

        result = set_combat_style(weapon, "not-a-real-style")

        self.assertFalse(result)
        self.assertEqual(weapon.db.default_combat_style, "irimi")

    def test_switching_mid_combat_refreshes_the_cached_active_style(self):
        """Regression target: without a refresh, a mid-fight style switch
        would silently keep swinging with the old style until the next wield
        or combat entry."""
        weapon = self._equip_shortsword()
        handler = ensure_combat_handler(self.char1)

        self.assertEqual(
            handler.ndb.active_weapon_data["active_combat_style"]["weapon_style"],
            "accurate",  # irimi
        )

        set_combat_style(weapon, "guard", combatant=self.char1)

        self.assertEqual(
            handler.ndb.active_weapon_data["active_combat_style"]["weapon_style"],
            "defensive",  # guard
        )

    def test_switching_out_of_combat_does_not_require_a_handler(self):
        weapon = self._equip_shortsword()

        result = set_combat_style(weapon, "slash", combatant=self.char1)

        self.assertTrue(result)
        self.assertEqual(weapon.db.default_combat_style, "slash")
