"""
ServerSession

The serversession is the Server-side in-memory representation of a
user connecting to the game.  Evennia manages one Session per
connection to the game. So a user logged into the game with multiple
clients (if Evennia is configured to allow that) will have multiple
sessions tied to one Account object. All communication between Evennia
and the real-world user goes through the Session(s) associated with that user.

It should be noted that modifying the Session object is not usually
necessary except for the most custom and exotic designs - and even
then it might be enough to just add custom session-level commands to
the SessionCmdSet instead.

This module is not normally called. To tell Evennia to use the class
in this module instead of the default one, add the following to your
settings file:

    SERVER_SESSION_CLASS = "server.conf.serversession.ServerSession"

"""


from evennia.server.serversession import ServerSession as BaseServerSession
from evennia import EVENNIA_SERVER_SERVICE

from systems.statefeed import resync, subscriptions


class ServerSession(BaseServerSession):
    def at_sync(self):
        """Called whenever the session is (re)synced with the Portal,
        both on first connect and after every server reload/restart."""
        super().at_sync()

        # Force server-side echoing for the Godot client. init_session()
        # only runs on the Portal side, so protocol_flags must be forced
        # here and pushed back down to the Portal's copy of the session,
        # which is what actually decides whether to echo typed input.
        self.protocol_flags["LOCALECHO"] = True

        # The test runner never connects the AMP protocol to a Portal, so
        # there is nothing to push back down to -- skip the sync there.
        if EVENNIA_SERVER_SERVICE is not None and EVENNIA_SERVER_SERVICE.amp_protocol is not None:
            self.sessionhandler.session_portal_partial_sync(
                {self.sessid: {"protocol_flags": {"LOCALECHO": True}}}
            )

        self._announce_statefeed()
        self._resync_statefeed()

    def _announce_statefeed(self):
        """Tell a graphical client what it is subscribed to, which after a
        sync is usually nothing.

        This is the ONLY moment the server can tell a client its subscription
        is gone, and it covers both ways that happens:

        - A reload wipes Session ndb, where subscriptions live. The client's
          socket never dropped, so nothing else would ever tell it that the
          world had stopped updating.
        - A client that connects while the Server is down or restarting talks
          to a Portal that accepts the socket immediately. Its subscribe is
          sent into a Server that cannot route an inputfunc yet and is dropped
          silently. at_sync is by definition the first instant that is no
          longer true.

        Both were observed against the Godot client on 08/11/2026. Subscribing
        on socket-open alone is a race the client loses often enough to matter.

        Guarded for the same reason _resync_statefeed is: at_sync runs on every
        session sync, including during startup, and must not be able to fail.
        """
        try:
            subscriptions.announce(self)
        except Exception:
            from evennia.utils import logger

            logger.log_trace()

    def _resync_statefeed(self):
        """Re-send the structured state feed's full snapshot after a reload.

        A reload wipes Session ndb, which is where the feed keeps both its
        subscription set and its rate-limit state. A graphical client would
        otherwise sit holding a world that stopped updating, with nothing to
        tell it so -- reconnecting is the only recovery, and the player has no
        reason to think they need to.

        This is a no-op in every case that matters for cost: a session with no
        subscriptions reaches send_full_state, finds nothing subscribed, and
        returns having sent zero messages. A session that has not puppeted
        anything yet passes None and returns immediately.

        send_full_state swallows and logs its own failures. The guard here is
        for the import and attribute access, not for the send: at_sync runs on
        every session sync including during startup, and must not be able to
        fail.
        """
        try:
            resync.send_full_state(self.puppet)
        except Exception:
            from evennia.utils import logger

            logger.log_trace()