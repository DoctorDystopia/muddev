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
CHANNEL_CHAR_AVATAR: str = "char_avatar"              # -> Char.Avatar
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

# Every quest the observer has taken, and where they are in it.
#
# GMCP has no standard name for a quest log, so this follows the vocabulary of
# the Char.* channels above rather than being namespaced under blackout_: "what
# my character is doing" is exactly what a Char.* channel is for, and a client
# that understands Char.Vitals will look for it there.
#
# STRUCTURED, not rendered. `QuestHandler.objective_lines` already produces
# prose for the telnet screen, and shipping that would have been the smaller
# change -- but an objective is DATA: a description, a count and a requirement.
# A client given the numbers can draw a progress bar, sort by completion and
# grey out what is done; a client given "[x] Cut 3/5 poles" can only print it.
# The payload is built beside `objective_lines` from the same handler reads, so
# the two cannot disagree -- the arrangement CombatPayload uses to mirror
# ActionResult.
CHANNEL_CHAR_QUESTS: str = "char_quests"              # -> Char.Quests

# Every skill the observer has, with its XP curve and everything it unlocks.
#
# Named beside the other Char.* channels for the reason CHANNEL_CHAR_SUMMARY
# gives: "what my character can do" is exactly what a Char.* channel is for.
#
# IT IS NOT A SLICE OF char_summary, and the split is the point. The skills
# band used to be a panel under systems/summary/panel_defs/, which meant a
# client wanting a skills SCREEN had to reach into the dossier payload and pull
# one key out of it by name -- and the dossier's whole contract, stated at
# length on CharSummaryPayload, is that a client never names a panel. One
# screen, one channel; the dossier no longer carries skills at all.
#
# STRUCTURED, NOT RENDERED, the same argument CHANNEL_CHAR_QUESTS makes. A
# client given `{level, current_xp, needed_xp}` can draw a grid of meters and
# sort by progress; a client given "Cutting 30 [====----]" can only print it.
#
# IT CARRIES THE UNLOCKS TOO, which is the one thing here that looks like too
# much. It is static per skill -- what a recipe requires does not depend on who
# is asking -- so it could have been a second request. Shipping it in the
# snapshot is what makes clicking a skill instant instead of a round trip, and
# the whole table is a few kilobytes for the entire roster.
CHANNEL_CHAR_SKILLS: str = "char_skills"              # -> Char.Skills

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
    CHANNEL_CHAR_AVATAR,
    CHANNEL_CHAR_VITALS,
    CHANNEL_CHAR_STATUS,
    CHANNEL_CHAR_SUMMARY,
    CHANNEL_CHAR_ITEMS,
    CHANNEL_CHAR_QUESTS,
    CHANNEL_CHAR_SKILLS,
    CHANNEL_MAP,
    CHANNEL_COMBAT,
    CHANNEL_AURA,
))

# Evennia's websocket `send_default` silently DROPS an outputfunc with this
# name, and `clean_senddata` injects a key of the same name into every
# outputfunc's kwargs. Named here so the guard in emit.py is not a bare string.
RESERVED_CHANNEL_NAME: str = "options"


# ─── Text routing ──────────────────────────────────────────────────

# What a line of game TEXT is about, so a client can put it somewhere.
#
# WHY THESE LIVE HERE, beside the channel names. `send_text` and `send_default`
# are two halves of one wire -- the client's dispatcher tells them apart by the
# outputfunc name and nothing else -- and a `type` tag is categorically the same
# thing as a channel name: a routing name the SERVER owns and a client reads.
# The generator, its output paths, its banner and its staleness test all exist
# here already, for exactly this kind of fact.
#
# HOW IT REACHES A CLIENT. `msg(text=(line, {"type": "combat"}))` becomes the
# outputfunc `("text", (line,), {"type": "combat"})`; `clean_senddata` carries
# the kwargs through untouched and the godotwebsocket contrib pops only
# `options` before it serialises, so the tag arrives intact. Telnet and MSDP
# ignore it, which is the point of putting it in kwargs rather than in the prose.
#
# WHAT OWNS WHAT, and this is the line that decides every argument about a tab:
#
#     The SERVER says what a line IS.       -- this table
#     The CLIENT says which tab shows it.   -- and the player may override it
#
# There is no server fact naming a tab, and there must not be one. The
# consequence, stated because it will otherwise be read as a bug: a type no tab
# claims is NOT lost. It appears in the client's `All` tab, which is where the
# player is by default -- the same degradation an item with no art gets from the
# mesh ladder.
#
# UNTAGGED IS A REAL STATE AND IT IS FINE. EvMenu nodes, `page`, and a good deal
# of Evennia's error prose carry no tag at all, and requiring every call site in
# the game to be correct before anything renders would be the wrong order of
# work. The client supplies MESSAGE_TYPE_GENERAL for a line that arrives without
# one; nothing here defaults it, because a default applied server-side would make
# "nobody has tagged this yet" indistinguishable from "this is general".

