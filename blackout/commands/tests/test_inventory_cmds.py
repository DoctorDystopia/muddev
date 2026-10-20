"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/15/2026
Description: Tests for the commands the 3D inventory pane sends -- swap,
             equip <target> and unequip <target>.

             The pane's whole safety argument is that it sends nothing a
             telnet player could not type, so these commands ARE the pane's
             API. A test here is testing both at once.

Run with:
    evennia test --settings settings.py commands.tests.test_inventory_cmds
"""

from evennia import DefaultObject
from evennia.utils.create import create_object
from evennia.utils.test_resources import EvenniaCommandTest, EvenniaTestCase

from commands.equipment_cmds import CmdEquipment, CmdInspect, CmdUnequip
from commands.inventory_cmds import CmdSwap, parse_slot_number
from items.equipment.constants import WieldLocation
from items.inventory.handler import SLOTS_TOTAL
from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid import movement
from systems.core.tilegrid.world import TileWorld, set_world
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import neighbourhood
from typeclasses.characters import Character as BlackoutCharacter
from world.item_database import ITEM_DB


# Public constant definitions

EQUIPPABLE_KEY = "glass_cannon_amulet"
PLAIN_KEY = "rusty_metal_chunk"
OTHER_PLAIN_KEY = "rusty_scrap_metal"

# The tile world of TestCmdInspectReach: one area, one floor, flat ground.
_AREA = "oasis"
_FLOOR = "sand"
_ORIGIN = (2, 2)


def _chunk(cx: int, cy: int) -> chunkfile.ChunkFile:
    """One open chunk of the ground plane."""
    tile_count = tile_const.CHUNK_SIZE * tile_const.CHUNK_SIZE

    return chunkfile.ChunkFile(
        cx=cx, cy=cy, plane=tile_const.GROUND_PLANE, floor_names=[_FLOOR],
        area_names=[_AREA],
        heights=[0] * tile_const.CORNERS_PER_SIDE ** 2,
        floors=[0] * tile_count, flags=[0] * tile_count,
        areas=[0] * tile_count, objects=[])


class TestParseSlotNumber(EvenniaTestCase):
    """The 1-based to 0-based conversion every slot argument goes through."""

    character_typeclass = BlackoutCharacter

    def test_the_first_slot_a_player_sees_is_index_zero(self):
        self.assertEqual(parse_slot_number("1"), 0)

    def test_the_last_slot_a_player_sees_is_the_final_index(self):
        parsed = parse_slot_number(str(SLOTS_TOTAL))

        self.assertEqual(parsed, SLOTS_TOTAL - 1)

    def test_zero_is_not_a_slot(self):
        self.assertEqual(parse_slot_number("0"), -1)

    def test_a_slot_past_the_grid_is_rejected(self):
        parsed = parse_slot_number(str(SLOTS_TOTAL + 1))

        self.assertEqual(parsed, -1)

    def test_a_name_is_not_a_slot_number(self):
        self.assertEqual(parse_slot_number("toy sword"), -1)


class TestCmdInspect(EvenniaCommandTest):
    """Reading one row's description, addressed the way the pane addresses it.

    `look <name>` could not do this. Three identical chunks answered it with
    Evennia's multimatch list, and the disambiguators it offered ("chunk-1",
    "chunk-2") are search ordinals naming no row the pane drew -- so the one
    action in the payload still going out as a name was the one action a
    player with a stack of anything could not use.
    """

    character_typeclass = BlackoutCharacter

    def _pile(self, count=3, item_key=PLAIN_KEY):
        made = [ITEM_DB[item_key].create(location=self.char1)
                for _each in range(count)]
        self.char1.inventory.sync()

        return made

    def test_a_grid_slot_describes_that_slots_item(self):
        made = self._pile()
        wanted = made[2]
        wanted.db.desc = "The third one, and no other."

        response = self.call(CmdInspect(), "3")

        self.assertIn("The third one, and no other.", response)

    def test_identical_copies_are_told_apart_by_slot(self):
        made = self._pile()

        for number, item in enumerate(made, start=1):
            item.db.desc = f"Copy number {number}."

        for number in (1, 2, 3):
            with self.subTest(slot=number):
                response = self.call(CmdInspect(), str(number))

                self.assertIn(f"Copy number {number}.", response)

    def test_an_empty_slot_is_refused_rather_than_searched(self):
        response = self.call(CmdInspect(), "9")

        self.assertIn("empty", response.lower())

    def test_a_slot_past_the_grid_says_so(self):
        response = self.call(CmdInspect(), str(SLOTS_TOTAL + 1))

        self.assertIn(str(SLOTS_TOTAL), response)

    def test_an_equipment_slot_describes_what_is_worn_there(self):
        item = ITEM_DB[EQUIPPABLE_KEY].create(location=self.char1)
        item.db.desc = "Worn, not carried."
        self.char1.equipment.equip(item)

        response = self.call(CmdInspect(), WieldLocation.NECK.value)

        self.assertIn("Worn, not carried.", response)

    def test_a_worn_slot_is_named_the_way_a_player_spells_it(self):
        """The pane sends "main_hand"; a player types "main hand"."""
        item = ITEM_DB[EQUIPPABLE_KEY].create(location=self.char1)
        item.db.desc = "Worn, not carried."
        self.char1.equipment.equip(item)
        spaced = WieldLocation.NECK.value.replace("_", " ")

        response = self.call(CmdInspect(), spaced)

        self.assertIn("Worn, not carried.", response)

    def test_an_empty_equipment_slot_says_what_is_bare(self):
        response = self.call(CmdInspect(), WieldLocation.BODY.value)

        self.assertIn(WieldLocation.BODY.label.lower(), response.lower())

    def test_a_bare_slot_still_finds_an_item_whose_name_it_prefixes(self):
        """Half the slot names are plausible item prefixes. Refusing `inspect
        head` outright would be refusing a headlamp sitting in the bag."""
        item = ITEM_DB[PLAIN_KEY].create(location=self.char1)
        item.key = "head lamp"
        item.db.desc = "Carried, not worn."
        self.char1.inventory.sync()

        response = self.call(CmdInspect(), WieldLocation.HEAD.value)

        self.assertIn("Carried, not worn.", response)

    def test_a_name_still_reaches_a_carried_item(self):
        item = ITEM_DB[EQUIPPABLE_KEY].create(location=self.char1)
        item.db.desc = "Named, not numbered."
        self.char1.inventory.sync()

        response = self.call(CmdInspect(), item.key)

        self.assertIn("Named, not numbered.", response)

    def test_a_name_reaches_an_equipped_item_too(self):
        """Equipped objects sit at location=None, so nothing finds them by
        name unless they are passed as candidates. Drawing a sword should not
        cost the player the ability to read it."""
        item = ITEM_DB[EQUIPPABLE_KEY].create(location=self.char1)
        item.db.desc = "Still readable once worn."
        self.char1.equipment.equip(item)

        response = self.call(CmdInspect(), item.key)

        self.assertIn("Still readable once worn.", response)

    def test_no_argument_asks_for_one(self):
        response = self.call(CmdInspect(), "")

        self.assertIn("usage", response.lower())

    # ─── By dbref, what the world pane sends ─────────────────────────────

    def _dbref(self, thing) -> str:
        # The neighbourhood cache keys on the room id, and each test gets
        # the same ids back. A tuple from an earlier test holds stale room
        # objects with the contents of that test. The real server
        # invalidates on room lifecycle, which no fixture here runs.
        neighbourhood.reset()
        self.addCleanup(neighbourhood.reset)

        return feed_const.ENTITY_DBREF_TEMPLATE.format(dbref=thing.id)

    def test_the_inspect_template_names_this_command(self):
        """The feed spells the verb without an import of this module."""
        self.assertEqual(feed_const.ENTITY_INSPECT_VERB, CmdInspect.key)
        self.assertTrue(feed_const.ENTITY_INSPECT_TEMPLATE.startswith(
            CmdInspect.key + " "))

    def test_inspect_never_walks_first(self):
        """The reach is the feed radius, so a walk would serve no purpose."""
        self.assertIn(CmdInspect.key, feed_const.SELF_APPROACHING_VERBS)

    def test_a_dbref_describes_a_thing_in_the_room(self):
        self.obj1.db.desc = "A thing on the ground, read from afar."

        response = self.call(CmdInspect(), self._dbref(self.obj1))

        self.assertIn("read from afar", response)

    def test_a_dbref_describes_a_carried_item(self):
        made = self._pile(count=1)
        made[0].db.desc = "A thing in the bag, read by dbref."

        response = self.call(CmdInspect(), self._dbref(made[0]))

        self.assertIn("read by dbref", response)

    def test_a_dbref_describes_a_worn_item(self):
        item = ITEM_DB[EQUIPPABLE_KEY].create(location=self.char1)
        item.db.desc = "A thing worn, read by dbref."
        self.char1.inventory.sync()
        self.char1.equipment.equip(item)

        response = self.call(CmdInspect(), self._dbref(item))

        self.assertIn("read by dbref", response)

    def test_a_dbref_out_of_sight_is_refused(self):
        """A dbref is global in Evennia. Here it is bounded by what the
        feed draws, so nobody can read a thing they cannot see."""
        self.obj2.db.desc = "A thing in another room."
        self.obj2.location = self.room2

        response = self.call(CmdInspect(), self._dbref(self.obj2))

        self.assertNotIn("another room", response)


class TestCmdInspectReach(EvenniaCommandTest):
    """`inspect #<id>` reaches as far as the feed draws, on the tile world.

    The rule is the one of `say`: a player can read each thing that the
    client draws. The edge is STATEFEED_ENTITY_RADIUS, read through the
    command's own constant, so a retune of the feed moves this test with it.
    """

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        radius = feed_const.STATEFEED_ENTITY_RADIUS
        span = (_ORIGIN[0] + radius + 1) // tile_const.CHUNK_SIZE + 1
        chunks = [_chunk(cx, cy) for cx in range(span) for cy in range(span)]
        self.world = TileWorld(chunks)
        self.world.load_rooms()
        set_world(self.world)
        self.addCleanup(set_world, None)
        self.edge = (_ORIGIN[0] + radius, _ORIGIN[1])
        self.past_edge = (_ORIGIN[0] + radius + 1, _ORIGIN[1])
        self._put(self.char1, _ORIGIN)

    def _put(self, thing, tile: tuple) -> None:
        rooms = self.world.plane(tile_const.GROUND_PLANE).rooms
        movement.place(rooms, thing, *tile, quiet=True)

    def _thing(self, tile: tuple):
        thing = create_object(DefaultObject, key="far thing")
        thing.db.desc = "Read from the edge of the feed."
        self._put(thing, tile)

        return thing

    def test_a_thing_at_the_edge_of_the_feed_is_read(self):
        thing = self._thing(self.edge)
        dbref = feed_const.ENTITY_DBREF_TEMPLATE.format(dbref=thing.id)

        response = self.call(CmdInspect(), dbref)

        self.assertIn("edge of the feed", response)

    def test_a_thing_past_the_edge_is_refused(self):
        thing = self._thing(self.past_edge)
        dbref = feed_const.ENTITY_DBREF_TEMPLATE.format(dbref=thing.id)

        response = self.call(CmdInspect(), dbref)

        self.assertNotIn("edge of the feed", response)


class TestCmdSwap(EvenniaCommandTest):
    """Rearranging the grid -- what a drag from one slot to another sends."""

    character_typeclass = BlackoutCharacter

    def test_swapping_two_occupied_slots_exchanges_them(self):
        first = ITEM_DB[PLAIN_KEY].create(location=self.char1)
        second = ITEM_DB[OTHER_PLAIN_KEY].create(location=self.char1)

        self.call(CmdSwap(), "1 2")

        self.assertEqual(self.char1.inventory.find_slot(first), 1)
        self.assertEqual(self.char1.inventory.find_slot(second), 0)

    def test_swapping_into_an_empty_slot_moves_the_item(self):
        item = ITEM_DB[PLAIN_KEY].create(location=self.char1)

        self.call(CmdSwap(), "1 20")

        self.assertEqual(self.char1.inventory.find_slot(item), 19)

    def test_one_argument_is_refused_with_usage(self):
        self.call(CmdSwap(), "1", "Usage: swap <slot> <slot>")

    def test_a_slot_outside_the_grid_is_refused(self):
        ITEM_DB[PLAIN_KEY].create(location=self.char1)

        self.call(CmdSwap(), "1 99", "Both slots must be numbers")

    def test_a_non_numeric_slot_is_refused(self):
        self.call(CmdSwap(), "1 sword", "Both slots must be numbers")


class TestCmdEquipWithTarget(EvenniaCommandTest):
    """equip <target> -- what a drag onto the paper doll sends."""

    character_typeclass = BlackoutCharacter

    def test_equipping_by_slot_number_equips_that_item(self):
        item = ITEM_DB[EQUIPPABLE_KEY].create(location=self.char1)

        self.call(CmdEquipment(), "1")

        self.assertTrue(self.char1.equipment.is_equipped(item))

    def test_equipping_by_name_equips_that_item(self):
        item = ITEM_DB[EQUIPPABLE_KEY].create(location=self.char1)

        self.call(CmdEquipment(), ITEM_DB[EQUIPPABLE_KEY].name)

        self.assertTrue(self.char1.equipment.is_equipped(item))

    def test_equipping_an_empty_slot_is_refused(self):
        self.call(CmdEquipment(), "5", "Slot 5 is empty")

    def test_equipping_a_slot_past_the_grid_is_refused(self):
        self.call(CmdEquipment(), "99", "You only have")

    def test_equipping_something_unequippable_is_refused(self):
        ITEM_DB[PLAIN_KEY].create(location=self.char1)

        self.call(CmdEquipment(), "1", "That item cannot be equipped")

    def test_an_equipped_item_leaves_the_carried_grid(self):
        item = ITEM_DB[EQUIPPABLE_KEY].create(location=self.char1)

        self.call(CmdEquipment(), "1")

        self.assertEqual(self.char1.inventory.find_slot(item), -1)


class TestCmdUnequip(EvenniaCommandTest):
    """unequip <target> -- what a drag off the paper doll sends."""

    character_typeclass = BlackoutCharacter

    def _equip(self):
        item = ITEM_DB[EQUIPPABLE_KEY].create(location=self.char1)
        self.char1.equipment.equip(item)

        return item

    def test_unequipping_by_slot_value_returns_the_item(self):
        item = self._equip()

        self.call(CmdUnequip(), WieldLocation.NECK.value)

        self.assertFalse(self.char1.equipment.is_equipped(item))

    def test_a_slot_may_be_typed_with_a_space_instead_of_an_underscore(self):
        item = ITEM_DB["rusty_scrap_shortsword"].create(location=self.char1)
        self.char1.equipment.equip(item)

        self.call(CmdUnequip(), "main hand")

        self.assertFalse(self.char1.equipment.is_equipped(item))

    def test_unequipping_by_item_name_works_though_search_cannot_see_it(self):
        """Equipped items are held at location=None, so caller.search finds
        nothing. The command needs its own lookup."""
        item = self._equip()

        self.call(CmdUnequip(), ITEM_DB[EQUIPPABLE_KEY].name)

        self.assertFalse(self.char1.equipment.is_equipped(item))

    def test_an_unequipped_item_returns_to_the_carried_grid(self):
        item = self._equip()

        self.call(CmdUnequip(), WieldLocation.NECK.value)

        self.assertGreaterEqual(self.char1.inventory.find_slot(item), 0)

    def test_unequipping_an_empty_slot_is_refused(self):
        self.call(CmdUnequip(), "body", "Nothing is equipped")

    def test_unequipping_something_not_worn_is_refused(self):
        self.call(
            CmdUnequip(), "toy sword", "You have nothing equipped called"
        )

    def test_no_argument_is_refused_with_usage(self):
        self.call(CmdUnequip(), "", "Usage: unequip <slot or item>")

    def test_the_usage_line_survives_the_ansi_parser(self):
        """A vertical bar in player-facing text is eaten as markup: "|i" made
        "<slot|item>" reach the player as "<slottem>"."""
        self.call(CmdUnequip(), "", "Usage: unequip <slot or item>")
