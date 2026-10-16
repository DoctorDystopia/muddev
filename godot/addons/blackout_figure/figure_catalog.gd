@tool
class_name FigureCatalog
extends RefCounted
## The item catalog of the figure workbench: each item that a character can
## equip, and each slot (DESIGN-0014 section 8.1, Phase W3).
##
## The server owns each fact here. `export_client_constants.py` renders
## `item_catalog.json` from `ITEM_DB` and the slot constants, and a Python
## test fails when the file is stale. This class only reads the file. Never
## edit the file by hand.
##
## ## The file
##
##     format      1
##     slots       [{key, label, clears}, ...], in the order of the screens
##     items       [{key, name, slot, tool_type, tier, family}, ...]
##     tool_types  each tool type of the server (Phase W6)
##     npcs        [{key, name, outfit}, ...]: each NPC def with an outfit
##                 (Phase W6). `outfit` is slot -> asset key.
##
## `clears` names each other slot that an item in this slot empties. A
## two-handed weapon clears the two hand slots. [method wear] follows it, so
## the outfit bar holds only an outfit that a character can wear.
##
## ## An outfit
##
## An outfit is the worn record of the workbench: slot -> asset key. An
## outfit can also hold the key of a slot in that slot. The slot shape then
## draws, so the author can see it with no item.
##
## Only the workbench reads the catalog. The game gets the worn record of a
## character from the server.

## The newest format that this reader knows.
const FORMAT := 1

const CATALOG_PATH := "res://addons/blackout_figure/item_catalog.json"

var data := {}

## Why the catalog does not read, or "" for a catalog that reads.
var error := ""

## Item key -> its row.
var _items := {}

## Slot key -> its row.
var _slots := {}

## NPC def key -> its row.
var _npcs := {}


# ─── Reading ────────────────────────────────────────────────────────────────

## The catalog of a parsed catalog file. Check [member error] after.
static func from_data(parsed: Variant) -> FigureCatalog:
	var catalog := FigureCatalog.new()

	if typeof(parsed) != TYPE_DICTIONARY or parsed.is_empty():
		catalog.error = "the item catalog must hold one JSON object"
		return catalog

	catalog.error = _problem(parsed)

	if catalog.error.is_empty():
		catalog.data = parsed
		catalog._build_index()

	return catalog


## Read the catalog file. Check [member error] after.
static func read_file(path := CATALOG_PATH) -> FigureCatalog:
	var text := FileAccess.get_file_as_string(path)
	var parser := JSON.new()

	if text.is_empty() or parser.parse(text) != OK:
		var refused := FigureCatalog.new()

		refused.error = "cannot read %s. Run export_client_constants.py" % path
		return refused

	return from_data(parser.data)


# ─── The facts of the catalog ───────────────────────────────────────────────

## The slot keys, in the order of the equipment screens.
func slot_keys() -> PackedStringArray:
	var keys := PackedStringArray()

	for row: Dictionary in data.get("slots", []):
		keys.append(row["key"])

	return keys


func has_slot(slot: String) -> bool:
	return _slots.has(slot)


## The name of a slot for the author, or the key of an unknown slot.
func label_of(slot: String) -> String:
	return _slots.get(slot, {}).get("label", slot)


## The other slots that an item in `slot` empties.
func clears(slot: String) -> Array:
	return _slots.get(slot, {}).get("clears", [])


## The item rows, sorted by key.
func items() -> Array:
	return data.get("items", [])


func has_item(key: String) -> bool:
	return _items.has(key)


## The row of one item, or an empty dictionary.
func item(key: String) -> Dictionary:
	return _items.get(key, {})


## The slot of one item, or "".
func slot_of(key: String) -> String:
	return item(key).get("slot", "")


## The rows of the items of one slot, sorted by tier and then by key.
func items_of(slot: String) -> Array:
	var rows := []

	for row: Dictionary in items():
		if row["slot"] == slot:
			rows.append(row)

	rows.sort_custom(func(first: Dictionary, second: Dictionary) -> bool:
		if first["tier"] != second["tier"]:
			return first["tier"] < second["tier"]

		return first["key"] < second["key"])

	return rows


## The tool type of one item, or "" for an item with none.
func tool_type_of(key: String) -> String:
	return item(key).get("tool_type", "")


## Each tool type of the server, in sorted order: the `tool_types` list of
## the file, and the tool type of each item. A stance keys on a tool type
## ([FigureStances]). A catalog of before Phase W6 has no list, and it
## gives the tool types of its items only.
func tool_types() -> PackedStringArray:
	var found := {}

	for tool_type: String in data.get("tool_types", []):
		found[tool_type] = true

	for row: Dictionary in items():
		if not str(row.get("tool_type", "")).is_empty():
			found[row["tool_type"]] = true

	var names := PackedStringArray(found.keys())

	names.sort()

	return names


