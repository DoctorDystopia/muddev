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

from dataclasses import dataclass, field, fields

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
        """
        Purpose: Return this payload as plain JSON-safe values.

        Entry:
            The subclass must be a dataclass whose every field already holds a
            JSON-safe value -- which the module docstring above requires of
            every payload, and which serializers.py is what guarantees.

        Exit/Returns:
            Returns a new dict of {field name: value}. The dict is new; the
            VALUES are the payload's own objects, not copies.

        Module Globals:
            None.

        Methodology:
            A shallow walk over `fields(self)`, not `dataclasses.asdict`.

            asdict recurses into every nested list and dict and deep-copies as
            it goes. That recursion buys nothing here: the module docstring
            already forbids a payload from holding anything but JSON-safe
            values, so there are no nested dataclasses to convert -- and the
            copy is charged per element on the largest payloads the feed sends.
            Measured with systems/profiling (scripts/profile_pipeline.py
            --layer statefeed):

                                          asdict        shallow walk
                MapChunkPayload   3.343 ms / 35,229    0.001 ms / 17
                  (1,600 nodes + 1,600 links)
                CharItemsPayload  0.097 ms /  1,170    0.001 ms / 17
                  (60 rows)

            The call count is the tell: 17 regardless of payload size, because
            nothing here walks into a value.

            The aliasing that a shallow copy allows is safe here because
            to_dict has exactly one production caller -- emit.py, which hands
            the body straight to msg() to be encoded and then drops it. Nothing
            mutates the returned dict, and a payload is built fresh per emit
            rather than shared.

        Notes/References:
            If a payload ever does need to hold a nested dataclass, this is the
            routine that has to learn about it -- and the module docstring's
            rule is what should stop that happening.

        Author: Nick Hobar
        Creation date: 08/07/2026
        """
        body = {}

        for entry in fields(self):
            body[entry.name] = getattr(self, entry.name)

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

    # What the tiles NEAR the observer afford: {"x:y": {command, kind}}.
    #
    # Near only -- the observer's own tile and everything one real exit away,
    # at most nine entries. A tile further off affords the same `goto (X,Y)`
    # wherever the observer stands, so that is stamped on the MAP NODE once per
    # session (see mapexport) rather than resent here on every move.
    #
    # `exits` above is kept and is not redundant with this. It is the GMCP
    # Room.Info field as IRE and Aardwolf define it, keyed by direction and
    # carrying destination ids, which is what a text client wants; this is
    # keyed by tile and carries commands, which is what a graphical one wants.
    tile_actions: dict = field(default_factory=dict)

    # What clicking the tile you are standing on means while a walk is running.
    # Not part of tile_actions because whether a walk IS running is the
    # client's own tracking; see serializers.cancel_action.
    cancel_action: dict = field(default_factory=dict)


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
class CharAvatarPayload(_Payload):
    """Who the observer IS, as the renderer needs to know it. Char.Avatar.

    The one thing a graphical client cannot work out for itself. Every other
    entity it draws arrives on room_players carrying `asset` and `family`, but
    emit_room_contents excludes the observer from their own list -- so the
    client knows where to put the camera and nothing at all about what to draw
    there. This channel closes exactly that gap and nothing else.

    `asset` and `family` are the same two tiers, spelled the same way, that
    every entity dict carries, so a client resolves its own mesh through the
    identical lookup it already runs for an NPC. `entity_id` is what makes a
    combat event recognisable as being about YOU: CombatPayload names an
    attacker and a target by id, and a client with no id of its own can only
    guess by name.

    DELIBERATELY THREE FIELDS. serialize_entity also reports name, coords, hp
    and max_hp -- all of which are already on char_vitals or room_info for this
    observer. Repeating them here would be a second source for a fact that
    changes on a different schedule, which is the drift char_items_list is
    written to avoid.
    """

    channel = const.CHANNEL_CHAR_AVATAR

    entity_id: int = 0
    asset: str = ""
    family: str = ""


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
class CharSkillsPayload(_Payload):
    """Every skill the observer has, and what each one opens. Char.Skills.

    A SNAPSHOT of the whole roster rather than one message per skill. The
    roster is small and fixed by SKILL_REGISTRY, and a skills SCREEN wants all
    of it at once -- a client assembling a grid from eight arriving messages
    would have to decide when it had them all.

    `skills` is a LIST, not a dict keyed by skill key, and that is the whole
    reason a client needs no ordering table. A dict would leave the client to
    decide what comes first, and the only honest answer to that lives in the
    registry -- so the order ships, and `categories` ships beside it so a grid
    can be grouped without the client inventing category order either.

    THE PAYLOAD IS PER-SKILL COMPLETE. Each row carries its level, its XP
    curve, its description and its unlock ladder, so clicking a skill costs no
    round trip. `current_xp` / `needed_xp` are progress INTO the level and that
    level's own threshold; `total_xp` is cumulative. Both ship under names that
    say which they are, because deriving one from the other is exactly the
    mistake that once rendered a "1154 / 152" bar.

    `command` on each row is the line a telnet player would type to read that
    skill's sheet. The server names it for the reason serialize_entity names
    `interact`: a client that composed it would be spelling a command, and a
    client verb table has been deleted twice here for being wrong within a
    week.

    `closest` is the one fact no single skill can produce -- it is a comparison
    across the roster -- and it is `{}` rather than absent when every skill
    sits at the cap, which is a real state and not an error.
    """

    channel = const.CHANNEL_CHAR_SKILLS

    skills: list = field(default_factory=list)      # [{key, name, level, ...}]
    categories: list = field(default_factory=list)  # category names, in order
    total_level: int = 0
    total_xp: int = 0
    max_level: int = 0
    closest: dict = field(default_factory=dict)


