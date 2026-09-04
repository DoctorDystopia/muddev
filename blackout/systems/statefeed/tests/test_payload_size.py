"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/03/2026
Description: Guard the one thing that decides whether a large statefeed payload
             arrives at all: its size against the client's socket ceiling.

Why this is a test and not a comment
------------------------------------
`blackout_map` is chunked at MAP_NODES_PER_CHUNK because Godot's WebSocketPeer
defaults to a 65535-byte inbound buffer, and on Godot < 4.4 an oversized
message was TRUNCATED SILENTLY. That reasoning is written down beside the
constant -- and it protected the map while `room_players` quietly grew past it
to become the larger payload of the two.

It grew because of a knob in another file: STATEFEED_ENTITY_RADIUS is 10, which
on every live map means "the whole map", so one room_players message names every
entity in the world. Measured at ~43 KB on a live-sized map
(docs/2026-09-03-PERF-0002-crowd-scaling.md).

The radius is expected to RISE. So the failure mode this file exists to prevent
is not today's size; it is the day somebody raises the radius, or a map grows,
or a market fills with dropped loot, and a payload silently crosses a ceiling
nobody re-checked. CLIENT_INBOUND_BUFFER_BYTES is that ceiling, it is exported
to the client so both sides read one number, and these tests are what make
crossing it a red suite rather than a bug report about players who cannot
connect.

