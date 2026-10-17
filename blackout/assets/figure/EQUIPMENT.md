# Authoring equipment

A worn look is what an item shows on a figure. The figure workbench makes it
on the **Gear** tab. Read [README.md](README.md) first for the workbench,
the parts, and the colors.

**The game draws no gear on a figure yet.** The worn looks wait for the
worn record of the server. The workbench shows them on the stands today.

| File | What it holds |
|---|---|
| `looks/<item key>.json` | The worn look of one item: its parts, its colors, and the regions it hides |
| `looks/<slot>.json` | The slot shape: what an item with no worn look shows, for example `head.json` |
| `looks/<item key>.json` with a `base` key | A tier: the parts of another look with other colors |
| `godot/world/figure/stances.json` | The clip of each action, for one tool type |
| `godot/addons/blackout_figure/item_catalog.json` | The rows of the Gear tab. The export writes it |

## Get the item on the Gear tab

The Gear tab lists each `ItemDef` with a `use_slot`. A new item needs the
export:

```bash
python scripts/export_client_constants.py
```

Run it from `blackout/`. A test fails while the catalog is stale.

## Give an item a worn look from shapes

1. On the **Gear** tab, pick the row of the item. Each stand wears it as its
   slot shape. Type in the field above the list to find a row.
2. Click **New look**. The item gets a copy of the slot shape as its own
   look.
3. Change the parts and the shapes in the part editor, as for a body. Click
   the item on the stand to select its part.
4. Tick each region in **Regions that the look hides on each other look**.
   A chainbody hides `torso` and `arms`.
5. Use the outfit bar above the tabs to put items in the other slots. Look
   for a part that goes through another part. Then press Ctrl+S.

**Copy look** gives the row the parts and the colors of another look.

**Remove look** takes the look away. The slot shape then draws again.

## Give an item a model from a modeler

First, make the file:

1. Select the body type that you model over. Dress the figure with the
   outfit bar in each item that the new one must fit over.
2. On the **Body** tab, click **Export reference body**. Save the `.glb`.
3. In Blender, model the item on the body. Do not move the body. Make one
   object for each bone that the item follows. A chainbody is a torso
   object and two arm objects.
4. Give each object the name of its bone, for example `LeftUpperArm`. Give
   each material the name of a color role.
5. Export only the new objects as one `.glb` file.

Then import it:

1. On the **Gear** tab, type the author, and click **Import model**. The
   status box says "Building ..." until the build ends.
2. Look at the parts. Each object is one part on the bone with its name.
   Change a bone that is wrong.
3. Press Ctrl+S.

**Parts from model** makes the parts from a model that the pipeline built
already.

**Import model for part** in the part editor changes one part only. Each
other part stays.

## Fit the other body type

1. Select the other body type. Click **Fit each part from the bone
   lengths**. Each part on a longer or shorter bone gets its own place.
2. Play each clip, and look at each stand.
3. To move one part on one body type only, select the part. Tick **Own
   place on this body type (the fit)**. Then move it.
4. Press Ctrl+S.

## Make a tier

A tier draws the parts of another look with its own colors. A bronze helm
and an iron helm come from one shape.

1. Give the first item of the set its worn look.
2. Pick the row of the next item. Select the first look in the list below
   **The look to copy, or the base of a tier**.
3. Click **Make tier**.
4. Pick a color for each color role in the color table. A `*` marks a role
   with a color of its own.
5. Press Ctrl+S. A change of the parts of the base shows on each tier.

## Give a tool type a stance

1. Put the item in a hand with the outfit bar. The stance list of the
   **Clips** tab goes to its tool type.
2. Pick a clip for each action that differs from the default clip set.
3. Click **Play** on a row to see it.
4. Press Ctrl+S.

## Dress an NPC

An NPC shows the gear of its `outfit`, in `world/npc_defs/`. The outfit is a
dict of slot to item key. It is a look, not a rule: combat reads the combat
block. After a change, run the export. The NPC list on the outfit bar then
dresses a stand in that outfit.

## Check and save

1. On the **Check** tab, click **Check the figure files**. An item with no
   worn look gives a note, because its slot shape draws.
2. Read the budget line below the list of body types. It gives the draws
   and the triangles of the dressed figure against the budget.
3. Press Ctrl+S.
