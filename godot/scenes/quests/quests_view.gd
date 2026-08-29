class_name QuestsView
extends Control
## The quest log, drawn from [QuestState].
##
## Presentation only, and it names no quest. Every row comes from whatever
## `char_quests` contained, so a quest added under
## `systems/quests/content/` appears here with no edit — the same contract
## [SummaryView] answers for panels, and for the same reason.
##
## ## It draws bars, which is why the channel is structured
##
## The server sends an objective as `{current, required, counted, done}` rather
## than as the rendered `[x] Rats culled 3/5` the telnet screen prints. Given
## the numbers, this can show progress at a glance and grey out what is done;
## given the sentence it could only print it. That is the whole argument for the
## channel's shape, and this file is what spends it.
##
## `required` is 1 for a one-shot objective, so the bar below has no branch for
## the two kinds — only the READING beside it differs, and `counted` says which.

## Shown before char_quests has ever arrived. Distinguished from an empty log,
## which is a real and different thing.
const NO_DATA_TEXT := "No quest log yet."

## Shown when the server has answered and the answer is nothing.
const NO_QUESTS_TEXT := "You have taken no quests."

const OBJECTIVE_BAR_WIDTH := 90
const OBJECTIVE_BAR_HEIGHT := 8

## A finished objective is dimmed rather than removed: the step still asks for
## it, and a list that shrank as you worked would keep moving under the cursor.
const COLOR_DONE := Color(0.45, 0.55, 0.45)
const COLOR_TODO := Color(0.85, 0.87, 0.90)
const COLOR_BAR := Color("4caf50")

var _state: QuestState
var _body: VBoxContainer


func _init() -> void:
	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	margin.theme_type_variation = &"PaneMargin"
	add_child(margin)

	var scroller := ScrollContainer.new()
	scroller.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	margin.add_child(scroller)

	_body = VBoxContainer.new()
	_body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_body.theme_type_variation = &"FormColumn"
	scroller.add_child(_body)


## Bind to a model and follow it.
func bind(state: QuestState) -> void:
	_state = state
	_state.changed.connect(_rebuild)
	_rebuild()


## Rebuild wholesale, the way the inventory grid does.
##
## `char_quests` is a snapshot, so throwing every row away and making them again
## is the only approach that cannot desync from it. Diffing against a payload
## that is already the whole truth would be inventing a delta protocol on the
## client side — which the server refused to do, at length, for good reasons.
func _rebuild() -> void:
	if _state == null:
		return

	for child: Node in _body.get_children():
		_body.remove_child(child)
		child.free()

	if not _state.has_data:
		_body.add_child(_label(NO_DATA_TEXT, &"RowKey"))
		return

	if _state.active.is_empty() and _state.completed.is_empty():
		_body.add_child(_label(NO_QUESTS_TEXT, &"RowKey"))
		return

	for quest: Dictionary in _state.active:
		_add_active(quest)

	if _state.completed.is_empty():
		return

	_body.add_child(HSeparator.new())
	_body.add_child(_label("Completed", &"PanelHeading"))

	for quest: Dictionary in _state.completed:
		_body.add_child(_label(str(quest.get("title", "")), &"RowKey"))


func _add_active(quest: Dictionary) -> void:
	_body.add_child(_label(str(quest.get("title", "")), &"PanelHeading"))
	_body.add_child(_wrapped(str(quest.get("step_description", ""))))

	for objective: Dictionary in quest.get("objectives", []):
		_body.add_child(_objective_row(objective))

	_body.add_child(HSeparator.new())


## One objective: a bar, a reading, and what it is.
func _objective_row(objective: Dictionary) -> Control:
	var row := HBoxContainer.new()
	var done := bool(objective.get("done", false))

	var bar := ProgressBar.new()
	bar.custom_minimum_size = Vector2(OBJECTIVE_BAR_WIDTH, OBJECTIVE_BAR_HEIGHT)
	bar.max_value = 1.0
	bar.step = 0.001
	bar.show_percentage = false
	bar.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	bar.value = _fraction(objective)
	bar.modulate = COLOR_BAR if done else COLOR_TODO
	row.add_child(bar)

	var reading := _label(_reading(objective), &"RowKey")
	reading.custom_minimum_size = Vector2(44, 0)
	row.add_child(reading)

	var what := _label(str(objective.get("description", "")), &"RowValue")
	what.modulate = COLOR_DONE if done else COLOR_TODO
	row.add_child(what)

	return row


## How full an objective's bar is.
##
## Clamped, because a counted objective can legitimately overshoot: the handler
## caps progress at the requirement, but nothing on the wire promises it, and a
## bar past its maximum draws as a full one anyway.
func _fraction(objective: Dictionary) -> float:
	var required := maxi(1, int(objective.get("required", 1)))

	return clampf(
		float(int(objective.get("current", 0))) / float(required), 0.0, 1.0)


## "3/5" for a counted objective, a tickbox for a one-shot one.
##
## The one place the two kinds are drawn differently, which is the whole job of
## the `counted` flag. Without it a boolean objective would read "1/1", which
## says nothing a tick does not say better.
func _reading(objective: Dictionary) -> String:
	var done := bool(objective.get("done", false))

	if not bool(objective.get("counted", false)):
		return "[x]" if done else "[ ]"

	return "%d/%d" % [int(objective.get("current", 0)),
		maxi(1, int(objective.get("required", 1)))]


func _label(text: String, variation: StringName) -> Label:
	var label := Label.new()
	label.text = text
	label.theme_type_variation = variation

	return label


func _wrapped(text: String) -> Label:
	var label := _label(text, &"RowKey")
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL

	return label
