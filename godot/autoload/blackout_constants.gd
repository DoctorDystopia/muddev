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
const CH_CHAR_CHAT := "char_chat"
const CH_CHAR_ABILITIES := "char_abilities"
const CH_COMBAT := "blackout_combat"
const CH_FACE := "blackout_face"
const CH_AURA := "blackout_aura"
const CH_XP_DROP := "blackout_xp"
const CH_TILE_CHUNK := "blackout_chunk"
const CH_WALK := "blackout_walk"
const CH_WORLD_MAP := "blackout_world_map"
const CH_WORLD_MAP_CHUNK := "blackout_world_map_chunk"
const CH_MOMENT := "blackout_moment"
const CH_TICK_PERF := "blackout_tick_perf"
const CH_SUBSCRIBED := "blackout_subscribed"
const CH_LOGIN_TOKEN := "blackout_login_token"

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

# Game moments -- what a client can mark with a sound.
const MOMENT_TASK_COMPLETE := "task_complete"
const MOMENT_CUT_ATTEMPT := "cut_attempt"
const MOMENT_BUTCHER_ATTEMPT := "butcher_attempt"
const MOMENT_METALSMITH_CRAFT := "metalsmith_craft"
const MOMENT_FOUNDRY_CRAFT := "foundry_craft"
const MOMENT_TRANSITION := "transition"
const MOMENT_GUNS_SHOT := "guns_shot"
const MOMENT_MELEE_SWING := "melee_swing"
const MOMENT_SHOP_BUY := "shop_buy"
const MOMENT_SHOP_SELL := "shop_sell"

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
const MSG_PAGE := "page"
const MSG_SYSTEM := "system"

# The server clock. One tile per tick is walking speed.
const TICK_SECONDS := 0.6

