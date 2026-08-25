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
        const.ASSET_KIND_*, const.ASSET_KEY_GENERIC and
        const.ASSET_KEY_CHARACTER read.

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

        A character is named ASSET_KEY_CHARACTER and not ASSET_KEY_GENERIC.
        The two were the same key until art existed for a person, and sharing
        them stopped being harmless the moment it did: generic is the fallback
        for an unclassified ITEM, so a client that registered a body against it
        would draw one for every unmodelled object in the game. A character
        that declares `asset_key` still overrides this, one branch above.

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

    # A typeclass that describes itself wins over anything inferred below.
    # This is what a Foundry Furnace, a bank terminal and a shopkeeper have in
    # common: nothing about their storage distinguishes them from a dropped
    # sword, so they say what they are rather than being guessed at.
    declared_kind = getattr(entity, "asset_kind", "")

    if declared_kind:
        declared_key = getattr(entity, "asset_key", "")

        return str(declared_kind), str(declared_key or const.ASSET_KEY_GENERIC)

    content_types = getattr(entity, "_content_types", ())

    if _CHARACTER_CONTENT_TYPE in content_types:
        return const.ASSET_KIND_CHARACTER, const.ASSET_KEY_CHARACTER

    proto_key = _prototype_key(entity)

    if proto_key:
        return const.ASSET_KIND_ITEM, proto_key

    return const.ASSET_KIND_ITEM, const.ASSET_KEY_GENERIC


def _item_family(item) -> str:
    """
    Purpose: Name the mesh FAMILY an item belongs to.

    Entry:
        item - a live object.

    Exit/Returns:
        One of the const.ITEM_FAMILY_* values, or ITEM_FAMILY_GENERIC when the
        item carries no recognised family tag.

    Module Globals:
        const.ITEM_FAMILIES and const.ITEM_FAMILY_GENERIC read.

    Methodology:
        Every ItemDef declares its family as a tag CATEGORY already -- a spear
        is tagged ("rusty_scrap_spear", "weapon") -- so this reads a fact the
        item database owns rather than restating it in a table here. The same
        rule the asset key follows: adding an item to ITEM_DB must not require
        an edit anywhere else before it renders.

        The walk is over const.ITEM_FAMILY_PRIORITY rather than over the
        object's tags, which is what makes this safe on both counts. A spawned
        item also carries Evennia's own from_prototype tag, and a naive "first
        category wins" would return that as the family for every item in the
        game. And an item may declare SEVERAL families -- the rusty scrap axe
        is a crafting_tool and a weapon -- where "first category wins" would
        answer differently between two calls, because Evennia hands tags back
        as an unordered set. Iterating the declared priority answers with the
        same family every time; ITEM_FAMILY_PRIORITY documents why that order
        is the one it is.

    Notes/References:
        A family with no mesh client-side falls through to a generic one, so
        adding a family to ITEM_FAMILIES ahead of its art is harmless.

        Lived in inventory.py until the world pane started resolving its
        entities through the same mesh resolver as the inventory pane. It sits
        beside _classify now because the two answer halves of one question --
        which mesh, and which mesh if that one does not exist -- and inventory.py
        imports it the way it already imports _classify.

    Author: Nick Hobar
    Creation date: 08/15/2026
    """
    tag_handler = getattr(item, "tags", None)

    if tag_handler is None:
        return const.ITEM_FAMILY_GENERIC

    tagged = tag_handler.all(return_key_and_category=True)
    categories = {category for _tag_key, category in tagged}

    for family in const.ITEM_FAMILY_PRIORITY:
        if family in categories:
            return str(family)

    return const.ITEM_FAMILY_GENERIC


def _mesh_family(entity, kind: str) -> str:
    """
    Purpose: Name the fallback mesh key for anything the feed can describe.

    Entry:
        entity - a live object.
        kind   - the entity's ASSET_KIND_*, as decided by _classify.

    Exit/Returns:
        Returns the item's family for an item, and the kind itself for
        everything else. Never "".

    Module Globals:
        const.ASSET_KIND_ITEM read.

    Methodology:
        ONE field, not two, and the reason is what happens on the client. The
        resolver takes an asset key and a fallback key; giving it a `family`
        for items and expecting it to reach for `kind` otherwise puts the
        precedence rule in the renderer, where it would have to be repeated in
        every client that ever connects. The server decides, exactly as it
        already decides the interact verb.

        The two vocabularies do not collide -- weapon, armor, jewellery,
        crafting_material, crafting_tool and currency against npc, character,
        station and gatherable -- so one namespace holds both.

    Notes/References:
        A spear on the floor and the same spear in a bag therefore report the
        same family and draw the same mesh, which is the whole point of the
        resolver being shared.

    Author: Nick Hobar
    Creation date: 08/17/2026
    """
    if kind != const.ASSET_KIND_ITEM:
        return kind

    family = _item_family(entity)

    return family


