# Welcome to Evennia!

This is your game directory, set up to let you start with
your new game right away. An overview of this directory is found here:
https://github.com/evennia/evennia/wiki/Directory-Overview#the-game-directory

You can delete this readme file when you've read it and you can
re-arrange things in this game-directory to suit your own sense of
organisation (the only exception is the directory structure of the
`server/` directory, which Evennia expects). If you change the structure
you must however also edit/add to your settings file to tell Evennia
where to look for things.

Your game's main configuration file is found in
`server/conf/settings.py` (but you don't need to change it to get
started). If you just created this directory (which means you'll already
have a `virtualenv` running if you followed the default instructions),
`cd` to this directory then initialize a new database using

    evennia migrate

To start the server, stand in this directory and run

    evennia start

This will start the server, logging output to the console. Make
sure to create a superuser when asked. By default you can now connect
to your new game using a MUD client on `localhost`, port `4000`.  You can
also log into the web client by pointing a browser to
`http://localhost:4001`.

# Getting started

From here on you might want to look at one of the beginner tutorials:
http://github.com/evennia/evennia/wiki/Tutorials.

Evennia's documentation is here:
https://github.com/evennia/evennia/wiki.

Enjoy!

# BLACKOUT

## Character stuff
### Update all characters in a loop
`from typeclasses.characters import Character; [char.at_object_creation() for char in Character.objects.all()]`

### Add object (e.g., cutting node)
`create/drop Rusty Pole:typeclasses.gathering_nodes.RustyPole`

### Set attribute for character in same room
`set testchar2/has_cutting_reward = True`
OR
`py self.search("testchar2").db.has_cutting_reward = True`

### Set echo back player input
option localecho = true

## Environment stuff
### Update maps

Use this standard loop whenever you expand a grid, shrink a grid, change room coordinates, or alter the layout of an ASCII map.

**1. Edit Map File**
Make structural changes in file (e.g., `world/maps/test_neo_cairo.py`).

* **Rule:** Ensure all new symbols are explicitly defined in the `legend` dictionary mapping to the relevant node (e.g., `TradeTownNode`).
* **Rule:** Respect the Evennia spacing rules (no spaces between rooms/links, padding around the `+` borders).

**2. Delete the Old Z-Level**
Before spawning new custom rooms, you must cleanly erase the existing ones from that specific Z-coordinate. In your terminal, run:

```bash
evennia xyzgrid delete "[z-coord-name]"
```

e.g., `evennia xyzgrid delete "trade town sector 1"`

**3. Update the Grid Manager's Memory**
Tell the system to read the updated Python file and load the new layout into its cache:

```bash
evennia xyzgrid add [map_location]
```

e.g., `evennia xyzgrid add world.maps.test_neo_cairo`

**4. Spawn the New Grid**
Write the new map layout to the physical database:

```bash
evennia xyzgrid spawn
```

**5. Refresh the Server Caches**
Because the game state was physically mutated independent of the portal process, have to force the system to fire its reload hooks and re-import modules:

```bash
evennia reload
```

### The Troubleshooting Procedure (The Nuclear Option)

If you ever make a typo in a map file (like using a symbol not in your legend) and the `spawn` command crashes with a `RuntimeError`, the Standard Procedure will temporarily break. The crash leaves behind "ghost rooms" that the CLI `delete` command cannot see.

If that happens, use this recovery loop:

**1. Fix the Map File**
Correct the typo or legend mismatch in [map_name]

**2. Manually Sweep the Database**
Drop into the Evennia interactive Python shell (`evennia shell`) and explicitly delete the physical objects to clear the physical space:

```python
from typeclasses.rooms import GridTile
from evennia.contrib.grid.xyzgrid.xyzroom import XYZExit

GridTile.objects.all().delete()
XYZExit.objects.all().delete()
```

*(Type `quit()` to exit the shell).*

**3. Resume the Standard Build**
Now that the physical database is empty, can safely load and spawn the fixed map:

```bash
evennia xyzgrid add [map_location]
evennia xyzgrid spawn
evennia reload
```