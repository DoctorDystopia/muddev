"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/03/2026
Description: Profiling scenarios for the cost that grows with the number of
             PLAYERS in a map, rather than with the amount of world in it.

The question these scenarios exist to answer
--------------------------------------------
Every other scenario in this package measures one observer doing one thing.
That is the right shape for asking "is this serialiser slow", and it is the
wrong shape for asking "why does the game stutter when the Oasis fills up" --
because a cost that is per-observer is completely invisible when the fixture
has exactly one.

The statefeed's fan-out is per-observer BY CONSTRUCTION. emit_to_area walks
every room in the neighbourhood, emit_to_room walks every occupant of each,
and emit() builds the payload dict and hands it to obj.msg() once per session
reached. So a payload's cost is (size of payload) x (number of subscribed
players who can see it), and a room where everyone can see everyone else makes
both factors the same number.

Why a ladder and not a before/after
-----------------------------------
CROWD_SIZES is three points, not two, and the third point is what makes the
measurement an argument rather than an anecdote. Two points cannot distinguish
"costs more with more players" (which is fine and expected) from "costs more
per player with more players" (which is the quadratic that closes a map). A
row that triples from 1 to 8 and triples again from 8 to 24 is linear in the
crowd; one that grows 8x and then 9x again is not.

Read the results as RATIOS between the rungs of one ladder. The absolute
milliseconds depend on the machine; the shape does not.

Where the crowd stands, and why it is not the centre
---------------------------------------------------
The crowd is created on first request and never torn down -- see
world_fixture.crowd on why rebuilding it between rungs would be worse. And this
module is discovered FIRST, not last: pkgutil walks alphabetically and "crowd"
sorts before "database", "engine" and "statefeed". So by the time the radius-3
scenarios are measured, this module's 24 Characters are already standing in the
world.

harness.py accepts shared state between scenarios. scenarios/engine.py's
_arm_crowd documents the one form of it that is NOT accepted -- silently
changing the SIZE of the world a later scenario walks -- and records that
getting this wrong once moved serialize_contents from 0.015 ms to 0.076 ms and
looked exactly like a regression in code that had not changed.

So the crowd stands on world_fixture.CROWD_TILE, a far corner outside the
radius-3 neighbourhood every other statefeed scenario measures. The whole-map
scenarios here DO see it, which is the point of them.