# The tile grid and its chunk file. DESIGN-0011 section 6.2.
const CHUNK_FORMAT_VERSION := 2
const CHUNK_FORMAT_PLAIN_WALLS := 1
const CHUNK_SIZE := 64
const CHUNK_CORNERS_PER_SIDE := 65
const CHUNK_PLANE_MAX := 3
const CHUNK_HEIGHT_MIN := -32768
const CHUNK_HEIGHT_MAX := 32767
const CHUNK_ROTATION_COUNT := 4
const CHUNK_NAME_PATTERN := "^[a-z0-9_]+$"
const CHUNK_TEXT_PATTERN := "^[!#-\\[\\]-{}~]([ !#-\\[\\]-{}~]*[!#-\\[\\]-{}~])?$"
const CHUNK_TEXT_MAX_CHARS := 64
const OBJECT_LOOK_KEY := "look"
const LOOK_VARIANT_KEY := "variant"
const LOOK_SCALE_KEY := "scale"
const LOOK_TURN_KEY := "turn"
const LOOK_OFFSET_KEY := "offset"
const LOOK_VARIANT_ANY := "*"
const LOOK_SCALE_UNIT := 100
const LOOK_SCALE_MIN := 10
const LOOK_SCALE_MAX := 1000
const LOOK_TURN_MAX := 180
const LOOK_OFFSET_UNIT := 100
const LOOK_OFFSET_MAX := 100
const LOOK_AXES := 3
const OBJECT_SPAWN_KEY := "spawn"
const SPAWN_ITEM_KEY := "item"
const SPAWN_QUANTITY_KEY := "quantity"
const SPAWN_RESPAWN_KEY := "respawn"
const SPAWN_QUANTITY_UNIT := 1
const SPAWN_QUANTITY_MAX := 100000
const SPAWN_QUANTITY_BOUNDS := 2
const SPAWN_RESPAWN_MIN := 1
const SPAWN_RESPAWN_MAX := 144000
const CHUNK_FILE_TEMPLATE := "chunk_{cx}_{cy}_p{plane}.json"
const CHUNK_DIRECTORY := "world/chunks"
const STRUCTURE_DIRECTORY := "world/structures"
const STRUCTURE_FILE_SUFFIX := ".json"
const STRUCTURE_FORMAT_VERSION := 1
const TILE_TABLE_DIRECTORY := "world/tables"
const TILE_TABLE_FILE_SUFFIX := ".json"
const TILE_TABLE_FORMAT := 1
const TILE_SYNC_STAMP_FILE := "server/tile_sync_state.json"
const TILE_VERSION_DIRECTORY := "world/versions"
const TILE_VERSION_META_FILE := "version.json"
const TILE_VERSION_FORMAT := 1
const TILE_VERSION_NOTE_MAX_CHARS := 200
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
const TILE_FLAGS_WALLS := 60
const TILE_FLAGS_ALL := 63
const OBJECT_CATEGORY_FACILITY := "facility"
const OBJECT_CATEGORY_GATHERING := "gathering"
const OBJECT_CATEGORY_LANDMARK := "landmark"
const OBJECT_CATEGORY_NPC := "npc"
const OBJECT_CATEGORY_SIGN := "sign"
const OBJECT_CATEGORY_TRANSITION := "transition"
const OBJECT_CATEGORY_CLIMB := "climb"
const OBJECT_CATEGORY_DECOR := "decor"
const OBJECT_CATEGORY_ITEM_SPAWN := "item_spawn"
const OBJECT_TEXT_CATEGORY := "sign"
const OBJECT_SPAWN_CATEGORY := "item_spawn"
const OBJECT_SIGNPOST_KIND := "signpost"
const OBJECT_ITEM_SPAWN_KIND := "item_spawn"
const SCENERY_LADDER := "ladder"
const SCENERY_STAIRS := "stairs"
const SCENERY_HATCH := "hatch"
const SCENERY_STAIRS_TOP := "stairs_top"
const SCENERY_CRATE := "crate"
const SCENERY_TABLE := "table"
const SCENERY_LAMP_POST := "lamp_post"
const SCENERY_OIL_LAMP := "oil_lamp"
const SCENERY_TORCH := "torch"
const TILE_DEFAULT_FLOOR := "sand"
const TILE_DEFAULT_AREA := "oasis"
const TILE_DEFAULT_WALL_STYLE := "plain"
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
const TILE_CHECK_SIGN_TEXT := "sign_text"
const TILE_CHECK_WALL_ON_VOID := "wall_on_void"
const TILE_CHECK_UNREACHABLE := "unreachable"
const TILE_CHECK_ROOF_WALKABLE := "roof_walkable"
const TILE_CHECK_SPAWN_TABLE := "spawn_table"
const TILE_CHECK_SPAWN_ITEM := "spawn_item"

