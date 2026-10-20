@tool
class_name FigureWorkbench
extends Node3D
## The figures that the figure workbench shows: one stand for each body
## type, side by side (DESIGN-0014, requirement A2).
##
## The figure files are its store ([FigureStore]). The scene holds no figure
## data. Each node here is made at load and has no owner, so a scene save
## stores none of it. The plugin saves the figure files on Ctrl+S.
##
## ## A stand
##
## A stand is the figure of one rig, from [FigureBuilder]: the same class
## that the game uses. A stand wears the body of its body type, which is
## the worn look with the key of the rig, and then the outfit.
##
## ## The outfit
##
## The outfit is the worn record of the workbench: slot -> asset key (Phase
## W3). Each stand wears the same outfit, so the author sees one item on
## each body type. [FigureOutfit] gives the look of each item, as it does in
## the game: the worn look of the item, then the slot shape, then the
## family shape. The items and the slots come from the item catalog
## ([FigureCatalog]).
##
## The outfit is no figure file. A save does not write it, and the dock
## keeps it in its options file.
##
## One worn look shows on each stand. A part of that look thus has one node
## on each stand, and a move of one of those nodes goes into the look.
##
## ## Two ways to change a file
##
## 1. The dock gives new content to [method put]. The plugin puts each such
##    change in the undo history of the editor.
## 2. The author moves a part with the Godot move, turn, or scale tool. The
##    editor changes the node and makes its own undo entry.
##    [method sync_from_nodes] then writes the place of the node into the
##    worn look. An undo of the editor moves the node back, and the same
##    routine writes the old place.
##
## The second way needs each part to keep its node. [FigureBuilder.refresh]
## does that.
##
## ## Clips
##
## Each stand plays the same clip at the same time, so the author sees one
## clip on each body type (Phase W2). The clips come from
## [member clip_directory] through [FigureClips], the class that the game
## uses. [method build_clips] makes the clip files again from each clip
## list of the store.
##
## [member show_probe] puts the probe of [FigureClearance] in each hand:
## an item as long as a long sword. The author then sees if a clip puts a
## held item through the body. The probe is no figure file, and a click
## does not select it.
##
## ## Models
##
## A part of a worn look can name one node of a served model (Phase W4).
## [member models] reads the served model tree from disk, and each stand
## draws from it ([FigureModels]). [method reload_models] reads the tree
## again after a model build. [method export_reference] writes the
## reference body that a modeler works over ([FigureReference]).
##
## ## The fit of a body type
##
## A worn look can give a part another place on one body type. A move of
## the node on that stand then goes into the fit row, and the node on each
## other stand stays ([method FigurePartEdits.set_part_place]).
##
## ## The palette, a tier, and the colors of the figure (Phase W5)
##
## Each stand takes its colors from the palette of the store
## ([FigurePalette]). A change of one named color thus shows on each look
## that names it.
##
## A tier is a look with a base: it draws the parts of that base. A move of
## such a part on a stand goes into the look that has the parts, and each
## tier of it follows.
##
## [method set_figure_colors] gives each stand the colors of one character:
## color role -> named color. The author sees a skin color or a hair color
## on the body with no change of a file. The table is no figure file, as
## the outfit is none.
##
## ## The kit of the figure, and the checks (Phase W6)
##
## A kit part is a worn look with a kit group: one hair shape, one head.
## [method set_kit] gives each stand the kit of one character: kit group ->
## the key of a kit part. The kit is no figure file, as the outfit is none.
##
## [method run_checks] gives the findings of [FigureChecks] for the store,
## the item catalog, the served models, and the clips of this workbench.
##
## ## The stance table
##
## The stance table is one more file of the store ([FigureStances]). It is
## beside the clip directory, because it names the clips of that directory.
## [method stance_of_outfit] gives the tool type whose stance the outfit
## takes.
##
## ## The family stand (ENG-0011, steps L5 and L6)
##
## One more stand, at the right of the figures, shows one entity as the
## game draws it: [method show_entity] names an asset key and a family, and
## [MeshResolver] draws them through the same ladder as the game. The
## Families tab shows the shape of a family on it. The Gear tab shows the
## served model of an item on it, with the presentation of the look file.
## The stand draws again on each change of a file, as the figures do.
##
## The stand has no part node. A click does not select a family shape, and
## the Godot tools do not move one. The part editor of the Families tab
## changes it.
##
## ## The scratch directory
##
## An empty [member figure_directory] is `blackout/assets/figure/` of this
## repository. A test gives a scratch directory, and it never writes a file
## of the repository. The same holds for [member clip_directory],
## [member source_directory], [member models_directory], and
## [member look_directory].

## A file of the store got new content. `kind` is a [FigureStore] kind.
signal changed(kind: String, key: String)

## The store read the directory again.
signal reloaded

## The stands wear another outfit.
signal outfit_changed

## The stands have the colors of another character.
signal figure_colors_changed

## The stands have the kit of another character.
signal kit_changed

## The distance between two stands.
const STAND_SPACING := 1.2

## The meta of a stand: the key of its rig.
const STAND_META := "figure_stand"

