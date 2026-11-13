@tool
class_name FigureColorsPanel
extends VBoxContainer
## The Colors tab of the figure workbench (DESIGN-0014 section 8.6, Phase
## W5): the named colors and the color roles of the palette, and the colors
## of the character on the stands.
##
## ## A named color
##
## The list has one row for each named color of the palette
## ([FigurePalette]). A selected row shows its color, its finish, and each
## worn look that names it. A change of the color shows on each such look
## at one time (use case 13).
##
## ## A color role
##
## The table below gives each color role the named color that it has when a
## worn look gives it none.
##
## ## A finish
##
## The Finishes section lists each finish of the palette (ENG-0011, step
## L4). A selected finish shows its metalness and its roughness in two spin
## boxes. "New finish" adds one with the name in the field. "Remove finish"
## refuses while a named color has the finish.
##
## ## The colors of the character
##
## The last table gives a color role one named color on each stand, over
## the color of each look. The author sees a skin color or a hair color on
## the body with it. It changes no figure file: the plugin keeps the table
## in the options of the dock.
##
## This panel changes no file itself. Each control sends a signal, and the
## plugin makes the change through [FigurePaletteEdits] and the undo history.

## "New palette from the start colors".
signal palette_requested

## A named color gets a color. A name that the palette does not have joins
## it.
signal color_set(color_name: String, color: Color)
signal finish_changed(color_name: String, finish: String)
signal color_removed(color_name: String)

## "Give the selected color this name". Each look and each color role that
## names the color follows.
signal color_renamed(color_name: String, new_name: String)

## A color role gets its named color. A role that the palette does not have
## joins it.
signal role_changed(role: String, color_name: String)
signal role_removed(role: String)

## A color role of the character gets a named color, or "" for the color of
## each look.
signal figure_color_changed(role: String, color_name: String)

## A finish gets its two numbers. A finish that the palette does not have
## joins it.
signal finish_set(finish: String, metalness: float, roughness: float)
signal finish_removed(finish: String)

const COLOR_LIST_HEIGHT := 200.0
const FINISH_LIST_HEIGHT := 90.0

## The step of the two spin boxes of a finish.
const FINISH_STEP := 0.01

## The two numbers of a new finish, before the author changes them.
const NEW_FINISH := [0.5, 0.5]

## The side of the color mark of a row, in pixels.
const MARK_SIZE := 16

## The color of a new named color, before the author picks one.
const NEW_COLOR := Color(0.5, 0.5, 0.5)

## The first choice of the color list of a color role.
const REMOVE_ROLE := "(remove this color role)"

## The first choice of the color list of a role of the character.
const OF_THE_LOOK := "(the color of each look)"

const HELP := "A worn look gives a color role a named color. The palette gives " \
	+ "the named color its color and its finish. Change a color here, and each " \
	+ "look that names it changes."

const NO_PALETTE := "No palette file. Each named color comes from the start " \
	+ "colors. Make a palette to change a color."

const FIGURE_HELP := "Colors of the character on the stands. They go over the " \
	+ "color of each look, and they change no file."

var _note := Label.new()
var _new_palette: Button
var _colors := ItemList.new()
var _picker := ColorPickerButton.new()
var _finish := OptionButton.new()
var _users := Label.new()
var _remove: Button
var _rename: Button
var _rename_text := LineEdit.new()
var _new_name := LineEdit.new()
var _add_color: Button
var _roles := GridContainer.new()
var _new_role := LineEdit.new()
var _add_role: Button
var _figure := GridContainer.new()
var _finishes := ItemList.new()
var _metalness: SpinBox
var _roughness: SpinBox
var _finish_users := Label.new()
var _remove_finish: Button
var _new_finish_name := LineEdit.new()
var _add_finish: Button

var _palette := FigurePalette.new()
var _looks := {}
var _selected := ""
var _selected_finish := ""
var _mark: ImageTexture

## The rows of the color list, of the role table, of the table of the
## character, and of the finish list, each as one text.
var _shown_colors := ""
var _shown_roles := ""
var _shown_figure := ""
var _shown_finishes := ""


