extends Node
## Tests for the model of ONE part (DESIGN-0014 section 20):
## [method FigurePartEdits.part_from_model] and
## [method FigurePartEdits.clear_part_model].
##
##     godot --headless --path godot res://tests/test_figure_part_model.tscn
##
## Needs nothing running and no editor, and it writes no file. The model of
## the test is a reference body with one node: the head of the mannequin,
## moved. That is the file an author gets when they export the reference
## body, change the head in Blender, and keep the name of its node. The
## cases:
##
## 1. The head takes the node of the model, at the place of the node, and
##    each other part stays as it was.
## 2. A figure draws the model for the head and the shape list for each
##    other part.
## 3. "Shape list again" takes the model away, and only from a part with a
##    model.
## 4. A model with two nodes that name no part gives the reason, and the
##    look stays.
## 5. A part that is not there gives the reason.
## 6. A part with a fit row on the body type takes the place into that
##    row, as a gizmo move does, and the part itself keeps its place.

const TOLERANCE := 0.001

## The model of the test, and the part that takes it.
const HEAD_MODEL := "test_blender_head"
const PART := "head"

## How far the author moved the head in the modeler.
const MOVE := Vector3(0.0, 0.03, 0.02)

var _failures := 0


func _ready() -> void:
	_the_part_takes_the_node()
	_a_figure_draws_the_model_for_one_part()
	_the_shape_list_comes_back()
	_a_model_with_no_matching_node_is_refused()
	_a_missing_part_is_refused()
	_a_fit_row_takes_the_place()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: figure_part_model")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


func _rig() -> FigureRig:
	return FigureEdits.rig_from_profile("body_1")


## The head of the mannequin, moved by MOVE, as the only part of a look.
func _moved_head(rig: FigureRig) -> FigureLook:
	var data: Dictionary = FigureEdits.mannequin(rig).data.duplicate(true)
	var head: Dictionary = {}

	for row: Dictionary in data["parts"]:
		if row["name"] == PART:
			head = row

	FigureLook.set_part_transform(head, Transform3D(Basis.IDENTITY, MOVE)
		* FigureLook.part_transform(head))
	data["parts"] = [head]

	return FigureLook.from_data(data)


func _models(rig: FigureRig, looks: Array) -> FigureModels:
	var models := FigureModels.new()

	_expect(models.put_buffer(HEAD_MODEL, FigureReference.buffer_of(rig, looks)),
		"the model of the test reads")

	return models


func _the_part_takes_the_node() -> void:
	var rig := _rig()
	var data: Dictionary = FigureEdits.mannequin(rig).data.duplicate(true)
	var before: Dictionary = data.duplicate(true)
	var models := _models(rig, [_moved_head(rig)])
	var problem := FigurePartEdits.part_from_model(data, rig, PART, HEAD_MODEL, models)
	var look := FigureLook.from_data(data)
	var row := look.part(PART)
	var wanted := FigureLook.part_transform(FigureLook.from_data(before).part(PART))

	wanted = Transform3D(Basis.IDENTITY, rig.global_rest_of(row["bone"]).basis.inverse()
		* MOVE) * wanted

	_expect(problem.is_empty(), "the head takes the model: " + problem)
	_expect(row.get("model", "") == HEAD_MODEL and not str(row.get("node", "")).is_empty(),
		"the head names the model and its node")
	_expect(FigureLook.part_transform(row).origin.distance_to(wanted.origin) < TOLERANCE,
		"the head sits where the author moved it")
	_expect(not row.get("shapes", []).is_empty(), "the head keeps its shape list")

	for other: Dictionary in before["parts"]:
		if other["name"] != PART:
			_expect(look.part(other["name"]) == other, "%s stays as it was" % other["name"])


func _a_figure_draws_the_model_for_one_part() -> void:
	var rig := _rig()
	var data: Dictionary = FigureEdits.mannequin(rig).data.duplicate(true)
	var models := _models(rig, [_moved_head(rig)])

	FigurePartEdits.part_from_model(data, rig, PART, HEAD_MODEL, models)

	var look := FigureLook.from_data(data)
	var figure := FigureBuilder.build(rig, [look], models)
	var node_name: String = look.part(PART)["node"]
	var drawn_models := 0

	for part: Node3D in FigureBuilder.part_nodes(figure):
		var from_model := part.get_child_count() == 1 and part.get_child(0).name == node_name

		if from_model:
			drawn_models += 1

		_expect(from_model == (FigureBuilder.part_id(part)[1] == PART),
			"%s draws %s" % [part.name, "its model" if from_model else "its shape list"])

	_expect(drawn_models == 1, "one part draws the model (%d)" % drawn_models)
	figure.free()


func _the_shape_list_comes_back() -> void:
	var rig := _rig()
	var data: Dictionary = FigureEdits.mannequin(rig).data.duplicate(true)
	var models := _models(rig, [_moved_head(rig)])

	FigurePartEdits.part_from_model(data, rig, PART, HEAD_MODEL, models)

	_expect(FigurePartEdits.clear_part_model(data, PART).is_empty(), "the model goes")
	_expect(not FigureLook.from_data(data).part(PART).has("model"), "the head has no model")
	_expect(not FigurePartEdits.clear_part_model(data, PART).is_empty(),
		"a part with no model gives a reason")


func _a_model_with_no_matching_node_is_refused() -> void:
	var rig := _rig()
	var body := FigureEdits.mannequin(rig)
	var two := FigureLook.from_data({"format": FigureLook.FORMAT, "key": "two",
		"parts": [body.part("hand_l"), body.part("hand_r")]})
	var models := _models(rig, [two])
	var data: Dictionary = body.data.duplicate(true)
	var before: Dictionary = data.duplicate(true)
	var problem := FigurePartEdits.part_from_model(data, rig, PART, HEAD_MODEL, models)

	_expect(problem.contains("2 nodes"), "the reason counts the nodes: " + problem)
	_expect(data == before, "a refused model changes nothing")


func _a_missing_part_is_refused() -> void:
	var rig := _rig()
	var data: Dictionary = FigureEdits.mannequin(rig).data.duplicate(true)
	var models := _models(rig, [_moved_head(rig)])

	_expect(not FigurePartEdits.part_from_model(data, rig, "no_such_part", HEAD_MODEL,
		models).is_empty(), "a part that is not there gives a reason")


func _a_fit_row_takes_the_place() -> void:
	var rig := _rig()
	var data: Dictionary = FigureEdits.mannequin(rig).data.duplicate(true)
	var models := _models(rig, [_moved_head(rig)])
	var before := FigureLook.part_transform(FigureLook.from_data(data).part(PART))

	FigurePartEdits.set_part_fit(data, rig.key(), PART, true)

	var problem := FigurePartEdits.part_from_model(data, rig, PART, HEAD_MODEL, models)
	var look := FigureLook.from_data(data)
	var fitted := FigureLook.part_transform(look.fit_row(rig.key(), PART))
	var own := FigureLook.part_transform(look.part(PART))

	_expect(problem.is_empty(), "the fitted head takes the model: " + problem)
	_expect(look.part(PART).get("model", "") == HEAD_MODEL, "the fitted head names the model")
	_expect(fitted.origin.distance_to(before.origin) > TOLERANCE,
		"the place goes into the fit row")
	_expect(own.origin.distance_to(before.origin) < TOLERANCE,
		"the part itself keeps its place")
