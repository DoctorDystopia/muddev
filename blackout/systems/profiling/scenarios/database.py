"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/03/2026
Description: Profiling scenarios for the database layer -- the ORM patterns
             every other layer is built on.

Why these are measured apart from the code that calls them
-----------------------------------------------------------
A statefeed scenario that reports 200 queries has told you there is a problem
but not where it is. These scenarios measure the primitives directly -- reading
an Attribute, reading a Tag, resolving a foreign key, filtering a room's
contents -- so that a serialiser's cost can be divided by the unit cost of what
it is doing and come out as a COUNT rather than a mystery.

The Evennia-specific fact the whole layer turns on
--------------------------------------------------
`db_location` and `db_destination` are real Django ForeignKeys, and every
Evennia model is a SharedMemoryModel with an idmapper in front of it. Whether
`obj.location` costs a query therefore depends on state -- whether the target
row is already in the idmapper, and whether Django's own per-instance field
cache is populated -- which is exactly the kind of thing that is safe in a test
of five objects and catastrophic in a room of five hundred. The paired
scenarios below read the same fact two ways, through the FK and through the raw
`_id` column, so the difference is a measurement rather than an argument.
"""

from evennia.objects.models import ObjectDB

from .. import constants as const
from . import scenario


# ─── Private constant definitions ────────────────────────────────────────────

# High enough that a per-object cost separates from constant overhead.
_ATTRIBUTE_REPEAT = 200

# Bulk queries are slower per pass, so they run fewer times.
_QUERY_REPEAT = 30


# ─── Public routines ─────────────────────────────────────────────────────────

@scenario(name="ObjectDB filter by location (49 rooms)",
          layer=const.LAYER_DATABASE,
          repeat=_QUERY_REPEAT,
          notes="The single bulk query serialize_area opens with.")
def bulk_contents_query(world):
    """Measure the one query that fetches every object across an area."""
    rooms = world.rooms_within(3)
    room_ids = []

    for room in rooms:
        room_ids.append(room.id)

    def work():
        found = ObjectDB.objects.filter(db_location__id__in=room_ids)
        list(found)

    return work


@scenario(name="FK traversal obj.location.id (147 objects)",
          layer=const.LAYER_DATABASE,
          repeat=_QUERY_REPEAT,
          notes="What serialize_area does per object today. Compare against "
                "the db_location_id scenario below -- the difference IS the "
                "avoidable cost.")
def fk_traversal(world):
    """Measure resolving each object's location through the FK descriptor."""
    rooms = world.rooms_within(3)
    room_ids = []

    for room in rooms:
        room_ids.append(room.id)

    def work():
        found = ObjectDB.objects.filter(db_location__id__in=room_ids)

        for obj in found:
            _ = obj.location.id

    return work


@scenario(name="Raw column obj.db_location_id (147 objects)",
          layer=const.LAYER_DATABASE,
          repeat=_QUERY_REPEAT,
          notes="The same fact read off the column already in the row. "
                "Cannot issue a query by construction.")
def raw_column_read(world):
    """Measure reading the location id without traversing the FK."""
    rooms = world.rooms_within(3)
    room_ids = []

    for room in rooms:
        room_ids.append(room.id)

    def work():
        found = ObjectDB.objects.filter(db_location__id__in=room_ids)

        for obj in found:
            _ = obj.db_location_id

    return work


@scenario(name="FK traversal obj.destination (147 objects)",
          layer=const.LAYER_DATABASE,
          repeat=_QUERY_REPEAT,
          notes="serialize_area's exit test. Every object in the area is "
                "asked, and almost none of them are exits.")
def destination_traversal(world):
    """Measure the exit test as the serialiser performs it."""
    rooms = world.rooms_within(3)
    room_ids = []

    for room in rooms:
        room_ids.append(room.id)

    def work():
        found = ObjectDB.objects.filter(db_location__id__in=room_ids)

        for obj in found:
            _ = obj.destination is not None

    return work


@scenario(name="Raw column obj.db_destination_id (147 objects)",
          layer=const.LAYER_DATABASE,
          repeat=_QUERY_REPEAT,
          notes="The same exit test with no FK fetch.")
def destination_raw(world):
    """Measure the exit test read off the raw column."""
    rooms = world.rooms_within(3)
    room_ids = []

    for room in rooms:
        room_ids.append(room.id)

    def work():
        found = ObjectDB.objects.filter(db_location__id__in=room_ids)

        for obj in found:
            _ = obj.db_destination_id is not None

    return work


@scenario(name="room.contents (single room)",
          layer=const.LAYER_DATABASE,
          repeat=_ATTRIBUTE_REPEAT,
          notes="Evennia's contents_cache. Establishes whether the one-room "
                "path pays a query at all.")
def room_contents(world):
    """Measure the cached contents read serialize_contents uses."""
    room = world.centre

    def work():
        list(room.contents)

    return work


@scenario(name="Tag read room.xyz (single room)",
          layer=const.LAYER_DATABASE,
          repeat=_ATTRIBUTE_REPEAT,
          notes="Coordinates are string Tags. This is what room_coords costs "
                "before any caching.")
def xyz_tag_read(world):
    """Measure the coordinate tag read behind room_coords."""
    room = world.centre

    def work():
        _ = room.xyz

    return work


@scenario(name="Attribute read obj.db.desc (single object)",
          layer=const.LAYER_DATABASE,
          repeat=_ATTRIBUTE_REPEAT,
          notes="The unit cost of one AttributeHandler read, which the "
                "serialisers perform several times per entity.")
def attribute_read(world):
    """Measure a single Attribute read through the handler."""
    entity = world.items[0]

    def work():
        _ = entity.db.desc

    return work
