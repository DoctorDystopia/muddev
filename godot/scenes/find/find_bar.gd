class_name FindBar
extends PanelContainer
## Ctrl+F over the game log.
##
## A MUD log is the transcript of everything that has happened to you, and the
## browser gave searching it away for free. This is the rebuild ENG-0006 §3.1
## calls for.
##
## Scrolling is done with [method RichTextLabel.get_character_line], which maps
## a character offset in the parsed text to the visual line holding it. That is
## the one piece of this that would be genuinely awkward to write by hand --
## the log wraps, so a paragraph index is not a line index -- and the engine
## already has it.

## Emitted when the bar closes, so focus can go back to the input.
signal dismissed

const NOT_FOUND := -1

var _output: RichTextLabel
var _find := ScrollbackFind.new()
var _field: LineEdit
var _status: Label


func _init() -> void:
	visible = false

	var row := HBoxContainer.new()
	add_child(row)

	var label := Label.new()
	label.text = "Find"
	row.add_child(label)

	_field = LineEdit.new()
	_field.custom_minimum_size = Vector2(160, 0)
	_field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_field.text_changed.connect(_on_query_changed)
	# Enter steps to the next match rather than submitting anything, which is
	# what every find box in every application does.
	_field.text_submitted.connect(func(_t): _step(true))
	row.add_child(_field)

	_status = Label.new()
	_status.custom_minimum_size = Vector2(70, 0)
	row.add_child(_status)

	row.add_child(_button("<", func(): _step(false)))
	row.add_child(_button(">", func(): _step(true)))
	row.add_child(_button("x", close))


## Point the bar at the log it searches.
func bind(output: RichTextLabel) -> void:
	_output = output


## Show and focus, keeping whatever was last searched for.
func open() -> void:
	show()
	_field.grab_focus()
	_field.select_all()
	_refresh()


func close() -> void:
	hide()
	dismissed.emit()


## Escape closes, from anywhere in the bar.
func _gui_input(event: InputEvent) -> void:
	if event is InputEventKey and (event as InputEventKey).pressed \
			and (event as InputEventKey).keycode == KEY_ESCAPE:
		close()
		accept_event()


func _on_query_changed(_text: String) -> void:
	_refresh()
	_scroll_to(_find.current())


## Re-run the search against the log as it stands NOW.
##
## Searched fresh on every keystroke rather than against a cached copy, because
## the log grows while the bar is open -- a fight can add twenty lines during a
## search, and a stale haystack would scroll to an offset that has moved.
func _refresh() -> void:
	if _output == null:
		return

	_find.search(_output.get_parsed_text(), _field.text)
	_status.text = _find.status_text()


func _step(forward: bool) -> void:
	_refresh_if_log_grew()

	var offset := _find.next() if forward else _find.previous()

	_status.text = _find.status_text()
	_scroll_to(offset)


## Keep the match list honest against a log that is still being written to.
func _refresh_if_log_grew() -> void:
	if _output == null or _find.query.is_empty():
		return

	var live := _output.get_parsed_text()

	if _find.match_count() != _count_in(live):
		_find.search(live, _field.text)


func _count_in(haystack: String) -> int:
	var probe := ScrollbackFind.new()

	return probe.search(haystack, _field.text)


func _scroll_to(offset: int) -> void:
	if _output == null or offset == NOT_FOUND:
		return

	_output.scroll_to_line(_output.get_character_line(offset))


func _button(text: String, action: Callable) -> Button:
	var button := Button.new()
	button.text = text
	button.pressed.connect(action)

	return button
