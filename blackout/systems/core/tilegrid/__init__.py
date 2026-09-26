"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: The tile grid: one contiguous world of heights, floor types, and
             walk flags, with a room only where something stands.

DESIGN-0011 (docs/2026-09-23-DESIGN-0011-terrain-verticality-fog.md) is the
design. This package is the Phase 1 spike, which measures the room model on a
64 x 64 grid. Nothing live uses it yet: no map, no command, and no cmdset.

| Module | Holds | May import |
|---|---|---|
| `constants.py` | Chunk size, walk flag bits, directions, step results, limits | nothing |
| `grid.py` | `Chunk`, `TileGrid`: the arrays and the step rule. No database | `constants` |
| `pathfind.py` | A* on a `TileGrid`, with a limit. No database | `constants` |
| `rooms.py` | `TileRooms`: the index from tile to room, and the pool | `constants`, `typeclasses.rooms` (late) |
| `movement.py` | `step` and `place`: a move from tile to tile | `constants` |
| `chunkfile.py` | The chunk file: read, check, write, seams, semantic dump | `constants`, `grid` |
| `world.py` | `TileWorld` and `get_world`: the chunk files of `world/chunks/` as one grid and one room index | `chunkfile`, `constants`, `rooms` |

`grid.py`, `pathfind.py`, and `chunkfile.py` touch no Evennia object. Thus,
their tests use plain `unittest.TestCase` and cost nothing.

Phase 4a (docs/2026-09-24-HANDOFF-0001-tile-grid.md, section 8) puts the
server on this package, beside the live xyzgrid maps.

Phase 2 added the chunk file. `godot/world/terrain/chunk_file.gd` is its
GDScript twin. `tests/test_chunkfile.py` and `godot/tests/test_chunk_file.gd`
are the two halves of the parity test, on the fixtures in `tests/fixtures/`.
"""
