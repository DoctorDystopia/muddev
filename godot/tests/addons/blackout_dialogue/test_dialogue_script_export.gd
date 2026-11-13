extends Node
## Unit tests for DialogueScriptExport, the script export of the dialogue
## plugin (DESIGN-0017). Each case writes to a disposable user:// directory,
## never to the game.
##
##     godot --headless --path godot res://tests/addons/blackout_dialogue/test_dialogue_script_export.tscn

const TEST_DIRECTORY := "user://test_dialogue_script_export"

## One dialogue script that the compiler accepts.
const GOOD_SCRIPT := "~ start\nGuard: Hello.\n"

## The digest of GOOD_SCRIPT. `test_script_files.py` in the game holds the
## same text and the same digest, so the two languages cannot give
## different digests.
const GOOD_DIGEST := "b8a8071d9127c2049efa30e76bfb0f8f0220b57034eb29840e4b15aa2dc82f1e"

## A jump to a cue that the script does not have. The compiler refuses it.
const BAD_SCRIPT := "~ start\nGuard: Hello.\n=> nowhere\n"

var _failures := 0


func _ready() -> void:
	_clean()

	_the_digest_is_the_one_that_python_gives()
	_the_line_ends_do_not_change_the_digest()
	_a_compiled_script_carries_its_three_stamps()
	_a_compiler_fault_gives_an_error_and_no_text()
	_a_sync_writes_a_missing_compiled_script()
	_a_second_sync_writes_nothing()
	_a_changed_script_is_written_again()
	_a_check_reports_and_changes_nothing()
	_a_compiled_script_with_no_source_is_removed()
	_a_json_file_that_is_no_compiled_script_stays()
	_a_script_with_a_fault_keeps_its_old_compiled_script()

	_clean()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: dialogue_script_export")
	get_tree().quit(0)


func _the_digest_is_the_one_that_python_gives() -> void:
	_expect(DialogueScriptExport.digest_of(GOOD_SCRIPT) == GOOD_DIGEST,
		"the digest of the shared text is the shared digest")


func _the_line_ends_do_not_change_the_digest() -> void:
	var with_crlf := GOOD_SCRIPT.replace("\n", "\r\n")

	_expect(DialogueScriptExport.digest_of(with_crlf) == GOOD_DIGEST,
		"a CRLF file has the digest of its LF form")


func _a_compiled_script_carries_its_three_stamps() -> void:
	var made := DialogueScriptExport.compile(GOOD_SCRIPT, "good.dialogue")
	var payload: Dictionary = JSON.parse_string(made["text"])

	_expect(made["errors"].is_empty(), "a good script gives no error")
	_expect(int(payload[DialogueScriptExport.KEY_FORMAT]) == DialogueScriptExport.FORMAT,
		"the format stamp")
	_expect(int(payload[DialogueScriptExport.KEY_COMPILER_VERSION])
		== DMImportPlugin.COMPILER_VERSION, "the compiler version stamp")
	_expect(payload[DialogueScriptExport.KEY_SOURCE_SHA256] == GOOD_DIGEST,
		"the digest stamp")
	_expect(payload[DialogueScriptExport.KEY_CUES].has("start"), "the cues")
	_expect(not payload[DialogueScriptExport.KEY_LINES].is_empty(), "the lines")


func _a_compiler_fault_gives_an_error_and_no_text() -> void:
	var made := DialogueScriptExport.compile(BAD_SCRIPT, "bad.dialogue")

	_expect(made["text"].is_empty(), "a script with a fault gives no text")
	_expect(made["errors"].size() == 1, "one error for one fault")
	_expect(made["errors"][0].contains("bad.dialogue, line 3"),
		"the error names the file and the line: %s" % [made["errors"]])


func _a_sync_writes_a_missing_compiled_script() -> void:
	_clean()
	_write("guard.dialogue", GOOD_SCRIPT)

	var report := _sync()

	_expect(report["written"] == ["guard.json"], "the sync reports the file")
	_expect(_exists("guard.json"), "the sync writes the file")


func _a_second_sync_writes_nothing() -> void:
	var report := _sync()

	_expect(report["written"].is_empty(), "a current file is not written again")


func _a_changed_script_is_written_again() -> void:
	_write("guard.dialogue", GOOD_SCRIPT + "Guard: Go.\n")

	var report := _sync()

	_expect(report["written"] == ["guard.json"], "a changed script is written")


func _a_check_reports_and_changes_nothing() -> void:
	_write("guard.dialogue", GOOD_SCRIPT)

	var before := _read("guard.json")
	var report := _sync(false)

	_expect(report["written"] == ["guard.json"], "the check names the stale file")
	_expect(_read("guard.json") == before, "the check writes nothing")

	_sync()


func _a_compiled_script_with_no_source_is_removed() -> void:
	DirAccess.remove_absolute(_path("guard.dialogue"))

	var checked := _sync(false)

	_expect(checked["removed"] == ["guard.json"], "the check names the orphan")
	_expect(_exists("guard.json"), "the check removes nothing")

	var report := _sync()

	_expect(report["removed"] == ["guard.json"], "the sync reports the orphan")
	_expect(not _exists("guard.json"), "the sync removes the orphan")


func _a_json_file_that_is_no_compiled_script_stays() -> void:
	_write("notes.json", "{\"hello\": 1}\n")

	var report := _sync()

	_expect(report["removed"].is_empty(), "a foreign JSON file is no orphan")
	_expect(_exists("notes.json"), "a foreign JSON file stays")


func _a_script_with_a_fault_keeps_its_old_compiled_script() -> void:
	_clean()
	_write("guard.dialogue", GOOD_SCRIPT)
	_sync()

	var before := _read("guard.json")

	_write("guard.dialogue", BAD_SCRIPT)

	var report := _sync()

	_expect(report["errors"].size() == 1, "the sync reports the fault")
	_expect(report["written"].is_empty(), "the sync writes nothing for it")
	_expect(_read("guard.json") == before, "the old compiled script stays")


func _sync(write := true) -> Dictionary:
	var directory := ProjectSettings.globalize_path(TEST_DIRECTORY)

	return DialogueScriptExport.sync(directory, directory, write)


func _path(file_name: String) -> String:
	return ProjectSettings.globalize_path(TEST_DIRECTORY).path_join(file_name)


func _write(file_name: String, text: String) -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(TEST_DIRECTORY))

	var file := FileAccess.open(_path(file_name), FileAccess.WRITE)

	file.store_string(text)
	file.close()


func _read(file_name: String) -> String:
	return FileAccess.get_file_as_string(_path(file_name))


func _exists(file_name: String) -> bool:
	return FileAccess.file_exists(_path(file_name))


func _clean() -> void:
	var directory := ProjectSettings.globalize_path(TEST_DIRECTORY)

	if not DirAccess.dir_exists_absolute(directory):
		return

	for file_name: String in DirAccess.get_files_at(directory):
		DirAccess.remove_absolute(directory.path_join(file_name))

	DirAccess.remove_absolute(directory)


func _expect(condition: bool, what: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("  FAIL: %s" % what)
