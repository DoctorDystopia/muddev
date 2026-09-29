"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/25/2026
Description: The cutover of DESIGN-0011 Phase 4b. It moves every character
             from the xyzgrid maps to the tile world. Then it deletes the
             xyzgrid rooms, their exits, and the grid Script.

Why an operator step
--------------------
The cutover deletes rooms, so a server start must never run it. Nick chose an
operator script, the pattern of the tile sync (09/25/2026). `plan` changes
nothing, and `apply` does what a plan says. `scripts/move_to_tile_world.py`
prints the plan, and it applies the plan only with `--apply`. A second run
finds nothing to do.

Where a character goes
----------------------
The converter put each map at the south-west corner of its own chunk
(`MAP_CHUNKS`). Thus, xyzgrid tile (x, y) of a map is world tile
(cx * 64 + x, cy * 64 + y), and a character keeps its place. A character on a
map with no chunk, or on a tile that the tile world blocks, goes to the
respawn point.

A character that stands in a room moves there now (`movement.place`). A
character that is logged out has no location. Evennia keeps its room in
`db.prelogout_location`. The cutover stores the tile in the login tile
attribute, and `Character.at_pre_puppet` puts the character there at the next
login.

A character whose home is an xyzgrid room, or no room, gets the respawn point
as its home. The pin of the respawn point keeps that room on its tile.

How the maps go
---------------
The cutover finds the xyzgrid rooms by their typeclass family, not through
the grid Script. `GridTile.at_object_delete` runs the teardown on each room, as
a map rebuild does. It spares player characters, and none is left there.

The grid Script pickles each legend class of each map in `db.map_data`
(`world/maps/gridstate.py`). A read of that row after the map modules move
gives a raw string, not an error. Thus, the cutover removes the attribute
before it deletes the Script, and it never reads the row.

