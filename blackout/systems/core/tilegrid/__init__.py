"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: The tile grid: one contiguous world of heights, floor types, and
             walk flags, with a room only where something stands.

DESIGN-0011 (docs/2026-09-23-DESIGN-0011-terrain-verticality-fog.md) is the
design. Since Phase 4b (09/25/2026), the tile world is the only world, and
this package is its core.

| Module | Holds | May import |
|---|---|---|
| `constants.py` | Chunk size, walk flag bits, directions, step results, limits | nothing |
| `grid.py` | `Chunk`, `TileGrid`: the arrays and the step rule. No database | `constants` |
| `pathfind.py` | A* on a `TileGrid`, with a limit. No database | `constants` |
| `sight.py` | Line of sight on a `TileGrid`. No database | `constants` |
| `planes.py` | The room Z of each plane, and the plane of a Z | `constants` |
| `rooms.py` | `TileRooms`: the index from tile to room, and the pool | `constants`, `typeclasses.rooms` (late) |
| `movement.py` | `step` and `place`: a move from tile to tile | `constants` |
| `chunkfile.py` | The chunk file: read, check, write, seams, semantic dump | `constants`, `grid` |
| `world.py` | `TileWorld`, `TilePlane`, `get_world`: the chunk files of `world/chunks/` as one grid and one room index for each plane | `chunkfile`, `constants`, `planes`, `rooms`, `world.object_kinds` (late) |
| `sweep.py` | The tick hook that gives empty rooms back to the pool | `constants`, `world` |
| `syncstamp.py` | The digest of the chunk files at the last tile sync | `constants`, `chunkfile` |

`grid.py`, `pathfind.py`, `sight.py`, `planes.py`, and `chunkfile.py` touch
no Evennia object. Thus, their tests use plain `unittest.TestCase` and cost
nothing.

Phase 2 added the chunk file. `godot/world/terrain/chunk_file.gd` is its
GDScript twin. `tests/test_chunkfile.py` and `godot/tests/test_chunk_file.gd`
are the two halves of the parity test, on the fixtures in `tests/fixtures/`.
"""
