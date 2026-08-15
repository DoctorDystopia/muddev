"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/14/2026
Description: Tests for the loot delivery layer -- table resolution, spawning
             onto the floor, the stackable/non-stackable split, and the
             end-to-end path from a killing blow to items in the room.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.loot

The roll layer itself is covered by world/tests/test_loot_database.py with no
Evennia fixture at all; these are the cases that need real objects.
"""

from unittest import mock

from evennia.prototypes.prototypes import PROTOTYPE_TAG_CATEGORY
from evennia.utils.ansi import strip_ansi
from evennia.utils.test_resources import EvenniaTest

from systems.loot.drops import award_drops, resolve_table
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.npc_combat import spawn_mutant_raider
from world.loot_database import LootEntry, LootTableDef


# Private constant definitions

# A stackable item and a non-stackable one, named rather than discovered so a
# failure points at a specific definition. Mirrors world/tests/
# test_item_database.py, which picks its fixtures the same way.
_STACKABLE_KEY = "credits"
_NON_STACKABLE_KEY = "rusty_metal_chunk"

# Damage large enough to kill any fixture NPC outright.
_LETHAL_DAMAGE = 9999


class _FixedRandom:
    """A random.Random stand-in returning the low end of every range.

    Pins quantity rolls to their minimum so a delivery test asserts on an
    exact stack size without restating the roll layer's arithmetic.
    """

    def randint(self, low, high):
        return low


def _spawned_from(container, prototype_key):
    """Every object in `container` that ItemDef.create() made from a given def.

    Identity comes from the prototype TAG, not an attribute -- Evennia's
    spawner records origin as a tag under PROTOTYPE_TAG_CATEGORY
    (prototypes/spawner.py:1013) and writes no prototype_key attribute at all.
    """
    found = []

    for obj in container.contents:
        origins = obj.tags.get(category=PROTOTYPE_TAG_CATEGORY,
                               return_list=True)

        if prototype_key in origins:
            found.append(obj)

    return found


def _fixed_table(item_key, quantity=1):
    """A table that drops exactly one thing, every time, with no randomness."""
    return LootTableDef(
        key="fixture_drops",
        always=[LootEntry(item_key=item_key, min_quantity=quantity,
                          max_quantity=quantity)],
    )


class TestTableResolution(EvenniaTest):
    """Which table an NPC rolls, and what happens when it names none."""

    character_typeclass = BlackoutCharacter

    def test_npc_key_resolves_through_npc_db_to_loot_db(self):
        npc = spawn_mutant_raider(self.room1)

        table = resolve_table(npc)

        self.assertIsNotNone(table)
        self.assertEqual(table.key, "mutant_raider_drops")

    def test_instance_override_wins_over_the_npc_def(self):
        """A builder can give one unique NPC its own table."""
        npc = spawn_mutant_raider(self.room1)
        npc.db.loot_table_key = "big_mutant_drops"

        table = resolve_table(npc)

        self.assertEqual(table.key, "big_mutant_drops")

    def test_an_unstamped_object_resolves_to_no_table(self):
        npc = spawn_mutant_raider(self.room1)
        npc.db.npc_key = None

        table = resolve_table(npc)

        self.assertIsNone(table)

    def test_an_unknown_table_key_resolves_to_none_without_raising(self):
        npc = spawn_mutant_raider(self.room1)
        npc.db.loot_table_key = "no_such_table"

        table = resolve_table(npc)

        self.assertIsNone(table)

    def test_resolution_is_live_rather_than_stamped_at_spawn(self):
        """Editing a table plus a reload must reach NPCs already on the grid."""
        npc = spawn_mutant_raider(self.room1)

        with mock.patch.dict("world.loot_database.LOOT_DB",
                             {"mutant_raider_drops": _fixed_table("credits")}):
            table = resolve_table(npc)

        self.assertEqual(table.always[0].item_key, "credits")


class TestDelivery(EvenniaTest):
    """Rolled pairs become real objects on the floor of the death room."""

    character_typeclass = BlackoutCharacter

    def _kill_with_table(self, table, killer=None):
        """Award drops from `table` on a raider standing in room1."""
        npc = spawn_mutant_raider(self.room1)

        with mock.patch("systems.loot.drops.resolve_table",
                        return_value=table):
            delivered = award_drops(npc, killer, rng=_FixedRandom())

        return npc, delivered

    def _room_items(self, key):
        """Every object on the floor of room1 spawned from a given ItemDef."""
        found = _spawned_from(self.room1, key)

        return found

    def test_a_stackable_drop_becomes_one_object_carrying_the_quantity(self):
        table = _fixed_table(_STACKABLE_KEY, quantity=12)

        self._kill_with_table(table)

        items = self._room_items(_STACKABLE_KEY)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].db.quantity, 12)

    def test_a_non_stackable_drop_becomes_one_object_per_unit(self):
        """quantity=3 on a non-stackable must not yield one item claiming 3."""
        table = _fixed_table(_NON_STACKABLE_KEY, quantity=3)

        self._kill_with_table(table)

        items = self._room_items(_NON_STACKABLE_KEY)
        self.assertEqual(len(items), 3)

    def test_drops_land_in_the_room_not_on_the_killer(self):
        table = _fixed_table(_NON_STACKABLE_KEY)

        self._kill_with_table(table, killer=self.char1)

        self.assertEqual(len(self._room_items(_NON_STACKABLE_KEY)), 1)

        carried = _spawned_from(self.char1, _NON_STACKABLE_KEY)

        self.assertEqual(carried, [])

    def test_delivered_pairs_report_display_names(self):
        table = _fixed_table(_STACKABLE_KEY, quantity=5)

        _, delivered = self._kill_with_table(table)

        self.assertEqual(delivered, [("credits", 5)])

    def test_an_unknown_item_key_is_skipped_rather_than_raised(self):
        table = _fixed_table("no_such_item")

        _, delivered = self._kill_with_table(table)

        self.assertEqual(delivered, [])

    def test_a_valid_entry_still_lands_beside_a_skipped_one(self):
        table = LootTableDef(
            key="fixture_drops",
            always=[
                LootEntry(item_key="no_such_item"),
                LootEntry(item_key=_NON_STACKABLE_KEY),
            ],
        )

        _, delivered = self._kill_with_table(table)

        self.assertEqual(len(delivered), 1)
        self.assertEqual(len(self._room_items(_NON_STACKABLE_KEY)), 1)

    def test_no_table_drops_nothing(self):
        npc = spawn_mutant_raider(self.room1)
        before = len(self.room1.contents)

        with mock.patch("systems.loot.drops.resolve_table", return_value=None):
            delivered = award_drops(npc, self.char1)

        self.assertEqual(delivered, [])
        self.assertEqual(len(self.room1.contents), before)

    def test_an_empty_roll_drops_nothing(self):
        table = LootTableDef(key="fixture_drops")
        before = len(self.room1.contents)

        _, delivered = self._kill_with_table(table)

        self.assertEqual(delivered, [])
        # The raider itself is the only addition.
        self.assertEqual(len(self.room1.contents), before + 1)

    def test_a_locationless_npc_drops_nothing(self):
        npc = spawn_mutant_raider(self.room1)
        npc.location = None

        delivered = award_drops(npc, self.char1)

        self.assertEqual(delivered, [])


class TestAnnouncement(EvenniaTest):
    """The drop line, and when it is suppressed."""

    character_typeclass = BlackoutCharacter

    def _announce(self, table):
        npc = spawn_mutant_raider(self.room1)

        with mock.patch("systems.loot.drops.resolve_table",
                        return_value=table):
            with mock.patch.object(type(self.room1), "msg_contents") as mocked:
                award_drops(npc, self.char1, rng=_FixedRandom())

        return mocked

    def test_the_drop_line_names_the_item(self):
        table = _fixed_table(_NON_STACKABLE_KEY)

        mocked = self._announce(table)

        mocked.assert_called_once()
        line = strip_ansi(mocked.call_args[0][0])
        self.assertIn("rusty metal chunk", line)

    def test_a_quantity_above_one_is_suffixed(self):
        table = _fixed_table(_STACKABLE_KEY, quantity=12)

        mocked = self._announce(table)

        line = strip_ansi(mocked.call_args[0][0])
        self.assertIn("credits (x12)", line)

    def test_a_single_item_carries_no_suffix(self):
        table = _fixed_table(_NON_STACKABLE_KEY, quantity=1)

        mocked = self._announce(table)

        line = strip_ansi(mocked.call_args[0][0])
        self.assertNotIn("(x", line)

    def test_nothing_is_announced_when_nothing_dropped(self):
        table = LootTableDef(key="fixture_drops")

        mocked = self._announce(table)

        mocked.assert_not_called()

    def test_a_skipped_item_is_never_announced(self):
        """The line must not name something the player cannot pick up."""
        table = _fixed_table("no_such_item")

        mocked = self._announce(table)

        mocked.assert_not_called()


class TestDeathIntegration(EvenniaTest):
    """The whole path: killing blow -> drops on the floor -> NPC row gone."""

    character_typeclass = BlackoutCharacter

    def test_a_killing_blow_leaves_loot_and_deletes_the_npc(self):
        npc = spawn_mutant_raider(self.room1)
        table = _fixed_table(_NON_STACKABLE_KEY, quantity=2)

        with mock.patch("systems.loot.drops.resolve_table",
                        return_value=table):
            npc.at_damage(_LETHAL_DAMAGE, attacker=self.char1)

        dropped = _spawned_from(self.room1, _NON_STACKABLE_KEY)

        self.assertEqual(len(dropped), 2)
        self.assertIsNone(npc.pk)

    def test_loot_rolls_before_the_row_is_deleted(self):
        """respawn() deletes the NPC; drop_loot must have run first."""
        npc = spawn_mutant_raider(self.room1)
        seen = {}

        def _record(self_npc, killer=None):
            seen["pk_at_drop_time"] = self_npc.pk

        with mock.patch.object(type(npc), "drop_loot", _record):
            npc.at_damage(_LETHAL_DAMAGE, attacker=self.char1)

        self.assertIsNotNone(seen["pk_at_drop_time"])

    def test_a_broken_loot_table_does_not_block_the_death(self):
        """A raised drop must never leave a 0-hp corpse standing."""
        npc = spawn_mutant_raider(self.room1)

        with mock.patch("systems.loot.drops.award_drops",
                        side_effect=RuntimeError("boom")):
            npc.at_damage(_LETHAL_DAMAGE, attacker=self.char1)

        self.assertIsNone(npc.pk)

    def test_a_surviving_hit_drops_nothing(self):
        npc = spawn_mutant_raider(self.room1)
        before = len(self.room1.contents)

        npc.at_damage(1, attacker=self.char1)

        self.assertEqual(len(self.room1.contents), before)

    def test_the_base_hook_is_a_no_op_for_players(self):
        """Player death penalty is deliberately out of scope for now."""
        result = BlackoutCharacter.drop_loot(self.char1, self.char2)

        self.assertIsNone(result)
