"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: Cases for an EvMenu drawn as a pop-up.

             The menu here is a dict of three nodes, built for the test, so no
             case depends on the wording of a game menu. The cases send each
             button's command through the real parser, the way a click does,
             and read where the menu went.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.interface.popups.tests.test_menu_popup
"""

from unittest import mock

from evennia import create_object
from evennia.utils.test_resources import EvenniaCommandTest

from systems.interface.menus.base_menu import start_blackout_menu
from systems.interface.menus.constants import QUIT_KEYS
from systems.interface.popups import menu as menu_popup
from systems.interface.popups import service
from systems.interface.popups.popup_defs.bank import BANK_POPUP_KEY
from systems.interface.statefeed import buffer
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import events
from systems.interface.statefeed import popup as popup_feed
from systems.interface.statefeed import subscriptions
from typeclasses.bank_nodes import BankNode
from typeclasses.characters import Character as BlackoutCharacter


# ─── Private constant definitions ────────────────────────────────────────────

_START_TEXT = "Pick a door."
_ASK_TEXT = "Say a number."
_END_TEXT = "The door shuts."
_ANSWER = "42"


# ─── Private helper routines ─────────────────────────────────────────────────

def _node_start(caller, raw_string, **kwargs):
    return _START_TEXT, [
        {"desc": "Ask me", "goto": "node_ask"},
        {"desc": "Leave", "goto": "node_end"},
    ]


def _heard(caller, raw_string, **kwargs):
    caller.ndb.heard = raw_string.strip()

    return "node_end"


def _node_ask(caller, raw_string, **kwargs):
    return _ASK_TEXT, [{"key": "_default", "goto": _heard}]


def _node_end(caller, raw_string, **kwargs):
    return _END_TEXT, None


_MENU = {
    "start": _node_start,
    "node_ask": _node_ask,
    "node_end": _node_end,
}


class _MenuFixture(EvenniaCommandTest):
    """A character with a clean buffer and a way to read what it was told."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        buffer.reset()
        self.addCleanup(buffer.reset)

    def _subscribe(self) -> None:
        for session in self.char1.sessions.all():
            subscriptions.subscribe(session, feed_const.CHANNEL_CHAR_POPUP)

    def _open(self):
        return start_blackout_menu(self.char1, _MENU, startnode="start",
                                   cmd_on_exit=None)

    def _snapshot(self) -> dict:
        return popup_feed.build_payload(self.char1).to_dict()

    def _texts_while(self, action) -> str:
        """Run `action` and return every text line the character was sent."""
        with mock.patch.object(self.char1, "msg") as msg:
            action()

        lines = []

        for call in msg.call_args_list:
            text = call.kwargs.get("text", call.args[0] if call.args else None)

            if isinstance(text, tuple):
                text = text[0]

            lines.append(str(text))

        return "\n".join(lines)

    def _send(self, command: str) -> None:
        self.char1.execute_cmd(command, session=self.session)


# ─── Test cases ──────────────────────────────────────────────────────────────

class TestTheNodeIsAPopup(_MenuFixture):
    """A subscribed session sees the node as a pop-up, not as log text."""

    def test_the_snapshot_describes_the_node(self):
        self._subscribe()
        self._open()

        snapshot = self._snapshot()

        self.assertTrue(snapshot["open"])
        self.assertEqual(menu_popup.MENU_POPUP_KEY, snapshot["key"])
        self.assertIn(_START_TEXT, snapshot["text"])
        self.assertEqual(["Ask me", "Leave"],
                         [row["label"] for row in snapshot["choices"]])
        self.assertEqual(QUIT_KEYS[0], snapshot["close_command"])

    def test_the_node_text_stays_out_of_the_log(self):
        self._subscribe()

        said = self._texts_while(self._open)

        self.assertNotIn(_START_TEXT, said)

    def test_the_snapshot_reaches_the_client(self):
        self._subscribe()

        with mock.patch.object(events, "emit", return_value=1) as sent:
            self._open()

        channels = [call.args[1].channel for call in sent.call_args_list]
        self.assertIn(feed_const.CHANNEL_CHAR_POPUP, channels)

    def test_an_unsubscribed_session_gets_the_text(self):
        said = self._texts_while(self._open)

        self.assertIn(_START_TEXT, said)


class TestButtonsTypeWhatAPlayerTypes(_MenuFixture):
    """Each button sends its option key, and the menu answers it."""

    def test_a_button_moves_the_menu(self):
        self._subscribe()
        self._open()
        ask = self._snapshot()["choices"][0]

        self._send(ask["command"])

        self.assertIn(_ASK_TEXT, self._snapshot()["text"])

    def test_a_node_that_reads_text_offers_a_box(self):
        self._subscribe()
        self._open()
        self._send(self._snapshot()["choices"][0]["command"])

        self.assertTrue(self._snapshot()["input"])

    def test_the_box_sends_what_was_typed(self):
        self._subscribe()
        self._open()
        self._send(self._snapshot()["choices"][0]["command"])

        self._send(_ANSWER)

        self.assertEqual(_ANSWER, self.char1.ndb.heard)

    def test_a_node_with_no_typed_input_offers_no_box(self):
        self._subscribe()
        self._open()

        self.assertEqual({}, self._snapshot()["input"])


class TestClosing(_MenuFixture):
    """The close command and an ending node both take the pop-up down."""

    def test_the_close_command_closes_it(self):
        self._subscribe()
        self._open()

        self._send(QUIT_KEYS[0])

        self.assertFalse(self._snapshot()["open"])

    def test_an_ending_goes_to_the_log_and_closes(self):
        self._subscribe()
        self._open()
        leave = self._snapshot()["choices"][1]

        said = self._texts_while(lambda: self._send(leave["command"]))

        self.assertIn(_END_TEXT, said)
        self.assertFalse(self._snapshot()["open"])


class TestOnePopupAtATime(_MenuFixture):
    """A menu that opens replaces a grid pop-up."""

    def test_a_menu_replaces_the_bank(self):
        self._subscribe()
        terminal = create_object(BankNode, key="bank terminal", location=self.room1)
        service.open_popup(self.char1, BANK_POPUP_KEY, terminal)

        self._open()

        self.assertEqual(menu_popup.MENU_POPUP_KEY, self._snapshot()["key"])

    def test_closing_the_menu_leaves_nothing_open(self):
        self._subscribe()
        terminal = create_object(BankNode, key="bank terminal", location=self.room1)
        service.open_popup(self.char1, BANK_POPUP_KEY, terminal)
        self._open()

        self._send(QUIT_KEYS[0])

        self.assertFalse(self._snapshot()["open"])
