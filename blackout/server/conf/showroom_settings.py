r"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/03/2026
Description: The settings of the showroom server: the real game on a
             generated world that holds one of each item and one of each
             object kind. `world/showroom.py` makes the world, and
             `scripts/showroom.py` writes it and runs the tile sync.

             Selected on the command line, from blackout/:
                 ../evenv/Scripts/evennia.exe --settings showroom_settings.py start

             It imports the real game settings, so the showroom runs the
             same code. It changes four things:

             1. A separate database, `server/showroom.db3`. The live
                database never changes.
             2. A separate chunk directory, `world/showroom/`. The live
                chunk files never change.
             3. Separate play ports, on 127.0.0.1 only. The Cloudflare
                Tunnel forwards 4002 and 4008, so it reaches no showroom
                socket. Start the Godot client with
                `--server=ws://127.0.0.1:4108`.
             4. Separate log files in `server/logs/`.

             The web server stays on 4001, because a debug client loads the
             model files from `http://127.0.0.1:4001`. ALLOWED_HOSTS names
             the local host only. The tunnel sends the public host name, so
             Django refuses each public request for a page.

             ONE SERVER AT A TIME. The Evennia launcher writes `server.pid`
             and `portal.pid` into `blackout/server/`, and no setting moves
             them. Stop the live server before the showroom starts.
"""

import copy
import os

from server.conf.settings import *

SERVERNAME = "Blackout showroom"

# 1. The database. A copy, so that the dict of the live settings stays as it
# is for each other reader of that module.
DATABASES = copy.deepcopy(DATABASES)
DATABASES["default"]["NAME"] = os.path.join(GAME_DIR, "server",
                                            "showroom.db3")

# 2. The chunk directory. `scripts/showroom.py` writes it, and
# `systems/core/tilegrid/world.py` reads it.
TILE_WORLD_DIR = os.path.join(GAME_DIR, "world", "showroom")

# 3. The play ports. LOCKDOWN_MODE binds each port to 127.0.0.1, the Godot
# socket included (server/conf/godot_websocket.py).
LOCKDOWN_MODE = True
TELNET_PORTS = [4100]
WEBSOCKET_CLIENT_PORT = 4102
AMP_PORT = 4106
GODOT_CLIENT_WEBSOCKET_PORT = 4108
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# 4. The log files.
SERVER_LOG_FILE = os.path.join(LOG_DIR, "showroom_server.log")
PORTAL_LOG_FILE = os.path.join(LOG_DIR, "showroom_portal.log")
HTTP_LOG_FILE = os.path.join(LOG_DIR, "showroom_http_requests.log")
LOCKWARNING_LOG_FILE = os.path.join(LOG_DIR, "showroom_lockwarnings.log")
