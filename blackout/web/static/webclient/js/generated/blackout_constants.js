// GENERATED FILE -- DO NOT EDIT.
//
// Rendered from systems/statefeed/constants.py by
// systems/statefeed/clientexport.py. Change the Python and re-run:
//
//     python scripts/export_client_constants.py
//
// Every name below is a fact the SERVER owns. Presentation -- colours,
// meshes, camera, the model registry -- is the client's own and is
// deliberately not generated; see the module docstring in clientexport.py.
//
// A test asserts the committed copy of this file matches a fresh render,
// so an edit here fails the suite rather than surviving quietly.

// Feed channels.
export const CH_ROOM_INFO = "room_info";
export const CH_ROOM_PLAYERS = "room_players";
export const CH_PLAYER_ADD = "room_add_player";
export const CH_PLAYER_REMOVE = "room_remove_player";
export const CH_CHAR_AVATAR = "char_avatar";
export const CH_CHAR_VITALS = "char_vitals";
export const CH_CHAR_STATUS = "char_status";
export const CH_CHAR_SUMMARY = "char_summary";
export const CH_CHAR_ITEMS = "char_items_list";
export const CH_CHAR_QUESTS = "char_quests";
export const CH_CHAR_SKILLS = "char_skills";
export const CH_MAP = "blackout_map";
export const CH_COMBAT = "blackout_combat";
export const CH_AURA = "blackout_aura";
export const CH_SUBSCRIBED = "blackout_subscribed";

// Asset kinds -- the client's mesh `family` vocabulary.
export const FAMILY_ITEM = "item";
export const FAMILY_NPC = "npc";
export const FAMILY_CHARACTER = "character";
export const FAMILY_ROOM = "room";
export const FAMILY_STATION = "station";
export const FAMILY_GATHERABLE = "gatherable";
export const FAMILY_GENERIC = "generic";

// Item families.
export const ITEM_FAMILY_WEAPON = "weapon";
export const ITEM_FAMILY_ARMOR = "armor";
export const ITEM_FAMILY_JEWELLERY = "jewellery";
export const ITEM_FAMILY_MATERIAL = "crafting_material";
export const ITEM_FAMILY_TOOL = "crafting_tool";
export const ITEM_FAMILY_CURRENCY = "currency";
export const ITEM_FAMILY_GENERIC = "generic";

// Tile action kinds -- what a click does to a walk in progress.
export const KIND_STEP = "step";
export const KIND_WALK = "walk";
export const KIND_LOOK = "look";
export const KIND_CANCEL = "cancel";

// Text routing -- what a line of game text is ABOUT. Which tab shows it is the client's own.
export const MESSAGE_TYPE_KEY = "type";
export const MSG_GENERAL = "general";
export const MSG_LOOK = "look";
export const MSG_POSE = "pose";
export const MSG_SAY = "say";
export const MSG_WHISPER = "whisper";
export const MSG_HELP = "help";
export const MSG_EXAMINE = "examine";
export const MSG_MOVE = "move";
export const MSG_TELEPORT = "teleport";
export const MSG_ROOM = "room";
export const MSG_MAP = "xymap";
export const MSG_COMBAT = "combat";
export const MSG_VITALS = "vitals";
export const MSG_PROGRESSION = "progression";
export const MSG_INVENTORY = "inventory";
export const MSG_CRAFTING = "crafting";
export const MSG_GATHERING = "gathering";
export const MSG_QUEST = "quest";
export const MSG_COMMERCE = "commerce";
export const MSG_DIALOGUE = "dialogue";
export const MSG_CHANNEL = "channel";
export const MSG_SYSTEM = "system";

// Everything else.
export const SUBSCRIBE_ALL = "all";
export const ASSET_KEY_CHARACTER = "player_character";
export const ROOM_KIND_TRANSITION = "map_transition";
export const ROOM_KIND_DEFAULT = "default";
export const INVENTORY_SWAP_TEMPLATE = "swap {source} {target}";
export const TILE_KEY_TEMPLATE = "{x}:{y}";

// Derived sets, so a client can iterate rather than
// rebuild these from the names above.
export const SUBSCRIBABLE_CHANNELS = ["blackout_aura", "blackout_combat", "blackout_map", "char_avatar", "char_items_list", "char_quests", "char_skills", "char_status", "char_summary", "char_vitals", "room_add_player", "room_info", "room_players", "room_remove_player"];
export const ITEM_FAMILIES = ["armor", "crafting_material", "crafting_tool", "currency", "jewellery", "weapon"];
export const MESSAGE_TYPES = ["channel", "combat", "commerce", "crafting", "dialogue", "examine", "gathering", "general", "help", "inventory", "look", "move", "pose", "progression", "quest", "room", "say", "system", "teleport", "vitals", "whisper", "xymap"];