# The kwarg key itself. Named so no call site types the string, and so the
# scanner in tests/test_message_types.py has one thing to look for.
MESSAGE_TYPE_KEY: str = "type"


# Tags Evennia already sends.
#
# THESE ARE NOT INVENTED HERE AND NOTHING IN BLACKOUT WRITES THEM. Evennia's own
# hooks and commands already tag a good deal of what a player reads, and the
# values below are ITS spelling, read off the installed engine:
#
#     objects.py:at_say           -> "say" / "whisper"
#     general.py:CmdPose          -> "pose"
#     general.py:CmdLook,
#       objects.py:at_post_puppet -> "look"
#     help.py:CmdHelp             -> "help"
#     building.py:CmdExamine      -> "examine"
#     objects.py:announce_move_*  -> whatever `move_type` was passed
#
# So they are DECLARED, not implemented: a client tab may name them and the game
# needs no override to produce them. Copying the engine's vocabulary rather than
# inventing a parallel one is the same call the moderator egg makes when it types
# Evennia's own `ban` through execute_cmd -- there is one owner of what a say is
# called, and it is upstream.
#
# `whisper`, and not `tell`, for exactly that reason.
MESSAGE_TYPE_LOOK: str = "look"
MESSAGE_TYPE_POSE: str = "pose"
MESSAGE_TYPE_SAY: str = "say"
MESSAGE_TYPE_WHISPER: str = "whisper"
MESSAGE_TYPE_HELP: str = "help"
MESSAGE_TYPE_EXAMINE: str = "examine"

# An arrival or a departure. `announce_move_from`/`_to` tag with whatever
# `move_type` they were given, so the tag is the MOVE KIND rather than one fixed
# name -- and Blackout passes `get`, `drop`, `buy`, `sell` and `craft` as well as
# these two.
#
# Only the two that reach a player un-quieted are declared. The rest go with
# `quiet=True` and announce nothing; if one ever stops being quiet it lands in
# the client's `All` tab like any other unclaimed type, which is the documented
# degradation and not a bug.
MESSAGE_TYPE_MOVE: str = "move"
MESSAGE_TYPE_TELEPORT: str = "teleport"


# Tags Blackout sends itself.

# The fallback a client applies to an untagged line. Never sent.
MESSAGE_TYPE_GENERAL: str = "general"

# Something happening in the room that Blackout narrates itself: sitting down,
# standing up, an object reacting. Distinct from `look`, which is the engine
# describing the room, and from `move`, which is somebody entering or leaving.
MESSAGE_TYPE_ROOM: str = "room"

# The ASCII map printed above a room description.
#
# `xymap`, and NOT the `map` this was renamed to for half a day. The xyzgrid
# contrib msg's the map itself on the ordinary no-aura path -- see
# XYZRoom.return_appearance, whose docstring says "the map is tagged with
# type='xymap'" -- so the engine already owns this spelling and a second one
# here would mean the two paths reached a client under different tags, with a
# tab claiming only the rarer of them.
#
# It is the same rule as `say` and `look` above, learned the same way: where
# Evennia already tags something, its spelling wins.
MESSAGE_TYPE_MAP: str = "xymap"

# One resolved swing: a hit, a miss, a death.
#
# This was `testing` until 08/28/2026 -- a placeholder that shipped, and the only
# tag combat had.
MESSAGE_TYPE_COMBAT: str = "combat"

# An HP readout in prose.
#
# ONE tag, where there were two. `target_health` and `player_health` were two
# names for one thing, distinguished only by whose HP it was -- which the line
# itself already says and which `char_vitals` already carries structurally.
MESSAGE_TYPE_VITALS: str = "vitals"

# XP awards and level-ups.
MESSAGE_TYPE_PROGRESSION: str = "progression"

