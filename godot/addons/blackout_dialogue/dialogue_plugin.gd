@tool
extends EditorPlugin
## The Blackout dialogue plugin (DESIGN-0017). It keeps each compiled script
## equal to its dialogue script, so the author only saves:
##
## 1. The author saves a dialogue script in the Dialogue tab (Dialogue
##    Manager). The editor imports the file again.
## 2. This plugin runs the script export ([DialogueScriptExport]). It writes
##    the compiled script that the server reads.
## 3. This plugin runs the server check ([DialogueServerCheck]) on a thread.
##    The Output panel shows each fault: a name that is not in the dialogue
##    vocabulary, a quest key that names no quest, or a feature that the
##    dialogue runner does not read.
##
## The server reads a compiled script again when its file changes. Thus, the
## next `talk` in a running game uses the saved script, with no reload.
##
## "Project > Tools > Export the dialogue scripts" runs the same steps by
## hand.

const MENU_ITEM := "Export the dialogue scripts"

const PREFIX := "[dialogue] "

var _check := FigureJob.new()

## True when a save came while the server check ran. The check runs again.
var _check_again := false


func _enter_tree() -> void:
	var filesystem := EditorInterface.get_resource_filesystem()

	filesystem.resources_reimported.connect(_on_resources_reimported)
	filesystem.filesystem_changed.connect(_on_filesystem_changed)
	add_tool_menu_item(MENU_ITEM, export_all)
	set_process(false)


func _exit_tree() -> void:
	var filesystem := EditorInterface.get_resource_filesystem()

	filesystem.resources_reimported.disconnect(_on_resources_reimported)
	filesystem.filesystem_changed.disconnect(_on_filesystem_changed)
	remove_tool_menu_item(MENU_ITEM)
	_check.wait()


func _process(_delta: float) -> void:
	if not _check.finish():
		return

	if _check_again:
		_check_again = false
		_start_check()
	else:
		set_process(false)


## Run the script export for each pair of directories, then the server check.
func export_all() -> void:
	for target: Dictionary in DialogueScriptExport.targets():
		var report := DialogueScriptExport.sync(target["source"], target["compiled"])

		for file_name: String in report["written"]:
			print(PREFIX + "written  " + file_name)

		for file_name: String in report["removed"]:
			print(PREFIX + "removed  " + file_name)

		for error: String in report["errors"]:
			push_error(PREFIX + error)

	_start_check()


func _start_check() -> void:
	if _check.is_running():
		_check_again = true
		return

	_check.start(DialogueServerCheck.LABEL, DialogueServerCheck.run, _on_checked)
	set_process(true)


func _on_checked(result: Dictionary) -> void:
	if result["ok"]:
		print(PREFIX + result["output"])
		return

	for line: String in result["output"].split("\n"):
		push_error(PREFIX + line)


func _on_resources_reimported(paths: PackedStringArray) -> void:
	for path: String in paths:
		if path.get_extension() == DialogueScriptExport.SOURCE_SUFFIX:
			export_all()
			return


## A removed or renamed dialogue script leaves a compiled script with no
## source. The editor imports nothing for it, so this signal finds it.
func _on_filesystem_changed() -> void:
	var game: Dictionary = DialogueScriptExport.targets()[0]
	var orphans := DialogueScriptExport.orphans(game["source"], game["compiled"])

	if not orphans.is_empty():
		export_all()
