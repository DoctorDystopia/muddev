@tool
class_name FigureEdits
extends RefCounted
## The one name of the edit rules of the figure workbench (DESIGN-0014),
## for the tests. Each rule lives in one script under `edits/`, by the
## file that it changes:
##
## - [FigureRigEdits]: the rig profile, the bones, the sockets, the
##   regions, the slot table, and the mirror name.
## - [FigurePartEdits]: a part of a look, its fit, and the parts from a
##   model.
## - [FigureShapeEdits]: the shapes of a part and their fields.
## - [FigureLookEdits]: the mannequin, the slot shape, the copy, the hide
##   list, the colors of a look, the kit parts, and the tiers.
## - [FigurePaletteEdits]: the palette, the named colors, the finishes, and
##   the color roles.
## - [FigureClipEdits]: the stance table and the clip lists.
##
## Each routine here forwards to one of them. The panels and the plugin
## name the script directly. A test names this class, so a test needs no
## edit when a rule moves. A rule that no test names has no forwarder.

const ARM_PLACES := FigureRigEdits.ARM_PLACES
const GRIP_R := FigureRigEdits.GRIP_R
const SOCKETS := FigureRigEdits.SOCKETS
const SLOTS := FigureRigEdits.SLOTS

const COPY_SUFFIX := FigurePartEdits.COPY_SUFFIX
const MIRROR_SUFFIX := FigurePartEdits.MIRROR_SUFFIX

const SHAPE_FIELDS := FigureShapeEdits.SHAPE_FIELDS
const FIELD_KINDS := FigureShapeEdits.FIELD_KINDS
const FINISH_OF_COLOR := FigureShapeEdits.FINISH_OF_COLOR

const SKIN_ROLE := FigureLookEdits.SKIN_ROLE
const ROLE_METAL := FigureLookEdits.ROLE_METAL
const ITEM_PART := FigureLookEdits.ITEM_PART


# ─── The rig ────────────────────────────────────────────────────────────────

static func rig_from_profile(key: String, limb_scale := 1.0) -> FigureRig:
	return FigureRigEdits.rig_from_profile(key, limb_scale)


static func add_socket(rig: Dictionary, socket: String, parent: String,
		position := Vector3.ZERO) -> String:
	return FigureRigEdits.add_socket(rig, socket, parent, position)


static func remove_socket(rig: Dictionary, socket: String) -> String:
	return FigureRigEdits.remove_socket(rig, socket)


static func set_bone_position(rig: Dictionary, bone: String, position: Vector3,
		mirror := false) -> String:
	return FigureRigEdits.set_bone_position(rig, bone, position, mirror)


static func set_bone_rotation(rig: Dictionary, bone: String, rotation: Quaternion) -> String:
	return FigureRigEdits.set_bone_rotation(rig, bone, rotation)


static func mirror_name(text: String) -> String:
	return FigureRigEdits.mirror_name(text)


static func add_region(rig: Dictionary, region: String) -> String:
	return FigureRigEdits.add_region(rig, region)


static func remove_region(rig: Dictionary, region: String,
		users := PackedStringArray()) -> String:
	return FigureRigEdits.remove_region(rig, region, users)


static func set_bone_region(rig: Dictionary, bone: String, region: String) -> String:
	return FigureRigEdits.set_bone_region(rig, bone, region)


static func looks_in_region(looks: Dictionary, region: String) -> PackedStringArray:
	return FigureRigEdits.looks_in_region(looks, region)


static func looks_on_bone(looks: Dictionary, bone: String) -> PackedStringArray:
	return FigureRigEdits.looks_on_bone(looks, bone)


static func set_slot_bone(rig: Dictionary, slot: String, bone: String) -> String:
	return FigureRigEdits.set_slot_bone(rig, slot, bone)


static func _bone_index(rig: Dictionary, bone: String) -> int:
	return FigureRigEdits.bone_index(rig, bone)


# ─── A part ─────────────────────────────────────────────────────────────────