# The carried grid, and picking things up, dropping and wearing them. Shares the
# engine's spelling: Evennia's own CmdInventory tags `inventory` too, and
# Blackout's command overrides it.
MESSAGE_TYPE_INVENTORY: str = "inventory"

MESSAGE_TYPE_CRAFTING: str = "crafting"
MESSAGE_TYPE_GATHERING: str = "gathering"
MESSAGE_TYPE_QUEST: str = "quest"

# Shops and banks. One tag for both: they are the same thing to a player reading
# a log, and a client that wanted them apart could split on the command it sent
# rather than on a tag.
MESSAGE_TYPE_COMMERCE: str = "commerce"

# What an NPC says, including every EvMenu node that renders as speech.
MESSAGE_TYPE_DIALOGUE: str = "dialogue"

# An Evennia Channel. The engine stamps `from_channel` on these and no `type`,
# so Account.channel_msg adds one; see typeclasses/accounts.py.
MESSAGE_TYPE_CHANNEL: str = "channel"

# Connection notices, permission refusals, and anything the server says as itself
# rather than as the world.
MESSAGE_TYPE_SYSTEM: str = "system"

# Every tag a client may be told about, whoever sends it.
#
# The guard test scans BLACKOUT's source as text for `"type": "..."` literals and
# asserts each value is in here -- so a typo fails the suite instead of routing a
# line to a tab that will never exist. It is a MEMBERSHIP set and never a census:
# adding a type is one constant and one entry, and no test lists them.
#
# MESSAGE_TYPE_GENERAL is a member even though nothing sends it, because a client
# names it when declaring which types its fallback tab shows.
MESSAGE_TYPES: frozenset = frozenset((
    MESSAGE_TYPE_LOOK,
    MESSAGE_TYPE_POSE,
    MESSAGE_TYPE_SAY,
    MESSAGE_TYPE_WHISPER,
    MESSAGE_TYPE_HELP,
    MESSAGE_TYPE_EXAMINE,
    MESSAGE_TYPE_MOVE,
    MESSAGE_TYPE_TELEPORT,
    MESSAGE_TYPE_GENERAL,
    MESSAGE_TYPE_ROOM,
    MESSAGE_TYPE_MAP,
    MESSAGE_TYPE_COMBAT,
    MESSAGE_TYPE_VITALS,
    MESSAGE_TYPE_PROGRESSION,
    MESSAGE_TYPE_INVENTORY,
    MESSAGE_TYPE_CRAFTING,
    MESSAGE_TYPE_GATHERING,
    MESSAGE_TYPE_QUEST,
    MESSAGE_TYPE_COMMERCE,
    MESSAGE_TYPE_DIALOGUE,
    MESSAGE_TYPE_CHANNEL,
    MESSAGE_TYPE_SYSTEM,
))


# ─── Graphical clients ───────────────────────────────────────────────────────

# The `protocol_key` the godotwebsocket contrib stamps on every session it
# accepts.
#
# Named here rather than typed at the one place that reads it, because it is a
# fact about the WIRE and this module owns those. The contrib sets it in its
# own `__init__`; it is not configurable and not ours, so a mismatch would be
# silent -- every Godot session would look like a telnet one and the map below
# would keep being printed at a client already drawing it.
GODOT_PROTOCOL_KEY: str = "godotclient/websocket"

# Attribute on a Character deciding whether the ASCII map is msg'd on look.
#
# UNSET is the normal case and means "decide from the client": a session on the
# protocol above draws its own minimap from `blackout_map`, so printing thirty
# lines of box characters into its log on every step is noise nothing reads.
# Everyone else gets the map, exactly as before.
#
# It is an OVERRIDE and not a switch, and the difference matters: a Godot player
# who wants the text map can set it True and keep it, and a telnet player who is
# tired of it can set it False. Neither is a client capability, which is why
# this is a per-character attribute rather than something the client announces.
#
# WHY IT EXISTS AT ALL. `XYZRoom.return_appearance` msg's the map on every
# `look`, and `look` runs on every room change -- so on a 95-node map the text
# pane's dominant content was a picture the graphical client was already
# drawing beside it. This is the single largest reduction in log noise
# available, and it costs one attribute read.
ASCII_MAP_ATTR: str = "show_ascii_map"


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
#   - CHANNEL_CHAR_SKILLS is uncapped for the same reason as the summary, and
#     it is worth stating separately because the channel LOOKS event-driven:
#     combat awards XP on every hit. It is not published on an XP award. It
#     fires when a level actually MOVES, when the player asks about skills, and
#     on resync -- so its rate is bounded by the player, not by the tick, and a
#     cap would only mean `skills` twice in a second answering once.
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

