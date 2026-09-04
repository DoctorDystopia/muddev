# GENERATED FILE -- DO NOT EDIT.
#
# Rendered from systems/statefeed/constants.py by
# systems/statefeed/clientexport.py. Change the Python and re-run:
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
const CH_PLAYER_ADD := "room_add_player"
const CH_PLAYER_REMOVE := "room_remove_player"
const CH_CHAR_AVATAR := "char_avatar"
const CH_CHAR_VITALS := "char_vitals"
const CH_CHAR_STATUS := "char_status"
const CH_CHAR_SUMMARY := "char_summary"
const CH_CHAR_ITEMS := "char_items_list"
const CH_CHAR_QUESTS := "char_quests"
const CH_CHAR_SKILLS := "char_skills"
const CH_MAP := "blackout_map"
const CH_COMBAT := "blackout_combat"
const CH_AURA := "blackout_aura"
const CH_SUBSCRIBED := "blackout_subscribed"

# Asset kinds -- the client's mesh `family` vocabulary.
const FAMILY_ITEM := "item"
const FAMILY_NPC := "npc"
const FAMILY_CHARACTER := "character"
const FAMILY_ROOM := "room"
const FAMILY_STATION := "station"
const FAMILY_GATHERABLE := "gatherable"
const FAMILY_GENERIC := "generic"

# Item families.
const ITEM_FAMILY_WEAPON := "weapon"
const ITEM_FAMILY_ARMOR := "armor"
const ITEM_FAMILY_JEWELLERY := "jewellery"
const ITEM_FAMILY_MATERIAL := "crafting_material"
const ITEM_FAMILY_TOOL := "crafting_tool"
const ITEM_FAMILY_CURRENCY := "currency"
const ITEM_FAMILY_GENERIC := "generic"

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

# Everything else.
const SUBSCRIBE_ALL := "all"
const ASSET_KEY_CHARACTER := "player_character"
const ROOM_KIND_TRANSITION := "map_transition"
const ROOM_KIND_DEFAULT := "default"
const INVENTORY_SWAP_TEMPLATE := "swap {source} {target}"
const TILE_KEY_TEMPLATE := "{x}:{y}"
const ACTION_AMOUNT_PLACEHOLDER := "{amount}"
const ACTION_INPUT_KIND_QUANTITY := "quantity"
const ACTION_INPUT_KIND_KEY := "kind"
const ACTION_INPUT_MIN_KEY := "min"
const ACTION_INPUT_MAX_KEY := "max"
const ACTION_INPUT_LABEL_KEY := "label"
const CLIENT_INBOUND_BUFFER_BYTES := 1048576

# Derived sets, so a client can iterate rather than
# rebuild these from the names above.
const SUBSCRIBABLE_CHANNELS := ["blackout_aura", "blackout_combat", "blackout_map", "char_avatar", "char_items_list", "char_quests", "char_skills", "char_status", "char_summary", "char_vitals", "room_add_player", "room_info", "room_players", "room_remove_player"]
const ITEM_FAMILIES := ["armor", "crafting_material", "crafting_tool", "currency", "jewellery", "weapon"]
const MESSAGE_TYPES := ["channel", "combat", "commerce", "crafting", "dialogue", "examine", "gathering", "general", "help", "inventory", "look", "move", "pose", "progression", "quest", "room", "say", "system", "teleport", "vitals", "whisper", "xymap"]