const FLOOR_NAME := "Floor"
const FLOOR_DEPTH := 2.4
const FLOOR_MARGIN := 1.2
const FLOOR_COLOR := Color(0.32, 0.3, 0.28)

## The label of a stand, above the head of its figure.
const LABEL_NAME := "Label"
const LABEL_HEIGHT := 2.05
const LABEL_PIXEL_SIZE := 0.004

## The mark on the bone that the Rig tab selects.
const MARK_NAME := "BoneMark"
const MARK_RADIUS := 0.022
const MARK_COLOR := Color(1.0, 0.3, 1.0)

## A node that is nearer than this to its place in the worn look did not
## move. The file keeps five digits, so a smaller difference is rounding.
const PLACE_TOLERANCE := 0.0001

## The stand of one entity, at the right of the figures.
const FAMILY_STAND_NAME := "FamilyStand"

## The name of the node that holds the drawn entity on the family stand.
const ENTITY_NAME := "Entity"

## The entity of the family stand is one unit across, with its middle at
## the origin. The stand lifts it by this much, so it stands on the floor.
const ENTITY_LIFT := 0.5

## The directory of the look files of a scratch workbench, below its figure
## directory.
const SCRATCH_LOOK_DIRECTORY := "look"

## The path of the model tree below the models directory: the directory IS
## the tree.
const OWN_MODEL_ROOT := "/"

## Where the figure files are: an OS path, or a `user://` path. Empty for
## `blackout/assets/figure/` of this repository.
@export var figure_directory := ""

## Where the clip files are: a `res://` path or an OS path. Empty for the
## clip directory of the game ([constant FigureClips.CLIP_DIRECTORY]).
@export var clip_directory := ""

## Where the sources of the clip lists are: an OS path. Empty for
## `blackout/assets/sources/` of this repository.
@export var source_directory := ""

## Where the item catalog is: a `res://` path or an OS path. Empty for the
## catalog of the plugin ([constant FigureCatalog.CATALOG_PATH]).
@export var catalog_path := ""

## Where the served model tree is: an OS path, or a `user://` path. It is
## the directory that holds `manifest.json`. Empty for the served tree of
## this repository.
@export var models_directory := ""

## Where the look files are: a `res://` path or an OS path. Empty for
## `res://world/look` of the game, or for `look/` below a scratch figure
## directory. A scratch workbench thus never writes a look file of the
## repository.
@export var look_directory := ""

var store: FigureStore

## The models that the parts of a worn look draw.
var models: FigureModels

## The items and the slots that the outfit can hold.
var catalog := FigureCatalog.new()

## The clips that each stand can play.
var clips := AnimationLibrary.new()

## True while each stand holds the probe of [FigureClearance].
var show_probe := false:
	set(value):
		show_probe = value

		if store != null:
			_sync_stands()

## Body type -> the stand node.
var _stands := {}

var _marked_bone := ""

## The clip that each stand shows, or "" for the rest pose.
var _clip := ""

## The outfit of each stand: slot -> asset key.
var _outfit := {}

## The colors of the character on each stand: color role -> named color.
var _figure_colors := {}

## The kit of the character on each stand: kit group -> the key of a kit
## part.
var _kit := {}

## The entity of the family stand: its asset key, or "", and its family.
var _shown_asset := ""
var _shown_family := ""

## The resolver that draws the family stand, or null before the first
## entity. Each change makes a new one, so a changed look file reaches it.
var _resolver: MeshResolver

## Body type -> asset key -> the row of the served part that the stand
## draws. A moved node of a served model differs from its row.
var _served_rows := {}


func _ready() -> void:
	set_process(Engine.is_editor_hint())
	reload()


func _process(_delta: float) -> void:
	sync_from_nodes()


## The workbench that holds `node`, or null.
static func of(node: Object) -> FigureWorkbench:
	var walk := node as Node

	while walk != null:
		if walk is FigureWorkbench:
			return walk

		walk = walk.get_parent()

	return null


# ─── The store ──────────────────────────────────────────────────────────────

## The OS path of the figure directory.
func directory() -> String:
	if figure_directory.is_empty():
		return FigureStore.repo_directory()

	return ProjectSettings.globalize_path(figure_directory)


## True when a save writes a file of the repository: a figure file, the
## stance table, or a clip. A scratch figure directory with no scratch clip
## directory still writes the clips and the stance table of the
## repository, so this asks the two directories.
func writes_repo() -> bool:
	return writes_repo_figures() or clip_directory.is_empty()


## True when a save writes the figure files of the repository. The served
## `figure.json` and a model import follow those files, so the plugin asks
## this before it runs the pipeline.
func writes_repo_figures() -> bool:
	return figure_directory.is_empty()


## The path of the directory of the look files.
func looks_directory() -> String:
	if not look_directory.is_empty():
		return ProjectSettings.globalize_path(look_directory)

	if figure_directory.is_empty():
		return LookFile.DIRECTORY

	return directory().path_join(SCRATCH_LOOK_DIRECTORY)


