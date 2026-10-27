@tool
class_name FigureChecks
extends RefCounted
## The content rules of the figure files, for the Check tab of the figure
## workbench (DESIGN-0014 section 7.3, Phase W6).
##
## A figure file with a fault still draws (requirement D7). The fault thus
## shows as a part that is not there, and nothing reports it. [method run]
## finds each such fault before the game does.
##
## ## A finding
##
## A finding is `{rule, kind, key, part, message}`:
##
## - `rule` is a RULE_* constant.
## - `kind` and `key` name the file: a kind of [FigureStore], or
##   [constant KIND_CLIP] for a clip file, or [constant KIND_ITEM] for an
##   item of the item catalog.
## - `part` names the part, the bone, the color role, or the body type of
##   the fault, or "".
## - `message` is for a person. A test does not compare it.
##
## A rule of [constant NOTE_RULES] gives a note. A note warns and is no
## fault ([method is_note]).
##
## ## The rules
##
## Section 7.3 of the design gives a number to each rule. The table below
## gives the constant of each number.
##
##     C1   RULE_LOOK_KEY     a look whose key names nothing
##     C2   RULE_BONE         a bone that a rig does not have
##     C2   RULE_REGION       a region that a rig does not have
##     C3   RULE_MODEL        a model that the served tree does not have
##     C3   RULE_NODE         a node that its model does not have
##     C4   RULE_NO_LOOK      an item with no worn look (a note)
##     C5   RULE_BUDGET       a look over the triangle budget of its slot
##     C6   RULE_COLOR_ROLE   a surface of a model with no color role
##     C7   RULE_STANCE       a stance with an unknown clip or tool type
##     C8   RULE_CLIP_BONE    a clip that moves a bone of no rig
##     C9   RULE_BASE         a base that is not there, or a ring of bases
##     C10  RULE_SLOT         a slot table that differs from the server
##     C11  RULE_CLEARANCE    a held item that goes into the body in a clip
##     C12  RULE_COLOR        a color name that the palette does not have
##     C13  RULE_FIT          a fit row for no body type or for no part
##     C14  RULE_RIG          a rig that cannot share a clip with the others
##     C15  RULE_BODY         a body type with no body
##     C16  RULE_FILE         a figure file that does not read
##
## Rules C11 to C16 are new in Phase W6. Phase W2 made the check of rule
## C11, and it had no number.
##
## ## The server names
##
## Rules C1, C7, and C10 compare a name with the server. The item catalog
## has those names ([FigureCatalog]). `test_figure_files.py` owns the three
## rules in the Python suite. This class gives the author the same findings
## in the workbench, with no test run. With no catalog, those rules say
## nothing.
##
## ## The budgets
##
## A budget is a count of triangles or of draws. [constant DEFAULT_BUDGETS]
## gives the start numbers. The Check tab changes them, and the dock keeps
## them in its options file. They are no figure file: a budget is a limit
## that the author sets for the work, and no fact of a figure.
##
## Nothing here needs the editor. `tests/test_figure_checks.tscn` runs each
## rule on a fixture with one fault for each rule (requirement S3).

const RULE_LOOK_KEY := "look_key"
const RULE_BONE := "bone"
const RULE_REGION := "region"
const RULE_MODEL := "model"
const RULE_NODE := "node"
const RULE_NO_LOOK := "no_look"
const RULE_BUDGET := "budget"
const RULE_COLOR_ROLE := "color_role"
const RULE_STANCE := "stance"
const RULE_CLIP_BONE := "clip_bone"
const RULE_BASE := "base"
const RULE_SLOT := "slot"
const RULE_CLEARANCE := "clearance"
const RULE_COLOR := "color"
const RULE_FIT := "fit"
const RULE_RIG := "rig"
const RULE_BODY := "body"
const RULE_FILE := "file"

## The rules that give a note.
const NOTE_RULES := [RULE_NO_LOOK]