func _init() -> void:
	add_child(FigureFields.label(HELP))
	_note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_note)
	_new_palette = FigureFields.button("New palette", palette_requested.emit,
		"Make a palette file from the start colors of MeshPalette.")
	add_child(_new_palette)
	_build_color_rows()
	_build_role_rows()
	_build_finish_rows()
	add_child(FigureFields.label(FIGURE_HELP))
	_figure.columns = 2
	add_child(_figure)


## Show a palette. `has_file` is false for a store with no palette file.
## `looks` is key -> [FigureLook], for the looks that name a color.
## `body_roles` names each color role of the body, and `figure_colors` is
## the color table of the character on the stands.
func set_content(palette: FigurePalette, has_file: bool, looks: Dictionary,
		body_roles: Array, figure_colors: Dictionary) -> void:
	_palette = palette
	_looks = looks

	if not _palette.has_color(_selected):
		_selected = ""

	if not _palette.finishes().has(_selected_finish):
		_selected_finish = ""

	_note.text = NO_PALETTE if not has_file else "%d named color(s), %d color role(s), %d finish(es)." \
		% [_palette.colors().size(), _palette.roles().size(), _palette.finishes().size()]
	_new_palette.disabled = has_file
	FigureFields.fill(_finish, FigurePaletteEdits.finish_choices(_palette))
	_fill_colors()
	_show_color()
	_show_roles()
	_fill_finishes()
	_show_finish()
	_show_figure(body_roles, figure_colors)


func selected_color() -> String:
	return _selected


func selected_finish() -> String:
	return _selected_finish


## Select a finish of the list. The panel sends no signal.
func select_finish(finish: String) -> void:
	_selected_finish = finish if _palette.finishes().has(finish) else ""
	_fill_finishes()
	_show_finish()


## Select a named color of the list. The panel sends no signal.
func select_color(color_name: String) -> void:
	_selected = color_name if _palette.has_color(color_name) else ""
	_fill_colors()
	_show_color()


# ─── Building the panel ─────────────────────────────────────────────────────

func _build_color_rows() -> void:
	_colors.custom_minimum_size.y = COLOR_LIST_HEIGHT
	_colors.item_selected.connect(func(row: int) -> void:
		select_color(_colors.get_item_metadata(row)))
	_picker.custom_minimum_size.y = MARK_SIZE * 2.0
	_picker.edit_alpha = false
	_picker.color_changed.connect(func(color: Color) -> void:
		if not _selected.is_empty():
			color_set.emit(_selected, color))
	_finish.item_selected.connect(func(_index: int) -> void:
		finish_changed.emit(_selected, FigureFields.text_of(_finish)))
	_users.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_remove = FigureFields.button("Remove color", func() -> void:
		color_removed.emit(_selected), "Remove the selected named color from the palette.")
	_rename_text.placeholder_text = "A new name for the selected color"
	_rename = FigureFields.button("Rename color", func() -> void:
		color_renamed.emit(_selected, _rename_text.text.strip_edges()),
		"Give the selected color the name in the field. Each look that names it follows.")
	_new_name.placeholder_text = "The name of a new color, for example copper_dark"
	add_child(FigureFields.label("Named colors (name, color, finish)"))
	add_child(_colors)
	add_child(FigureFields.label("Color of the selected name"))
	add_child(_picker)
	add_child(FigureFields.label("Finish of the selected name"))
	add_child(_finish)
	add_child(_users)
	add_child(_remove)
	add_child(_rename_text)
	add_child(_rename)
	_add_color = FigureFields.button("Add color", func() -> void:
		color_set.emit(_new_name.text.strip_edges(), NEW_COLOR),
		"Add a named color with the name in the field.")
	add_child(_new_name)
	add_child(_add_color)


func _build_role_rows() -> void:
	_roles.columns = 2
	_new_role.placeholder_text = "The name of a new color role, for example trim"
	add_child(FigureFields.label("Color roles (role, its color with no color of a look)"))
	add_child(_roles)
	_add_role = FigureFields.button("Add color role", func() -> void:
		role_changed.emit(_new_role.text.strip_edges(), _first_color()),
		"Add a color role with the name in the field.")
	add_child(_new_role)
	add_child(_add_role)


