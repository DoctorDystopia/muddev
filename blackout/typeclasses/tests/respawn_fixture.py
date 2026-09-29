"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/25/2026
Description: A one-chunk tile world for the respawn tests, with or without a
             respawn point.

A test that does not install a world reads the real `world/chunks/`, which
places a respawn point. Thus, a test of the "no respawn point" case must
install an empty world, and every test must remove its world after.
"""

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid.world import TileWorld, set_world
from world.respawn import RESPAWN_KIND, get_respawn_room


# ─── Public constant definitions ─────────────────────────────────────────────

# The tile of the respawn point in the fixture world.
RESPAWN_TILE: tuple = (3, 4)


# ─── Private constant definitions ────────────────────────────────────────────

_SIZE = tile_const.CHUNK_SIZE


# ─── Public routines ─────────────────────────────────────────────────────────

def build_world(with_respawn: bool) -> TileWorld:
    """Return a loaded one-chunk world of open ground."""
    tile_count = _SIZE * _SIZE
    objects = []

    if with_respawn:
        objects.append(chunkfile.ChunkObject(RESPAWN_KIND, *RESPAWN_TILE))

    chunk_file = chunkfile.ChunkFile(
        cx=0, cy=0, plane=0, floor_names=["sand"], area_names=["oasis"],
        heights=[0] * tile_const.CORNERS_PER_SIDE ** 2,
        floors=[0] * tile_count, flags=[0] * tile_count,
        areas=[0] * tile_count, objects=objects)
    world = TileWorld([chunk_file])
    world.rooms.load()

    return world


def install_empty_world() -> TileWorld:
    """Install a world with no respawn point, and return it."""
    world = build_world(with_respawn=False)
    set_world(world)

    return world


def make_respawn_room():
    """Install a world with a respawn point, and return its room."""
    set_world(build_world(with_respawn=True))

    return get_respawn_room()


def remove_world() -> None:
    """Drop the installed world, so the next test starts clean."""
    set_world(None)