## The kind of a finding that names a clip file, and of one that names an
## item of the item catalog. Each other kind is a kind of [FigureStore].
const KIND_CLIP := "clip"
const KIND_ITEM := "item"

## The keys of a budget table.
const BUDGET_SLOT := "each_slot"
const BUDGET_BODY := "body"
const BUDGET_TRIANGLES := "figure_triangles"
const BUDGET_DRAWS := "figure_draws"
const BUDGET_SLOTS := "slots"

## The start budgets. A worn look of one slot has [constant BUDGET_SLOT]
## triangles, and `slots` gives one slot another number. A body has
## [constant BUDGET_BODY]. A dressed figure has the two last numbers.
##
## The numbers come from the figure files of 10/13/2026. A body has 928
## triangles. The largest slot shape, that of the `body` slot, has 416. A
## figure with four items has 1,264 triangles and 58 draws. Each start
## number is a little above those. On the web export, the draw count is
## the main cost (section 12.2).
const DEFAULT_BUDGETS := {
	BUDGET_SLOT: 500,
	BUDGET_BODY: 1200,
	BUDGET_TRIANGLES: 3000,
	BUDGET_DRAWS: 100,
	BUDGET_SLOTS: {},
}

## Two rest rotations of one bone are the same below this angle, in radians.
const ROTATION_TOLERANCE := 0.001


# ─── The check ──────────────────────────────────────────────────────────────

## Check each figure file of a store. Returns the findings, sorted by rule,
## kind, key, and part. An empty list means that the files are good.
##
## - `catalog` gives the server names, or null.
## - `models` gives the served models, or null.
## - `clips` is the clip library, or null.
## - `budgets` is a budget table. A key that it does not have gets its
##   start number.
static func run(store: FigureStore, catalog: FigureCatalog, models: FigureModels,
		clips: AnimationLibrary, budgets := {}) -> Array[Dictionary]:
	var found: Array[Dictionary] = []
	var names: FigureCatalog = null

	if catalog != null and catalog.error.is_empty():
		names = catalog

	found.append_array(_check_files(store))
	found.append_array(_check_rigs(store, names))
	found.append_array(_check_looks(store, names, models))
	found.append_array(_check_colors(store))
	found.append_array(_check_budgets(store, names, models, with_defaults(budgets)))
	found.append_array(_check_stances(store, names, clips))
	found.append_array(_check_clips(store, clips))
	found.append_array(_check_items(store, names))
	found.sort_custom(_before)

	return found


## One line of text for a finding, for the Check tab.
static func describe(finding: Dictionary) -> String:
	var kind := "note" if is_note(finding) else "finding"

	return "%s %s: %s" % [kind, finding["rule"], finding["message"]]


## True for a note: a warning that is no fault.
static func is_note(finding: Dictionary) -> bool:
	return finding["rule"] in NOTE_RULES


## The findings of `found` that are no note.
static func faults_of(found: Array[Dictionary]) -> Array[Dictionary]:
	var faults: Array[Dictionary] = []

	for finding: Dictionary in found:
		if not is_note(finding):
			faults.append(finding)

	return faults


# ─── The budgets ────────────────────────────────────────────────────────────

## A budget table with each key: `budgets`, and the start number of each
## key that it does not have. A number below 1 is no budget, so it gets the
## start number also.
static func with_defaults(budgets: Dictionary) -> Dictionary:
	var full := DEFAULT_BUDGETS.duplicate(true)

	for budget_key: String in [BUDGET_SLOT, BUDGET_BODY, BUDGET_TRIANGLES, BUDGET_DRAWS]:
		if int(budgets.get(budget_key, 0)) >= 1:
			full[budget_key] = int(budgets[budget_key])

	var slots: Variant = budgets.get(BUDGET_SLOTS, {})

	if typeof(slots) == TYPE_DICTIONARY:
		for slot: Variant in slots:
			if int(slots[slot]) >= 1:
				full[BUDGET_SLOTS][str(slot)] = int(slots[slot])

	return full


