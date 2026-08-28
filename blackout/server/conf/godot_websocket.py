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
import re

from autobahn.twisted import WebSocketServerFactory
from twisted.application import internet

from django.conf import settings
from evennia.contrib.base_systems.godotwebsocket.text2bbcode import (
    TextToBBCODEparser, parse_to_bbcode)
from evennia.contrib.base_systems.godotwebsocket.webclient import (
    GodotWebSocketClient)
from evennia.server.portal.portalsessionhandler import PORTAL_SESSIONS
from evennia.utils.ansi import parse_ansi

from server.conf.websocket import KeepAliveWebSocketClient


# The only character that can open a BBCode tag, and the only one escaped.
#
# NOT the one immediately after an ESC: by the time this runs, markup has
# already become ANSI, and the `[` of a `CSI` sequence is the conversion's own
# input rather than the game's prose. Escaping it is what left every menu table
# printing raw escape codes at players -- see the module docstring.
#
# `]` closes nothing on its own and is deliberately left alone, which is what
# keeps the `[MODTOOL]` audit line rendering as itself.
_TAG_OPEN = re.compile(r"(?<!\x1b)\[")

# Godot's RichTextLabel escape for a literal `[`. `[rb]` is its counterpart for
# `]` and is deliberately unused here.
_TAG_OPEN_ESCAPED = "[lb]"

# Loopback-only when Evennia is in lockdown, matching the contrib exactly.
_LOCKDOWN_INTERFACE = "127.0.0.1"


def escape_bbcode(text: str) -> str:
    """
    Purpose: Neutralise BBCode a player could have typed into game text.

    Entry:
        text - one line of game output that has ALREADY been through
        parse_ansi, so that every `[` still in it is one the game wrote.
        A non-string is returned unchanged.

    Exit/Returns:
        The same text with every such `[` replaced by `[lb]`, which a
        RichTextLabel renders as a literal `[`.

    Module Globals:
        _TAG_OPEN, _TAG_OPEN_ESCAPED read.

    Methodology:
        A single substitution, deliberately. A denylist of known-dangerous
        tags (`img`, `url`, `color`) would have to be revised every time Godot
        adds a tag, and would be wrong the moment it did. Escaping the
        character that can open ANY tag cannot go stale.

        The one exclusion is the `[` of an ANSI CSI sequence, which always
        follows ESC. Those are the conversion's INPUT, not the game's prose,
        and escaping them is what broke every table and every coloured bar in
        the game until 08/27/2026.

        WHERE this runs is the rest of the fix and it is not this function's
        to decide -- see [BlackoutBBCodeParser].

    Notes/References:
        Godot RichTextLabel BBCode escapes: `[lb]` and `[rb]`.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    if not isinstance(text, str):
        return text

    return _TAG_OPEN.sub(_TAG_OPEN_ESCAPED, text)


class BlackoutBBCodeParser(TextToBBCODEparser):
    """
    Purpose: The contrib's ANSI-to-BBCode parser, with the escape moved to the
             one point in the conversion where the game's own brackets can
             still be told apart from the tags it is about to write, and with
             the HTML parser's character handling undone.

    Notes/References:
        The body of `parse` is the contrib's, with one line inserted after the
        ANSI conversion. It is copied rather than wrapped because there is no
        seam: `parse` calls parse_ansi itself and hands the result straight to
        the MXP substitutions, which are the first step that writes a bracket
        of its own. Calling super().parse on already-converted text would run
        parse_ansi TWICE, and that is not a no-op -- `||n`, the escape for a
        literal `|n`, survives one pass and becomes a real reset on the next.

        KEEP IN STEP WITH THE CONTRIB, the same way start_plugin_services
        below is kept in step with the contrib's own.

    Author: Nick Hobar
    Creation date: 08/27/2026
    """

    def sub_text(self, match):
        """
        Purpose: Replace one match of `re_string`, which covers line endings,
                 tabs, and the three characters HTML has to escape.

        Entry:
            match - a match of TextToHTMLparser.re_string.

        Exit/Returns:
            A line ending is normalised to "\\n"; everything else is returned
            as itself.

        Module Globals:
            None.

        Methodology:
            The contrib inherits this substitution from the HTML parser, where
            `<`, `&`, `>` and tabs all have to become entities -- and then
            returns None for every one of them, which DELETES them. Measured
            08/27/2026, on the real parser:

                'HP -> 40'          -> 'HP - 40'
                'usage: get <item>' -> 'usage: get item'
                'Tom & Jerry'       -> 'Tom  Jerry'

            None of the three means anything to a RichTextLabel, which escapes
            `[` and nothing else, so all three travel as themselves. The tab
            travels too: the label has its own `tab_size` and aligns to real
            tab stops, which expanding to a fixed run of spaces here could not.

        Notes/References:
            This is why the MXP substitutions two lines below can work at all:
            they match on markers the deletion was eating.

        Author: Nick Hobar
        Creation date: 08/27/2026
        """
        if match.groupdict()["lineend"]:
            return "\n"

        return match.group(0)

    def parse(self, text: str, strip_ansi: bool = False) -> str:
        """Convert one line of game text to BBCode, escaping what it wrote."""
        text = parse_ansi(text, strip_ansi=strip_ansi, xterm256=True, mxp=True)
        text = escape_bbcode(text)

        result = re.sub(self.re_string, self.sub_text, text)
        result = re.sub(self.re_mxplink, self.sub_mxp_links, result)
        result = re.sub(self.re_mxpurl, self.sub_mxp_urls, result)
        result = self.remove_bells(result)
        result = self.format_styles(result)
        result = self.remove_backspaces(result)
        result = self.convert_urls(result)

        return result


# The one parser every frame on 4008 goes through. Built once, like the
# contrib's own BBCODE_PARSER, because it holds no per-session state.
BLACKOUT_BBCODE_PARSER = BlackoutBBCodeParser()


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
