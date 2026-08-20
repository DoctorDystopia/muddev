"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/17/2026
Description: Regression tests for DropCmd -- dropping a duplicate-named
             carried item (several unstacked instances sharing one name)
             must resolve without forcing the player, or the 3D pane's
             right-click Drop action, to supply a disambiguating suffix.

Run with:
    evennia test --settings settings.py commands.tests.test_drop_cmd
"""

from evennia.utils.test_resources import EvenniaCommandTest

from commands.drop_cmds import DropCmd, _is_single_stacked_group
from typeclasses.characters import Character as BlackoutCharacter
from world.item_database import ITEM_DB

# Public constant definitions

NON_STACKABLE_KEY = "hammer"
DUPLICATE_DROP_KEY = "rusty_metal_chunk"
DUPLICATE_DROP_COUNT = 8


class TestDropCmdBySlot(EvenniaCommandTest):
    """
    The form the 3D pane sends.

    Right-clicking the eighth of eight identical chunks must drop THAT
    chunk. The pane used to send a bare name, which the server resolved
    to the lowest-numbered copy -- so every right-click dropped the first
    item regardless of which one was clicked.

    Author: Nick Hobar
    Creation date: 08/17/2026
    """

    character_typeclass = BlackoutCharacter

    def _carry_duplicates(self, count=DUPLICATE_DROP_COUNT):
        """Carry `count` identical chunks and return them in slot order."""
        item_def = ITEM_DB[DUPLICATE_DROP_KEY]
        for _ in range(count):
            item_def.create(location=self.char1)

        handler = self.char1.inventory
        handler.sync()

        return [item for _slot, item in handler.all_items()]

    def test_dropping_a_slot_drops_the_item_in_that_slot(self):
        carried = self._carry_duplicates()
        wanted = carried[-1]

        self.call(DropCmd(), str(DUPLICATE_DROP_COUNT), caller=self.char1)

        self.assertEqual(wanted.location, self.room1)

    def test_dropping_a_slot_leaves_every_other_copy_carried(self):
        carried = self._carry_duplicates()
        wanted = carried[-1]

        self.call(DropCmd(), str(DUPLICATE_DROP_COUNT), caller=self.char1)

        for item in carried:
            if item.id == wanted.id:
                continue
            self.assertEqual(item.location, self.char1)

    def test_dropping_a_middle_slot_picks_that_one_not_the_first(self):
        """The regression proper: slot 4 of 8 is neither first nor last, so
        an off-by-anything resolves to the wrong object."""
        carried = self._carry_duplicates()
        wanted = carried[3]

        self.call(DropCmd(), "4", caller=self.char1)

        self.assertEqual(wanted.location, self.room1)
        self.assertEqual(carried[0].location, self.char1)

    def test_an_empty_slot_is_reported_rather_than_dropping_something_else(self):
        self._carry_duplicates(count=2)

        response = self.call(DropCmd(), "20", caller=self.char1)

        self.assertIn("empty", response.lower())
        self.assertEqual(self.char1.inventory.count_used(), 2)

    def test_a_slot_past_the_grid_falls_through_to_the_name_path(self):
        """`drop 99` is not a slot, so it must fail as a missing target
        rather than being silently treated as one."""
        self._carry_duplicates(count=2)

        response = self.call(DropCmd(), "99", caller=self.char1)

        self.assertIn("aren't carrying", response.lower())
        self.assertEqual(self.char1.inventory.count_used(), 2)

    def test_the_count_form_still_drops_that_many(self):
        """`drop 3 <name>` is a count, not a slot -- parse() splits it off
        before func() ever sees it."""
        self._carry_duplicates()
        item_def = ITEM_DB[DUPLICATE_DROP_KEY]

        self.call(DropCmd(), f"3 {item_def.name}", caller=self.char1)

        on_ground = self.room1.search(
            item_def.name, location=self.room1, quiet=True
        )
        self.assertEqual(len(on_ground), 3)
        self.assertEqual(
            self.char1.inventory.count_used(), DUPLICATE_DROP_COUNT - 3
        )


class TestDropCmdDuplicateCarriedItems(EvenniaCommandTest):
    """
    Purpose: Reproduces the bug report -- a character carrying several
    separate instances of the same non-stackable item (e.g. eight "rusty
    metal chunk" objects) cannot right-click Drop from the 3D webclient,
    because the pane sends a bare `drop <name>` and vanilla CmdDrop treats
    that as an unresolvable multimatch. A bare `drop <name>` must resolve
    to the lowest-numbered instance instead.

    Author: Nick Hobar
    Creation date: 08/17/2026
    """

    character_typeclass = BlackoutCharacter

    def test_drop_with_no_count_resolves_to_lowest_numbered_duplicate(self):
        item_def = ITEM_DB[DUPLICATE_DROP_KEY]
        for _ in range(DUPLICATE_DROP_COUNT):
            item_def.create(location=self.char1)

        response = self.call(DropCmd(), item_def.name, caller=self.char1)

        self.assertNotIn("you carry more than one", response.lower())
        self.assertIn("drop", response.lower())
        carried = self.char1.search(item_def.name, location=self.char1, quiet=True)
        self.assertEqual(len(carried), DUPLICATE_DROP_COUNT - 1)
        on_ground = self.room1.search(item_def.name, location=self.room1, quiet=True)
        self.assertEqual(len(on_ground), 1)

    def test_drop_single_item_still_works(self):
        ITEM_DB[NON_STACKABLE_KEY].create(location=self.char1)

        response = self.call(DropCmd(), NON_STACKABLE_KEY, caller=self.char1)

        self.assertIn("drop", response.lower())
        dropped = self.room1.search(NON_STACKABLE_KEY, location=self.room1, quiet=True)
        self.assertEqual(len(dropped), 1)

    def test_drop_leaves_the_grid_consistent_with_the_text_view(self):
        """The state-feed snapshot published from at_object_leave must
        describe the inventory AFTER the drop.

        move_to calls at_object_leave before it reassigns the object's
        location, so the dropped chunk is still in contents while the
        hook runs. Without InventoryHandler.sync's `ignore`, sync()
        re-adopts it into the slot remove_item just cleared and the
        pane is told nothing changed.
        """
        item_def = ITEM_DB[DUPLICATE_DROP_KEY]
        for _ in range(DUPLICATE_DROP_COUNT):
            item_def.create(location=self.char1)

        self.call(DropCmd(), item_def.name, caller=self.char1)

        handler = self.char1.inventory
        self.assertEqual(handler.count_used(), DUPLICATE_DROP_COUNT - 1)
        carried_ids = {item.id for _slot, item in handler.all_items()}
        on_ground = self.room1.search(
            item_def.name, location=self.room1, quiet=True
        )
        self.assertEqual(len(on_ground), 1)
        self.assertNotIn(on_ground[0].id, carried_ids)


class TestIsSingleStackedGroupForDrop(EvenniaCommandTest):
    """
    Purpose: Unit-tests `_is_single_stacked_group` directly, mirroring
    commands/tests/test_get_cmd.py's coverage of the identical helper on
    the `get` side.

    Author: Nick Hobar
    Creation date: 08/17/2026
    """

    character_typeclass = BlackoutCharacter

    def test_true_for_two_identical_duplicates(self):
        item_def = ITEM_DB[DUPLICATE_DROP_KEY]
        first = item_def.create(location=self.char1)
        second = item_def.create(location=self.char1)

        self.assertTrue(_is_single_stacked_group(self.char1, [first, second]))

    def test_false_for_a_single_match(self):
        item_def = ITEM_DB[DUPLICATE_DROP_KEY]
        only = item_def.create(location=self.char1)

        self.assertFalse(_is_single_stacked_group(self.char1, [only]))

    def test_false_for_distinct_items(self):
        chunk = ITEM_DB[DUPLICATE_DROP_KEY].create(location=self.char1)
        hammer = ITEM_DB[NON_STACKABLE_KEY].create(location=self.char1)

        self.assertFalse(_is_single_stacked_group(self.char1, [chunk, hammer]))