## The triangle budget of a worn look of one slot.
static func slot_budget(budgets: Dictionary, slot: String) -> int:
	var full := with_defaults(budgets)

	return full[BUDGET_SLOTS].get(slot, full[BUDGET_SLOT])


## What a dressed figure has over its budget: one text for each count, or
## an empty list. `counts` is `{parts, draws, triangles}` of
## [method FigureBuilder.counts].
static func over_budget(counts: Dictionary, budgets: Dictionary) -> PackedStringArray:
	var full := with_defaults(budgets)
	var over := PackedStringArray()

	if counts.get("triangles", 0) > full[BUDGET_TRIANGLES]:
		over.append("%d triangles over" % (counts["triangles"] - full[BUDGET_TRIANGLES]))

	if counts.get("draws", 0) > full[BUDGET_DRAWS]:
		over.append("%d draws over" % (counts["draws"] - full[BUDGET_DRAWS]))

	return over


## The cost of one worn look on one rig: `{parts, draws, triangles}`.
static func counts_of(rig: FigureRig, look: FigureLook, models: FigureModels,
		palette: FigurePalette) -> Dictionary:
	var figure := FigureBuilder.build(rig, [look], models, palette)
	var counts := FigureBuilder.counts(figure)

	figure.free()

	return counts


# ─── The files and the rigs ─────────────────────────────────────────────────

## Rule C16: one finding for each file that does not read.
static func _check_files(store: FigureStore) -> Array[Dictionary]:
	var found: Array[Dictionary] = []

	for line: String in store.errors:
		found.append(_finding(RULE_FILE, "", "", "", line))

	return found


static func _check_rigs(store: FigureStore, names: FigureCatalog) -> Array[Dictionary]:
	var found: Array[Dictionary] = []
	var keys := store.keys_of(FigureStore.KIND_RIG)

	for key: String in keys:
		var rig: FigureRig = store.rigs[key]

		if not store.has(FigureStore.KIND_LOOK, key):
			found.append(_rig_finding(RULE_BODY, key, "",
				"the body type %s has no body: no worn look has its key" % key))

		found.append_array(_check_rig_tables(rig))
		found.append_array(_check_rig_slots(rig, names))
		found.append_array(_check_rig_pair(store.rigs[keys[0]], rig))

	return found


## Rule C2 for the tables of one rig: each socket, each bone of a region,
## and the bone of each slot is a bone of the rig.
static func _check_rig_tables(rig: FigureRig) -> Array[Dictionary]:
	var found: Array[Dictionary] = []

	for socket: String in rig.sockets():
		if not rig.has_bone(socket):
			found.append(_rig_finding(RULE_BONE, rig.key(), socket,
				"%s: the socket %s is no bone of the rig" % [rig.key(), socket]))

	for region: String in rig.regions():
		for bone: String in rig.regions()[region]:
			if not rig.has_bone(bone):
				found.append(_rig_finding(RULE_BONE, rig.key(), bone,
					"%s: the region %s names the bone %s, and the rig has none"
					% [rig.key(), region, bone]))

	for slot: String in rig.slots():
		if not rig.has_bone(rig.slots()[slot]):
			found.append(_rig_finding(RULE_BONE, rig.key(), slot,
				"%s: the slot %s names the bone %s, and the rig has none"
				% [rig.key(), slot, rig.slots()[slot]]))

	return found


## Rule C10: the slot table of a rig has each slot of the server, and no
## other slot.
static func _check_rig_slots(rig: FigureRig, names: FigureCatalog) -> Array[Dictionary]:
	var found: Array[Dictionary] = []

	if names == null:
		return found

	for slot: String in rig.slots():
		if not names.has_slot(slot):
			found.append(_rig_finding(RULE_SLOT, rig.key(), slot,
				"%s: the slot table names %s, and the server has no such slot"
				% [rig.key(), slot]))

	for slot: String in names.slot_keys():
		if not rig.slots().has(slot):
			found.append(_rig_finding(RULE_SLOT, rig.key(), slot,
				"%s: the slot %s of the server has no row in the slot table"
				% [rig.key(), slot]))

	return found