## Read the directory again, and build each stand. This drops each unsaved
## change.
func reload() -> void:
	store = FigureStore.new(directory(), stances_path(), looks_directory())
	store.load_all()
	catalog = FigureCatalog.read_file(
		FigureCatalog.CATALOG_PATH if catalog_path.is_empty() else catalog_path)

	if not catalog.error.is_empty():
		store.errors.append("item catalog: " + catalog.error)

	models = FigureModels.from_directory(served_models_directory())
	_outfit = catalog.valid_outfit(_outfit)
	_sync_stands()
	reload_clips()
	reloaded.emit()


## Read the directory again when a file of it changed on the disk, and the
## store has no unsaved change. The gear editor and the figure workbench
## write the same files, so a save in one makes the other stale. Returns
## true for a reload.
func reload_if_changed() -> bool:
	if store == null or store.has_unsaved_changes() or not store.disk_differs():
		return false

	reload()

	return true


## Give one figure file new content, and show it. An empty dictionary
## removes the file. Returns the reason for a content that does not read,
## or "". The undo history of the editor calls this routine.
func put(kind: String, key: String, data: Dictionary) -> String:
	var problem := store.put(kind, key, data)

	if not problem.is_empty():
		return problem

	_sync_stands()
	changed.emit(kind, key)

	return ""


## Give several figure files new content, and show them one time. Each row
## of `rows` is `[kind, key, data]`. Returns the reason of the first content
## that does not read, or "".
##
## A change of one name in several files uses this routine. With one
## [method put] for each file, the stands would draw between two files, with
## a name that one of them does not have yet.
func put_many(rows: Array) -> String:
	var problem := ""

	for row: Array in rows:
		var refused := store.put(row[0], row[1], row[2])

		if problem.is_empty():
			problem = refused

	_sync_stands()

	for row: Array in rows:
		changed.emit(row[0], row[1])

	return problem


func has_unsaved_changes() -> bool:
	return store != null and store.has_unsaved_changes()


## The name of each unsaved file, in sorted order.
func unsaved_names() -> PackedStringArray:
	if store == null:
		return PackedStringArray()

	return store.unsaved_names()


## Write each changed figure file. Returns the name of each one.
func save() -> PackedStringArray:
	return store.save()


# ─── The models ─────────────────────────────────────────────────────────────

## The OS path of the served model tree: the directory of `manifest.json`.
func served_models_directory() -> String:
	if models_directory.is_empty():
		return FigureStore.repo_models_directory()

	return ProjectSettings.globalize_path(models_directory)


## Read the served model tree again, and draw each stand from it. Call this
## after a model build.
func reload_models() -> void:
	models.read_manifest()
	_sync_stands()


## Write the reference body of one body type to an OS path: the body and
## the outfit of its stand, in the rest pose. Returns OK, or the error of
## the writer. A body type with no rig gives ERR_DOES_NOT_EXIST.
func export_reference(body_key: String, path: String) -> Error:
	if not store.has(FigureStore.KIND_RIG, body_key):
		return ERR_DOES_NOT_EXIST

	var looks := FigureOutfit.looks_for(store.rigs[body_key], _outfit, store.looks,
		catalog.families(), _kit, models)

	return FigureReference.export(store.rigs[body_key], looks, path, models,
		store.palette())


# ─── The outfit ─────────────────────────────────────────────────────────────

## A copy of the outfit: slot -> asset key.
func outfit() -> Dictionary:
	return _outfit.duplicate()


## Dress each stand in an outfit. The workbench drops each entry that the
## item catalog does not have.
func set_outfit(new_outfit: Dictionary) -> void:
	var valid := catalog.valid_outfit(new_outfit)

	if valid == _outfit:
		return

	_outfit = valid
	_sync_stands()
	outfit_changed.emit()


## Put one item in one slot of the outfit, and empty each slot that the item
## clears. An empty `asset_key` empties the slot. The key of the slot itself
## shows the slot shape with no item.
func wear(slot: String, asset_key: String) -> void:
	set_outfit(catalog.wear(_outfit, slot, asset_key))


## What a stand shows for the item in one slot of the outfit: a SOURCE_* of
## [FigureOutfit].
func source_of(body_key: String, slot: String) -> String:
	if not store.has(FigureStore.KIND_RIG, body_key):
		return FigureOutfit.SOURCE_NOTHING

	return FigureOutfit.source_of(store.rigs[body_key], slot, _outfit.get(slot, ""),
		store.looks, models)


## The tool type whose stance the outfit takes, or "" for the default clip
## set: the first item of the outfit, in the order of the slots, whose tool
## type has a stance.
func stance_of_outfit() -> String:
	return store.stances().stance_of(catalog.outfit_tool_types(_outfit))


# ─── The colors of the figure ───────────────────────────────────────────────

## A copy of the colors of the character on each stand: color role -> named
## color.
func figure_colors() -> Dictionary:
	return _figure_colors.duplicate()


## Give each stand the colors of one character. An entry with no text for
## its role or for its color does not go in.
func set_figure_colors(colors: Dictionary) -> void:
	var valid := {}

	for role: Variant in colors:
		if typeof(role) == TYPE_STRING and typeof(colors[role]) == TYPE_STRING \
				and not role.is_empty() and not colors[role].is_empty():
			valid[role] = colors[role]

	if valid == _figure_colors:
		return

	_figure_colors = valid
	_sync_stands()
	figure_colors_changed.emit()


