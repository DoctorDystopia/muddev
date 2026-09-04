"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/03/2026
Description: A stand-in for a connected Godot client, for scenarios that need
             the statefeed to actually SEND something.

Why this module exists at all
-----------------------------
emit() short-circuits on an observer with no subscribed sessions, and it does
so on purpose -- a telnet player who will never render a mesh must pay nothing.
The consequence for profiling is that a fixture built out of bare Characters
measures the statefeed's *early return* and reports a fan-out cost of zero, no
matter how many observers are standing in the room. Every crowd scenario in
this package would have been measuring nothing.

So the fixture needs something on the far side of obj.sessions that is
subscribed, that survives the rate cap, and that pays the same per-message cost
a real session pays.

Where the measurement stops, and why THERE
------------------------------------------
A real ServerSession's data_out ends in
`amp_protocol.send_MsgServer2Portal(session, **kwargs)`, which is

    callRemote(command, packed_data=pickle.dumps((sessid, kwargs)))

across a socket to the Portal process. This module reproduces everything up to
and including that pickle, and stops before the socket.

That boundary is not a shortcut, it is the same one
scenarios/protocol.py already draws and defends: a socket write's cost belongs
to the network, and a test database on a local disk cannot make an honest claim
about it. What the harness CAN measure is every cost the server controls, and
on the per-session path there are exactly two of those:

  1. `clean_senddata`, which recursively walks the whole payload -- every dict,
     every list, every leaf -- coercing it to AMP-safe values. PER SESSION.
  2. `pickle.dumps` at HIGHEST_PROTOCOL over the result. PER SESSION.

Both are proportional to the SIZE of the payload and both are paid once per
recipient, which is precisely the multiplication a crowd scenario exists to
measure. Stubbing them out would have left the fan-out looking like a cheap
loop over a session list.

Why not a real ServerSession
----------------------------
A real one wants a Portal connection, a sessionhandler registration and an AMP
protocol object, and gets torn down by machinery this harness does not run. The
part of it that matters to a payload -- ndb, sessid, protocol_flags, data_out
-- is four attributes, and writing those four is more honest than half-building
the real class and hoping the half that is missing was not on the hot path.
"""

import pickle
from types import SimpleNamespace

from systems.statefeed import constants as feed_const
from systems.statefeed import subscriptions


# ─── Private constant definitions ────────────────────────────────────────────

# Matches evennia.server.portal.amp.dumps, which is what the real send path
# uses. Named rather than inlined because the whole point of this module is
# that the number it produces is the number the server pays.
_PICKLE_PROTOCOL = pickle.HIGHEST_PROTOCOL

# The encoding flag clean_senddata reads when it meets a bytes value. Real
# sessions carry a full protocol_flags dict; a payload of JSON-safe primitives
# only ever reaches this one key.
_DEFAULT_ENCODING = "utf-8"


# ─── Private helper routines ─────────────────────────────────────────────────

def _session_handler():
    """
    Purpose: Hand back the ServerSessionHandler whose clean_senddata to use.

    Entry:
        No conditions. Safe to call before evennia._init() has run.

    Exit/Returns:
        Returns a ServerSessionHandler instance.

    Module Globals:
        None.

    Methodology:
        Prefers the process-wide handler that `evennia._init()` installs,
        because that is the object the live server actually calls and using a
        second one would risk measuring a differently-configured code path.

        Falls back to constructing one only when that global is still None,
        which happens if this module is imported outside a test run. The
        fallback is never registered anywhere, so it cannot receive a session
        or interfere with the real handler.

    Notes/References:
        evennia/__init__.py:288 is where the global is bound.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    from evennia.server import sessionhandler

    handler = getattr(sessionhandler, "SESSION_HANDLER", None)

    if handler is not None:
        return handler

    return sessionhandler.ServerSessionHandler()


# ─── Public routines / Classes ───────────────────────────────────────────────

