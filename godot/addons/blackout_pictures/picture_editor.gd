@tool
class_name PictureEditor
extends VBoxContainer
## The picture editor: the panel of the Pictures tab (Nick, 11/16/2026).
##
## The author picks an item in the list, and sets the zoom, the offset, and
## the turn of its item picture. Those three are the picture pose of the
## item ([PicturePose]). The game reads the poses from the look file
## `item_pictures.json` at its start.
##
## ## Three zones
##
## - The item list ([PictureItemList]): each item with its picture, a text
##   filter, and a filter on the items with a pose of their own.
## - The view ([PictureViewer]): the picture of the item, large, with its
##   guides. Below it, the picture at the sizes of the game.
## - The fields ([PictureFields]): one number field and one slider for each
##   value of the pose.
##
## ## The author sees the picture of the player
##
## The editor draws each picture with an [ItemStage], the class that draws
## the cells of the bag, of the doll, and of a pop-up. The stage reads the
## served model tree and the figure set of the repository from disk, as the
## figure workbench does. Thus, the order of the three sources of a picture
## is the order of the game: the served model, the worn look, and then the
## family shape.
##
## ## The content, the cache, and the file
##
## The editor keeps the content of the picture file in memory. Each change
## goes into that content. The cache of [LookFile] holds the same
## dictionary, so the stage draws the change at once. [method save] writes
## the file. [method revert] reads the file again.

## The path of the model tree below its directory: none, because the
## directory is the model tree itself. The figure workbench does the same.
const MODEL_TREE_ROOT := "/"

## The zoom that one step of the wheel adds, as a share of the cell.
const ZOOM_WHEEL_STEP := 0.05

## How many rows of the list get their picture on one frame.
const PICTURES_PER_FRAME := 4

## How many frames the views draw again after the stage changes. The stage
## renders on the frame after a change.
const FRESH_FRAMES := 3

## The sides of the small pictures below the view, in pixels: the picture
## of a cell of the bag, a middle size, and the cell of the render target.
const REAL_SIZES := [InventorySlotCell.ART_HEIGHT, 64, ItemStage.CELL_PIXELS]

const SIZE_TEXT := "%d px"
const FIELDS_WIDTH := 360.0
const STRIP_GAP := 16

const SOURCE_MODEL := "the served model"
const SOURCE_LOOK := "the worn look"
const SOURCE_FAMILY := "the family shape"
const ITEM_TEXT := "%s   (%s)   The picture draws %s."
const NO_ITEM_TEXT := "Pick an item."

const STATE_TEXT := "%d items. %d with a pose of their own."
const UNSAVED_TEXT := " Unsaved: %d."
const NOT_JSON := "%s is not one JSON object. Correct the file, then click Revert."
const BAD_FORM := "%s does not read: %s. Correct the file, then click Revert."
const NO_WRITE := "Cannot write %s (error %d)."
const REVERT_ASK := "Read the picture file again? The unsaved poses of %d item(s) go."

const SAVE_TIP := "Write the picture poses to the look file. Ctrl+S does the same."
const REVERT_TIP := "Read the look file again, and drop each unsaved pose."
const NOTHING_TO_SAVE := "Each pose is in the file."
const FILE_IS_BAD := "The picture file does not read."
const NOT_OPEN := "The picture editor did not read its files yet."

var _list := PictureItemList.new()
var _viewer := PictureViewer.new()
var _fields := PictureFields.new()

var _item_line := Label.new()
var _status := Label.new()
var _guides := CheckBox.new()
var _background := ColorPickerButton.new()
var _save_button: Button
var _revert_button: Button
var _revert_ask := ConfirmationDialog.new()

## The small pictures below the view, and the colour behind each.
var _real: Array[TextureRect] = []
var _real_backs: Array[ColorRect] = []

var _stage: ItemStage
var _resolver: MeshResolver
var _library: FigureLibrary
var _items: SpawnItems

## The file that [method save] writes.
var _path := PicturePose.PATH

## The content of the picture file with each change of the author.
var _content := {}

## The text of the picture file as it is on the disk, and its content.
var _saved_text := ""
var _saved := {}

## Why the picture file does not read, or "".
var _problem := ""

var _open := false

## The frames that the views still draw again.
var _fresh := 0


