"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Tests for the action rules introspection report.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.combat
"""

from evennia.utils.ansi import strip_ansi
from evennia.utils.test_resources import EvenniaTest

from systems.combat.rules.introspect import (
    describe_registry,
    describe_action_rules,
)
from systems.combat.rules.registry import RULES_REGISTRY
from typeclasses.characters import Character as BlackoutCharacter
from world.item_database import ITEM_DB


class TestDescribeRegistry(EvenniaTest):
    """The catalogue view."""

    def test_every_registered_rule_is_listed(self):
        report = strip_ansi(describe_registry())

        for rules in RULES_REGISTRY.values():
            self.assertIn(rules.key, report)

    def test_each_entry_names_the_seams_it_overrides(self):
        report = strip_ansi(describe_registry())

        self.assertIn("overrides: resolve", report)
        self.assertIn("overrides: roll_damage", report)


class TestDescribeActionRules(EvenniaTest):
    """The per-combatant view — the actual debugging surface."""

    character_typeclass = BlackoutCharacter

    def _equip(self, item_key: str):
        item = ITEM_DB[item_key].create(location=self.char1)
        self.char1.equipment.equip(item)

        return item

    def test_bare_hands_report_no_contributors(self):
        report = strip_ansi(describe_action_rules(self.char1))

        self.assertIn("none", report)

    def test_bare_hands_report_every_seam_as_default(self):
        report = strip_ansi(describe_action_rules(self.char1))

        self.assertIn("roll_damage", report)
        self.assertNotIn("toy_sword", report)

    def test_a_wielded_gadget_is_named_as_the_resolve_owner(self):
        self._equip("malfunctioning_gizmo")

        report = strip_ansi(describe_action_rules(self.char1))

        self.assertIn("malfunctioning_gizmo", report)
        self.assertIn("resolve", report)

    def test_the_modifier_seam_is_not_listed_as_a_contest(self):
        # Every contributor's modifiers run, so naming a single winner for
        # contribute_modifiers would state the opposite of the truth.
        self._equip("glass_cannon_amulet")

        report = strip_ansi(describe_action_rules(self.char1))
        seam_table = report.split("Seam owners")[1]

        self.assertNotIn("contribute_modifiers", seam_table)

    def test_a_modifier_only_rule_still_appears_as_a_contributor(self):
        self._equip("glass_cannon_amulet")

        report = strip_ansi(describe_action_rules(self.char1))
        contributors = report.split("Seam owners")[0]

        self.assertIn("glass_cannon_amulet", contributors)
        self.assertIn("contribute_modifiers", contributors)

    def test_two_items_report_two_different_seam_owners(self):
        self._equip("toy_sword")
        self._equip("glass_cannon_amulet")

        report = strip_ansi(describe_action_rules(self.char1))

        self.assertIn("toy_sword", report)
        self.assertIn("glass_cannon_amulet", report)

    def test_the_report_reflects_current_gear_not_a_stale_cache(self):
        # Collected fresh on purpose: reading the handler's ndb cache would
        # hide the exact bug someone running this command is hunting.
        from systems.combat.combat import ensure_combat_handler

        handler = ensure_combat_handler(self.char1)
        handler.active_rules()

        self._equip("toy_sword")
        report = strip_ansi(describe_action_rules(self.char1))

        self.assertIn("toy_sword", report)
