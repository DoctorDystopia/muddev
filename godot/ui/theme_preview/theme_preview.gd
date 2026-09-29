@tool
class_name ThemePreview
extends VBoxContainer
## One sample of each theme type, for the scene preview of the Theme editor.
##
## To use it, open `ui/blackout_theme.tres`. In the Theme editor, click
## "Add Preview", then "Add Scene Preview", and select one of the two scenes
## beside this script. Click the picker button of the preview, then click a
## sample. The editor then selects the theme type of that sample.
##
## The picker reads the `theme_type_variation` of the control first, then its
## class. Thus, each variation sample is its base class with the variation set,
## and each class sample is a plain instance of the class.
##
## ## Built from the themes, not from a list
##
## The script walks the type list of the Blackout theme and of the Godot default
## theme. A new variation in the theme gets a sample with no edit here. The
## script is a tool script, so it builds the samples in the editor too. It gives
## them no owner, so a save of the scene keeps none of them.
##
## ## The two parts
##
## `blackout.tscn` shows every type that the Blackout theme sets. `godot.tscn`
## shows every other control type of the Godot default theme, so a type that the
## Blackout theme does not set yet is one click away. A Window type (for example
## `PopupMenu`) cannot be a child of a Control. The last line of each part names
## those types. Edit them from the type list of the Theme editor.
##
## `test_theme_preview.gd` checks that each part shows each type that it owns.

const THEME_PATH := "res://ui/blackout_theme.tres"

const PART_BLACKOUT := "blackout"
const PART_GODOT := "godot"

## The state of each button sample, in the order that the row shows them.
const BUTTON_STATES := ["normal", "pressed", "disabled"]
const STATE_PRESSED := "pressed"
const STATE_DISABLED := "disabled"

const SAMPLE_TEXT := "Sample"
const RICH_TEXT := "[b]Bold[/b], [i]italic[/i] and [color=#e05050]color[/color]"
const TEXT_LINES := "First line\nSecond line\nThird line"
const TAB_NAMES := ["First", "Second"]
const LIST_ITEMS := ["First item", "Second item", "Third item"]

const RANGE_MAX := 100.0
const RANGE_VALUE := 40.0
const SCROLL_PAGE := 20.0

## The floor size of a sample whose own minimum is zero.
const SMALL_SIZE := Vector2(160, 24)
const BOX_SIZE := Vector2(240, 120)
const SWATCH_SIZE := Vector2(24, 24)
const SWATCH_COUNT := 4
const SWATCH_COLOR := Color(0.35, 0.38, 0.44, 1)
const GRID_COLUMNS := 2
const CAPTION_WIDTH := 190.0

## The part to show. One of [constant PART_BLACKOUT] or [constant PART_GODOT].
@export_enum("blackout", "godot") var part := PART_BLACKOUT:
	set(value):
		part = value

		if is_inside_tree():
			_rebuild()

var _theme: Theme

## The type list at the last build. A theme edit that changes only a value
## keeps the list the same, so the samples stay and do not flicker.
var _built_types := PackedStringArray()


func _ready() -> void:
	_theme = load(THEME_PATH)

	if not _theme.changed.is_connected(_on_theme_changed):
		_theme.changed.connect(_on_theme_changed)

	_rebuild()


## The types that this part shows, as `{type: base class}`. A class sample has
## itself as its base.
func shown_types() -> Dictionary:
	var shown := {}

	for type_name: String in _owned_types():
		var base := _base_class(type_name)

		if _is_previewable(base):
			shown[type_name] = base

	return shown


## The types that this part owns but cannot show, because they are not Controls.
func hidden_types() -> PackedStringArray:
	var hidden := PackedStringArray()

	for type_name: String in _owned_types():
		if not _is_previewable(_base_class(type_name)):
			hidden.append(type_name)

	return hidden


func _on_theme_changed() -> void:
	if _theme.get_type_list() != _built_types:
		_rebuild.call_deferred()


func _rebuild() -> void:
	for child: Node in get_children():
		remove_child(child)
		child.queue_free()

	_built_types = _theme.get_type_list()
	var shown := shown_types()
	var names: Array = shown.keys()
	names.sort()

	add_child(_heading("Variations"))

	for type_name: String in names:
		if type_name != shown[type_name]:
			add_child(_sample_row(type_name, shown[type_name]))

	add_child(_heading("Classes"))

	for type_name: String in names:
		if type_name == shown[type_name]:
			add_child(_sample_row(type_name, type_name))

	add_child(_heading("Not in this preview"))
	add_child(_caption("Windows, and names that are not a class. Pick them "
		+ "from the type list: " + ", ".join(hidden_types())))


## Every type of this part. The Blackout part owns each type that the Blackout
## theme sets. The Godot part owns each other type of the default theme.
func _owned_types() -> PackedStringArray:
	var blackout := _theme.get_type_list()

	if part == PART_BLACKOUT:
		return blackout

	var owned := PackedStringArray()

	for type_name: String in ThemeDB.get_default_theme().get_type_list():
		if not blackout.has(type_name):
			owned.append(type_name)

	return owned


## The class that a type draws on. A variation names its base in the theme that
## declares it. A class is its own base.
func _base_class(type_name: String) -> String:
	var base := String(_theme.get_type_variation_base(type_name))

	if base.is_empty():
		base = String(ThemeDB.get_default_theme().get_type_variation_base(type_name))

	if base.is_empty():
		return type_name

	return base


func _is_previewable(base: String) -> bool:
	return (ClassDB.class_exists(base)
		and ClassDB.can_instantiate(base)
		and ClassDB.is_parent_class(base, "Control"))


