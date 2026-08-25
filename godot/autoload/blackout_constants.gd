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
const KIND_NONE := "none"

# Everything else.
const SUBSCRIBE_ALL := "all"
const ASSET_KEY_CHARACTER := "player_character"
const ROOM_KIND_TRANSITION := "map_transition"
const ROOM_KIND_DEFAULT := "default"
const INVENTORY_SWAP_TEMPLATE := "swap {source} {target}"
const TILE_KEY_TEMPLATE := "{x}:{y}"

# Derived sets, so a client can iterate rather than
# rebuild these from the names above.
const SUBSCRIBABLE_CHANNELS := ["blackout_aura", "blackout_combat", "blackout_map", "char_avatar", "char_items_list", "char_status", "char_summary", "char_vitals", "room_add_player", "room_info", "room_players", "room_remove_player"]
const ITEM_FAMILIES := ["armor", "crafting_material", "crafting_tool", "currency", "jewellery", "weapon"]
