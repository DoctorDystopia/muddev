"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: Tests for the tile sync: the plan, each of its four verbs, the
             facing of each entity, and the decor rules. The kinds come from
             the kind table by category, not by name.
"""

import os
import tempfile

from evennia.utils.test_resources import EvenniaTestCase

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid.world import TileWorld, load_world
from systems.gameplay.spawning import tile_sync
from world.object_kinds import OBJECT_KINDS, UNPINNED_KINDS


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = tile_const.CHUNK_SIZE


def _first_of(category: str) -> str:
    """Return the first kind key of a category."""
    for key, kind in OBJECT_KINDS.items():
        if kind.category == category:
            return key

    raise LookupError(category)


_FACILITY = _first_of(tile_const.OBJECT_CATEGORY_FACILITY)
_SIGN = _first_of(tile_const.OBJECT_CATEGORY_SIGN)
_TRANSITION = _first_of(tile_const.OBJECT_CATEGORY_TRANSITION)
_DECOR = _first_of(tile_const.OBJECT_CATEGORY_DECOR)

# The tiles of the test world.
_FACILITY_TILE = (4, 4)
_TRANSITION_TILE = (9, 9)
_DECOR_TILE = (6, 6)

# The words of the sign, before and after an edit.
_WORDS = "Bank"
_NEW_WORDS = "Old Bank"

# The kind list entry of the sign.
_SIGN_ENTRY = _SIGN + tile_sync.ENTRY_TEXT_SEPARATOR + _WORDS

# Two different quarter turns, so a swapped facing shows.
_FACILITY_TURN = 3
_SIGN_TURN = 1


# ─── Private helper routines ─────────────────────────────────────────────────

def _chunk(objects: list) -> chunkfile.ChunkFile:
    """
    One chunk file with these (kind, x, y, text) objects. A fifth item gives
    the rotation of an object.
    """
    tile_count = _SIZE * _SIZE

    return chunkfile.ChunkFile(
        cx=0, cy=0, plane=0, floor_names=["sand"], area_names=["oasis"],
        heights=[0] * tile_const.CORNERS_PER_SIDE ** 2,
        floors=[0] * tile_count, flags=[0] * tile_count,
        areas=[0] * tile_count,
        objects=[chunkfile.ChunkObject(kind, x, y, turn[0] if turn else 0,
                                       text=text)
                 for kind, x, y, text, *turn in objects])


def _world(objects: list) -> TileWorld:
    """A loaded one-chunk world of `_chunk(objects)`, with the real pin rule."""
    world = TileWorld([_chunk(objects)], unpinned=UNPINNED_KINDS)
    world.rooms.load()

    return world


def _placed(words: str = _WORDS, facility_turn: int = 0, sign_turn: int = 0):
    """The standard objects: a signed facility, and a lone transition."""
    return [(_FACILITY, *_FACILITY_TILE, "", facility_turn),
            (_SIGN, *_FACILITY_TILE, words, sign_turn),
            (_TRANSITION, *_TRANSITION_TILE, "")]


def _facings(room) -> dict:
    """Return "sign" and "facility" -> the facing of that entity in `room`."""
    found = {}

    for thing in room.contents:
        role = "sign" if getattr(thing, "world_label", "") else "facility"
        found[role] = thing.attributes.get(tile_const.FACING_ATTR)

    return found


def _verbs(actions) -> dict:
    return {action.tile: action.verb for action in actions}


# ─── Tests ───────────────────────────────────────────────────────────────────

class TileSyncTests(EvenniaTestCase):

    def test_a_fresh_world_plans_new_tiles_and_skips_a_transition(self):
        world = _world(_placed())
        actions = tile_sync.plan(world)

        self.assertEqual(_verbs(actions), {_FACILITY_TILE: tile_sync.VERB_NEW})
        self.assertEqual(actions[0].kinds, (_FACILITY, _SIGN_ENTRY))

    def test_the_plan_changes_nothing(self):
        world = _world(_placed())
        tile_sync.plan(world)

        self.assertIsNone(world.rooms.room_at(*_FACILITY_TILE))

    def test_apply_stands_up_each_kind_and_records_it(self):
        world = _world(_placed())
        tile_sync.apply(world, tile_sync.plan(world))
        room = world.rooms.room_at(*_FACILITY_TILE)

        self.assertIsNotNone(room)
        self.assertTrue(room.contents)
        self.assertEqual(room.attributes.get(tile_sync.TILE_KINDS_ATTR),
                         [_FACILITY, _SIGN_ENTRY])

    def test_a_second_run_is_a_refresh_that_adds_nothing(self):
        world = _world(_placed())
        tile_sync.apply(world, tile_sync.plan(world))
        room = world.rooms.room_at(*_FACILITY_TILE)
        before = len(room.contents)
        actions = tile_sync.plan(world)
        tile_sync.apply(world, actions)

        self.assertEqual(_verbs(actions),
                         {_FACILITY_TILE: tile_sync.VERB_REFRESH})
        self.assertEqual(len(room.contents), before)

    def test_a_new_kind_list_is_a_change(self):
        world = _world(_placed())
        tile_sync.apply(world, tile_sync.plan(world))
        edited = _world([(_FACILITY, *_FACILITY_TILE, "")])
        actions = tile_sync.plan(edited)
        tile_sync.apply(edited, actions)
        room = edited.rooms.room_at(*_FACILITY_TILE)

        self.assertEqual(_verbs(actions),
                         {_FACILITY_TILE: tile_sync.VERB_CHANGED})
        self.assertEqual(room.attributes.get(tile_sync.TILE_KINDS_ATTR),
                         [_FACILITY])

    def test_new_words_are_a_refresh_that_keeps_the_facility(self):
        # A typo fix on a sign must not demolish the facility beside it.
        world = _world(_placed())
        tile_sync.apply(world, tile_sync.plan(world))
        before = set(world.rooms.room_at(*_FACILITY_TILE).contents)
        edited = _world(_placed(_NEW_WORDS))
        actions = tile_sync.plan(edited)
        destroyed = tile_sync.apply(edited, actions)
        room = edited.rooms.room_at(*_FACILITY_TILE)
        labels = [thing.world_label for thing in room.contents
                  if getattr(thing, "world_label", "")]

        self.assertEqual(_verbs(actions),
                         {_FACILITY_TILE: tile_sync.VERB_REFRESH})
        self.assertEqual(destroyed, 0)
        self.assertEqual(set(room.contents), before)
        self.assertEqual(labels, [_NEW_WORDS])
        self.assertEqual(room.attributes.get(tile_sync.TILE_KINDS_ATTR),
                         [_FACILITY, _SIGN_ENTRY.replace(_WORDS, _NEW_WORDS)])

    def test_a_sign_that_loses_its_words_is_a_change(self):
        # place_signpost cannot take words away, so only a demolish can.
        world = _world(_placed())
        tile_sync.apply(world, tile_sync.plan(world))
        edited = _world(_placed(""))
        actions = tile_sync.plan(edited)

        self.assertEqual(_verbs(actions),
                         {_FACILITY_TILE: tile_sync.VERB_CHANGED})

    def test_a_tile_that_lost_every_kind_is_cleared_and_released(self):
        world = _world(_placed())
        tile_sync.apply(world, tile_sync.plan(world))
        emptied = _world([])
        actions = tile_sync.plan(emptied)
        tile_sync.apply(emptied, actions)

        self.assertEqual(_verbs(actions),
                         {_FACILITY_TILE: tile_sync.VERB_REMOVED})
        self.assertIsNone(emptied.rooms.room_at(*_FACILITY_TILE))

    def test_a_placed_tile_is_pinned(self):
        world = _world(_placed())
        tile_sync.apply(world, tile_sync.plan(world))
        room = world.rooms.room_at(*_FACILITY_TILE)

        for thing in list(room.contents):
            thing.delete()

        self.assertFalse(world.rooms.release(room))
        self.assertIs(world.rooms.room_at(*_FACILITY_TILE), room)

    def test_apply_gives_each_entity_the_turn_of_its_object(self):
        world = _world(_placed(facility_turn=_FACILITY_TURN,
                               sign_turn=_SIGN_TURN))
        tile_sync.apply(world, tile_sync.plan(world))
        room = world.rooms.room_at(*_FACILITY_TILE)

        self.assertEqual(_facings(room), {"facility": _FACILITY_TURN,
                                          "sign": _SIGN_TURN})

    def test_a_turn_alone_is_a_refresh_that_turns_the_entity(self):
        # The editor Turn changes no kind, so nothing may be demolished.
        world = _world(_placed())
        tile_sync.apply(world, tile_sync.plan(world))
        before = set(world.rooms.room_at(*_FACILITY_TILE).contents)
        turned = _world(_placed(facility_turn=_FACILITY_TURN))
        actions = tile_sync.plan(turned)
        destroyed = tile_sync.apply(turned, actions)
        room = turned.rooms.room_at(*_FACILITY_TILE)

        self.assertEqual(_verbs(actions),
                         {_FACILITY_TILE: tile_sync.VERB_REFRESH})
        self.assertEqual(destroyed, 0)
        self.assertEqual(set(room.contents), before)
        self.assertEqual(_facings(room)["facility"], _FACILITY_TURN)

    def test_an_action_with_no_facings_stamps_nothing(self):
        world = _world(_placed())
        actions = [tile_sync.TileAction(action.tile, action.verb, action.kinds,
                                        action.previous, action.plane)
                   for action in tile_sync.plan(world)]
        tile_sync.apply(world, actions)
        room = world.rooms.room_at(*_FACILITY_TILE)

        self.assertTrue(room.contents)
        self.assertEqual(_facings(room), {"facility": None, "sign": None})


class DecorTests(EvenniaTestCase):
    """DESIGN-0013 section 6.5: decor stands nothing up and pins nothing."""

    def test_the_sync_stands_nothing_up_for_decor(self):
        world = _world([(_DECOR, *_DECOR_TILE, "")])

        self.assertEqual(tile_sync.plan(world), [])

    def test_a_tile_of_decor_alone_is_not_pinned(self):
        world = _world([(_DECOR, *_DECOR_TILE, "")])

        self.assertFalse(world.rooms.is_pinned(*_DECOR_TILE))

    def test_decor_beside_a_facility_keeps_the_pin(self):
        world = _world([(_DECOR, *_FACILITY_TILE, ""),
                        (_FACILITY, *_FACILITY_TILE, "")])

        self.assertTrue(world.rooms.is_pinned(*_FACILITY_TILE))

    def test_the_world_of_the_server_pins_no_decor(self):
        # load_world gives the kinds itself, so a server start and the
        # operator script share the rule.
        chunk_file = _chunk([(_DECOR, *_DECOR_TILE, ""),
                             (_FACILITY, *_FACILITY_TILE, "")])

        with tempfile.TemporaryDirectory() as directory:
            chunkfile.write_file(os.path.join(directory, chunk_file.file_name()),
                                 chunk_file)
            world = load_world(directory)

        self.assertFalse(world.rooms.is_pinned(*_DECOR_TILE))
        self.assertTrue(world.rooms.is_pinned(*_FACILITY_TILE))
