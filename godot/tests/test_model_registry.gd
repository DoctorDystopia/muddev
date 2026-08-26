extends Node
## Unit tests for ModelRegistry. Needs no server and no files -- the manifest is
## hand-built in the shape Godot's JSON parser produces.
##
##     godot --headless --path godot res://tests/test_model_registry.tscn

var _failures := 0


func _ready() -> void:
	_nothing_is_known_before_the_manifest_arrives()
	_a_manifest_names_what_has_art()
	_a_key_with_no_art_is_not_an_error()
	_urls_are_built_from_the_origin()
	_a_suspicious_path_is_refused()
	_a_malformed_manifest_is_survived()
	_presentation_is_client_side_and_defaults_to_none()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: model_registry")
	get_tree().quit(0)


func _nothing_is_known_before_the_manifest_arrives() -> void:
	# The first snapshot must render generics rather than waiting. This is the
	# same degradation the browser pane guarantees.
	var reg := ModelRegistry.new()

	_expect(not reg.manifest_seen(), "no manifest has been seen yet")
	_expect(not reg.has_model("player_character"), "nothing is known yet")
	_expect(reg.url_for("https://x", "player_character").is_empty(),
		"and no URL is offered")


func _a_manifest_names_what_has_art() -> void:
	var reg := ModelRegistry.new()
	var count := reg.ingest_manifest({
		"player_character": "characters/player_character.glb",
		"rusty_scrap_shortsword": "items/rusty_scrap_shortsword.glb",
	})

	_expect(count == 2, "both entries were accepted")
	_expect(reg.manifest_seen(), "the manifest is marked as seen")
	_expect(reg.has_model("player_character"), "a listed key has art")
	_expect(reg.known_keys().size() == 2, "known_keys reports both")
	_expect(reg.known_keys()[0] == "player_character", "known_keys is sorted")


func _a_key_with_no_art_is_not_an_error() -> void:
	# Content must never wait on art: an ItemDef added today with no model
	# draws its family's procedural mesh and nothing complains.
	var reg := ModelRegistry.new()
	reg.ingest_manifest({"player_character": "characters/player_character.glb"})

	_expect(not reg.has_model("an_item_with_no_art"), "an unlisted key has no art")
	_expect(reg.url_for("https://x", "an_item_with_no_art").is_empty(),
		"and produces no URL to 404 on")


func _urls_are_built_from_the_origin() -> void:
	var reg := ModelRegistry.new()
	reg.ingest_manifest({"floating_eye": "npcs/floating_eye.glb"})

	_expect(
		reg.url_for("https://game.playblackout.io", "floating_eye")
			== "https://game.playblackout.io/static/webclient/models/npcs/floating_eye.glb",
		"a model URL is the origin plus the served path"
	)
	# A trailing slash on the origin must not double up.
	_expect(
		reg.url_for("https://game.playblackout.io/", "floating_eye")
			== "https://game.playblackout.io/static/webclient/models/npcs/floating_eye.glb",
		"a trailing slash on the origin is absorbed"
	)
	_expect(
		reg.manifest_url("http://127.0.0.1:4001")
			== "http://127.0.0.1:4001/static/webclient/models/manifest.json",
		"the manifest URL is built the same way"
	)


func _a_suspicious_path_is_refused() -> void:
	# The manifest is server-rendered and trusted today. This costs one
	# comparison and means a hand-edited one cannot aim the client elsewhere.
	var reg := ModelRegistry.new()
	var count := reg.ingest_manifest({
		"ok": "items/ok.glb",
		"escapes": "../../../etc/passwd",
		"absolute": "/etc/passwd",
		"remote": "https://evil.example/x.glb",
		"empty": "",
	})

	_expect(count == 1, "only the safe entry survived")
	_expect(reg.has_model("ok"), "the safe entry is kept")
	_expect(not reg.has_model("escapes"), "a traversal path is refused")
	_expect(not reg.has_model("absolute"), "an absolute path is refused")
	_expect(not reg.has_model("remote"), "an off-origin URL is refused")
	_expect(not reg.has_model("empty"), "an empty path is refused")


func _a_malformed_manifest_is_survived() -> void:
	# Art metadata failing to parse must not stop a client booting.
	var reg := ModelRegistry.new()

	_expect(reg.ingest_manifest("not a dictionary") == 0, "junk yields nothing")
	_expect(reg.manifest_seen(), "but it still counts as having been told")
	_expect(reg.known_keys().is_empty(), "and nothing is registered")


func _presentation_is_client_side_and_defaults_to_none() -> void:
	# The sword's quarter-turn is a judgement about how a blade reads in an
	# inventory cell. It is deliberately NOT in the served manifest.
	var reg := ModelRegistry.new()

	_expect(
		reg.rotation_for("rusty_scrap_shortsword").is_equal_approx(
			Vector3(PI / 2.0, 0.0, 0.0)),
		"the sword is stood up"
	)
	_expect(
		reg.rotation_for("player_character") == Vector3.ZERO,
		"anything with no entry is drawn as exported"
	)


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
