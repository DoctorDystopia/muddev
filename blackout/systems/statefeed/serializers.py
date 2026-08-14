"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/07/2026
Description: Turn live Evennia objects into the plain, JSON-safe values the
             payload dataclasses carry.

             The central idea here is the ASSET KEY. Every renderable entity is
             sent with a stable string naming what it is -- `rusty_scrap_spear`,
             `mutant_raider`, `Bank` -- and a client resolves that to a mesh.
             When it has no asset for the key it draws a generic mesh with the
             entity's real name. That fallback is what stops a graphical client
             from blocking content work: an item added to ITEM_DB renders
             immediately, correctly labelled, with no art request. IRE's GMCP
             surface calls the same field `icon`.

             Blackout already had every key this needs; none of it is new
             state. Items carry a prototype tag stamped by ItemDef.create ->
             spawn(); NPCs carry db.npc_key stamped by NpcDef.create; rooms
             carry their map prototype's key.
"""

from evennia.prototypes.prototypes import PROTOTYPE_TAG_CATEGORY

from . import constants as const


# ─── Private constant definitions ────────────────────────────────────────────

# Members in an XYZRoom.xyz tuple. Named so the shape check in room_coords is
# not a bare literal.
_XYZ_LENGTH: int = 3

# Evennia's own content-type marker for a puppetable character. Declared on
# DefaultCharacter as _content_types = ("character",).
_CHARACTER_CONTENT_TYPE: str = "character"


# ─── Private helper routines ─────────────────────────────────────────────────

def _prototype_key(entity) -> str:
    """
    Purpose: Read the prototype key Evennia stamped on a spawned ITEM.

    Entry:
        entity - any object. Need not have been spawned from a prototype.

        Items only. Do NOT call this for rooms: the xyzgrid sets no explicit
        prototype_key, so Evennia auto-generates a per-room hash
        ("prototype-8ede16d") which names nothing. room_kind() reads the room
        key instead, and documents why.

    Exit/Returns:
        The prototype key string, or "" when the object carries no prototype
        tag or has no tag handler at all.

    Module Globals:
        PROTOTYPE_TAG_CATEGORY read.

    Methodology:
        evennia.prototypes.spawner stores the key as a TAG in the
        "from_prototype" category, not as an Attribute -- so this cannot read
        entity.db.prototype_key, which is always None on a spawned object.

        tags.get() returns a bare string for one match and a list for several.
        An object should only ever carry one prototype tag, but normalising
        both shapes here means a hand-built or re-applied object cannot crash
        the feed.

    Notes/References:
        world/item_database.py:151 is where the key originates.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    tag_handler = getattr(entity, "tags", None)

    if tag_handler is None:
        return ""

    tagged = tag_handler.get(category=PROTOTYPE_TAG_CATEGORY, return_list=True)

    if not tagged:
        return ""

    return str(tagged[0])


def _classify(entity) -> tuple:
    """
    Purpose: Decide what kind of thing an entity is and which asset key names it.

    Entry:
        entity - any object with a `key`.

    Exit/Returns:
        Returns (kind, asset_key). `kind` is one of the ASSET_KIND_*
        constants; `asset_key` is ASSET_KEY_GENERIC when nothing better exists.

    Module Globals:
        const.ASSET_KIND_* and const.ASSET_KEY_GENERIC read.

    Methodology:
        Ordered most-specific first. npc_key is checked before anything else
        because every hostile NPC shares one typeclass -- the typeclass cannot
        tell a mutant raider from a big mutant, but npc_key can.

        gatherable_key is read the same way, and for the same reason: it is a
        plain db attribute, so this module stays out of the typeclass layer
        instead of importing gathering_nodes and inverting the dependency
        between a system and it. A node must not fall through to "item" --
        it carries `get:false()`, so a client told "item" would offer to pick
        up the one thing that cannot be picked up.

        Characters are identified by Evennia's own `_content_types`, which is
        ("character",) on DefaultCharacter and ("object",) on everything else.
        Using the engine's classification keeps this module from importing the
        typeclass layer and inverting the dependency between a system and it.

        Do NOT be tempted back to a `hasattr(entity, "sessions")` check here.
        Every DefaultObject carries a sessions handler, so that test is true
        for a rock and classified the entire item catalogue as characters.

    Notes/References:
        world/npc_database.py:143 stamps db.npc_key.
        evennia/objects/objects.py:3024 declares the character content type.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    npc_key = entity.attributes.get("npc_key", default=None)

    if npc_key:
        return const.ASSET_KIND_NPC, str(npc_key)

    gatherable_key = entity.attributes.get("gatherable_key", default=None)

    if gatherable_key:
        return const.ASSET_KIND_GATHERABLE, str(gatherable_key)

    content_types = getattr(entity, "_content_types", ())

    if _CHARACTER_CONTENT_TYPE in content_types:
        return const.ASSET_KIND_CHARACTER, const.ASSET_KEY_GENERIC

    proto_key = _prototype_key(entity)

    if proto_key:
        return const.ASSET_KIND_ITEM, proto_key

    return const.ASSET_KIND_ITEM, const.ASSET_KEY_GENERIC


# ─── Public routines ─────────────────────────────────────────────────────────

def serialize_entity(entity) -> dict:
    """
    Purpose: Render one visible entity as a plain dict for a graphical client.

    Entry:
        entity - a live, non-deleted object.

    Exit/Returns:
        Returns a dict of JSON-safe primitives. Always carries id, name, kind
        and asset. Carries hp / max_hp only when the entity actually has them,
        so a client can tell "full health" from "not a combatant" -- an item
        reported at 0/0 would render a health bar on a rock.

    Module Globals:
        None.

    Methodology:
        Reads through getattr with defaults throughout. This runs during
        combat and room broadcasts, where an entity may be mid-deletion, and a
        cosmetic feed must never be able to raise into a gameplay path.

    Notes/References:
        Deliberately omits `desc`. The text channel already carries it, and
        duplicating prose into the feed is how the two drift apart.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    kind, asset_key = _classify(entity)
    body = {
        "id": entity.id,
        "name": str(entity.key),
        "kind": kind,
        "asset": asset_key,
    }

    max_hp = getattr(entity, "max_hp", None)

    if max_hp:
        body["hp"] = getattr(entity, "hp", 0)
        body["max_hp"] = max_hp

    return body


