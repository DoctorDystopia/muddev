# GENERATED FILE -- DO NOT EDIT.
#
# Rendered from systems/interface/statefeed/constants.py by
# systems/interface/statefeed/clientexport.py. Change the Python and re-run:
#
#     python scripts/export_client_constants.py
#
# Every name below is a fact the SERVER owns. Presentation -- colours,
# meshes, camera, the model registry -- is the client's own and is
# deliberately not generated; see the module docstring in clientexport.py.
#
# A test asserts the committed copy of this file matches a fresh render,
# so an edit here fails the suite rather than surviving quietly.

# Feed channels.
const CH_ROOM_INFO := "room_info"
const CH_ROOM_PLAYERS := "room_players"
const CH_ROOM_PLAYERS_DELTA := "room_players_delta"
const CH_PLAYER_ADD := "room_add_player"
const CH_PLAYER_REMOVE := "room_remove_player"
const CH_CHAR_AVATAR := "char_avatar"
const CH_CHAR_VITALS := "char_vitals"
const CH_CHAR_STATUS := "char_status"
const CH_CHAR_SUMMARY := "char_summary"
const CH_CHAR_ITEMS := "char_items_list"
const CH_CHAR_QUESTS := "char_quests"
const CH_CHAR_SKILLS := "char_skills"
const CH_CHAR_COMBAT := "char_combat"
const CH_CHAR_POPUP := "char_popup"
const CH_COMBAT := "blackout_combat"
const CH_AURA := "blackout_aura"
const CH_XP_DROP := "blackout_xp"
const CH_TILE_CHUNK := "blackout_chunk"
const CH_SUBSCRIBED := "blackout_subscribed"

# Asset kinds -- the client's mesh `family` vocabulary.
const FAMILY_ITEM := "item"
const FAMILY_NPC := "npc"
const FAMILY_CHARACTER := "character"
const FAMILY_ROOM := "room"
const FAMILY_STATION := "station"
const FAMILY_GATHERABLE := "gatherable"
const FAMILY_CORPSE := "corpse"
const FAMILY_SIGN := "sign"
const FAMILY_GENERIC := "generic"

# Item families.
const ITEM_FAMILY_WEAPON := "weapon"
const ITEM_FAMILY_ARMOR := "armor"
const ITEM_FAMILY_JEWELLERY := "jewellery"
const ITEM_FAMILY_MATERIAL := "crafting_material"
const ITEM_FAMILY_TOOL := "crafting_tool"
const ITEM_FAMILY_CURRENCY := "currency"
const ITEM_FAMILY_FOOD := "food"
const ITEM_FAMILY_GENERIC := "generic"

# World label kinds -- what sort of text an entity's `label` is.
const LABEL_KIND_SIGN := "sign"
const LABEL_KIND_MARKER := "marker"
const LABEL_KIND_GRAFFITI := "graffiti"

# Tile action kinds -- what a click does to a walk in progress.
const KIND_STEP := "step"
const KIND_WALK := "walk"
const KIND_LOOK := "look"
const KIND_CANCEL := "cancel"

# Text routing -- what a line of game text is ABOUT. Which tab shows it is the client's own.
const MESSAGE_TYPE_KEY := "type"
const MSG_GENERAL := "general"
const MSG_LOOK := "look"
const MSG_POSE := "pose"
const MSG_SAY := "say"
const MSG_WHISPER := "whisper"
const MSG_HELP := "help"
const MSG_EXAMINE := "examine"
const MSG_MENU := "menu"
const MSG_MOVE := "move"
const MSG_TELEPORT := "teleport"
const MSG_ROOM := "room"
const MSG_MAP := "xymap"
const MSG_COMBAT := "combat"
const MSG_VITALS := "vitals"
const MSG_PROGRESSION := "progression"
const MSG_INVENTORY := "inventory"
const MSG_CRAFTING := "crafting"
const MSG_GATHERING := "gathering"
const MSG_QUEST := "quest"
const MSG_COMMERCE := "commerce"
const MSG_DIALOGUE := "dialogue"
const MSG_CHANNEL := "channel"
const MSG_SYSTEM := "system"

# The server clock. One tile per tick is walking speed.
const TICK_SECONDS := 0.6

# The tile grid and its chunk file. DESIGN-0011 section 6.2.
const CHUNK_FORMAT_VERSION := 1
const CHUNK_SIZE := 64
const CHUNK_CORNERS_PER_SIDE := 65
const CHUNK_PLANE_MAX := 3
const CHUNK_HEIGHT_MIN := -32768
const CHUNK_HEIGHT_MAX := 32767
const CHUNK_ROTATION_COUNT := 4
const CHUNK_NAME_PATTERN := "^[a-z0-9_]+$"
const CHUNK_FILE_TEMPLATE := "chunk_{cx}_{cy}_p{plane}.json"
const CHUNK_DIRECTORY := "world/chunks"
const TILE_SYNC_STAMP_FILE := "server/tile_sync_state.json"
const CHUNK_STREAM_RADIUS := 1
const TILE_WORLD_Z := "tile_world"
const TILE_WALK_LIMIT := 16
const TILE_FLAG_BLOCKED := 1
const TILE_FLAG_WATER := 2
const TILE_FLAG_WALL_NORTH := 4
const TILE_FLAG_WALL_EAST := 8
const TILE_FLAG_WALL_SOUTH := 16
const TILE_FLAG_WALL_WEST := 32
const TILE_FLAGS_UNWALKABLE := 3
const TILE_FLAGS_ALL := 63
const OBJECT_CATEGORY_FACILITY := "facility"
const OBJECT_CATEGORY_GATHERING := "gathering"
const OBJECT_CATEGORY_LANDMARK := "landmark"
const OBJECT_CATEGORY_NPC := "npc"
const OBJECT_CATEGORY_SIGN := "sign"
const OBJECT_CATEGORY_TRANSITION := "transition"
const OBJECT_CATEGORY_CLIMB := "climb"
const TILE_DEFAULT_FLOOR := "sand"
const TILE_DEFAULT_AREA := "oasis"
const TILE_GROUND_PLANE := 0
const TILE_PLANE_Z_TEMPLATE := "{world}_p{plane}"
const TILE_VOID_FLOOR := "void"
const TILE_RESPAWN_KIND := "respawn_point"
const CLIMB_UP := "up"
const CLIMB_DOWN := "down"
const TILE_CHECK_UNKNOWN_KIND := "unknown_kind"
const TILE_CHECK_OBJECT_UNWALKABLE := "object_unwalkable"
const TILE_CHECK_TRANSITION_LANDING := "transition_landing"
const TILE_CHECK_CLIMB_LANDING := "climb_landing"
const TILE_CHECK_VOID_OPEN := "void_open"
const TILE_CHECK_RESPAWN_COUNT := "respawn_count"