## Rule C14: one clip moves each body type. Thus, each rig has the bones of
## the first rig, and each bone of the body has the same rest rotation. A
## socket carries no body part and no track, so its rotation is free.
static func _check_rig_pair(first: FigureRig, rig: FigureRig) -> Array[Dictionary]:
	var found: Array[Dictionary] = []

	if first == rig:
		return found

	if first.structure() != rig.structure():
		found.append(_rig_finding(RULE_RIG, rig.key(), "",
			"%s does not have the bones of %s, so one clip cannot move the two"
			% [rig.key(), first.key()]))
		return found

	for bone: String in rig.bone_names():
		if rig.is_socket(bone) or first.is_socket(bone):
			continue

		var own := FigureJson.quaternion(rig.bone(bone)["rotation"])
		var other := FigureJson.quaternion(first.bone(bone)["rotation"])

		if own.angle_to(other) > ROTATION_TOLERANCE:
			found.append(_rig_finding(RULE_RIG, rig.key(), bone,
				"%s: the bone %s does not have the rest rotation that it has on %s"
				% [rig.key(), bone, first.key()]))

	return found


# ─── The worn looks ─────────────────────────────────────────────────────────

static func _check_looks(store: FigureStore, names: FigureCatalog,
		models: FigureModels) -> Array[Dictionary]:
	var found: Array[Dictionary] = []

	for key: String in store.keys_of(FigureStore.KIND_LOOK):
		var look: FigureLook = store.looks[key]
		var rigs := _rigs_of(store, key)
		var problem := look.base_problem(store.looks)

		if names != null and not _key_names_something(store, names, look):
			found.append(_look_finding(RULE_LOOK_KEY, key, "",
				"%s is no item, no slot, no body type, and no kit part" % key))

		if not problem.is_empty():
			found.append(_look_finding(RULE_BASE, key, "", problem))

		for region: String in look.hides():
			if not _lacking(rigs, region, true).is_empty():
				found.append(_look_finding(RULE_REGION, key, "",
					"%s hides the region %s, and %s has no such region"
					% [key, region, ", ".join(_lacking(rigs, region, true))]))

		for row: Dictionary in look.parts():
			found.append_array(_check_part(look, row, rigs))
			found.append_array(_check_part_model(store, look, row, models))

		found.append_array(_check_fit(store, look))

	return found


## Rule C1: the key of a look is an item, a slot, or a body type, or the
## look is a kit part.
static func _key_names_something(store: FigureStore, names: FigureCatalog,
		look: FigureLook) -> bool:
	if names.has_item(look.key()) or names.has_slot(look.key()):
		return true

	return store.has(FigureStore.KIND_RIG, look.key()) or not look.kit().is_empty()


## The rigs that a look must fit. A body serves its own body type. Each
## other look serves each body type (decision 10).
static func _rigs_of(store: FigureStore, look_key: String) -> Array:
	if store.has(FigureStore.KIND_RIG, look_key):
		return [store.rigs[look_key]]

	var rigs := []

	for key: String in store.keys_of(FigureStore.KIND_RIG):
		rigs.append(store.rigs[key])

	return rigs


## The key of each rig of `rigs` that does not have one bone, or one region
## when `region` is true.
static func _lacking(rigs: Array, name_of: String, region: bool) -> PackedStringArray:
	var keys := PackedStringArray()

	for rig: FigureRig in rigs:
		var has: bool = rig.regions().has(name_of) if region else rig.has_bone(name_of)

		if not has:
			keys.append(rig.key())

	return keys


