"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: Tests for the moderator effects -- god mode, restore, spawning,
             teleport, XP and level writes, and the delegated account
             commands.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py systems.devtools
"""

import unittest

from evennia.utils.test_resources import EvenniaTest

from items.equipment.constants import MAX_INVENTORY_SLOTS
from systems.devtools import actions as dev_actions
from systems.devtools import constants as dev_constants
from systems.progression.skills import constants as skill_constants
from systems.progression.skills.registry import SKILL_REGISTRY
from world.item_database import ITEM_DB
from world.maps.manifest import load_entries, zcoords_of


# The stackable and non-stackable items the spawn tests use. Resolved from the
# registry rather than named, so adding or renaming an ItemDef cannot silently
# turn one of these tests into a no-op.
def _first_key(stackable: bool) -> str:
    """Name any item in ITEM_DB with the wanted stackability."""
    for key in sorted(ITEM_DB.keys()):
        item_def = ITEM_DB[key]

        if item_def.stackable == stackable:
            return key

    return ""



class GodModeTests(EvenniaTest):
    """The one genuinely new game rule the moderator tool adds."""

    def test_damage_applies_normally_with_god_mode_off(self):
        start_hp = self.char1.hp
        removed = self.char1.at_damage(3, attacker=self.char2)

        self.assertEqual(removed, 3)
        self.assertEqual(self.char1.hp, start_hp - 3)

    def test_god_mode_removes_no_hp_and_reports_none_removed(self):
        dev_actions.set_godmode(self.char2, self.char1, True)
        start_hp = self.char1.hp
        removed = self.char1.at_damage(999, attacker=self.char2)

        self.assertEqual(removed, 0)
        self.assertEqual(self.char1.hp, start_hp)

    def test_god_mode_prevents_the_death_that_damage_would_have_caused(self):
        dev_actions.set_godmode(self.char2, self.char1, True)
        self.char1.at_damage(self.char1.max_hp * 2, attacker=self.char2)

        self.assertTrue(self.char1.is_alive())

    def test_an_immune_target_still_records_its_attacker(self):
        """
        Aggro must survive immunity. If it did not, standing in a fight with
        god mode on would silently pacify the thing being observed -- which is
        the opposite of what a moderator turned it on to do.
        """
        dev_actions.set_godmode(self.char2, self.char1, True)
        self.char1.at_damage(5, attacker=self.char2)

        from systems.ai.constants import LAST_ATTACKER_ID_ATTR

        recorded = getattr(self.char1.ndb, LAST_ATTACKER_ID_ATTR, None)

        self.assertEqual(recorded, self.char2.id)

    def test_turning_god_mode_off_restores_normal_damage(self):
        dev_actions.set_godmode(self.char2, self.char1, True)
        dev_actions.set_godmode(self.char2, self.char1, False)
        start_hp = self.char1.hp
        removed = self.char1.at_damage(2, attacker=self.char2)

        self.assertEqual(removed, 2)
        self.assertEqual(self.char1.hp, start_hp - 2)

    def test_the_reader_and_the_combat_hot_path_agree(self):
        """
        at_damage reads the flag inline instead of calling godmode_enabled,
        to keep ITEM_DB and the xyzgrid contrib out of the combat hot path.
        Only the attribute NAME is shared. This is the assertion that keeps
        the two readers from drifting apart.
        """
        self.assertFalse(dev_actions.godmode_enabled(self.char1))

        dev_actions.set_godmode(self.char2, self.char1, True)

        self.assertTrue(dev_actions.godmode_enabled(self.char1))
        self.assertEqual(self.char1.at_damage(1, attacker=self.char2), 0)

    def test_an_object_with_no_attributes_reads_as_not_immune(self):
        self.assertFalse(dev_actions.godmode_enabled(None))



class RestoreTests(EvenniaTest):
    """Full heal, and the honest scope of "anything else depleted"."""

    def test_restore_returns_the_target_to_full_hp(self):
        self.char1.at_damage(5, attacker=self.char2)
        succeeded, _message = dev_actions.restore(self.char2, self.char1)

        self.assertTrue(succeeded)
        self.assertEqual(self.char1.hp, self.char1.max_hp)

    def test_restore_refreshes_the_cap_from_fortitude_before_healing(self):
        """
        A Fortitude level written without a level-up hook firing leaves
        max_hp stale. Restore must heal to the CURRENT cap, not the old one.
        """
        fortitude = skill_constants.FORTITUDE_SKILL_KEY
        old_cap = self.char1.max_hp
        self.char1.skills.set_level(fortitude, old_cap + 5)
        dev_actions.restore(self.char2, self.char1)

        self.assertEqual(self.char1.hp, self.char1.max_hp)
        self.assertGreater(self.char1.max_hp, old_cap)

    def test_restore_on_an_untouched_character_is_harmless(self):
        succeeded, _message = dev_actions.restore(self.char2, self.char1)

        self.assertTrue(succeeded)
        self.assertEqual(self.char1.hp, self.char1.max_hp)



class SpawnTests(EvenniaTest):
    """Item delivery, and what happens when the 32-slot grid runs out."""

    def test_an_unknown_item_key_is_refused(self):
        succeeded, message = dev_actions.grant_item(
            self.char2, self.char1, "no_such_item", 1
        )

        self.assertFalse(succeeded)
        self.assertIn("no_such_item", message)

    def test_a_stackable_item_arrives_as_one_object_carrying_the_count(self):
        item_key = _first_key(stackable=True)
        succeeded, _message = dev_actions.grant_item(
            self.char2, self.char1, item_key, 7
        )

        self.assertTrue(succeeded)

        carried = self.char1.inventory.all_items()
        quantities = [obj.quantity for _slot, obj in carried]

        self.assertIn(7, quantities)

    def test_a_non_stackable_item_arrives_as_separate_objects(self):
        item_key = _first_key(stackable=False)
        succeeded, _message = dev_actions.grant_item(
            self.char2, self.char1, item_key, 3
        )
        used = self.char1.inventory.count_used()

        self.assertTrue(succeeded)
        self.assertEqual(used, 3)

    def test_more_copies_than_slots_is_a_clamped_success_not_a_failure(self):
        """
        A moderator who asked for 200 swords and got the 32 that fit has been
        served. Refusing outright would only make them ask again for 32.
        """
        item_key = _first_key(stackable=False)
        asked = MAX_INVENTORY_SLOTS + 10
        succeeded, message = dev_actions.grant_item(
            self.char2, self.char1, item_key, asked
        )
        used = self.char1.inventory.count_used()

        self.assertTrue(succeeded)
        self.assertEqual(used, MAX_INVENTORY_SLOTS)
        self.assertIn(str(MAX_INVENTORY_SLOTS), message)

    def test_a_full_grid_refuses_rather_than_leaking_a_detached_object(self):
        item_key = _first_key(stackable=False)
        dev_actions.grant_item(self.char2, self.char1, item_key, MAX_INVENTORY_SLOTS)
        succeeded, _message = dev_actions.grant_item(
            self.char2, self.char1, item_key, 1
        )

        self.assertFalse(succeeded)
        self.assertEqual(self.char1.inventory.count_used(), MAX_INVENTORY_SLOTS)

    def test_the_quantity_ceiling_is_applied(self):
        item_key = _first_key(stackable=True)
        over = dev_constants.MAX_SPAWN_QUANTITY + 500
        succeeded, _message = dev_actions.grant_item(
            self.char2, self.char1, item_key, over
        )
        carried = self.char1.inventory.all_items()
        quantities = [obj.quantity for _slot, obj in carried]

        self.assertTrue(succeeded)
        self.assertIn(dev_constants.MAX_SPAWN_QUANTITY, quantities)

    def test_every_item_in_the_database_is_offered(self):
        """Derived from the registry, never a census -- adding an ItemDef
        must reach the moderator's list with no edit to this test."""
        offered = dev_actions.item_keys()

        self.assertEqual(sorted(offered), sorted(ITEM_DB.keys()))



