class_name InventoryState
extends RefCounted
## What you are carrying and what you are wearing, from `char_items_list`.
##
## The third model beside [WorldState] and [CharState], and it exists for the
## same reason: the shape of the feed and the float boundary belong somewhere
## that is not the thing drawing pixels.
##
## ## A snapshot, and it must stay one
##
## Every message replaces everything. The server's own reasoning, from
## `payloads.py`, is worth not rediscovering: inventory mutation points are
## many and undisciplined — `InventoryHandler.add_item` merges stacks with a
## bare `existing.quantity += additional` and fires no hook, crafting consumes
## materials directly, banking moves items in bulk, equipping displaces items
## back into the grid. A delta protocol would need an emit at every one of them
## and would rot at the first one anybody forgot. **A missed delta on an NPC
## three tiles away is a cosmetic ghost; a missed delta on your own inventory
## is a phantom item you will try to click.**
##
## So: do not "optimise" this into deltas. Replacing a couple of kilobytes
## cannot desync.
##
## ## `slot` is polymorphic, and that is the trap
##
##     carried  -> a 0-based ARRAY INDEX, an int
##     equipped -> a WieldLocation VALUE, a string
##
## They share a field because both answer "which frame does this sit in", which
## is what lets one drag implementation serve both grids. But a client that
## coerces the whole payload would turn `"weapon_hand"` into 0 and quietly file
## every worn item in the first carried slot.
##
## Player-facing slot NUMBERS are 1-based. `serialize_inventory` does the same
## +1 when it builds its action commands, so the two agree; see
## [method swap_command].
##
## ## Empty frames ship, and are iterated
##
## `equip_slots` is every wield location in display order, occupied or not.
## Adding one to `WieldLocation` must light up a new frame with no client edit,
## so this never restates `SLOT_DISPLAY_ORDER`.

const _Const := preload("res://autoload/blackout_constants.gd")

## Smallest amount a quantity prompt may be set to, whatever the server said.
##
## A floor rather than a trusted value: the server sends a `min` and it is 1,
## but a prompt that could be driven to zero is one where confirming does
## nothing, which reads as a broken dialog rather than as a declined action.
const ACTION_AMOUNT_FLOOR := 1

signal changed

## How many carried frames to draw, and how many are full.
var slots_total := 0
var slots_used := 0

## slot index (int) -> row dictionary. Only OCCUPIED slots appear: the server
## omits empties rather than sending rows of defaults, so a stale id it has
## already nulled cannot reach us looking like an item.
var carried: Dictionary = {}

## WieldLocation value (String) -> row dictionary, for what is worn.
var equipped: Dictionary = {}

## [{slot, label}, ...] in display order. Every frame, occupied or not.
var equip_frames: Array = []

## False until a payload has arrived, so an empty grid at login is not drawn as
## "you are carrying nothing".
var has_data := false


## Fold one `char_items_list` message in, replacing everything.
##
## Returns true when the channel was ours, matching [CharState.ingest] so the
## console can route both the same way.
func ingest(channel: String, payload: Dictionary) -> bool:
	if channel != _Const.CH_CHAR_ITEMS:
		return false

	slots_total = int(payload.get("slots_total", 0))
	slots_used = int(payload.get("slots_used", 0))
	carried = _index_carried(payload.get("items", []))
	equipped = _index_equipped(payload.get("equipped", []))
	equip_frames = _frames(payload.get("equip_slots", []))
	has_data = true

	changed.emit()

	return true


## The row in one carried slot, or an empty dictionary when it is free.
func carried_at(slot_index: int) -> Dictionary:
	return carried.get(slot_index, {})


## The row worn in one equipment slot, or an empty dictionary.
func equipped_at(slot_value: String) -> Dictionary:
	return equipped.get(slot_value, {})


## The commands the SERVER named for one row, as [{label, command}].
##
## Never composed here. `serialize_inventory` sends whole commands precisely so
## a client cannot invent a verb — the browser pane had a verb table once, it
## was wrong within a week, and a superuser walked off with a Foundry Furnace.
func actions_for(row: Dictionary) -> Array:
	return row.get("actions", [])


## Whether a carried row may be dropped into one equipment frame.
##
## A comparison of two SERVER-supplied values, not a rule invented here: the
## row's own `equip_slot` against the frame's slot. An item with no
## `equip_slot` is not equipment and fits nowhere.
func can_equip(row: Dictionary, frame_slot: String) -> bool:
	var slot := str(row.get("equip_slot", ""))

	if slot.is_empty():
		return false

	return slot == frame_slot