# ─── Coalescing ──────────────────────────────────────────────────────────────
# Channels whose messages may be COALESCED: held during a tick and sent once at
# the end, newest winning. This is the "trailing send" the cap discussion above
# asks for -- nothing is dropped, the client simply gets one message per tick
# instead of several.
#
# The membership rule is the same distinction the cap table draws, applied more
# strictly. A channel may be coalesced ONLY if each message entirely SUPERSEDES
# the last, so that keeping only the newest loses nothing:
#
#   - Whole-snapshot channels qualify. A grid, a vitals reading, a room's
#     occupant list: the newest one tells the whole truth on its own.
#   - EVENT and DELTA channels do NOT, and this is the half that matters.
#     CHANNEL_COMBAT carries one message per swing; two attackers hitting the
#     same target on one tick produce two, and keeping only the newest loses a
#     hit the text log still shows. CHANNEL_ROOM_PLAYER_ADD / _REMOVE are
#     deltas for the same reason -- coalescing two arrivals into one is the
#     room_players bug in a new place.
#   - CHANNEL_MAP is excluded despite being a snapshot, because it is CHUNKED:
#     its messages are pieces of one payload, not successive versions of it,
#     so "newest wins" would deliver chunk 2 and drop chunk 1.
#
# When in doubt, leave a channel OUT. An uncoalesced channel is merely chattier;
# a wrongly coalesced one silently loses information.
COALESCABLE_CHANNELS: frozenset = frozenset((
    CHANNEL_CHAR_AVATAR,
    CHANNEL_CHAR_VITALS,
    CHANNEL_CHAR_STATUS,
    CHANNEL_CHAR_SUMMARY,
    CHANNEL_CHAR_SKILLS,
    CHANNEL_CHAR_ITEMS,
    CHANNEL_ROOM_INFO,
    CHANNEL_ROOM_PLAYERS,
))

# The ndb attribute holding {channel: last_send_monotonic} per session.
RATE_STATE_ATTR: str = "statefeed_last_send"


# ─── Payload sizing ──────────────────────────────────────────────────────────

# Map nodes per `blackout_map` message. Godot's WebSocketPeer defaults to a
# 65535-byte inbound buffer and historically TRUNCATED oversized JSON silently
# rather than erroring (fixed for Godot >= 4.4). A full Blackout map is ~95
# nodes and would fit in one frame today, but chunking now costs nothing and
# removes a failure mode that only appears once a map grows.
MAP_NODES_PER_CHUNK: int = 40

# How large an inbound websocket message a Godot client must be prepared to
# accept, in bytes. Exported to the client, which sets it on its WebSocketPeer
# before connecting.
#
# WHY THIS IS A SERVER CONSTANT. It is the SERVER that decides how big a message
# gets -- STATEFEED_ENTITY_RADIUS above is the knob, and raising it grows
# room_players quadratically. A ceiling owned by the client would be a number
# nobody re-checked when the radius moved, which is precisely how the map
# payload earned its chunker. One owner, exported, and
# test_payload_size.py fails when the two drift.
#
# WHY 1 MiB RATHER THAN THE 65535 DEFAULT. Godot's WebSocketPeer defaults to a
# 64 KiB inbound buffer. A whole-map room_players payload measures ~43 KB on a
# live-sized map today (see docs/2026-09-03-PERF-0002-crowd-scaling.md), which
# is 66% of that default -- one radius increase or one busy market away from
# hitting it. On Godot < 4.4 the overflow TRUNCATED SILENTLY; on 4.7, which
# this client targets, it errors instead, which is better and still a
# disconnection nobody can diagnose from the symptom.
#
# The cost is one buffer on one socket in one client process, so the headroom
# is nearly free and the alternative -- chunking room_players the way
# blackout_map is chunked -- is a two-sided change that would make a client
# render a partially-applied entity list. That change may still be worth making
# if the radius rises far enough; this constant is what makes the moment it
# becomes necessary a failing test rather than a bug report.
#
# It does NOT apply to a web export. A browser build delegates to the native
# WebSocket API, which has no such ceiling; the property is simply ignored
# there.
CLIENT_INBOUND_BUFFER_BYTES: int = 1024 * 1024


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

