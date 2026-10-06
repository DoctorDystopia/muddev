"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/29/2026
Description: Tests for Blackout's `page`: the routing tag on every line, and
             `page/reply`.

             The tag is what puts a page in the Private tab of the Godot
             client. `page/reply` is the line that the Reply chat mode sends,
             so the reply cases are the proof that the mode works.

             Each case runs the typed line through the account's own cmdset,
             so a lost cmdset entry fails here too.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        commands.tests.test_comms_cmds
"""

from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from commands.comms_cmds import PAGE_REPLY_SWITCH, CmdPage
from systems.interface.statefeed import constants as feed_const
from typeclasses.characters import Character as BlackoutCharacter


# ─── Private constant definitions ────────────────────────────────────────────

_FIRST_TEXT = "meet at the market"
_REPLY_TEXT = "on my way"


# ─── Private helper routines ─────────────────────────────────────────────────

def _lines(mocked_msg) -> list:
    """Each (text, kwargs) pair that a mocked msg got, as the call gave it."""
    pairs = []

    for call in mocked_msg.call_args_list:
        text = call.kwargs.get("text", call.args[0] if call.args else None)

        if isinstance(text, tuple):
            pairs.append((str(text[0]), text[1]))
        else:
            pairs.append((str(text), {}))

    return pairs


# ─── Test cases ──────────────────────────────────────────────────────────────

class TestPageTag(EvenniaTest):
    """Every line that page sends carries the page tag."""

    character_typeclass = BlackoutCharacter

    def _page(self, line: str):
        with mock.patch.object(self.account, "msg") as sender, \
                mock.patch.object(self.account2, "msg") as target:
            self.account.execute_cmd(line)

        return _lines(sender), _lines(target)

    def test_the_account_cmdset_holds_blackouts_page(self):
        found = self.account.cmdset.current.get(CmdPage.key)

        self.assertIsInstance(found, CmdPage)

    def test_the_target_gets_the_message_tagged(self):
        _sent, heard = self._page(
            f"{CmdPage.key} {self.account2.key} = {_FIRST_TEXT}")

        self.assertEqual(1, len(heard))
        self.assertIn(_FIRST_TEXT, heard[0][0])
        self.assertEqual(feed_const.MESSAGE_TYPE_PAGE,
                         heard[0][1].get(feed_const.MESSAGE_TYPE_KEY))

    def test_every_line_to_the_sender_is_tagged(self):
        sent, _heard = self._page(
            f"{CmdPage.key} {self.account2.key} = {_FIRST_TEXT}")

        self.assertTrue(sent)

        for text, kwargs in sent:
            with self.subTest(line=text):
                self.assertEqual(feed_const.MESSAGE_TYPE_PAGE,
                                 kwargs.get(feed_const.MESSAGE_TYPE_KEY))

    def test_the_history_read_is_tagged_too(self):
        self._page(f"{CmdPage.key} {self.account2.key} = {_FIRST_TEXT}")

        sent, _heard = self._page(CmdPage.key)

        self.assertIn(_FIRST_TEXT, " ".join(text for text, _ in sent))
        self.assertTrue(all(kwargs.get(feed_const.MESSAGE_TYPE_KEY)
                            == feed_const.MESSAGE_TYPE_PAGE
                            for _text, kwargs in sent))

    def test_a_page_with_no_equals_finds_its_target(self):
        _sent, heard = self._page(
            f"{CmdPage.key} {self.account2.key} {_FIRST_TEXT}")

        self.assertIn(_FIRST_TEXT, heard[0][0])


class TestPageReply(EvenniaTest):
    """`page/reply` goes to the last partner, in either direction."""

    character_typeclass = BlackoutCharacter

    def _reply_line(self, text: str) -> str:
        return f"{CmdPage.key}/{PAGE_REPLY_SWITCH} {text}"

    def test_a_reply_goes_back_to_the_account_that_paged(self):
        self.account2.execute_cmd(
            f"{CmdPage.key} {self.account.key} = {_FIRST_TEXT}")

        with mock.patch.object(self.account2, "msg") as heard:
            self.account.execute_cmd(self._reply_line(_REPLY_TEXT))

        self.assertIn(_REPLY_TEXT, " ".join(text for text, _ in _lines(heard)))

    def test_a_reply_goes_to_the_account_last_paged(self):
        self.account.execute_cmd(
            f"{CmdPage.key} {self.account2.key} = {_FIRST_TEXT}")

        with mock.patch.object(self.account2, "msg") as heard:
            self.account.execute_cmd(self._reply_line(_REPLY_TEXT))

        self.assertIn(_REPLY_TEXT, " ".join(text for text, _ in _lines(heard)))

    def test_a_reply_never_reads_a_target_from_the_message(self):
        # The message starts with the name of an account. A plain `page` reads
        # that word as the target. The reply must go to the partner, account2,
        # with the whole message.
        self.account.execute_cmd(
            f"{CmdPage.key} {self.account2.key} = {_FIRST_TEXT}")
        message = f"{self.account.key} {_REPLY_TEXT}"

        with mock.patch.object(self.account2, "msg") as heard:
            self.account.execute_cmd(self._reply_line(message))

        self.assertIn(message, " ".join(text for text, _ in _lines(heard)))

    def test_a_reply_with_no_partner_is_refused(self):
        with mock.patch.object(self.account, "msg") as sent:
            self.account.execute_cmd(self._reply_line(_REPLY_TEXT))

        self.assertIn("no page", " ".join(t for t, _ in _lines(sent)).lower())

    def test_an_empty_reply_is_refused(self):
        with mock.patch.object(self.account, "msg") as sent:
            self.account.execute_cmd(self._reply_line(""))

        self.assertIn("reply with what",
                      " ".join(t for t, _ in _lines(sent)).lower())
