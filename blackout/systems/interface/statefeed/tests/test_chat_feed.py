"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/29/2026
Description: Cases for the char_chat channel and the prefixes that it sends.

             The load-bearing case is
             `test_every_prefix_runs_the_command_it_names`: each mode prefix,
             with text added, must find the command that it names. A prefix
             that finds no command sends the player "Command not found" for
             each chat line.

             NOTHING HERE ASSERTS A CENSUS of the modes. The channel rows come
             from the channels that the account listens to.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.interface.statefeed.tests.test_chat_feed
"""

import json
from unittest import mock

from evennia.utils import create
from evennia.utils.test_resources import EvenniaTest

from commands.comms_cmds import PAGE_REPLY_SWITCH, CmdPage
from systems.interface.statefeed import chat as chat_feed
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import events as feed
from systems.interface.statefeed import resync, subscriptions
from typeclasses.channels import Channel
from typeclasses.characters import Character as BlackoutCharacter


# ─── Private constant definitions ────────────────────────────────────────────

# A channel key with a space, the case that needs the `=` form of the prefix.
_CHANNEL_KEY = "Night Market"
_SENT_TEXT = "hello there"
_CHANNEL_TYPECLASS = f"{Channel.__module__}.{Channel.__name__}"


# ─── Private helper routines ─────────────────────────────────────────────────

class _Fixture:
    """A channel to join, and payload helpers."""

    character_typeclass = BlackoutCharacter

    def _channel(self, locks: str = "listen:all();send:all()"):
        channel = create.create_channel(
            _CHANNEL_KEY, typeclass=_CHANNEL_TYPECLASS, locks=locks)

        return channel

    def _modes(self) -> list:
        return chat_feed.build_payload(self.char1).to_dict()["modes"]

    def _mode_keys(self) -> list:
        return [row["key"] for row in self._modes()]

    def _subscribe(self) -> None:
        for session in self.char1.sessions.all():
            subscriptions.subscribe(session, feed_const.CHANNEL_CHAR_CHAT)


# ─── Test cases ──────────────────────────────────────────────────────────────

class TestChannel(_Fixture, EvenniaTest):
    """The channel's declaration, which decides whether it can be reached."""

    def test_a_client_may_subscribe_to_it(self):
        self.assertIn(
            feed_const.CHANNEL_CHAR_CHAT, feed_const.SUBSCRIBABLE_CHANNELS)

    def test_channel_is_not_rate_capped(self):
        self.assertNotIn(
            feed_const.CHANNEL_CHAR_CHAT,
            feed_const.CHANNEL_MIN_INTERVAL_SECONDS)

    def test_channel_may_be_coalesced(self):
        self.assertIn(
            feed_const.CHANNEL_CHAR_CHAT, feed_const.COALESCABLE_CHANNELS)

    def test_emit_is_a_no_op_without_a_subscriber(self):
        self.assertEqual(0, feed.emit_chat(self.char1))

    def test_emit_reaches_a_subscribed_session(self):
        self._subscribe()

        self.assertGreater(feed.emit_chat(self.char1), 0)

    def test_resync_sends_it(self):
        with mock.patch.object(feed, "emit_chat", return_value=0) as mocked:
            resync.send_full_state(self.char1)

        mocked.assert_called_once_with(self.char1, force=True)


class TestPayload(_Fixture, EvenniaTest):
    """What each mode row says."""

    def test_the_speaker_is_the_character(self):
        payload = chat_feed.build_payload(self.char1).to_dict()

        self.assertEqual(self.char1.key, payload["speaker"])

    def test_every_row_is_well_formed(self):
        self._channel().connect(self.account)

        for row in self._modes():
            with self.subTest(mode=row["key"]):
                self.assertTrue(row["key"])
                self.assertTrue(row["label"])
                self.assertIn(row["type"], feed_const.MESSAGE_TYPES)
                self.assertTrue(row["prefix"].endswith(" "))

    def test_keys_are_unique(self):
        self._channel().connect(self.account)
        keys = self._mode_keys()

        self.assertEqual(len(keys), len(set(keys)))

    def test_a_joined_channel_is_a_mode(self):
        channel = self._channel()
        channel.connect(self.account)
        rows = [row for row in self._modes() if row["label"] == channel.key]

        self.assertEqual(1, len(rows))
        self.assertEqual(feed_const.MESSAGE_TYPE_CHANNEL, rows[0]["type"])

    def test_a_channel_the_player_cannot_send_to_is_not_a_mode(self):
        channel = self._channel(locks="listen:all();send:false()")
        channel.connect(self.account)

        labels = [row["label"] for row in self._modes()]

        self.assertNotIn(channel.key, labels)

    def test_reply_names_the_page_reply_switch(self):
        rows = [row for row in self._modes()
                if row["key"] == chat_feed.MODE_KEY_REPLY]

        self.assertEqual(f"{CmdPage.key}/{PAGE_REPLY_SWITCH} ", rows[0]["prefix"])
        self.assertEqual(feed_const.MESSAGE_TYPE_PAGE, rows[0]["type"])

    def test_an_observer_with_no_account_can_only_speak(self):
        keys = [row["key"] for row in chat_feed.chat_modes(self.obj1)]

        self.assertEqual([chat_feed.MODE_KEY_SAY, chat_feed.MODE_KEY_YELL],
                         keys)

    def test_both_speech_modes_go_on_the_say_tab(self):
        """A yell line has the `say` type, so its mode goes on that tab."""
        rows = [row for row in self._modes()
                if row["key"] in (chat_feed.MODE_KEY_SAY,
                                  chat_feed.MODE_KEY_YELL)]

        self.assertEqual(2, len(rows))

        for row in rows:
            with self.subTest(mode=row["key"]):
                self.assertEqual(feed_const.MESSAGE_TYPE_SAY, row["type"])

    def test_the_whole_payload_survives_json(self):
        self._channel().connect(self.account)

        json.dumps(chat_feed.build_payload(self.char1).to_dict())


class TestPrefixesRun(_Fixture, EvenniaTest):
    """Each prefix names a command that the player has."""

    def _command_names(self) -> set:
        names = set()

        for cmdset_owner in (self.char1, self.account):
            for command in cmdset_owner.cmdset.current.commands:
                names.add(command.key.lower())
                names.update(alias.lower() for alias in command.aliases)

        return names

    def test_every_prefix_runs_the_command_it_names(self):
        self._channel().connect(self.account)
        names = self._command_names()

        for row in self._modes():
            first_word = row["prefix"].split()[0]
            command_name = first_word.split("/")[0].lower()

            with self.subTest(mode=row["key"]):
                self.assertIn(command_name, names)

    def test_a_channel_prefix_sends_to_that_channel(self):
        channel = self._channel()
        channel.connect(self.account)
        row = [row for row in self._modes() if row["label"] == channel.key][0]

        with mock.patch.object(Channel, "msg") as sent:
            self.account.execute_cmd(row["prefix"] + _SENT_TEXT)

        self.assertIn(_SENT_TEXT, str(sent.call_args))
