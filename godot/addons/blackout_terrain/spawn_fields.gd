@tool
class_name SpawnFields
extends VBoxContainer
## The fields of the spawn of an item spawn object (10/21/2026): the item,
## the quantity range, and the respawn in ticks.
##
## The Object tool of the Paint tab has one, for a new object. The Objects
## tab has one, for the selected object. Each change by the author sends
## [signal changed]. A fill by [method set_spawn] sends nothing.
##
## The items come from [SpawnItems]. An item that does not stack takes one
## unit (the `spawn_item` rule of `tile_checks.py`). Thus, the quantity
## fields lock at one for it. The respawn shows its time in seconds too,
## from `TICK_SECONDS`.

signal changed

const _Const := preload("res://autoload/blackout_constants.gd")
const _Fields := preload("res://addons/blackout_terrain/terrain_fields.gd")

## The respawn of a new spawn in the editor, in ticks: one minute. The
## server reads the respawn of each object, so this is a start value only.
const DEFAULT_RESPAWN_TICKS := 100

var _item := OptionButton.new()
var _low := SpinBox.new()
var _high := SpinBox.new()
var _respawn := SpinBox.new()
var _seconds := Label.new()

## True while [method set_spawn] fills the fields, so they send nothing.
var _filling := false


func _init() -> void:
	var unit: float = _Const.SPAWN_QUANTITY_UNIT
	var quantity := HBoxContainer.new()

	refill_items()
	_item.item_selected.connect(func(_index: int) -> void: _on_item())
	_Fields.row(self, "Item", _item, "The item that lies on the tile.")

	for pair: Array in [[_low, "from "], [_high, "to "]]:
		var box: SpinBox = pair[0]

		_Fields.spin(box, unit, _Const.SPAWN_QUANTITY_MAX, 1.0, unit)
		box.prefix = pair[1]
		box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		quantity.add_child(box)

	_low.value_changed.connect(func(_value: float) -> void: _on_bounds(_low))
	_high.value_changed.connect(func(_value: float) -> void: _on_bounds(_high))
	_Fields.row(self, "Quantity", quantity,
		"Each new item rolls a quantity in this range. An item that does not stack takes one.")
	_Fields.spin(_respawn, _Const.SPAWN_RESPAWN_MIN, _Const.SPAWN_RESPAWN_MAX, 1.0,
		DEFAULT_RESPAWN_TICKS)
	_respawn.suffix = "ticks"
	_respawn.value_changed.connect(func(_value: float) -> void: _on_respawn())
	_Fields.row(self, "Respawn", _respawn,
		"Game ticks from the time the item leaves the tile to the next item.")
	add_child(_seconds)
	_show_seconds()
	_lock_quantity()


# ─── Reading and filling ────────────────────────────────────────────────────

## The spawn that the fields show, in the form of the chunk file: the
## quantity key only for a range above one unit.
func spawn() -> Dictionary:
	var made := {_Const.SPAWN_ITEM_KEY: _Fields.text_of(_item)}
	var low := int(_low.value)
	var high := int(_high.value)

	if high > _Const.SPAWN_QUANTITY_UNIT:
		made[_Const.SPAWN_QUANTITY_KEY] = [low, high]

	made[_Const.SPAWN_RESPAWN_KEY] = int(_respawn.value)

	return made


## Show `spawn` in the fields. An empty spawn shows the first item, one
## unit, and [constant DEFAULT_RESPAWN_TICKS]. The fields send nothing.
func set_spawn(spawn: Dictionary) -> void:
	var bounds: Array = ChunkFile.spawn_quantity(spawn)

	_filling = true
	_Fields.select_text(_item, str(spawn.get(_Const.SPAWN_ITEM_KEY, _Fields.text_of(_item))))
	_low.value = bounds[0]
	_high.value = bounds[1]
	_respawn.value = spawn.get(_Const.SPAWN_RESPAWN_KEY, DEFAULT_RESPAWN_TICKS)
	_lock_quantity()
	_show_seconds()
	_filling = false


## Fill the Item list again from the item list of the game. The choice
## stays when the list still has it.
func refill_items() -> void:
	_Fields.refill(_item, Array(SpawnItems.game().keys()))


# ─── Changes ────────────────────────────────────────────────────────────────

func _on_item() -> void:
	_lock_quantity()
	_send()


## Keep the low end at or under the high end: the field that moved wins.
func _on_bounds(moved: SpinBox) -> void:
	if _low.value > _high.value:
		if moved == _low:
			_high.set_value_no_signal(_low.value)
		else:
			_low.set_value_no_signal(_high.value)

	_send()


func _on_respawn() -> void:
	_show_seconds()
	_send()


func _send() -> void:
	if not _filling:
		changed.emit()


## An item that does not stack takes one unit, so its range locks at one.
func _lock_quantity() -> void:
	var stacks := SpawnItems.game().stacks(_Fields.text_of(_item))
	var unit: float = _Const.SPAWN_QUANTITY_UNIT

	if not stacks:
		_low.set_value_no_signal(unit)
		_high.set_value_no_signal(unit)

	_low.editable = stacks
	_high.editable = stacks


func _show_seconds() -> void:
	_seconds.text = "%.1f seconds" % (_respawn.value * _Const.TICK_SECONDS)