# ─── Public routines ─────────────────────────────────────────────────────────

def interact_command(entity, kind: str) -> str:
    """
    Purpose: Name the command a client should send to act on this entity.

    Entry:
        entity - a live object.
        kind   - the entity's ASSET_KIND_*, as decided by _classify.

    Exit/Returns:
        Returns a complete command string ("craft", "attack mutant raider"), or
        "" when the entity affords nothing.

    Module Globals:
        const.TARGETED_VERB_BY_KIND read.

    Methodology:
        The SERVER names the verb, not the renderer. That is the standing
        instruction from the gathering-node fix: a client that keeps its own
        kind-to-verb table has to be edited every time the game grows a new
        kind of thing, and until it is edited it offers the wrong interaction
        confidently. The Foundry Furnace is what that looks like in practice --
        it was offered as `get Foundry Furnace`, and it worked.

        Two sources, in order:

        1. `interact_verb` declared on the typeclass. A verb declared there
           means the object carries its OWN cmdset -- CraftingFacility has
           `craft`, BankNode has `bank`, TalkativeNPC has `talk` -- and such a
           command takes no target, because the object the cmdset hangs on is
           already the target.
        2. Otherwise TARGETED_VERB_BY_KIND, whose commands live on the
           CHARACTER and therefore need the entity named.

        Read with getattr rather than through an import, so this module stays
        out of the typeclass layer. A class attribute rather than a db
        attribute is deliberate too: the verb is a fact about the typeclass,
        not about the instance, so every furnace already in the database gains
        it without being respawned or migrated.

    Notes/References:
        The returned string is exactly what a telnet player would type. A
        graphical client sending it can therefore do nothing a text player
        cannot, which is what keeps every lock and cooldown honest.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    own_verb = getattr(entity, "interact_verb", "")

    if own_verb:
        return str(own_verb)

    targeted_verb = const.TARGETED_VERB_BY_KIND.get(kind, "")

    if not targeted_verb:
        return ""

    return targeted_verb + " " + str(entity.key)


def serialize_entity(entity, coords=()) -> dict:
    """
    Purpose: Render one visible entity as a plain dict for a graphical client.

    Entry:
        entity - a live, non-deleted object.
        coords - the [x, y, z] of the room it is standing in, or () when the
                 caller has not resolved one.

    Exit/Returns:
        Returns a dict of JSON-safe primitives. Always carries id, name, kind,
        asset, family, interact and coords -- `interact` being "" for anything
        that affords nothing, which a client reads as "not clickable". Carries
        hp / max_hp only when the entity actually has them, so a client can
        tell "full health" from "not a combatant" -- an item reported at 0/0
        would render a health bar on a rock.

        `coords` became load-bearing when STATEFEED_ENTITY_RADIUS stopped
        being 0: once the feed reports entities the observer is not standing
        with, a client has no way to place them without being told where they
        are, and would stack the whole neighbourhood onto the player's tile.

        `asset` and `family` are the two tiers of one lookup, the same pair
        CharItemsPayload sends: the client draws a model for the asset key if
        it has one, and the family's generic mesh if it does not.

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
    family = _mesh_family(entity, kind)
    body = {
        "id": entity.id,
        "name": str(entity.key),
        "kind": kind,
        "asset": asset_key,
        "family": family,
        "interact": interact_command(entity, kind),
        "coords": list(coords),
    }

    max_hp = getattr(entity, "max_hp", None)

    if max_hp:
        body["hp"] = getattr(entity, "hp", 0)
        body["max_hp"] = max_hp

    return body