@dataclass
class CharItemsPayload(_Payload):
    """The whole carried inventory and every equipment slot. Char.Items.List.

    A SNAPSHOT, deliberately, where RoomPlayersPayload is the list half of a
    list-then-delta pair. The reasoning is inverted from that channel's and is
    worth stating, because "be consistent with room_players" is the obvious
    wrong answer here.

    room_players uses deltas because with a radius of 10 the full list is large
    and the mutation points are few and disciplined: an entity enters a room or
    leaves it. The inventory is the other way round on both counts. The full
    list is 32 slots plus 11 equipment slots -- a couple of kilobytes, well
    inside the 65535-byte inbound buffer that forces MapChunkPayload to chunk --
    while the mutation points are many and undisciplined. InventoryHandler
    .add_item merges stacks with a bare `existing.quantity += additional` and
    fires no hook at all; crafting consumes materials directly; banking moves
    items in bulk; equipping displaces items back into the grid. A delta
    protocol would need an emit at every one of those and would rot silently at
    the first one anybody forgot.

    A missed delta on an NPC three tiles away is a cosmetic ghost. A missed
    delta on the player's own inventory is a phantom item they will try to
    click. Sending the whole grid is cheap and cannot desync.

    `items` and `equipped` ship together rather than as two messages because
    equipping is a single transaction that changes both, and two messages could
    be rendered half-applied.

    `equip_slots` is the EMPTY FRAME list -- every wield location in display
    order, whether or not something is in it. It ships because the alternative
    is a client-side table restating SLOT_DISPLAY_ORDER, which is the exact
    shape of duplication that made the client's old verb table wrong within a
    week. Adding a slot to WieldLocation should light up a new frame in the 3D
    pane with no client edit at all.
    """

    channel = const.CHANNEL_CHAR_ITEMS

    slots_total: int = 0
    slots_used: int = 0
    items: list = field(default_factory=list)        # the carried grid
    equipped: list = field(default_factory=list)     # what is worn
    equip_slots: list = field(default_factory=list)  # every frame to draw


@dataclass
class CharQuestsPayload(_Payload):
    """The observer's quest log. Char.Quests.

    A SNAPSHOT, for the reason CharItemsPayload gives at length: the mutation
    points are many -- accepting, every `notify_quests` fan-out, a step
    completing, a forced jump from the moderator tool -- and a delta protocol
    would rot at the first one anybody forgot. It is also small: a handful of
    quests with a handful of objectives each.

    `active` rows carry the CURRENT step only. A client showing the steps
    already finished would be showing a history the handler does not keep, and
    one showing the steps ahead would be spoiling the quest.

    OBJECTIVES ARE STRUCTURED. Each is `{key, description, current, required,
    counted, done}`. `required` is 1 for a one-shot objective rather than
    absent, so a client can draw the same progress bar for both without a
    branch; `counted` is what says whether to render "3/5" or a tickbox. The
    prose form lives in QuestHandler.objective_lines and stays there -- it is
    what the telnet screen prints.
    """

    channel = const.CHANNEL_CHAR_QUESTS

    active: list = field(default_factory=list)     # [{key, title, step, ...}]
    completed: list = field(default_factory=list)  # [{key, title}, ...]


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