func _init() -> void:
	add_child(_bar())

	var split := HSplitContainer.new()
	var right := HSplitContainer.new()
	var scroll := ScrollContainer.new()

	split.size_flags_vertical = Control.SIZE_EXPAND_FILL
	right.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.custom_minimum_size.x = FIELDS_WIDTH
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_fields.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(_fields)
	right.add_child(_middle())
	right.add_child(scroll)
	split.add_child(_list)
	split.add_child(right)
	add_child(split)
	add_child(_revert_ask)
	_viewer.set_fill(ItemStage.ITEM_FILL)
	_list.item_chosen.connect(_show_item)
	_fields.pose_changed.connect(set_pose)
	_viewer.offset_dragged.connect(_on_offset_dragged)
	_viewer.turn_dragged.connect(_on_turn_dragged)
	_viewer.zoom_stepped.connect(_on_zoom_stepped)
	_revert_ask.confirmed.connect(revert)
	_refresh_state()


func _process(_delta: float) -> void:
	if not _open or not is_visible_in_tree():
		return

	if _list.fill_pictures(PICTURES_PER_FRAME) > 0:
		_fresh = FRESH_FRAMES

	if _fresh > 0:
		_fresh -= 1
		_redraw_views()


# ─── The life of the editor ─────────────────────────────────────────────────

## Read the models, the figure set, the items, and the picture file.
##
## - `models_directory` is the served model tree. Empty for the tree of
##   the repository.
## - `items` is the item list. Null for the list of the game.
## - `path` is the picture file that [method save] writes.
func open(models_directory := "", items: SpawnItems = null,
		path := PicturePose.PATH) -> void:
	close()

	var directory := models_directory

	if directory.is_empty():
		directory = FigureStore.repo_models_directory()

	_path = path
	_items = items if items != null else SpawnItems.game()
	_resolver = MeshResolver.from_directory(directory, MODEL_TREE_ROOT)
	_library = _library_of(directory)
	_stage = ItemStage.new()
	add_child(_stage)
	_stage.bind_meshes(_resolver)
	_stage.bind_figures(_library)
	_open = true
	_read()
	_list.set_items(_items, _picture_of)
	_list.set_content(_content)

	if not _items.keys().is_empty():
		select_item(_items.keys()[0])

	_refresh_state()


## True after [method open].
func is_open() -> bool:
	return _open


## Free the stage and its sources. The cache of [LookFile] forgets the
## content of the editor, so the next reader gets the file.
func close() -> void:
	if not _open:
		return

	_open = false
	_viewer.show_picture(null)

	for rect: TextureRect in _real:
		rect.texture = null

	_list.set_items(null, Callable())
	remove_child(_stage)
	_stage.free()
	_library.free()
	_resolver.free_models()
	_resolver.free()
	LookFile.forget(PicturePose.PATH)


# ─── The item and its pose ──────────────────────────────────────────────────

## Select an item by its key, and show its picture and its pose.
func select_item(key: String) -> void:
	_list.select_item(key)
	_show_item(_list.selected_key())


## The key of the selected item, or "".
func selected_key() -> String:
	return _list.selected_key()


## The full pose of the selected item, or the default pose for no item.
func shown_pose() -> Dictionary:
	return PicturePose.shown_row(_content, selected_key())


## Give the selected item a pose. The picture changes at once, and the file
## changes at the next save.
func set_pose(row: Dictionary) -> void:
	var key := selected_key()

	if not _open or key.is_empty():
		return

	PicturePose.set_picture(_content, key, row)
	_stage.redraw(key)
	_fields.show_pose(shown_pose())
	_list.refresh_mark(key)
	_fresh = FRESH_FRAMES
	_refresh_state()


# ─── The file ───────────────────────────────────────────────────────────────

## True when the content differs from the picture file.
func has_unsaved_changes() -> bool:
	return _open and _problem.is_empty() and _text_of(_content) != _saved_text


## How many items have a pose that differs from the picture file.
func unsaved_count() -> int:
	var now: Dictionary = FigureJson.canonical(_content).get(PicturePose.KEY_PICTURES, {})
	var before: Dictionary = _saved.get(PicturePose.KEY_PICTURES, {})
	var keys := {}
	var count := 0

	for key: String in now.keys() + before.keys():
		keys[key] = true

	for key: String in keys:
		if now.get(key, {}) != before.get(key, {}):
			count += 1

	return count