class ProgressionTests(EvenniaTest):
    """XP grants and direct level writes."""

    def test_an_unknown_skill_is_refused_for_xp(self):
        succeeded, message = dev_actions.grant_xp(
            self.char2, self.char1, "no_such_skill", 100
        )

        self.assertFalse(succeeded)
        self.assertIn("no_such_skill", message)

    def test_an_unknown_skill_is_refused_for_a_level_write(self):
        succeeded, _message = dev_actions.set_skill_level(
            self.char2, self.char1, "no_such_skill", 10
        )

        self.assertFalse(succeeded)

    def test_granting_xp_raises_the_banked_total(self):
        skill_key = sorted(SKILL_REGISTRY.keys())[0]
        before = self.char1.skills.get_total_xp(skill_key)
        succeeded, _message = dev_actions.grant_xp(
            self.char2, self.char1, skill_key, 500
        )
        after = self.char1.skills.get_total_xp(skill_key)

        self.assertTrue(succeeded)
        self.assertGreater(after, before)

    def test_a_level_write_reports_the_level_actually_stored(self):
        """
        The clamp belongs to skills.logic.set_level. The message must quote
        what that returned, never what was asked for, or the menu can claim a
        level the write refused.
        """
        skill_key = sorted(SKILL_REGISTRY.keys())[0]
        over = skill_constants.MAX_BASE_SKILL_LEVEL + 50
        succeeded, message = dev_actions.set_skill_level(
            self.char2, self.char1, skill_key, over
        )
        stored = self.char1.skills.get_level(skill_key)

        self.assertTrue(succeeded)
        self.assertEqual(stored, skill_constants.MAX_BASE_SKILL_LEVEL)
        self.assertIn(str(skill_constants.MAX_BASE_SKILL_LEVEL), message)

    def test_the_bottom_of_the_level_range_is_reachable(self):
        """MIN_BASE_SKILL_LEVEL is 0, and a tool that cannot express the
        bottom of the range cannot undo what it did to the top."""
        skill_key = sorted(SKILL_REGISTRY.keys())[0]
        dev_actions.set_skill_level(self.char2, self.char1, skill_key,
                                    skill_constants.MIN_BASE_SKILL_LEVEL)
        stored = self.char1.skills.get_level(skill_key)

        self.assertEqual(stored, skill_constants.MIN_BASE_SKILL_LEVEL)

    def test_every_registered_skill_is_offered(self):
        offered = dev_actions.skill_keys()

        self.assertEqual(sorted(offered), sorted(SKILL_REGISTRY.keys()))



