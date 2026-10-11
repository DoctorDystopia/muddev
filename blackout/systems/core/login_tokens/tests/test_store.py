"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/05/2026
Description: Tests for the login token store: a token logs in, a bad one
             does not, the life of a token, the cap, and the two ways a
             token ends early.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py systems.core.login_tokens
"""

from unittest import mock

from evennia.utils import create
from evennia.utils.test_resources import EvenniaTestCase

from systems.core.login_tokens import constants as tok_const
from systems.core.login_tokens import store


# ─── Private constant definitions ────────────────────────────────────────────

_START = 1_000_000.0
_LIFETIME = tok_const.TOKEN_LIFETIME_SECONDS


# ─── Test cases ──────────────────────────────────────────────────────────────

class TestLoginTokenStore(EvenniaTestCase):
    """One account, one or more devices."""

    def setUp(self):
        super().setUp()
        self.account = create.create_account("Rook", None, "hunter2-long")

    def tearDown(self):
        self.account.delete()
        super().tearDown()

    def test_an_issued_token_verifies(self):
        token, digest = store.issue(self.account, now=_START)

        self.assertEqual(store.verify(self.account, token, now=_START), digest)

    def test_a_wrong_token_does_not_verify(self):
        store.issue(self.account, now=_START)

        self.assertEqual(store.verify(self.account, "not-the-token", now=_START), "")

    def test_the_token_itself_is_never_stored(self):
        # A copy of the database must not be able to log anyone in.
        token, _digest = store.issue(self.account, now=_START)
        stored = self.account.attributes.get(tok_const.TOKENS_ATTR)

        self.assertNotIn(token, repr(stored))

    def test_a_token_ends_after_its_lifetime(self):
        token, _digest = store.issue(self.account, now=_START)
        too_late = _START + _LIFETIME + 1

        self.assertEqual(store.verify(self.account, token, now=too_late), "")

    def test_each_use_moves_the_end_of_life_forward(self):
        token, digest = store.issue(self.account, now=_START)
        first_use = _START + _LIFETIME - 1
        second_use = first_use + _LIFETIME - 1

        self.assertEqual(store.verify(self.account, token, now=first_use), digest)
        self.assertEqual(store.verify(self.account, token, now=second_use), digest)

    def test_a_new_password_ends_every_token(self):
        # The stamp covers every path that sets a password, with no hook on
        # the Account typeclass.
        first, _ = store.issue(self.account, now=_START)
        second, _ = store.issue(self.account, now=_START)

        self.account.set_password("a-new-password")
        self.account.save()

        self.assertEqual(store.verify(self.account, first, now=_START), "")
        self.assertEqual(store.verify(self.account, second, now=_START), "")

    def test_revoke_drops_one_device_and_keeps_the_other(self):
        first, first_digest = store.issue(self.account, now=_START)
        second, second_digest = store.issue(self.account, now=_START)

        self.assertTrue(store.revoke(self.account, first_digest, now=_START))
        self.assertEqual(store.verify(self.account, first, now=_START), "")
        self.assertEqual(store.verify(self.account, second, now=_START),
                         second_digest)

    def test_revoke_of_an_unknown_digest_says_so(self):
        self.assertFalse(store.revoke(self.account, "0" * 64, now=_START))

    def test_revoke_all_drops_every_device_and_counts_them(self):
        tokens = []

        for _ in range(3):
            token, _digest = store.issue(self.account, now=_START)
            tokens.append(token)

        self.assertEqual(store.revoke_all(self.account, now=_START), 3)

        for token in tokens:
            with self.subTest(token=token):
                self.assertEqual(store.verify(self.account, token, now=_START), "")

    def test_the_cap_drops_the_least_recently_used_token(self):
        cap = tok_const.MAX_TOKENS_PER_ACCOUNT
        tokens = []

        for i in range(cap + 1):
            token, _digest = store.issue(self.account, now=_START + i)
            tokens.append(token)

        now = _START + cap + 1

        self.assertEqual(store.live_count(self.account, now=now), cap)
        self.assertEqual(store.verify(self.account, tokens[0], now=now), "")
        self.assertNotEqual(store.verify(self.account, tokens[-1], now=now), "")

    def test_a_used_token_outlives_the_cap(self):
        # The cap counts the LAST USE, not the issue. The device that the
        # player uses every day must not lose its login to new devices.
        cap = tok_const.MAX_TOKENS_PER_ACCOUNT
        oldest, _ = store.issue(self.account, now=_START)

        for i in range(1, cap):
            store.issue(self.account, now=_START + i)

        store.verify(self.account, oldest, now=_START + cap)
        store.issue(self.account, now=_START + cap + 1)

        self.assertNotEqual(
            store.verify(self.account, oldest, now=_START + cap + 2), "")

    def test_a_failed_check_writes_nothing(self):
        # A stream of bad tokens must not make a stream of database writes.
        store.issue(self.account, now=_START)

        with mock.patch.object(store, "_save") as saved:
            store.verify(self.account, "not-the-token", now=_START)

        saved.assert_not_called()

    def test_the_last_revoke_removes_the_attribute(self):
        _token, digest = store.issue(self.account, now=_START)
        store.revoke(self.account, digest, now=_START)

        self.assertFalse(self.account.attributes.has(tok_const.TOKENS_ATTR))
