"""
Purpose:  The Godot client's portal service: the contrib's BBCode conversion,
          plus the two things it is missing.

Description:
          Evennia's godotwebsocket contrib gives port 4008 a protocol that
          converts ANSI to BBCode for a RichTextLabel. It is a good 80 lines
          and this module inherits all of it. It has two gaps that only matter
          once a Godot client is the client people actually use, and under
          ENG-0006 that is where this is going.

          GAP 1 -- NO KEEPALIVE ON 4008.
          INFRA-0001 §5.2 says the 45-second websocket ping "covers the Godot
          client too". It does not, and the reason is easy to miss:
          WEBSOCKET_PROTOCOL_CLASS is read in exactly one place,
          evennia/server/portal/service.py, which builds the MAIN webclient
          service on 4002. The contrib builds its own service and hardcodes
          `factory.protocol = GodotWebSocketClient`, which subclasses the STOCK
          WebSocketClient. So KeepAliveWebSocketClient never touches 4008, and
          a Godot client behind Cloudflare would be closed with an abnormal
          1006 after ~100 seconds of quiet -- the exact failure that ping
          exists to prevent, measured at 125.6s / 126.0s / 126.9s in
          INFRA-0001. Fixed here by inheriting from both.

          GAP 2 -- BBCODE IS MARKUP, AND GAME TEXT IS NOT ESCAPED.
          `parse_to_bbcode` builds BBCode out of ANSI, but its TextTag emits
          its text verbatim: a `[` that was already in the game's own text
          survives into the RichTextLabel, which parses it. Measured against
          the real parser on 08/25/2026:

              'Bob[b]HUGE[/b]'            -> 'Bob[b]HUGE[/b]'
              'Bob[color=red]red[/color]' -> 'Bob[color=red]red[/color]'

          Both reach every player who can see that name. `[color=...]` lets a
          player forge the colours the game uses for system messages, and
          `[img]` asks the client to fetch a URL the player chose.

          The URL auto-linker then makes it worse rather than better, because
          `convert_urls` runs AFTER the tags are built and rewrites inside the
          injected one:

              'Bob[url=https://x/]click[/url]'
                  -> 'Bob[url=[url=https://x/]https://x/[/url]]click[/url]'

          So the failure is not only injection, it is corrupted output for
          anything containing a bracket and a URL.

          THE FIX IS ONE SUBSTITUTION, AND WHERE IT HAPPENS IS THE WHOLE
          POINT. Escaping runs on the text BEFORE the contrib sees it, so it
          escapes only what the GAME wrote. Every tag in the final frame is
          generated afterwards, out of ANSI codes, by code that never sees a
          literal bracket. Escaping the contrib's OUTPUT instead would destroy
          the very tags the client needs.

          Only `[` is escaped. A lone `]` opens nothing, so leaving it alone
          keeps `[MODTOOL] admin godmode Bob` rendering as itself rather than
          as `[lb]MODTOOL[rb]`, which is the audit line every staff action
          writes.

Author: Nick Hobar
Creation date: 08/25/2026
"""

from autobahn.twisted import WebSocketServerFactory
from twisted.application import internet

from django.conf import settings
from evennia.contrib.base_systems.godotwebsocket.webclient import (
    GodotWebSocketClient)
from evennia.server.portal.portalsessionhandler import PORTAL_SESSIONS

from server.conf.websocket import KeepAliveWebSocketClient


# The only character that can open a BBCode tag. `]` closes nothing on its own,
# so escaping it too would only mangle ordinary prose -- see the module
# docstring on the [MODTOOL] audit line.
_TAG_OPEN = "["

# Godot's RichTextLabel escape for a literal `[`. `[rb]` is its counterpart for
# `]` and is deliberately unused here.
_TAG_OPEN_ESCAPED = "[lb]"

# Loopback-only when Evennia is in lockdown, matching the contrib exactly.
_LOCKDOWN_INTERFACE = "127.0.0.1"


