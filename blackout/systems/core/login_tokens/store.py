"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/05/2026
Description: The login token store. It gives out, checks, and drops the login
             tokens of one account.

The store is the one owner of the token records on an Account. The commands
in commands/login_cmds.py call it, and nothing else reads the Attribute.

A token is a random secret. The server keeps only its SHA-256 digest. A token
is 32 random bytes, so a fast hash is correct here: nobody can guess the
input, and a slow password hash would only cost time at each login.

Each record carries a stamp of the password hash. A new password thus ends
every token of the account, on every path that sets a password, with no hook
on the Account typeclass.
"""

import hashlib
import hmac
import secrets
import time

from systems.core.login_tokens import constants as tok_const


# ─── Private constant definitions ────────────────────────────────────────────

_TEXT_ENCODING = "utf-8"


# ─── Private helper routines ─────────────────────────────────────────────────

def _sha256(text: str) -> str:
    """Return the SHA-256 hex digest of a text."""
    encoded = text.encode(_TEXT_ENCODING)

    return hashlib.sha256(encoded).hexdigest()


def _password_stamp(account) -> str:
    """Return the stamp of the current password hash of an account."""
    password_hash = account.password or ""
    stamp = _sha256(password_hash)

    return stamp


def _clock(now) -> float:
    """Return `now`, or the wall clock when the caller gave no time."""
    if now is None:
        return time.time()

    return now


def _is_live(record: dict, stamp: str, now: float) -> bool:
    """Say whether a record is in date and belongs to the current password."""
    expires = record.get(tok_const.RECORD_EXPIRES, 0)
    same_password = record.get(tok_const.RECORD_STAMP) == stamp

    return expires > now and same_password


def _save(account, records: list) -> None:
    """Write the records back, or remove the Attribute when none is left."""
    if records:
        account.attributes.add(tok_const.TOKENS_ATTR, records)
        return

    account.attributes.remove(tok_const.TOKENS_ATTR)


def _live_records(account, now: float) -> list:
    """
    Purpose: Read the records of an account, and drop each dead record.

    Entry:
        account - an Account.
        now     - the time, in seconds since the epoch.

    Exit/Returns:
        Returns a list of plain dicts, one for each live record.
        Writes the Attribute only if a record was dead.

    Module Globals:
        None.

    Methodology:
        1. Copy each stored record to a plain dict.
        2. Keep a record only if it is in date and has the current stamp.
        3. If a record went, write the remaining records back.

    Notes/References:
        A copy, because Evennia gives back a saver list. A change to it
        writes to the database at once, before the caller decides anything.

    Author: Nick Hobar
    Creation date: 10/05/2026
    """
    stored = account.attributes.get(tok_const.TOKENS_ATTR, default=None) or []
    stamp = _password_stamp(account)
    live = []

    for record in stored:
        copied = dict(record)
        alive = _is_live(copied, stamp, now)

        if alive:
            live.append(copied)

    if len(live) != len(stored):
        _save(account, live)

    return live


def _find(records: list, digest: str):
    """Return the record with this digest, or None."""
    for record in records:
        stored_digest = record.get(tok_const.RECORD_DIGEST, "")
        matched = hmac.compare_digest(stored_digest, digest)

        if matched:
            return record

    return None


def _last_used(record: dict) -> float:
    """Sort key: the time of the last use of a record."""
    return record.get(tok_const.RECORD_LAST_USED, 0)


# ─── Public routines ─────────────────────────────────────────────────────────

def digest_of(token: str) -> str:
    """Return the digest that the store keeps for a token."""
    digest = _sha256(token)

    return digest


def issue(account, now=None) -> tuple:
    """
    Purpose: Give out a new login token for one device of an account.

    Entry:
        account - an Account with a primary key.
        now     - the time in seconds since the epoch, or None for the
                  wall clock.

    Exit/Returns:
        Returns (token, digest). The token goes to the client. The digest
        is the one value that the server keeps.

    Module Globals:
        tok_const.TOKEN_BYTES, TOKEN_LIFETIME_SECONDS and
        MAX_TOKENS_PER_ACCOUNT read.

    Methodology:
        1. Read the live records, and drop the dead ones.
        2. Add a record for the new token.
        3. If the account has too many records, drop the least recently used.
        4. Write the records.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/05/2026
    """
    moment = _clock(now)
    records = _live_records(account, moment)
    token = secrets.token_urlsafe(tok_const.TOKEN_BYTES)
    digest = _sha256(token)
    stamp = _password_stamp(account)

    records.append({
        tok_const.RECORD_DIGEST: digest,
        tok_const.RECORD_STAMP: stamp,
        tok_const.RECORD_EXPIRES: moment + tok_const.TOKEN_LIFETIME_SECONDS,
        tok_const.RECORD_LAST_USED: moment,
    })
    records.sort(key=_last_used)
    kept = records[-tok_const.MAX_TOKENS_PER_ACCOUNT:]
    _save(account, kept)

    return token, digest


def verify(account, token: str, now=None) -> str:
    """
    Purpose: Check a login token, and extend its life if it is good.

    Entry:
        account - an Account.
        token   - the token that the client sent.
        now     - the time in seconds since the epoch, or None for the
                  wall clock.

    Exit/Returns:
        Returns the digest of the token if it is good, else "".
        A good token gets a new end of life and a new last use.

    Module Globals:
        tok_const.TOKEN_LIFETIME_SECONDS read.

    Methodology:
        None.

    Notes/References:
        A failed check writes nothing, unless it also drops a dead record.
        Thus, a stream of bad tokens cannot make a stream of writes.

    Author: Nick Hobar
    Creation date: 10/05/2026
    """
    moment = _clock(now)
    records = _live_records(account, moment)
    digest = _sha256(token)
    record = _find(records, digest)

    if record is None:
        return ""

    record[tok_const.RECORD_EXPIRES] = moment + tok_const.TOKEN_LIFETIME_SECONDS
    record[tok_const.RECORD_LAST_USED] = moment
    _save(account, records)

    return digest


def revoke(account, digest: str, now=None) -> bool:
    """
    Purpose: Drop the token of one device.

    Entry:
        account - an Account.
        digest  - the digest of the token, from issue or verify.
        now     - the time in seconds since the epoch, or None for the
                  wall clock.

    Exit/Returns:
        Returns True if a live token had this digest, else False.

    Module Globals:
        None.

    Methodology:
        None.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/05/2026
    """
    moment = _clock(now)
    records = _live_records(account, moment)
    record = _find(records, digest)

    if record is None:
        return False

    records.remove(record)
    _save(account, records)

    return True


def revoke_all(account, now=None) -> int:
    """
    Purpose: Drop the token of every device of an account.

    Entry:
        account - an Account.
        now     - the time in seconds since the epoch, or None for the
                  wall clock.

    Exit/Returns:
        Returns the count of live tokens that it dropped.

    Module Globals:
        None.

    Methodology:
        None.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/05/2026
    """
    moment = _clock(now)
    records = _live_records(account, moment)
    _save(account, [])

    return len(records)


def live_count(account, now=None) -> int:
    """Return the count of live tokens of an account."""
    moment = _clock(now)
    records = _live_records(account, moment)

    return len(records)
