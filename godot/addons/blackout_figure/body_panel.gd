@tool
class_name FigureBodyPanel
extends FigurePartsPanel
## The Body tab of the figure workbench (DESIGN-0014 section 8.6): the
## parts of the body of the selected body type, the kit parts, and the
## shape list of each part.
##
## A body is the worn look with the key of its body type. Thus, this tab is
## the part editor of each worn look ([FigurePartsPanel]), with two more
## actions: "New body from the rig", and "Export the reference body". The
## second one asks for a file, and the plugin writes the figure of the
## selected body type there ([FigureReference]).
##
## ## The kit parts (Phase W6)
##
## A kit part is a worn look with a kit group: one hair shape, one head,
## one beard ([method FigureLook.kit]). This tab has three controls for
## them:
##
## - "The part editor shows" picks the look that the part editor below
##   edits: the body, or one kit part.
## - "Kit of the figure on the stands" gives each stand one kit part of
##   each kit group. It changes no file.
## - "New kit part" makes a kit part with one prism on the bone of the list
##   "Add a part on this bone".
##
## A kit part serves each body type, so it has the fit controls of the Gear
## tab. A body serves one body type, and it has none.
##
## This panel changes no worn look itself. Each control sends a signal, and
## the plugin makes the change through [FigureLookEdits] and the undo history.

signal new_body_requested

## "Export the reference body" (Phase W4). `path` is an OS path.
signal reference_requested(path: String)

## The part editor shows another look.
signal edited_changed

## The stands get one kit part of one kit group, or none for "".
signal kit_part_chosen(group: String, look_key: String)

## "New kit part", on the bone of the new part list.
signal kit_requested(key: String, group: String, bone: String)

## "Remove the kit part that the part editor shows".
signal kit_removed(key: String)

## The kit part that the part editor shows hides a region, or shows it.
signal hide_changed(region: String, hidden: bool)

const HELP := "Click a part in the 3D view, or pick a row. Then use the move, " \
	+ "turn, and scale tools of Godot (W, E, R), or the fields below."

const KIT_HELP := "A kit part is one choice of a character: a hair shape, a head, " \
	+ "a beard. It hides the region of the body part that it takes the place of."

const REFERENCE_TEXT := "Export reference body"
const REFERENCE_TIP := "Export the reference body: the figure of the selected body type " \
	+ "in its rest pose, with its outfit, as a file for a modeler."
const REFERENCE_TITLE := "Export the reference body: the figure in its rest pose"

## The title of the fold that holds the kit controls.
const FOLD_KIT := "Kit"
const REFERENCE_FILTER := "*.glb ; glTF binary"

## The first choice of the list of the edited look.
const THE_BODY := "(the body of the body type)"

## The first choice of the list of one kit group.
const NO_KIT_PART := "(the body as it is)"

## How the list of the edited look names a kit part: its group, then its
## key.
const KIT_ROW := "%s: %s"

var _save_dialog := FileDialog.new()
var _kit_fold: FoldableContainer
var _remove_kit: Button
var _edited := OptionButton.new()
var _kit_grid := GridContainer.new()
var _kit_key := LineEdit.new()
var _kit_group := LineEdit.new()
var _hide_label := FigureFields.label("Regions of the body that the kit part hides")
var _hides := GridContainer.new()

## The regions of the hide list, as one text.
var _shown_regions := ""

## Kit group -> the keys of its kit parts.
var _groups := {}

## The key of the kit part that the part editor shows, or "" for the body.
var _edited_kit := ""

var _body_key := ""

## The rows of the kit grid, as one text.
var _shown_kit := ""


func _init() -> void:
	super()

	_kit_fold = FigureFields.fold(FOLD_KIT, FigureFields.column(_kit_rows()), false)

	var rows: Array[Control] = [FigureFields.label(HELP),
		FigureFields.button("New body", new_body_requested.emit,
			"New body from the rig: the shape list body of the selected body type. " \
			+ "It takes the place of the body that is there."),
		FigureFields.button(REFERENCE_TEXT, func() -> void:
			_save_dialog.popup_centered_ratio(), REFERENCE_TIP),
		_kit_fold]

	# A body serves one body type, so it has no fit.
	fit_controls = false

	# The rows of a body go before the fold of the part editor.
	for index in rows.size():
		add_child(rows[index])
		move_child(rows[index], index)

	_enable_kit_buttons()

	_save_dialog.title = REFERENCE_TITLE
	_save_dialog.access = FileDialog.ACCESS_FILESYSTEM
	_save_dialog.file_mode = FileDialog.FILE_MODE_SAVE_FILE
	_save_dialog.filters = PackedStringArray([REFERENCE_FILTER])
	_save_dialog.file_selected.connect(func(path: String) -> void:
		reference_requested.emit(path))
	add_child(_save_dialog)


## The name that the save box starts with: the body type of the file.
func set_reference_name(body_key: String) -> void:
	_save_dialog.current_file = FigureReference.ROOT_PREFIX + body_key \
		+ FigureReference.FILE_SUFFIX


## Show the kit parts. Call this before [method set_content].
##
## - `body_key` is the selected body type.
## - `looks` is key -> [FigureLook], for each worn look of the store.
## - `kit` is the kit of the figure on the stands: kit group -> look key.
func set_kit_content(body_key: String, looks: Dictionary, kit: Dictionary) -> void:
	_body_key = body_key
	_groups = FigureOutfit.kit_groups(looks)

	if not looks.has(_edited_kit) or looks[_edited_kit].kit().is_empty():
		_edited_kit = ""

	_fill_edited()
	_show_kit(kit)
	fit_controls = not _edited_kit.is_empty()


