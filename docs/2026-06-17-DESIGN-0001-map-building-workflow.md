### Phase 1: Conceptualization & ASCII Drafting (The Blueprint)

Before writing any Python, you need to define the physical space and the entities that will occupy it. The XYZGrid parser is notoriously strict, so doing this in a plain text editor is best.

* **Draft the ASCII Layout:** Draw your map using a monospaced font.
* *XYZGrid Specifics:* You must enclose the map with `+` signs at the top-left and bottom-left to define the bounding box. Every room must be exactly one character wide. Links between rooms *must* be standard characters (`-`, `|`, `/`, `\`) and cannot have trailing spaces that break the grid alignment.


* **Identify Node Types:** Look at your map and decide how many unique room Types you need. For example, `#` for generic streets (`GridTile`), `S` for Shops, and `M` for a Medical Bay.

### Phase 2: Typeclass & Legend Development (The Engine)

This is where you bridge your visual map to Evennia's database. Create a new file for your map (e.g., `world/maps/sector_two.py`).

* **Define the Database Entities:** If your map introduces new room types (like a Shop), ensure you have an Evennia Typeclass built for it in `typeclasses/rooms.py`.
* **Create the MapNodes:** For every unique symbol on your map, create a subclass of `evennia.contrib.grid.xyzgrid.xymap_legend.MapNode`.
* *XYZGrid Specifics:* Set the `display_symbol` (what players see on the map) and the `prototype` dictionary, which tells Evennia exactly which Python class to spawn in the database (e.g., `{"typeclass": "typeclasses.rooms.ShopTile"}`).


* **Construct the `XYMAP_DATA`:** Assemble the Z-coordinate name, paste your ASCII string into the `map` field, and build your `legend` dictionary mapping the ASCII symbols directly to your new `MapNode` classes.

### Phase 3: Sandbox Testing (The Build)

Because Evennia writes grid changes directly to your live database, it is best practice to test new, complex map logic on a temporary Z-level before officially linking it to your world.

* **Load the Map into Memory:** Run `evennia xyzgrid add world.maps.sector_two`. Pay close attention to the terminal output to ensure the parser correctly read your custom nodes and didn't throw a syntax error.
* **Spawn the Grid:** Run `evennia xyzgrid spawn`. If you hit a `RuntimeError` due to a custom Typeclass mismatch, use the "Nuclear Option" from your README to sweep the physical database, fix your legend, and try again.
* **Refresh the Server:** Run `evennia reload`.
    * *Evennia Specifics:* As detailed in Evennia's Dual-Process architecture docs, the game state is managed by the Server process. Because you mutated the database from the CLI, you must reload to force the Server to re-cache the rooms so the Portal (the player's connection) can see them.


* **In-Game QA:** Teleport to the new Z-coordinate (`teleport (0,0,sector two)`). Walk the perimeter, check the room descriptions, and ensure the `display_symbol` renders correctly on the map UI.

### Phase 4: Implementation & Linking (World Integration)

Once the Z-level is spawned and tested, it is technically floating in a void. You must stitch it into the fabric of your existing game world.

* **Z-Level Transitions:** XYZGrid natively supports moving up and down between maps. You can add specific transition nodes to your map strings (like `U` for a staircase going Up) and map them to a `TransitionNode` in your legend, pointing it to the exact `(X, Y, Z)` coordinate of the connecting map.
* **Teleportation/Transit Points:** If the map is geographically separated (like another city), you can implement custom Evennia Exits or transit commands (like "board train") in an adjacent generic Evennia room that explicitly moves the character's location to the XYZ coordinate.