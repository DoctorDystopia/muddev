extends Node
## Tests for the Models dock (11/02/2026): [ModelForm], the GUI of
## `python -m assets.pipeline add`, and its bridge [ModelPipeline].
##
##     godot --headless --path godot res://tests/test_model_form.tscn
##
## The form cases need nothing running. The answers are hand-built in the
## shape that `blackout/assets/pipeline/form.py` writes. The last case runs
## the real pipeline once, read-only: `add-options` and `add-check` write
## nothing. The cases:
##
## 1. The lists fill from `add-options`. The origin starts on its first
##    row. The license, the family and the source start with no choice.
## 2. Each origin puts only the fields of its own sections in the plan.
## 3. An answer shows each problem under its field and each default as the
##    hint. Write is on only for a ready plan.
## 4. A pick of the offer puts the key in the asset key field.
## 5. A lookup puts the Poly Haven model in the plan. A new id clears it.
## 6. A good write clears the fields of the model and asks for the lists.
##    A bad write keeps them and shows each problem.
## 7. The export plan of the gear editor, and the problem text.
## 8. The bridge runs the real pipeline and reads its answer.

var _failures := 0
var _options_asked := 0


func _ready() -> void:
	_the_lists_fill_and_the_choices_start_empty()
	_each_origin_gives_only_its_own_fields()
	_an_answer_shows_problems_and_turns_write_on_when_ready()
	_a_pick_of_the_offer_fills_the_key()
	_a_lookup_goes_into_the_plan()
	_a_write_clears_the_model_or_shows_its_problems()
	_the_export_plan_and_the_problem_text()
	_the_bridge_runs_the_real_pipeline()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: model_form")
	get_tree().quit(0)


func _options() -> Dictionary:
	return {"format": 1, "problem": "",
		"origins": [
			{"key": ModelPipeline.ORIGIN_FILE, "label": "A file"},
			{"key": ModelPipeline.ORIGIN_POLYHAVEN, "label": "A Poly Haven model"},
			{"key": ModelPipeline.ORIGIN_SOURCE, "label": "A source"},
			{"key": ModelPipeline.ORIGIN_EXPORT, "label": "An export"}],
		"licenses": [{"spdx": "CC0-1.0", "name": "CC0 1.0", "note": ""},
			{"spdx": "CC-BY-4.0", "name": "CC BY 4.0", "note": ""}],
		"families": [{"key": "items", "label": "items"}, {"key": "npcs", "label": "npcs"}],
		"sources": [{"id": "itch_kit", "label": "itch_kit (CC0)", "problem": "", "refusal": ""},
			{"id": "itch_empty", "label": "itch_empty", "problem": "no model file",
				"refusal": ""}],
		"model_suffixes": [".glb", ".gltf"], "zip_suffix": ".zip"}


func _form() -> ModelForm:
	var form := ModelForm.new()

	add_child(form)
	form.options_wanted.connect(func() -> void: _options_asked += 1)
	form.show_options(_options())

	return form


## Choose the row of `key` in a list, as a click does.
func _choose(list: OptionButton, key: String) -> void:
	for index: int in list.item_count:
		if str(list.get_item_metadata(index)) == key:
			list.select(index)
			list.item_selected.emit(index)
			return

	_expect(false, "the list has the key %s" % key)


func _the_lists_fill_and_the_choices_start_empty() -> void:
	var form := _form()

	_expect(form.origin() == ModelPipeline.ORIGIN_FILE, "the origin starts on its first row")
	_expect(form._license.selected == -1, "the license starts with no choice")
	_expect(form._family.selected == -1, "the family starts with no choice")
	_expect(form._source.selected == -1, "the source starts with no choice")
	_expect(form._license.item_count == 3, "the license list ends with another license")
	_expect(form._source.is_item_disabled(1), "a source with a problem cannot be chosen")
	_expect(form._filters.size() == 2, "the file dialog has models and .zip files")
	_expect(form.upload_mode() == FileDialog.FILE_MODE_OPEN_ANY, "a file origin takes a folder")
	form.free()


