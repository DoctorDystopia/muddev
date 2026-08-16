"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/15/2026
Description: Tests for the inventory snapshot payload.

             Evennia-backed rather than stand-in based, unlike test_emit.py.
             What is under test here is not routing but AGREEMENT: the payload
             has to describe the same grid the InventoryHandler and the
             EquipmentHandler actually hold, including after a stack merge and
             after an equip displaces something. A hand-built stand-in could
             only ever restate this module's own assumptions about those
             handlers, which is exactly what the tests need to check.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.statefeed
"""

from evennia.utils.test_resources import EvenniaTest

from items.equipment.constants import MAX_INVENTORY_SLOTS, WieldLocation
from systems.statefeed import constants as const
from systems.statefeed import inventory as feed_inventory
from world.item_database import ITEM_DB


# Public constant definitions

EQUIPPABLE_KEY = "glass_cannon_amulet"


# ─── Private helper routines ─────────────────────────────────────────────────

def _row_for(payload, name: str):
    """Return the carried row named `name`, or None."""
    for row in payload.items:
        if row["name"] == name:
            return row

    return None


def _commands(row) -> list:
    """Return just the command strings from a row's action list."""
    return [action["command"] for action in row["actions"]]


# ─── Test cases ──────────────────────────────────────────────────────────────

class TestInventorySnapshot(EvenniaTest):
    """The carried half of the payload."""

    def _carry(self, item_key: str, quantity: int = 1):
        return ITEM_DB[item_key].create(location=self.char1, quantity=quantity)

    def test_an_empty_inventory_reports_totals_and_no_rows(self):
        payload = feed_inventory.build_payload(self.char1)

        self.assertEqual(payload.slots_total, MAX_INVENTORY_SLOTS)
        self.assertEqual(payload.slots_used, 0)
        self.assertEqual(payload.items, [])
        self.assertEqual(payload.equipped, [])

    def test_a_carried_item_reports_its_slot_and_asset_key(self):
        self._carry("rusty_scrap_shortsword")

        payload = feed_inventory.build_payload(self.char1)
        row = _row_for(payload, ITEM_DB["rusty_scrap_shortsword"].name)

        self.assertIsNotNone(row)
        self.assertEqual(row["slot"], 0)
        self.assertEqual(row["asset"], "rusty_scrap_shortsword")

    def test_the_family_comes_from_the_item_database_tag_category(self):
        self._carry("rusty_scrap_shortsword")
        self._carry("glass_cannon_amulet")
        self._carry("rusty_metal_chunk")

        payload = feed_inventory.build_payload(self.char1)
        families = {row["name"]: row["family"] for row in payload.items}

        self.assertIn(const.ITEM_FAMILY_WEAPON, families.values())
        self.assertIn(const.ITEM_FAMILY_JEWELLERY, families.values())
        self.assertIn(const.ITEM_FAMILY_MATERIAL, families.values())

    def test_the_prototype_tag_is_not_mistaken_for_a_family(self):
        """Every spawned item also carries Evennia's from_prototype tag. A
        naive 'first category wins' would return that for everything."""
        self._carry("rusty_scrap_shortsword")

        payload = feed_inventory.build_payload(self.char1)
        row = _row_for(payload, ITEM_DB["rusty_scrap_shortsword"].name)

        self.assertEqual(row["family"], const.ITEM_FAMILY_WEAPON)

    def test_slots_used_counts_a_whole_stack_as_one(self):
        self._carry("credits", quantity=85)

        payload = feed_inventory.build_payload(self.char1)

        self.assertEqual(payload.slots_used, 1)

    def test_a_stack_reports_its_quantity(self):
        self._carry("credits", quantity=85)

        payload = feed_inventory.build_payload(self.char1)
        row = payload.items[0]

        self.assertEqual(row["quantity"], 85)
        self.assertTrue(row["stackable"])

    def test_a_merged_stack_is_one_row_carrying_the_total(self):
        """add_item merges by writing onto the surviving stack and deleting
        the incoming object. The snapshot must describe the survivor only."""
        self._carry("credits", quantity=10)
        self._carry("credits", quantity=15)

        payload = feed_inventory.build_payload(self.char1)

        self.assertEqual(len(payload.items), 1)
        self.assertEqual(payload.items[0]["quantity"], 25)

    def test_no_row_carries_a_null_id(self):
        """A slot pointing at a deleted object must be repaired by the sync
        build_payload performs, not shipped as a row of defaults."""
        item = self._carry("rusty_metal_chunk")
        self.char1.inventory.slots[5] = item.id + 9999

        payload = feed_inventory.build_payload(self.char1)

        for row in payload.items:
            self.assertIsNotNone(row["id"])


