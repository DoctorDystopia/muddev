"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/21/2026
Description: Tests for the item spawn: the item that the tile sync puts on
             its tile, the clock that starts when the item leaves, and the
             new item when the clock comes due (Nick, 10/21/2026).

The items come from the item list of the game (`spawn_items.item_rows`), one
that stacks and one that does not. No test names an item key. Each test
installs its own tile world (CLAUDE.md, "A test installs its own world").
No test sleeps: the sweep takes an injectable `now`.
"""

import random
import time

from evennia.utils.test_resources import EvenniaTestCase

from systems.core.tick.constants import TICK_SECONDS
from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid.world import TileWorld, set_world
from systems.gameplay.spawning import item_spawns, tile_sync
from systems.gameplay.spawning.respawn import ITEM_ENTRY_KEY, get_respawn_manager
from systems.interface.statefeed import spawn_items
from world.item_database import ITEM_DB
from world.object_kinds import ITEM_SPAWN_KIND, SIGNPOST_KIND, UNPINNED_KINDS


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = tile_const.CHUNK_SIZE

# The tile of the spawn, and a tile that a picked-up item goes to.
_SPAWN_TILE = (5, 5)
_AWAY_TILE = (8, 8)

# A rotation that is not the default, so a lost facing shows.
_TURN = 2

# The look of the spawn object.
_LOOK = {tile_const.LOOK_SCALE_KEY: 150}

# The respawn of each spawn, in ticks.
_RESPAWN_TICKS = 100

# The quantity range of the spawn of the item that stacks.
_RANGE = [3, 9]

# The seed of the quantity roll, and how many rolls the range test makes.
_SEED = 20261021
_ROLLS = 20

# A margin of the clock, in seconds, on each side of a deadline.
_MARGIN = 1

# The words of a sign that takes the tile of a spawn.
_SIGN_TEXT = "Taken"


def _plain_item(stacks: bool) -> str:
    """
    Return the key of the first item of the item list that stacks or not,
    and that the item typeclasses make. A corpse and a tool of the staff
    have their own rules.
    """
    for row in spawn_items.item_rows():
        item_def = ITEM_DB[row["key"]]

        if row["stackable"] == stacks and item_def.typeclass.startswith(
                "typeclasses.items."):
            return row["key"]

    raise LookupError(stacks)


_STACKED = _plain_item(True)
_SINGLE = _plain_item(False)


# ─── Private helper routines ─────────────────────────────────────────────────

def _spawn(item_key: str, quantity: list = None) -> dict:
    """A spawn of `item_key` that the chunk file reader accepts."""
    spawn = {tile_const.SPAWN_ITEM_KEY: item_key}

    if quantity:
        spawn[tile_const.SPAWN_QUANTITY_KEY] = list(quantity)

    spawn[tile_const.SPAWN_RESPAWN_KEY] = _RESPAWN_TICKS

    return spawn


def _world(spawns: list, others: list = ()) -> TileWorld:
    """
    A loaded one-chunk world with an item spawn object for each spawn, and
    each ChunkObject of `others` after them.
    """
    tile_count = _SIZE * _SIZE
    chunk = chunkfile.ChunkFile(
        cx=0, cy=0, plane=0, floor_names=["sand"], area_names=["oasis"],
        heights=[0] * tile_const.CORNERS_PER_SIDE ** 2,
        floors=[0] * tile_count, flags=[0] * tile_count,
        areas=[0] * tile_count,
        objects=[chunkfile.ChunkObject(ITEM_SPAWN_KIND, *_SPAWN_TILE, _TURN,
                                       look=dict(_LOOK), spawn=spawn)
                 for spawn in spawns] + list(others))
    world = TileWorld([chunk], unpinned=UNPINNED_KINDS)
    world.rooms.load()

    return world


def _marked(room, item_key: str) -> list:
    """Return each item in `room` that the spawn of `item_key` put down."""
    return [obj for obj in room.contents
            if obj.attributes.get(tile_const.SPAWN_ITEM_ATTR) == item_key]


def _respawn_seconds() -> int:
    """The respawn of each test spawn in whole seconds."""
    return int(round(_RESPAWN_TICKS * TICK_SECONDS))


# ─── Tests ───────────────────────────────────────────────────────────────────

class ItemSpawnTests(EvenniaTestCase):

    def _install(self, spawns: list) -> TileWorld:
        """Install a world of `spawns`, sync it, and return it."""
        world = _world(spawns)
        set_world(world)
        self.addCleanup(set_world, None)
        tile_sync.apply(world, tile_sync.plan(world))

        return world

    def _pick_up(self, world, item):
        """Move `item` off its tile, as a `get` does. Return the room."""
        away = world.rooms.ensure_room(*_AWAY_TILE)
        item.move_to(away, quiet=True)

        return away

    def test_the_sync_puts_the_item_on_its_tile(self):
        world = self._install([_spawn(_STACKED, _RANGE)])
        room = world.rooms.room_at(*_SPAWN_TILE)
        items = _marked(room, _STACKED)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].attributes.get(tile_const.FACING_ATTR), _TURN)
        self.assertEqual(items[0].attributes.get(tile_const.LOOK_ATTR), _LOOK)
        self.assertIn(items[0].attributes.get("quantity"),
                      range(_RANGE[0], _RANGE[1] + 1))

    def test_the_sync_records_the_item_in_the_kind_list(self):
        world = self._install([_spawn(_STACKED)])
        room = world.rooms.room_at(*_SPAWN_TILE)
        entry = ITEM_SPAWN_KIND + tile_sync.ENTRY_TEXT_SEPARATOR + _STACKED

        self.assertEqual(room.attributes.get(tile_sync.TILE_KINDS_ATTR), [entry])

    def test_a_second_sync_adds_no_item(self):
        world = self._install([_spawn(_STACKED)])
        actions = tile_sync.plan(world)
        tile_sync.apply(world, actions)
        room = world.rooms.room_at(*_SPAWN_TILE)

        self.assertEqual(actions[0].verb, tile_sync.VERB_REFRESH)
        self.assertEqual(len(_marked(room, _STACKED)), 1)

    def test_a_pickup_starts_the_clock_and_frees_the_item(self):
        world = self._install([_spawn(_STACKED)])
        room = world.rooms.room_at(*_SPAWN_TILE)
        item = _marked(room, _STACKED)[0]
        before = time.time()
        self._pick_up(world, item)
        entries = [entry for entry in get_respawn_manager()._read_queue()
                   if entry.get(ITEM_ENTRY_KEY) == _STACKED]

        for attr in (tile_const.SPAWN_ITEM_ATTR, tile_const.FACING_ATTR,
                     tile_const.LOOK_ATTR):
            with self.subTest(attr=attr):
                self.assertFalse(item.attributes.has(attr))

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["room"], room)
        self.assertGreaterEqual(entries[0]["due_at"],
                                before + _respawn_seconds())

    def test_the_clock_brings_a_new_item_when_it_comes_due(self):
        world = self._install([_spawn(_STACKED)])
        room = world.rooms.room_at(*_SPAWN_TILE)
        self._pick_up(world, _marked(room, _STACKED)[0])
        due = time.time() + _respawn_seconds()
        manager = get_respawn_manager()

        self.assertEqual(manager.sweep(now=due - _respawn_seconds()), 0)
        self.assertEqual(_marked(room, _STACKED), [])
        self.assertEqual(manager.sweep(now=due + _MARGIN), 1)
        self.assertEqual(len(_marked(room, _STACKED)), 1)
        self.assertFalse(manager.is_item_queued(_STACKED, room))

    def test_a_new_item_gets_the_facing_and_the_look_of_its_object(self):
        world = self._install([_spawn(_STACKED)])
        room = world.rooms.room_at(*_SPAWN_TILE)
        self._pick_up(world, _marked(room, _STACKED)[0])
        get_respawn_manager().sweep(now=time.time() + _respawn_seconds()
                                    + _MARGIN)
        item = _marked(room, _STACKED)[0]

        self.assertEqual(item.attributes.get(tile_const.FACING_ATTR), _TURN)
        self.assertEqual(item.attributes.get(tile_const.LOOK_ATTR), _LOOK)

    def test_a_sync_during_the_clock_puts_no_item(self):
        world = self._install([_spawn(_STACKED)])
        room = world.rooms.room_at(*_SPAWN_TILE)
        self._pick_up(world, _marked(room, _STACKED)[0])
        tile_sync.apply(world, tile_sync.plan(world))

        self.assertEqual(_marked(room, _STACKED), [])
        self.assertTrue(get_respawn_manager().is_item_queued(_STACKED, room))

    def test_a_dropped_item_of_the_same_kind_does_not_stop_the_clock(self):
        # A player who drops the item back on the tile drops a plain item.
        world = self._install([_spawn(_STACKED)])
        room = world.rooms.room_at(*_SPAWN_TILE)
        item = _marked(room, _STACKED)[0]
        self._pick_up(world, item)
        item.move_to(room, quiet=True)
        get_respawn_manager().sweep(now=time.time() + _respawn_seconds()
                                    + _MARGIN)

        self.assertEqual(len(_marked(room, _STACKED)), 1)
        self.assertIn(item, room.contents)

    def test_a_spawn_that_the_file_lost_gives_no_item(self):
        world = self._install([_spawn(_STACKED)])
        room = world.rooms.room_at(*_SPAWN_TILE)
        self._pick_up(world, _marked(room, _STACKED)[0])
        set_world(_world([_spawn(_SINGLE)]))
        get_respawn_manager().sweep(now=time.time() + _respawn_seconds()
                                    + _MARGIN)

        self.assertEqual(_marked(room, _STACKED), [])
        self.assertFalse(get_respawn_manager().is_item_queued(_STACKED, room))

    def test_a_new_item_on_the_tile_is_a_refresh_that_swaps_the_item(self):
        world = self._install([_spawn(_STACKED)])
        room = world.rooms.room_at(*_SPAWN_TILE)
        edited = _world([_spawn(_SINGLE)])
        set_world(edited)
        actions = tile_sync.plan(edited)
        tile_sync.apply(edited, actions)

        self.assertEqual(actions[0].verb, tile_sync.VERB_REFRESH)
        self.assertEqual(_marked(room, _STACKED), [])
        self.assertEqual(len(_marked(room, _SINGLE)), 1)

    def test_a_new_item_drops_the_clock_of_the_old_item(self):
        world = self._install([_spawn(_STACKED)])
        room = world.rooms.room_at(*_SPAWN_TILE)
        self._pick_up(world, _marked(room, _STACKED)[0])
        edited = _world([_spawn(_SINGLE)])
        set_world(edited)
        tile_sync.apply(edited, tile_sync.plan(edited))

        self.assertFalse(get_respawn_manager().is_item_queued(_STACKED, room))

    def test_a_removed_spawn_takes_its_item_and_its_clock(self):
        world = self._install([_spawn(_STACKED), _spawn(_SINGLE)])
        room = world.rooms.room_at(*_SPAWN_TILE)
        self._pick_up(world, _marked(room, _STACKED)[0])
        emptied = _world([])
        set_world(emptied)
        actions = tile_sync.plan(emptied)
        tile_sync.apply(emptied, actions)

        self.assertEqual(actions[0].verb, tile_sync.VERB_REMOVED)
        self.assertEqual(_marked(room, _SINGLE), [])
        self.assertFalse(get_respawn_manager().is_item_queued(_STACKED, room))

    def test_a_changed_tile_drops_the_clock_and_keeps_its_room(self):
        # A sign takes the tile. The room stays on it, so a clock that
        # stays would put the item down beside the sign.
        world = self._install([_spawn(_STACKED)])
        room = world.rooms.room_at(*_SPAWN_TILE)
        self._pick_up(world, _marked(room, _STACKED)[0])
        sign = chunkfile.ChunkObject(SIGNPOST_KIND, *_SPAWN_TILE,
                                     text=_SIGN_TEXT)
        changed = _world([], [sign])
        set_world(changed)
        actions = tile_sync.plan(changed)
        tile_sync.apply(changed, actions)

        self.assertEqual(actions[0].verb, tile_sync.VERB_CHANGED)
        self.assertEqual(changed.rooms.room_at(*_SPAWN_TILE).pk, room.pk)
        self.assertFalse(get_respawn_manager().is_item_queued(_STACKED, room))
        get_respawn_manager().sweep(now=time.time() + _respawn_seconds()
                                    + _MARGIN)
        self.assertEqual(_marked(room, _STACKED), [])


class QuantityTests(EvenniaTestCase):

    def setUp(self):
        super().setUp()
        self.world = _world([])
        set_world(self.world)
        self.room = self.world.rooms.ensure_room(*_SPAWN_TILE)

    def tearDown(self):
        set_world(None)
        super().tearDown()

    def test_each_roll_stays_in_the_range(self):
        rng = random.Random(_SEED)
        spawn = _spawn(_STACKED, _RANGE)
        rolled = set()

        for _roll in range(_ROLLS):
            item = item_spawns.place(self.room, spawn, rng=rng)
            rolled.add(item.attributes.get("quantity"))
            item.delete()

        self.assertLessEqual(rolled, set(range(_RANGE[0], _RANGE[1] + 1)))
        self.assertGreater(len(rolled), 1)

    def test_an_item_that_does_not_stack_comes_one_at_a_time(self):
        # tile_checks refuses the range. This is the guard of a hand edit.
        item_spawns.place(self.room, _spawn(_SINGLE, _RANGE),
                          rng=random.Random(_SEED))

        self.assertEqual(len(_marked(self.room, _SINGLE)), 1)

    def test_an_unknown_item_gives_nothing(self):
        found = item_spawns.place(self.room, _spawn(_STACKED + "_missing"))

        self.assertIsNone(found)
        self.assertEqual(list(self.room.contents), [])
