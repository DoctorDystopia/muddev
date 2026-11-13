@tool
class_name FigureRigPanel
extends VBoxContainer
## The Rig tab of the figure workbench (DESIGN-0014 section 8.6): the bones
## of the selected body type, its sockets, and its slot table.
##
## This panel changes no rig itself. Each control sends a signal, and the
## plugin makes the change through [FigureRigEdits] and the undo history.
##
## The slot rows come from the slot table of the rig. A new slot on the
## server is a new row of [constant FigureRigEdits.SLOTS], and it needs no
## edit here.
##
## Phase W6 added three controls. The rotation fields give a socket its
## rest rotation: the grip of a hand socket. A bone of the body refuses
## one. The mirror box moves the bone of the other side with a moved bone.
## The region rows put the selected bone in a region, add a region, and
## remove one.

signal bone_chosen(bone_name: String)

## `mirror` is true when the bone of the other side moves also. `axis` is
## the name of the field that changed, for the label of the undo entry.
signal bone_moved(bone_name: String, position: Vector3, mirror: bool, axis: String)

## A socket got a rest rotation: the grip of a hand socket. `axis` is the
## name of the field that changed.
signal bone_turned(bone_name: String, rotation: Quaternion, axis: String)

## The selected bone goes into a region, or into no region for "".
signal bone_region_changed(bone_name: String, region: String)
signal region_requested(region: String)
signal region_removed(region: String)
signal socket_requested(socket: String, parent: String)
signal socket_removed(socket: String)
signal slot_changed(slot: String, bone: String)
signal new_rig_requested(key: String, limb_scale: float)

const BONE_LIST_HEIGHT := 240.0

## The range of the limb scale of a new rig.
const LIMB_SCALE_LOW := 0.5
const LIMB_SCALE_HIGH := 1.5
const LIMB_SCALE_STEP := 0.01

const HELP := "Select a bone to mark it on each figure. The position is on the " \
	+ "parent bone. Each body type has the same bones and the same rest " \
	+ "rotations, so one clip moves each of them."

## The choice of the region list for a bone in no region.
const NO_REGION := "(no region)"

const MIRROR_TEXT := "Move the bone of the other side also"

const ROTATION_HELP := "Rotation of the selected socket in degrees. " \
	+ "A held item has its length along +Y of a hand socket."

## Why the rotation row and the socket button are off for a bone of the
## body.
const ONLY_SOCKET := "Only a socket takes a rotation of its own. Each body type shares " \
	+ "the rest rotation of each bone of the body, so one clip moves each of them."
const ONLY_SOCKET_REMOVE := "Only a socket can go. Select a socket first: its name is in " \
	+ "brackets."

var _bones := Tree.new()
var _position: HBoxContainer
var _rotation: HBoxContainer
var _remove_socket: Button
var _mirror := CheckBox.new()
var _region := OptionButton.new()
var _region_name := LineEdit.new()
var _socket_name := LineEdit.new()
var _slots := GridContainer.new()
var _new_key := LineEdit.new()
var _limb_scale: SpinBox

var _rig: FigureRig

## The bones that the tree shows, as one text.
var _shown_bones := ""

## The slot rows that the grid shows, as one text.
var _shown_slots := ""

## True while this panel fills a control. The tree sends its signal for a
## selection by code also.
var _filling := false


func _init() -> void:
	add_child(FigureFields.label(HELP))
	_bones.custom_minimum_size.y = BONE_LIST_HEIGHT
	_bones.hide_root = true
	_bones.item_selected.connect(_on_bone_selected)
	add_child(FigureFields.label("Bones (a socket is in brackets)"))
	add_child(_bones)
	_position = FigureFields.vector_row(FigureFields.LENGTH_LOW, FigureFields.LENGTH_HIGH,
		FigureFields.LENGTH_STEP, _on_position_changed, true)
	add_child(FigureFields.label("Position of the selected bone"))
	add_child(_position)
	_mirror.text = MIRROR_TEXT
	add_child(_mirror)
	_rotation = FigureFields.vector_row(-FigureFields.ANGLE_LIMIT, FigureFields.ANGLE_LIMIT,
		FigureFields.ANGLE_STEP, _on_rotation_changed, true)
	add_child(FigureFields.label(ROTATION_HELP))
	add_child(_rotation)
	_build_region_rows()
	_build_socket_rows()
	_slots.columns = 2
	add_child(FigureFields.label("Slot table: the default bone of each slot"))
	add_child(_slots)
	_build_new_rig_rows()


