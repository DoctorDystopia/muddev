r"""
Evennia settings file.

The available options are found in the default settings file found
here:

https://www.evennia.com/docs/latest/Setup/Settings-Default.html

Remember:

Don't copy more from the default file than you actually intend to
change; this will make sure that you don't overload upstream updates
unnecessarily.

When changing a setting requiring a file system path (like
path/to/actual/file.py), use GAME_DIR and EVENNIA_DIR to reference
your game folder and the Evennia library folders respectively. Python
paths (path.to.module) should be given relative to the game's root
folder (typeclasses.foo) whereas paths within the Evennia library
needs to be given explicitly (evennia.foo).

If you want to share your game dir, including its settings, you can
put secret game- or server-specific settings in secret_settings.py.

"""

# Use the defaults from Evennia unless explicitly overridden
from evennia.settings_default import *

######################################################################
# Evennia base server config
######################################################################

# This is the name of your game. Make it catchy!
SERVERNAME = "blackout"

# Use the custom ServerSession class for Blackout
SERVER_SESSION_CLASS = "server.conf.serversession.ServerSession"

# Add the XYZGrid command to the launcher
EXTRA_LAUNCHER_COMMANDS['xyzgrid'] = 'evennia.contrib.grid.xyzgrid.launchcmd.xyzcommand'
PROTOTYPE_MODULES += ['evennia.contrib.grid.xyzgrid.prototypes']

# Crafting recipe modules for the Evennia crafting contrib
CRAFT_RECIPE_MODULES = [
    "systems.crafting.recipes.foundry_recipes",
    "systems.crafting.recipes.metalsmith_recipes",
]

# Godot web socket
PORTAL_SERVICES_PLUGIN_MODULES.append('evennia.contrib.base_systems.godotwebsocket.webclient')
GODOT_CLIENT_WEBSOCKET_PORT = 4008
GODOT_CLIENT_WEBSOCKET_CLIENT_INTERFACE = "127.0.0.1"

######################################################################
# Settings given in secret_settings.py override those in this file.
######################################################################
try:
    from server.conf.secret_settings import *
except ImportError:
    print("secret_settings.py file not found or failed to import.")
