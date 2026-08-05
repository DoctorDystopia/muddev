"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Tests for action rules auto-discovery and structural seam detection.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.combat
"""

import unittest

from systems.combat import constants as const
from systems.combat.rules.registry import (
    RULES_REGISTRY,
    _overridden_seams,
    find_rules,
)
from systems.combat.rules.rule_defs.base_rules import (
    ACTION_SEAM_NAMES,
    BaseActionRules,
)


class TestRulesDiscovery(unittest.TestCase):
    """What the registry does and does not pick up."""

    def test_the_base_class_is_not_registered(self):
        for rules in RULES_REGISTRY.values():
            self.assertIsNot(type(rules), BaseActionRules)

    def test_the_placeholder_key_is_not_registered(self):
        self.assertNotIn(BaseActionRules.key, RULES_REGISTRY)

    def test_every_entry_subclasses_the_base(self):
        for rules in RULES_REGISTRY.values():
            self.assertIsInstance(rules, BaseActionRules)

    def test_the_registry_holds_instances_not_classes(self):
        for rules in RULES_REGISTRY.values():
            self.assertFalse(isinstance(rules, type))

    def test_every_entry_is_keyed_by_its_own_key(self):
        for registry_key, rules in RULES_REGISTRY.items():
            self.assertEqual(registry_key, rules.key)

    def test_every_entry_declares_a_known_priority_tier(self):
        tiers = (
            const.RULES_PRIORITY_DEFAULT,
            const.RULES_PRIORITY_MODIFIER,
            const.RULES_PRIORITY_WEAPON,
            const.RULES_PRIORITY_OVERRIDE,
        )

        for rules in RULES_REGISTRY.values():
            self.assertIn(rules.priority, tiers)

    def test_every_entry_overrides_at_least_one_seam(self):
        # A definition that overrides nothing is dead weight the pipeline
        # will still walk on every action. The registry logs it; this asserts
        # none has slipped into the tree.
        for rules in RULES_REGISTRY.values():
            self.assertTrue(rules._overridden_seams, msg=rules.key)

    def test_find_rules_resolves_a_registered_key(self):
        for registry_key, rules in RULES_REGISTRY.items():
            self.assertIs(find_rules(registry_key), rules)

    def test_find_rules_returns_none_for_an_unknown_key(self):
        # No prefix or display-name fallback, unlike find_aura: a rules key is
        # written by a developer in an ItemDef, never typed by a player, so a
        # near-miss is a bug to surface rather than a guess to make.
        self.assertIsNone(find_rules("toy_swor"))

    def test_find_rules_returns_none_for_empty_input(self):
        self.assertIsNone(find_rules(""))


class TestSeamDetection(unittest.TestCase):
    """Structural override detection, in place of a hand-maintained tuple."""

    def test_the_base_class_overrides_nothing(self):
        self.assertEqual(_overridden_seams(BaseActionRules), frozenset())

    def test_a_subclass_that_changes_nothing_overrides_nothing(self):
        class _Inert(BaseActionRules):
            key = "inert"

        self.assertEqual(_overridden_seams(_Inert), frozenset())

    def test_one_replaced_method_is_detected(self):
        class _Diced(BaseActionRules):
            key = "diced"

            def roll_damage(self, context, result) -> None:
                result.damage = 1

        self.assertEqual(_overridden_seams(_Diced), frozenset({"roll_damage"}))

    def test_two_replaced_methods_are_both_detected(self):
        class _Pair(BaseActionRules):
            key = "pair"

            def max_hit(self, context, eff_str: int) -> int:
                return 1

            def roll_accuracy(self, context, chance: float) -> bool:
                return True

        expected = frozenset({"max_hit", "roll_accuracy"})
        self.assertEqual(_overridden_seams(_Pair), expected)

    def test_an_inherited_override_is_still_reported(self):
        # A grandchild must report its parent's override too, or the pipeline
        # would stop dispatching to behaviour the class demonstrably has.
        class _Parent(BaseActionRules):
            key = "parent"

            def roll_damage(self, context, result) -> None:
                result.damage = 1

        class _Child(_Parent):
            key = "child"

        self.assertIn("roll_damage", _overridden_seams(_Child))

    def test_every_detected_seam_is_a_declared_seam_name(self):
        for rules in RULES_REGISTRY.values():
            for seam_name in rules._overridden_seams:
                self.assertIn(seam_name, ACTION_SEAM_NAMES)

    def test_a_method_outside_the_seam_list_is_not_detected(self):
        class _Helper(BaseActionRules):
            key = "helper"

            def some_private_helper(self) -> int:
                return 1

        self.assertEqual(_overridden_seams(_Helper), frozenset())