class TeleportDestinationTests(unittest.TestCase):
    """The destination list, which needs no database."""

    def test_the_destinations_are_exactly_the_manifest_maps(self):
        entries = load_entries()
        expected = zcoords_of(entries)
        offered = dev_actions.map_zcoords()

        self.assertEqual(sorted(offered), sorted(expected))

    def test_the_game_ships_at_least_one_destination(self):
        # Deliberately not a census: adding a map must never fail a test.
        offered = dev_actions.map_zcoords()

        self.assertGreater(len(offered), 0)



class TeleportTests(EvenniaTest):
    """Teleport refusals. The successful path needs a built grid, which the
    test database does not have -- map_sync runs against the live DB only."""

    def test_a_map_the_manifest_does_not_name_is_refused(self):
        succeeded, message = dev_actions.teleport_to_map(
            self.char2, self.char1, "no_such_map"
        )

        self.assertFalse(succeeded)
        self.assertIn("no_such_map", message)

    def test_a_named_map_with_no_rooms_built_reports_that_and_does_not_move(self):
        entries = load_entries()
        zcoords = zcoords_of(entries)
        start_location = self.char1.location
        succeeded, _message = dev_actions.teleport_to_map(
            self.char2, self.char1, zcoords[0]
        )

        self.assertFalse(succeeded)
        self.assertIs(self.char1.location, start_location)



class _RecordingActor:
    """Stands in for a moderator, capturing what was dispatched.

    A stub rather than a real Character because the assertion is about the
    STRING handed to Evennia's own command, and a real account would run the
    ban for real against the test server's config.
    """

    key = "TestMod"
    account = None

    def __init__(self):
        self.executed = []

    def execute_cmd(self, command):
        self.executed.append(command)



class DelegationTests(unittest.TestCase):
    """Boot and ban are Evennia's. The egg only types them."""

    def test_a_blank_account_name_is_refused_and_dispatches_nothing(self):
        actor = _RecordingActor()
        succeeded, _message = dev_actions.delegate_account_command(
            actor,
            dev_constants.ACCOUNT_COMMAND_BAN,
            "   ",
            dev_constants.ACTION_BAN,
        )

        self.assertFalse(succeeded)
        self.assertEqual(actor.executed, [])

    def test_a_named_account_dispatches_the_stock_command(self):
        actor = _RecordingActor()
        succeeded, _message = dev_actions.delegate_account_command(
            actor,
            dev_constants.ACCOUNT_COMMAND_BOOT,
            "griefer",
            dev_constants.ACTION_BOOT,
        )

        self.assertTrue(succeeded)
        self.assertEqual(actor.executed, ["boot griefer"])

    def test_a_reason_is_appended_in_the_form_the_stock_command_parses(self):
        actor = _RecordingActor()
        dev_actions.delegate_account_command(
            actor,
            dev_constants.ACCOUNT_COMMAND_BAN,
            "griefer",
            dev_constants.ACTION_BAN,
            "spawn camping",
        )
        separator = dev_constants.ACCOUNT_REASON_SEPARATOR

        self.assertEqual(actor.executed, [f"ban griefer {separator} spawn camping"])



class AuditVocabularyTests(unittest.TestCase):
    """Every verb an effect audits under must be in the vocabulary."""

    def test_each_action_constant_is_a_member_of_the_set(self):
        named = [
            dev_constants.ACTION_SPAWN,
            dev_constants.ACTION_GODMODE,
            dev_constants.ACTION_RESTORE,
            dev_constants.ACTION_TELEPORT,
            dev_constants.ACTION_XP,
            dev_constants.ACTION_LEVEL,
            dev_constants.ACTION_BOOT,
            dev_constants.ACTION_BAN,
            dev_constants.ACTION_UNBAN,
        ]

        for action in named:
            with self.subTest(action=action):
                self.assertIn(action, dev_constants.MODERATOR_ACTIONS)

    def test_the_audit_template_names_every_field_the_logger_fills(self):
        line = dev_constants.AUDIT_LINE_TEMPLATE.format(
            prefix=dev_constants.AUDIT_LOG_PREFIX,
            actor="mod",
            action=dev_constants.ACTION_SPAWN,
            target="player",
            detail="1x thing",
        )

        self.assertIn(dev_constants.AUDIT_LOG_PREFIX, line)
        self.assertIn("mod", line)
        self.assertIn("player", line)