## Give one color role of the character its named color. An empty
## `color_name` gives the role back to each look.
func set_figure_color(role: String, color_name: String) -> void:
	var colors := figure_colors()

	if color_name.is_empty():
		colors.erase(role)
	else:
		colors[role] = color_name

	set_figure_colors(colors)


# ─── The kit of the figure ──────────────────────────────────────────────────

## A copy of the kit of the character on each stand: kit group -> the key
## of a kit part.
func kit() -> Dictionary:
	return _kit.duplicate()


## Give each stand the kit of one character. An entry with no text for its
## group or for its key does not go in. A key that names no kit part of its
## group stays in the kit, and it draws nothing ([FigureOutfit]).
func set_kit(new_kit: Dictionary) -> void:
	var valid := {}

	for group: Variant in new_kit:
		if typeof(group) == TYPE_STRING and typeof(new_kit[group]) == TYPE_STRING \
				and not group.is_empty() and not new_kit[group].is_empty():
			valid[group] = new_kit[group]

	if valid == _kit:
		return

	_kit = valid
	_sync_stands()
	kit_changed.emit()


## Give the character one kit part of one kit group. An empty `look_key`
## takes the kit part of that group away, and the body then shows as it is.
func set_kit_part(group: String, look_key: String) -> void:
	var new_kit := kit()

	if look_key.is_empty():
		new_kit.erase(group)
	else:
		new_kit[group] = look_key

	set_kit(new_kit)


# ─── The checks ─────────────────────────────────────────────────────────────

## Check each figure file of the store, the stance table, and each clip
## ([FigureChecks]). `budgets` is the budget table of the Check tab. Returns
## the findings.
func run_checks(budgets := {}) -> Array[Dictionary]:
	return FigureChecks.run(store, catalog, models, clips, budgets)


# ─── The stands ─────────────────────────────────────────────────────────────

## The body types, in sorted order: one for each rig.
func body_keys() -> PackedStringArray:
	return store.keys_of(FigureStore.KIND_RIG)


## The figure of one body type, or null.
func figure_of(body_key: String) -> Node3D:
	if not _stands.has(body_key):
		return null

	return _stands[body_key].get_node(FigureBuilder.FIGURE_NAME)


## The body type of the stand that holds `node`, or "".
func body_of(node: Node) -> String:
	var walk := node

	while walk != null and walk != self:
		if walk.has_meta(STAND_META):
			return walk.get_meta(STAND_META)

		walk = walk.get_parent()

	return ""


## The node of one part on the stand of one body type, or null.
func part_node(body_key: String, look_key: String, part_name: String) -> Node3D:
	var figure := figure_of(body_key)

	if figure == null:
		return null

	return FigureBuilder.part_node(figure, look_key, part_name)


## The part node that a ray meets first, on any stand, or null. A part of
## the probe is no part of a figure file, so the ray goes through it.
func part_at(origin: Vector3, direction: Vector3) -> Node3D:
	return FigurePicking.pick(_file_parts(), origin, direction)


## The mesh node that a ray meets first, on any stand, or null: the node of
## one shape of a shape list, or the node of a model. Its parent is the
## part. [method FigureBuilder.shape_id] tells the two apart.
func shape_at(origin: Vector3, direction: Vector3) -> MeshInstance3D:
	return FigurePicking.pick_instance(_file_parts(), origin, direction)


## The node of one shape of one part on the stand of one body type, or
## null.
func shape_node(body_key: String, look_key: String, part_name: String,
		shape_index: int) -> MeshInstance3D:
	var figure := figure_of(body_key)

	if figure == null:
		return null

	return FigureBuilder.shape_node(figure, look_key, part_name, shape_index)


## Each part node of a look that the store has, on each stand, and each
## node of a served model. A move of a served model makes the look of its
## item when the store has none.
func _file_parts() -> Array[Node3D]:
	var parts: Array[Node3D] = []

	for body_key: String in _stands:
		for node: Node3D in FigureBuilder.part_nodes(figure_of(body_key)):
			var id := FigureBuilder.part_id(node)

			if store.has(FigureStore.KIND_LOOK, id[0]) or id[1] == FigureLook.SERVED_PART:
				parts.append(node)

	return parts


## The cost of the figure of one body type: `{parts, draws, triangles}`.
func counts_of(body_key: String) -> Dictionary:
	var figure := figure_of(body_key)

	if figure == null:
		return {"parts": 0, "draws": 0, "triangles": 0}

	return FigureBuilder.counts(figure)


## Mark one bone on each stand, or no bone for "".
func mark_bone(bone_name: String) -> void:
	_marked_bone = bone_name
	_place_marks()


## The bone that the marks show, or "".
func marked_bone() -> String:
	return _marked_bone


## The mark of one body type, or null. The plugin selects it, so the Godot
## move tool can move the bone (ENG-0011, item 30).
func mark_node(body_key: String) -> Node3D:
	if not _stands.has(body_key):
		return null

	return _stands[body_key].get_node_or_null(MARK_NAME)


