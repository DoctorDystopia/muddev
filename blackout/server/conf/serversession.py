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