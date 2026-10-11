"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/05/2026
Description: The commands of a saved login: `resume`, `remember` and
             `forget`.

             `remember` gives this connection a login token on
             CHANNEL_LOGIN_TOKEN. The Godot client keeps the token. At its
             next start, it sends `resume <name> <token>` from the connection
             screen, and the player is in with no password typed. The
             password never stays on the device.

             The token store (systems/core/login_tokens/store.py) owns the
             records. These commands only call it, and they send the token
             to the one session that asked.

             `resume` follows Evennia's `connect` in each check that is not
             about the password: the login throttle, the ban list, and the
             security log. A token is thus no way around a ban or the
             throttle.
"""

import re

from django.conf import settings
from evennia.accounts.accounts import LOGIN_THROTTLE, DefaultGuest
from evennia.accounts.models import AccountDB
from evennia.commands.command import Command
from evennia.utils import class_from_module, logger

from systems.core.login_tokens import constants as tok_const
from systems.core.login_tokens import store
from systems.interface.statefeed import constants as feed_const


# ─── Private constant definitions ────────────────────────────────────────────

_RESUME_KEY = "resume"
_FORGET_ALL_ARG = "all"
_QUOTE_SPLIT = r"\""

_MSG_RESUME_USAGE = "Usage: resume <name> <token>"
_MSG_THROTTLED = "|rToo many failed logins. Try again in a few minutes.|n"
_MSG_BANNED = ("|rYou have been banned and cannot continue from here."
               "\nIf you feel this ban is in error, please email an admin.|n")
_MSG_REFUSED = ("|rThat saved login is no longer good. "
                "Log in with your password.|n")
_MSG_REMEMBERED = ("This device will log you in by itself. The login lasts "
                   "{days} days from its last use. Type |wforget|n to stop it.")
_MSG_GUEST = "A guest account cannot be remembered."
_MSG_FORGOT = "This device will no longer log you in by itself."
_MSG_FORGOT_NONE = ("This connection did not use a saved login. Type "
                    "|wforget all|n to forget every device.")
_MSG_FORGOT_ALL = ("Forgot the saved login of {count} device(s). Each one "
                   "needs your password again.")
_MSG_FORGET_USAGE = "Usage: forget  or  forget all"

_THROTTLE_REASON_BANNED = "Too many sightings of banned artifact."
_THROTTLE_REASON_TOKEN = "Too many failed token logins."


# ─── Private helper routines ─────────────────────────────────────────────────

def _split_name_and_token(args: str):
    """
    Purpose: Split the arguments of `resume` into a name and a token.

    Entry:
        args - the text after the command word.

    Exit/Returns:
        Returns (name, token), or None if the text does not hold both.

    Module Globals:
        _QUOTE_SPLIT read.

    Methodology:
        The rule of Evennia's `connect`: a name in double quotes may hold
        spaces. Else the first word is the name, and the rest is the token.

    Notes/References:
        evennia/commands/default/unloggedin.py, CmdUnconnectedConnect.func.

    Author: Nick Hobar
    Creation date: 10/05/2026
    """
    parts = []

    for part in re.split(_QUOTE_SPLIT, args):
        stripped = part.strip()

        if stripped:
            parts.append(stripped)

    if len(parts) == 1:
        parts = parts[0].split(None, 1)

    if len(parts) != 2:
        return None

    return parts[0], parts[1]


def _send_token(session, account_name: str, token: str) -> None:
    """Send a token to one session. An empty token says to forget it."""
    payload = {
        feed_const.LOGIN_ACCOUNT_KEY: account_name,
        feed_const.LOGIN_TOKEN_KEY: token,
    }

    session.msg(**{feed_const.CHANNEL_LOGIN_TOKEN: payload})


def _session_digest(session) -> str:
    """Return the digest of the token of this session, or ""."""
    digest = getattr(session.ndb, tok_const.SESSION_DIGEST_ATTR, None)

    return digest or ""


def _set_session_digest(session, digest: str) -> None:
    """Record which token this session holds. "" records none."""
    setattr(session.ndb, tok_const.SESSION_DIGEST_ATTR, digest or None)


def _refuse(session, name: str, ip: str) -> None:
    """Refuse a token login: log it, count it, and clear the client copy."""
    logger.log_sec(f"Authentication Failure (token): {name} (IP: {ip}).")

    if ip:
        LOGIN_THROTTLE.update(ip, _THROTTLE_REASON_TOKEN)

    session.msg(_MSG_REFUSED)
    _send_token(session, name, "")


def _gate(session, name: str, ip: str) -> bool:
    """
    Purpose: Apply the checks of `connect` that come before the password.

    Entry:
        session - the unlogged ServerSession.
        name    - the account name that the client sent.
        ip      - the address of the session, as text.

    Exit/Returns:
        Returns True if the login may go on. Else it tells the session why,
        and returns False.

    Module Globals:
        LOGIN_THROTTLE read and written.

    Methodology:
        1. If the address failed too often, refuse.
        2. If the name or the address is banned, refuse and count it.

    Notes/References:
        DefaultAccount.authenticate does the same two checks, in this order.

    Author: Nick Hobar
    Creation date: 10/05/2026
    """
    throttled = bool(ip) and LOGIN_THROTTLE.check(ip)

    if throttled:
        session.msg(_MSG_THROTTLED)
        return False

    account_class = class_from_module(settings.BASE_ACCOUNT_TYPECLASS)
    banned = account_class.is_banned(username=name, ip=ip)

    if banned:
        logger.log_sec(f"Authentication Denied (Banned): {name} (IP: {ip}).")
        LOGIN_THROTTLE.update(ip, _THROTTLE_REASON_BANNED)
        session.msg(_MSG_BANNED)
        return False

    return True


# ─── Public classes ──────────────────────────────────────────────────────────

class CmdUnconnectedResume(Command):
    """
    log in with a saved login

    Usage (at login screen):
      resume <name> <token>
      resume "account name" <token>

    The Godot client sends this by itself when it holds a saved login. A
    player gets a saved login with the remember command, after a normal
    connect.
    """

    key = _RESUME_KEY
    locks = "cmd:all()"
    arg_regex = r"\s.*?|$"

    def func(self):
        """Check the token, and log the session in to its account."""
        session = self.caller
        ip = str(session.address)
        parsed = _split_name_and_token(self.args)

        if parsed is None:
            session.msg(_MSG_RESUME_USAGE)
            return

        name, token = parsed
        allowed = _gate(session, name, ip)

        if not allowed:
            return

        account = AccountDB.objects.get_account_from_name(name)
        digest = ""

        if account is not None:
            digest = store.verify(account, token)

        if not digest:
            _refuse(session, name, ip)
            return

        _set_session_digest(session, digest)
        logger.log_sec(f"Authentication Success (token): {account} (IP: {ip}).")
        session.sessionhandler.login(session, account)


class CmdRemember(Command):
    """
    Keep this device logged in.

    Usage:
      remember

    The server gives this device a login token, and the Godot client logs
    you in with it at each start. Your password does not stay on the
    device. The token ends after a long absence, and a new password ends
    every token. Use forget to stop it.
    """

    key = feed_const.COMMAND_REMEMBER
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        """Give this session a new token, in place of any older one."""
        account = self.account
        session = self.session

        if account is None or session is None:
            return

        if isinstance(account, DefaultGuest):
            self.msg(_MSG_GUEST)
            return

        old_digest = _session_digest(session)

        if old_digest:
            store.revoke(account, old_digest)

        token, digest = store.issue(account)
        _set_session_digest(session, digest)
        _send_token(session, account.username, token)

        self.msg(_MSG_REMEMBERED.format(days=tok_const.TOKEN_LIFETIME_DAYS))


class CmdForget(Command):
    """
    Stop a device from logging in by itself.

    Usage:
      forget
      forget all

    forget stops this device. forget all stops every device, and each one
    then needs your password again.
    """

    key = feed_const.COMMAND_FORGET
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        """Drop one token or all of them, and clear the client copy."""
        account = self.account
        session = self.session

        if account is None or session is None:
            return

        choice = self.args.strip().lower()

        if choice == _FORGET_ALL_ARG:
            self._forget_all(account)
        elif not choice:
            self._forget_this_device(account, session)
        else:
            self.msg(_MSG_FORGET_USAGE)
            return

        _set_session_digest(session, "")
        _send_token(session, account.username, "")

    def _forget_all(self, account) -> None:
        """Drop every token of the account."""
        count = store.revoke_all(account)

        self.msg(_MSG_FORGOT_ALL.format(count=count))

    def _forget_this_device(self, account, session) -> None:
        """Drop the token that this session holds, if it holds one."""
        digest = _session_digest(session)

        if not digest:
            self.msg(_MSG_FORGOT_NONE)
            return

        store.revoke(account, digest)
        self.msg(_MSG_FORGOT)
