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

# Godot web socket.
#
# server.conf.godot_websocket, NOT the contrib module it wraps. It subclasses
# the contrib's protocol to add two things the contrib has no hook for:
#
#   - the 45s keepalive ping. WEBSOCKET_PROTOCOL_CLASS below is read only by
#     the MAIN webclient service on 4002 (evennia/server/portal/service.py);
#     the contrib builds its own service and hardcodes the stock protocol, so
#     4008 had no keepalive and would drop at ~100s idle behind Cloudflare.
#   - escaping BBCode a player typed, before the contrib converts ANSI into
#     BBCode. Without it a name containing [color=...] or [img] is markup in
#     every player's log.
#
# Naming both this and the contrib module would bind port 4008 twice.
PORTAL_SERVICES_PLUGIN_MODULES.append('server.conf.godot_websocket')
GODOT_CLIENT_WEBSOCKET_PORT = 4008
GODOT_CLIENT_WEBSOCKET_CLIENT_INTERFACE = "127.0.0.1"

######################################################################
# Public hosting - game.playblackout.io via Cloudflare Tunnel
#
# The tunnel dials out from this machine, so nothing is port-forwarded.
# Cloudflare terminates TLS at the edge and forwards plain HTTP to the
# ports below, which is why SECURE_PROXY_SSL_HEADER is required: without
# it Django believes every request arrived over http:// and rejects the
# secure-cookie handshake.
######################################################################

# Evennia defaults this to ["*"]. Narrow it - a wildcard lets anyone
# reach the site through any hostname that resolves here.
ALLOWED_HOSTS = [
    "game.playblackout.io",
    "localhost",
    "127.0.0.1",
]

# Admin logins and any form POST are rejected without this.
CSRF_TRUSTED_ORIGINS = ["https://game.playblackout.io"]

# Trust Cloudflare's forwarded scheme so request.is_secure() is correct.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Safe to enable now that every public request arrives over TLS.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# The three.js/GoldenLayout browser webclient is retired -- see
# archive/webclient-js/README.md. Godot (server/conf/godot_websocket.py,
# port 4008 below) is the sole client now, on every platform including the
# public website. This is Evennia's own gate: it 404s the Django /webclient/
# route and removes the "Play in the browser!"/"Play Online" links from the
# stock homepage and nav templates, since both are already wrapped in
# `{% if webclient_enabled %}` there.
WEBCLIENT_ENABLED = False

# The webclient template falls back to `"ws://" + hostname + ":4002"` when
# this is None (evennia/web/templates/webclient/base.html). Over HTTPS the
# browser blocks that as mixed content and the client silently never
# connects, so the wss:// URL must be stated explicitly. No query string -
# evennia.js appends its own session parameters.
#
# Left set even though WEBCLIENT_ENABLED is False above: this only gates the
# Django view/template, not the browser websocket service itself, which
# stays registered. Tearing that out means also editing the LIVE
# deploy/cloudflared/config.yml (a template here; the deployed copy is
# elsewhere) and restarting the tunnel service -- a live-infra change,
# deliberately not bundled into the webclient retirement.
WEBSOCKET_CLIENT_URL = "wss://game.playblackout.io/ws"

# Cloudflare closes a proxied websocket after ~100s with no traffic either
# way, as an abnormal 1006 with no reason attached -- which reads in-game as
# an aggressive inactivity disconnect even though IDLE_TIMEOUT is off below.
# Measured 08/21/2026: three silent sockets through the tunnel died at 125.6s,
# 126.0s and 126.9s; a socket pinged every 45s survived, and a control socket
# straight to ws://127.0.0.1:4002 stayed up for the full 30-minute test.
#
# This cannot be fixed from deploy/cloudflared/config.yml -- originRequest
# keepAliveTimeout covers cloudflared's HTTP pool to the origin, not the
# edge's websocket idle timer. The protocol below pings instead.
WEBSOCKET_PROTOCOL_CLASS = "server.conf.websocket.KeepAliveWebSocketClient"

# Seconds between those pings. Must stay well under the ~100s edge limit;
# 0 disables the keepalive and restores stock behaviour.
WEBSOCKET_KEEPALIVE_INTERVAL = 45.0

# Left explicit rather than inherited: the disconnects players reported were
# never Evennia's idle timer, and this records that we checked.
IDLE_TIMEOUT = -1

######################################################################
# Settings given in secret_settings.py override those in this file.
######################################################################
try:
    from server.conf.secret_settings import *
except ImportError:
    print("secret_settings.py file not found or failed to import.")