## Write the place of each node that moved into its file: a part node into
## its worn look, and a bone mark into its rig. Returns true when a file
## changed. The editor calls this each frame.
func sync_from_nodes() -> bool:
	var written := _write_moved_parts()

	written.append_array(_write_moved_marks())

	if written.is_empty():
		return false

	_sync_stands()

	for pair: Array in written:
		changed.emit(pair[0], pair[1])

	return true


## Write the place of each moved part node into its worn look, and the
## place of each moved shape node into its shape. A moved served model goes
## into the `served` row of the look of its item. Returns `[kind, key]` of
## each look that changed, one time each.
func _write_moved_parts() -> Array:
	var moves := _moved_nodes()
	var shape_moves := _moved_shapes()
	var served_moves := _moved_served()
	var written := {}

	# The store changes only after the search. A part of one look has a node
	# on each stand. The node that did not move must not write its old place
	# back.
	for move: Array in moves:
		if _write_place(move[0], move[1], move[2], move[3]):
			written[move[0]] = true

	for move: Array in shape_moves:
		if _write_shape_place(move[0], move[1], move[2], move[3]):
			written[move[0]] = true

	for move: Array in served_moves:
		if _write_served_place(move[0], move[1], move[2]):
			written[move[0]] = true

	var pairs := []

	for look_key: String in written:
		pairs.append([FigureStore.KIND_LOOK, look_key])

	return pairs


## Each shape node whose place differs from its shape, as `[look key, part
## name, shape index, place]`. A shape has one place on each body type, so
## the stand does not matter. The look key is that of the look that has the
## part: for a tier, its last base.
func _moved_shapes() -> Array:
	var moves := []

	for body_key: String in _stands:
		for node: Node3D in FigureBuilder.part_nodes(figure_of(body_key)):
			var id := FigureBuilder.part_id(node)

			if not store.has(FigureStore.KIND_LOOK, id[0]) or node.get_meta(
					FigureBuilder.MODEL_META, false):
				continue

			var look: FigureLook = store.looks[id[0]].resolved(store.looks)
			var shapes: Array = look.part(id[1]).get("shapes", [])

			for index in mini(shapes.size(), node.get_child_count()):
				var instance := node.get_child(index) as Node3D

				if instance != null and not _same_place(FigureLook.shape_transform(shapes[index]),
						instance.transform):
					moves.append([parts_owner(id[0]), id[1], index, instance.transform])

	return moves


## Each node of a served model whose place differs from the row that its
## stand drew, as `[asset key, bone, place]`. A served place has no fit
## row, so the stand does not matter.
func _moved_served() -> Array:
	var moves := []

	for body_key: String in _stands:
		var rows: Dictionary = _served_rows.get(body_key, {})

		for node: Node3D in FigureBuilder.part_nodes(figure_of(body_key)):
			var id := FigureBuilder.part_id(node)
			var row: Dictionary = rows.get(id[0], {})

			if id[1] == FigureLook.SERVED_PART and not row.is_empty() \
					and not _same_place(FigureLook.part_transform(row), node.transform):
				moves.append([id[0], row["bone"], node.transform])

	return moves


## Write the place of one moved served model into the look of its item.
## An item with no look gets one with the `served` row only. Returns false
## when the store refuses the content.
func _write_served_place(asset_key: String, bone: String, xform: Transform3D) -> bool:
	var data := store.data_of(FigureStore.KIND_LOOK, asset_key)

	if data.is_empty():
		data = {"format": FigureLook.FORMAT, "key": asset_key}

	FigureLookEdits.set_served_place(data, bone, xform)

	return store.put(FigureStore.KIND_LOOK, asset_key, data).is_empty()


## Write the place of one moved shape into the store. Returns false when
## the store refuses the content.
func _write_shape_place(look_key: String, part_name: String, shape_index: int,
		xform: Transform3D) -> bool:
	var data := store.data_of(FigureStore.KIND_LOOK, look_key)

	FigureShapeEdits.set_shape_place(data, part_name, shape_index, xform)

	return store.put(FigureStore.KIND_LOOK, look_key, data).is_empty()


## Write the place of each moved bone mark into the rig of its stand.
## Returns `[kind, key]` of each rig that changed.
func _write_moved_marks() -> Array:
	var pairs := []

	for body_key: String in _stands:
		var mark := mark_node(body_key)
		var rig: FigureRig = store.rigs[body_key]

		if mark == null or not mark.visible or not rig.has_bone(_marked_bone):
			continue

		if mark.position.distance_to(rig.global_rest_of(_marked_bone).origin) > PLACE_TOLERANCE \
				and _write_bone(body_key, mark.position):
			pairs.append([FigureStore.KIND_RIG, body_key])

	return pairs


## Write the global place of the marked bone of one body type into its rig,
## as the position on the parent bone. The mirror box of the Rig tab does
## not apply to a mark. Returns false when the store refuses the content.
func _write_bone(body_key: String, global_position: Vector3) -> bool:
	var rig: FigureRig = store.rigs[body_key]
	var parent: String = rig.bone(_marked_bone).get("parent", "")
	var local := global_position
	var data := store.data_of(FigureStore.KIND_RIG, body_key)

	if not parent.is_empty():
		local = rig.global_rest_of(parent).affine_inverse() * global_position

	FigureRigEdits.set_bone_position(data, _marked_bone, local)

	return store.put(FigureStore.KIND_RIG, body_key, data).is_empty()