# What the terrain editor paints and places. The order is
# the order of each table under world/.
const TILE_FLOOR_TYPES := ["sand", "dirt", "gravel", "rubble", "asphalt", "concrete", "grass", "water_bed", "roof_sheet_metal", "roof_tile", "roof_concrete", "void"]
const TILE_ROOF_FLOOR_TYPES := ["roof_sheet_metal", "roof_tile", "roof_concrete"]
const TILE_AREAS := ["oasis", "oasis_outskirts", "azm_plains", "al_wasta"]
const TILE_WALL_STYLES := ["plain", "concrete", "brick", "sheet_metal", "chain_link", "rubble"]
const OBJECT_CATEGORIES := ["climb", "decor", "facility", "gathering", "item_spawn", "landmark", "npc", "sign", "transition"]
const TILE_CHECK_RULES := ["unknown_kind", "object_unwalkable", "transition_landing", "climb_landing", "void_open", "respawn_count", "sign_text", "wall_on_void", "unreachable", "roof_walkable", "spawn_table", "spawn_item"]
const TILE_CHECK_NOTE_RULES := ["unreachable"]
const SCENERY_PRIMITIVES := ["ladder", "stairs", "hatch", "stairs_top", "crate", "table", "lamp_post", "oil_lamp", "torch"]
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
	"shopkeeper_al_wasta": "npc",
	"shopkeeper_ephiri": "npc",
	"atticus_quin": "npc",
	"atum_musa": "npc",
	"mutant_raider": "npc",
	"big_mutant": "npc",
	"bong": "npc",
	"floating_eye": "npc",
	"mutant_crab": "npc",
	"mutant_giant": "npc",
	"signpost": "sign",
	"item_spawn": "item_spawn",
	"respawn_point": "landmark",
	"transition_oasis_to_outskirts": "transition",
	"transition_outskirts_to_oasis": "transition",
	"transition_outskirts_to_azm_plains": "transition",
	"transition_azm_plains_to_outskirts": "transition",
	"ladder_up": "climb",
	"ladder_down": "climb",
	"ladder_both": "climb",
	"stairs_up": "climb",
	"stairs_down": "climb",
	"crate": "decor",
	"table": "decor",
	"lamp_post": "decor",
	"oil_lamp": "decor",
	"torch": "decor",
}
const OBJECT_CATEGORY_LABELS := {
	"climb": "Ladder or stairs",
	"decor": "Decor",
	"facility": "Facility",
	"gathering": "Gathering node",
	"item_spawn": "Item spawn",
	"landmark": "Landmark",
	"npc": "NPC",
	"sign": "Sign",
	"transition": "Transition",
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
const OBJECT_KIND_CLIMB_RUNS := {
	"stairs_up": 3,
	"stairs_down": 3,
}
const CHUNK_ROTATION_STEPS := {
	0: [0, 1],
	1: [1, 0],
	2: [0, -1],
	3: [-1, 0],
}
const OBJECT_KIND_SCENERY := {
	"transition_oasis_to_outskirts": "map_transition",
	"transition_outskirts_to_oasis": "map_transition",
	"transition_outskirts_to_azm_plains": "map_transition",
	"transition_azm_plains_to_outskirts": "map_transition",
	"ladder_up": "ladder",
	"ladder_down": "hatch",
	"ladder_both": "ladder",
	"stairs_up": "stairs",
	"stairs_down": "stairs_top",
	"crate": "crate",
	"table": "table",
	"lamp_post": "lamp_post",
	"oil_lamp": "oil_lamp",
	"torch": "torch",
}
const OBJECT_KIND_PREVIEW := {
	"bank": ["bank_terminal", "station"],
	"foundry_furnace": ["furnace", "station"],
	"metalsmith_anvil": ["anvil", "station"],
	"rendering_cooker": ["rendering_cooker", "station"],
	"curing_chamber": ["curing_chamber", "station"],
	"gunsmith_bench": ["gunbench", "station"],
	"gastronomy_worktable": ["gastro_worktable", "station"],
	"rusty_pole": ["rusty_pole", "gatherable"],
	"metal_pole": ["metal_pole", "gatherable"],
	"copper_pole": ["copper_pole", "gatherable"],
	"lone_android": ["lone_android", "npc"],
	"shopkeeper_oasis": ["shopkeeper", "npc"],
	"shopkeeper_al_wasta": ["shopkeeper_al_wasta", "npc"],
	"shopkeeper_ephiri": ["shopkeeper_ephiri", "npc"],
	"atticus_quin": ["talkative_npc", "npc"],
	"atum_musa": ["atum_musa", "npc"],
	"mutant_raider": ["mutant_raider", "npc"],
	"big_mutant": ["big_mutant", "npc"],
	"bong": ["bong", "npc"],
	"floating_eye": ["floating_eye", "npc"],
	"mutant_crab": ["mutant_crab", "npc"],
	"mutant_giant": ["mutant_giant", "npc"],
	"signpost": ["generic", "sign"],
}
const CLIMB_PLANE_STEPS := {
	"up": 1,
	"down": -1,
}
const TILE_TABLE_FIELDS := {
	"areas": ["key", "note", "name", "desc"],
	"floor_types": ["key", "note", "roof"],
	"wall_styles": ["key", "note"],
	"decor_kinds": ["key", "note", "scenery"],
}

# Everything else.
const SUBSCRIBE_ALL := "all"
const ASSET_KEY_CHARACTER := "player_character"
const INVENTORY_SWAP_TEMPLATE := "swap {source} {target}"
const INVENTORY_DROP_KEY := "drop"
const TILE_KEY_TEMPLATE := "{x}:{y}"
const ENTITY_APPROACH_TEMPLATE := "goto ({x},{y}) then {command}"
const ENTITY_INSPECT_TEMPLATE := "inspect #{dbref}"
const TILE_WALK_TEMPLATE := "goto ({x},{y})"
const RUN_TOGGLE_COMMAND := "run"
const GOTO_PACE_WALK := "walk"
const GOTO_PACE_RUN := "run"
const TILE_PACED_WALK_TEMPLATE := "goto/{pace} ({x},{y})"
const ENTITY_PACED_APPROACH_TEMPLATE := "goto/{pace} ({x},{y}) then {command}"
const TILE_ACTION_PACED_KEY := "paced"
const ABILITY_STATE_READY := "ready"
const ABILITY_STATE_ACTIVE := "active"
const ABILITY_STATE_LOCKED := "locked"
const ABILITY_KIND_TOGGLE := "toggle"
const TIP_KEY := "tip"
const TIP_TITLE_KEY := "title"
const TIP_LINES_KEY := "lines"
const ENTITY_SPENT_KEY := "spent"
const ENTITY_FACING_KEY := "facing"
const ENTITY_LOOK_KEY := "look"
const ENTITY_BODY_TYPE_KEY := "body_type"
const ENTITY_FIGURE_COLORS_KEY := "figure_colors"
const ENTITY_WORN_KEY := "worn"
const ACTION_AMOUNT_PLACEHOLDER := "{amount}"
const ACTION_INPUT_KIND_QUANTITY := "quantity"
const ACTION_INPUT_KIND_KEY := "kind"
const ACTION_INPUT_MIN_KEY := "min"
const ACTION_INPUT_MAX_KEY := "max"
const ACTION_INPUT_LABEL_KEY := "label"
const ACTION_TEXT_PLACEHOLDER := "{text}"
const ACTION_INPUT_KIND_TEXT := "text"
const DRAG_SOURCE_TOKEN := "{source}"
const DRAG_TARGET_TOKEN := "{target}"
const CLIENT_INBOUND_BUFFER_BYTES := 4194304
const WORLD_MAP_ALPHABET := "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
const WORLD_MAP_COMMAND := "worldmap"
const LOGIN_ACCOUNT_KEY := "account"
const LOGIN_TOKEN_KEY := "token"
const LOGIN_RESUME_TEMPLATE := "resume {account} {token}"
const REMEMBER_COMMAND := "remember"
const FORGET_COMMAND := "forget"

# Derived sets, so a client can iterate rather than
# rebuild these from the names above.
const SUBSCRIBABLE_CHANNELS := ["blackout_aura", "blackout_chunk", "blackout_combat", "blackout_face", "blackout_moment", "blackout_tick_perf", "blackout_walk", "blackout_world_map", "blackout_world_map_chunk", "blackout_xp", "char_abilities", "char_avatar", "char_chat", "char_combat", "char_items_list", "char_popup", "char_quests", "char_skills", "char_status", "char_summary", "char_vitals", "room_add_player", "room_info", "room_players", "room_players_delta", "room_remove_player"]
const ITEM_FAMILIES := ["armor", "corpse", "crafting_material", "crafting_tool", "currency", "food", "jewellery", "weapon"]
const MESSAGE_TYPES := ["channel", "combat", "commerce", "crafting", "dialogue", "examine", "gathering", "general", "help", "inventory", "look", "menu", "move", "page", "pose", "progression", "quest", "room", "say", "system", "teleport", "vitals", "whisper", "xymap"]
