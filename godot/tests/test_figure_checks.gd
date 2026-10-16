extends Node
## Tests for the content rules of the figure files (DESIGN-0014 section
## 7.3, Phase W6): [FigureChecks], the Check tab, and the budget line.
##
##     godot --headless --path godot res://tests/test_figure_checks.tscn
##
## Needs nothing running and no editor. It writes only below `user://`.
##
## The fixture is a store that this test makes: three rigs, two bodies, one
## slot shape for each slot, a palette, a stance table, an item catalog, a
## model, and a clip library. The cases:
##
## 1. The fixture with no fault gives no finding. It gives one note for
##    each item with no worn look.
## 2. The fixture with one fault for each rule gives each finding of
##    [constant EXPECTED], and no other.
## 3. With no catalog, the rules of the server names say nothing.
## 4. A budget table gets each start number, and a slot can have its own.
## 5. The Check tab shows each finding, hides the notes on request, and
##    sends the finding of a clicked row. Its budget fields make a table.
## 6. The budget line of the dock says when a figure is over its budget.
## 7. The figure files of the repository have no finding.

const RIG := FigureStore.KIND_RIG
const LOOK := FigureStore.KIND_LOOK
const PALETTE := FigureStore.KIND_PALETTE
const STANCES := FigureStore.KIND_STANCES

const MODEL := "test_model"
const SECONDS := 1.0

## The part of the hips height that a clip of the fixture holds the hips
## at: the hips of the rest pose.
const HIPS_PART := 1.0

## Each finding of the fixture with its faults: `[rule, kind, key, part]`,
## in the order of [method FigureChecks.run].
const EXPECTED := [
	["base", "looks", "test_axe", ""],
	["body", "rigs", "body_3", ""],
	["bone", "looks", "test_sword", "p_bone"],
	["bone", "rigs", "body_2", "Ghost"],
	["bone", "rigs", "body_2", "neck"],
	["bone", "rigs", "body_2", "phantom"],
	["budget", "looks", "head", ""],
	["clearance", "clip", "stab", "body_1"],
	["clearance", "clip", "stab", "body_2"],
	["clip_bone", "clip", "wag", "Tail"],
	["color", "looks", "test_sword", "metal"],
	["color", "looks", "test_sword", "p_bone"],
	["color", "palette", "palette", "ghost"],
	["color_role", "looks", "test_sword", "p_role"],
	["file", "", "", ""],
	["fit", "looks", "test_sword", "body_9"],
	["fit", "looks", "test_sword", "nope"],
	["look_key", "looks", "stray_look", ""],
	["model", "looks", "test_sword", "p_model"],
	["no_look", "item", "test_helm", ""],
	["node", "looks", "test_sword", "p_node"],
	["region", "looks", "test_sword", ""],
	["region", "looks", "test_sword", "p_region"],
	["rig", "rigs", "body_2", "Head"],
	["slot", "rigs", "body_2", "ammo"],
	["slot", "rigs", "body_2", "tail_slot"],
	["stance", "stances", "stances", "laser"],
	["stance", "stances", "stances", "laser/idle"],
]

var _failures := 0
var _scratch := ""


func _ready() -> void:
	_scratch = ProjectSettings.globalize_path("user://figure_checks_test_%d"
		% Time.get_ticks_usec())

	_a_good_fixture_has_no_finding()
	_each_fault_has_its_finding()
	_no_catalog_means_no_server_rule()
	_a_budget_table_has_each_number()
	_the_check_tab_shows_the_findings()
	_the_budget_line_names_a_figure_over_its_budget()
	_the_repository_files_have_no_finding()
	_remove_scratch(_scratch)

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: figure_checks")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


# ─── The fixture ────────────────────────────────────────────────────────────

