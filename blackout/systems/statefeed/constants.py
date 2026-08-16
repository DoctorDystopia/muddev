"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/07/2026
Description: Tunables and channel names for the structured state feed.

             Channel names follow the GMCP vocabulary on purpose. Evennia's OOB
             layer maps an outputfunc named `foo_bar` to GMCP `Foo.Bar` on
             telnet and `FOO_BAR` on MSDP, while the websocket protocol passes
             it through as raw JSON. Naming channels the way Achaea/IRE and
             Aardwolf already name them therefore buys Mudlet / MUSHclient /
             TinTin++ support for the same data, from one implementation, at no
             cost. Game-specific channels with no GMCP standard equivalent are
             namespaced under `blackout_` (-> `Blackout.*`), which is the
             mudstandards convention for vendor extensions.
"""


# ─── Channel names (outputfunc names) ────────────────────────────────────────

# Standard GMCP vocabulary. These have equivalents in published MUD specs.
CHANNEL_ROOM_INFO: str = "room_info"                  # -> Room.Info
CHANNEL_ROOM_PLAYERS: str = "room_players"            # -> Room.Players
CHANNEL_ROOM_PLAYER_ADD: str = "room_add_player"      # -> Room.AddPlayer
CHANNEL_ROOM_PLAYER_REMOVE: str = "room_remove_player"  # -> Room.RemovePlayer
CHANNEL_CHAR_VITALS: str = "char_vitals"              # -> Char.Vitals
CHANNEL_CHAR_STATUS: str = "char_status"              # -> Char.Status

# The whole player summary screen, panel by panel. GMCP has no standard name
# for this; Char.Summary follows the vocabulary of the two above rather than
# being namespaced under blackout_, because "everything about my character" is
# exactly what a Char.* channel is for and a client that understands
# Char.Vitals will look for it there.
CHANNEL_CHAR_SUMMARY: str = "char_summary"            # -> Char.Summary

# The carried inventory grid and the equipment slots, together, as one
# snapshot. IRE's published name for this is Char.Items.List, and Evennia's
# GMCP encoder turns `char_items_list` into exactly that (it capitalises each
# underscore-separated part), so a Mudlet user gets a channel their client
# already understands.
#
# This is the one place the repo's "say inventory, never bag/items" rule loses,
# and it loses only on the WIRE name. Everything Blackout owns inside the
# payload says inventory -- see ITEM_LOCATION_INVENTORY below.
CHANNEL_CHAR_ITEMS: str = "char_items_list"           # -> Char.Items.List

# Blackout-specific extensions.
CHANNEL_MAP: str = "blackout_map"          # -> Blackout.Map
CHANNEL_COMBAT: str = "blackout_combat"    # -> Blackout.Combat
CHANNEL_AURA: str = "blackout_aura"        # -> Blackout.Aura

# Every channel a client may subscribe to. A name absent from here is rejected
# by the subscribe inputfunc rather than silently accepted, so a typo in a
# client shows up immediately instead of as a channel that never fires.
SUBSCRIBABLE_CHANNELS: frozenset = frozenset((
    CHANNEL_ROOM_INFO,
    CHANNEL_ROOM_PLAYERS,
    CHANNEL_ROOM_PLAYER_ADD,
    CHANNEL_ROOM_PLAYER_REMOVE,
    CHANNEL_CHAR_VITALS,
    CHANNEL_CHAR_STATUS,
    CHANNEL_CHAR_SUMMARY,
    CHANNEL_CHAR_ITEMS,
    CHANNEL_MAP,
    CHANNEL_COMBAT,
    CHANNEL_AURA,
))

# Evennia's websocket `send_default` silently DROPS an outputfunc with this
# name, and `clean_senddata` injects a key of the same name into every
# outputfunc's kwargs. Named here so the guard in emit.py is not a bare string.
RESERVED_CHANNEL_NAME: str = "options"


# ─── Subscription ────────────────────────────────────────────────────────────

# The ndb attribute on a Session holding its subscribed channel set. ndb, not
# db: a subscription is meaningless across a disconnect, and Session ndb is
# wiped by a server reload anyway -- which is precisely why the client
# re-subscribes on reconnect and why at_sync pushes a resync.
SUBSCRIPTION_ATTR: str = "statefeed_channels"

# Sent by the subscribe inputfunc to mean "every channel". Spelling this as a
# constant keeps the client-facing wire vocabulary in one place.
SUBSCRIBE_ALL: str = "all"

# The outputfunc carrying the answer to "what am I subscribed to". Not in
# SUBSCRIBABLE_CHANNELS on purpose: a client cannot subscribe to it, it is
# always sent, and it is the one channel name a client must know before the
# server has told it anything.
#
# An EMPTY set on this channel is a real answer meaning "I have forgotten you,
# ask again". at_sync sends exactly that, which is what lets a client survive
# both a reload (ndb wiped) and a subscribe that raced the Portal-to-Server
# sync and was dropped.
CHANNEL_SUBSCRIBED_ACK: str = "blackout_subscribed"


# ─── Visibility ──────────────────────────────────────────────────────────────

# How many tiles beyond the observer's own room may have their CONTENTS fed to
# a client. Zero means the feed shows exactly what the text channel shows.
#
# This is a BALANCE knob, not a rendering one: above zero, a graphical client
# is told about NPCs through walls that a telnet player would have to walk to.
# It is read in exactly one place -- events._visible_rooms -- so the contents
# list and the add/remove deltas can never be widened out of step with each
# other.
#
# COST. It is (2r+1)^2 rooms per contents emit: 9 at r=1, 49 at r=3, 441 at
# r=10, which on Blackout's ~95-node maps is the entire map. The room lookup
# and the contents lookup are one query each regardless of r, so the cost is
# in the SIZE of the message rather than the number of queries -- but a
# message naming every entity on the map, rebuilt on every room change, is
# still the wrong shape. Keep this small; 2-3 tiles is a diorama, 10 is a
# broadcast.
#
# Zero is not a dead setting: rooms_within_radius short-circuits to [origin]
# without a query, so setting it back costs nothing and restores exactly the
# text channel's visibility.
STATEFEED_ENTITY_RADIUS: int = 10


# ─── Rate limiting ───────────────────────────────────────────────────────────

# Minimum seconds between two sends on the same channel to the same session.
# Aardwolf hard-caps its group channel at one send per second for exactly this
# reason.
#
# ONLY cap channels that report a CONTINUOUS VALUE, where a dropped message is
# superseded by the next one and costs the client nothing but latency. Vitals
# and status qualify: miss an HP reading and the following one still tells the
# whole truth.
#
# Never cap a channel that reports a STATE TRANSITION. Those do not supersede
# one another -- dropping one leaves the client permanently wrong, with nothing
# scheduled that would correct it:
#
#   - CHANNEL_ROOM_PLAYERS was capped at 1.0s here and it was a bug. Walking
#     two rooms inside a second published the second room_info with no matching
#     contents, so the client kept rendering the previous room's occupants
#     until the player happened to move again slowly enough.
#   - CHANNEL_COMBAT is uncapped for the same reason. At a 0.6s tick and a
#     4-tick weapon cycle it is self-limiting anyway, and dropping a swing
#     would desync the HP readout from the text log.
#   - CHANNEL_CHAR_SUMMARY is uncapped despite carrying continuous values,
#     because it is REQUEST-DRIVEN rather than event-driven: it fires when the
#     player opens their dossier and on resync, nowhere else. Nothing is
#     scheduled behind a dropped one, so a cap here would mean a player pressing
#     `score` twice in a second and getting no answer the second time.
#   - CHANNEL_CHAR_ITEMS is uncapped, and this is the one most likely to be
#     "fixed" by someone reading only the first paragraph. It LOOKS like a
#     continuous value -- a whole-grid snapshot, each superseding the last --
#     but nothing is scheduled behind a dropped one. Pick an item up, lose that
#     send to a cap, and the pane shows a grid missing the item until the
#     player happens to act again. That is the room_players bug exactly.
#
#     It is self-limiting anyway: sends are driven by discrete player actions
#     bounded by the 0.6s tick. If a gathering loop ever does make it chatty,
#     the fix is a COALESCING cap -- schedule a trailing send -- not a dropping
#     one. emit.py has no such mechanism today, and adding one is a bigger
#     change than the entry in this dict would suggest.
CHANNEL_MIN_INTERVAL_SECONDS: dict = {
    CHANNEL_CHAR_VITALS: 0.5,
    CHANNEL_CHAR_STATUS: 1.0,
}

# Fallback when a channel has no entry above.
DEFAULT_MIN_INTERVAL_SECONDS: float = 0.0

# The ndb attribute holding {channel: last_send_monotonic} per session.
RATE_STATE_ATTR: str = "statefeed_last_send"


# ─── Payload sizing ──────────────────────────────────────────────────────────

# Map nodes per `blackout_map` message. Godot's WebSocketPeer defaults to a
# 65535-byte inbound buffer and historically TRUNCATED oversized JSON silently
# rather than erroring (fixed for Godot >= 4.4). A full Blackout map is ~95
# nodes and would fit in one frame today, but chunking now costs nothing and
# removes a failure mode that only appears once a map grows.
MAP_NODES_PER_CHUNK: int = 40


# ─── Asset keys ──────────────────────────────────────────────────────────────

# What a client renders when it has no asset for an entity's key. The server
# always names an asset; the client always has a fallback. This pair is what
# stops a graphical client from blocking content work -- a new item added to
# ITEM_DB renders as a generic mesh with its real name, immediately, with no
# art request.
ASSET_KIND_ITEM: str = "item"
ASSET_KIND_NPC: str = "npc"
ASSET_KIND_CHARACTER: str = "character"
ASSET_KIND_ROOM: str = "room"

# A fixed installation you use where it stands: a crafting facility, a bank
# terminal. Distinct from an item for the same reason a gathering node is --
# it carries `get:false()`, and a client told "item" offers to pocket the one
# thing that cannot be pocketed. That is not hypothetical: the Foundry Furnace
# fell through to "item", the 3D pane offered `get Foundry Furnace`, and a
# superuser test account was allowed to walk off with the furnace.
ASSET_KIND_STATION: str = "station"

# A gathering node. Distinct from an item because the two afford opposite
# things: an item is picked up, a node is harvested where it stands and carries
# `get:false()` precisely so it cannot be pocketed. A client told only "item"
# offers the one interaction the object refuses.
ASSET_KIND_GATHERABLE: str = "gatherable"

ASSET_KEY_GENERIC: str = "generic"

# The command a client sends to act on an entity, when there is one.
#
# These two are the CHARACTER's commands, so they need a target appended:
# `attack mutant raider`, `get rusty scrap spear`. Everything else that affords
# anything carries its own cmdset -- a furnace has `craft`, a bank terminal has
# `bank`, a talkative NPC has `talk` -- and those take no target because the
# object the cmdset hangs on IS the target. A typeclass declares its own verb
# in `interact_verb`; see serializers.interact_command.
#
# A CHARACTER is absent on purpose, and its absence is the policy: everything
# else a misclick can do is recoverable, and opening combat on another player
# is not.
TARGETED_VERB_BY_KIND: dict = {
    ASSET_KIND_NPC: "attack",
    ASSET_KIND_ITEM: "get",
}

# Room prototype key used when a room carries none. Matches the wildcard
# behaviour of the ('*', '*') entry in a map's PROTOTYPES table.
ROOM_KIND_DEFAULT: str = "default"


# ─── Inventory ───────────────────────────────────────────────────────────────

# The second tier of the client's mesh lookup, after the per-item asset key.
#
# These are already the TAG CATEGORIES every ItemDef declares -- a spear is
# tagged ("rusty_scrap_spear", "weapon") -- so this restates no fact the item
# database does not already own. It exists as an explicit set because a live
# object also carries Evennia's own from_prototype tag, and the family reader
# has to be able to tell a family category from an engine one.
#
# A key absent here is not an error: the client falls through to a generic mesh
# labelled with the item's real name, which is the same guarantee the world
# pane already gives. Adding a family here without adding a mesh for it
# client-side is therefore harmless.
ITEM_FAMILY_WEAPON: str = "weapon"
ITEM_FAMILY_ARMOR: str = "armor"
ITEM_FAMILY_JEWELLERY: str = "jewellery"
ITEM_FAMILY_MATERIAL: str = "crafting_material"
ITEM_FAMILY_TOOL: str = "crafting_tool"
ITEM_FAMILY_CURRENCY: str = "currency"

ITEM_FAMILIES: frozenset = frozenset((
    ITEM_FAMILY_WEAPON,
    ITEM_FAMILY_ARMOR,
    ITEM_FAMILY_JEWELLERY,
    ITEM_FAMILY_MATERIAL,
    ITEM_FAMILY_TOOL,
    ITEM_FAMILY_CURRENCY,
))

ITEM_FAMILY_GENERIC: str = "generic"

# The verbs an item in the inventory affords, as (label, command template).
#
# `{slot}` is substituted with the item's 1-BASED grid position and `{name}`
# with its key. One-based because that is what the text grid prints
# (display.py renders `slot_idx + 1`) and what the commands parse, so what the
# pane sends is exactly what the player sees beside the item when they type
# `inventory`. The 0-based index in the payload is an array position, and the
# conversion happens here rather than in the client.
INVENTORY_ACTION_EQUIP: tuple = ("Equip", "equip {slot}")
INVENTORY_ACTION_DROP: tuple = ("Drop", "drop {name}")
INVENTORY_ACTION_INSPECT: tuple = ("Inspect", "look {name}")

# What an equipped item affords. Keyed by slot value rather than grid index,
# because an equipped item has no grid position to name.
EQUIPMENT_ACTION_UNEQUIP: tuple = ("Unequip", "unequip {equip_slot}")
EQUIPMENT_ACTION_INSPECT: tuple = ("Inspect", "look {name}")