class ProfilingSession:
    """One stand-in for a subscribed Godot client.

    Carries the four attributes a payload's journey actually touches: `ndb`
    (where subscriptions and the rate-cap clock live), `sessid` (which goes
    into the pickled tuple), `protocol_flags` (read by clean_senddata's utf-8
    helper) and `data_out`.
    """

    def __init__(self, sessid: int):
        self.sessid = sessid
        self.ndb = SimpleNamespace()
        self.protocol_flags = {"ENCODING": _DEFAULT_ENCODING}
        self.sends = 0
        self.bytes_sent = 0
        self._handler = _session_handler()


    def data_out(self, **kwargs) -> None:
        """
        Purpose: Pay what a real session pays to put one payload on the wire,
                 and stop at the wire.

        Entry:
            kwargs - the outputfunc mapping obj.msg() assembled, already
                     carrying the `options` key clean_senddata expects to pop.

        Exit/Returns:
            Returns nothing. Records the send count and the pickled size so a
            scenario's setup can report how many bytes a crowd is being sent
            without the measured pass having to compute it.

        Module Globals:
            _PICKLE_PROTOCOL read.

        Methodology:
            The two real per-session costs, in the real order. See the module
            header for why these two and not others, and why the socket is
            where this stops.

            The length is taken rather than the bytes retained. Holding one
            pickled payload per send across a 24-observer scenario at 200
            repeats is tens of megabytes of garbage, which would perturb the
            timing it is embedded in -- the same reason instruments.py gives
            for putting the query capture in its own pass.

        Notes/References:
            evennia/server/sessionhandler.py:824 and
            evennia/server/amp_client.py:141 are the two lines reproduced here.

        Author: Nick Hobar
        Creation date: 09/03/2026
        """
        cleaned = self._handler.clean_senddata(self, kwargs)
        packed = pickle.dumps((self.sessid, cleaned), _PICKLE_PROTOCOL)

        self.sends += 1
        self.bytes_sent += len(packed)


class ProfilingSessionHandler:
    """The `obj.sessions` stand-in, offering the one method emit() calls.

    DefaultObject.sessions is a lazy_property, and CLAUDE.md records that a
    lazy_property caches into obj.__dict__ under its own __name__ -- so an
    instance of this class written to `character.__dict__["sessions"]` replaces
    the real handler for that one object with no patching and nothing to undo.
    """

    def __init__(self, sessions):
        self._sessions = list(sessions)


    def all(self) -> list:
        """Return the attached sessions, as ObjectSessionHandler.all() does."""
        return self._sessions


def attach_client(character, sessid: int, channels=None) -> ProfilingSession:
    """
    Purpose: Give a character one subscribed client, as though a Godot player
             had just connected and completed its handshake.

    Entry:
        character - a live Character.
        sessid    - a session id unique within the run.
        channels  - channel names to subscribe, or None for every subscribable
                    channel.

    Exit/Returns:
        Returns the attached ProfilingSession, so a caller can read its
        counters afterwards.

    Module Globals:
        None.

    Methodology:
        Subscribes through subscriptions.subscribe rather than by writing the
        ndb attribute directly, so the fixture cannot subscribe a session to a
        channel the real subscribe path would have rejected -- which is exactly
        the mistake that would make a scenario measure a fan-out the live game
        never performs.

        The handler is written into __dict__ rather than assigned, because
        `sessions` is a lazy_property and a plain assignment would go through
        its (raising) setter. It is written FIRST, so that nothing can build
        the real ObjectSessionHandler in the window before the stub is in
        place.

        `db_sessid` is then set to match. That column is what a real puppeted
        character carries, and emit.py's _could_listen reads it as its cheap
        "could this object possibly have a session" pre-filter -- so a stub
        that left it empty would be skipped by every room broadcast and every
        crowd scenario would measure a fan-out of zero while looking like it
        worked. The stub has to be faithful in exactly the fields the code
        under measurement reads.

    Notes/References:
        Evennia.gd's handshake subscribes with the SUBSCRIBE_ALL sentinel,
        which is why that is the default here.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    session = ProfilingSession(sessid)
    wanted = channels if channels is not None else feed_const.SUBSCRIBE_ALL

    subscriptions.subscribe(session, wanted)
    character.__dict__["sessions"] = ProfilingSessionHandler([session])
    character.db_sessid = str(sessid)
    character.save(update_fields=["db_sessid"])

    return session