## The item catalog of the fixture: each slot of a new rig, three items,
## and one tool type.
func _catalog() -> FigureCatalog:
	var slots := []
	var items := []

	for slot: String in FigureEdits.SLOTS:
		slots.append({"key": slot, "label": slot, "clears": []})

	for row: Array in [["test_axe", "main_hand", "axe"], ["test_helm", "head", ""],
			["test_sword", "main_hand", "sword"]]:
		items.append({"key": row[0], "name": row[0], "slot": row[1], "tool_type": row[2],
			"tier": 1, "family": "weapon"})

	return FigureCatalog.from_data({"format": 1, "slots": slots, "items": items,
		"tool_types": ["axe", "sword"], "npcs": []})


## A store with no fault, saved in `directory`: two rigs with a body, each
## slot shape, the start palette, and a stance table with one clip.
func _good_store(directory: String) -> FigureStore:
	var store := FigureStore.new(directory, directory.path_join("stances.json"))
	var first := FigureEdits.rig_from_profile("body_1")

	for pair: Array in [["body_1", 1.0], ["body_2", 0.95]]:
		var rig := FigureEdits.rig_from_profile(pair[0], pair[1])

		store.put(RIG, pair[0], rig.data)
		store.put(LOOK, pair[0], FigureEdits.mannequin(rig).data)

	for slot: String in FigureEdits.SLOTS:
		store.put(LOOK, slot, FigureEdits.slot_shape(first, slot).data)

	store.put(LOOK, "hair_test", FigureEdits.new_kit_part("hair_test", "hair", first,
		"head_top"))
	store.put(PALETTE, PALETTE, FigureEdits.new_palette().data)

	var stances := FigureEdits.new_stances()

	FigureEdits.set_stance_clip(stances, "", "idle", "idle")
	store.put(STANCES, STANCES, stances)
	store.save()

	return store


## A clip that turns one bone a little from its rest, and that holds the
## hips at their height.
func _clip_for(rig: FigureRig, bone: String, turn: Quaternion) -> Animation:
	var clip := Animation.new()
	var rest := rig.rest_of(bone).basis.get_rotation_quaternion()
	var track := clip.add_track(Animation.TYPE_ROTATION_3D)
	var hips := clip.add_track(Animation.TYPE_POSITION_3D)

	clip.length = SECONDS
	clip.track_set_path(track, FigureClips.track_path(bone))
	clip.rotation_track_insert_key(track, 0.0, rest)
	clip.rotation_track_insert_key(track, SECONDS, rest * turn)
	clip.track_set_path(hips, FigureClips.track_path(FigureRig.SCALE_BONE))
	clip.position_track_insert_key(hips, 0.0, Vector3(0.0, HIPS_PART, 0.0))
	clip.position_track_insert_key(hips, SECONDS, Vector3(0.0, HIPS_PART, 0.0))

	return clip


## The clip library of the fixture. With `faults`, it has two more clips:
## one that moves a bone of no rig, and one that puts a held item into the
## other arm.
func _clips(rig: FigureRig, faults: bool) -> AnimationLibrary:
	var library := AnimationLibrary.new()
	var arm := "RightUpperArm"
	var in_figure := rig.global_rest_of(arm).basis.get_rotation_quaternion()

	library.add_animation("idle", _clip_for(rig, "Head", Quaternion(Vector3.UP, 0.1)))

	if faults:
		var wag := _clip_for(rig, "Head", Quaternion.IDENTITY)

		wag.track_set_path(0, FigureClips.track_path("Tail"))
		library.add_animation("wag", wag)
		# The right arm turns half a circle about the up axis of the figure.
		library.add_animation("stab", _clip_for(rig, arm,
			in_figure.inverse() * Quaternion(Vector3.UP, PI) * in_figure))

	return library