## A caption with the type name, then one sample, or one sample for each button
## state.
func _sample_row(type_name: String, base: String) -> HBoxContainer:
	var row := HBoxContainer.new()
	var caption := _caption(type_name if type_name == base
		else "%s (%s)" % [type_name, base])
	caption.custom_minimum_size.x = CAPTION_WIDTH
	caption.autowrap_mode = TextServer.AUTOWRAP_OFF
	row.add_child(caption)

	var states: Array = [""]

	if ClassDB.is_parent_class(base, "BaseButton"):
		states = BUTTON_STATES

	for state: String in states:
		var sample: Control = ClassDB.instantiate(base)

		if type_name != base:
			sample.theme_type_variation = StringName(type_name)

		_fill(sample)
		_set_state(sample, state)
		row.add_child(sample)

	return row


## Content, so that the sample draws its styles. The order of the tests
## matters: a TabContainer and a ColorPicker are Containers too.
func _fill(sample: Control) -> void:
	if sample is BaseButton:
		_fill_button(sample as BaseButton)
	elif sample is Range:
		_fill_range(sample as Range)
	elif sample is RichTextLabel:
		_fill_rich_text(sample as RichTextLabel)
	elif sample is TextEdit:
		(sample as TextEdit).text = TEXT_LINES
		sample.custom_minimum_size = BOX_SIZE
	elif sample is TabContainer or sample is TabBar:
		_fill_tabs(sample)
	elif sample is ItemList or sample is Tree:
		_fill_list(sample)
	elif sample is GraphEdit or sample is GraphFrame:
		sample.custom_minimum_size = BOX_SIZE
	elif sample is HSeparator:
		sample.custom_minimum_size = SMALL_SIZE
	elif sample is VSeparator:
		sample.custom_minimum_size = Vector2(SMALL_SIZE.y, SMALL_SIZE.x)
	elif sample is MenuBar:
		var menu := PopupMenu.new()
		menu.name = SAMPLE_TEXT
		sample.add_child(menu)
	elif sample is ColorPicker:
		pass
	elif sample is Container:
		_fill_container(sample as Container)
	elif "text" in sample:
		sample.set("text", SAMPLE_TEXT)

	if sample.get_combined_minimum_size() == Vector2.ZERO:
		sample.custom_minimum_size = SMALL_SIZE


func _fill_button(button: BaseButton) -> void:
	if "text" in button:
		button.set("text", SAMPLE_TEXT)

	if button is OptionButton:
		for item: String in LIST_ITEMS:
			(button as OptionButton).add_item(item)
	elif button is MenuButton:
		for item: String in LIST_ITEMS:
			(button as MenuButton).get_popup().add_item(item)


func _fill_range(range_control: Range) -> void:
	range_control.max_value = RANGE_MAX
	range_control.value = RANGE_VALUE

	if range_control is ScrollBar:
		range_control.page = SCROLL_PAGE

	var horizontal := range_control is HScrollBar or range_control is HSlider
	var vertical := range_control is VScrollBar or range_control is VSlider

	if horizontal or range_control is ProgressBar:
		range_control.custom_minimum_size = SMALL_SIZE
	elif vertical:
		range_control.custom_minimum_size = Vector2(SMALL_SIZE.y, SMALL_SIZE.x)


func _fill_rich_text(rich: RichTextLabel) -> void:
	rich.bbcode_enabled = true
	rich.fit_content = true
	rich.text = RICH_TEXT
	rich.custom_minimum_size.x = BOX_SIZE.x


func _fill_tabs(sample: Control) -> void:
	for tab_name: String in TAB_NAMES:
		if sample is TabBar:
			(sample as TabBar).add_tab(tab_name)
			continue

		var page := Control.new()
		page.name = tab_name
		page.custom_minimum_size = SMALL_SIZE
		sample.add_child(page)


func _fill_list(sample: Control) -> void:
	sample.custom_minimum_size = BOX_SIZE

	if sample is ItemList:
		for item: String in LIST_ITEMS:
			(sample as ItemList).add_item(item)

		return

	var tree := sample as Tree
	var root := tree.create_item()
	root.set_text(0, SAMPLE_TEXT)

	for item: String in LIST_ITEMS:
		tree.create_item(root).set_text(0, item)


## A panel or a margin gets a label, so its content margin shows. Every other
## container gets swatches, so its separation shows.
func _fill_container(container: Container) -> void:
	if container is GridContainer:
		(container as GridContainer).columns = GRID_COLUMNS

	if container is PanelContainer or container is MarginContainer:
		var label := Label.new()
		label.text = SAMPLE_TEXT
		container.add_child(label)
		return

	if container is ScrollContainer:
		container.custom_minimum_size = BOX_SIZE
		var content := _swatch()
		content.custom_minimum_size = BOX_SIZE * 2
		container.add_child(content)
		return

	for index: int in SWATCH_COUNT:
		container.add_child(_swatch())


func _set_state(sample: Control, state: String) -> void:
	var button := sample as BaseButton

	if button == null:
		return

	if state == STATE_PRESSED:
		button.toggle_mode = true
		button.button_pressed = true
	elif state == STATE_DISABLED:
		button.disabled = true


func _swatch() -> ColorRect:
	var swatch := ColorRect.new()
	swatch.color = SWATCH_COLOR
	swatch.custom_minimum_size = SWATCH_SIZE

	return swatch


func _heading(text: String) -> Label:
	var label := Label.new()
	label.text = text
	label.theme_type_variation = &"FormHeading"

	return label


func _caption(text: String) -> Label:
	var label := Label.new()
	label.text = text
	label.theme_type_variation = &"RowKey"
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.size_flags_vertical = Control.SIZE_SHRINK_CENTER

	return label
