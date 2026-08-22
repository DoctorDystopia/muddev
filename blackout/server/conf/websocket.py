"""
Purpose:  Websocket protocol that keeps proxied connections from going idle.

Description:
          Cloudflare closes a proxied websocket that has carried no traffic in
          either direction for ~100s (measured against game.playblackout.io:
          three silent sockets died at 125.6s, 126.0s and 126.9s, while a
          socket pinged every 45s survived). The close arrives as an abnormal
          1006 with no code or reason, so neither side can report a cause --
          the player simply sees the client drop and reconnect.

          Nothing in Evennia causes this. IDLE_TIMEOUT is -1 (disabled) and
          the stock websocket protocol sets only setTcpKeepAlive(1), which is
          an OS-level probe on the origin socket that the Cloudflare edge
          never sees. A control socket held directly against
          ws://127.0.0.1:4002 stayed open for the full 30-minute test.

          It is also not fixable from the tunnel side: originRequest
          keepAliveTimeout governs cloudflared's HTTP connection pool to the
          origin, not the edge's websocket idle timer. The measurements above
          were taken with keepAliveTimeout already raised to 1000s.

          The fix therefore has to be traffic. This protocol sends a websocket
          PING frame on a timer, which resets the edge's idle timer and which
          browsers answer with PONG automatically -- no client-side change,
          and it covers the Godot client and any future websocket client too.

Author: Nick Hobar
Creation date: 08/21/2026
"""

from autobahn.exception import Disconnected
from django.conf import settings
from twisted.internet.task import LoopingCall

from evennia.server.portal.webclient import WebSocketClient
from evennia.utils import logger


# Seconds between keepalive pings when WEBSOCKET_KEEPALIVE_INTERVAL is unset.
# Must stay well under the ~100s Cloudflare idle limit, with room for one
# missed tick under load. Set the setting to 0 to disable pinging entirely.
_DEFAULT_KEEPALIVE_INTERVAL = 45.0

# Value of WEBSOCKET_KEEPALIVE_INTERVAL that turns the keepalive off.
_KEEPALIVE_DISABLED = 0


class KeepAliveWebSocketClient(WebSocketClient):
    """
    Purpose: Stock Evennia websocket protocol plus a periodic PING frame.

    Notes/References:
        Installed via WEBSOCKET_PROTOCOL_CLASS in server/conf/settings.py.
        The Portal resolves that setting through class_from_module in
        evennia/server/portal/service.py, so a game-dir path works here the
        same way SERVER_SESSION_CLASS does.

    Author: Nick Hobar
    Creation date: 08/21/2026
    """

    # Class-level default so _stop_keepalive is safe even if onClose fires
    # without a matching onOpen -- a handshake that fails partway does that.
    _keepalive_task = None


    def onOpen(self) -> None:
        """
        Purpose: Begin the keepalive timer once the connection is established.

        Entry:
            No conditions. Called by autobahn after the websocket handshake.

        Exit/Returns:
            No return. self._keepalive_task holds a running LoopingCall
            unless the keepalive is disabled by setting.

        Author: Nick Hobar
        Creation date: 08/21/2026
        """
        super().onOpen()
        self._start_keepalive()


    def onClose(self, wasClean, code=None, reason=None) -> None:
        """
        Purpose: Stop the keepalive timer before the session tears down.

        Entry:
            Signature must match the stock protocol's; autobahn supplies all
            three arguments positionally.

        Exit/Returns:
            No return. self._keepalive_task is stopped and cleared.

        Notes/References:
            Stopping BEFORE the super() call matters: the parent disconnects
            the session, after which a firing tick would ping a dead
            transport and raise inside the LoopingCall.

        Author: Nick Hobar
        Creation date: 08/21/2026
        """
        self._stop_keepalive()
        super().onClose(wasClean, code, reason)


    def _start_keepalive(self) -> None:
        """
        Purpose: Start the LoopingCall that pings this connection.

        Entry:
            No conditions.

        Exit/Returns:
            No return, and never raises -- a failure here must not take down
            an otherwise healthy connection.

        Methodology:
            Read the interval from settings, falling back to the module
            default. A non-positive interval disables the keepalive, which is
            the escape hatch if this ever needs to be turned off without a
            code change. now=False so the first ping waits one full interval
            rather than firing during connection setup.

        Author: Nick Hobar
        Creation date: 08/21/2026
        """
        interval = getattr(
            settings, "WEBSOCKET_KEEPALIVE_INTERVAL", _DEFAULT_KEEPALIVE_INTERVAL
        )
        if interval <= _KEEPALIVE_DISABLED:
            return

        try:
            self._keepalive_task = LoopingCall(self._send_keepalive_ping)
            self._keepalive_task.start(interval, now=False)
        except Exception as exc:
            logger.log_err(f"websocket keepalive failed to start: {exc!r}")
            self._keepalive_task = None


    def _stop_keepalive(self) -> None:
        """
        Purpose: Cancel the keepalive timer if one is running.

        Entry:
            No conditions. Safe to call when no timer was ever started.

        Exit/Returns:
            No return, and never raises. self._keepalive_task is None after.

        Author: Nick Hobar
        Creation date: 08/21/2026
        """
        task = self._keepalive_task
        self._keepalive_task = None
        if task is None:
            return

        try:
            if task.running:
                task.stop()
        except Exception as exc:
            logger.log_err(f"websocket keepalive failed to stop: {exc!r}")


    def _send_keepalive_ping(self) -> None:
        """
        Purpose: Send one websocket PING frame to reset the proxy idle timer.

        Entry:
            No conditions.

        Exit/Returns:
            No return, and never raises. A dead transport stops the timer
            rather than letting the LoopingCall unwind on its own.

        Notes/References:
            Disconnected is autobahn's "the transport is already gone" error
            and is expected during the window between the socket dropping and
            onClose running. It is not logged, because at that point the
            connection is going away anyway and the noise would be constant.

        Author: Nick Hobar
        Creation date: 08/21/2026
        """
        try:
            self.sendPing()
        except Disconnected:
            self._stop_keepalive()
        except Exception as exc:
            logger.log_err(f"websocket keepalive ping failed: {exc!r}")
            self._stop_keepalive()
