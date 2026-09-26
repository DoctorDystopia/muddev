"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: Builds the chunk file fixtures of the parity test, from a fixed
             seed.

The fixtures in `fixtures/` are the output of `build_fixtures`, written by
`chunkfile.to_text`. `test_chunkfile` rebuilds them and fails if a committed
file differs. Thus, the builder is the owner, and a hand edit of a fixture
fails at once.

To change a fixture, change this module, then run from `blackout/`:

    ../evenv/Scripts/python.exe -m systems.core.tilegrid.tests.fixture_builder

That writes the fixtures and `fixtures/digests.json`. The Godot test reads the
same files, so run `test_chunk_file.tscn` after it.

What the fixtures cover
-----------------------
Every feature that a reader can get wrong, in three files:

| File | Covers |
|---|---|
| chunk_-1_2_p0.json | Negative chunk x, every flag bit, negative heights, three floors, two areas, objects in all four rotations |
| chunk_0_2_p0.json | The east neighbour of the first. Its west edge corners equal the first's east edge, so the seam matches |
| chunk_0_0_p1.json | Plane 1, one floor, one area, no objects |
"""

import json
import os
import random

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as const


# ─── Public constant definitions ─────────────────────────────────────────────

FIXTURE_DIRECTORY: str = os.path.join(os.path.dirname(os.path.abspath(
    __file__)), "fixtures")

DIGEST_FILE_NAME: str = "digests.json"


# ─── Private constant definitions ────────────────────────────────────────────

_SEED = 20260924

# Heights run below zero, so a reader that reads an unsigned byte fails.
_HEIGHT_LOW = -12
_HEIGHT_HIGH = 40

# Every single bit, plus two combined, so each bit appears somewhere.
_FLAG_CHOICES = (0, 0, 0, 0, const.FLAG_BLOCKED, const.FLAG_WATER,
                 const.FLAG_WALL_NORTH, const.FLAG_WALL_EAST,
                 const.FLAG_WALL_SOUTH, const.FLAG_WALL_WEST,
                 const.FLAG_WALL_NORTH | const.FLAG_WALL_WEST,
                 const.FLAG_BLOCKED | const.FLAG_WALL_EAST)

_WEST_CHUNK = (-1, 2)
_EAST_CHUNK = (0, 2)
_UPPER_CHUNK = (0, 0)
_UPPER_PLANE = 1


# ─── Private helper routines ─────────────────────────────────────────────────

def _random_grid(rng, side: int, low: int, high: int) -> list:
    return [rng.randint(low, high) for _ in range(side * side)]


def _flag_grid(rng) -> list:
    size = const.CHUNK_SIZE

    return [rng.choice(_FLAG_CHOICES) for _ in range(size * size)]


def _west_chunk(rng) -> chunkfile.ChunkFile:
    size = const.CHUNK_SIZE
    objects = [chunkfile.ChunkObject("rendering_cooker", 12, 40, 0),
               chunkfile.ChunkObject("desert_anvil", 0, 63, 1),
               chunkfile.ChunkObject("npc_spawn_raider", 63, 0, 2),
               chunkfile.ChunkObject("sign", 31, 7, 3)]

    return chunkfile.ChunkFile(
        cx=_WEST_CHUNK[0], cy=_WEST_CHUNK[1], plane=0,
        floor_names=["sand", "asphalt", "rubble"],
        area_names=["oasis", "azm_plains"],
        heights=_random_grid(rng, const.CORNERS_PER_SIDE, _HEIGHT_LOW,
                             _HEIGHT_HIGH),
        floors=_random_grid(rng, size, 0, 2),
        flags=_flag_grid(rng),
        areas=_random_grid(rng, size, 0, 1),
        objects=objects)


def _east_chunk(rng, west: chunkfile.ChunkFile) -> chunkfile.ChunkFile:
    """The east neighbour of `west`, with the shared seam copied."""
    size = const.CHUNK_SIZE
    side = const.CORNERS_PER_SIDE
    heights = _random_grid(rng, side, _HEIGHT_LOW, _HEIGHT_HIGH)

    for row in range(side):
        heights[row * side] = west.heights[row * side + side - 1]

    return chunkfile.ChunkFile(
        cx=_EAST_CHUNK[0], cy=_EAST_CHUNK[1], plane=0,
        floor_names=["asphalt", "sand"],
        area_names=["azm_plains"],
        heights=heights,
        floors=_random_grid(rng, size, 0, 1),
        flags=_flag_grid(rng),
        areas=[0] * (size * size),
        objects=[chunkfile.ChunkObject("bank_booth", 5, 6, 0)])


def _upper_chunk() -> chunkfile.ChunkFile:
    size = const.CHUNK_SIZE
    side = const.CORNERS_PER_SIDE

    return chunkfile.ChunkFile(
        cx=_UPPER_CHUNK[0], cy=_UPPER_CHUNK[1], plane=_UPPER_PLANE,
        floor_names=["wood"],
        area_names=["oasis"],
        heights=[const.DEFAULT_HEIGHT] * (side * side),
        floors=[0] * (size * size),
        flags=[const.FLAG_NONE] * (size * size),
        areas=[0] * (size * size),
        objects=[])


# ─── Public routines ─────────────────────────────────────────────────────────

def build_fixtures() -> list:
    """Return the fixture ChunkFiles, the same on every call."""
    rng = random.Random(_SEED)
    west = _west_chunk(rng)
    east = _east_chunk(rng, west)

    return [west, east, _upper_chunk()]


def digests(chunk_files: list) -> dict:
    """Return {file name: semantic digest} for the fixtures."""
    return {f.file_name(): chunkfile.semantic_digest(f) for f in chunk_files}


def digest_text(chunk_files: list) -> str:
    """Return the text of the digest file: sorted keys, "\\n" line ends."""
    return json.dumps(digests(chunk_files), indent=2, sort_keys=True) + "\n"


def write_fixtures() -> None:
    """Write every fixture and the digest file."""
    chunk_files = build_fixtures()

    os.makedirs(FIXTURE_DIRECTORY, exist_ok=True)

    for chunk_file in chunk_files:
        path = os.path.join(FIXTURE_DIRECTORY, chunk_file.file_name())
        chunkfile.write_file(path, chunk_file)

    digest_path = os.path.join(FIXTURE_DIRECTORY, DIGEST_FILE_NAME)

    with open(digest_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(digest_text(chunk_files))


if __name__ == "__main__":
    write_fixtures()
    print("wrote the chunk file fixtures to", FIXTURE_DIRECTORY)