## Rule C2 for one part: its bone and its region are in each rig.
static func _check_part(look: FigureLook, row: Dictionary, rigs: Array) -> Array[Dictionary]:
	var found: Array[Dictionary] = []
	var no_bone := _lacking(rigs, row["bone"], false)
	var region: String = row.get("region", "")

	if not no_bone.is_empty():
		found.append(_look_finding(RULE_BONE, look.key(), row["name"],
			"%s: the part %s is on the bone %s, and %s has no such bone"
			% [look.key(), row["name"], row["bone"], ", ".join(no_bone)]))

	if not region.is_empty() and not _lacking(rigs, region, true).is_empty():
		found.append(_look_finding(RULE_REGION, look.key(), row["name"],
			"%s: the part %s is in the region %s, and %s has no such region"
			% [look.key(), row["name"], region, ", ".join(_lacking(rigs, region, true))]))

	return found


## Rules C3 and C6 for one part with a model: the served tree has the
## model, the model has the node, and each surface of the node has the name
## of a color role.
static func _check_part_model(store: FigureStore, look: FigureLook, row: Dictionary,
		models: FigureModels) -> Array[Dictionary]:
	var found: Array[Dictionary] = []
	var model_key: String = row.get("model", "")
	var node_name: String = row.get("node", "")
	var where := "%s: the part %s" % [look.key(), row["name"]]

	if model_key.is_empty():
		return found

	if models == null or not models.has(model_key):
		found.append(_look_finding(RULE_MODEL, look.key(), row["name"],
			"%s names the model %s, and the served tree has none" % [where, model_key]))
		return found

	if not models.has_node(model_key, node_name):
		found.append(_look_finding(RULE_NODE, look.key(), row["name"],
			"%s names the node %s, and the model %s has none"
			% [where, node_name, model_key]))
		return found

	var roles := _roles_of(store, look)

	for surface: String in models.material_names(model_key, node_name):
		if not roles.has(surface):
			found.append(_look_finding(RULE_COLOR_ROLE, look.key(), row["name"],
				"%s: a surface of the node %s has the name \"%s\", which is no color role"
				% [where, node_name, surface]))

	return found


## Each color role that a surface or a shape of one look can name: the
## roles of its color table, with those of each base, and the roles of the
## palette.
static func _roles_of(store: FigureStore, look: FigureLook) -> Dictionary:
	var roles: Dictionary = look.resolved(store.looks).colors().duplicate()

	roles.merge(store.palette().roles())

	return roles


## Rule C13: each fit row names a body type with a rig, and a part of the
## look.
static func _check_fit(store: FigureStore, look: FigureLook) -> Array[Dictionary]:
	var found: Array[Dictionary] = []

	for body_key: String in look.fit():
		if not store.has(FigureStore.KIND_RIG, body_key):
			found.append(_look_finding(RULE_FIT, look.key(), body_key,
				"%s has a fit for %s, and no rig has that key" % [look.key(), body_key]))

		for row: Dictionary in look.fit()[body_key]:
			if look.part(row["part"]).is_empty():
				found.append(_look_finding(RULE_FIT, look.key(), row["part"],
					"%s has a fit row on %s for the part %s, and it has no such part"
					% [look.key(), body_key, row["part"]]))

	return found


# ─── The colors ─────────────────────────────────────────────────────────────

## Rule C12: each color name of a file is a named color. With a palette
## file, the palette has each name. With none, [MeshPalette] has it.
static func _check_colors(store: FigureStore) -> Array[Dictionary]:
	var found: Array[Dictionary] = []
	var palette := store.palette()

	for role: String in palette.role_names():
		if not _is_color(store, palette.roles()[role]):
			found.append(_finding(RULE_COLOR, FigureStore.KIND_PALETTE, FigurePalette.KEY,
				role, "the color role %s has the color %s, and the palette has none"
				% [role, palette.roles()[role]]))

	for key: String in store.keys_of(FigureStore.KIND_LOOK):
		var look: FigureLook = store.looks[key]

		for role: String in look.colors():
			if not _is_color(store, look.colors()[role]):
				found.append(_look_finding(RULE_COLOR, key, role,
					"%s gives the color role %s the color %s, and the palette has none"
					% [key, role, look.colors()[role]]))

		for row: Dictionary in look.parts():
			found.append_array(_check_shape_colors(store, look, row))

	return found