## Each part node whose place differs from its worn look, as
## `[look key, part name, place, body type]`. The place of a part on a
## stand is its place on that body type, with the fit. The look key is
## that of the look that has the part: for a tier, its last base.
func _moved_nodes() -> Array:
	var moves := []

	for body_key: String in _stands:
		for node: Node3D in FigureBuilder.part_nodes(figure_of(body_key)):
			var id := FigureBuilder.part_id(node)

			if not store.has(FigureStore.KIND_LOOK, id[0]):
				continue

			var look: FigureLook = store.looks[id[0]].resolved(store.looks)

			if not look.part(id[1]).is_empty() \
					and not _same_place(look.place_of(id[1], body_key), node.transform):
				moves.append([parts_owner(id[0]), id[1], node.transform, body_key])

	return moves


## The key of the look that has the parts of one look: the look itself, or
## the last base of a tier.
func parts_owner(look_key: String) -> String:
	if not store.has(FigureStore.KIND_LOOK, look_key):
		return look_key

	return store.looks[look_key].base_chain(store.looks)[-1].key()


## Write the place of one moved part into the store. The place goes into
## the fit row of the body type when the look has one. Returns false when
## the store refuses the content.
func _write_place(look_key: String, part_name: String, xform: Transform3D,
		body_key: String) -> bool:
	var data := store.data_of(FigureStore.KIND_LOOK, look_key)

	FigurePartEdits.set_part_place(data, part_name, xform, body_key)

	return store.put(FigureStore.KIND_LOOK, look_key, data).is_empty()


static func _same_place(first: Transform3D, second: Transform3D) -> bool:
	if first.origin.distance_to(second.origin) > PLACE_TOLERANCE:
		return false

	for axis in 3:
		if first.basis[axis].distance_to(second.basis[axis]) > PLACE_TOLERANCE:
			return false

	return true


## Make the stands show the store: one stand for each rig, in the order of
## the keys. A stand that stays keeps its figure and each part node. The
## palette of the store becomes the active palette, so the family stand
## and each other procedural mesh of the editor draw with it.
func _sync_stands() -> void:
	var keys := body_keys()

	FigurePalette.active = store.palette()

	for body_key: String in _stands.keys():
		if not body_key in keys:
			_stands[body_key].queue_free()
			_stands.erase(body_key)

	var time := clip_time()
	var playing := is_playing()
	var added := false

	for index in keys.size():
		var body_key := keys[index]
		var rig: FigureRig = store.rigs[body_key]

		if not _stands.has(body_key):
			_stands[body_key] = _new_stand(rig)
			added = true

		FigureBuilder.refresh(figure_of(body_key), rig, _looks_of(body_key), models,
			store.palette(), _figure_colors)
		_stands[body_key].position.x = _stand_x(index, keys.size())

	_sync_family_stand(keys.size())
	_size_floor(keys.size() + 1)
	_place_marks()

	# A new stand joins the clip of the other stands.
	if added and not _clip.is_empty() and show_clip(_clip, time) and playing:
		play_clip(_clip, time)


## The worn looks of one stand. The body is first, then each item of the
## outfit, then the probe when it shows. The row of each served part goes
## into [member _served_rows].
func _looks_of(body_key: String) -> Array:
	var looks := FigureOutfit.looks_for(store.rigs[body_key], _outfit, store.looks,
		catalog.families(), _kit, models)
	var served := {}

	for look: FigureLook in looks:
		var row := look.part(FigureLook.SERVED_PART)

		if not row.is_empty():
			served[look.key()] = row

	_served_rows[body_key] = served

	if show_probe:
		looks.append(FigureClearance.probe_look(store.rigs[body_key]))

	return looks


# ─── The clips ──────────────────────────────────────────────────────────────

## The directory of the clip files.
func clips_directory() -> String:
	return FigureClips.CLIP_DIRECTORY if clip_directory.is_empty() else clip_directory


## The OS path of the stance table: `stances.json` beside the clip
## directory.
func stances_path() -> String:
	var beside := clips_directory().get_base_dir().path_join(FigureStances.FILE_NAME)

	return ProjectSettings.globalize_path(beside)


## The OS path of the sources of the clip lists.
func sources_directory() -> String:
	if source_directory.is_empty():
		return FigureStore.repo_sources_directory()

	return ProjectSettings.globalize_path(source_directory)


## Read the clip files again, and give them to each stand. A stand that
## plays a clip that is not there any more goes to its rest pose.
func reload_clips() -> void:
	var time := clip_time()
	var playing := is_playing()

	clips = FigureClips.library_from(clips_directory())

	for body_key: String in _stands:
		FigureClips.player_of(figure_of(body_key), clips)

	if not clips.has_animation(_clip):
		stop_clip()
		return

	show_clip(_clip, time)

	if playing:
		play_clip(_clip, time)


## The clip names, in sorted order.
func clip_names() -> PackedStringArray:
	return FigureClips.names_of(clips)


## The clip that each stand shows, or "".
func shown_clip() -> String:
	return _clip


