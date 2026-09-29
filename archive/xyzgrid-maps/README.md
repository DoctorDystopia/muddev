# Archive: the xyzgrid maps

**Retired on 09/25/2026**, in DESIGN-0011 Phase 4b. The tile world replaced
them: the chunk files in [`blackout/world/chunks/`](../../blackout/world/chunks/README.md).

This directory is outside `blackout/` on purpose. Nothing under `blackout/`
may import anything here, so the archive cannot come back through a stray
path. It is for reference only.

## What is here

The paths inside mirror the old paths under `blackout/`.

| Path | What it was |
|---|---|
| `world/maps/oasis.py`, `oasis_outskirts.py`, `azm_plains.py`, `neo_cairo.py` | The map strings, legends, and `PROTOTYPES` tables of the four maps. `neo_cairo` was never in the manifest |
| `world/maps/manifest.py`, `scope.py`, `gridstate.py` | The manifest reader, the `--map` and `--tile` scope of a rebuild, and the readability check of the grid Script |
| `world/maps/chunk_converter.py` | The one-time converter from a map to a chunk file |
| `world/maps/map_glyph_legend.md` | The glyphs of the map strings |
| `scripts/map_sync.py`, `map_manifest.json` | The map rebuild and the list of maps that it built |
| `scripts/clean_and_reload_all_maps.ps1`, `.sh` | The operator wrappers of `map_sync.py` |
| `scripts/convert_maps_to_chunks.py` | The operator wrapper of the converter |
| `world/tests/` | The tests of the modules above |

## What is not here

- `blackout/world/tile_cutover.py` and `scripts/move_to_tile_world.py`. The
  cutover moves each character off the maps and deletes the map rooms. It
  stays live, because another database can still hold the maps. It owns
  `MAP_CHUNKS`, the chunk of each map.
- `GridTile` in `blackout/typeclasses/rooms.py`. It is the base class of
  `TileRoom`, which keeps the xyz tags of the contrib.

## How to read an old map

The chunk files hold the converted maps. To see a map string, read the
module here. The converter ran on 09/24/2026. Its rules are in the docstring
of `chunk_converter.py`.