## Rule C12 for the shapes of one part: each shape names a color role or a
## named color, and a finish of the palette or of [MeshPalette].
static func _check_shape_colors(store: FigureStore, look: FigureLook,
		row: Dictionary) -> Array[Dictionary]:
	var found: Array[Dictionary] = []
	var roles := _roles_of(store, look)

	for shape: Dictionary in row.get("shapes", []):
		var color: String = shape.get("color", MeshPalette.GENERIC)
		var finish: String = shape.get("finish", FigurePalette.DEFAULT_FINISH)

		if not roles.has(color) and not _is_color(store, color):
			found.append(_look_finding(RULE_COLOR, look.key(), row["name"],
				"%s: a shape of the part %s has the color %s, which is no color role and no named color"
				% [look.key(), row["name"], color]))

		if not store.palette().has_finish(finish):
			found.append(_look_finding(RULE_COLOR, look.key(), row["name"],
				"%s: a shape of the part %s has the finish %s, and no finish has that name"
				% [look.key(), row["name"], finish]))

	return found


## True for a name that draws with a color of its own.
static func _is_color(store: FigureStore, color_name: String) -> bool:
	if store.has(FigureStore.KIND_PALETTE, FigurePalette.KEY):
		return store.palette().has_color(color_name)

	return MeshPalette.COLORS.has(color_name)


# ─── The budgets of the looks ───────────────────────────────────────────────

## Rule C5: each look with parts is in the triangle budget of its slot. A
## tier draws the mesh of its base, so only the base gets a finding.
static func _check_budgets(store: FigureStore, names: FigureCatalog, models: FigureModels,
		budgets: Dictionary) -> Array[Dictionary]:
	var found: Array[Dictionary] = []

	for key: String in store.keys_of(FigureStore.KIND_LOOK):
		var look: FigureLook = store.looks[key]
		var rigs := _rigs_of(store, key)

		if look.parts().is_empty() or rigs.is_empty():
			continue

		var triangles: int = counts_of(rigs[0], look, models, store.palette())["triangles"]
		var budget := _budget_of(store, names, budgets, key)

		if triangles > budget:
			found.append(_look_finding(RULE_BUDGET, key, "",
				"%s has %d triangles, and its budget is %d" % [key, triangles, budget]))

	return found


## The triangle budget of one look: that of a body, or that of its slot.
static func _budget_of(store: FigureStore, names: FigureCatalog, budgets: Dictionary,
		look_key: String) -> int:
	if store.has(FigureStore.KIND_RIG, look_key):
		return budgets[BUDGET_BODY]

	var slot := ""

	if names != null:
		slot = look_key if names.has_slot(look_key) else names.slot_of(look_key)

	return budgets[BUDGET_SLOTS].get(slot, budgets[BUDGET_SLOT])


# ─── The stances and the clips ──────────────────────────────────────────────