func _build_finish_rows() -> void:
	_finishes.custom_minimum_size.y = FINISH_LIST_HEIGHT
	_finishes.item_selected.connect(func(row: int) -> void:
		select_finish(_finishes.get_item_metadata(row)))
	_metalness = FigureFields.spin(FigurePalette.FINISH_LOW, FigurePalette.FINISH_HIGH, FINISH_STEP)
	_roughness = FigureFields.spin(FigurePalette.FINISH_LOW, FigurePalette.FINISH_HIGH, FINISH_STEP)
	_metalness.value_changed.connect(func(_value: float) -> void: _send_finish())
	_roughness.value_changed.connect(func(_value: float) -> void: _send_finish())
	_finish_users.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_remove_finish = FigureFields.button("Remove finish", func() -> void:
		finish_removed.emit(_selected_finish),
		"Remove the selected finish from the palette. A finish that a color has stays.")
	_new_finish_name.placeholder_text = "The name of a new finish, for example chrome"
	_add_finish = FigureFields.button("New finish", func() -> void:
		finish_set.emit(_new_finish_name.text.strip_edges(), NEW_FINISH[0], NEW_FINISH[1]),
		"Add a finish with the name in the field.")
	add_child(FigureFields.label("Finishes (name, metalness, roughness)"))
	add_child(_finishes)
	add_child(FigureFields.label("Metalness of the selected finish"))
	add_child(_metalness)
	add_child(FigureFields.label("Roughness of the selected finish"))
	add_child(_roughness)
	add_child(_finish_users)
	add_child(_remove_finish)
	add_child(_new_finish_name)
	add_child(_add_finish)


## Send the two numbers of the selected finish.
func _send_finish() -> void:
	if not _selected_finish.is_empty():
		finish_set.emit(_selected_finish, _metalness.value, _roughness.value)


## The named color that a new color role starts with.
func _first_color() -> String:
	if _palette.has_color(MeshPalette.GENERIC) or _palette.colors().is_empty():
		return MeshPalette.GENERIC

	return _palette.color_names()[0]


# ─── The named colors ───────────────────────────────────────────────────────

## Fill the color list. A list with the same names keeps its rows. Thus, a
## drag in the color picker does not move the scroll bar. Each row then
## gets its text and its mark again.
func _fill_colors() -> void:
	var names := _palette.color_names()

	if ",".join(names) != _shown_colors:
		_shown_colors = ",".join(names)
		_colors.clear()

		for index in names.size():
			_colors.add_item(names[index], _color_mark())
			_colors.set_item_metadata(index, names[index])

	_colors.deselect_all()

	for index in names.size():
		_colors.set_item_text(index, "%s   #%s   %s" % [names[index],
			_palette.hex_of(names[index]), _palette.finish_of(names[index])])
		_colors.set_item_icon_modulate(index, _palette.color_of(names[index]))

		if names[index] == _selected:
			_colors.select(index)


## One white square. Each row tints it with its color.
func _color_mark() -> ImageTexture:
	if _mark == null:
		var image := Image.create(MARK_SIZE, MARK_SIZE, false, Image.FORMAT_RGBA8)

		image.fill(Color.WHITE)
		_mark = ImageTexture.create_from_image(image)

	return _mark


## Show the selected named color: its color, its finish, and the looks that
## name it.
func _show_color() -> void:
	var known := _palette.has_color(_selected)
	var color := _palette.color_of(_selected) if known else NEW_COLOR

	# A picker that has the color keeps it, so a drag does not jump. The
	# file keeps six hex digits, so the two colors compare as that text.
	if _picker.color.to_html(false) != color.to_html(false):
		_picker.color = color

	_picker.disabled = not known
	_finish.disabled = not known
	_remove.disabled = not known
	_rename.disabled = not known
	FigureFields.select_text(_finish, _palette.finish_of(_selected))
	_users.text = _users_text() if known else "No named color is selected."


func _users_text() -> String:
	var users := FigurePaletteEdits.looks_with_color(_looks, _selected)
	var roles := PackedStringArray()

	for role: String in _palette.role_names():
		if _palette.roles()[role] == _selected:
			roles.append(role)

	return "%s: %s. %s." % [_selected, _count_text(users, "look(s) name it"),
		_count_text(roles, "color role(s) have it")]