static func add_part(look: Dictionary, rig: FigureRig, bone: String) -> String:
	return FigurePartEdits.add_part(look, rig, bone)


static func remove_part(look: Dictionary, part_name: String) -> String:
	return FigurePartEdits.remove_part(look, part_name)


static func rename_part(look: Dictionary, part_name: String, new_name: String) -> String:
	return FigurePartEdits.rename_part(look, part_name, new_name)


static func set_part_region(look: Dictionary, part_name: String, region: String) -> String:
	return FigurePartEdits.set_part_region(look, part_name, region)


static func set_part_place(look: Dictionary, part_name: String,
		xform: Transform3D, body_key := "") -> String:
	return FigurePartEdits.set_part_place(look, part_name, xform, body_key)


static func set_part_fit(look: Dictionary, body_key: String, part_name: String,
		fitted: bool) -> String:
	return FigurePartEdits.set_part_fit(look, body_key, part_name, fitted)


static func fit_to_rig(look: Dictionary, made_on: FigureRig, rig: FigureRig) -> int:
	return FigurePartEdits.fit_to_rig(look, made_on, rig)


static func set_part_bone(look: Dictionary, part_name: String, bone: String,
		rig: FigureRig, rigs := {}) -> String:
	return FigurePartEdits.set_part_bone(look, part_name, bone, rig, rigs)


static func duplicate_part(look: Dictionary, part_name: String) -> String:
	return FigurePartEdits.duplicate_part(look, part_name)


static func mirror_problem(look: Dictionary, part_name: String, rig: FigureRig) -> String:
	return FigurePartEdits.mirror_problem(look, part_name, rig)


static func mirror_part(look: Dictionary, part_name: String, rig: FigureRig) -> String:
	return FigurePartEdits.mirror_part(look, part_name, rig)


static func parts_from_model(look: Dictionary, rig: FigureRig, model_key: String,
		models: FigureModels) -> String:
	return FigurePartEdits.parts_from_model(look, rig, model_key, models)


static func bone_for_node(rig: FigureRig, node_name: String, bounds: AABB) -> String:
	return FigurePartEdits.bone_for_node(rig, node_name, bounds)


static func nearest_bone(rig: FigureRig, point: Vector3) -> String:
	return FigurePartEdits.nearest_bone(rig, point)


static func unique_name(base: String, taken: PackedStringArray) -> String:
	return FigurePartEdits.unique_name(base, taken)


# ─── A shape ────────────────────────────────────────────────────────────────

static func new_shape(kind: String) -> Dictionary:
	return FigureShapeEdits.new_shape(kind)


static func add_shape(look: Dictionary, part_name: String, kind: String) -> int:
	return FigureShapeEdits.add_shape(look, part_name, kind)


static func remove_shape(look: Dictionary, part_name: String, shape_index: int) -> String:
	return FigureShapeEdits.remove_shape(look, part_name, shape_index)


static func duplicate_shape(look: Dictionary, part_name: String, shape_index: int) -> int:
	return FigureShapeEdits.duplicate_shape(look, part_name, shape_index)


static func fields_of(shape: Dictionary) -> Array:
	return FigureShapeEdits.fields_of(shape)


static func shape_value(shape: Dictionary, field: String) -> Variant:
	return FigureShapeEdits.shape_value(shape, field)


static func set_shape_value(look: Dictionary, part_name: String, shape_index: int,
		field: String, value: Variant) -> String:
	return FigureShapeEdits.set_shape_value(look, part_name, shape_index, field, value)


static func set_shape_place(look: Dictionary, part_name: String, shape_index: int,
		xform: Transform3D) -> String:
	return FigureShapeEdits.set_shape_place(look, part_name, shape_index, xform)


# ─── A look ─────────────────────────────────────────────────────────────────

static func mannequin(rig: FigureRig, girth := 1.0) -> FigureLook:
	return FigureLookEdits.mannequin(rig, girth)


static func slot_shape(rig: FigureRig, slot: String) -> FigureLook:
	return FigureLookEdits.slot_shape(rig, slot)


