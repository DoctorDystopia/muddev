# Authoring equipment

A worn look is what an item shows on a figure. The gear editor makes it:
the Godot plugin `godot/addons/blackout_gear/`. Read [README.md](README.md)
first for the figure workbench, the parts, and the colors. The gear editor
reads and writes the same files.

**The game draws the gear of a player on the figure** (since 10/16/2026).
The server sends the worn record of each character, and the figure wears
the worn look of each item. A look that you save reaches the local game
after `evennia reload`. The gear editor shows the same look on the stands.

**A served model wins over the worn look** (since 10/17/2026). An item
with a model in the served tree holds that model, in the hand and in a
cell. Its worn look stands in until the model arrives, and it gives the
model its first place. See "Place a served model" below.

| File | What it holds |
|---|---|
| `looks/<item key>.json` | The worn look of one item: its parts, its colors, and the regions it hides |
| `looks/<slot>.json` | The slot shape: what an item with no worn look shows, for example `head.json` |
| `looks/<item key>.json` with a `base` key | A tier: the parts of another look with other colors |
| `looks/<item key>.json` with a `served` key | The place of the served model of the item, after you moved it |
| `godot/world/figure/stances.json` | The clip of each action, for one tool type |
| `godot/addons/blackout_figure/item_catalog.json` | The rows of the gear editor. The export writes it |

## Open the gear editor

Click **Open gear editor** in the top strip of the Figure dock. Or open
`res://addons/blackout_gear/gear_workbench.tscn` in Godot, and select the
`GearWorkbench` node. The Gear dock has three zones: the items, the part
editor, and the look.

## Get the item in the item list

The item list has each `ItemDef` with a `use_slot`. A new item needs the
export:

```bash
python scripts/export_client_constants.py
```

Run it from `blackout/`. A test fails while the catalog is stale.

## Give an item a worn look from shapes

1. Pick the row of the item in the item list. Each stand wears it as its
   slot shape. Type in the field above the list to find a row.
2. Open the **Look** fold, and click **New look**. The item gets a copy of
   the slot shape as its own look.
3. Click a shape on a stand. The Godot tools (W, E, R) move that shape.
   A second click on the same shape selects the whole part. The tree of
   the part editor shows each part and its shapes, and the two grids show
   the selected part and the selected shape.
4. Add a shape with one of the `+` buttons above the tree. Delete removes
   the selected row, and Ctrl+D copies it.
5. Tick each region in the **Hides** fold. A chainbody hides `torso` and
   `arms`.
6. Use the outfit bar to put items in the other slots. Play a clip. Look
   for a part that goes through another part. Then press Ctrl+S.

**Copy look** gives the row the parts and the colors of another look.

**Remove look** takes the look away. The slot shape then draws again.

## Give an item a model from a modeler

First, make the file:

1. Select the body type that you model over. Dress the figure with the
   outfit bar in each item that the new one must fit over.
2. In the figure workbench, on the **Body** tab, click **Export reference
   body**. Save the `.glb`.
3. In Blender, model the item on the body. Do not move the body. Make one
   object for each bone that the item follows. A chainbody is a torso
   object and two arm objects.
4. Give each object the name of its bone, for example `LeftUpperArm`. Give
   each material the name of a color role.
5. Export only the new objects as one `.glb` file.

Then import it:

1. In the gear editor, pick the row. Open the **Model** fold, type the
   author, and click **Import model**. The status box says "Building ..."
   until the build ends.
2. Look at the parts. Each object is one part on the bone with its name.
   Change a bone that is wrong.
3. Press Ctrl+S.

**Parts from model** makes the parts from a model that the pipeline built
already.

**Import model for part** in the Part model fold changes one part only.
Each other part stays.

## Place a served model

An item with a served model, for example `rusty_scrap_shortsword`, holds
that model on each stand. The row says "served model". The model takes the
length and the middle of the worn look, or of the slot shape. To change
its place:

1. Pick the row of the item.
2. Click the model on a stand. The status box says "The served model of
   ...".
3. Move it with W, and turn it with E. The other stand follows.
4. To scale the whole model, type a number in **Scale in the hand** in
   the **Model** fold. R scales one axis only.
5. Press Ctrl+S. The look file of the item keeps the place in its
   `served` row. An item with no look gets a look with that row only.

**Fit served model to look** in the **Model** fold takes the place away.
The model then takes the box of the look again.

The presentation fields below it change the model on the ground, not in
the hand.

**Import model** is off for such a row. The import does not write over a
model that it did not bring. To import a model of the look, type another
key in the model field.

## Fit the other body type

1. Select the other body type. Click **Fit from bone lengths**. Each part
   on a longer or shorter bone gets its own place.
2. Play each clip, and look at each stand.
3. To move one part on one body type only, select the part. Tick **Own
   place on this body type (the fit)**. Then move it.
4. Press Ctrl+S.

## Make a tier

A tier draws the parts of another look with its own colors. A bronze helm
and an iron helm come from one shape.

1. Give the first item of the set its worn look.
2. Pick the row of the next item. In the **Look** fold, select the first
   look in the list below **The look to copy, or the base of a tier**.
3. Click **Make tier**.
4. Pick a color for each color role in the **Colors** fold. A `*` marks a
   role with a color of its own.
5. Press Ctrl+S. A change of the parts of the base shows on each tier.

## Give a tool type a stance

1. Put the item in a hand with the outfit bar. In the figure workbench,
   the stance list of the **Clips** tab goes to its tool type.
2. Pick a clip for each action that differs from the default clip set.
3. Click **Play** on a row to see it.
4. Press Ctrl+S.

## Dress an NPC

An NPC shows the gear of its `outfit`, in `world/npc_defs/`. The outfit is a
dict of slot to item key. It is a look, not a rule: combat reads the combat
block. After a change, run the export. The NPC list on the outfit bar then
dresses a stand in that outfit.

## Check and save

1. In the figure workbench, on the **Check** tab, click **Check the figure
   files**. An item with no worn look gives a note, because its slot shape
   draws. A finding on the look of an item names the part. Change it in
   the gear editor.
2. Read the budget line below the list of body types. It gives the draws
   and the triangles of the dressed figure against the budget. The Gear
   dock has the same line.
3. Press Ctrl+S. The figure workbench and the gear editor write the same
   files. A switch between the two asks to save unsaved files first.
