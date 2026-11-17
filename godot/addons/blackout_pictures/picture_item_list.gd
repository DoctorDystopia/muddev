@tool
class_name PictureItemList
extends VBoxContainer
## The item list of the picture editor: each item of the game, with its
## item picture beside its name.
##
## The rows come from the item list of the terrain editor ([SpawnItems]).
## The server owns each fact there: the key, the name, and the family of an
## item. The feed names an item by the same key and the same family, so the
## picture of a row is the picture of the game.
##
## The text filter keeps the rows with the typed text, in the name or in the
## key, with no regard to the case. The second filter keeps the items with a
## pose of their own, or the items with the default pose. A row with a pose
## of its own has a mark after its key.
##
## ## The pictures arrive some at a time
##
## The first picture of an item builds its model. [method fill_pictures]
## gives a picture to some rows on each call, so the editor stays usable
## while the list fills.

signal item_chosen(key: String)

const FILTER_EACH := 0
const FILTER_OWN_POSE := 1
const FILTER_DEFAULT_POSE := 2

## The choices of the second filter, in the order of the constants above.
const FILTER_NAMES := ["Each item", "Items with a pose of their own",
	"Items with the default pose"]

## The side of the picture of a row, in pixels.
const PICTURE_SIDE := 32

const ROW_TEXT := "%s   (%s)"

## What a row says after its key when the item has a pose of its own.
const OWN_POSE_MARK := "   *"

const LIST_WIDTH := 300.0

var _text_filter := LineEdit.new()
var _pose_filter := OptionButton.new()
var _rows := ItemList.new()

var _items: SpawnItems

## The content of the picture file, for the mark and the second filter.
var _content := {}

## The key of each row of the list, in the order of the rows.
var _shown := PackedStringArray()

var _selected := ""

## Gives the picture of one item: `(key: String) -> Texture2D`.
var _picture_of := Callable()

## Item key -> its picture, for each picture that the list asked for.
var _pictures := {}


func _init() -> void:
	custom_minimum_size.x = LIST_WIDTH
	_text_filter.placeholder_text = "Keep the items with this text"
	_text_filter.clear_button_enabled = true
	_text_filter.text_changed.connect(func(_text: String) -> void: _fill_rows())
	FigureFields.fill(_pose_filter, FILTER_NAMES)
	_pose_filter.select(FILTER_EACH)
	_pose_filter.item_selected.connect(func(_index: int) -> void: _fill_rows())
	_rows.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_rows.fixed_icon_size = Vector2i(PICTURE_SIDE, PICTURE_SIDE)
	_rows.item_selected.connect(_on_row_selected)
	add_child(_text_filter)
	add_child(_pose_filter)
	add_child(_rows)


## Show the items of a list. `picture_of` gives the picture of one item.
func set_items(items: SpawnItems, picture_of: Callable) -> void:
	_items = items
	_picture_of = picture_of
	_pictures.clear()

	if _items == null or not _items.has(_selected):
		_selected = ""

	_fill_rows()


## Take the content of the picture file, and fill the rows again. The
## editor calls it after a read of the file.
func set_content(content: Dictionary) -> void:
	_content = content
	_fill_rows()


## Write the mark of one row again, after a change of its pose. The filter
## keeps the row, so an item does not leave the list while the author
## changes it.
func refresh_mark(key: String) -> void:
	var row := _shown.find(key)

	if row >= 0:
		_rows.set_item_text(row, _row_text(key))


## The key of the selected item, or "".
func selected_key() -> String:
	return _selected


## The keys of the rows that the filters keep.
func shown_keys() -> PackedStringArray:
	return _shown


## Select an item by its key. The list sends no signal. An item that a
## filter hides takes the filters off.
func select_item(key: String) -> void:
	if _items == null or not _items.has(key):
		key = ""

	_selected = key

	if not key.is_empty() and not key in _keys_kept():
		_text_filter.text = ""
		_pose_filter.select(FILTER_EACH)

	_fill_rows()


## Give a picture to at most `count` rows that have none. Returns how many
## rows got one.
func fill_pictures(count: int) -> int:
	var given := 0

	if not _picture_of.is_valid():
		return given

	for row in _shown.size():
		if given == count:
			break

		if _rows.get_item_icon(row) == null:
			_rows.set_item_icon(row, _picture(_shown[row]))
			given += 1

	return given


## Draw the list again. The editor calls it after the stage renders, so a
## row shows the new picture.
func redraw_pictures() -> void:
	_rows.queue_redraw()


## How many rows have their picture. For tests.
func picture_count() -> int:
	var count := 0

	for row in _shown.size():
		if _rows.get_item_icon(row) != null:
			count += 1

	return count


## Type a text into the text filter, as the author does. For tests.
func type_filter(text: String) -> void:
	_text_filter.text = text
	_fill_rows()


## Pick a choice of the second filter, as the author does. For tests.
func pick_pose_filter(choice: int) -> void:
	_pose_filter.select(choice)
	_fill_rows()


# ─── Private ────────────────────────────────────────────────────────────────

## The picture of one item. The list keeps it, so a filter change asks for
## no picture again.
func _picture(key: String) -> Texture2D:
	if not _pictures.has(key):
		_pictures[key] = _picture_of.call(key)

	return _pictures[key]


## The keys that the two filters keep, sorted by key.
func _keys_kept() -> PackedStringArray:
	var kept := PackedStringArray()

	if _items == null:
		return kept

	var text := _text_filter.text.strip_edges().to_lower()

	for key: String in _items.keys():
		var own := PicturePose.has_picture(_content, key)

		if _pose_filter.selected == FILTER_OWN_POSE and not own:
			continue

		if _pose_filter.selected == FILTER_DEFAULT_POSE and own:
			continue

		if text.is_empty() or _row_text(key).to_lower().contains(text):
			kept.append(key)

	return kept


func _row_text(key: String) -> String:
	var text := ROW_TEXT % [_items.name_of(key), key]

	return text + OWN_POSE_MARK if PicturePose.has_picture(_content, key) else text


## Fill the list with the rows that the filters keep. A row whose picture
## the list has gets it now. Each other row waits for
## [method fill_pictures].
func _fill_rows() -> void:
	_shown = _keys_kept()
	_rows.clear()

	for key: String in _shown:
		var row := _rows.add_item(_row_text(key), _pictures.get(key))

		if key == _selected:
			_rows.select(row)
			_rows.ensure_current_is_visible()


func _on_row_selected(row: int) -> void:
	_selected = _shown[row]
	item_chosen.emit(_selected)
