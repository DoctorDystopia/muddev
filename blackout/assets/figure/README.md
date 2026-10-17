# Authoring a figure

A figure is the body that the game draws for a player character. The figure
workbench in Godot makes it. This directory holds the files that it writes.
The guide for equipment is [EQUIPMENT.md](EQUIPMENT.md).

| File | What it holds |
|---|---|
| `rigs/<body type>.json` | The bones, the sockets, the regions, and the slot bones of one body type |
| `looks/<body type>.json` | The body: one part for each bone, and the shape list of each part |
| `looks/<key>.json` with a `kit` key | A kit part: a hair shape, a beard, a head |
| `palette.json` | The named colors, their finish, and the color of each color role |
| `clips/` | The source of the animation clips |

A save writes these files and the served `figure.json`. The game reads
`figure.json` only. Never edit `figure.json` by hand.

## Open the workbench

1. Open `godot/` in Godot 4.7.
2. On the **Figure** dock, click **Open workbench**.
3. Select the **FigureWorkbench** node. One stand shows each body type.
4. Pick the body type in **Body type that the tabs show**. The tabs then
   edit that body type.

Each button says a verb and an object. A button that is off gives the reason
in its tooltip.

## Change the body

1. On the **Body** tab, click a part on the stand, or pick it in the part
   list. The hint line below the 3D view names the part and its bone.
2. Move the part with the Godot tools: W moves, E turns, R scales.
3. Change the shape list of the part. Each shape is a prism with a size, a
   top width, a top depth, and a color role. Add a shape with **Add shape**.
4. Give a new part a bone in the list above **Add part**, then click
   **Add part**. The part starts with one prism.
5. Press Ctrl+S.

The color of a shape is a color role, not a color. The palette gives each
role its color, so one change of the palette changes each shape of that
role. The roles `skin` and `hair` belong to the character: the moderator egg
sets them for one player.

## Make a body type

1. On the **Rig** tab, click **New rig**. Type the key, for example
   `body_3`. The rig starts as the humanoid profile.
2. Change **Limb scale** and the position of each bone. Select a bone in
   the list, and move its mark on the stand with W.
3. On the **Body** tab, click **New body**. The body type gets a body with
   the start shapes.
4. Press Ctrl+S. The server reads the body types from the rig files. The
   egg lists the new one with no code change.

## Add a kit part

A kit part is a shape that a character wears over the body: a hair shape, a
beard. The game sends no kit yet, so each figure draws the body as it is.

1. On the **Body** tab, select the bone in the list above **Add a part on
   this bone**. Use `head_top` for a hair shape.
2. Type a key and a kit group below **Kit of the figure on the stands**,
   for example `hair_short` and `hair`.
3. Click **New kit part**. Each stand wears it.
4. Change its parts and shapes. Tick each region of the body that it hides.
5. Press Ctrl+S.

## Put a modeled part on the body

One part can draw a model from Blender in place of its shapes. The head and
the hair are the usual ones.

1. On the **Body** tab, click **Export reference body**. Save the `.glb`.
2. In Blender, model the new part over the old one. Keep its place. Give the
   object the name of the part, for example `head`. Give each material the
   name of a color role: `skin`, `eyes`, `hair`.
3. Save a `.blend` file, or export the new object as a `.glb` file.
4. In the part editor, select the part. Leave the model key empty, or type
   one. Click **Import model for part**, and pick the file.
5. Press Ctrl+S. The pipeline writes the source, the model record, and the
   served `.glb`.

**Part from served model** gives the part a model that the pipeline built
already.

**Shape list again** takes the model away. The shapes stay, and they draw
while the model is not in hand.

## Change the colors

1. On the **Colors** tab, pick a named color. Click the color bar, and pick
   a color. Each stand shows the change.
2. Pick a finish for the color: a metalness and a roughness.
3. In **Color roles**, give a role another named color.
4. Press Ctrl+S.

**Colors of the character on the stands** shows one skin and one hair color
on the stands. It writes no file.

## Play a clip

1. On the **Clips** tab, select a clip, and click **Play**. Each stand plays
   it.
2. Tick **Show a held item in each hand**, and look for an item that goes
   through the body.
3. To add a clip, click **List source clips**, pick one, and click **Put
   clip in list**. Then click **Build the clips**.

## Check, save, and see it in the game

1. On the **Check** tab, click **Check the figure files**. A finding is a
   fault. A note is no fault. Click a row to go to the fault.
2. Press Ctrl+S. **Save** counts the unsaved files.
3. Run `evennia reload` from `blackout/`. The client fetches the new
   `figure.json` and draws each figure again.
4. For the public game, run `deploy/webexport/publish.sh --changed-only`.
   A player sees the change at the next login.

A player with no body type draws `body_1`. The moderator egg sets a body
type for one player with **Set the body type**. It sets a skin or hair color
with **Set a figure color**.