## Write the picture file. Returns the error of the write. A file that does
## not read stays as it is.
func save() -> Error:
	if not _open or not _problem.is_empty():
		return ERR_INVALID_DATA

	var text := _text_of(_content)
	var file := FileAccess.open(_path, FileAccess.WRITE)

	if file == null:
		var error := FileAccess.get_open_error()

		_status.text = NO_WRITE % [_path, error]

		return error

	file.store_string(text)
	file.close()
	_take_saved(text)
	_refresh_state()

	return OK


## Read the picture file again, and draw each picture again.
func revert() -> void:
	if not _open:
		return

	_read()
	_stage.redraw_all()
	_list.set_content(_content)
	_show_item(selected_key())


# ─── Private: the panel ─────────────────────────────────────────────────────

## The bar above the zones: the state, the guides, the background, and the
## two file buttons.
func _bar() -> HBoxContainer:
	var bar := HBoxContainer.new()

	_status.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_status.clip_text = true
	_guides.text = "Guides"
	_guides.button_pressed = true
	_guides.toggled.connect(_viewer.set_guides)
	_background.color = PictureViewer.DEFAULT_BACKGROUND
	_background.custom_minimum_size.x = STRIP_GAP * 3
	_background.edit_alpha = false
	_background.color_changed.connect(_on_background)
	_revert_button = FigureFields.button("Revert", _on_revert_pressed, REVERT_TIP)
	_save_button = FigureFields.button("Save", save, SAVE_TIP)
	bar.add_child(_status)
	bar.add_child(_guides)
	bar.add_child(FigureFields.cell_label("Background"))
	bar.add_child(_background)
	bar.add_child(_revert_button)
	bar.add_child(_save_button)

	return bar


## The middle zone: the line of the item, the view, and the small pictures.
func _middle() -> VBoxContainer:
	var middle := VBoxContainer.new()
	var strip := HBoxContainer.new()

	middle.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_item_line.text = NO_ITEM_TEXT
	_item_line.clip_text = true
	strip.alignment = BoxContainer.ALIGNMENT_CENTER
	strip.add_theme_constant_override("separation", STRIP_GAP)

	for side: int in REAL_SIZES:
		strip.add_child(_real_picture(side))

	middle.add_child(_item_line)
	middle.add_child(_viewer)
	middle.add_child(strip)

	return middle


## One small picture at `side` pixels, over the background colour, with its
## size below it. The filter is the filter of a cell of the game.
func _real_picture(side: int) -> VBoxContainer:
	var column := VBoxContainer.new()
	var back := ColorRect.new()
	var rect := TextureRect.new()
	var label := FigureFields.cell_label(SIZE_TEXT % side)

	back.color = PictureViewer.DEFAULT_BACKGROUND
	back.custom_minimum_size = Vector2(side, side)
	back.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	back.size_flags_vertical = Control.SIZE_SHRINK_END
	rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	back.add_child(rect)
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	column.alignment = BoxContainer.ALIGNMENT_END
	column.add_child(back)
	column.add_child(label)
	_real.append(rect)
	_real_backs.append(back)

	return column


func _on_background(color: Color) -> void:
	_viewer.set_background(color)

	for back: ColorRect in _real_backs:
		back.color = color


func _redraw_views() -> void:
	_viewer.queue_redraw()
	_list.redraw_pictures()

	for rect: TextureRect in _real:
		rect.queue_redraw()


## Show one item in the view and in the fields. An empty key shows none.
func _show_item(key: String) -> void:
	var picture: Texture2D = null

	if _open and not key.is_empty():
		picture = _picture_of(key)

	_viewer.show_picture(picture)

	for rect: TextureRect in _real:
		rect.texture = picture

	_fields.set_enabled(picture != null)
	_fields.show_pose(shown_pose())
	_item_line.text = NO_ITEM_TEXT if picture == null \
		else ITEM_TEXT % [_items.name_of(key), key, _source_of(key)]
	_fresh = FRESH_FRAMES


## The picture of one item, from the stage. The key and the family are
## those that the feed sends for the item.
func _picture_of(key: String) -> Texture2D:
	return _stage.picture(key, _items.family(key))