## Show a rig, or no rig for null.
func set_rig(rig: FigureRig) -> void:
	_rig = rig
	_fill_bones()
	_fill_slots()
	_fill_regions()
	_show_position()


## True when a move of a bone moves the bone of the other side also.
func mirrors() -> bool:
	return _mirror.button_pressed


func selected_bone() -> String:
	var item := _bones.get_selected()

	if item == null:
		return ""

	return item.get_metadata(0)


## Select a bone of the tree. The panel sends no signal.
func select_bone(bone_name: String) -> void:
	_filling = true
	_select_item(_bones.get_root(), bone_name)
	_filling = false
	_show_position()


# ─── Building the panel ─────────────────────────────────────────────────────

## The region of the selected bone, a new region, and the removal of one. A
## new part on a bone starts in the region of that bone.
func _build_region_rows() -> void:
	_region.item_selected.connect(func(index: int) -> void:
		bone_region_changed.emit(selected_bone(),
			"" if index == 0 else FigureFields.text_of(_region)))
	_region_name.placeholder_text = "The name of a new region, for example cape"
	add_child(FigureFields.label("Region of the selected bone"))
	add_child(_region)
	add_child(_region_name)
	add_child(FigureFields.button("Add region", func() -> void:
		region_requested.emit(_region_name.text.strip_edges()),
		"Add a region with the name in the field."))
	add_child(FigureFields.button("Remove region", func() -> void:
		region_removed.emit("" if _region.selected <= 0 else FigureFields.text_of(_region)),
		"Remove the region of the selected bone. A region that a look names stays."))


func _build_socket_rows() -> void:
	_socket_name.placeholder_text = "The name of a new socket, for example sheath_l"
	add_child(_socket_name)
	add_child(FigureFields.button("Add socket", func() -> void:
		socket_requested.emit(_socket_name.text.strip_edges(), selected_bone()),
		"Add a socket with the name in the field, on the selected bone."))
	_remove_socket = FigureFields.button("Remove socket", func() -> void:
		socket_removed.emit(selected_bone()),
		"Remove the selected socket. A socket that carries a part of a look stays.")
	add_child(_remove_socket)


func _build_new_rig_rows() -> void:
	_new_key.placeholder_text = "The key of a new body type, for example body_3"
	_limb_scale = FigureFields.spin(LIMB_SCALE_LOW, LIMB_SCALE_HIGH, LIMB_SCALE_STEP, 1.0)
	add_child(FigureFields.label("New rig"))
	add_child(_new_key)
	add_child(FigureFields.label("Limb scale (1 is the humanoid profile)"))
	add_child(_limb_scale)
	add_child(FigureFields.button("New rig", func() -> void:
		new_rig_requested.emit(_new_key.text.strip_edges(), _limb_scale.value),
		"New rig from the humanoid profile, with the key and the limb scale of the fields."))


# ─── Showing a rig ──────────────────────────────────────────────────────────

## Fill the bone tree. A rig with the same bones keeps the tree and its
## selection.
func _fill_bones() -> void:
	var wanted := "" if _rig == null else _rig.key() + ":" + _rig.structure()

	if wanted == _shown_bones:
		return

	var kept := selected_bone()

	_shown_bones = wanted
	_filling = true
	_bones.clear()

	if _rig != null:
		var root := _bones.create_item()

		for row: Dictionary in _rig.bones():
			if row["parent"].is_empty():
				_add_bone_item(root, row["name"])

		_select_item(root, kept)

	_filling = false