## The key of each NPC def that has an outfit, in the order of the file
## (Phase W6). The server owns the outfit of an NPC (decision 8).
func npc_keys() -> PackedStringArray:
	var keys := PackedStringArray()

	for row: Dictionary in data.get("npcs", []):
		keys.append(row["key"])

	return keys


## The name of one NPC def for the author, or its key.
func npc_name(key: String) -> String:
	return _npcs.get(key, {}).get("name", key)


## The outfit of one NPC def: slot -> asset key. An empty dictionary for an
## NPC def that the catalog does not have.
func npc_outfit(key: String) -> Dictionary:
	return _npcs.get(key, {}).get("outfit", {}).duplicate()


## The tool type of each item of an outfit, in the order of the slots. An
## item with no tool type is not in the list.
func outfit_tool_types(outfit: Dictionary) -> Array:
	var found := []

	for slot: String in slot_keys():
		var tool_type := tool_type_of(outfit.get(slot, ""))

		if not tool_type.is_empty():
			found.append(tool_type)

	return found


## Asset key -> family, for [method FigureOutfit.looks_for].
func families() -> Dictionary:
	var found := {}

	for row: Dictionary in items():
		found[row["key"]] = row["family"]

	return found


# ─── An outfit ──────────────────────────────────────────────────────────────

## `outfit` with `asset_key` in `slot`, and with each slot empty that the
## item clears. An empty `asset_key` empties the slot. Returns a new
## dictionary.
func wear(outfit: Dictionary, slot: String, asset_key: String) -> Dictionary:
	var out := outfit.duplicate()

	if asset_key.is_empty():
		out.erase(slot)
		return out

	for cleared: String in clears(slot):
		out.erase(cleared)

	out[slot] = asset_key

	return out


## `outfit` with only the entries that this catalog knows: a slot of the
## catalog that holds its own key or an item of that slot. Returns a new
## dictionary. An outfit from the options file can name an item of the past.
##
## Each entry goes in through [method wear], in the order of the slots.
## Thus, the outfit holds no two items that clear each other: a later slot
## of the order empties an earlier one. Two hands and a main hand cannot
## both hold.
func valid_outfit(outfit: Dictionary) -> Dictionary:
	var out := {}

	for slot: String in slot_keys():
		var asset_key: Variant = outfit.get(slot)

		if typeof(asset_key) != TYPE_STRING:
			continue

		if asset_key == slot or slot_of(asset_key) == slot:
			out = wear(out, slot, asset_key)

	return out


# ─── The form of the catalog file ───────────────────────────────────────────

## Why a parsed catalog file has a bad form, or "".
static func _problem(parsed: Dictionary) -> String:
	var format: Variant = parsed.get("format")

	if (typeof(format) != TYPE_INT and typeof(format) != TYPE_FLOAT) or format < 1:
		return "the item catalog needs a format number"

	if format > FORMAT:
		return "format %d is newer than this reader (format %d)" % [format, FORMAT]

	if typeof(parsed.get("slots")) != TYPE_ARRAY or typeof(parsed.get("items")) != TYPE_ARRAY:
		return "the item catalog needs slots and items"

	for row: Variant in parsed["slots"]:
		if typeof(row) != TYPE_DICTIONARY or typeof(row.get("key")) != TYPE_STRING \
				or not FigureJson.is_strings(row.get("clears", [])):
			return "each slot of the item catalog needs a key"

	for row: Variant in parsed["items"]:
		if typeof(row) != TYPE_DICTIONARY:
			return "each item of the item catalog must be a table"

		for field: String in ["key", "name", "slot", "family"]:
			if typeof(row.get(field)) != TYPE_STRING:
				return "each item of the item catalog needs a %s" % field

	return _more_problem(parsed)


## Why a table of Phase W6 has a bad form, or "". The tables are the tool
## types of the server, and the NPC defs with an outfit. A file with no such
## table reads.
static func _more_problem(parsed: Dictionary) -> String:
	if not FigureJson.is_strings(parsed.get("tool_types", [])):
		return "tool_types must be a list of names"

	if typeof(parsed.get("npcs", [])) != TYPE_ARRAY:
		return "npcs must be a list"

	for row: Variant in parsed.get("npcs", []):
		if typeof(row) != TYPE_DICTIONARY or typeof(row.get("key")) != TYPE_STRING \
				or typeof(row.get("name")) != TYPE_STRING \
				or typeof(row.get("outfit")) != TYPE_DICTIONARY:
			return "each NPC def of the item catalog needs a key, a name, and an outfit"

	return ""


func _build_index() -> void:
	for row: Dictionary in data["slots"]:
		_slots[row["key"]] = row

	for row: Dictionary in data["items"]:
		if not row.has("tier"):
			row["tier"] = 0

		row["tier"] = int(row["tier"])
		_items[row["key"]] = row

	for row: Dictionary in data.get("npcs", []):
		_npcs[row["key"]] = row