This module owns `MAP_CHUNKS`. The converter reads it from here, so the fact
stays when the converter goes to `archive/`.
"""

from dataclasses import dataclass, field

from evennia.contrib.grid.xyzgrid.xyzgrid import XYZGrid
from evennia.contrib.grid.xyzgrid.xyzroom import XYZExit, XYZRoom

from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid import movement
from world.respawn import get_respawn_room, respawn_tile


# ─── Public constant definitions ─────────────────────────────────────────────

# The chunk of each map, by its Z. Each map sits at the south-west corner of
# its own chunk (Phase 4 decision, 09/24/2026). The area of each chunk has the
# name of its map.
MAP_CHUNKS: dict = {
    "oasis": (0, 0),
    "oasis_outskirts": (1, 0),
    "azm_plains": (2, 0),
}


# ─── Private constant definitions ────────────────────────────────────────────

# The attribute of the grid Script that holds the pickled maps.
_MAP_DATA_ATTR: str = "map_data"


# ─── Public classes ──────────────────────────────────────────────────────────

class CutoverError(RuntimeError):
    """The cutover cannot start. Nothing changed."""


@dataclass(frozen=True)
class CharacterMove:
    """
    One character to move. `source` is the xyz of its xyzgrid room. `online`
    is True if it stands in that room now, and False if it logged out there.
    """

    character: object
    source: tuple
    tile: tuple
    online: bool


@dataclass
class CutoverPlan:
    """
    What a cutover would do. `rooms` counts the xyzgrid rooms by Z. `rehome`
    holds each character whose home is an xyzgrid room or no room.
    """

    respawn: tuple
    moves: list = field(default_factory=list)
    rehome: list = field(default_factory=list)
    rooms: dict = field(default_factory=dict)
    exits: int = 0
    grids: int = 0

    def is_empty(self) -> bool:
        """Return True if the cutover has nothing to do."""
        return not (self.moves or self.rehome or self.rooms
                    or self.exits or self.grids)


# ─── Private helper routines ─────────────────────────────────────────────────

def _is_map_room(room) -> bool:
    """Return True for a room of an xyzgrid map, never for a tile room."""
    from typeclasses.rooms import TileRoom

    if room is None:
        return False

    if not room.is_typeclass(XYZRoom, exact=False):
        return False

    return not room.is_typeclass(TileRoom, exact=False)


def _map_rooms() -> list:
    """Return every room of an xyzgrid map, in id order."""
    rooms = XYZRoom.objects.filter_family().order_by("id")

    return [room for room in rooms if _is_map_room(room)]


def _characters() -> list:
    """Return every player character, in id order."""
    from typeclasses.characters import Character

    return list(Character.objects.all_family().order_by("id"))


def _map_room_of(character):
    """
    Return (room, online) of the xyzgrid room of a character, or
    (None, False). A logged-out character has its room in
    `db.prelogout_location`.
    """
    if _is_map_room(character.location):
        return character.location, True

    if character.location is None:
        stored = character.db.prelogout_location

        if _is_map_room(stored):
            return stored, False

    return None, False


# ─── Public routines ─────────────────────────────────────────────────────────

def target_tile(world, xyz: tuple, respawn: tuple) -> tuple:
    """
    Purpose: Give the world tile of a place on an xyzgrid map.

    Entry:
        world   - a TileWorld.
        xyz     - (x, y, z) of an xyzgrid room. x and y can be strings.
        respawn - the tile of the respawn point.

    Exit/Returns:
        The world tile (x, y). The respawn point for a map with no chunk, and
        for a tile that is off the grid or that a character cannot stand on.

    Module Globals:
        MAP_CHUNKS read.

    Methodology:
        The converter put each map at the south-west corner of its chunk, so
        the offset is the chunk origin.

    Notes/References:
        archive/xyzgrid-maps/blackout/world/maps/chunk_converter.py, `_world_tile`.

    Author: Nick Hobar
    Creation date: 09/25/2026
    """
    chunk = MAP_CHUNKS.get(xyz[2])

    if chunk is None:
        return respawn

    size = tile_const.CHUNK_SIZE
    x = chunk[0] * size + int(xyz[0])
    y = chunk[1] * size + int(xyz[1])

    if not world.has_tile(x, y):
        return respawn

    if world.grid.flags_at(x, y) & tile_const.FLAGS_UNWALKABLE:
        return respawn

    return (x, y)


def plan(world) -> CutoverPlan:
    """
    Purpose: Say what a cutover would do. Change nothing.

    Entry:
        world - a TileWorld, with its room index loaded.

    Exit/Returns:
        A CutoverPlan. Raises CutoverError if no chunk file places the
        respawn point, because a character could then have no tile.

    Module Globals:
        None.

    Methodology:
        1. Find the respawn point.
        2. For each character, find its xyzgrid room and its home.
        3. Count the xyzgrid rooms by Z, the exits, and the grid Scripts.

    Notes/References:
        The script prints the plan. `apply` takes it.

    Author: Nick Hobar
    Creation date: 09/25/2026
    """
    respawn = respawn_tile(world)

    if respawn is None:
        raise CutoverError("no chunk file places the respawn point")

    result = CutoverPlan(respawn=respawn)

    for character in _characters():
        room, online = _map_room_of(character)

        if room is not None:
            tile = target_tile(world, room.xyz, respawn)
            result.moves.append(CharacterMove(character, tuple(room.xyz), tile, online))

        if character.home is None or _is_map_room(character.home):
            result.rehome.append(character)

    for room in _map_rooms():
        z = room.xyz[2]
        result.rooms[z] = result.rooms.get(z, 0) + 1

    result.exits = XYZExit.objects.filter_family().count()
    result.grids = XYZGrid.objects.filter_family().count()

    return result


def _move(world, move: CharacterMove) -> None:
    """Put one character on its tile, or store the tile for its login."""
    from typeclasses.characters import PRELOGOUT_TILE_ATTR

    if move.online:
        movement.place(world.rooms, move.character, move.tile[0],
                       move.tile[1], quiet=True)
        return

    move.character.attributes.add(PRELOGOUT_TILE_ATTR, list(move.tile))
    move.character.db.prelogout_location = None


def _delete_maps() -> int:
    """
    Delete every xyzgrid room, exit, and grid Script. Return the rooms. A
    queued NPC respawn in a room goes too, or it would stand up nowhere.
    """
    from systems.gameplay.spawning.respawn import get_respawn_manager

    manager = get_respawn_manager()
    rooms = _map_rooms()

    for room in rooms:
        manager.cancel_room(room)
        room.delete()

    for leftover in XYZExit.objects.filter_family():
        leftover.delete()

    for grid in XYZGrid.objects.filter_family():
        grid.attributes.remove(_MAP_DATA_ATTR)
        grid.delete()

    return len(rooms)


def apply(world, cutover: CutoverPlan) -> int:
    """
    Purpose: Do what a plan says.

    Entry:
        world   - the TileWorld that `plan` read.
        cutover - a CutoverPlan from `plan`.

    Exit/Returns:
        The number of xyzgrid rooms deleted. Raises CutoverError, with no
        change, if the respawn point has no room.

    Module Globals:
        None.

    Methodology:
        1. Get the room of the respawn point. It is the new home.
        2. Move each character. Set each home.
        3. Delete the maps last. No character stands there then, and no
           home points there.

    Notes/References:
        The server keeps the tile room index in memory. Run this with the
        server down, or reload it after.

    Author: Nick Hobar
    Creation date: 09/25/2026
    """
    home = get_respawn_room(world)

    if home is None:
        raise CutoverError("the respawn point has no room")

    for move in cutover.moves:
        _move(world, move)

    for character in cutover.rehome:
        character.home = home

    return _delete_maps()