## The models of the fixture: one model with two nodes. The surface of the
## node `good` has the name of a color role. That of `odd` has no such
## name.
func _models(rig: FigureRig) -> FigureModels:
	var models := FigureModels.new()
	var art := FigureLook.from_data({"format": 1, "key": MODEL,
		"colors": {"metal": MeshPalette.STEEL, "mystery": MeshPalette.STEEL}, "parts": [
		{"name": "good", "bone": "hand_r", "shapes": [{"shape": "box", "color": "metal"}]},
		{"name": "odd", "bone": "hand_r", "shapes": [{"shape": "box", "color": "mystery"}]},
	]})

	_expect(models.put_buffer(MODEL, FigureReference.buffer_of(rig, [art])),
		"the model of the fixture reads")

	return models


## Give a saved store one fault for each rule, and read it again.
func _add_faults(store: FigureStore) -> FigureStore:
	var rig := store.data_of(RIG, "body_2")
	var head: Dictionary = rig["bones"][FigureEdits._bone_index(rig, "Head")]
	var palette := store.data_of(PALETTE, PALETTE)
	var stances := store.data_of(STANCES, STANCES)
	var stray := store.data_of(LOOK, "head")

	rig["slots"]["tail_slot"] = "Hips"
	rig["slots"].erase("ammo")
	rig["slots"]["neck"] = "NoBone"
	rig["regions"]["torso"].append("Ghost")
	rig["sockets"].append("phantom")
	head["rotation"] = FigureJson.from_quaternion(Quaternion(Vector3.UP, 0.5))
	store.put(RIG, "body_2", rig)
	store.put(RIG, "body_3", FigureEdits.rig_from_profile("body_3", 0.9).data)
	palette["roles"]["ghost"] = "no_color"
	store.put(PALETTE, PALETTE, palette)
	stances["stances"]["laser"] = {"idle": "gone_clip"}
	store.put(STANCES, STANCES, stances)
	stray["key"] = "stray_look"
	store.put(LOOK, "stray_look", stray)
	store.put(LOOK, "test_axe", {"format": 1, "key": "test_axe", "base": "nothing_there"})
	store.put(LOOK, "test_sword", _faulty_sword())
	store.save()

	var broken := FileAccess.open(store.path_of(LOOK, "broken"), FileAccess.WRITE)

	broken.store_string("{ this is not JSON")
	broken.close()

	var read := FigureStore.new(store.directory, store.stances_path)

	read.load_all()

	return read


## The worn look of the fixture with a fault in each key.
func _faulty_sword() -> Dictionary:
	var box := {"shape": "box", "size": [0.05, 0.05, 0.05], "color": "metal"}
	var odd_color := box.duplicate()

	odd_color["color"] = "mystery"

	return {"format": 1, "key": "test_sword",
		"hides": ["wings"],
		"colors": {"metal": "no_such_color"},
		"fit": {"body_9": [{"part": "p_bone"}], "body_1": [{"part": "nope"}]},
		"parts": [
			{"name": "p_bone", "bone": "Tail", "shapes": [odd_color]},
			{"name": "p_region", "bone": "hand_r", "region": "wings", "shapes": [box]},
			{"name": "p_model", "bone": "hand_r", "model": "gone_model", "node": "any"},
			{"name": "p_node", "bone": "hand_r", "model": MODEL, "node": "no_such_node"},
			{"name": "p_role", "bone": "hand_r", "model": MODEL, "node": MODEL + "__odd"},
			{"name": "p_good", "bone": "hand_r", "model": MODEL, "node": MODEL + "__good"},
		]}


## `[rule, kind, key, part]` of each finding, as one line each.
func _lines(found: Array) -> PackedStringArray:
	var lines := PackedStringArray()

	for finding: Variant in found:
		if finding is Dictionary:
			lines.append("%s|%s|%s|%s" % [finding["rule"], finding["kind"], finding["key"],
				finding["part"]])
		else:
			lines.append("|".join(PackedStringArray(finding)))

	return lines


# ─── The cases ──────────────────────────────────────────────────────────────