class TestInventoryActions(EvenniaTest):
    """The verbs the server names for each item."""

    def test_slot_numbers_in_commands_are_one_based(self):
        """The grid is 0-indexed internally and 1-indexed everywhere a player
        can see it. What the pane sends must match what `inventory` prints."""
        ITEM_DB["glass_cannon_amulet"].create(location=self.char1)

        payload = feed_inventory.build_payload(self.char1)
        row = payload.items[0]

        self.assertEqual(row["slot"], 0)
        self.assertIn("equip 1", _commands(row))

    def test_an_equippable_item_is_offered_equip(self):
        ITEM_DB["glass_cannon_amulet"].create(location=self.char1)

        payload = feed_inventory.build_payload(self.char1)
        row = payload.items[0]

        self.assertEqual(row["equip_slot"], WieldLocation.NECK.value)
        self.assertTrue(any(c.startswith("equip ") for c in _commands(row)))

    def test_a_non_equippable_item_is_not_offered_equip(self):
        ITEM_DB["rusty_metal_chunk"].create(location=self.char1)

        payload = feed_inventory.build_payload(self.char1)
        row = payload.items[0]

        self.assertEqual(row["equip_slot"], "")
        self.assertFalse(any(c.startswith("equip ") for c in _commands(row)))

    def test_every_item_can_be_dropped(self):
        ITEM_DB["rusty_metal_chunk"].create(location=self.char1)

        payload = feed_inventory.build_payload(self.char1)
        row = payload.items[0]
        expected = "drop " + ITEM_DB["rusty_metal_chunk"].name

        self.assertIn(expected, _commands(row))


class TestEquippedSnapshot(EvenniaTest):
    """The paper-doll half of the payload."""

    def test_an_equipped_item_moves_from_items_to_equipped(self):
        amulet = ITEM_DB["glass_cannon_amulet"].create(location=self.char1)
        self.char1.equipment.equip(amulet)

        payload = feed_inventory.build_payload(self.char1)

        self.assertEqual(payload.items, [])
        self.assertEqual(len(payload.equipped), 1)

    def test_an_equipped_row_is_slotted_by_wield_location(self):
        amulet = ITEM_DB["glass_cannon_amulet"].create(location=self.char1)
        self.char1.equipment.equip(amulet)

        payload = feed_inventory.build_payload(self.char1)
        row = payload.equipped[0]

        self.assertEqual(row["slot"], WieldLocation.NECK.value)

    def test_an_equipped_item_is_offered_unequip_by_slot(self):
        amulet = ITEM_DB["glass_cannon_amulet"].create(location=self.char1)
        self.char1.equipment.equip(amulet)

        payload = feed_inventory.build_payload(self.char1)
        row = payload.equipped[0]
        expected = "unequip " + WieldLocation.NECK.value

        self.assertIn(expected, _commands(row))

    def test_a_displaced_item_reappears_in_the_carried_grid(self):
        """Equipping into an occupied slot returns the old item to inventory.
        Both halves of the payload have to agree about where it went."""
        first = ITEM_DB["glass_cannon_amulet"].create(location=self.char1)
        second = ITEM_DB["glass_cannon_amulet"].create(location=self.char1)
        self.char1.equipment.equip(first)
        self.char1.equipment.equip(second)

        payload = feed_inventory.build_payload(self.char1)
        carried_ids = [row["id"] for row in payload.items]
        equipped_ids = [row["id"] for row in payload.equipped]

        self.assertIn(first.id, carried_ids)
        self.assertIn(second.id, equipped_ids)


class TestSlotFrames(EvenniaTest):
    """The empty-frame list the pane draws its paper doll from."""

    def test_every_wield_location_is_named(self):
        from items.equipment.constants import SLOT_DISPLAY_ORDER

        payload = feed_inventory.build_payload(self.char1)

        self.assertEqual(len(payload.equip_slots), len(SLOT_DISPLAY_ORDER))

    def test_frames_are_in_display_order(self):
        from items.equipment.constants import SLOT_DISPLAY_ORDER

        payload = feed_inventory.build_payload(self.char1)
        sent = [entry["slot"] for entry in payload.equip_slots]
        expected = [slot.value for slot in SLOT_DISPLAY_ORDER]

        self.assertEqual(sent, expected)

    def test_each_frame_carries_a_human_label(self):
        payload = feed_inventory.build_payload(self.char1)
        labels = {entry["slot"]: entry["label"] for entry in payload.equip_slots}

        self.assertEqual(labels[WieldLocation.MAIN_HAND.value], "Main Hand")

    def test_an_equipped_slot_value_matches_a_frame(self):
        """The pane looks an equipped row up by its slot string. If these two
        ever disagreed, worn gear would render into no frame at all."""
        amulet = ITEM_DB[EQUIPPABLE_KEY].create(location=self.char1)
        self.char1.equipment.equip(amulet)

        payload = feed_inventory.build_payload(self.char1)
        frames = [entry["slot"] for entry in payload.equip_slots]

        for row in payload.equipped:
            self.assertIn(row["slot"], frames)


class TestMissingHandlers(EvenniaTest):
    """The feed must not raise on an object that has no inventory."""

    def test_an_object_without_an_inventory_yields_no_payload(self):
        payload = feed_inventory.build_payload(self.obj1)

        self.assertIsNone(payload)