## Show the worn look of the part editor, as [FigurePartsPanel] does. A kit
## part also shows its hide list: one box for each region of the rig.
func set_content(rig: FigureRig, look: FigureLook, models: FigureModels = null,
		palette: FigurePalette = null) -> void:
	super(rig, look, models, palette)
	_show_hides(rig, look)


## The folds of this tab: the kit, and the part editor.
func folds() -> Dictionary:
	var found := super()

	found[FOLD_KIT] = _kit_fold

	return found


## The key of the worn look that the part editor shows: the body of the
## selected body type, or one kit part.
func edited_look() -> String:
	return _body_key if _edited_kit.is_empty() else _edited_kit


## Make the part editor show one kit part, or the body for "". The panel
## sends no signal. The plugin gives the panel its content again after.
func edit_kit(look_key: String) -> void:
	_edited_kit = look_key
	_fill_edited()
	fit_controls = not _edited_kit.is_empty()


## The remove button needs a kit part in the part editor.
func _enable_kit_buttons() -> void:
	FigureFields.enable(_remove_kit, not _edited_kit.is_empty(),
		"The part editor shows the body. Select a kit part first.")


# ─── Building the panel ─────────────────────────────────────────────────────

## The controls of the kit parts, in the order of the tab.
func _kit_rows() -> Array[Control]:
	_edited.item_selected.connect(func(index: int) -> void:
		_edited_kit = _edited.get_item_metadata(index)
		fit_controls = not _edited_kit.is_empty()
		edited_changed.emit())
	_kit_grid.columns = 2
	_kit_key.placeholder_text = "The key of a new kit part, for example hair_short"
	_kit_group.placeholder_text = "Its kit group, for example hair"

	_hides.columns = 2
	_remove_kit = FigureFields.button("Remove kit part", func() -> void:
		kit_removed.emit(_edited_kit), "Remove the kit part that the part editor shows.")

	return [FigureFields.label(KIT_HELP),
		FigureFields.label("The part editor shows"), _edited,
		FigureFields.label("Kit of the figure on the stands"), _kit_grid,
		_kit_key, _kit_group,
		FigureFields.button("New kit part", func() -> void:
			kit_requested.emit(_kit_key.text.strip_edges(), _kit_group.text.strip_edges(),
				new_part_bone()),
			"Make a kit part with the key and the kit group of the fields, with one prism " \
			+ "on the bone of the part list."),
		_remove_kit, _hide_label, _hides]


## Show the hide list of a kit part: one box for each region of the rig, in
## the order of the names. The body has no hide list, so the boxes do not
## show for it. The boxes stay while the regions stay.
func _show_hides(rig: FigureRig, look: FigureLook) -> void:
	var regions: Array = [] if rig == null else rig.regions().keys()
	var shown := look != null and not _edited_kit.is_empty()

	regions.sort()
	_hide_label.visible = shown
	_hides.visible = shown

	if ",".join(regions) != _shown_regions:
		_shown_regions = ",".join(regions)

		for child: Node in _hides.get_children():
			_hides.remove_child(child)
			child.queue_free()

		for region: String in regions:
			var box := CheckBox.new()

			box.text = region
			box.toggled.connect(func(pressed: bool) -> void:
				hide_changed.emit(region, pressed))
			_hides.add_child(box)

	for index in regions.size():
		(_hides.get_child(index) as CheckBox).set_pressed_no_signal(
			shown and regions[index] in look.hides())


## Fill the list of the edited look: the body, then each kit part.
func _fill_edited() -> void:
	var groups := _groups.keys()

	_enable_kit_buttons()
	groups.sort()
	_edited.clear()
	_edited.add_item(THE_BODY)
	_edited.set_item_metadata(0, "")
	_edited.select(0)

	for group: String in groups:
		for look_key: String in _groups[group]:
			_edited.add_item(KIT_ROW % [group, look_key])
			_edited.set_item_metadata(_edited.item_count - 1, look_key)

			if look_key == _edited_kit:
				_edited.select(_edited.item_count - 1)


## Show one row for each kit group: its name, and the list of its kit
## parts. The rows stay while the groups and their kit parts stay.
func _show_kit(kit: Dictionary) -> void:
	var groups := _groups.keys()
	var lines := PackedStringArray()

	groups.sort()

	for group: String in groups:
		lines.append("%s=%s" % [group, ",".join(_groups[group])])

	if "\n".join(lines) != _shown_kit:
		_shown_kit = "\n".join(lines)

		for child: Node in _kit_grid.get_children():
			_kit_grid.remove_child(child)
			child.queue_free()

		for group: String in groups:
			_kit_grid.add_child(FigureFields.cell_label(group))
			_kit_grid.add_child(_new_kit_list(group))

	for index in groups.size():
		var list := _kit_grid.get_child(index * 2 + 1) as OptionButton

		FigureFields.select_text(list, kit.get(groups[index], NO_KIT_PART))

		if list.selected < 0:
			list.select(0)


## The list of one kit group: the body as it is, then each kit part.
func _new_kit_list(group: String) -> OptionButton:
	var list := OptionButton.new()

	list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	list.add_item(NO_KIT_PART)

	for look_key: String in _groups[group]:
		list.add_item(look_key)

	list.item_selected.connect(func(index: int) -> void:
		kit_part_chosen.emit(group, "" if index == 0 else list.get_item_text(index)))

	return list