static func look_from(key: String, source: FigureLook) -> Dictionary:
	return FigureLookEdits.look_from(key, source)


static func copy_look(look: Dictionary, source: Dictionary) -> String:
	return FigureLookEdits.copy_look(look, source)


static func set_hide(look: Dictionary, region: String, hidden: bool) -> String:
	return FigureLookEdits.set_hide(look, region, hidden)


static func set_color(look: Dictionary, role: String, color: String,
		palette: FigurePalette = null) -> String:
	return FigureLookEdits.set_color(look, role, color, palette)


static func remove_color(look: Dictionary, role: String,
		palette: FigurePalette = null) -> String:
	return FigureLookEdits.remove_color(look, role, palette)


static func roles_of_look(look: FigureLook, models: FigureModels = null,
		palette: FigurePalette = null) -> PackedStringArray:
	return FigureLookEdits.roles_of_look(look, models, palette)


static func new_kit_part(key: String, group: String, rig: FigureRig, bone: String,
		palette: FigurePalette = null) -> Dictionary:
	return FigureLookEdits.new_kit_part(key, group, rig, bone, palette)


static func kit_problem(key: String, group: String, rig: FigureRig, bone: String,
		taken: PackedStringArray) -> String:
	return FigureLookEdits.kit_problem(key, group, rig, bone, taken)


static func set_kit(look: Dictionary, group: String) -> String:
	return FigureLookEdits.set_kit(look, group)


static func make_tier(look: Dictionary, base_key: String, looks: Dictionary) -> String:
	return FigureLookEdits.make_tier(look, base_key, looks)


static func tiers_of(looks: Dictionary, key: String) -> PackedStringArray:
	return FigureLookEdits.tiers_of(looks, key)


# ─── The palette ────────────────────────────────────────────────────────────

static func new_palette() -> FigurePalette:
	return FigurePaletteEdits.new_palette()


static func set_named_color(palette: Dictionary, color_name: String, color: Color) -> String:
	return FigurePaletteEdits.set_named_color(palette, color_name, color)


static func set_color_finish(palette: Dictionary, color_name: String,
		finish: String) -> String:
	return FigurePaletteEdits.set_color_finish(palette, color_name, finish)


static func remove_named_color(palette: Dictionary, color_name: String,
		looks: Dictionary) -> String:
	return FigurePaletteEdits.remove_named_color(palette, color_name, looks)


static func rename_named_color(palette: Dictionary, color_name: String,
		new_name: String) -> String:
	return FigurePaletteEdits.rename_named_color(palette, color_name, new_name)


static func rename_color_in_look(look: Dictionary, color_name: String, new_name: String,
		roles := PackedStringArray()) -> bool:
	return FigurePaletteEdits.rename_color_in_look(look, color_name, new_name, roles)


static func set_role_color(palette: Dictionary, role: String, color_name: String) -> String:
	return FigurePaletteEdits.set_role_color(palette, role, color_name)


static func remove_role(palette: Dictionary, role: String, looks: Dictionary) -> String:
	return FigurePaletteEdits.remove_role(palette, role, looks)


static func looks_with_color(looks: Dictionary, color_name: String) -> PackedStringArray:
	return FigurePaletteEdits.looks_with_color(looks, color_name)


static func color_choices(palette: FigurePalette) -> Array:
	return FigurePaletteEdits.color_choices(palette)


# ─── The clips ──────────────────────────────────────────────────────────────

static func new_stances() -> Dictionary:
	return FigureClipEdits.new_stances()


static func set_stance_clip(table: Dictionary, tool_type: String, action: String,
		clip_name: String) -> String:
	return FigureClipEdits.set_stance_clip(table, tool_type, action, clip_name)


static func set_clip(list: Dictionary, clip_name: String, from: String,
		loop: bool) -> String:
	return FigureClipEdits.set_clip(list, clip_name, from, loop)


static func remove_clip(list: Dictionary, clip_name: String) -> String:
	return FigureClipEdits.remove_clip(list, clip_name)
