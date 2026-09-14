"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/13/2026
Description: Cases for STAT_REGISTRY against the key constants that name it.

             Written for a real defect: butchery.py declared
             BUTCHERY_TOTALS_STAT_KEY as its stat_key while the registry had no
             entry for it, so every harvest raised KeyError inside a guard that
             logged and carried on, and butchery totals never accumulated.
             Nothing a player could see said so.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.core.stat_tracker.tests
"""

import unittest

from systems.core.stat_tracker import constants as stat_constants
from systems.core.stat_tracker.registry import STAT_REGISTRY, StatDef, StatKind


# ─── Private constant definitions ────────────────────────────────────────────

# Every name in constants.py spelled this way is a key some system increments.
_STAT_KEY_SUFFIX: str = "_STAT_KEY"


class TestRegistryCoversItsKeys(unittest.TestCase):
    """A key constant is a promise that some caller will increment it."""

    def _declared_keys(self) -> dict:
        declared = {
            name: value
            for name, value in vars(stat_constants).items()
            if name.endswith(_STAT_KEY_SUFFIX)
        }

        return declared

    def test_every_declared_stat_key_is_registered(self):
        for name, stat_key in self._declared_keys().items():
            with self.subTest(constant=name):
                self.assertIn(stat_key, STAT_REGISTRY)

    def test_every_entry_is_filed_under_its_own_key(self):
        for registry_key, stat_def in STAT_REGISTRY.items():
            with self.subTest(stat=registry_key):
                self.assertIsInstance(stat_def, StatDef)
                self.assertEqual(registry_key, stat_def.key)

    def test_every_entry_is_well_formed(self):
        for registry_key, stat_def in STAT_REGISTRY.items():
            with self.subTest(stat=registry_key):
                self.assertIsInstance(stat_def.kind, StatKind)
                self.assertTrue(stat_def.name)
                self.assertTrue(stat_def.label)
                self.assertTrue(stat_def.category)
