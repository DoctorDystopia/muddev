"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Evennia-backed tests for collecting action rules off real gear.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.combat

These need the DB because the whole point is that combat_rules travels from an
ItemDef, through the prototype, onto a spawned object, into an equipment slot,
and back out again. Every link in that chain is a place it can be dropped.
"""

from evennia.utils.test_resources import EvenniaTest

from items.equipment.constants import WieldLocation
from items.equipment.handler import EquipmentError
from systems.combat import constants as const
from systems.combat.rules.contributors import collect_contributors
from systems.combat.rules.rule_defs.glass_cannon_amulet import (
    GlassCannonAmuletRules,
)
from systems.combat.rules.rule_defs.malfunctioning_gizmo import (
    MalfunctioningGizmoRules,
)
from systems.combat.rules.rule_defs.toy_sword import ToySwordRules
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.npc_combat import spawn_mutant_raider
from world.item_database import ITEM_DB


class TestItemDefPlumbing(EvenniaTest):
    """combat_rules must survive the ItemDef -> prototype -> object trip."""

    character_typeclass = BlackoutCharacter

    def test_the_demo_items_are_in_the_database(self):
        # A def module imported but left out of the ITEM_DB build loop
        # contributes nothing and raises nothing.
        for key in (
            "malfunctioning_gizmo",
            "toy_sword",
            "glass_cannon_amulet",
            "rusty_scrap_chainbody",
        ):
            self.assertIn(key, ITEM_DB)

    def test_an_items_rules_reach_the_spawned_object(self):
        item = ITEM_DB["toy_sword"].create(location=self.char1)

        stored = getattr(item.db, const.COMBAT_RULES_ATTR)

        self.assertEqual(stored, [ToySwordRules.key])

    def test_an_item_without_rules_carries_no_attribute(self):
        # Non-combat items must stay clean; the field is only emitted when
        # populated, like every other optional ItemDef field.
        item = ITEM_DB["rusty_scrap_shortsword"].create(location=self.char1)

        self.assertFalse(getattr(item.db, const.COMBAT_RULES_ATTR, None))

    def test_every_declared_rules_key_resolves(self):
        # A typo'd key is logged and skipped at collection time, which is
        # quiet. Catch it here instead, across the whole item database.
        from systems.combat.rules.registry import RULES_REGISTRY

        for item_def in ITEM_DB.values():
            for rules_key in item_def.combat_rules:
                self.assertIn(rules_key, RULES_REGISTRY, msg=item_def.key)


class TestContributorCollection(EvenniaTest):
    """Which equipped items contribute, and in what order."""

    character_typeclass = BlackoutCharacter

    def _equip(self, item_key: str):
        item = ITEM_DB[item_key].create(location=self.char1)
        self.char1.equipment.equip(item)

        return item

    def test_bare_hands_contribute_nothing(self):
        self.assertEqual(collect_contributors(self.char1), ())

    def test_a_wielded_gadget_contributes_its_rules(self):
        self._equip("malfunctioning_gizmo")

        contributors = collect_contributors(self.char1)

        self.assertEqual([rules.key for rules in contributors],
                         [MalfunctioningGizmoRules.key])

    def test_an_amulet_in_a_non_hand_slot_contributes_its_rules(self):
        # The reason contributors are collected from every slot rather than
        # from the wielded weapon alone.
        self._equip("glass_cannon_amulet")

        contributors = collect_contributors(self.char1)

        self.assertEqual([rules.key for rules in contributors],
                         [GlassCannonAmuletRules.key])

    def test_a_weapon_without_rules_contributes_nothing(self):
        self._equip("rusty_scrap_shortsword")

        self.assertEqual(collect_contributors(self.char1), ())

    def test_two_items_both_contribute(self):
        self._equip("toy_sword")
        self._equip("glass_cannon_amulet")

        keys = [rules.key for rules in collect_contributors(self.char1)]

        self.assertIn(ToySwordRules.key, keys)
        self.assertIn(GlassCannonAmuletRules.key, keys)

    def test_contributors_are_sorted_lowest_priority_first(self):
        # The pipeline walks the tuple in order and lets later entries win a
        # contested seam, so this ordering IS the priority contract.
        self._equip("malfunctioning_gizmo")
        self._equip("glass_cannon_amulet")

        priorities = [rules.priority for rules in collect_contributors(self.char1)]

        self.assertEqual(priorities, sorted(priorities))
        self.assertEqual(priorities[-1], const.RULES_PRIORITY_OVERRIDE)

    def test_collection_is_deterministic_across_repeated_calls(self):
        # Equipment slots are a dict, and an unstable walk order would make
        # two equal-priority contributors take turns winning a seam.
        self._equip("toy_sword")
        self._equip("glass_cannon_amulet")

        first = [rules.key for rules in collect_contributors(self.char1)]
        second = [rules.key for rules in collect_contributors(self.char1)]

        self.assertEqual(first, second)

    def test_an_unknown_rules_key_is_skipped_not_raised(self):
        # A stale key left on one ring must not stop its wearer acting.
        item = self._equip("toy_sword")
        item.db.combat_rules = ["no_such_rules", ToySwordRules.key]

        keys = [rules.key for rules in collect_contributors(self.char1)]

        self.assertEqual(keys, [ToySwordRules.key])

    def test_a_bare_string_is_accepted_as_a_single_key(self):
        # Defensive: the field is documented as a list, but a hand-edited
        # attribute holding one string should not iterate into characters.
        item = self._equip("toy_sword")
        item.db.combat_rules = ToySwordRules.key

        keys = [rules.key for rules in collect_contributors(self.char1)]

        self.assertEqual(keys, [ToySwordRules.key])

    def test_unequipping_removes_the_contribution(self):
        item = self._equip("toy_sword")

        self.char1.equipment.remove(item)

        self.assertEqual(collect_contributors(self.char1), ())

    def test_none_collects_nothing(self):
        self.assertEqual(collect_contributors(None), ())


class TestNpcContributors(EvenniaTest):
    """An NPC has no equipment handler and carries its rules on itself."""

    character_typeclass = BlackoutCharacter

    def test_a_plain_npc_contributes_nothing(self):
        npc = spawn_mutant_raider(self.room1)

        self.assertEqual(collect_contributors(npc), ())

    def test_an_npc_with_rules_contributes_them_without_equipment(self):
        npc = spawn_mutant_raider(self.room1)
        npc.db.combat_rules = [MalfunctioningGizmoRules.key]

        contributors = collect_contributors(npc)

        self.assertFalse(hasattr(npc, "equipment"))
        self.assertEqual([rules.key for rules in contributors],
                         [MalfunctioningGizmoRules.key])


class TestHandlerRulesCache(EvenniaTest):
    """Contributors are cached on ndb and invalidated by _refresh_weapon."""

    character_typeclass = BlackoutCharacter

    def test_the_cache_is_populated_on_first_use(self):
        from systems.combat.combat import ensure_combat_handler

        handler = ensure_combat_handler(self.char1)
        self.assertIsNone(handler.ndb.active_rules)

        collected = handler.active_rules()

        self.assertIs(handler.ndb.active_rules, collected)

    def test_the_cache_is_reused_rather_than_recollected(self):
        from systems.combat.combat import ensure_combat_handler

        handler = ensure_combat_handler(self.char1)

        self.assertIs(handler.active_rules(), handler.active_rules())

    def test_refreshing_the_weapon_invalidates_the_cache(self):
        # Equipment is the only thing that decides contributors, and
        # _refresh_weapon already runs on every path that can change it.
        from systems.combat.combat import ensure_combat_handler

        handler = ensure_combat_handler(self.char1)
        handler.active_rules()

        handler._refresh_weapon()

        self.assertIsNone(handler.ndb.active_rules)

    def test_a_newly_wielded_gadget_reaches_the_next_action(self):
        from systems.combat.combat import ensure_combat_handler

        handler = ensure_combat_handler(self.char1)
        self.assertEqual(handler.active_rules(), ())

        item = ITEM_DB["malfunctioning_gizmo"].create(location=self.char1)
        self.char1.equipment.equip(item)
        handler._refresh_weapon()

        keys = [rules.key for rules in handler.active_rules()]
        self.assertEqual(keys, [MalfunctioningGizmoRules.key])

    def test_plain_equip_alone_invalidates_the_cache(self):
        """EquipmentHandler.equip() must invalidate the cache on its own.

        Regression test for the `equip <item>` command leaving a fighter
        swinging with a dead weapon's rules mid-combat: only the 'wield'
        combat action called _refresh_weapon(), so equipping through the
        general equip command (or the equipment EvMenu) left ndb.active_rules
        stale until combat was broken and restarted. No manual
        handler._refresh_weapon() call here -- that is the point.
        """
        from systems.combat.combat import ensure_combat_handler

        handler = ensure_combat_handler(self.char1)
        handler.active_rules()  # populate the cache with the unarmed baseline

        item = ITEM_DB["malfunctioning_gizmo"].create(location=self.char1)
        self.char1.equipment.equip(item)

        keys = [rules.key for rules in handler.active_rules()]
        self.assertEqual(keys, [MalfunctioningGizmoRules.key])


class TestEquippingTheDemoItems(EvenniaTest):
    """A new tool_type fails closed unless it is registered."""

    character_typeclass = BlackoutCharacter

    def test_a_gadget_can_actually_be_equipped(self):
        # WEAPON_SKILL_MAP treats an unregistered tool_type as a
        # misconfiguration and refuses the wield, so a missing entry would
        # make the whole demo unreachable in game while every unit test
        # still passed.
        item = ITEM_DB["malfunctioning_gizmo"].create(location=self.char1)

        self.char1.equipment.equip(item)

        self.assertTrue(self.char1.equipment.is_equipped(item))

    def test_the_amulet_lands_in_the_neck_slot(self):
        item = ITEM_DB["glass_cannon_amulet"].create(location=self.char1)

        self.char1.equipment.equip(item)

        slot = self.char1.equipment.get_current_slot(item)
        self.assertEqual(slot, WieldLocation.NECK)

    def test_a_gadget_and_an_amulet_can_be_worn_together(self):
        gizmo = ITEM_DB["malfunctioning_gizmo"].create(location=self.char1)
        amulet = ITEM_DB["glass_cannon_amulet"].create(location=self.char1)

        self.char1.equipment.equip(gizmo)
        self.char1.equipment.equip(amulet)

        self.assertTrue(self.char1.equipment.is_equipped(gizmo))
        self.assertTrue(self.char1.equipment.is_equipped(amulet))

    def test_the_chainbody_lands_in_the_body_slot(self):
        # The crafted rusty chainbody must be equippable; ARMOR_SKILL_MAP
        # registers "chainbody" the way WEAPON_SKILL_MAP registers weapons.
        item = ITEM_DB["rusty_scrap_chainbody"].create(location=self.char1)

        self.char1.equipment.equip(item)

        slot = self.char1.equipment.get_current_slot(item)
        self.assertEqual(slot, WieldLocation.BODY)

    def test_the_armor_gate_checks_defense(self):
        # ARMOR_SKILL_MAP wires chainbody -> Defense; a req_level above the
        # character's level must refuse the equip and name the skill.
        item = ITEM_DB["rusty_scrap_chainbody"].create(location=self.char1)
        item.db.req_level = 99

        with self.assertRaises(EquipmentError) as ctx:
            self.char1.equipment.equip(item)

        self.assertIn("Defense", str(ctx.exception))
