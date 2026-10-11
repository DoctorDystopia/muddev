"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/05/2026
Description: Tunables and record keys of the login token store (store.py).

A login token lets one device log in to one account with no password. The
server gives it out on `remember`, and the client keeps it. The server keeps
only a digest of it, so a copy of the database cannot log anyone in.

The wire names (the channel, its keys, and the command words) belong to the
statefeed, in systems/interface/statefeed/constants.py, because the client
reads them from the generated file.
"""

# ─── Lifetime ────────────────────────────────────────────────────────────────

# How long a login token stays good after its last use. Each login with the
# token moves the end of its life forward again, so a device in regular use
# never has to type the password. A device that stays away this long must.
TOKEN_LIFETIME_DAYS: int = 30

_SECONDS_PER_DAY: int = 24 * 60 * 60
TOKEN_LIFETIME_SECONDS: int = TOKEN_LIFETIME_DAYS * _SECONDS_PER_DAY

# The most devices one account can keep at one time. A new token past this
# count pushes out the token that was used least recently. The cap bounds the
# tokens that nobody holds any more, for example after a client forgets its
# copy with no connection to the server.
MAX_TOKENS_PER_ACCOUNT: int = 10

# Random bytes in one token. secrets.token_urlsafe gives 43 characters for 32
# bytes, from the URL-safe alphabet. Thus, a token has no space and no quote,
# and it travels as one word of a command.
TOKEN_BYTES: int = 32


# ─── Records ─────────────────────────────────────────────────────────────────

# The Attribute on the Account that holds its token records, as a list of
# dicts. Nothing outside store.py reads it.
TOKENS_ATTR: str = "login_tokens"

# The keys of one token record.
#
# DIGEST is the SHA-256 of the token. The token itself is never stored.
# STAMP is the SHA-256 of the password hash of the account when the token was
# given out. A new password changes the hash, and every older token then
# fails. This covers every path that sets a password: the `password` command,
# a staff reset, and the web admin.
RECORD_DIGEST: str = "digest"
RECORD_STAMP: str = "stamp"
RECORD_EXPIRES: str = "expires"
RECORD_LAST_USED: str = "last_used"

# The ndb attribute on a Session that holds the digest of the token that this
# session logged in with or got from `remember`. `forget` reads it to know
# which device to forget. ndb, because a token belongs to one connection.
SESSION_DIGEST_ATTR: str = "login_token_digest"