## Rule C7: each stance names a tool type of the server, and each action
## names a clip of the clip library. Each attack action is one that a swing
## of the server can name (10/25/2026). A typed one never plays.
static func _check_stances(store: FigureStore, names: FigureCatalog,
		clips: AnimationLibrary) -> Array[Dictionary]:
	var found: Array[Dictionary] = []
	var table := store.stances()
	var sets := {"": table.default_set()}

	sets.merge(table.stances())

	for tool_type: String in sets:
		var stance := "the default clip set" if tool_type.is_empty() \
			else "the stance of " + tool_type

		if names != null and not tool_type.is_empty() \
				and not tool_type in names.tool_types():
			found.append(_finding(RULE_STANCE, FigureStore.KIND_STANCES, FigureStances.KEY,
				tool_type, "the server has no tool type %s" % tool_type))

		for action: String in sets[tool_type]:
			var clip: String = sets[tool_type][action]

			if names != null and FigureStances.is_attack_action(action) \
					and not action in names.attack_actions():
				found.append(_finding(RULE_STANCE, FigureStore.KIND_STANCES,
					FigureStances.KEY, "%s/%s" % [tool_type, action],
					"%s names the action %s, and no swing of the server names it"
					% [stance, action]))

			if clips != null and not clips.has_animation(clip):
				found.append(_finding(RULE_STANCE, FigureStore.KIND_STANCES,
					FigureStances.KEY, "%s/%s" % [tool_type, action],
					"%s names the clip %s for %s, and the clip library has none"
					% [stance, clip, action]))

	return found


## Rules C8 and C11 for each clip of the library.
static func _check_clips(store: FigureStore, clips: AnimationLibrary) -> Array[Dictionary]:
	var found: Array[Dictionary] = []

	if clips == null:
		return found

	for clip_name: String in FigureClips.names_of(clips):
		var clip := clips.get_animation(clip_name)

		for bone: String in FigureClips.bones_of(clip):
			var rigs := _lacking(_rigs_of(store, ""), bone, false)

			if not rigs.is_empty():
				found.append(_finding(RULE_CLIP_BONE, KIND_CLIP, clip_name, bone,
					"the clip %s moves the bone %s, and %s has no such bone"
					% [clip_name, bone, ", ".join(rigs)]))

		found.append_array(_check_clearance(store, clip_name, clip))

	return found


## Rule C11: a held item stays clear of the body through one clip, on each
## body type ([FigureClearance]).
static func _check_clearance(store: FigureStore, clip_name: String,
		clip: Animation) -> Array[Dictionary]:
	var found: Array[Dictionary] = []

	for body_key: String in store.keys_of(FigureStore.KIND_RIG):
		if not store.has(FigureStore.KIND_LOOK, body_key):
			continue

		var result := FigureClearance.check(store.rigs[body_key],
			store.looks[body_key].resolved(store.looks), clip, store.held_in(clip_name))

		if not FigureClearance.is_clear(result):
			found.append(_finding(RULE_CLEARANCE, KIND_CLIP, clip_name, body_key,
				"%s, %s" % [body_key, FigureClearance.line_of(clip_name, result)]))

	return found


# ─── The items ──────────────────────────────────────────────────────────────

## Rule C4, a note: an item with no worn look. Its slot shape draws.
static func _check_items(store: FigureStore, names: FigureCatalog) -> Array[Dictionary]:
	var found: Array[Dictionary] = []

	if names == null:
		return found

	for row: Dictionary in names.items():
		if not store.has(FigureStore.KIND_LOOK, row["key"]):
			found.append(_finding(RULE_NO_LOOK, KIND_ITEM, row["key"], "",
				"%s (%s) has no worn look, so the slot shape of %s draws"
				% [row["key"], row["name"], row["slot"]]))

	return found


# ─── Helpers ────────────────────────────────────────────────────────────────

static func _finding(rule: String, kind: String, key: String, part: String,
		message: String) -> Dictionary:
	return {"rule": rule, "kind": kind, "key": key, "part": part, "message": message}


static func _rig_finding(rule: String, key: String, part: String,
		message: String) -> Dictionary:
	return _finding(rule, FigureStore.KIND_RIG, key, part, message)


static func _look_finding(rule: String, key: String, part: String,
		message: String) -> Dictionary:
	return _finding(rule, FigureStore.KIND_LOOK, key, part, message)


## The order of two findings: by rule, kind, key, part, and then message.
static func _before(first: Dictionary, second: Dictionary) -> bool:
	for field: String in ["rule", "kind", "key", "part", "message"]:
		if first[field] != second[field]:
			return first[field] < second[field]

	return false