def serialize_area(rooms, exclude=()) -> list:
    """
    Purpose: Render everything visible across a group of rooms.

    Entry:
        rooms   - room objects, typically from targeting.rooms_within_radius.
        exclude - objects to leave out (typically the observer themself).

    Exit/Returns:
        Returns a flat list of entity dicts, each carrying the coords of the
        room it is standing in. Empty list when `rooms` is empty.

    Module Globals:
        None.

    Methodology:
        ONE database query for the contents of every room, not one per room.
        A radius of 3 is 49 rooms and a radius of 10 is 441; asking each of
        them for `.contents` in turn is the shape of query storm that
        targeting.rooms_within_radius went out of its way to avoid on the room
        lookup itself, and it would be undone here.

        Exits are skipped for the same reason serialize_contents skips them:
        an exit is a real object sitting in room.contents, but it is topology
        rather than an occupant.

        Coordinates are resolved per ROOM and shared by everything standing in
        it, rather than read per entity. An entity's own location lookup would
        be a query each, which is the storm again by another route.

    Notes/References:
        A room that is off-grid contributes an empty coords list, which is the
        same thing room_coords returns and which a client already has to
        handle for its own room.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    from evennia.objects.models import ObjectDB

    coords_by_room = {}

    for room in rooms:
        coords_by_room[room.id] = room_coords(room)

    if not coords_by_room:
        return []

    contents = ObjectDB.objects.filter(db_location__id__in=list(coords_by_room))
    entities = []

    for obj in contents:
        if obj in exclude:
            continue

        if obj.destination is not None:
            continue

        coords = coords_by_room.get(obj.location.id, [])
        entry = serialize_entity(obj, coords=coords)
        entities.append(entry)

    return entities


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
        Single-room rendering. serialize_area is what the radius-aware feed
        calls; this one remains for the callers that genuinely mean one room,
        and it stamps that room's coords so both produce the same entity shape.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """
    if room is None:
        return []

    coords = room_coords(room)
    entities = []

    for obj in room.contents:
        if obj in exclude:
            continue

        if obj.destination is not None:
            continue

        entry = serialize_entity(obj, coords=coords)
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


def tile_key(x: int, y: int) -> str:
    """
    Purpose: Render a tile's coordinate pair as the key a client looks it up by.

    Entry:
        x, y - grid coordinates on one map. The map name (z) is NOT part of the
        key: a tile-action map is always about one map, and the caller knows
        which.

    Exit/Returns:
        The key string, e.g. "6:3".

    Module Globals:
        const.TILE_KEY_TEMPLATE read.

    Methodology:
        One template, one owner. The client used to build this string itself in
        two places and the map's own node lookup built it in a third.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/23/2026
    """
    return const.TILE_KEY_TEMPLATE.format(x=x, y=y)


def tile_action(command: str, kind: str) -> dict:
    """
    Purpose: Build one tile affordance.

    Entry:
        command - the whole command to send, with nothing left to substitute.
        kind    - one of the const.TILE_ACTION_KIND_* values.

    Exit/Returns:
        Returns {"command": str, "kind": str}.

    Module Globals:
        None.

    Methodology:
        A named constructor rather than a dict literal at each call site, so
        the payload's shape has one definition and the two keys cannot be
        spelled differently in two places.

    Notes/References:
        `kind` exists because the client tracks the walk IT started -- see
        runAction in blackout3d.js. The client needs to know whether a command
        begins a walk, ends one, or leaves it alone; it should not have to
        infer that from the command's text.

    Author: Nick Hobar
    Creation date: 08/23/2026
    """
    return {"command": command, "kind": kind}


def goto_action(x: int, y: int) -> dict:
    """
    Purpose: The pathfinder walk to one tile.

    Entry:
        x, y - grid coordinates on the observer's own map.

    Exit/Returns:
        Returns a tile action whose command is `goto (X,Y)`.

    Module Globals:
        const.TILE_COMMAND_GOTO_TEMPLATE read.

    Methodology:
        The command is spelled out in full here so no client has to know the
        coordinate syntax. It is a property of the NODE rather than of the
        observer -- the walk to (6,3) is `goto (6,3)` from anywhere on the map
        -- which is why mapexport stamps it on the map node once per session
        rather than emit_room_info resending it per move.

    Notes/References:
        Everything about the walk then belongs to the server: Dijkstra over the
        contrib's baked path matrix, `interrupt_path` nodes that stop it, and a
        re-path when the player walks off-route by hand.

    Author: Nick Hobar
    Creation date: 08/23/2026
    """
    command = const.TILE_COMMAND_GOTO_TEMPLATE.format(x=x, y=y)

    return tile_action(command, const.TILE_ACTION_KIND_WALK)