# Every puppetable character, until one of them says otherwise.
#
# It has to be a key of its own rather than ASSET_KEY_GENERIC, and the reason
# is the client's registry: an asset key with art registered against it draws
# that art for EVERY entity carrying the key. Generic is also the fallback for
# an item nothing else classified, so art registered there would put a person
# in place of every unmodelled object in the game.
#
# Named for what it is rather than for a particular download, so replacing the
# art is a client-side edit and reaches every character at once.
ASSET_KEY_CHARACTER: str = "player_character"

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

# The kind reported for a MAP-TRANSITION node: the `T` glyph that moves a
# player to a coordinate on another map.
#
# It is a synthesised kind rather than a prototype key, because a transition
# node has no prototype -- the contrib requires `prototype = None` on it, so no
# room is ever spawned there and there is no key to read. Without this the
# lookup below falls through to the map's ('*', '*') wildcard and reports the
# tile as ordinary ground, which is how the one tile leading off the map came
# to be drawn as more sand.
#
# Written in the ROOM_KIND_DEFAULT style -- a lowercase machine token rather
# than a display name like "Bank" -- because no author typed it and none can
# override it.
ROOM_KIND_TRANSITION: str = "map_transition"


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

# The order the families are resolved in when ONE item declares several of
# them.
#
# An item is allowed to be more than one thing: the rusty scrap axe is a
# crafting_tool and a weapon, and nothing about a tag stops a third or a
# fourth category joining it. Evennia stores an object's tags as an unordered
# set, so "the first family category on the object" is whatever the database
# happens to hand back on that call -- the same axe could render as a tool in
# one session and a weapon in the next. Resolving against THIS tuple instead
# of against tag order makes the answer the same every time.
#
# Ordered most-distinctive silhouette first, because this only decides which
# mesh a multi-family item FALLS BACK to: an axe that chops trees and raiders
# still looks like an axe, so the tool mesh describes it better than the
# generic weapon one. A single-family item matches exactly one entry and is
# unaffected by the order.
ITEM_FAMILY_PRIORITY: tuple = (
    ITEM_FAMILY_CURRENCY,
    ITEM_FAMILY_MATERIAL,
    ITEM_FAMILY_JEWELLERY,
    ITEM_FAMILY_TOOL,
    ITEM_FAMILY_ARMOR,
    ITEM_FAMILY_WEAPON,
)

# Membership set, derived so the two can never list different families.
ITEM_FAMILIES: frozenset = frozenset(ITEM_FAMILY_PRIORITY)

ITEM_FAMILY_GENERIC: str = "generic"

# The verbs an item in the inventory affords, as (label, command template).
#
# `{slot}` is substituted with the item's 1-BASED grid position and `{name}`
# with its key. One-based because that is what the text grid prints
# (display.py renders `slot_idx + 1`) and what the commands parse, so what the
# pane sends is exactly what the player sees beside the item when they type
# `inventory`. The 0-based index in the payload is an array position, and the
# conversion happens here rather than in the client.
#
# Drop names a SLOT, not a name, for the reason commands.inventory_cmds
# .resolve_carried_item gives: eight identical rusty metal chunks are a real
# inventory, and `drop rusty metal chunk` is a command whose target the pane
# cannot predict. It sent one anyway until 08/17/2026, and the server picked
# the lowest-numbered copy -- so right-clicking the eighth chunk dropped the
# first. A slot index is exactly what the pane has.
INVENTORY_ACTION_EQUIP: tuple = ("Equip", "equip {slot}")
INVENTORY_ACTION_DROP: tuple = ("Drop", "drop {slot}")
INVENTORY_ACTION_INSPECT: tuple = ("Inspect", "look {name}")

# What an equipped item affords. Keyed by slot value rather than grid index,
# because an equipped item has no grid position to name.
EQUIPMENT_ACTION_UNEQUIP: tuple = ("Unequip", "unequip {equip_slot}")
EQUIPMENT_ACTION_INSPECT: tuple = ("Inspect", "look {name}")


# ─── Tile affordances ────────────────────────────────────────────────────────

