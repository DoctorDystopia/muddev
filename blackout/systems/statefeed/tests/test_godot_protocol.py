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

from evennia.contrib.base_systems.godotwebsocket.text2bbcode import (
    parse_to_bbcode)
from evennia.contrib.base_systems.godotwebsocket.webclient import (
    GodotWebSocketClient)
from evennia.server.portal.webclient import WebSocketClient

from server.conf.godot_websocket import (
    BlackoutGodotWebSocketClient, escape_bbcode)
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

    def test_escaping_survives_the_contribs_own_conversion(self):
        """
        The escape is only worth anything if it is still there after
        parse_to_bbcode has run, since that is what actually reaches the client.
        """
        converted = parse_to_bbcode(escape_bbcode("Bob[color=red]x[/color]"))

        self.assertIn("[lb]", converted)
        self.assertNotIn("[color=red]", converted)

    def test_real_colour_codes_still_become_real_tags(self):
        """
        The failure mode of over-escaping: escape the contrib's OUTPUT instead
        of its input and the player reads `[lb]color=#ff0000]` in place of red
        text. Order is the whole fix, so it gets its own case.
        """
        converted = parse_to_bbcode(escape_bbcode("|rdanger|n"))

        self.assertIn("[color=", converted)
        self.assertNotIn("[lb]color=", converted)

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

    def test_send_text_escapes_before_the_contrib_converts(self):
        """
        The behaviour, not the method name: what the contrib finally receives
        must already be escaped.

        Built with __new__ rather than the constructor: a real protocol wants a
        transport and a sessionhandler, and neither is under test here. The
        zero-argument `super()` in send_text still needs a genuine instance of
        the class to resolve against, though, which is why this is not just a
        bare object.

        Patching the CONTRIB method is what proves the ordering --
        `super().send_text` resolves there through the MRO, so whatever it
        records is exactly what conversion would have been handed.
        """
        from unittest import mock

        protocol = BlackoutGodotWebSocketClient.__new__(
            BlackoutGodotWebSocketClient)

        with mock.patch.object(GodotWebSocketClient, "send_text") as delegated:
            protocol.send_text("Bob[color=red]x[/color]")

        self.assertTrue(delegated.called, "the contrib was never delegated to")

        forwarded = delegated.call_args[0][0]

        self.assertNotIn("[color=red]", forwarded)
        self.assertIn("[lb]color=red]", forwarded)


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
