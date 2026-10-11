"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/09/2026
Description: Tests for NpcDef, NPC_DB, and the spawner of each NPC.

             Every expectation comes from NPC_DB, SHOP_DB, PRECEPTOR_DB and
             OBJECT_KINDS, never from a list of names here. Thus, a new NPC
             gets every check with no edit to this file (CLAUDE.md, "Never
             assert a census of a registry").
"""

import unittest

from evennia import create_object
from evennia.utils.test_resources import EvenniaTest
from evennia.utils.utils import class_from_module, mod_import

from systems.core.tilegrid import constants as tile_const
from systems.gameplay.exterminator.preceptors import PRECEPTOR_DB
from typeclasses.mixins import CombatEntity
from typeclasses.npc_defined import NpcDefined
from typeclasses.npc_spawners import LEGACY_NPC_TYPECLASSES, spawn_npc
from typeclasses.npcs import PreceptorNPC, ShopkeepNPC
from typeclasses.spawners import SPAWNER_REGISTRY, load_all_spawners
from world.npc_database import NPC_DB, NPC_KEY_ATTR, combatant_defs
from world.object_kinds import OBJECT_KINDS
from world.shop_defs import SHOP_DB


# A description that no def holds, to stand for a stale stamp.
_STALE_DESC: str = "A stale description from an old spawner."



def _typeclass_of(npc_def):
    """The class that the def creates."""
    return class_from_module(npc_def.resolved_typeclass())


def _first_key_of(typeclass) -> str:
    """The key of the first def whose typeclass is `typeclass`, or ""."""
    for key, npc_def in NPC_DB.items():
        if _typeclass_of(npc_def) is typeclass:
            return key

    return ""



class NpcDefRuleTests(unittest.TestCase):
    """Every def is well-formed. No DB."""

    def test_every_typeclass_reads_its_facts_from_the_def(self):
        for key, npc_def in NPC_DB.items():
            with self.subTest(npc=key):
                self.assertTrue(issubclass(_typeclass_of(npc_def), NpcDefined))

    def test_a_def_can_fight_if_and_only_if_its_typeclass_can(self):
        for key, npc_def in NPC_DB.items():
            with self.subTest(npc=key):
                fights = issubclass(_typeclass_of(npc_def), CombatEntity)

                self.assertEqual(fights, npc_def.combat is not None)

    def test_combatant_defs_holds_every_def_with_a_combat_block(self):
        expected = {key for key, npc_def in NPC_DB.items()
                    if npc_def.combat is not None}

        self.assertEqual(set(combatant_defs()), expected)

    def test_every_dialogue_names_a_module_that_imports(self):
        for key, npc_def in NPC_DB.items():
            if not npc_def.dialogue:
                continue

            with self.subTest(npc=key):
                self.assertIsNotNone(mod_import(npc_def.dialogue_module()))

    def test_a_shopkeep_names_a_shop_and_only_a_shopkeep_does(self):
        for key, npc_def in NPC_DB.items():
            with self.subTest(npc=key):
                is_shopkeep = issubclass(_typeclass_of(npc_def), ShopkeepNPC)

                self.assertEqual(is_shopkeep, bool(npc_def.shop_key))

                if is_shopkeep:
                    self.assertIn(npc_def.shop_key, SHOP_DB)

    def test_a_preceptor_names_its_row_and_only_a_preceptor_does(self):
        for key, npc_def in NPC_DB.items():
            with self.subTest(npc=key):
                is_preceptor = issubclass(_typeclass_of(npc_def), PreceptorNPC)

                self.assertEqual(is_preceptor, bool(npc_def.preceptor_key))

                if is_preceptor:
                    self.assertIn(npc_def.preceptor_key, PRECEPTOR_DB)



class NpcObjectKindTests(unittest.TestCase):
    """The object kinds and the defs agree. No DB."""

    def test_every_npc_kind_names_a_def_as_its_spawner(self):
        npc_kinds = [kind for kind in OBJECT_KINDS.values()
                     if kind.category == tile_const.OBJECT_CATEGORY_NPC]

        for kind in npc_kinds:
            with self.subTest(kind=kind.key):
                self.assertIn(kind.spawner, NPC_DB)

    def test_every_npc_kind_previews_the_model_of_its_def(self):
        for kind in OBJECT_KINDS.values():
            if kind.spawner not in NPC_DB:
                continue

            with self.subTest(kind=kind.key):
                npc_def = NPC_DB[kind.spawner]

                self.assertEqual(kind.preview[0], npc_def.resolved_asset_key())

    def test_every_def_has_a_spawner(self):
        load_all_spawners()

        for key in NPC_DB:
            with self.subTest(npc=key):
                self.assertIn(key, SPAWNER_REGISTRY)



class NpcSpawnTests(EvenniaTest):
    """The spawner stands each NPC up one time, and adopts an old row."""

    def test_each_def_spawns_one_npc_however_often_it_runs(self):
        for key in NPC_DB:
            with self.subTest(npc=key):
                first = spawn_npc(key, self.room1)
                second = spawn_npc(key, self.room1)

                self.assertEqual(first, second)
                self.assertEqual(first.attributes.get(NPC_KEY_ATTR), key)
                first.delete()

    def test_the_def_desc_beats_a_stale_stamp(self):
        for key, npc_def in NPC_DB.items():
            if not npc_def.desc:
                continue

            with self.subTest(npc=key):
                npc = npc_def.create(location=self.room1)
                npc.db.desc = _STALE_DESC

                self.assertEqual(npc.get_display_desc(self.char1), npc_def.desc)
                npc.delete()

    def test_the_model_comes_from_the_def(self):
        for key, npc_def in NPC_DB.items():
            with self.subTest(npc=key):
                npc = npc_def.create(location=self.room1)

                self.assertEqual(npc.asset_key, npc_def.resolved_asset_key())
                npc.delete()

    def test_a_preceptor_reads_its_row_from_the_def(self):
        key = _first_key_of(PreceptorNPC)

        if not key:
            self.skipTest("no Preceptor def")

        npc = NPC_DB[key].create(location=self.room1)

        self.assertEqual(npc.preceptor_key, NPC_DB[key].preceptor_key)

    def test_a_spawn_renames_an_npc_to_its_def(self):
        key = next(iter(NPC_DB))
        npc = NPC_DB[key].create(location=self.room1)
        npc.key = "an old name"

        spawn_npc(key, self.room1)

        self.assertEqual(npc.key, NPC_DB[key].name)



class LegacyAdoptionTests(EvenniaTest):
    """An NPC that an old spawner made gets its def at the next tile sync."""

    def _old_row(self, legacy_path: str):
        """
        An object that carries an old typeclass path and no npc key. A path
        that still imports makes a real object of that class. A path that
        does not import makes the object that Evennia loads for such a row:
        the base typeclass, with the old path in the database field.
        """
        try:
            class_from_module(legacy_path)
        except ImportError:
            obj = create_object("typeclasses.objects.Object", key="old npc",
                                location=self.room1)
            obj.db_typeclass_path = legacy_path
            obj.save(update_fields=["db_typeclass_path"])

            return obj

        return create_object(legacy_path, key="old npc", location=self.room1)

    def test_each_old_row_is_adopted_and_not_duplicated(self):
        for legacy_path, key in LEGACY_NPC_TYPECLASSES.items():
            with self.subTest(old=legacy_path):
                old = self._old_row(legacy_path)

                adopted = spawn_npc(key, self.room1)

                self.assertEqual(adopted.pk, old.pk)
                self.assertEqual(adopted.attributes.get(NPC_KEY_ATTR), key)
                self.assertEqual(adopted.typeclass_path,
                                 NPC_DB[key].resolved_typeclass())
                adopted.delete()

    def test_an_npc_with_a_key_is_never_adopted(self):
        legacy_path, key = next(iter(LEGACY_NPC_TYPECLASSES.items()))
        old = self._old_row(legacy_path)
        old.attributes.add(NPC_KEY_ATTR, "some other npc")

        spawned = spawn_npc(key, self.room1)

        self.assertNotEqual(spawned.pk, old.pk)
