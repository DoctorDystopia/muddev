"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/05/2026
Description: Tests for the commands of a saved login: `resume`, `remember`
             and `forget`, and for the echo rule of the server session.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py commands.tests.test_login_cmds
"""

from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from evennia.utils import class_from_module, create
from evennia.utils.test_resources import EvenniaTestCase

from commands import login_cmds
from commands.login_cmds import CmdForget, CmdRemember, CmdUnconnectedResume
from server.conf.serversession import ServerSession as BlackoutServerSession
from systems.core.login_tokens import constants as tok_const
from systems.core.login_tokens import store
from systems.interface.statefeed import constants as feed_const


# ─── Private constant definitions ────────────────────────────────────────────

_NAME = "Rook"
_ADDRESS = "203.0.113.7"


# ─── Private helper routines ─────────────────────────────────────────────────

class _FakeSession:
    """A stand-in Session that records what went back to the client."""

    def __init__(self):
        self.ndb = SimpleNamespace()
        self.address = _ADDRESS
        self.sessionhandler = mock.Mock()
        self.sent = []

    def msg(self, text=None, **kwargs):
        self.sent.append((text, kwargs))

    def texts(self) -> list:
        return [text for text, _kwargs in self.sent if text]

    def tokens(self) -> list:
        """Every payload sent on the login token channel, in order."""
        channel = feed_const.CHANNEL_LOGIN_TOKEN

        return [kwargs[channel] for _text, kwargs in self.sent if channel in kwargs]


def _run(cmd, caller, session, account=None, args=""):
    """Run one command by hand, and return the lines it sent to the caller."""
    lines = []
    cmd.caller = caller
    cmd.session = session
    cmd.account = account
    cmd.args = args
    cmd.msg = lambda text=None, **_kwargs: lines.append(text)
    cmd.func()

    return lines


# ─── Test cases ──────────────────────────────────────────────────────────────

class TestResume(EvenniaTestCase):
    """The login of a saved login, from the connection screen."""

    def setUp(self):
        super().setUp()
        self.account = create.create_account(_NAME, None, "hunter2-long")
        self.session = _FakeSession()
        self.token, self.digest = store.issue(self.account)

        throttle = mock.patch.object(login_cmds, "LOGIN_THROTTLE")
        self.throttle = throttle.start()
        self.throttle.check.return_value = False
        self.addCleanup(throttle.stop)

    def tearDown(self):
        self.account.delete()
        super().tearDown()

    def _resume(self, args: str) -> None:
        _run(CmdUnconnectedResume(), self.session, self.session, args=args)

    def test_a_good_token_logs_the_session_in(self):
        self._resume(f"{_NAME} {self.token}")

        self.session.sessionhandler.login.assert_called_once_with(
            self.session, self.account)

    def test_the_session_remembers_which_token_it_used(self):
        # `forget` reads it to know which device to forget.
        self._resume(f"{_NAME} {self.token}")

        held = getattr(self.session.ndb, tok_const.SESSION_DIGEST_ATTR)
        self.assertEqual(held, self.digest)

    def test_the_name_is_not_case_sensitive(self):
        self._resume(f"{_NAME.lower()} {self.token}")

        self.assertTrue(self.session.sessionhandler.login.called)

    def test_a_quoted_name_may_hold_spaces(self):
        spaced = create.create_account("Two Words", None, "hunter2-long")
        self.addCleanup(spaced.delete)
        token, _digest = store.issue(spaced)

        self._resume(f'"Two Words" {token}')

        self.session.sessionhandler.login.assert_called_once_with(
            self.session, spaced)

    def test_a_bad_token_is_refused_and_the_client_forgets_it(self):
        self._resume(f"{_NAME} not-the-token")

        self.assertFalse(self.session.sessionhandler.login.called)
        self.assertEqual(self.session.tokens()[-1][feed_const.LOGIN_TOKEN_KEY], "")
        self.assertTrue(self.throttle.update.called)

    def test_an_unknown_name_is_refused_the_same_way(self):
        # The same answer as a bad token, so a probe learns nothing about
        # which names exist.
        self._resume(f"Nobody {self.token}")

        self.assertFalse(self.session.sessionhandler.login.called)
        self.assertIn("no longer good", self.session.texts()[-1])

    def test_a_throttled_address_is_not_checked_at_all(self):
        self.throttle.check.return_value = True

        with mock.patch.object(store, "verify") as verify:
            self._resume(f"{_NAME} {self.token}")

        verify.assert_not_called()
        self.assertFalse(self.session.sessionhandler.login.called)

    def test_a_banned_name_cannot_use_a_good_token(self):
        account_class = class_from_module(settings.BASE_ACCOUNT_TYPECLASS)

        with mock.patch.object(account_class, "is_banned", return_value=True):
            self._resume(f"{_NAME} {self.token}")

        self.assertFalse(self.session.sessionhandler.login.called)
        self.assertIn("banned", self.session.texts()[-1])

    def test_one_word_gets_the_usage(self):
        self._resume(_NAME)

        self.assertFalse(self.session.sessionhandler.login.called)
        self.assertIn("usage", self.session.texts()[-1].lower())


class TestRememberAndForget(EvenniaTestCase):
    """The account commands that give out and drop a token."""

    def setUp(self):
        super().setUp()
        self.account = create.create_account(_NAME, None, "hunter2-long")
        self.session = _FakeSession()

    def tearDown(self):
        self.account.delete()
        super().tearDown()

    def _command(self, cmd, args: str = "") -> list:
        return _run(cmd, self.account, self.session, self.account, args)

    def _remember(self) -> str:
        """Run `remember`, and return the token that went to the client."""
        self._command(CmdRemember())

        return self.session.tokens()[-1][feed_const.LOGIN_TOKEN_KEY]

    def test_remember_sends_a_token_that_logs_in(self):
        token = self._remember()

        self.assertNotEqual(store.verify(self.account, token), "")

    def test_the_token_names_its_account(self):
        self._remember()

        payload = self.session.tokens()[-1]
        self.assertEqual(payload[feed_const.LOGIN_ACCOUNT_KEY], _NAME)

    def test_the_token_never_goes_out_as_text(self):
        # Text reaches the game log, and a screenshot of the log would carry
        # a key to the account.
        lines = self._command(CmdRemember())
        token = self.session.tokens()[-1][feed_const.LOGIN_TOKEN_KEY]

        for line in lines + self.session.texts():
            with self.subTest(line=line):
                self.assertNotIn(token, line)

    def test_a_second_remember_replaces_the_first_token(self):
        first = self._remember()
        second = self._remember()

        self.assertEqual(store.verify(self.account, first), "")
        self.assertNotEqual(store.verify(self.account, second), "")

    def test_forget_drops_this_device_and_clears_the_client(self):
        token = self._remember()

        self._command(CmdForget())

        self.assertEqual(store.verify(self.account, token), "")
        self.assertEqual(self.session.tokens()[-1][feed_const.LOGIN_TOKEN_KEY], "")

    def test_forget_leaves_the_other_devices(self):
        other, _digest = store.issue(self.account)
        self._remember()

        self._command(CmdForget())

        self.assertNotEqual(store.verify(self.account, other), "")

    def test_forget_all_drops_every_device(self):
        other, _digest = store.issue(self.account)
        token = self._remember()

        lines = self._command(CmdForget(), "all")

        self.assertEqual(store.verify(self.account, other), "")
        self.assertEqual(store.verify(self.account, token), "")
        self.assertIn("2", lines[-1])

    def test_forget_with_no_saved_login_says_so_and_still_clears(self):
        # After a reload the session forgets its digest. The client copy must
        # still go, or `forget` would leave a device that logs in.
        lines = self._command(CmdForget())

        self.assertIn("forget all", lines[-1])
        self.assertEqual(self.session.tokens()[-1][feed_const.LOGIN_TOKEN_KEY], "")

    def test_forget_with_a_stray_argument_changes_nothing(self):
        token = self._remember()

        lines = self._command(CmdForget(), "everything")

        self.assertIn("usage", lines[-1].lower())
        self.assertNotEqual(store.verify(self.account, token), "")


class TestLoginEcho(EvenniaTestCase):
    """The portal echo stays off until login.

    Before login, every typed line is a login line, with a password or a
    token in it. The echo would print that secret into the game log.
    """

    def _session(self, logged_in: bool) -> BlackoutServerSession:
        session = BlackoutServerSession()
        session.protocol_flags = {}
        session.logged_in = logged_in

        return session

    def _sync(self, session) -> None:
        with mock.patch("server.conf.serversession.BaseServerSession.at_sync"):
            with mock.patch("server.conf.serversession.resync"):
                with mock.patch("server.conf.serversession.subscriptions"):
                    session.at_sync()

    def test_an_unlogged_session_gets_no_echo(self):
        session = self._session(logged_in=False)

        self._sync(session)

        self.assertFalse(session.protocol_flags["LOCALECHO"])

    def test_a_reload_keeps_the_echo_of_a_logged_in_session(self):
        session = self._session(logged_in=True)

        self._sync(session)

        self.assertTrue(session.protocol_flags["LOCALECHO"])

    def test_the_echo_starts_at_login(self):
        session = self._session(logged_in=False)

        with mock.patch("server.conf.serversession.BaseServerSession.at_login"):
            session.at_login(mock.Mock())

        self.assertTrue(session.protocol_flags["LOCALECHO"])
