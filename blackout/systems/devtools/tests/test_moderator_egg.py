"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: Tests for the egg itself -- its ItemDef, the command it carries,
             and the wiring of its menu.

             The menu's NAVIGATION is what is guarded here, not its prose. A
             `goto` naming a node that does not exist is EvMenu's one silent
             failure mode of consequence: the player gets "not implemented"
             and the moderator finds out mid-incident.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py systems.devtools
"""

import unittest

from evennia.utils.test_resources import EvenniaTest
from evennia.utils.utils import class_from_module

from systems.menus import dev_egg_menu
from systems.progression.skills import constants as skill_constants
from typeclasses.dev_tools import CmdEgg, EggCmdSet, ModeratorEgg
from typeclasses.items import BaseItem
from world.item_database import ITEM_DB


# The one key this whole feature hangs off.
_EGG_KEY = "moderator_egg"



class EggItemDefTests(unittest.TestCase):
    """The database row, with no database needed."""

    def setUp(self):
        self.item_def = ITEM_DB[_EGG_KEY]

    def test_the_egg_is_registered_in_the_item_database(self):
        """world/item_defs/dev_tools.py must appear in BOTH lists in
        item_database.py. A module imported but left out of the loop
        contributes nothing and raises nothing."""
        self.assertIn(_EGG_KEY, ITEM_DB)

    def test_the_egg_names_a_typeclass_that_actually_resolves(self):
        resolved = class_from_module(self.item_def.typeclass)

        self.assertIs(resolved, ModeratorEgg)

    def test_the_egg_is_not_tradeable(self):
        """The one field that keeps a staff tool out of the economy."""
        self.assertFalse(self.item_def.tradeable)

    def test_the_egg_is_weightless_and_worthless(self):
        self.assertEqual(self.item_def.value, 0)
        self.assertEqual(self.item_def.weight, 0.0)

    def test_the_egg_occupies_no_equipment_slot(self):
        """It is used from the bag; nothing about it is equipment."""
        self.assertIsNone(self.item_def.use_slot)

    def test_the_egg_is_an_inventory_item(self):
        """
        Inheriting BaseItem is what makes Character.at_object_receive route
        the egg into the 32-slot grid -- `is_stackable` is the attribute that
        hook tests for. An egg that skipped it would sit in contents with no
        slot: invisible to `inv`, uncounted, and still real.
        """
        self.assertTrue(issubclass(ModeratorEgg, BaseItem))



class EggCommandTests(unittest.TestCase):
    """The lock, which is the whole permission story for this tool."""

    def test_the_command_is_bound_to_egg(self):
        self.assertEqual(CmdEgg.key, "egg")

    def test_the_command_is_locked_to_admins_and_above(self):
        """Superusers bypass every lock in Evennia, so they pass this
        unnamed. Anyone below Admin gets an inert ceramic egg."""
        self.assertIn("perm(Admin)", CmdEgg.locks)

    def test_the_cmdset_carries_the_command(self):
        cmdset = EggCmdSet()
        cmdset.at_cmdset_creation()
        keys = [command.key for command in cmdset.commands]

        self.assertIn("egg", keys)



class EggObjectTests(EvenniaTest):
    """The spawned object."""

    def setUp(self):
        super().setUp()
        item_def = ITEM_DB[_EGG_KEY]
        self.egg = item_def.create(location=self.char1, home=self.char1)

    def test_a_spawned_egg_carries_its_command_set(self):
        stored = self.egg.cmdset.get()
        keys = [cmdset.key for cmdset in stored]

        self.assertIn(EggCmdSet.key, keys)

    def test_a_spawned_egg_lands_in_the_inventory_grid(self):
        slot = self.char1.inventory.find_slot(self.egg)

        self.assertGreaterEqual(slot, 0)

    def test_a_carried_egg_makes_the_command_reachable_to_an_admin(self):
        """
        The end-to-end assertion for the whole design. Evennia's cmdhandler
        merges cmdsets from `location.contents_get() + caller.contents_get() +
        [location]`, which is the only reason an object in the BAG can supply
        a command at all. If that ever stops being true, this fails and
        everything else in the feature still passes.

        Run on char2, not char1: EvenniaTest hands char1 Developer in setUp,
        so a permission test on char1 passes without the lock ever being the
        reason. char2 starts with nothing, which is what makes the pair of
        tests below mean anything.

        The permission goes on the ACCOUNT, and that is not incidental. For a
        puppeted object, Evennia's `perm` lockfunc reads the ACCOUNT's
        hierarchy permissions and ignores the character's own unless the
        account is quelling (evennia/locks/lockfuncs.py). Granting Admin to a
        moderator's character and not their account leaves the egg inert with
        no error to explain why.
        """
        self.egg.move_to(self.char2, quiet=True)
        self.account2.permissions.add("Admin")
        self.char2.execute_cmd("egg")
        menu = self.char2.ndb._evmenu

        self.assertIsNotNone(menu)

    def test_the_egg_is_inert_without_the_permission(self):
        """A player who is handed one gets a warm ceramic egg and nothing
        else. The lock is the entire permission story for this tool."""
        self.egg.move_to(self.char2, quiet=True)
        self.char2.execute_cmd("egg")
        menu = self.char2.ndb._evmenu

        self.assertIsNone(menu)

    def test_an_admin_without_the_egg_has_no_command(self):
        """The power is attached to an object staff can put down and take
        back, not to a permission bit that is invisible until it is used."""
        self.account2.permissions.add("Admin")
        self.char2.execute_cmd("egg")
        menu = self.char2.ndb._evmenu

        self.assertIsNone(menu)



class MenuWiringTests(EvenniaTest):
    """Every destination the menu names must exist."""

    def _string_gotos(self, options) -> list:
        """Collect the node NAMES an option list points at, ignoring the
        callables -- a callable that does not exist is an ImportError at
        module load, which needs no test."""
        names = []

        for option in options:
            goto = option.get("goto")

            if isinstance(goto, tuple):
                goto = goto[0]

            if isinstance(goto, str):
                names.append(goto)

        return names

    def test_the_root_node_renders_without_an_open_menu(self):
        """`start` is also called directly by _typed_node on a successful
        answer, so it must not require menu state to exist."""
        text, options = dev_egg_menu.start(self.char1)

        self.assertIn(self.char1.key, text)
        self.assertGreater(len(options), 0)

    def test_every_destination_named_from_the_root_exists(self):
        _text, options = dev_egg_menu.start(self.char1)
        names = self._string_gotos(options)

        for name in names:
            with self.subTest(node=name):
                self.assertTrue(hasattr(dev_egg_menu, name))

    def test_every_prompt_names_a_node_and_a_way_back(self):
        for node_name, prompt in dev_egg_menu._PROMPT_TABLE.items():
            with self.subTest(prompt=node_name):
                self.assertTrue(hasattr(dev_egg_menu, prompt.node))
                self.assertTrue(hasattr(dev_egg_menu, prompt.back_node))
                self.assertEqual(prompt.node, node_name)

    def test_every_list_node_offers_a_way_back(self):
        list_nodes = (
            dev_egg_menu.node_spawn,
            dev_egg_menu.node_teleport,
            dev_egg_menu.node_xp_skill,
            dev_egg_menu.node_level_skill,
            dev_egg_menu.node_account,
        )

        for node in list_nodes:
            with self.subTest(node=node.__name__):
                _text, options = node(self.char1)
                names = self._string_gotos(options)

                self.assertIn("start", names)

    def test_the_spawn_list_offers_every_item_in_the_database(self):
        _text, options = dev_egg_menu.node_spawn(self.char1)
        descriptions = [option.get("desc") for option in options]

        for item_key in ITEM_DB:
            with self.subTest(item=item_key):
                self.assertIn(item_key, descriptions)

    def test_the_root_reports_god_mode_state(self):
        from systems.devtools import actions as dev_actions

        text_off, _options = dev_egg_menu.start(self.char1)
        dev_actions.set_godmode(self.char1, self.char1, True)
        text_on, _options = dev_egg_menu.start(self.char1)

        self.assertNotEqual(text_off, text_on)

    def test_the_menu_declares_a_closing_line(self):
        """Read by BlackoutEvMenu.close_menu, however the menu is closed."""
        self.assertTrue(dev_egg_menu.CLOSING_TEXT)



class LevelPromptParseTests(unittest.TestCase):
    """The level prompt's parser, which base_menu.parse_quantity cannot be."""

    def test_zero_is_accepted_because_the_skill_floor_is_zero(self):
        minimum = skill_constants.MIN_BASE_SKILL_LEVEL
        maximum = skill_constants.MAX_BASE_SKILL_LEVEL
        value, error = dev_egg_menu._parse_bounded_int("0", minimum, maximum)

        self.assertIsNone(error)
        self.assertEqual(value, minimum)

    def test_a_level_over_the_ceiling_is_refused_rather_than_clamped(self):
        """A quantity clamps up top ("as many as you have"); a LEVEL does
        not -- silently storing 127 after someone typed 500 hides a typo."""
        maximum = skill_constants.MAX_BASE_SKILL_LEVEL
        value, error = dev_egg_menu._parse_bounded_int(str(maximum + 1), 0, maximum)

        self.assertIsNone(value)
        self.assertIsNotNone(error)

    def test_a_negative_level_is_refused(self):
        value, error = dev_egg_menu._parse_bounded_int("-3", 0, 127)

        self.assertIsNone(value)
        self.assertIsNotNone(error)

    def test_nonsense_is_refused_with_a_message_naming_the_range(self):
        value, error = dev_egg_menu._parse_bounded_int("lots", 0, 127)

        self.assertIsNone(value)
        self.assertIn("127", error)