## Play one clip on each stand, from `time`. Returns false for no such clip.
func play_clip(clip_name: String, time := 0.0, speed := 1.0) -> bool:
	if not clips.has_animation(clip_name):
		return false

	_clip = clip_name

	for player: AnimationPlayer in _players():
		player.play(clip_name, -1.0, speed)
		player.seek(time, true)

	return true


## Hold each stand at one moment of one clip.
func show_clip(clip_name: String, time: float) -> bool:
	if not play_clip(clip_name, time):
		return false

	for player: AnimationPlayer in _players():
		player.pause()

	return true


## Put each stand back in its rest pose.
func stop_clip() -> void:
	_clip = ""

	for body_key: String in _stands:
		FigureClips.stop(figure_of(body_key))


## True while a clip moves the stands.
func is_playing() -> bool:
	for player: AnimationPlayer in _players():
		return player.is_playing()

	return false


## The time of the shown clip, in seconds.
func clip_time() -> float:
	for player: AnimationPlayer in _players():
		if not _clip.is_empty() and player.assigned_animation == _clip:
			return player.current_animation_position

	return 0.0


## The length of one clip in seconds, or zero for no such clip.
func clip_length(clip_name: String) -> float:
	if not clips.has_animation(clip_name):
		return 0.0

	return clips.get_animation(clip_name).length


## The player of one body type, or null. The Godot animation editor shows
## the tracks of a selected player.
func player_of(body_key: String) -> AnimationPlayer:
	if figure_of(body_key) == null:
		return null

	return FigureClips.player_of(figure_of(body_key), clips)


## One line for each body type: how near a held item comes to the body
## through one clip ([FigureClearance]).
func clearance_lines(clip_name: String) -> PackedStringArray:
	var lines := PackedStringArray()

	if not clips.has_animation(clip_name):
		return lines

	for body_key: String in body_keys():
		if store.has(FigureStore.KIND_LOOK, body_key):
			lines.append("%s, %s" % [body_key, FigureClearance.line_of(clip_name,
				FigureClearance.check(store.rigs[body_key],
					store.looks[body_key].resolved(store.looks),
					clips.get_animation(clip_name)))])

	return lines


## Make each clip file of each clip list again. Returns one line for each
## clip list. This starts Godot two times for each list, and it takes some
## seconds. The plugin runs the same steps on a thread: [method clip_build_plan],
## [method run_clip_build], then [method reload_clips].
func build_clips() -> PackedStringArray:
	var plan := clip_build_plan()
	var lines: PackedStringArray = plan["lines"]

	lines.append_array(run_clip_build(plan["rows"]))
	reload_clips()

	return lines


## The plan of a clip build: `{rows, lines}`. Each row is `[clip list,
## source directory, rig, clip directory]`, for [method run_clip_build].
## `lines` holds one line for each clip list that the build leaves out.
func clip_build_plan() -> Dictionary:
	var plan := {"rows": [], "lines": PackedStringArray()}
	var made := {}

	if body_keys().is_empty():
		plan["lines"].append("Make a rig first. A clip needs the bones of a rig.")
		return plan

	for key: String in store.keys_of(FigureStore.KIND_CLIPS):
		var list: FigureClipList = store.clip_lists[key]
		var twice := _made_twice(list, made)

		if not twice.is_empty():
			plan["lines"].append("%s: the clip %s is also in the clip list %s. Not built."
				% [key, twice, made[twice]])
			continue

		plan["rows"].append([list, sources_directory().path_join(key),
			store.rigs[body_keys()[0]], clips_directory()])

	return plan


## Build each row of a plan. Returns one line for each row. This touches no
## node and no store, so a thread can run it.
static func run_clip_build(rows: Array) -> PackedStringArray:
	var lines := PackedStringArray()

	for row: Array in rows:
		var list: FigureClipList = row[0]
		var result := FigureClipImport.build(list, row[1], row[2], row[3])

		lines.append("%s: built %d clip(s). %s" % [list.key(), result["clips"].size(),
			result["error"]])

	return lines


## The file of each clip that a build writes over: each clip of each clip
## list that is on the disk now. The build question lists them.
func overwritten_clip_files() -> PackedStringArray:
	var files := PackedStringArray()

	for key: String in store.keys_of(FigureStore.KIND_CLIPS):
		var list: FigureClipList = store.clip_lists[key]

		for clip_name: String in list.clip_names():
			var path := FigureClipImport.clip_path(clips_directory(), clip_name)

			if FileAccess.file_exists(path):
				files.append(path)

	return files


## The arguments of the import step of one clip list, for
## [method FigureClipImport.import_source] with no clip: `[clip list, source
## directory, rig]`. An empty array for no such list or no rig.
func source_clips_arguments(key: String) -> Array:
	if body_keys().is_empty() or not store.has(FigureStore.KIND_CLIPS, key):
		return []

	return [store.clip_lists[key], sources_directory().path_join(key),
		store.rigs[body_keys()[0]]]


## The first clip name of `list` that `made` has from another clip list, or
## "". This also records each clip name of `list` in `made`.
static func _made_twice(list: FigureClipList, made: Dictionary) -> String:
	for clip_name: String in list.clip_names():
		if made.has(clip_name):
			return clip_name

	for clip_name: String in list.clip_names():
		made[clip_name] = list.key()

	return ""


