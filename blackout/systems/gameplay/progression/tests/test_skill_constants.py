"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/14/2026
Description: Relation tests between the skill constants and SKILL_REGISTRY.

The constants module holds each skill key, each skill category, and one tuple
of keys for each category. The skill classes also declare a key and a
category. These tests make sure that the two sources agree, in both
directions, so that a tuple name never makes a false claim.
"""



import unittest

from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills.registry import SKILL_REGISTRY



# Private constant definitions

# Each category and the tuple that must hold every skill in it. A category
# with no row here makes test_every_category_has_a_key_tuple fail.
_KEYS_BY_CATEGORY: dict = {
    skill_constants.SKILL_CATEGORY_COMBAT: skill_constants.SKILL_KEYS_CATEGORY_COMBAT,
    skill_constants.SKILL_CATEGORY_GATHERING: skill_constants.SKILL_KEYS_CATEGORY_GATHERING,
    skill_constants.SKILL_CATEGORY_PROCESSING: skill_constants.SKILL_KEYS_CATEGORY_PROCESSING,
    skill_constants.SKILL_CATEGORY_PRODUCTION: skill_constants.SKILL_KEYS_CATEGORY_PRODUCTION,
}

# The name prefix of a single skill key constant.
_SKILL_KEY_PREFIX: str = "SKILL_KEY_"



class SkillConstantsRegistryTests(unittest.TestCase):
    """The constants module and the skill classes name the same skills."""

    def test_every_category_has_a_key_tuple(self):
        self.assertEqual(set(skill_constants.SKILL_CATEGORIES), set(_KEYS_BY_CATEGORY))


    def test_every_skill_declares_a_known_category(self):
        for key, skill_cls in SKILL_REGISTRY.items():
            with self.subTest(skill=key):
                self.assertIn(skill_cls.category, skill_constants.SKILL_CATEGORIES)


    def test_each_category_tuple_holds_exactly_its_skills(self):
        for category, keys in _KEYS_BY_CATEGORY.items():
            declared = {
                key for key, skill_cls in SKILL_REGISTRY.items()
                if skill_cls.category == category
            }

            with self.subTest(category=category):
                self.assertEqual(set(keys), declared)


    def test_every_skill_key_constant_names_a_registered_skill(self):
        for name, value in vars(skill_constants).items():
            if not name.startswith(_SKILL_KEY_PREFIX):
                continue

            with self.subTest(constant=name):
                self.assertIn(value, SKILL_REGISTRY)
