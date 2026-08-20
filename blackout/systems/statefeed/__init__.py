"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/07/2026
Description: The structured state feed — a machine-readable side-channel that
             mirrors what the text channel already says, for graphical clients.

             Nothing here is required for play. The text channel stays complete
             and authoritative; this package is enrichment that a client opts
             into and that costs a non-subscribed session nothing.

             Public surface:
                 emit.emit / emit.emit_to_room  — send a payload
                 payloads.*                     — one dataclass per channel
                 constants.CHANNEL_*            — the channel names
"""

# Imported for its side effect: buffer registers the tick-phase hooks that
# bracket its per-tick coalescing window.
from . import buffer  # noqa: E402,F401