## The command for dragging one carried slot onto another.
##
## THE ONE COMMAND THIS CLIENT COMPOSES, and the only one it can: `swap` takes
## two endpoints and only the drag knows both, so pre-naming it per item would
## be every pair of slots to express one verb. The SPELLING is still the
## server's — [code]INVENTORY_SWAP_TEMPLATE[/code] is generated — so the verb
## and the argument order have one owner even though the gesture does not.
##
## Both indices are converted to the player's 1-based numbering here, which is
## the same +1 `serialize_inventory` applies when it builds its own commands.
## Returns "" for a no-op drag onto the same slot.
func swap_command(from_index: int, to_index: int) -> String:
	if from_index == to_index:
		return ""

	return _Const.INVENTORY_SWAP_TEMPLATE \
		.replace("{source}", str(from_index + 1)) \
		.replace("{target}", str(to_index + 1))


## The quantity prompt one of the server's actions asks for, or an empty
## dictionary when it asks for nothing.
##
## An action carrying an `input` block is one whose AMOUNT only this client
## holds — Sell X, Deposit X — the same split [method swap_command] describes
## for a drag. Everything else the server named whole.
##
## Read as a question rather than as a flag so the caller gets the bounds and
## the wording in the same call it learns there is a prompt at all.
func action_prompt(action: Dictionary) -> Dictionary:
	var prompt: Variant = action.get("input")

	if typeof(prompt) != TYPE_DICTIONARY:
		return {}

	if str(prompt.get(_Const.ACTION_INPUT_KIND_KEY, "")) \
			!= _Const.ACTION_INPUT_KIND_QUANTITY:
		return {}

	var maximum := int(prompt.get(_Const.ACTION_INPUT_MAX_KEY, 1))
	var minimum := int(prompt.get(
		_Const.ACTION_INPUT_MIN_KEY, ACTION_AMOUNT_FLOOR))

	return {
		_Const.ACTION_INPUT_MIN_KEY: maxi(minimum, ACTION_AMOUNT_FLOOR),
		_Const.ACTION_INPUT_MAX_KEY: maxi(maximum, minimum),
		_Const.ACTION_INPUT_LABEL_KEY: str(
			prompt.get(_Const.ACTION_INPUT_LABEL_KEY, "")),
	}


## What to send for one of the server's actions, given the amount the player
## chose.
##
## Three cases, and the middle one is the whole reason this exists:
##
##     a non-empty `command`  -> send it verbatim, `amount` ignored
##     a prompted action      -> substitute into its `template`
##     anything else          -> "", the server declining
##
## **The empty string is not an error and must never be guessed at.** An action
## with no command is the server saying "do not offer this", exactly as an
## empty tile action is, and a prompted action on a client that could not
## prompt would arrive here as one. Returning "" rather than a half-built
## string is what makes the payload's contract degrade safely.
##
## The placeholder is [code]ACTION_AMOUNT_PLACEHOLDER[/code], generated from
## the server's constants, never a literal here — the same rule
## [method swap_command] follows for its two.
func action_command(action: Dictionary, amount: int = 0) -> String:
	var command := str(action.get("command", ""))

	if not command.is_empty():
		return command

	if action_prompt(action).is_empty():
		return ""

	var template := str(action.get("template", ""))

	if template.is_empty():
		return ""

	return template.replace(_Const.ACTION_AMOUNT_PLACEHOLDER, str(amount))


## Carried rows keyed by their slot index.
##
## Only the `slot` field crosses the float boundary, and only here, where it is
## known to be a carried row and therefore known to be a number.
func _index_carried(rows: Variant) -> Dictionary:
	var indexed: Dictionary = {}

	if typeof(rows) != TYPE_ARRAY:
		return indexed

	for row: Variant in rows:
		if typeof(row) != TYPE_DICTIONARY:
			continue

		indexed[int(row.get("slot", 0))] = _normalise(row)

	return indexed


## Worn rows keyed by their WieldLocation value.
##
## `slot` is a STRING here and is deliberately not passed through `int()`. That
## is the whole reason this is a separate routine rather than a flag on one.
func _index_equipped(rows: Variant) -> Dictionary:
	var indexed: Dictionary = {}

	if typeof(rows) != TYPE_ARRAY:
		return indexed

	for row: Variant in rows:
		if typeof(row) != TYPE_DICTIONARY:
			continue

		indexed[str(row.get("slot", ""))] = _normalise(row)

	return indexed


## Convert the numeric fields every row carries, leaving `slot` alone.
func _normalise(row: Dictionary) -> Dictionary:
	var copy := row.duplicate(true)

	copy["id"] = int(row.get("id", 0))
	copy["quantity"] = int(row.get("quantity", 1))
	copy["stackable"] = bool(row.get("stackable", false))
	copy["name"] = str(row.get("name", ""))
	copy["asset"] = str(row.get("asset", ""))
	copy["family"] = str(row.get("family", ""))
	copy["equip_slot"] = str(row.get("equip_slot", ""))

	return copy


## The empty-frame list, defended against a malformed payload.
func _frames(rows: Variant) -> Array:
	var frames: Array = []

	if typeof(rows) != TYPE_ARRAY:
		return frames

	for row: Variant in rows:
		if typeof(row) != TYPE_DICTIONARY:
			continue

		frames.append({
			"slot": str(row.get("slot", "")),
			"label": str(row.get("label", "")),
		})

	return frames
