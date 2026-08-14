"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/07/2026
Description: One dataclass per state-feed channel.

             These exist so the feed can be tested without a socket, a Portal,
             or an AMP connection: a test asserts on the payload a game event
             produces, not on bytes arriving somewhere. That is also why every
             payload is a plain data carrier with no behaviour beyond
             serialisation.

             Every field must survive json.dumps. No Evennia objects, no
             SaverDict / SaverList, no Decimals -- Evennia's clean_senddata
             would stringify a DB object and the Godot contrib README calls out
             SaverDict as an outright serialisation failure. serializers.py is
             what turns live objects into the plain values these hold.
"""

from dataclasses import asdict, dataclass, field

from . import constants as const


# ─── Private helper routines ─────────────────────────────────────────────────

class _Payload:
    """
    Purpose: Shared serialisation for every channel payload.

    Entry:
        Subclasses must be dataclasses and must set `channel` to one of the
        constants.CHANNEL_* values.

    Exit/Returns:
        Not applicable — a base class.

    Module Globals:
        None.

    Methodology:
        `channel` is a plain class attribute rather than a dataclass field so
        it never appears in the serialised body. The client already knows the
        channel from the outputfunc name; repeating it inside the payload
        would be a second source of truth for the same fact.

    Notes/References:
        style.md section 7 -- private symbols carry a leading underscore.

    Author: Nick Hobar
    Creation date: 08/07/2026
    """

    channel: str = ""

    def to_dict(self) -> dict:
        """Return this payload as plain JSON-safe values."""
        body = asdict(self)

        return body


# ─── Public routines / Classes ───────────────────────────────────────────────

@dataclass
class RoomInfoPayload(_Payload):
    """The observer's current room. GMCP Room.Info.

    `room_kind` is the room prototype's key ("Bank", "Foundry Furnace
    Facility"). Phase 2 uses it to tint a box; it is also the lookup key a
    modular kit-room renderer will use to pick a prefab later, which is why it
    is named for what it means rather than for what it currently does.
    """

    channel = const.CHANNEL_ROOM_INFO

    num: int = 0
    name: str = ""
    room_kind: str = const.ROOM_KIND_DEFAULT
    coords: list = field(default_factory=list)   # [x, y, z] -- z is a map NAME
    exits: dict = field(default_factory=dict)    # {direction: destination_num}


@dataclass
class RoomPlayersPayload(_Payload):
    """Everything visible in the observer's room. GMCP Room.Players.

    The full list. Sent on arrival and on resync; the add/remove channels carry
    the deltas in between, which is the list-then-delta pattern both Aardwolf
    and the IRE games use throughout their GMCP surface.
    """

    channel = const.CHANNEL_ROOM_PLAYERS

    entities: list = field(default_factory=list)


@dataclass
class RoomPlayerAddPayload(_Payload):
    """One entity appeared in the observer's room. GMCP Room.AddPlayer."""

    channel = const.CHANNEL_ROOM_PLAYER_ADD

    entity: dict = field(default_factory=dict)


@dataclass
class RoomPlayerRemovePayload(_Payload):
    """One entity left the observer's room. GMCP Room.RemovePlayer.

    Carries the id rather than the whole entity: this also fires for an NPC
    that died, and by then the object may already be deleted.
    """

    channel = const.CHANNEL_ROOM_PLAYER_REMOVE

    entity_id: int = 0


@dataclass
class CharVitalsPayload(_Payload):
    """The observer's own health. GMCP Char.Vitals."""

    channel = const.CHANNEL_CHAR_VITALS

    hp: int = 0
    max_hp: int = 0


@dataclass
class CharStatusPayload(_Payload):
    """The observer's own non-vital state. GMCP Char.Status."""

    channel = const.CHANNEL_CHAR_STATUS

    in_combat: bool = False
    levels: dict = field(default_factory=dict)


@dataclass
class CharSummaryPayload(_Payload):
    """The observer's whole dossier, panel by panel. Char.Summary.

    `panels` is an open dict keyed by panel key -- {"vitals": {...},
    "skills": {...}} -- rather than a field per panel. That is deliberate: the
    summary screen's whole design contract is that adding a band is ONE new
    file under systems/summary/panel_defs/, and a dataclass field per panel
    would make it two, with this module the one nobody remembers to edit.

    The cost is that a client cannot rely on any given key being present. That
    is the correct trade here anyway, since a panel legitimately reports nothing
    when the system behind it has nothing to say.
    """

    channel = const.CHANNEL_CHAR_SUMMARY

    panels: dict = field(default_factory=dict)


@dataclass
class MapChunkPayload(_Payload):
    """One slice of a Z-level's grid. Blackout.Map.

    Chunked because Godot's WebSocketPeer defaults to a 65535-byte inbound
    buffer and historically truncated oversized JSON silently. A client
    reassembles by collecting `chunk_count` chunks for a given `z`.

    Nodes carry world coordinates, not xygrid coordinates. The xygrid puts a
    world node at (2X, 2Y) with link glyphs on the odd cells; that transform is
    the map layer's business and must not leak to a client.
    """

    channel = const.CHANNEL_MAP

    z: str = ""
    chunk_index: int = 0
    chunk_count: int = 1
    nodes: list = field(default_factory=list)   # [{x, y, room_kind}, ...]
    links: list = field(default_factory=list)   # [{from: [x,y], to: [x,y]}, ...]


@dataclass
class CombatPayload(_Payload):
    """One resolved swing. Blackout.Combat.

    Fields mirror ActionResult (systems/combat/rules/context.py) so the feed
    and the prose in combat_msg cannot drift: both are built from the same
    result object in the same function.

    `hp_after` is arithmetic on the PRE-damage total, not a re-read of the
    target -- the same reason _land_hit builds its HP bar that way. The event
    is emitted before at_damage runs, because a killed NPC deletes itself
    inside at_damage and a client resolving `target_id` afterwards would find
    nothing.
    """

    channel = const.CHANNEL_COMBAT

    attacker_id: int = 0
    attacker_name: str = ""
    target_id: int = 0
    target_name: str = ""
    hit: bool = False
    damage: int = 0
    damage_type: str = ""
    attack_type: str = ""
    style: str = ""
    hp_after: int = 0
    max_hp: int = 0
    killed: bool = False
    backfire: bool = False


@dataclass
class AuraPayload(_Payload):
    """An aura activating, deactivating, or pulsing. Blackout.Aura.

    `tiles` is the pulse footprint in world coordinates. This is the only
    mechanic in the game whose effect covers more than one room, and the only
    channel that legitimately names tiles the observer is not standing on --
    the text channel already tells them their aura is burning those tiles, via
    the tinted map overlay in typeclasses/rooms.py.
    """

    channel = const.CHANNEL_AURA

    event: str = ""          # activate | deactivate | pulse
    aura_key: str = ""
    radius: int = 0
    tiles: list = field(default_factory=list)   # [[x, y], ...]
    damage: int = 0
