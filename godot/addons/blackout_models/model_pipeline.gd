@tool
class_name ModelPipeline
extends RefCounted
## Runs the commands of the model form of the model pipeline
## (`blackout/assets/pipeline/form.py`) through [FigurePipeline]. The
## Models dock ([ModelForm]) and the import buttons of the gear editor use
## it. Nick chose this shape on 11/02/2026: a form and JSON commands, not
## the terminal wizard over a pipe.
##
## ## A plan file and an answer file
##
## Each command reads its input from a file and writes its answer to a
## file: `add-check <plan> <answer>`. [method OS.execute] gives the output
## of stdout and stderr as one text, and a build prints lines. Thus, a JSON
## answer in a file stays whole. The files go in [constant WORK_DIRECTORY]
## and go away after the read. Each run has its own file names, so the
## dock and the gear editor can run at the same time.
##
## ## One owner of each rule
##
## The pipeline checks each field: the license gate, the key pattern, a
## taken key, a base that is an alias. This class decides nothing. The
## keys of a plan are the FIELD_* constants, and the origins are the
## ORIGIN_* constants. `form.py` and `plans.py` name the same keys, and
## `test_model_form.py` fails when the two languages differ.
##
## A command blocks until it ends. Thus, the callers run it on a thread
## ([FigureJob]). A test calls the routines as they are.

const COMMAND_OPTIONS := "add-options"
const COMMAND_POLYHAVEN := "add-polyhaven"
const COMMAND_CHECK := "add-check"
const COMMAND_WRITE := "add-write"

## The format of a plan file and of an answer file: `FORM_FORMAT`.
const FORM_FORMAT := 1

const FIELD_FORMAT := "format"
const FIELD_ORIGIN := "origin"
const FIELD_UPLOAD := "upload"
const FIELD_POLYHAVEN := "polyhaven"
const FIELD_SOURCE_ID := "source_id"
const FIELD_LICENSE := "license"
const FIELD_EXCEPTION := "exception"
const FIELD_TITLE := "title"
const FIELD_AUTHOR := "author"
const FIELD_URL := "url"
const FIELD_SITE := "site"
const FIELD_NOTES := "notes"
const FIELD_MODEL_FILE := "model_file"
const FIELD_FAMILY := "family"
const FIELD_ASSET_KEY := "asset_key"
const FIELD_ALIASES := "aliases"
const FIELD_VARIANT := "variant_of"
const FIELD_KEEP_UNNAMED := "keep_unnamed"
const FIELD_USE_REFUSED := "use_refused_source"
const FIELD_BUILD := "build"

const ORIGIN_FILE := "file"
const ORIGIN_POLYHAVEN := "polyhaven"
const ORIGIN_SOURCE := "source"
const ORIGIN_EXPORT := "export"

## Where the plan files and the answer files go while a command runs.
const WORK_DIRECTORY := "user://blackout_model_form"

## A model build in this editor moves this mark. An editor that keeps the
## served models (the terrain editor) compares it before a draw, and reads
## the served tree again when it moved.
static var served_mark := 0


## The lists of the form: the origins, the licenses, the families, and the
## sources. Returns `{ok, answer, output}`.
static func options(game := "") -> Dictionary:
	return _run(COMMAND_OPTIONS, PackedStringArray(), game)


## What Poly Haven says of one model: its title, its author, and its model
## file. `typed` is the id or the URL of its page. See [method options].
static func look_up(typed: String, game := "") -> Dictionary:
	return _run(COMMAND_POLYHAVEN, PackedStringArray([typed]), game)


## The problem of each field of `plan`, the defaults, and each file that a
## write makes. Writes nothing. See [method options].
static func check(plan: Dictionary, game := "") -> Dictionary:
	return _run_plan(COMMAND_CHECK, plan, game)


## Check `plan` again, write it, and build it when the plan asks. A build
## moves [member served_mark]. See [method options].
static func write(plan: Dictionary, game := "") -> Dictionary:
	var result := _run_plan(COMMAND_WRITE, plan, game)

	if result["answer"].get("built", false):
		served_mark += 1

	return result


## The plan of an export of art made here: one model file, brought in as
## `blackout_<key>`, and built. An import of the same key again replaces
## the file of the source.
static func export_plan(family: String, model_key: String, path: String,
		author := "") -> Dictionary:
	return {FIELD_FORMAT: FORM_FORMAT, FIELD_ORIGIN: ORIGIN_EXPORT, FIELD_UPLOAD: path,
		FIELD_AUTHOR: author, FIELD_FAMILY: family, FIELD_ASSET_KEY: model_key,
		FIELD_KEEP_UNNAMED: true, FIELD_BUILD: true}


## The import of the gear editor: write and build an export. Returns
## `{ok, output}`, as [method FigurePipeline.run] does: true when the
## model is built, and the text of each problem or of the build.
##
## A figure part is no key that the server names, so the plan says yes to
## that warning. Each other problem stops the write.
static func import_export(family: String, model_key: String, path: String,
		author := "", game := "") -> Dictionary:
	var result := write(export_plan(family, model_key, path, author), game)
	var answer: Dictionary = result["answer"]
	var problem := problem_text(answer)
	var lines := PackedStringArray([problem, result["output"]])

	return {"ok": answer.get("built", false),
		"output": "\n".join(lines).strip_edges()}


## Each problem of an answer as lines of text: the problem of the whole
## plan, then the problem of each field, then why the machine cannot
## build. "" for an answer with no problem.
static func problem_text(answer: Dictionary) -> String:
	var lines := PackedStringArray()
	var problems: Dictionary = answer.get("problems", {})

	if not str(answer.get("problem", "")).is_empty():
		lines.append(answer["problem"])

	for field: String in problems:
		lines.append("%s: %s" % [field, problems[field]])

	if answer.get("ok", false) and not str(answer.get("build_problem", "")).is_empty():
		lines.append("No build: %s" % answer["build_problem"])

	return "\n".join(lines)


## Run one command with a plan file first.
static func _run_plan(command: String, plan: Dictionary, game: String) -> Dictionary:
	var plan_path := _work_path(command, "plan")
	var file := FileAccess.open(plan_path, FileAccess.WRITE)

	if file == null:
		return {"ok": false, "answer": {}, "output": "%s does not open." % plan_path}

	file.store_string(JSON.stringify(plan, "\t"))
	file.close()

	var result := _run(command, PackedStringArray([plan_path]), game)

	DirAccess.remove_absolute(plan_path)

	return result


## Run one command, with the answer file last, and read the answer. An
## answer that is not there or is no JSON object gives `{}`.
static func _run(command: String, leading: PackedStringArray, game: String) -> Dictionary:
	var answer_path := _work_path(command, "answer")
	var arguments := PackedStringArray([command])

	arguments.append_array(leading)
	arguments.append(answer_path)

	var result := FigurePipeline.run(arguments, game)
	var text := FileAccess.get_file_as_string(answer_path)
	var parsed: Variant = JSON.parse_string(text) if not text.is_empty() else null

	DirAccess.remove_absolute(answer_path)

	return {"ok": result["ok"], "answer": parsed if parsed is Dictionary else {},
		"output": result["output"]}


## A path in the work directory, new for each run: the command, the role,
## the clock, and a random number.
static func _work_path(command: String, role: String) -> String:
	var directory := ProjectSettings.globalize_path(WORK_DIRECTORY)

	DirAccess.make_dir_recursive_absolute(directory)

	return directory.path_join("%s_%s_%d_%d.json" % [command, role, Time.get_ticks_usec(),
		randi()])
