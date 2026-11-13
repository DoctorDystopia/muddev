@tool
class_name DialogueScriptExport
extends RefCounted
## The script export (DESIGN-0017). It compiles each dialogue script with the
## compiler of Dialogue Manager, and it writes the compiled script that the
## server reads.
##
## The server runs each dialogue. The client gets only text and responses.
## Thus, the runtime of the addon never runs a dialogue of the game, and no
## dialogue script goes into the client export.
##
## A compiled script is JSON: the cues and the lines as the addon compiler
## made them, with three stamps. `compiler_version` is the version of that
## compiler. `source_sha256` is the digest of the dialogue script, so a
## Python test finds a compiled script that is out of date. `format` is the
## version of this file shape.
##
## Three callers: the editor plugin after each save, the headless command
## (`export_cli.gd`), and the test.
##
## The Python reader is `blackout/systems/gameplay/dialogue/script.py`.
## [method digest_of] and `source_digest` there must give the same digest.

## The version of the file shape. `COMPILED_FORMAT` in the Python constants
## is the same number.
const FORMAT := 1

const SOURCE_SUFFIX := "dialogue"
const COMPILED_SUFFIX := "json"

## The dialogue scripts of the game, in this project.
const SOURCE_DIRECTORY := "res://dialogue"

## The compiled scripts of the game, from the game directory.
const COMPILED_FROM_GAME := "world/npc_dialogues/compiled"

## The script pairs of the Python tests, from the game directory. The source
## and the compiled script are in the same directory.
const FIXTURES_FROM_GAME := "systems/gameplay/dialogue/tests/fixtures"

## The game directory, from this project.
const GAME_FROM_PROJECT := "../blackout"

const KEY_FORMAT := "format"
const KEY_COMPILER_VERSION := "compiler_version"
const KEY_SOURCE := "source"
const KEY_SOURCE_SHA256 := "source_sha256"
const KEY_CUES := "cues"
const KEY_LINES := "lines"


## The game directory of this repository: `blackout/`.
static func game_directory() -> String:
	var project := ProjectSettings.globalize_path("res://")

	return project.path_join(GAME_FROM_PROJECT).simplify_path()


## Each pair of directories that the export keeps: `{source, compiled}`.
## The first pair is the game. The second pair is the Python test fixtures.
static func targets(game := "") -> Array[Dictionary]:
	var directory := game_directory() if game.is_empty() else game
	var fixtures := directory.path_join(FIXTURES_FROM_GAME)

	return [
		{"source": ProjectSettings.globalize_path(SOURCE_DIRECTORY),
			"compiled": directory.path_join(COMPILED_FROM_GAME)},
		{"source": fixtures, "compiled": fixtures},
	]


## The text with LF line ends. git stores LF, and a tool can write CRLF.
static func normalized(text: String) -> String:
	return text.replace("\r\n", "\n")


## The digest of the text of one dialogue script: SHA-256 of the UTF-8 text
## with LF line ends, as lowercase hex.
static func digest_of(text: String) -> String:
	return normalized(text).sha256_text()


## Compile the text of one dialogue script. Returns `{errors, text}`:
## `errors` holds one line for each fault of the compiler, and `text` is the
## compiled script as JSON. `text` is empty when the compiler found a fault.
static func compile(source_text: String, file_name: String) -> Dictionary:
	var clean := normalized(source_text)
	var result: DMCompilerResult = DMCompiler.compile_string(clean, file_name)
	var errors: Array[String] = []

	# The compiler counts the lines of an error from 1.
	for error: DMError in result.errors:
		errors.append("%s, line %d: %s" % [file_name, error.line_number,
			DMConstants.get_error_message(error.error)])

	if not errors.is_empty():
		return {"errors": errors, "text": ""}

	var payload := {
		KEY_FORMAT: FORMAT,
		KEY_COMPILER_VERSION: DMImportPlugin.COMPILER_VERSION,
		KEY_SOURCE: file_name,
		KEY_SOURCE_SHA256: digest_of(clean),
		KEY_CUES: result.cues,
		KEY_LINES: result.lines,
	}

	return {"errors": errors, "text": JSON.stringify(payload, "\t", true) + "\n"}


## The file names in one directory that have one suffix, in name order.
static func files_of(directory: String, suffix: String) -> Array[String]:
	var found: Array[String] = []

	if not DirAccess.dir_exists_absolute(directory):
		return found

	for file_name: String in DirAccess.get_files_at(directory):
		if file_name.get_extension() == suffix:
			found.append(file_name)

	found.sort()

	return found


## The name of the compiled script of one dialogue script file.
static func compiled_name(source_name: String) -> String:
	return "%s.%s" % [source_name.get_basename(), COMPILED_SUFFIX]


## Make one pair of directories equal: compile each dialogue script of
## `source` into `compiled`, and remove each compiled script with no source.
## With `write` false, change nothing and only report.
##
## Returns `{written, removed, errors}`. `written` and `removed` hold file
## names. With `write` false, they hold what a real run changes: a compiled
## script that is missing or out of date, and one with no source.
static func sync(source: String, compiled: String, write := true) -> Dictionary:
	var report := {"written": [], "removed": [], "errors": []}

	for source_name: String in files_of(source, SOURCE_SUFFIX):
		var source_text := FileAccess.get_file_as_string(source.path_join(source_name))
		var made := compile(source_text, source_name)
		var target := compiled.path_join(compiled_name(source_name))

		report["errors"].append_array(made["errors"])

		if made["text"].is_empty() or _holds(target, made["text"]):
			continue

		report["written"].append(compiled_name(source_name))

		if write:
			_write(target, made["text"])

	for orphan: String in orphans(source, compiled):
		report["removed"].append(orphan)

		if write:
			DirAccess.remove_absolute(compiled.path_join(orphan))

	return report


## Each compiled script in `compiled` that has no dialogue script in
## `source`. A JSON file that is not a compiled script is never in the list.
static func orphans(source: String, compiled: String) -> Array[String]:
	var found: Array[String] = []

	for compiled_file: String in files_of(compiled, COMPILED_SUFFIX):
		var source_name := "%s.%s" % [compiled_file.get_basename(), SOURCE_SUFFIX]

		if FileAccess.file_exists(source.path_join(source_name)):
			continue

		if _is_compiled_script(compiled.path_join(compiled_file)):
			found.append(compiled_file)

	return found


## True when the file at `path` holds exactly `text`, with any line ends.
static func _holds(path: String, text: String) -> bool:
	if not FileAccess.file_exists(path):
		return false

	return normalized(FileAccess.get_file_as_string(path)) == text


static func _write(path: String, text: String) -> void:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())

	var file := FileAccess.open(path, FileAccess.WRITE)

	file.store_string(text)
	file.close()


## True when a JSON file has the stamps of a compiled script. The export
## removes only such a file.
static func _is_compiled_script(path: String) -> bool:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))

	if not parsed is Dictionary:
		return false

	return parsed.has(KEY_FORMAT) and parsed.has(KEY_SOURCE_SHA256)
