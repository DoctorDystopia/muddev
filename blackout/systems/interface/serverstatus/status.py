"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: The status endpoint that the website reads.

             The website at playblackout.io shows a status light in its nav
             bar. Its Worker asks this endpoint, through the tunnel, and
             caches the answer for a short time. Thus, a page view never
             reaches this machine.

             The endpoint says only two facts: the server is up, and the
             number of players on it. An answer means "up". No answer, or
             an answer that is not this JSON, means "down". The Worker owns
             that rule, because a server that is down cannot say so.

             IT IS A TWISTED RESOURCE, NOT A DJANGO VIEW.
             `server/conf/web_plugins.py` mounts it beside Django on the
             web root of the Server. A Django view runs Evennia's
             `SharedLoginMiddleware`, and that middleware saves a new session
             row for every request with no cookie. The Worker sends no
             cookie. Thus, each probe would add one row to `django_session`.
             A Twisted child of the root runs no middleware, opens no
             session, and needs no thread from the Django pool.

             The resource runs in the Server process, not in the Portal.
             Thus, during an `evennia reload` the Portal proxy has no Server
             to ask, and the website shows "down" for those seconds. That is
             correct: nobody can log in then.

Module Globals:
    STATUS_PATH       -- the URL path, without a leading slash.
    FIELD_ONLINE      -- the key of the "up" flag in the JSON.
    FIELD_PLAYERS     -- the key of the player count in the JSON.
"""

import json

import evennia

from twisted.web import resource


# ─── Public constant definitions ─────────────────────────────────────────────

# The child name on the web root. The website names the same URL in
# GAME_STATUS_URL in playblackout-site/src/config.ts.
STATUS_PATH: str = "status.json"

FIELD_ONLINE: str = "online"
FIELD_PLAYERS: str = "players"


# ─── Private constant definitions ────────────────────────────────────────────

_CONTENT_TYPE: bytes = b"application/json"

# The Worker caches the answer. A cache between the two would make the
# Worker's age limit a lie, so the answer forbids every other cache.
_CACHE_CONTROL: bytes = b"no-store"


# ─── Public functions ────────────────────────────────────────────────────────

def status_payload(session_handler) -> dict:
    """
    Purpose: Build the status JSON for the website.

    Entry:
        session_handler -- an object with `account_count()`, normally
                           evennia.SESSION_HANDLER.

    Exit/Returns:
        {FIELD_ONLINE: True, FIELD_PLAYERS: <int>}.

    Notes:
        The count is of logged-in ACCOUNTS, not of sessions. A player with
        two clients open is one player. A connection at the login screen is
        no player. This is the count that Evennia's own front page shows.

    Author & Date: Nick Hobar, 10/06/2026
    """
    players = session_handler.account_count()

    return {FIELD_ONLINE: True, FIELD_PLAYERS: players}


class StatusResource(resource.Resource):
    """
    Purpose: Answer GET /status.json with the status_payload.

    Notes:
        `isLeaf` stops the lookup here, so `/status.json/x` gets this answer
        too, not Django. Twisted gives HEAD the GET answer with no body, and
        any other method a 405.

        It reads evennia.SESSION_HANDLER at call time, not at import time.
        The flat API is empty when the web plugins load. It runs in the
        reactor thread, the same thread that changes the session handler.

    Author & Date: Nick Hobar, 10/06/2026
    """

    isLeaf = True

    def render_GET(self, request) -> bytes:
        payload = status_payload(evennia.SESSION_HANDLER)
        body = json.dumps(payload).encode("utf-8")

        request.setHeader(b"Content-Type", _CONTENT_TYPE)
        request.setHeader(b"Cache-Control", _CACHE_CONTROL)

        return body


def mount(web_root):
    """
    Purpose: Put the status resource on the Server's web root.

    Entry:
        web_root -- the twisted.web Resource that the Server builds.
                    `at_webserver_root_creation` passes it.

    Exit/Returns:
        web_root, with STATUS_PATH as a child.

    Notes:
        A child added with `putChild` wins over Django: Twisted checks the
        children before `DjangoWebRoot.getChild` hands a path to Django.

    Author & Date: Nick Hobar, 10/06/2026
    """
    child_name = STATUS_PATH.encode("utf-8")
    web_root.putChild(child_name, StatusResource())

    return web_root
