# Tileset_desert

The download this directory's per-tile sources were split out of.

- **Source:** https://wizp.itch.io/3d-tileset, by wizp
- **Licence:** whatever that page states. The download carries no licence file,
  so the grant is **not recorded** and has to be confirmed before this art
  ships anywhere public. Recorded as unknown rather than guessed at — a licence
  nobody checked and a licence recorded wrongly look identical afterwards.
- **Downloaded:** 08/28/2026

## What is here

| Path | What it is |
|---|---|
| `Tileset.gltf` | The download, unmodified. 34 tiles, one shared palette. |
| `ColorPalette.png` | The palette, as it arrived beside the `.gltf`. |
| `center_h/`, `center_b/` | Split out by `../../split_tileset.py`. Generated. |

The download also ships `Tileset.dae` and `Tileset.fbx` — the same 34 tiles in
two other formats, neither of which anything in this repo reads. They are not
kept, which is the one departure from "drop the download in unmodified" that
`assets/README.md` asks for; re-download if a DCC tool ever needs them.

`ColorPalette.png` is duplicated inside `Tileset.gltf` as an embedded image,
which is where the split actually reads it from. It is kept beside the `.gltf`
anyway because that is how the download arrived and because it is the one file
that makes the tileset legible: the art is palette-mapped, so the image is a
chart of flat swatches rather than a surface, and every tile is a set of UVs
pointing into one column of it.

## Splitting another tile

```bash
../evenv/Scripts/python.exe assets/split_tileset.py \
    assets/tiles/desert/Tileset.gltf assets/tiles/desert <node_name>
```

Run with a node name the file does not hold and it prints all 34, which is the
fastest way to see what is in here. Then add a row to
`assets/model_manifest.json` and pack it; `assets/README.md` has the rest.
