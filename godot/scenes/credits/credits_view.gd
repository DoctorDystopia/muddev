class_name CreditsView
extends Control
## The credits box: who made each model the game shows, and its license.
##
## The Options pane opens it with its Credits button. It is the CLIENT's box,
## not a server pop-up: nothing here is game state, the server never hears of
## it, and the close button hides it at once.
##
## A full-console Control, for the reason [PopupView] gives: a native `Window`
## on the web is an embedded subwindow with no keyboard route to it. While it
## shows, it owns every click, so a click beside the box cannot walk the player.
##
## The list is fetched the first time the box opens, from the same origin as
## the models, and kept after that. [CreditsState] reads it.

## How dark the backdrop dims the game behind the box.
const BACKDROP_COLOR := Color(0, 0, 0, 0.35)

## The box's size, as a part of the whole console.
const BOX_FRACTION := Vector2(0.6, 0.7)

## How long to wait for the list before giving up.
const TIMEOUT_SECONDS := 20.0

const TITLE_TEXT := "Credits"
const CLOSE_TEXT := "Close"
const INTRO_TEXT := "The 3D models in Blackout, who made them, and their licenses."
const LOADING_TEXT := "Loading the credits..."
const FAILED_TEXT := "The credits could not be loaded. Try again later."
const EMPTY_TEXT := "No model credits yet."
const UNCONFIRMED_TEXT := "License not confirmed. A placeholder, to be replaced."

var _state := CreditsState.new()
var _url := ""
var _box: PanelContainer
var _list: VBoxContainer
var _message: Label
var _fetching := false


func _init() -> void:
	visible = false
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	resized.connect(_place_box)

	var backdrop := ColorRect.new()
	backdrop.color = BACKDROP_COLOR
	backdrop.mouse_filter = Control.MOUSE_FILTER_IGNORE
	backdrop.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(backdrop)

	_box = PanelContainer.new()
	_box.theme_type_variation = &"PopupBox"
	_box.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_box)

	var margin := MarginContainer.new()
	margin.theme_type_variation = &"PaneMargin"
	_box.add_child(margin)

	var column := VBoxContainer.new()
	margin.add_child(column)
	column.add_child(_header())

	var intro := Label.new()
	intro.text = INTRO_TEXT
	intro.theme_type_variation = &"RowValue"
	intro.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(intro)

	var scroller := ScrollContainer.new()
	scroller.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroller.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	column.add_child(scroller)

	_list = VBoxContainer.new()
	_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroller.add_child(_list)

	_message = Label.new()
	_message.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_list.add_child(_message)


## Where to fetch `credits.json` from, as an absolute URL.
##
## Empty means the box can only show what [method show_document] gives it,
## which is what a test does.
func bind(url: String) -> void:
	_url = url


## Show the box. Fetch the list the first time.
func open() -> void:
	visible = true
	_place_box()

	if _state.loaded():
		_render()
		return

	_show_message(LOADING_TEXT)
	_fetch()


## Hide the box. Client-only, so it closes at once.
func close() -> void:
	visible = false


## Fold in a parsed document and draw it. The fetch calls this, and so can a
## test.
func show_document(document: Variant) -> void:
	_state.ingest(document)
	_render()


## Every entry the box draws. For tests.
func state() -> CreditsState:
	return _state


func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return

	if event.is_action_pressed("ui_cancel"):
		close()
		get_viewport().set_input_as_handled()


func _header() -> Control:
	var row := HBoxContainer.new()

	var title := Label.new()
	title.text = TITLE_TEXT
	title.theme_type_variation = &"PanelHeading"
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(title)

	var close_button := Button.new()
	close_button.text = CLOSE_TEXT
	close_button.pressed.connect(close)
	row.add_child(close_button)

	return row


func _place_box() -> void:
	var box_size := size * BOX_FRACTION

	_box.size = box_size
	_box.position = (size - box_size) / 2.0


func _fetch() -> void:
	if _fetching or _url.is_empty():
		return

	_fetching = true
	var http := HTTPRequest.new()
	http.timeout = TIMEOUT_SECONDS
	add_child(http)

	http.request_completed.connect(
		func(result: int, code: int, _headers: PackedStringArray,
				body: PackedByteArray):
			http.queue_free()
			_fetching = false
			_finish(result, code, body))

	if http.request(_url) != OK:
		http.queue_free()
		_fetching = false
		_show_message(FAILED_TEXT)


func _finish(result: int, code: int, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or code != 200:
		push_warning("CreditsView: http %d (result %d)" % [code, result])
		_show_message(FAILED_TEXT)
		return

	show_document(JSON.parse_string(body.get_string_from_utf8()))


func _show_message(text: String) -> void:
	for child: Node in _list.get_children():
		if child != _message:
			child.queue_free()

	_message.text = text
	_message.visible = true


func _render() -> void:
	var entries := _state.entries()

	if entries.is_empty():
		_show_message(EMPTY_TEXT)
		return

	_show_message("")
	_message.visible = false

	for entry: Dictionary in entries:
		_list.add_child(_entry_row(entry))


## One credit: the title, the author, the license, and a link to the source.
func _entry_row(entry: Dictionary) -> Control:
	var block := VBoxContainer.new()

	var title := Label.new()
	title.text = entry["title"]
	title.theme_type_variation = &"SectionHeading"
	block.add_child(title)

	var author := Label.new()
	author.text = "by %s" % entry["author"]
	author.theme_type_variation = &"RowValue"
	block.add_child(author)

	block.add_child(_link(entry["license"], entry["license_url"]))
	block.add_child(_link(entry["url"], entry["url"]))

	if not entry["confirmed"]:
		var warning := Label.new()
		warning.text = UNCONFIRMED_TEXT
		warning.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		block.add_child(warning)

	return block


## A link when there is a URL, and plain text when there is not.
func _link(text: String, url: String) -> Control:
	if url.is_empty():
		var plain := Label.new()
		plain.text = text
		return plain

	var link := LinkButton.new()
	link.text = text
	link.uri = url

	return link