Every scenario below names its own crowd size rather than inheriting one, so
none of them depends on what the scenario before it left behind.
"""

from systems.statefeed import events, serializers
from systems.statefeed.payloads import RoomPlayerAddPayload
from systems.statefeed.emit import emit_to_area

from .. import constants as const
from ..world_fixture import CROWD_SIZES, CROWD_TILE
from . import scenario


# ─── Private constant definitions ────────────────────────────────────────────

# Passes per measured scenario. The fan-out scenarios send to every member of
# the crowd on every pass, so the 24-observer rung does 24 clean_senddata walks
# and 24 pickles per pass -- enough work that a high repeat count buys nothing
# but wall-clock.
_FANOUT_REPEAT = 20

# The area serialisations walk the whole fixture map. Fewer passes still.
_AREA_REPEAT = 10

# One move drives the full at_object_leave / at_object_receive hook chain,
# which is the most expensive single thing a player can do. Kept low because
# each pass is two real moves.
_MOVE_REPEAT = 10


# ─── Private helper routines ─────────────────────────────────────────────────

def _add_payload(world):
    """Build the one-entity delta an arrival broadcasts.

    Built in SETUP, so a fan-out scenario measures the fan-out and not the
    serialisation feeding it. serialize_entity has its own scenario, and
    folding the two together is what would make a regression in either
    unattributable to one of them.
    """
    coords = serializers.room_coords(world.centre)
    body = serializers.serialize_entity(world.items[0], coords=coords)

    return RoomPlayerAddPayload(entity=body)

# ─── Public routines ─────────────────────────────────────────────────────────
#
# REGISTRATION ORDER IS THE MEASUREMENT ORDER, and here it is load-bearing
# rather than cosmetic. world.crowd() only ever grows the pool, so the clean
# whole-map baseline has to be measured before anything asks for a crowd at
# all -- otherwise the row labelled "no players" is taken against a world that
# already has 24 of them, and the delta the crowded row is supposed to reveal
# has already been paid by its own baseline.
#
# The ladder therefore reads top to bottom as 0 players, 1, 1, 8, 24, 24.

@scenario(name="serialize_area whole map (radius 10)",
          layer=const.LAYER_STATEFEED,
          repeat=_AREA_REPEAT,
          notes="What emit_room_contents ACTUALLY builds in production. "
                "STATEFEED_ENTITY_RADIUS is 10 and every live map is smaller "
                "than that, so the neighbourhood is the whole map. Compare "
                "against the radius-3 row above.")
def serialize_whole_map(world):
    """Measure the area serialisation at the radius the live game uses."""
    rooms = world.full_map()
    exclude = (world.character,)

    def work():
        serializers.serialize_area(rooms, exclude=exclude)

    return work


@scenario(name="emit_room_contents to 1 player",
          layer=const.LAYER_STATEFEED,
          repeat=_AREA_REPEAT,
          notes="Serialise the map AND send it. One observer.")
def contents_emit_one(world):
    """Measure the whole-map snapshot build and send for a single client."""
    crowd = world.crowd(CROWD_SIZES[0])
    observer = crowd[0]

    def work():
        events.emit_room_contents(observer, force=True)

    return work


@scenario(name="fan-out: 1-entity delta to 1 player",
          layer=const.LAYER_STATEFEED,
          repeat=_FANOUT_REPEAT,
          notes="Whole map, one subscribed observer. The unit the next two "
                "rows are read against.")
def fanout_delta_one(world):
    """Measure a one-entity broadcast reaching a single subscribed client."""
    world.crowd(CROWD_SIZES[0])
    rooms = world.full_map()
    payload = _add_payload(world)

    def work():
        emit_to_area(rooms, payload)

    return work


@scenario(name="fan-out: 1-entity delta to 8 players",
          layer=const.LAYER_STATEFEED,
          repeat=_FANOUT_REPEAT,
          notes="The same broadcast with 8 subscribed observers on the tile.")
def fanout_delta_eight(world):
    """Measure the same broadcast against a small crowd."""
    world.crowd(CROWD_SIZES[1])
    rooms = world.full_map()
    payload = _add_payload(world)

    def work():
        emit_to_area(rooms, payload)

    return work


@scenario(name="fan-out: 1-entity delta to 24 players",
          layer=const.LAYER_STATEFEED,
          repeat=_FANOUT_REPEAT,
          notes="A busy Oasis. Compare the ratio against the 1- and 8-player "
                "rows: linear in the crowd is expected, worse is the bug.")
def fanout_delta_crowd(world):
    """Measure the same broadcast against a full room."""
    world.crowd(CROWD_SIZES[2])
    rooms = world.full_map()
    payload = _add_payload(world)

    def work():
        emit_to_area(rooms, payload)

    return work


@scenario(name="serialize_area whole map, 24 players present",
          layer=const.LAYER_STATEFEED,
          repeat=_AREA_REPEAT,
          notes="The same build with a crowd standing in it. The delta "
                "against the row above is what each additional player costs "
                "EVERY other player's snapshot.")
def serialize_whole_map_crowded(world):
    """Measure the area serialisation with a crowd inside the radius."""
    world.crowd(CROWD_SIZES[2])
    rooms = world.full_map()
    exclude = (world.character,)

    def work():
        serializers.serialize_area(rooms, exclude=exclude)

    return work


@scenario(name="emit_room_contents to each of 24 players",
          layer=const.LAYER_STATEFEED,
          repeat=_AREA_REPEAT,
          notes="What a resync or a mass arrival costs: every observer "
                "rebuilds the whole-map snapshot INDEPENDENTLY. Divide by 24 "
                "and compare against the 1-player row -- the per-player cost "
                "should be identical, and that is the finding, not a relief.")
def contents_emit_crowd(world):
    """Measure every member of a crowd rebuilding its own map snapshot."""
    crowd = world.crowd(CROWD_SIZES[2])

    def work():
        for observer in crowd:
            events.emit_room_contents(observer, force=True)

    return work


@scenario(name="player move, 24 players watching",
          layer=const.LAYER_STATEFEED,
          repeat=_MOVE_REPEAT,
          notes="One real move_to and back, driving the full at_object_leave "
                "/ at_object_receive hook chain with a crowd watching. This "
                "is the composite a player feels when they press a "
                "direction key in a busy room.")
def player_move_crowded(world):
    """Measure a complete round-trip move with a crowd in the room."""
    crowd = world.crowd(CROWD_SIZES[2])
    mover = crowd[0]
    home = world.tiles[CROWD_TILE]
    neighbour = world.tiles[(CROWD_TILE[0] + 1, CROWD_TILE[1])]

    def work():
        mover.move_to(neighbour, quiet=True, move_hooks=True)
        mover.move_to(home, quiet=True, move_hooks=True)

    return work


@scenario(name="_visible_rooms at production radius 10",
          layer=const.LAYER_DATABASE,
          repeat=_FANOUT_REPEAT,
          notes="The room lookup every single feed event opens with. One "
                "query, but a bounding-box tag join over a 21x21 box, and it "
                "runs once per arrival, once per departure and once per "
                "contents rebuild -- so its cost multiplies by the crowd too.")
def visible_rooms_production(world):
    """Measure the neighbourhood lookup at the radius the live game uses."""
    room = world.centre

    def work():
        events._visible_rooms(room)

    return work
