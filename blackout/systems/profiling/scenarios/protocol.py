"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/03/2026
Description: Profiling scenarios for the protocol layer -- what happens to a
             payload between the statefeed handing it over and the socket
             carrying it away.

What this layer actually is
---------------------------
Two different costs share one name here, and the audit has to keep them apart:

  1. STRUCTURED payloads. A _Payload becomes a dict, the dict becomes an
     outputfunc kwarg, and Evennia's send_default JSON-dumps it. No parsing,
     no ANSI, no BBCode -- this is the path every statefeed channel takes.
  2. TEXT. Every line of prose the game sends a Godot client goes through
     BlackoutBBCodeParser.parse, which runs parse_ansi and then SEVEN regular
     expression passes over the result. This is the path `look`, combat prose
     and every system message take.

The second is the one worth measuring, because its cost is per LINE and the
number of lines is unbounded -- a `look` at a busy room, a combat round with
six combatants, a shop list. The first is bounded by the payload's own size,
which the chunking already caps.

Why the parser is measured and not the socket
----------------------------------------------
A socket write's cost is the network's, and the harness cannot make a
meaningful claim about it from a test database. What it CAN measure is
everything the server does before the bytes leave, which is where every cost
the game controls lives.
"""

import json

from server.conf.godot_websocket import BLACKOUT_BBCODE_PARSER, escape_bbcode

from .. import constants as const
from . import scenario


# ─── Private constant definitions ────────────────────────────────────────────

# A line of game prose with the ANSI the game really emits: a colour code, a
# reset, and brackets a player could have typed.
_COLOURED_LINE = ("|cMutant Raider|n hits you for |r14|n damage. "
                  "[usage: attack <target>]")

# A plain line with no ANSI at all, to separate the parser's fixed cost from
# the colour handling.
_PLAIN_LINE = "You see a rusty scrap spear lying in the dust."

# Lines per measured pass. A `look` at a populated room is this order.
_LINES_PER_PASS = 40

_TEXT_REPEAT = 50
_JSON_REPEAT = 200


# ─── Public routines ─────────────────────────────────────────────────────────

@scenario(name="BBCode parse, 40 coloured lines",
          layer=const.LAYER_PROTOCOL,
          repeat=_TEXT_REPEAT,
          notes="parse_ansi plus seven regex passes, per line. This runs on "
                "every line of prose a Godot client is sent.")
def bbcode_coloured(world):
    """Measure the full text conversion on realistic coloured game output."""
    parser = BLACKOUT_BBCODE_PARSER

    def work():
        for _ in range(_LINES_PER_PASS):
            parser.parse(_COLOURED_LINE)

    return work


@scenario(name="BBCode parse, 40 plain lines",
          layer=const.LAYER_PROTOCOL,
          repeat=_TEXT_REPEAT,
          notes="The same path with no ANSI to convert. The difference "
                "against the coloured scenario is what colour handling costs; "
                "what remains is the fixed regex cost paid either way.")
def bbcode_plain(world):
    """Measure the conversion's fixed cost on text with no ANSI."""
    parser = BLACKOUT_BBCODE_PARSER

    def work():
        for _ in range(_LINES_PER_PASS):
            parser.parse(_PLAIN_LINE)

    return work


@scenario(name="escape_bbcode alone, 40 lines",
          layer=const.LAYER_PROTOCOL,
          repeat=_TEXT_REPEAT,
          notes="One regex substitution. Isolates the escape from the six "
                "other passes around it.")
def escape_only(world):
    """Measure the bracket escape in isolation."""
    def work():
        for _ in range(_LINES_PER_PASS):
            escape_bbcode(_COLOURED_LINE)

    return work


@scenario(name="json.dumps a serialised area payload",
          layer=const.LAYER_PROTOCOL,
          repeat=_JSON_REPEAT,
          notes="What send_default does to a structured payload. Measured on "
                "the real output of serialize_area rather than a stand-in.")
def json_encode_area(world):
    """Measure JSON encoding of a real area serialisation."""
    from systems.statefeed import serializers

    rooms = world.rooms_within(3)
    entities = serializers.serialize_area(rooms, exclude=(world.character,))

    def work():
        json.dumps(entities)

    return work