# What the terrain editor paints and places. The order is
# the order of each table under world/.
const TILE_FLOOR_TYPES := ["sand", "dirt", "gravel", "rubble", "asphalt", "concrete", "grass", "water_bed", "void"]
const TILE_AREAS := ["oasis", "oasis_outskirts", "azm_plains"]
const OBJECT_CATEGORIES := ["climb", "facility", "gathering", "landmark", "npc", "sign", "transition"]
const TILE_CHECK_RULES := ["unknown_kind", "object_unwalkable", "transition_landing", "climb_landing", "void_open", "respawn_count"]
const OBJECT_KINDS := {
	"bank": "facility",
	"foundry_furnace": "facility",
	"metalsmith_anvil": "facility",
	"rendering_cooker": "facility",
	"curing_chamber": "facility",
	"gunsmith_bench": "facility",
	"gastronomy_worktable": "facility",
	"rusty_pole": "gathering",
	"metal_pole": "gathering",
	"copper_pole": "gathering",
	"lone_android": "npc",
	"shopkeeper_oasis": "npc",
	"mutant_raider": "npc",
	"big_mutant": "npc",
	"floating_eye": "npc",
	"mutant_crab": "npc",
	"mutant_giant": "npc",
	"signpost_bank": "sign",
	"signpost_foundry_furnace": "sign",
	"signpost_metalsmith_anvil": "sign",
	"signpost_gunsmith_bench": "sign",
	"signpost_rendering_cooker": "sign",
	"signpost_curing_chamber": "sign",
	"signpost_gastronomy_worktable": "sign",
	"respawn_point": "landmark",
	"transition_oasis_to_outskirts": "transition",
	"transition_outskirts_to_oasis": "transition",
	"ladder_up": "climb",
	"ladder_down": "climb",
	"ladder_both": "climb",
	"stairs_up": "climb",
	"stairs_down": "climb",
	"transition_outskirts_to_azm_plains": "transition",
	"transition_azm_plains_to_outskirts": "transition",
}
const OBJECT_KIND_TARGETS := {
	"transition_oasis_to_outskirts": [72, 10],
	"transition_outskirts_to_oasis": [1, 2],
	"transition_outskirts_to_azm_plains": [129, 2],
	"transition_azm_plains_to_outskirts": [73, 8],
}
const OBJECT_KIND_CLIMBS := {
	"ladder_up": ["up"],
	"ladder_down": ["down"],
	"ladder_both": ["up", "down"],
	"stairs_up": ["up"],
	"stairs_down": ["down"],
}
const CLIMB_PLANE_STEPS := {
	"up": 1,
	"down": -1,
}

# Everything else.
const SUBSCRIBE_ALL := "all"
const ASSET_KEY_CHARACTER := "player_character"
const INVENTORY_SWAP_TEMPLATE := "swap {source} {target}"
const TILE_KEY_TEMPLATE := "{x}:{y}"
const ENTITY_APPROACH_TEMPLATE := "goto ({x},{y}) then {command}"
const TILE_WALK_TEMPLATE := "goto ({x},{y})"
const ENTITY_SPENT_KEY := "spent"
const ACTION_AMOUNT_PLACEHOLDER := "{amount}"
const ACTION_INPUT_KIND_QUANTITY := "quantity"
const ACTION_INPUT_KIND_KEY := "kind"
const ACTION_INPUT_MIN_KEY := "min"
const ACTION_INPUT_MAX_KEY := "max"
const ACTION_INPUT_LABEL_KEY := "label"
const CLIENT_INBOUND_BUFFER_BYTES := 2097152

# Derived sets, so a client can iterate rather than
# rebuild these from the names above.
const SUBSCRIBABLE_CHANNELS := ["blackout_aura", "blackout_chunk", "blackout_combat", "blackout_xp", "char_avatar", "char_combat", "char_items_list", "char_popup", "char_quests", "char_skills", "char_status", "char_summary", "char_vitals", "room_add_player", "room_info", "room_players", "room_players_delta", "room_remove_player"]
const ITEM_FAMILIES := ["armor", "corpse", "crafting_material", "crafting_tool", "currency", "food", "jewellery", "weapon"]
const MESSAGE_TYPES := ["channel", "combat", "commerce", "crafting", "dialogue", "examine", "gathering", "general", "help", "inventory", "look", "menu", "move", "pose", "progression", "quest", "room", "say", "system", "teleport", "vitals", "whisper", "xymap"]