def serialize_contents(room, exclude=()) -> list:
    """
    Purpose: Render everything visible in a room.

    Entry:
        room    - a room object, or None.
        exclude - objects to leave out (typically the observer themself).

    Exit/Returns:
        Returns a list of entity dicts. Empty list when room is None.

    Module Globals:
        None.

    Methodology:
        Skips exits. An exit is a real Evennia object sitting in room.contents,
        but it is topology rather than an occupant -- exits reach the client
        through RoomInfoPayload.exits, and emitting them here too would have a
        client drawing a mesh for every doorway.

    Notes/References:
        Only ever called with the observer's OWN room while
        STATEFEED_ENTITY_RADIUS is 0. See that constant before widening this.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    if room is None:
        return []

    entities = []

    for obj in room.contents:
        if obj in exclude:
            continue

        if obj.destination is not None:
            continue

        entry = serialize_entity(obj)
        entities.append(entry)

    return entities


def room_kind(room) -> str:
    """
    Purpose: Name the room's type for a client's prefab / tint lookup.

    Entry:
        room - a room object, or None.

    Exit/Returns:
        Returns the room's kind ("Oasis", "Bank", "Pole clearing", ...), or
        ROOM_KIND_DEFAULT when the room has no key at all.

    Module Globals:
        const.ROOM_KIND_DEFAULT read.

    Methodology:
        Reads the room's KEY, and deliberately not its prototype tag.

        Every map's PROTOTYPES table sets "key" per coordinate (or via the
        ('*', '*') wildcard), and the xyzgrid builder applies that key to the
        spawned room. mapexport reads that same "key" out of the same table.
        So key is exactly the value that makes room_info agree with
        blackout_map, which is the whole point of the field: a client looks a
        tile up in the map it was sent.

        The prototype tag is NOT usable here even though it is the right
        source for items. The xyzgrid does not set an explicit prototype_key
        for rooms, so Evennia auto-generates one -- rooms come back tagged
        "prototype-8ede16d" and every tile gets a different hash. Using it made
        room_info report a hash while blackout_map reported "Oasis" for the
        same tile, and nothing could be matched up.

    Notes/References:
        This is the field a modular kit-room renderer will key its prefab
        table off. Named for what it means, not for the box-tinting that is
        currently all it drives.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    if room is None:
        return const.ROOM_KIND_DEFAULT

    room_key = getattr(room, "key", "")

    if room_key:
        return str(room_key)

    return const.ROOM_KIND_DEFAULT


def serialize_exits(room) -> dict:
    """
    Purpose: Render a room's exits as {direction: destination_id}.

    Entry:
        room - a room object, or None.

    Exit/Returns:
        Returns a dict mapping each exit's key to its destination's id.
        Destinations that are None (a broken exit) are skipped rather than
        sent as null.

    Module Globals:
        None.

    Methodology:
        Reads room.exits, which Evennia already filters to objects with a
        destination.

    Notes/References:
        Mirrors GMCP Room.Info's `exits` field as IRE and Aardwolf define it.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    if room is None:
        return {}

    exits = {}

    for exit_obj in room.exits:
        destination = exit_obj.destination

        if destination is None:
            continue

        exits[str(exit_obj.key)] = destination.id

    return exits


def room_coords(room) -> list:
    """
    Purpose: Read a room's grid coordinates as [x, y, z].

    Entry:
        room - a room object. May be a plain Room with no coordinates.

    Exit/Returns:
        Returns [x, y, z] with x/y as ints and z as the map NAME string, or an
        empty list for a room that is not on the grid.

    Module Globals:
        None.

    Methodology:
        Two distinct "no coordinates" cases have to be absorbed here, because a
        client must never learn either of them. A plain Room has no `xyz`
        attribute at all and raises AttributeError. An XYZRoom whose coordinate
        tags have not finished saving returns a tuple of Nones rather than
        raising -- and that tuple is TRUTHY, so an emptiness check alone would
        let it through and int(None) would blow up inside a broadcast.

    Notes/References:
        Z is a map NAME ("oasis"), not an elevation. A client needs an authored
        z -> world-offset table; it cannot derive one from this value.

        Coordinates are stored as string Tags, hence the int() conversions.
        See systems/combat/auras/targeting.py:80 for why that storage choice
        matters elsewhere.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    try:
        xyz = room.xyz
    except Exception:
        return []

    if not xyz or len(xyz) != _XYZ_LENGTH:
        return []

    if None in xyz:
        return []

    return [int(xyz[0]), int(xyz[1]), str(xyz[2])]