## The player of each stand.
func _players() -> Array[AnimationPlayer]:
	var found: Array[AnimationPlayer] = []

	for body_key: String in _stands:
		found.append(FigureClips.player_of(figure_of(body_key), clips))

	return found


func _new_stand(rig: FigureRig) -> Node3D:
	var stand := Node3D.new()

	stand.name = rig.key()
	stand.set_meta(STAND_META, rig.key())
	stand.add_child(FigureBuilder.build(rig, []))
	FigureClips.player_of(stand.get_node(FigureBuilder.FIGURE_NAME), clips)
	stand.add_child(_new_label(rig.key()))
	add_child(stand)

	return stand


## The label of a stand, above the head of its figure.
static func _new_label(text: String) -> Label3D:
	var label := Label3D.new()

	label.name = LABEL_NAME
	label.text = text
	label.position.y = LABEL_HEIGHT
	label.pixel_size = LABEL_PIXEL_SIZE
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED

	return label


## The X of the stand at `index` of `count` stands, with the family stand
## as one more at the right. The row is centred on the origin.
static func _stand_x(index: int, count: int) -> float:
	return (index - count * 0.5) * STAND_SPACING


# ─── The family stand ───────────────────────────────────────────────────────

## Show one entity on the family stand: an asset key, or "" for no art, and
## a family. The stand draws it as the game draws an entity.
func show_entity(asset_key: String, family: String) -> void:
	_shown_asset = asset_key
	_shown_family = family

	if store != null:
		_sync_family_stand(body_keys().size())


## The asset key of the entity on the family stand, or "".
func shown_asset() -> String:
	return _shown_asset


## The family of the entity on the family stand, or "".
func shown_family() -> String:
	return _shown_family


## The node that the family stand draws, or null for no entity.
func entity_node() -> Node3D:
	var stand := get_node_or_null(FAMILY_STAND_NAME)

	if stand == null:
		return null

	return stand.get_node_or_null(ENTITY_NAME)


## Draw the entity of the family stand again, from the look files as they
## are now. `stand_count` is the count of the figure stands.
func _sync_family_stand(stand_count: int) -> void:
	var stand := get_node_or_null(FAMILY_STAND_NAME) as Node3D

	if stand == null:
		stand = Node3D.new()
		stand.name = FAMILY_STAND_NAME
		stand.add_child(_new_label(""))
		add_child(stand)

	var old := entity_node()

	if old != null:
		stand.remove_child(old)
		old.free()

	_free_resolver()
	stand.position.x = _stand_x(stand_count, stand_count)
	stand.visible = not _shown_family.is_empty()
	(stand.get_node(LABEL_NAME) as Label3D).text = _entity_label()

	if not stand.visible:
		return

	_resolver = MeshResolver.from_directory(served_models_directory(), OWN_MODEL_ROOT)

	var entity := _resolver.resolve_entity(_shown_asset, _shown_family)

	entity.name = ENTITY_NAME
	entity.position.y = ENTITY_LIFT
	stand.add_child(entity)


## The label of the family stand: the family, and the asset key when one
## shows.
func _entity_label() -> String:
	if _shown_asset.is_empty():
		return _shown_family

	return "%s (%s)" % [_shown_asset, _shown_family]


func _free_resolver() -> void:
	if _resolver == null:
		return

	_resolver.free_models()
	_resolver.free()
	_resolver = null


func _exit_tree() -> void:
	_free_resolver()


## The floor below the stands, so the author sees where the feet stand.
func _size_floor(stand_count: int) -> void:
	var floor_node := get_node_or_null(FLOOR_NAME) as MeshInstance3D

	if floor_node == null:
		var material := StandardMaterial3D.new()

		floor_node = MeshInstance3D.new()
		floor_node.name = FLOOR_NAME
		floor_node.mesh = PlaneMesh.new()
		material.albedo_color = FLOOR_COLOR
		floor_node.material_override = material
		add_child(floor_node)

	(floor_node.mesh as PlaneMesh).size = Vector2(
		maxi(stand_count, 1) * STAND_SPACING + FLOOR_MARGIN, FLOOR_DEPTH)


## Put the bone mark of each stand on the marked bone.
func _place_marks() -> void:
	for body_key: String in _stands:
		var stand: Node3D = _stands[body_key]
		var mark := stand.get_node_or_null(MARK_NAME) as MeshInstance3D
		var rig: FigureRig = store.rigs[body_key]

		if mark == null:
			mark = _new_mark()
			stand.add_child(mark)

		mark.visible = rig.has_bone(_marked_bone)

		if mark.visible:
			mark.position = rig.global_rest_of(_marked_bone).origin


static func _new_mark() -> MeshInstance3D:
	var mark := MeshInstance3D.new()
	var mesh := SphereMesh.new()
	var material := StandardMaterial3D.new()

	mesh.radius = MARK_RADIUS
	mesh.height = MARK_RADIUS * 2.0
	material.albedo_color = MARK_COLOR
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.no_depth_test = true
	mark.name = MARK_NAME
	mark.mesh = mesh
	mark.material_override = material

	return mark
