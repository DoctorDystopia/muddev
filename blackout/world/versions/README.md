# World versions

This directory is the shelf of saved worlds. One directory holds one
version: a copy of every chunk file of `world/chunks/`, and a
`version.json` with a note and a save time. The directory name is the key.

A map author tries a layout, keeps it, and tries another (Nick,
10/28/2026). A git branch switches the code with the map, and it needs a
clean tree. A version is a shelf item: nothing else in the repo moves with
it, and git keeps its history as it keeps the chunk files.

`world/world_versions.py` owns the rules. The GDScript twin is
`godot/addons/blackout_terrain/world_versions.gd`. The server never reads
this directory.

## How to use it

The **Versions** tab of the terrain editor needs no terminal.

1. Open `godot/addons/blackout_terrain/terrain_editor.tscn`, and select
   the `TerrainWorld` node.
2. On the **Versions** tab, type a key and a note. Click **Save version**.
   The unsaved chunks of the block save first.
3. Edit the world. Save it as a second version.
4. Select a version, and click **Switch to version**. The block reads
   again. A star marks the version that the world is now.
5. Stop the server, run `scripts/sync_tile_objects.py --apply` from
   `blackout/`, and start the server. The database then holds the version.

The same from a terminal, from `blackout/`:

```bash
../evenv/Scripts/python.exe scripts/world_versions.py list
```

```bash
../evenv/Scripts/python.exe scripts/world_versions.py save market_v2 --note "two gates"
```

```bash
../evenv/Scripts/python.exe scripts/world_versions.py switch market_v2
```

`rename <old> <new>` and `remove <key>` do what they say. `--help` lists
each flag.

## The rules

- **A switch replaces the chunk files, and nothing else.** The world stays
  in `world/chunks/`. Thus, the server, the tests, and the tile sync read
  one directory, as before. The World tab of the editor names each file
  that changed since the last tile sync, as after any edit.
- **A switch never drops a world that no version holds.** The version
  whose files equal the world, byte for byte with CRLF read as LF, is the
  current one. When none is, the editor asks first and counts the files
  that go. The script refuses, unless you add `--drop`.
- **A version is a whole copy.** A removal of one changes no other. A
  version of thirty chunks is about one megabyte. Remove a version that
  nobody needs.
- **The tables are shared.** A version names the areas, the floor types,
  the wall styles, and the object kinds of today. A rename on the Tables
  tab reaches each version. A removal refuses a row that a version names.
- **A key is a legal chunk file name:** a-z, 0-9, and `_`. A note is one
  line of at most 200 characters.
- **A copy by hand is a version.** Copy `world/chunks/` to a new directory
  here. It lists with no note and no date. Click **Read files again**.

## The meta file

```json
{"format": 1, "note": "the market with two gates", "saved": "2026-10-28T15:04:05Z"}
```

`format` is `VERSION_FORMAT_VERSION` of `systems/core/tilegrid/constants.py`.
`saved` is UTC. A version with no meta file is legal.

## The tests

`world/tests/test_world_versions.py` tests the rules in a temporary
directory. Its last case reads this directory: each version must read, its
seams must close, and each name must be a row of its table.

```bash
../evenv/Scripts/evennia.exe test --settings test_settings.py world.tests.test_world_versions
```

`godot/tests/test_world_versions.tscn` tests the GDScript twin and the
form of the tab, in a scratch directory under `user://`.