# What clicking a TILE does, named by the server the way an entity's `interact`
# already is.
#
# WHY THIS MOVED. The client used to work it out, and the rules it needed were
# all facts about the map: that a different z is a different map and cannot be
# walked to, which neighbours were walls, and a grid-delta -> direction-name
# table to turn any of it into a command. Every one of those is the server's to
# know, and the neighbour rule was got wrong TWICE -- first refusing every
# diagonal, then, once it had moved here, refusing every unlinked cardinal.
# Both times the symptom was the same: tiles the player could plainly reach
# were the only ones in the pane that could not be clicked.
#
# It is the same argument that deleted the client's entity verb table, and it
# is stronger here: a second client (godot/) has not yet reimplemented any of
# it, so moving it now costs one implementation instead of two that must agree.

# A tile's action is {command, kind}. The command is what to SEND -- whole, no
# substitution left to do. The kind is what it means for a walk in progress,
# which the client tracks because the client is what started it.
TILE_ACTION_KIND_STEP: str = "step"      # one move; ends a tracked walk
TILE_ACTION_KIND_WALK: str = "walk"      # a pathfinder walk; starts tracking
TILE_ACTION_KIND_LOOK: str = "look"      # no movement, no effect on tracking
TILE_ACTION_KIND_CANCEL: str = "cancel"  # aborts the walk in progress

# THERE IS NO WALL MARKER, and the missing fifth kind is the point.
#
# A tile with no entry in tile_actions falls through to the map node's own
# `goto`, and until 08/28/2026 the server pushed back against that for one
# case: a CARDINAL neighbour reached by no exit was answered with an empty
# command, so that a click on what looked like a barrier did not send the
# player the long way around it.
#
# The premise is false on any map drawn with diagonal links. On the oasis,
# (6,3) carries the foundry furnace and is joined to FOUR diagonal neighbours
# and to no cardinal one, so standing at (6,2) -- directly below it, two steps
# away -- the one tile the player was looking at was the one tile the pane
# refused. The teleporter at (0,2) was refused the same way from (0,1).
#
# Nor was anything gained where the premise held: a cell the map has no node
# for is never DRAWN by either client, so there was no click there to refuse.
# The rule could only ever fire on tiles that were real and reachable.
#
# An unreachable tile still answers out loud, just further down: `goto`
# declines a route it cannot find, in words, in the text pane.

# The command a client sends to look at where it already is.
TILE_COMMAND_LOOK: str = "look"

# Bare `goto` aborts a walk in progress; `goto (X,Y)` starts one. Both are the
# contrib's pathfinder reached exactly as a telnet player reaches it -- see
# commands/movement_cmds.py, which lifts the contrib's Builder lock on the
# coordinate form because a tile is the only name a graphical client has for a
# room.
TILE_COMMAND_GOTO: str = "goto"
TILE_COMMAND_GOTO_TEMPLATE: str = "goto ({x},{y})"

# How a tile is keyed in a tile-action map. Formatted here rather than in the
# client for the same reason serialize_inventory formats its slot numbers here:
# one owner for the shape, and no client left holding a format string.
TILE_KEY_TEMPLATE: str = "{x}:{y}"


# The command that moves an item between two inventory slots.
#
# Unlike equip/unequip, this one CANNOT be pre-named per item the way
# INVENTORY_ACTION_* above are: it takes two endpoints, and only the drag knows
# both. So the server owns the SPELLING and the client composes the gesture --
# which is the honest split. A drag from slot 3 to slot 7 is a gesture, not a
# fact about slot 3, and pre-naming every pair would be 42x42 commands to
# express one verb.
#
# Slot numbers are 1-BASED, matching what the text grid prints, what CmdSwap
# parses, and what serialize_inventory converts to for the per-item actions.
INVENTORY_SWAP_TEMPLATE: str = "swap {source} {target}"


# ─── Commerce ────────────────────────────────────────────────────────────────

# What a nearby object lets you do with what you are carrying.
#
# Declared on the TYPECLASS as `commerce_role` and read with getattr, exactly
# the way `asset_kind` and `interact_verb` already are, and for the same three
# reasons: nothing about an object's storage distinguishes a shopkeeper from a
# dropped sword, a class attribute reaches every instance already in the
# database without a migration, and the state feed stays out of the typeclass
# layer.
#
# A new counterparty -- a fence, a pawnbroker, a second bank -- opts in with
# one class attribute and reaches both clients' context menus with no edit in
# systems/statefeed/ and none in either client.
COMMERCE_ROLE_SHOP: str = "shop"
COMMERCE_ROLE_BANK: str = "bank"

