extends Node
## Unit tests for CreditsState.
##
##     godot --headless --path godot res://tests/test_credits_state.tscn
##
## Needs nothing running. The documents are hand-built in the shape that
## `assets/pipeline/outputs.py` writes to `credits.json`.

var _failures := 0


func _ready() -> void:
	_a_document_is_read_entry_by_entry()
	_a_license_is_confirmed_only_when_the_file_says_so()
	_junk_gives_an_empty_list_and_still_counts_as_loaded()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: credits_state")
	get_tree().quit(0)


func _a_document_is_read_entry_by_entry() -> void:
	var state := CreditsState.new()
	var count := state.ingest([
		{"title": "Rusty sword", "author": "Leoskateman", "url": "https://a",
			"license": "CC BY 4.0", "license_url": "https://b",
			"confirmed": true, "models": ["rusty_scrap_shortsword"]},
		{"title": "", "author": "nobody"},
	])

	_expect(count == 1, "an entry with no title is dropped")
	_expect(state.entries()[0]["author"] == "Leoskateman", "fields survive")
	_expect(state.loaded(), "an ingested document counts as loaded")


func _a_license_is_confirmed_only_when_the_file_says_so() -> void:
	var state := CreditsState.new()
	state.ingest([
		{"title": "A", "confirmed": false},
		{"title": "B"},
		{"title": "C", "confirmed": "yes"},
	])

	_expect(state.entries().size() == 3, "every entry with a title is kept")

	for entry: Dictionary in state.entries():
		_expect(not entry["confirmed"],
			"%s is not shown as confirmed" % entry["title"])


func _junk_gives_an_empty_list_and_still_counts_as_loaded() -> void:
	var state := CreditsState.new()

	_expect(not state.loaded(), "nothing is loaded before a document")
	_expect(state.ingest("not a list") == 0, "junk gives no entries")
	_expect(state.loaded(), "but it counts as loaded, so the box stops waiting")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
