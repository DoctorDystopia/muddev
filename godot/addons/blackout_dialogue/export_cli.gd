extends SceneTree
## The script export as a headless command (DESIGN-0017). It makes each
## compiled script equal to its dialogue script: the scripts of the game, and
## the script pairs of the Python tests.
##
##     godot --headless --path godot -s res://addons/blackout_dialogue/export_cli.gd
##     godot --headless --path godot -s res://addons/blackout_dialogue/export_cli.gd -- --check
##
## With `--check` it writes nothing. It exits with 1 when a compiled script
## is out of date, and when the compiler finds a fault. Without `--check` it
## exits with 1 only for a compiler fault.

const CHECK_FLAG := "--check"


func _init() -> void:
	var check := CHECK_FLAG in OS.get_cmdline_user_args()
	var failed := false

	for target: Dictionary in DialogueScriptExport.targets():
		var report := DialogueScriptExport.sync(
			target["source"], target["compiled"], not check)
		var changed: int = report["written"].size() + report["removed"].size()

		_print_report(target["compiled"], report, check)

		if not report["errors"].is_empty() or (check and changed > 0):
			failed = true

	quit(1 if failed else 0)


func _print_report(directory: String, report: Dictionary, check: bool) -> void:
	var written_word := "out of date" if check else "written"
	var removed_word := "has no source" if check else "removed"

	print(directory)

	for file_name: String in report["written"]:
		print("  %s  %s" % [written_word, file_name])

	for file_name: String in report["removed"]:
		print("  %s  %s" % [removed_word, file_name])

	for error: String in report["errors"]:
		printerr("  error  %s" % error)

	if report["written"].is_empty() and report["removed"].is_empty() \
			and report["errors"].is_empty():
		print("  current")