def cancel_action() -> dict:
    """
    Purpose: The command that aborts a walk in progress.

    Entry:
        None.

    Exit/Returns:
        Returns a tile action carrying bare `goto`.

    Module Globals:
        const.TILE_COMMAND_GOTO read.

    Methodology:
        Sent alongside the tile actions rather than inside them, because it is
        not a property of any tile: it is what clicking the tile you are
        STANDING ON means while a walk is running, and whether one is running
        is the client's own tracking.

    Notes/References:
        Bare `goto` is the contrib's own abort. See commands/movement_cmds.py.

    Author: Nick Hobar
    Creation date: 08/23/2026
    """
    return tile_action(const.TILE_COMMAND_GOTO, const.TILE_ACTION_KIND_CANCEL)


def tile_actions(room) -> dict:
    """
    Purpose: What the tiles NEAR the observer afford, from where they stand.

    Entry:
        room - the observer's current room, or None.

    Exit/Returns:
        Returns {tile_key: {"command", "kind"}} covering the room the observer
        is in and every tile one real exit away. Empty for a room with no
        coordinates.

    Module Globals:
        const read.

    Methodology:
        NEAR tiles only, and that split is the whole reason this stays small.
        A tile further off affords the same `goto (X,Y)` no matter where the
        observer stands, so mapexport stamps that on the map node once per
        session; only the immediate exits change as the player moves, and there
        are at most eight of them. Sending every reachable tile from here would
        make room_info ~3KB on EVERY room change, on a channel that fires once
        per move, to say something that had not changed.

        Directions come from the room's real spawned EXITS, not from a
        grid-delta table. The exit already knows both its own name ("north",
        which is what a telnet player types) and its destination, and the
        destination knows its coordinates -- so the mapping is read off the
        world rather than derived from one. That is what makes a one-way exit,
        a diagonal link, or a map whose geometry does not match its directions
        come out right without a special case.

        An exit whose destination has no coordinates is skipped rather than
        guessed at; that is a room off the grid, which no tile can represent.

    Notes/References:
        A cardinal neighbour with NO exit simply has no entry here, and picks
        up the map node's `goto` instead -- which is the correction to the
        client rule this replaces. The client refused those outright, treating
        every unlinked neighbour as a wall; most maps are drawn with cardinal
        links only, so the diagonal neighbours around a player are ordinarily
        two steps away rather than walls.

    Author: Nick Hobar
    Creation date: 08/23/2026
    """
    here = room_coords(room)

    if not here:
        return {}

    actions = {
        tile_key(here[0], here[1]): tile_action(
            const.TILE_COMMAND_LOOK, const.TILE_ACTION_KIND_LOOK),
    }

    for exit_obj in room.exits:
        destination = exit_obj.destination

        if destination is None:
            continue

        there = room_coords(destination)

        if not there:
            continue

        key = tile_key(there[0], there[1])

        # The observer's own tile is already claimed by `look`, and an exit
        # looping back to its own room must not overwrite it.
        if key in actions:
            continue

        actions[key] = tile_action(
            str(exit_obj.key), const.TILE_ACTION_KIND_STEP)

    # A cardinal neighbour no exit reached is a wall. Say so, rather than
    # leaving it out: omission means "fall through to the node's own `goto`",
    # and the pathfinder would route the player the long way around a barrier
    # they can see. Diagonals are deliberately not checked -- see
    # const.TILE_ACTION_KIND_NONE for why those two cases differ.
    #
    # A cardinal offset that is not on the map at all also lands here, and that
    # is harmless: the client never draws a tile the map did not send, so the
    # entry is four bytes nobody reads. Checking would mean giving this routine
    # the parsed map for no gain.
    for offset_x, offset_y in const.TILE_CARDINAL_OFFSETS:
        key = tile_key(here[0] + offset_x, here[1] + offset_y)

        if key not in actions:
            actions[key] = tile_action("", const.TILE_ACTION_KIND_NONE)

    return actions
