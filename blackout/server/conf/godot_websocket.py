"""
Purpose:  The Godot client's portal service: the contrib's BBCode conversion,
          plus the three things it is missing.

Description:
          Evennia's godotwebsocket contrib gives port 4008 a protocol that
          converts ANSI to BBCode for a RichTextLabel. It is a good 80 lines
          and this module inherits all of it. It has three gaps that only
          matter once a Godot client is the client people actually use, and
          under ENG-0006 that is where this is going.

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
          POINT -- it has to run after every `[` that MEANS something has been
          consumed, and before the first `[` that means something is written.
          There is exactly one such moment, in the middle of the contrib's own
          `parse`, which is why BlackoutBBCodeParser below exists rather than
          a wrapper around it.

              raw text            `|[g47|[x`, `Bob[color=red]x[/color]`
              parse_ansi          markup and MXP become ESC sequences
          >>> ESCAPE HERE         every remaining `[` is the game's own
              tag building        ESC sequences become [color=...] and [url=]
              output              only generated tags carry a live bracket

          Escaping BEFORE parse_ansi -- which is what this module did until
          08/27/2026 -- is too early, and it broke every coloured screen in
          the game rather than only the rare one. Two kinds of `[` are already
          in the text at that point and neither is the game's prose:

              `ESC[0m`  an ANSI sequence, which EvTable emits directly. It
                        became `ESC[lb]0m`, which the ANSI splitter no longer
                        recognises, so it reached the player as literal escape
                        codes -- every menu table in the game, the banking
                        screen included.
              `|[g`     Evennia's BACKGROUND colour markup. It became
                        `|[lb]g`, which parse_ansi no longer recognises, so the
                        dossier's hitpoint bar read `|[g47 / 47|[x`.

          Escaping AFTER the whole conversion is too late in the other
          direction: it would destroy the very tags the client needs, leaving
          the player reading `[lb]color=#ff0000]`.

          Only `[` is escaped. A lone `]` opens nothing, so leaving it alone
          keeps `[MODTOOL] admin godmode Bob` rendering as itself rather than
          as `[lb]MODTOOL[rb]`, which is the audit line every staff action
          writes.

          GAP 3 -- THE CONTRIB DELETES CHARACTERS HTML HAS TO ESCAPE.
          Its whole-text substitution is inherited from the HTML parser, where
          `<`, `&`, `>` and tabs each become an entity, and it returns None
          for all of them. Measured against the real parser, 08/27/2026:

              'HP -> 40'          -> 'HP - 40'
              'usage: get <item>' -> 'usage: get item'
              'Tom & Jerry'       -> 'Tom  Jerry'

          A RichTextLabel escapes `[` and nothing else, so all four travel as
          themselves. See BlackoutBBCodeParser.sub_text.

VERIFIED LIVE, 08/25/2026, against the running server on 4008:

    keepalive : PING frame received at exactly 45.0s on an idle socket.
                The contrib's protocol sends none, so its arrival is proof
                this module is the one bound to the port.

    escaping  : sending `look [color=red]INJECTED[/color] [img]...[/img]`
                came back as
                `look [lb]color=red]INJECTED[lb]/color] [lb]img]...`
                -- and on an UNAUTHENTICATED session, because Evennia echoes
                an unknown command back, so the vector is reachable before
                anyone logs in.

MEASURED AGAINST THE REAL PARSER, 08/27/2026, when the escape moved:

    a menu's option table, which EvTable renders with raw ANSI

        before  '|ESC[lb]0m ESC[lb]22mESC[lb]33m1ESC[lb]0m ...'
        after   '| [color=#808000]1[/color] | View storage |'

    the dossier's hitpoint bar, which is background markup

        before  '|[lb]g47 / 47|[lb]x'
        after   '[bgcolor=#00ff00]47 / 47[/bgcolor]'

    and the injection cases above are unchanged, including the one the
    earlier order could not have caught: `Bob|[img]u[/img]`, where the
    bracket rides an INVALID colour code and so survives parse_ansi.

Author: Nick Hobar
Creation date: 08/25/2026
"""

import json

from autobahn.twisted import WebSocketServerFactory
from autobahn.websocket.compress import (
    PerMessageDeflateOffer, PerMessageDeflateOfferAccept)
from twisted.application import internet

from django.conf import settings
from evennia.contrib.base_systems.godotwebsocket.text2bbcode import (
    parse_to_bbcode)
from evennia.contrib.base_systems.godotwebsocket.webclient import (
    GodotWebSocketClient)
from evennia.server.portal.portalsessionhandler import PORTAL_SESSIONS

# The parser moved to a pure module on 09/18/2026, so the Server can convert a
# menu node without importing the Portal. Imported back here, so this module
# and every import of these names from it are unchanged.
from server.conf.bbcode import (  # noqa: F401
    BLACKOUT_BBCODE_PARSER,
    BlackoutBBCodeParser,
    _TAG_OPEN,
    _TAG_OPEN_ESCAPED,
    escape_bbcode,
)
from server.conf.websocket import KeepAliveWebSocketClient


# Loopback-only when Evennia is in lockdown, matching the contrib exactly.
_LOCKDOWN_INTERFACE = "127.0.0.1"