COMMERCE_ROLES: frozenset = frozenset((
    COMMERCE_ROLE_SHOP,
    COMMERCE_ROLE_BANK,
))

# The verbs a carried item affords when the matching counterparty is standing
# in the room, as (label, command template) -- the same shape and the same
# `{slot}` substitution INVENTORY_ACTION_* above use.
#
# THE LABELS CARRY NO PRICE. The server is the only thing that knows the miser
# factor, so putting it here was tempting, and it is wrong for one reason: a
# label is drawn once, when the snapshot is built, and a stack drains. "Sell
# All (24cr)" on a stack that is now eight units is a lie the player acts on.
# The line messages.format_trade prints after the sale describes a trade that
# has already happened and cannot go stale, which is where the money belongs.
INVENTORY_ACTION_SELL: tuple = ("Sell", "sell {slot}")
INVENTORY_ACTION_SELL_ONE: tuple = ("Sell 1", "sell {slot} 1")
INVENTORY_ACTION_SELL_ALL: tuple = ("Sell All", "sell {slot} all")

INVENTORY_ACTION_DEPOSIT: tuple = ("Deposit", "deposit {slot}")
INVENTORY_ACTION_DEPOSIT_ONE: tuple = ("Deposit 1", "deposit {slot} 1")
INVENTORY_ACTION_DEPOSIT_ALL: tuple = ("Deposit All", "deposit {slot} all")

# An equipped row has no grid position, so it is addressed the way
# EQUIPMENT_ACTION_UNEQUIP is -- by the slot it occupies. `deposit` resolves
# that through the equipment handler and unequips before banking.
#
# There is no equipped SELL, and the asymmetry is deliberate. An unequipped
# deposit is undone by `withdraw`; a sale at the miser factor is not, and worn
# gear is exactly what a misclick most wants back.
EQUIPMENT_ACTION_DEPOSIT: tuple = ("Deposit", "deposit {name}")

# The quantity prompt's spelling, for the one action the server cannot name
# outright.
#
# Sell 1 and Sell All are whole commands. Sell X is not: the amount is a
# GESTURE, something only the client holds, the same way a drag holds two slot
# endpoints and the server holds neither. INVENTORY_SWAP_TEMPLATE above is the
# established answer to that case -- the server owns the spelling, the client
# composes the one value it has.
INVENTORY_SELL_SOME_TEMPLATE: str = "sell {slot} {amount}"
INVENTORY_DEPOSIT_SOME_TEMPLATE: str = "deposit {slot} {amount}"

# The token a prompted action's `template` carries where the client's answer
# goes, and the kind of prompt to open.
#
# A PROMPTED ACTION SENDS AN EMPTY `command`, which both clients already read
# as "the server declines". That is what makes this degrade safely: a client
# that has not learned about `input` shows the entry and does nothing, rather
# than sending a literal "{amount}" at the parser. The rejected alternative
# was a non-empty command carrying the placeholder -- it reads better and it
# fails worse.
#
# Exported to the clients so the substitution has one owner; the templates
# themselves are not, because they arrive per action.
ACTION_AMOUNT_PLACEHOLDER: str = "{amount}"
ACTION_INPUT_KIND_QUANTITY: str = "quantity"

# Keys on a prompted action's `input` block. Named so neither the builder nor
# a test spells one as a literal.
ACTION_INPUT_KIND_KEY: str = "kind"
ACTION_INPUT_MIN_KEY: str = "min"
ACTION_INPUT_MAX_KEY: str = "max"
ACTION_INPUT_LABEL_KEY: str = "label"

# What a quantity prompt asks. The server words it because the server is what
# knows the verb; the client draws the box.
ACTION_PROMPT_SELL: str = "Sell how many?"
ACTION_PROMPT_DEPOSIT: str = "Deposit how many?"

# The label on a prompted action's menu entry.
INVENTORY_ACTION_SELL_SOME_LABEL: str = "Sell X"
INVENTORY_ACTION_DEPOSIT_SOME_LABEL: str = "Deposit X"

# Smallest amount a quantity prompt may be set to. One, not zero: an action
# that does nothing is not an action, and base_menu.MIN_QUANTITY refuses zero
# on the typed path for the same reason.
ACTION_INPUT_MIN_AMOUNT: int = 1

# Above this many units a row offers the three-verb group (1 / X / All);
# at or below it, one bare verb. Nobody wants "Sell All" on one sword.
ACTION_QUANTITY_SINGLE: int = 1