What "fails" means here
-----------------------
A failure is NOT necessarily a bug in the payload. It is a decision that has
come due, and there are three real answers: raise
CLIENT_INBOUND_BUFFER_BYTES (cheap -- it is one buffer in one client process),
lower STATEFEED_ENTITY_RADIUS, or chunk room_players the way the map is
chunked. The assertion messages say so, because a test that only says "43000 >
40000" invites the fourth answer, which is editing the threshold until it
passes.
"""

import json
import unittest

from evennia.utils.test_resources import EvenniaTest

from systems.statefeed import constants as const
from systems.statefeed import serializers
from systems.statefeed.payloads import RoomPlayersPayload


# ─── Private constant definitions ────────────────────────────────────────────

# The share of the client's buffer a single payload may occupy before this
# suite calls it a problem. Two thirds, not 100%: a payload that exactly fits
# has no room for the growth that a raised radius, a new map or a busy evening
# all produce, and the point of the guard is to fire BEFORE players are
# disconnected rather than at the moment they are.
_HEADROOM_FRACTION = 2.0 / 3.0

# Entities in the synthetic worst case. Chosen to be well past what any live
# map holds today -- the live maps are 59-81 rooms -- so this test is about the
# ceiling rather than about current content, and it does not need a database
# with a map in it to be meaningful.
_WORST_CASE_ENTITIES = 1200

# A generously long name and asset key. Real ones are shorter; a guard that
# assumed the short case would under-report exactly when content grew.
_LONG_NAME = "mutant raider sergeant of the eastern approach"
_LONG_ASSET = "npc_mutant_raider_sergeant_eastern_variant_b"


# ─── Private helper routines ─────────────────────────────────────────────────

def _wire_bytes(payload) -> int:
    """Return the size of the JSON frame this payload becomes on the socket.

    The same shape godot_websocket's send path writes -- [cmd, args, kwargs] --
    because a guard measured against the bare payload body would under-report
    the envelope every real message carries.
    """
    frame = json.dumps([payload.channel, [], payload.to_dict()])

    return len(frame.encode("utf-8"))


def _synthetic_entity(index: int) -> dict:
    """One entity row shaped exactly like serialize_entity's output."""
    return {
        "id": 100000 + index,
        "name": _LONG_NAME,
        "kind": "npc",
        "asset": _LONG_ASSET,
        "family": "weapon",
        "interact": f"attack {_LONG_NAME}",
        "coords": [index % 32, index // 32, "oasis_outskirts"],
        "hp": 40,
        "max_hp": 60,
    }


# ─── Test cases ──────────────────────────────────────────────────────────────

class PayloadCeilingTests(unittest.TestCase):
    """The synthetic worst case, which needs no database."""

    def test_the_client_ceiling_is_above_godots_default(self):
        """
        The whole point of exporting this number is that it is a decision. If
        it were left at WebSocketPeer's own 65535 default, exporting it would
        be ceremony -- the client could just as well not set it.
        """
        self.assertGreater(
            const.CLIENT_INBOUND_BUFFER_BYTES, 65535,
            "CLIENT_INBOUND_BUFFER_BYTES is at or below WebSocketPeer's "
            "default, so setting it on the client buys nothing. Either raise "
            "it or delete it and the client's assignment together.")

    def test_a_worst_case_room_players_payload_fits_with_headroom(self):
        """
        The one that will fail first when the radius rises. It is deliberately
        sized past any live map, so a pass here means the ceiling has room for
        content that does not exist yet.
        """
        entities = [_synthetic_entity(index)
                    for index in range(_WORST_CASE_ENTITIES)]
        size = _wire_bytes(RoomPlayersPayload(entities=entities))
        budget = int(const.CLIENT_INBOUND_BUFFER_BYTES * _HEADROOM_FRACTION)

        self.assertLess(
            size, budget,
            f"A {_WORST_CASE_ENTITIES}-entity room_players payload is "
            f"{size} bytes against a {budget}-byte budget "
            f"({const.CLIENT_INBOUND_BUFFER_BYTES} buffer x "
            f"{_HEADROOM_FRACTION:.2f}). This is a decision coming due, not a "
            "number to edit: raise CLIENT_INBOUND_BUFFER_BYTES (it is one "
            "buffer in one client process), lower STATEFEED_ENTITY_RADIUS, or "
            "chunk room_players the way blackout_map is chunked. See "
            "docs/2026-09-03-PERF-0002-crowd-scaling.md.")

    def test_the_map_chunk_ceiling_still_holds_too(self):
        """
        MAP_NODES_PER_CHUNK exists for the same reason and predates this file.
        Asserting it here keeps the two payload ceilings in one place, so a
        reader raising one is shown the other.
        """
        self.assertGreater(const.MAP_NODES_PER_CHUNK, 0)
        self.assertLess(
            const.MAP_NODES_PER_CHUNK, 2000,
            "A chunk this large defeats the chunking. See the constant.")


class RealPayloadSizeTests(EvenniaTest):
    """The same guard against payloads built by the real serialiser.

    The synthetic test above owns the ceiling; this one owns the claim that
    serialize_entity's real output is the shape the synthetic rows imitate. If
    a field is added to an entity, the synthetic case stops being a worst case
    and this test is what notices.
    """

    def test_a_real_entity_is_not_larger_than_the_synthetic_one(self):
        """The synthetic row must remain an over-estimate, not an under one."""
        real = serializers.serialize_entity(self.obj1, coords=[1, 2, "oasis"])
        real_size = len(json.dumps(real).encode("utf-8"))
        synthetic_size = len(json.dumps(_synthetic_entity(0)).encode("utf-8"))

        self.assertLessEqual(
            real_size, synthetic_size,
            "serialize_entity now produces a row larger than the synthetic "
            "worst case in this file, so the ceiling test above is no longer "
            "conservative. Widen _synthetic_entity to match.")

    def test_every_key_a_real_entity_carries_is_in_the_synthetic_row(self):
        """
        Derived from the serialiser rather than asserted as a census -- a new
        field must show up here, and a field being REMOVED must not fail.
        """
        real = serializers.serialize_entity(self.char1, coords=[0, 0, "oasis"])
        synthetic = _synthetic_entity(0)

        for key in real:
            with self.subTest(key=key):
                self.assertIn(
                    key, synthetic,
                    f"serialize_entity now emits {key!r}, which the synthetic "
                    "worst-case row in this file does not model.")