func _each_origin_gives_only_its_own_fields() -> void:
	var form := _form()

	form._upload.text = "C:/models/crate.glb"
	form._polyhaven.text = "wooden_crate_01"
	_choose(form._license, "CC0-1.0")
	_choose(form._family, "items")

	var from_file := form.plan()

	_expect(from_file[ModelPipeline.FIELD_UPLOAD] == "C:/models/crate.glb", "a file gives its path")
	_expect(from_file[ModelPipeline.FIELD_LICENSE] == "CC0-1.0", "a file gives its license")
	_expect(from_file[ModelPipeline.FIELD_FAMILY] == "items", "the family is in each plan")
	_expect(not from_file.has(ModelPipeline.FIELD_POLYHAVEN), "a file gives no Poly Haven id")

	_choose(form._origin, ModelPipeline.ORIGIN_POLYHAVEN)
	var from_polyhaven := form.plan()

	_expect(from_polyhaven[ModelPipeline.FIELD_POLYHAVEN] == "wooden_crate_01",
		"a Poly Haven model gives its id")
	_expect(not from_polyhaven.has(ModelPipeline.FIELD_UPLOAD), "it gives no upload")
	_expect(form._sections[ModelForm.SECTION_UPLOAD].visible == false, "the upload hides")

	_choose(form._origin, ModelPipeline.ORIGIN_EXPORT)
	var from_export := form.plan()

	_expect(from_export.has(ModelPipeline.FIELD_AUTHOR), "an export gives its author")
	_expect(not from_export.has(ModelPipeline.FIELD_LICENSE), "an export gives no license")
	_expect(form.upload_mode() == FileDialog.FILE_MODE_OPEN_FILE, "an export is one file")

	_choose(form._origin, ModelPipeline.ORIGIN_SOURCE)
	_choose(form._source, "itch_kit")
	_expect(form.plan()[ModelPipeline.FIELD_SOURCE_ID] == "itch_kit", "a source gives its id")
	form.free()


func _an_answer_shows_problems_and_turns_write_on_when_ready() -> void:
	var form := _form()
	var key_note: Label = form._notes[ModelPipeline.FIELD_ASSET_KEY][0]

	form.show_answer({"ready": false,
		"problems": {ModelPipeline.FIELD_ASSET_KEY: "crate has the key crate already."},
		"defaults": {ModelPipeline.FIELD_TITLE: "Crate"}, "model_files": ["a.glb", "b.glb"]})
	_expect(key_note.visible and key_note.text.contains("already"), "a problem shows")
	_expect(form._title.placeholder_text.contains("Crate"), "a default is the hint")
	_expect(form._model_file.item_count == 2, "each model file is a row")
	_expect(form._write.disabled, "a plan with a problem cannot be written")

	form.show_answer({"ready": false,
		"warnings": {ModelPipeline.FIELD_ASSET_KEY: "The game names no entity with ..."}})
	_expect(form._keep_unnamed.visible, "a key warning shows its box")
	_expect(form._write.disabled, "a warning with no yes cannot be written")

	form.show_answer({"ready": true, "files": [{"path": "models/items/crate.toml", "note": "",
		"text": "source = \"itch_kit\""}]})
	_expect(not key_note.visible, "a note goes when its problem goes")
	_expect(form._preview.text.contains("models/items/crate.toml"), "each file shows")
	_expect(not form._write.disabled, "a ready plan can be written")
	form.free()


func _a_pick_of_the_offer_fills_the_key() -> void:
	var form := _form()

	form.show_answer({"offered": [
		{"key": "gunbench", "kind": "station", "name": "gunsmith bench", "worn_look": false},
		{"key": "iron_helm", "kind": "armor", "name": "iron helm", "worn_look": true}]})
	_expect(form._offered.item_count == 3, "the offer has a heading and one row per key")
	form._offered.select(2)
	form._offered.item_selected.emit(2)
	_expect(form._asset_key.text == "iron_helm", "a pick fills the asset key")
	_expect(form._offered.selected == 0, "the list goes back to its heading")
	form.free()