func _add_bone_item(parent: TreeItem, bone_name: String) -> void:
	var item := _bones.create_item(parent)

	item.set_text(0, "[%s]" % bone_name if _rig.is_socket(bone_name) else bone_name)
	item.set_metadata(0, bone_name)

	for child: String in _rig.children_of(bone_name):
		_add_bone_item(item, child)


## Select the item of one bone below `item`. Returns true when it is there.
func _select_item(item: TreeItem, bone_name: String) -> bool:
	if item == null or bone_name.is_empty():
		return false

	if item.get_metadata(0) == bone_name:
		item.select(0)
		_bones.scroll_to_item(item)
		return true

	for child: TreeItem in item.get_children():
		if _select_item(child, bone_name):
			return true

	return false


## Fill the slot rows: one label and one bone list for each slot.
func _fill_slots() -> void:
	var slots := {} if _rig == null else _rig.slots()
	var names := slots.keys()

	names.sort()

	var wanted := "" if _rig == null else ",".join(names) + ":" + _rig.structure()

	if wanted != _shown_slots:
		_shown_slots = wanted

		for child: Node in _slots.get_children():
			_slots.remove_child(child)
			child.queue_free()

		for slot: String in names:
			var list := OptionButton.new()
			var slot_label := Label.new()

			# A label that wraps takes no width in a grid, so this one does not.
			slot_label.text = slot
			FigureFields.fill(list, _rig.bone_names())
			list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			list.item_selected.connect(func(_index: int) -> void:
				slot_changed.emit(slot, FigureFields.text_of(list)))
			_slots.add_child(slot_label)
			_slots.add_child(list)

	for index in names.size():
		FigureFields.select_text(_slots.get_child(index * 2 + 1), slots[names[index]])


## Fill the region list from the regions of the rig.
func _fill_regions() -> void:
	var names: Array = [NO_REGION]

	if _rig != null:
		var regions := _rig.regions().keys()

		regions.sort()
		names.append_array(regions)

	FigureFields.fill(_region, names)


## Show the place, the rest rotation, and the region of the selected bone.
func _show_position() -> void:
	var bone := selected_bone()

	_enable_socket_controls(bone)

	if _rig == null or not _rig.has_bone(bone):
		FigureFields.set_vector(_position, Vector3.ZERO)
		FigureFields.set_vector(_rotation, Vector3.ZERO)
		_region.select(0 if _region.item_count > 0 else -1)
		return

	var turn := _rig.rest_of(bone).basis.get_euler()
	var region := _rig.region_of(bone)

	FigureFields.set_vector(_position, _rig.rest_of(bone).origin)
	FigureFields.set_vector(_rotation, Vector3(rad_to_deg(turn.x), rad_to_deg(turn.y),
		rad_to_deg(turn.z)))
	FigureFields.select_text(_region, NO_REGION if region.is_empty() else region)


## The rotation row and the socket button work on a socket only. For a bone
## of the body, each is off, with the reason in its tooltip.
func _enable_socket_controls(bone: String) -> void:
	var is_socket := _rig != null and _rig.is_socket(bone)

	for axis in FigureFields.AXES:
		(_rotation.get_child(axis) as SpinBox).editable = is_socket

	_rotation.tooltip_text = "" if is_socket else ONLY_SOCKET
	FigureFields.enable(_remove_socket, is_socket, ONLY_SOCKET_REMOVE)


# ─── The signals of the controls ────────────────────────────────────────────

func _on_bone_selected() -> void:
	_show_position()

	if not _filling:
		bone_chosen.emit(selected_bone())


func _on_position_changed(position: Vector3, axis: int) -> void:
	if not selected_bone().is_empty():
		bone_moved.emit(selected_bone(), position, mirrors(), FigureFields.AXIS_NAMES[axis])


func _on_rotation_changed(degrees: Vector3, axis: int) -> void:
	if selected_bone().is_empty():
		return

	var turn := Vector3(deg_to_rad(degrees.x), deg_to_rad(degrees.y), deg_to_rad(degrees.z))

	bone_turned.emit(selected_bone(), Basis.from_euler(turn).get_rotation_quaternion(),
		FigureFields.AXIS_NAMES[axis])