## What the picture of one item draws, in the order of [ItemStage].
func _source_of(key: String) -> String:
	if _resolver.may_have_art(key):
		return SOURCE_MODEL

	return SOURCE_LOOK if _library.has_item_look(key) else SOURCE_FAMILY


## The state line and the two file buttons.
func _refresh_state() -> void:
	var unsaved := has_unsaved_changes()

	FigureFields.enable(_save_button, unsaved,
		NOTHING_TO_SAVE if _problem.is_empty() else FILE_IS_BAD)
	FigureFields.enable(_revert_button, _open, NOT_OPEN)

	if not _problem.is_empty():
		_status.text = _problem
		return

	if not _open:
		_status.text = ""
		return

	var own: Dictionary = _content.get(PicturePose.KEY_PICTURES, {})

	_status.text = STATE_TEXT % [_items.keys().size(), own.size()]

	if unsaved:
		_status.text += UNSAVED_TEXT % unsaved_count()


func _on_revert_pressed() -> void:
	if not has_unsaved_changes():
		revert()
		return

	_revert_ask.dialog_text = REVERT_ASK % unsaved_count()
	_revert_ask.popup_centered()


# ─── Private: the mouse of the view ─────────────────────────────────────────

func _on_offset_dragged(shares: Vector2) -> void:
	var row := shown_pose()

	set_pose(PicturePose.row_from(PicturePose.zoom_of(row),
		PicturePose.offset_of(row) + shares, PicturePose.turn_of(row)))


func _on_turn_dragged(degrees: Vector2) -> void:
	var row := shown_pose()
	var turn := PicturePose.turn_of(row)
	var limit := PicturePose.TURN_LIMIT

	turn.x = wrapf(turn.x + degrees.x, -limit, limit)
	turn.y = wrapf(turn.y + degrees.y, -limit, limit)
	set_pose(PicturePose.row_from(PicturePose.zoom_of(row), PicturePose.offset_of(row), turn))


func _on_zoom_stepped(steps: int) -> void:
	var row := shown_pose()

	set_pose(PicturePose.row_from(PicturePose.zoom_of(row) + (float(steps) * ZOOM_WHEEL_STEP),
		PicturePose.offset_of(row), PicturePose.turn_of(row)))


# ─── Private: the sources and the file ──────────────────────────────────────

## A figure library with the figure set and the models of a model tree. A
## tree with no figure set gives a library with none. Each item then draws
## its served model or its family shape.
func _library_of(directory: String) -> FigureLibrary:
	var library := FigureLibrary.new()
	var set_path := directory.path_join(FigureSet.FILE_NAME)

	library.models = FigureModels.from_directory(directory)

	if FileAccess.file_exists(set_path):
		library.take_text(FileAccess.get_file_as_string(set_path))

	return library


## Read the picture file into the content, and give the content to the
## cache of [LookFile]. A file that does not read gives an empty content
## and a problem. [method save] then writes nothing.
func _read() -> void:
	var text := ""

	if FileAccess.file_exists(_path):
		text = FileAccess.get_file_as_string(_path)

	var content := FigureJson.parse(text)

	_problem = ""

	if content.is_empty() and not text.strip_edges().is_empty():
		_problem = NOT_JSON % _path
	elif not PicturePose.problem_of(content).is_empty():
		_problem = BAD_FORM % [_path, PicturePose.problem_of(content)]
		content = {}

	_content = _normal(content)
	_take_saved(_text_of(_content))
	_refresh_state()


## The content is now the content of the file. The cache of [LookFile]
## holds the dictionary of the editor, so the stage reads each later change.
func _take_saved(text: String) -> void:
	_saved_text = text
	_saved = FigureJson.parse(text)
	LookFile.put(PicturePose.PATH, _content)

	if _path != PicturePose.PATH:
		LookFile.forget(_path)


## A content with its format and its table of pictures.
static func _normal(content: Dictionary) -> Dictionary:
	var rows: Variant = content.get(PicturePose.KEY_PICTURES, {})

	return {
		PicturePose.KEY_FORMAT: PicturePose.FORMAT,
		PicturePose.KEY_PICTURES: rows.duplicate(true) if rows is Dictionary else {},
	}


## The text of the picture file for a content.
static func _text_of(content: Dictionary) -> String:
	return FigureJson.to_text(_normal(content))