func _a_good_fixture_has_no_finding() -> void:
	var store := _good_store(_scratch.path_join("good"))
	var rig: FigureRig = store.rigs["body_1"]
	var found := FigureChecks.run(store, _catalog(), _models(rig), _clips(rig, false))
	var faults := FigureChecks.faults_of(found)

	_expect(faults.is_empty(), "a fixture with no fault has no finding: %s" % [_lines(faults)])
	_expect(found.size() == _catalog().items().size(),
		"each item with no worn look gives one note: %s" % [_lines(found)])

	for finding: Dictionary in found:
		_expect(FigureChecks.is_note(finding)
			and FigureChecks.describe(finding).begins_with("note "),
			"an item with no worn look is a note, and its line says so")


func _each_fault_has_its_finding() -> void:
	var store := _add_faults(_good_store(_scratch.path_join("faults")))
	var rig: FigureRig = store.rigs["body_1"]
	var budgets := {FigureChecks.BUDGET_SLOTS: {"head": 1}}
	var found := FigureChecks.run(store, _catalog(), _models(rig), _clips(rig, true), budgets)
	var lines := _lines(found)
	var wanted := _lines(EXPECTED)

	for line: String in wanted:
		_expect(line in lines, "the check finds the fault %s" % line)

	for line: String in lines:
		_expect(line in wanted, "the check finds no other fault: %s" % line)

	_expect(lines == wanted, "the findings are in the order of rule, kind, key, and part")

	for finding: Dictionary in found:
		_expect(not finding["message"].is_empty(), "each finding has a message")


func _no_catalog_means_no_server_rule() -> void:
	var store := _add_faults(_good_store(_scratch.path_join("no_catalog")))
	var rig: FigureRig = store.rigs["body_1"]
	var broken := FigureCatalog.from_data({})

	for catalog: FigureCatalog in [null, broken]:
		var rules := {}

		for finding: Dictionary in FigureChecks.run(store, catalog, _models(rig), null):
			rules[finding["rule"]] = true

		_expect(not rules.has(FigureChecks.RULE_LOOK_KEY)
			and not rules.has(FigureChecks.RULE_SLOT)
			and not rules.has(FigureChecks.RULE_NO_LOOK),
			"with no catalog, the rules of the server names say nothing")
		_expect(rules.has(FigureChecks.RULE_BONE) and rules.has(FigureChecks.RULE_BASE),
			"with no catalog, each other rule still runs")
		_expect(not rules.has(FigureChecks.RULE_CLIP_BONE),
			"with no clip library, the rules of a clip say nothing")


func _a_budget_table_has_each_number() -> void:
	var start: Dictionary = FigureChecks.DEFAULT_BUDGETS
	var full := FigureChecks.with_defaults({FigureChecks.BUDGET_BODY: 50,
		FigureChecks.BUDGET_DRAWS: 0, FigureChecks.BUDGET_SLOTS: {"head": 7, "feet": 0}})

	_expect(full[FigureChecks.BUDGET_BODY] == 50
		and full[FigureChecks.BUDGET_SLOT] == start[FigureChecks.BUDGET_SLOT],
		"a table keeps its own number, and gets each start number that it lacks")
	_expect(full[FigureChecks.BUDGET_DRAWS] == start[FigureChecks.BUDGET_DRAWS],
		"a number below 1 is no budget")
	_expect(FigureChecks.slot_budget(full, "head") == 7
		and FigureChecks.slot_budget(full, "feet") == start[FigureChecks.BUDGET_SLOT],
		"a slot has its own budget, or that of each slot")
	_expect(start[FigureChecks.BUDGET_SLOTS].is_empty(),
		"the start table is not changed by a table with a slot")

	var limit: int = start[FigureChecks.BUDGET_TRIANGLES]

	_expect(FigureChecks.over_budget({"triangles": limit, "draws": 1}, {}).is_empty()
		and FigureChecks.over_budget({"triangles": limit + 3, "draws": 1}, {}).size() == 1,
		"a figure at its budget is not over it, and one above it is")