## A count with its names, for the users line: "2 look(s) name it (a, b)".
## A count of zero has no names after it.
static func _count_text(names: PackedStringArray, what: String) -> String:
	if names.is_empty():
		return "0 " + what

	return "%d %s (%s)" % [names.size(), what, ", ".join(names)]


# ─── The finishes ───────────────────────────────────────────────────────────

## Fill the finish list from the finishes of the file. A list with the same
## names keeps its rows, as the color list does.
func _fill_finishes() -> void:
	var names := PackedStringArray(_palette.finishes().keys())

	names.sort()

	if ",".join(names) != _shown_finishes:
		_shown_finishes = ",".join(names)
		_finishes.clear()

		for index in names.size():
			_finishes.add_item(names[index])
			_finishes.set_item_metadata(index, names[index])

	_finishes.deselect_all()

	for index in names.size():
		var values := _palette.finish_values(names[index])

		_finishes.set_item_text(index, "%s   %.2f   %.2f" % [names[index], values[0], values[1]])

		if names[index] == _selected_finish:
			_finishes.select(index)


## Show the selected finish: its two numbers, and the colors that have it.
func _show_finish() -> void:
	var known := _palette.finishes().has(_selected_finish)
	var values := _palette.finish_values(_selected_finish) if known else NEW_FINISH

	_metalness.set_value_no_signal(values[0])
	_roughness.set_value_no_signal(values[1])
	_metalness.editable = known
	_roughness.editable = known
	_remove_finish.disabled = not known
	_finish_users.text = "No finish is selected." if not known else "%s: %s." % [
		_selected_finish, _count_text(_palette.colors_with_finish(_selected_finish),
			"color(s) have it")]


# ─── The color roles ────────────────────────────────────────────────────────

## Show one row for each color role of the palette. The rows stay while the
## roles and the color names stay, so a list keeps the focus through a
## change.
func _show_roles() -> void:
	var roles := _palette.role_names()
	var names := _palette.color_names()
	var wanted := ",".join(roles) + ":" + ",".join(names)

	if wanted != _shown_roles:
		_shown_roles = wanted
		_clear(_roles)

		for role: String in roles:
			_roles.add_child(FigureFields.cell_label(role))
			_roles.add_child(_new_list(REMOVE_ROLE, names, func(color_name: String) -> void:
				if color_name.is_empty():
					role_removed.emit(role)
				else:
					role_changed.emit(role, color_name)))

	for index in roles.size():
		var list := _roles.get_child(index * 2 + 1) as OptionButton

		FigureFields.select_text(list, _palette.roles()[roles[index]])
		FigureFields.mark_colors(list, _palette, {}, 1)


# ─── The colors of the character ────────────────────────────────────────────

## Show one row for each color role of the body. A list with no color of
## the character shows its first choice.
func _show_figure(body_roles: Array, figure_colors: Dictionary) -> void:
	var roles := body_roles.duplicate()
	var names := _palette.color_names()

	roles.sort()

	var wanted := ",".join(roles) + ":" + ",".join(names)

	if wanted != _shown_figure:
		_shown_figure = wanted
		_clear(_figure)

		for role: String in roles:
			_figure.add_child(FigureFields.cell_label(role))
			_figure.add_child(_new_list(OF_THE_LOOK, names, func(color_name: String) -> void:
				figure_color_changed.emit(role, color_name)))

	for index in roles.size():
		var list := _figure.get_child(index * 2 + 1) as OptionButton

		FigureFields.select_text(list, figure_colors.get(roles[index], OF_THE_LOOK))
		FigureFields.mark_colors(list, _palette, {}, 1)


## A list with `first` as its first choice, then each name. `send` gets ""
## for the first choice, and the name for each other one.
static func _new_list(first: String, names: PackedStringArray, send: Callable) -> OptionButton:
	var list := OptionButton.new()

	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	list.add_item(first)

	for color_name: String in names:
		list.add_item(color_name)

	list.item_selected.connect(func(index: int) -> void:
		send.call("" if index == 0 else list.get_item_text(index)))

	return list


static func _clear(grid: GridContainer) -> void:
	for child: Node in grid.get_children():
		grid.remove_child(child)
		child.queue_free()
