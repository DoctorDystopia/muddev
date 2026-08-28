"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: Guard the two things server/conf/godot_websocket.py adds to the
             godotwebsocket contrib, plus the invariant that keeps the
             structured feed safe for a BBCode client.

             All three failures here are SILENT ones. Nothing raises when a
             player's name injects BBCode, nothing raises when a socket has no
             keepalive, and nothing raises when a colour code rides a payload
             into a client that will not convert it. Each is only visible to
             somebody looking at the right screen at the right moment, which is
             what makes them worth a test rather than a comment.
"""

import unittest

from evennia.server.portal.webclient import WebSocketClient
from evennia.utils import evtable

from server.conf.godot_websocket import (
    BLACKOUT_BBCODE_PARSER, BlackoutGodotWebSocketClient, escape_bbcode)
from server.conf.websocket import KeepAliveWebSocketClient
from systems.statefeed import constants as const
from systems.statefeed import payloads


class BBCodeEscapingTests(unittest.TestCase):
    """Game-authored text cannot become markup in a RichTextLabel."""

    def test_a_tag_a_player_could_type_is_neutralised(self):
        """
        The attack: an object or account named so that its name is markup.
        Measured against the real contrib parser before the fix -- every one of
        these passed through untouched.
        """
        hostile = (
            "Bob[b]HUGE[/b]",
            "Bob[color=red]system message[/color]",
            "Bob[img]https://evil.example/x.png[/img]",
            "Bob[url=https://evil.example]click[/url]",
        )

        for name in hostile:
            with self.subTest(name=name):
                escaped = escape_bbcode(name)

                self.assertNotIn(
                    "[b]", escaped.replace("[lb]", ""),
                    "a bare tag survived escaping")
                self.assertEqual(
                    escaped.count("[lb]"), name.count("["),
                    "every opening bracket must be escaped, no more and no less")

    def test_escaping_survives_the_whole_conversion(self):
        """
        The escape is only worth anything if it is still there after the parse
        has run, since that is what actually reaches the client.
        """
        converted = BLACKOUT_BBCODE_PARSER.parse("Bob[color=red]x[/color]")

        self.assertIn("[lb]", converted)
        self.assertNotIn("[color=red]", converted)

    def test_a_tag_riding_an_invalid_colour_code_is_still_neutralised(self):
        """
        The case the OLD escaping order could not have caught, and the reason
        the exemption is ESC rather than a pipe.

        `|[img]` is not a colour code -- there is no background code `i` -- so
        parse_ansi leaves it alone and the bracket reaches the client. A fix
        that spared a `[` following a pipe in order to keep `|[g` working would
        hand every player an `[img]` tag.
        """
        converted = BLACKOUT_BBCODE_PARSER.parse("Bob|[img]evil[/img]")

        self.assertNotIn("[img]", converted)
        self.assertIn("[lb]img]", converted)

    def test_real_colour_codes_still_become_real_tags(self):
        """
        The failure mode of over-escaping: escape the OUTPUT instead of the
        game's own text and the player reads `[lb]color=#ff0000]` in place of
        red text. Order is the whole fix, so it gets its own case.
        """
        converted = BLACKOUT_BBCODE_PARSER.parse("|rdanger|n")

        self.assertIn("[color=", converted)
        self.assertNotIn("[lb]color=", converted)

    def test_a_menu_table_arrives_as_colour_and_not_as_escape_codes(self):
        """
        The reported bug, and the reason the escape moved.

        EvTable renders its cells with REAL ANSI escapes rather than with
        Evennia markup, so escaping every `[` before the conversion turned each
        CSI introducer into `[lb]`, which the ANSI splitter no longer
        recognises. Every menu in the game then printed its escape codes at the
        player: the banking screen, the character sheet, crafting.
        """
        table = evtable.EvTable()
        table.add_row("|Y1|n", "View storage")

        converted = BLACKOUT_BBCODE_PARSER.parse(str(table))

        self.assertNotIn("[lb]", converted,
                         "an ANSI escape's own bracket was escaped")
        self.assertIn("[color=", converted,
                      "the table's colour never became a tag")
        self.assertIn("View storage", converted)

    def test_background_markup_still_becomes_a_background_tag(self):
        """
        The other half of the reported bug. The dossier draws its hitpoint and
        XP bars with BACKGROUND markup, which is spelled `|[g` -- a pipe and
        then the one character this module escapes. It reached players as the
        literal text `|[g47 / 47|[x`.
        """
        converted = BLACKOUT_BBCODE_PARSER.parse("|[g47 / 47|[x")

        self.assertIn("[bgcolor=", converted)
        self.assertNotIn("[lb]", converted)

    def test_angle_brackets_ampersands_and_tabs_are_not_eaten(self):
        """
        The second half of the reported formatting bug, and a different
        mechanism from the first.

        The contrib inherits its whole-text substitution from the HTML parser,
        where `<`, `&`, `>` and tabs must all become entities -- and returns
        None for every one of them, which deletes them. None of the three
        means anything to a RichTextLabel.
        """
        pairs = (
            ("HP -> 40", "HP -> 40"),
            ("usage: get <item>", "usage: get <item>"),
            ("Tom & Jerry", "Tom & Jerry"),
            # Evennia's tab markup, which became a tab and was then eaten.
            ("a|-b", "a\tb"),
        )

        for sent, expected in pairs:
            with self.subTest(sent=sent):
                self.assertEqual(BLACKOUT_BBCODE_PARSER.parse(sent), expected)

    def test_a_line_ending_is_still_normalised(self):
        """The one substitution that pass is actually for."""
        self.assertEqual(
            BLACKOUT_BBCODE_PARSER.parse("line1\r\nline2"), "line1\nline2")

    def test_an_escaped_pipe_is_not_read_twice(self):
        """
        Why BlackoutBBCodeParser copies the contrib's `parse` instead of
        wrapping it. Wrapping means parse_ansi runs twice, and it is not
        idempotent: a doubled pipe is the escape for a literal one, and a
        second pass over what that produces reads the result as a real code.
        """
        self.assertEqual(BLACKOUT_BBCODE_PARSER.parse("a ||n b"), "a |n b")

    def test_the_audit_line_still_reads_as_itself(self):
        """
        Every staff action writes a [MODTOOL] line. `]` opens nothing, so it is
        deliberately not escaped -- escaping it too would render the line as
        `[lb]MODTOOL[rb]` for no gain.
        """
        escaped = escape_bbcode("[MODTOOL] admin godmode Bob")

        self.assertEqual(escaped, "[lb]MODTOOL] admin godmode Bob")

    def test_text_with_no_brackets_is_untouched(self):
        """The common case must cost nothing and change nothing."""
        plain = "You attack the mutant raider."

        self.assertEqual(escape_bbcode(plain), plain)

    def test_a_non_string_is_passed_through(self):
        """
        send_text is called positionally by the sessionhandler and args[0] is
        not guaranteed to be a str. Escaping must not be the thing that raises.
        """
        self.assertIsNone(escape_bbcode(None))
        self.assertEqual(escape_bbcode(7), 7)


class GodotProtocolCompositionTests(unittest.TestCase):
    """The class actually inherits the two behaviours it is built from."""

    def test_the_godot_protocol_carries_the_keepalive(self):
        """
        The bug this class exists for. WEBSOCKET_PROTOCOL_CLASS is read only by
        the main webclient service on 4002, and the contrib hardcodes the stock
        protocol for 4008 -- so before this, a Godot socket had no ping and
        Cloudflare closed it after ~100s idle (INFRA-0001 §5.2).
        """
        self.assertTrue(
            issubclass(BlackoutGodotWebSocketClient, KeepAliveWebSocketClient),
            "the Godot protocol must inherit the keepalive or 4008 goes quiet "
            "and drops behind Cloudflare")

    def test_the_keepalive_wins_over_the_stock_lifecycle(self):
        """
        Base ORDER decides this, not merely inheritance. onOpen must resolve to
        the keepalive's, or the ping never starts even though the class lists
        it as a parent.
        """
        resolution = BlackoutGodotWebSocketClient.onOpen

        self.assertIs(resolution, KeepAliveWebSocketClient.onOpen)
        self.assertIsNot(resolution, WebSocketClient.onOpen)

    def _frame_for(self, text, **options):
        """
        One send_text call, as the frame it puts on the wire.

        Built with __new__ rather than the constructor: a real protocol wants a
        transport and a sessionhandler, and neither is under test here. Only
        the one attribute send_text actually reads is supplied.
        """
        import json
        from unittest import mock

        protocol = BlackoutGodotWebSocketClient.__new__(
            BlackoutGodotWebSocketClient)
        protocol.protocol_flags = {}

        with mock.patch.object(BlackoutGodotWebSocketClient,
                               "sendLine") as written:
            protocol.send_text(text, options=options)

        self.assertTrue(written.called, "nothing was sent")

        return json.loads(written.call_args[0][0])

    def test_send_text_converts_and_escapes_on_the_way_out(self):
        """
        The behaviour, not the method name: what leaves the socket carries the
        game's colours as tags and the player's brackets as text.
        """
        cmd, args, _kwargs = self._frame_for("|rBob[color=red]x[/color]|n")

        self.assertEqual(cmd, "text")
        self.assertIn("[color=#ff0000]", args[0])
        self.assertIn("[lb]color=red]", args[0])

    def test_send_text_still_honours_the_prompt_and_nocolor_options(self):
        """
        send_text is a copy of the contrib's, so the two options it owns are
        worth asserting rather than assuming -- they are exactly the parts a
        copy loses silently.
        """
        cmd, _args, _kwargs = self._frame_for("hp 10/10", send_prompt=True)

        self.assertEqual(cmd, "prompt")

        _cmd, args, _kw = self._frame_for("|rdanger|n", nocolor=True)

        self.assertEqual(args[0], "danger")


class FeedIsSafeForBBCodeTests(unittest.TestCase):
    """
    ENG-0006 §5.2: no colour code may ride a structured payload.

    The contrib overrides `send_text` ONLY. Structured channels go out through
    the inherited `send_default`, which never calls parse_to_bbcode -- so a
    colour code in a payload arrives at a Godot client as a literal `|r`, with
    no conversion layer anywhere to catch it. systems/banking/messages.py
    already carries a comment warning about exactly this; this is the check.
    """

    # Evennia's colour markup. `|` followed by a code letter or a digit run.
    _MARKERS = ("|r", "|g", "|y", "|b", "|m", "|c", "|w", "|n",
                "|R", "|G", "|Y", "|B", "|M", "|C", "|W",
                "|x", "|X", "|h", "|H", "|u", "|U", "|*", "|_")

    def _payload_classes(self):
        """
        Every payload class the feed defines, derived rather than listed.

        Per CLAUDE.md: never assert a census of a registry. A payload added
        tomorrow is covered without an edit here.
        """
        found = []

        for name in dir(payloads):
            candidate = getattr(payloads, name)
            is_class = isinstance(candidate, type)

            if is_class and hasattr(candidate, "channel"):
                found.append(candidate)

        return found

    def test_the_feed_defines_payloads_at_all(self):
        """Vacuity guard: every case below is empty without this."""
        self.assertTrue(
            self._payload_classes(),
            "no payload classes found, so the colour-code check is vacuous")

    def test_no_payload_channel_name_carries_colour_markup(self):
        """
        A channel name is the one string in a payload that is definitely sent
        and definitely never converted.
        """
        for payload_class in self._payload_classes():
            channel = getattr(payload_class, "channel", "")

            with self.subTest(payload=payload_class.__name__):
                for marker in self._MARKERS:
                    self.assertNotIn(marker, str(channel))

    def test_no_message_template_in_statefeed_constants_carries_markup(self):
        """
        The templates the server sends as whole commands, which the client
        forwards verbatim. A colour code in one would reach Godot as `|r` and
        would ALSO be sent back as part of a command.
        """
        for name in dir(const):
            if name.startswith("_"):
                continue

            value = getattr(const, name)

            if not isinstance(value, str):
                continue

            with self.subTest(constant=name):
                for marker in self._MARKERS:
                    self.assertNotIn(
                        marker, value,
                        "%s carries colour markup; the structured feed is "
                        "never run through parse_to_bbcode, so it would reach "
                        "a Godot client as a literal %s" % (name, marker))
