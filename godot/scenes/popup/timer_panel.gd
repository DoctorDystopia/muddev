class_name TimerPanel
extends VBoxContainer
## The side panel of a station whose work ends later: one row for each slot,
## with a bar, the time left, and "Ready" when it can be collected. The curing
## chamber is the first such station.
##
## ## It knows no station
##
## The server sends `{title, total, slots}` in [member PopupState.timers], and
## this draws exactly that. A second timed station is a second server-side
## `timer_report` and no edit here. Free slots are `total` less the occupied
## ones, drawn as empty rows, so the player sees the room left.
##
## ## The bar moves between snapshots, and the server says when it is done
##
## A snapshot carries `remaining` at the moment it landed. The panel counts it
## down with [method PopupState.seconds_left], a few times a second, so the
## bar moves. At zero it shows [constant DUE_TEXT], not "Ready": `ready` is the
## server's word, and the delayed refresh the server schedules at the deadline
## is what sends it. The Collect button is the pop-up's footer, from the
## server's actions.

## How often the bars move, in seconds. A bar a few hundred pixels wide over a
## cure of minutes moves less than a pixel between two ticks at this rate.
const TICK_SECONDS := 0.25

## The panel's width, in pixels. Wide enough for "cured mutant raider steak".
const PANEL_WIDTH := 220.0

const READY_TEXT := "Ready - collect"
const DUE_TEXT := "Finishing..."
const EMPTY_TEXT := "Empty slot"

## The rows now drawn, one {bar, time} for each occupied slot, in slot order.
var _rows: Array = []
var _state: PopupState
var _since_tick := 0.0
var _title: Label


func _init() -> void:
	custom_minimum_size = Vector2(PANEL_WIDTH, 0)
	visible = false
	set_process(false)


## Draw the model's timers, or hide when it has none.
func show_timers(state: PopupState) -> void:
	_state = state
	_clear()
	visible = state.has_timers()
	set_process(visible)

	if not visible:
		return

	_title = Label.new()
	_title.theme_type_variation = &"SectionHeading"
	_title.text = str(state.timers.get("title", ""))
	add_child(_title)

	var slots: Array = state.timers.get("slots", [])

	for slot: Dictionary in slots:
		_add_slot_row(slot)

	var free := int(state.timers.get("total", 0)) - slots.size()

	for _index: int in range(maxi(free, 0)):
		_add_empty_row()

	_tick()


## The text of each row's time label, in slot order. For tests.
func row_texts() -> PackedStringArray:
	var texts := PackedStringArray()

	for row: Dictionary in _rows:
		texts.append((row["time"] as Label).text)

	return texts


## The bar of each occupied row, in slot order. For tests.
func bars() -> Array:
	var found: Array = []

	for row: Dictionary in _rows:
		found.append(row["bar"])

	return found


func _process(delta: float) -> void:
	_since_tick += delta

	if _since_tick < TICK_SECONDS:
		return

	_since_tick = 0.0
	_tick()


func _add_slot_row(slot: Dictionary) -> void:
	var name_label := Label.new()
	name_label.theme_type_variation = &"RowValue"
	name_label.text = str(slot.get("name", ""))
	name_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	add_child(name_label)

	var bar := ProgressBar.new()
	bar.show_percentage = false
	bar.max_value = 1.0
	bar.step = 0.0
	add_child(bar)

	var time := Label.new()
	time.theme_type_variation = &"CellDetail"
	add_child(time)

	_rows.append({"slot": slot, "bar": bar, "time": time})


func _add_empty_row() -> void:
	var label := Label.new()
	label.theme_type_variation = &"CellDetail"
	label.text = EMPTY_TEXT
	add_child(label)


## Move every bar to now.
func _tick() -> void:
	if _state == null:
		return

	var now := Time.get_ticks_msec()

	for row: Dictionary in _rows:
		_draw_row(row, now)


func _draw_row(row: Dictionary, now: int) -> void:
	var slot: Dictionary = row["slot"]
	var bar: ProgressBar = row["bar"]
	var time: Label = row["time"]

	if bool(slot.get("ready", false)):
		bar.value = 1.0
		time.text = READY_TEXT
		return

	var left := _state.seconds_left(slot, now)
	var duration := float(slot.get("duration", 0.0))
	bar.value = 1.0 - left / duration if duration > 0.0 else 0.0
	time.text = _clock(left) if left > 0.0 else DUE_TEXT


## "4m 05s" or "38s".
static func _clock(seconds: float) -> String:
	var whole := ceili(seconds)
	var minutes := whole / 60
	var rest := whole % 60

	if minutes > 0:
		return "%dm %02ds left" % [minutes, rest]

	return "%ds left" % rest


## Freed with free(), not queue_free(), for the reason [InventoryView] gives.
func _clear() -> void:
	_rows = []

	for child: Node in get_children():
		remove_child(child)
		child.free()