def escape_bbcode(text: str) -> str:
    """
    Purpose: Neutralise BBCode a player could have typed into game text.

    Entry:
        text - one line of game output, before any ANSI-to-BBCode conversion.
        A non-string is returned unchanged.

    Exit/Returns:
        The same text with every `[` replaced by `[lb]`, which a RichTextLabel
        renders as a literal `[`.

    Module Globals:
        _TAG_OPEN, _TAG_OPEN_ESCAPED read.

    Methodology:
        A single replace, deliberately. A denylist of known-dangerous tags
        (`img`, `url`, `color`) would have to be revised every time Godot adds
        a tag, and would be wrong the moment it did. Escaping the character
        that can open ANY tag cannot go stale.

        This must run BEFORE parse_to_bbcode, never after: the tags that
        conversion produces are exactly what the client needs, and escaping
        them would leave a player reading `[lb]color=#ff0000]`.

    Notes/References:
        Godot RichTextLabel BBCode escapes: `[lb]` and `[rb]`.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    if not isinstance(text, str):
        return text

    return text.replace(_TAG_OPEN, _TAG_OPEN_ESCAPED)


class BlackoutGodotWebSocketClient(KeepAliveWebSocketClient,
                                   GodotWebSocketClient):
    """
    Purpose: The contrib's Godot protocol, with the keepalive and escaping.

    Notes/References:
        The base order is load-bearing. Both parents descend from
        evennia.server.portal.webclient.WebSocketClient, so the MRO is
        Blackout -> KeepAlive -> Godot -> WebSocketClient. That gives
        `onOpen`/`onClose` from KeepAliveWebSocketClient (which is what starts
        and stops the ping) and `send_text` from GodotWebSocketClient (which is
        what makes the BBCode). Swapping the bases would silently drop the
        keepalive and put the stock HTML converter back on 4008.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """

    def send_text(self, *args, **kwargs) -> None:
        """
        Purpose: Escape game-authored BBCode, then send as the contrib does.

        Entry:
            args[0] is the text to send, when there is one. Signature must
            match the contrib's, which the sessionhandler calls positionally.

        Exit/Returns:
            No return. Delegates the whole conversion and send to the contrib.

        Module Globals:
            None written.

        Methodology:
            Escape and delegate, rather than reimplement. The contrib's
            send_text also handles `nocolor`, the prompt flag and the outputfunc
            envelope; copying that here to insert one substitution would be a
            second copy of logic that already works, and it would rot the first
            time the contrib changed.

            Only args[0] is touched. The contrib reads no other positional
            argument, and kwargs carries options rather than text.

        Notes/References:
            See the module docstring for what happens without this, measured.

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        if args:
            args = list(args)
            args[0] = escape_bbcode(args[0])

        super().send_text(*args, **kwargs)


def start_plugin_services(portal) -> None:
    """
    Purpose: Add the Godot websocket service to the Portal.

    Entry:
        portal - the Portal application, supplied by Evennia's plugin loader.
        settings must define GODOT_CLIENT_WEBSOCKET_PORT and
        GODOT_CLIENT_WEBSOCKET_CLIENT_INTERFACE.

    Exit/Returns:
        No return. The Portal gains one TCPServer service.

    Module Globals:
        _LOCKDOWN_INTERFACE read.

    Methodology:
        A near-copy of the contrib's own start_plugin_services, and it has to
        be: the contrib hardcodes `factory.protocol = GodotWebSocketClient`,
        with no setting and no hook to point it anywhere else. Installing a
        different protocol therefore means building the service, which is
        fifteen lines, rather than subclassing something.

        settings.py names THIS module in PORTAL_SERVICES_PLUGIN_MODULES instead
        of the contrib's. Naming both would bind port 4008 twice.

    Notes/References:
        evennia/contrib/base_systems/godotwebsocket/webclient.py is the
        original. Keep this in step with it if the contrib is ever updated.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    class GodotWebsocket(WebSocketServerFactory):
        """Named for the Portal's service log, as the contrib does."""

    factory = GodotWebsocket()
    factory.noisy = False
    factory.protocol = BlackoutGodotWebSocketClient
    factory.sessionhandler = PORTAL_SESSIONS

    # `django.conf.settings`, not `evennia.settings` and not
    # `evennia.settings_default`. The contrib uses both, and each is a trap:
    # `evennia.settings` is a lazy proxy that is None until the launcher
    # populates it, and `from evennia.settings_default import LOCKDOWN_MODE`
    # binds the SHIPPED DEFAULT at import time -- so a game that sets
    # LOCKDOWN_MODE = True in its own settings.py would still be read as False
    # here and the port would bind publicly. Reading it off django.conf honours
    # the game's value, and matches server/conf/websocket.py.
    if getattr(settings, "LOCKDOWN_MODE", False):
        interface = _LOCKDOWN_INTERFACE
    else:
        interface = settings.GODOT_CLIENT_WEBSOCKET_CLIENT_INTERFACE

    port = settings.GODOT_CLIENT_WEBSOCKET_PORT
    service = internet.TCPServer(port, factory, interface=interface)
    service.setName("BlackoutGodotWebSocket%s:%s" % (interface, port))
    portal.addService(service)