func _a_lookup_goes_into_the_plan() -> void:
	var form := _form()

	_choose(form._origin, ModelPipeline.ORIGIN_POLYHAVEN)
	form._polyhaven.text = "wooden_crate_01"
	form.show_look_up({"ok": true, "title": "Wooden Crate 01", "author": "Jane Doe",
		"model_file": "wooden_crate_01_1k.gltf", "file_count": 3})

	var plan := form.plan()

	_expect(plan[ModelPipeline.FIELD_MODEL_FILE] == "wooden_crate_01_1k.gltf",
		"the lookup gives the model file")
	_expect(plan[ModelPipeline.FIELD_AUTHOR] == "Jane Doe", "the lookup gives the author")

	form._polyhaven.text_changed.emit("other_id")
	_expect(form.plan()[ModelPipeline.FIELD_MODEL_FILE] == "", "a new id clears the lookup")
	form.free()


func _a_write_clears_the_model_or_shows_its_problems() -> void:
	var form := _form()
	var asked := _options_asked

	form._asset_key.text = "crate"
	form.set_busy("Writing ...")
	_expect(form._write.disabled, "a running write turns Write off")
	form.show_written({"ok": false, "problem": "The plan is not ready.",
		"problems": {ModelPipeline.FIELD_FAMILY: "Choose a family."}})
	_expect(form._status.text.contains("Choose a family."), "a bad write shows each problem")
	_expect(form._asset_key.text == "crate", "a bad write keeps the fields")

	form.show_written({"ok": true, "asset_key": "crate", "built": true,
		"record_path": "models/items/crate.toml"})
	_expect(form._last_write.text.contains("models/items/crate.toml"), "a write names its record")
	_expect(form._asset_key.text.is_empty(), "a good write clears the key")
	_expect(_options_asked == asked + 1, "a good write asks for the lists again")
	form.free()


func _the_export_plan_and_the_problem_text() -> void:
	var plan := ModelPipeline.export_plan("items", "iron_helm", "C:/art/helm.glb", "Nick")

	_expect(plan[ModelPipeline.FIELD_ORIGIN] == ModelPipeline.ORIGIN_EXPORT, "an export plan")
	_expect(plan[ModelPipeline.FIELD_BUILD] == true, "the gear import always builds")
	_expect(plan[ModelPipeline.FIELD_KEEP_UNNAMED] == true, "a figure part needs no key list row")

	var text := ModelPipeline.problem_text({"problem": "Not ready.",
		"problems": {"asset_key": "taken"}})

	_expect(text.contains("Not ready.") and text.contains("asset_key: taken"),
		"the problem text names each problem")
	_expect(ModelPipeline.problem_text({}).is_empty(), "no problem gives no text")


func _the_bridge_runs_the_real_pipeline() -> void:
	if not FigurePipeline.is_there():
		_expect(false, "the repository has the model pipeline")
		return

	var options := ModelPipeline.options()
	var keys := []

	for row: Dictionary in options["answer"].get("origins", []):
		keys.append(row["key"])

	_expect(options["ok"], "add-options ends well: %s" % options["output"])
	_expect(ModelPipeline.ORIGIN_EXPORT in keys, "the origins come from the pipeline")

	var checked := ModelPipeline.check({ModelPipeline.FIELD_FORMAT: ModelPipeline.FORM_FORMAT})
	var problems: Dictionary = checked["answer"].get("problems", {})

	_expect(problems.has(ModelPipeline.FIELD_ORIGIN), "a plan with no origin has its problem")
	_expect(not checked["answer"].get("ready", true), "and it is not ready")


func _expect(condition: bool, what: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("  case failed: %s" % what)