class BlackoutGodotWebSocketClient(KeepAliveWebSocketClient,
                                   GodotWebSocketClient):
    """
    Purpose: The contrib's Godot protocol, with the keepalive and escaping.

    Notes/References:
        The base order is load-bearing. Both parents descend from
        evennia.server.portal.webclient.WebSocketClient, so the MRO is
        Blackout -> KeepAlive -> Godot -> WebSocketClient. That gives
        `onOpen`/`onClose` from KeepAliveWebSocketClient, which is what starts
        and stops the ping. Swapping the bases would silently drop the
        keepalive and put the stock HTML converter back on 4008 for anything
        send_text below does not override.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """

    def send_text(self, *args, **kwargs) -> None:
        """
        Purpose: Send one line of game output as BBCode, escaped.

        Entry:
            args[0] is the text to send, when there is one. Signature must
            match the contrib's, which the sessionhandler calls positionally.

        Exit/Returns:
            No return. One frame is written to the socket.

        Module Globals:
            BLACKOUT_BBCODE_PARSER read.

        Methodology:
            The contrib's own send_text, with ONE argument different: the
            parser. `parse_to_bbcode` takes it as a keyword and the contrib
            never passes one, so its module-level default is bound at def time
            and cannot be reached from a subclass -- which is why this is a
            copy of twelve lines rather than a call to super().

            The alternative was to keep delegating and escape beforehand, and
            that is exactly what this module did until 08/27/2026. It cannot
            work: escaping before the contrib means escaping before parse_ansi,
            and the module docstring has the measurements.

        Notes/References:
            KEEP IN STEP WITH THE CONTRIB's send_text, which owns the `nocolor`
            flag, the prompt flag and the outputfunc envelope reproduced here.

        Author: Nick Hobar
        Creation date: 08/25/2026
        """
        if not args:
            return

        args = list(args)
        text = args[0]

        if text is None:
            return

        flags = self.protocol_flags
        options = kwargs.pop("options", {})
        nocolor = options.get("nocolor", flags.get("NOCOLOR", False))
        prompt = options.get("send_prompt", False)
        cmd = "prompt" if prompt else "text"
        args[0] = parse_to_bbcode(text, strip_ansi=nocolor,
                                  parser=BLACKOUT_BBCODE_PARSER)

        # [cmdname, args, kwargs], the form every Evennia outputfunc travels in.
        self.sendLine(json.dumps([cmd, args, kwargs]))


def _accept_deflate(offers):
    """
    Purpose: Accept a client's permessage-deflate offer, so the statefeed's
             large payloads are compressed on the wire.

    Entry:
        offers - the compression extensions the client offered, in its
                 preference order. Autobahn calls this once per handshake and
                 only when the client offered something.

    Exit/Returns:
        Returns a PerMessageDeflateOfferAccept for the first deflate offer, or
        None to decline every offer and speak uncompressed.

    Module Globals:
        None.

    Methodology:
        WHY THIS IS WORTH A CALLBACK AT ALL. Autobahn compresses nothing unless
        a server explicitly accepts, and Evennia sets no protocol options on
        any of its factories -- so every frame this port has ever sent went out
        raw. Measured on a whole-map room_players payload: 88,058 bytes raw,
        5,704 deflated, a 15.4x cut. See
        docs/2026-09-03-PERF-0002-crowd-scaling.md.

        WHY IT MATTERS MOST ON THE WEBSITE. A web-exported Godot build does not
        use WebSocketPeer's own implementation; it delegates to the browser's
        native WebSocket, which offers permessage-deflate on every handshake
        and inflates transparently. So the browser clients -- the ones reaching
        this server through a Cloudflare tunnel rather than over a LAN -- are
        exactly the ones that negotiate this, with no client change at all.
        Cloudflare proxies websocket frames without compressing them, so the
        origin is the only place the saving can be taken.

        WHY DECLINING IS SAFE. A native desktop build whose peer does not offer
        deflate never reaches this function, and the connection is byte-for-byte
        what it was before. There is no flag to keep in step and no version to
        gate on: the handshake already negotiates it.

        The offer is accepted AS OFFERED, with no window or context-takeover
        counter-proposal. Autobahn's defaults are already the two things worth
        having -- a full 15-bit (32 KiB) window and context takeover left on,
        so the deflate context survives ACROSS messages and consecutive
        room_players payloads back-reference each other. Naming them
        explicitly would only add a failure mode: `request_max_window_bits` is
        rejected by autobahn unless the client's offer set
        `accept_max_window_bits`, so a client that offered plain deflate would
        raise here, inside a handshake, on the Portal.

        The FIRST deflate offer is taken rather than the best one scored. The
        client sends its preferences in order, and picking anything but its
        first choice is a negotiation this server has no reason to want.

    Notes/References:
        Autobahn 20.12.3's compression API is snake_case
        (`request_max_window_bits`); the camelCase spelling in its older
        examples is not accepted by this version.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    for offer in offers:
        if isinstance(offer, PerMessageDeflateOffer):
            return PerMessageDeflateOfferAccept(offer)

    return None


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
    class BlackoutGodotWebsocket(WebSocketServerFactory):
        """
        Named so the Portal log says WHICH Godot service started.

        The contrib's own factory is called `GodotWebsocket` with the comment
        "Only here for better naming in logs" -- and twisted logs the FACTORY
        CLASS name, not the service name set below. Reusing the contrib's name
        here made the two indistinguishable in portal.log, so after a reboot
        there was no way to tell whether the replacement had actually taken
        without attaching to the port. Hence a different name.
        """

    factory = BlackoutGodotWebsocket()
    factory.noisy = False
    factory.protocol = BlackoutGodotWebSocketClient
    factory.sessionhandler = PORTAL_SESSIONS

    # Compression is OPT-IN in autobahn and Evennia opts in nowhere, so without
    # this line every frame leaves uncompressed. See _accept_deflate for the
    # measurements and for why the browser clients are the ones that benefit.
    factory.setProtocolOptions(perMessageCompressionAccept=_accept_deflate)

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
