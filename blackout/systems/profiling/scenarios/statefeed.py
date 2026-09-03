"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/03/2026
Description: Profiling scenarios for the statefeed layer -- the serialisers
             that turn world objects into the dicts a client draws.

             This is the layer the audit cares most about, because it is the
             only one that runs per observer per tick AND walks an unbounded
             number of objects. A combat handler's cost is bounded by the
             number of combatants; serialize_area's is bounded by how much
             world is within the observer's radius, which is a content
             decision made in world/maps/.

             Every scenario here resolves its input in the factory and
             measures only the serialiser. Handing serialize_area a list of
             rooms it did not have to look up is the point: the targeting
             query has its own scenario, and folding the two together would
             make it impossible to say which of them a regression was in.
"""

from systems.statefeed import serializers
from systems.statefeed.payloads import CharItemsPayload, MapChunkPayload

from .. import constants as const
from . import scenario


# ─── Private constant definitions ────────────────────────────────────────────

# Radii the feed actually uses. 1 is a doorway's worth of context and 3 is what
# the area feed sends on a move, so the pair brackets the real range and the
# ratio between them says whether the cost is per-room or per-object.
_SMALL_RADIUS = 1
_LARGE_RADIUS = 3

# Repeat counts. The area scenarios touch hundreds of objects per pass, so they
# run fewer times than the single-object ones and still take longer.
_AREA_REPEAT = 10
_ENTITY_REPEAT = 200

# A payload body big enough that asdict's recursive walk is measurable against
# the dataclass construction around it.
_ITEM_ROWS = 60
_MAP_ROWS = 40


# ─── Public routines ─────────────────────────────────────────────────────────

@scenario(name="serialize_area radius 3",
          layer=const.LAYER_STATEFEED,
          repeat=_AREA_REPEAT,
          notes="49 tiles, 3 objects each. The move-time area feed.")
def serialize_area_wide(world):
    """Measure the wide-radius area serialisation the feed sends on a move."""
    rooms = world.rooms_within(_LARGE_RADIUS)
    exclude = (world.character,)

    def work():
        serializers.serialize_area(rooms, exclude=exclude)

    return work


@scenario(name="serialize_area radius 1",
          layer=const.LAYER_STATEFEED,
          repeat=_AREA_REPEAT,
          notes="9 tiles. Compare against radius 3 to separate per-room "
                "cost from per-object cost.")
def serialize_area_narrow(world):
    """Measure the narrow-radius area serialisation."""
    rooms = world.rooms_within(_SMALL_RADIUS)
    exclude = (world.character,)

    def work():
        serializers.serialize_area(rooms, exclude=exclude)

    return work


@scenario(name="serialize_contents single room",
          layer=const.LAYER_STATEFEED,
          repeat=_AREA_REPEAT,
          notes="The one-room path, for callers that genuinely mean one room.")
def serialize_contents_one(world):
    """Measure the single-room serialisation."""
    room = world.centre
    exclude = (world.character,)

    def work():
        serializers.serialize_contents(room, exclude=exclude)

    return work


@scenario(name="serialize_entity single object",
          layer=const.LAYER_STATEFEED,
          repeat=_ENTITY_REPEAT,
          notes="The per-object unit cost every area serialisation multiplies.")
def serialize_entity_one(world):
    """Measure one entity's serialisation, which the area paths repeat."""
    entity = world.items[0]
    coords = serializers.room_coords(world.centre)

    def work():
        serializers.serialize_entity(entity, coords=coords)

    return work


@scenario(name="room_coords single room",
          layer=const.LAYER_STATEFEED,
          repeat=_ENTITY_REPEAT,
          notes="Reads coordinate Tags. serialize_area calls this once per "
                "room, so its query cost multiplies by the radius.")
def room_coords_one(world):
    """Measure the coordinate read the area path repeats per room."""
    room = world.centre

    def work():
        serializers.room_coords(room)

    return work


@scenario(name="tile_actions for a room",
          layer=const.LAYER_STATEFEED,
          repeat=_AREA_REPEAT,
          notes="Builds the per-tile affordances the client sends verbatim.")
def tile_actions_one(world):
    """Measure the tile-affordance build."""
    room = world.centre

    def work():
        serializers.tile_actions(room)

    return work


@scenario(name="payload.to_dict (items, 60 rows)",
          layer=const.LAYER_STATEFEED,
          repeat=_ENTITY_REPEAT,
          notes="dataclasses.asdict recursively deep-copies every nested "
                "value. Measured against the payload the inventory sends.")
def payload_to_dict_items(world):
    """Measure the dataclass-to-dict conversion on a realistic item payload."""
    rows = []

    for index in range(_ITEM_ROWS):
        rows.append({"id": index,
                     "name": f"scrap_{index}",
                     "family": "junk",
                     "quantity": index,
                     "commands": {"use": f"use scrap_{index}",
                                  "drop": f"drop scrap_{index}"}})

    payload = CharItemsPayload(items=rows)

    def work():
        payload.to_dict()

    return work


@scenario(name="payload.to_dict (map chunk, 1600 nodes)",
          layer=const.LAYER_STATEFEED,
          repeat=_ENTITY_REPEAT,
          notes="The largest single payload the feed sends, which is why it "
                "is the one that had to be chunked.")
def payload_to_dict_map(world):
    """Measure the conversion on the map-chunk payload."""
    nodes = []
    links = []

    for row in range(_MAP_ROWS):
        for column in range(_MAP_ROWS):
            nodes.append({"x": column, "y": row, "room_kind": "Wastes"})
            links.append({"from": [column, row], "to": [column + 1, row]})

    payload = MapChunkPayload(z="profiling_fixture", nodes=nodes, links=links)

    def work():
        payload.to_dict()

    return work