func _the_check_tab_shows_the_findings() -> void:
	var panel := FigureCheckPanel.new()
	var found: Array[Dictionary] = [
		{"rule": FigureChecks.RULE_BONE, "kind": LOOK, "key": "a", "part": "p", "message": "m"},
		{"rule": FigureChecks.RULE_NO_LOOK, "kind": "item", "key": "b", "part": "",
			"message": "n"}]
	var sent := []

	add_child(panel)
	panel.finding_chosen.connect(func(finding: Dictionary) -> void: sent.append(finding))
	panel.set_findings(found)
	_expect(panel._findings.item_count == 2 and panel._summary.text.contains("1 finding"),
		"the tab has one row for each finding, and it counts the faults")
	panel._findings.item_selected.emit(0)
	_expect(sent.size() == 1 and sent[0]["key"] == "a", "a click sends the finding of the row")
	panel._notes.button_pressed = false
	_expect(panel._findings.item_count == 1, "the tab hides each note on request")

	var changed := []

	panel.budgets_changed.connect(func(budgets: Dictionary) -> void: changed.append(budgets))
	panel.set_budgets({FigureChecks.BUDGET_BODY: 77}, PackedStringArray(["head", "feet"]))
	_expect(changed.is_empty() and panel.budgets()[FigureChecks.BUDGET_BODY] == 77,
		"the tab shows a budget table, and it sends no change for that")
	(panel._slot_fields["head"] as SpinBox).value = 12
	_expect(changed.size() == 1 and changed[0][FigureChecks.BUDGET_SLOTS] == {"head": 12},
		"a changed field sends the budget table, with the slot")
	panel.queue_free()


func _the_budget_line_names_a_figure_over_its_budget() -> void:
	var dock := FigureDock.new()
	var limit: int = FigureChecks.DEFAULT_BUDGETS[FigureChecks.BUDGET_DRAWS]

	dock.persist = false
	add_child(dock)
	dock.set_cost({"parts": 1, "draws": limit, "triangles": 10})
	_expect(dock._cost.text.contains("%d of %d draw" % [limit, limit])
		and not dock._cost.text.contains("OVER"),
		"the budget line gives each count against its budget")
	dock.set_cost({"parts": 1, "draws": limit, "triangles": 10},
		{FigureChecks.BUDGET_DRAWS: limit - 1})
	_expect(dock._cost.text.contains("OVER"), "the budget line says when a count is over")
	_expect(dock._tabs.get_tab_title(dock._tabs.get_tab_count() - 1) == FigureDock.TAB_CHECK
		and dock.check_panel() != null, "the Check tab is the last tab of the dock")
	_expect(dock.saved_budgets().is_empty() and dock.saved_kit().is_empty(),
		"a dock that does not persist reads no option")
	dock.queue_free()


## The proof for the repository: its figure files have no finding. A note
## is no fault, and each item with no worn look gives one.
func _the_repository_files_have_no_finding() -> void:
	var store := FigureStore.new(FigureStore.repo_directory(),
		ProjectSettings.globalize_path(FigureStances.STANCES_PATH))

	store.load_all()

	var faults := FigureChecks.faults_of(FigureChecks.run(store, FigureCatalog.read_file(),
		FigureModels.from_directory(FigureStore.repo_models_directory()),
		FigureClips.library_from(FigureClips.CLIP_DIRECTORY)))

	_expect(not store.keys_of(RIG).is_empty(), "the repository has a rig")

	for finding: Dictionary in faults:
		_expect(false, "the repository: " + FigureChecks.describe(finding))


func _remove_scratch(path: String) -> void:
	if not DirAccess.dir_exists_absolute(path):
		return

	for child: String in DirAccess.get_directories_at(path):
		_remove_scratch(path.path_join(child))

	for file_name: String in DirAccess.get_files_at(path):
		DirAccess.remove_absolute(path.path_join(file_name))

	DirAccess.remove_absolute(path)
