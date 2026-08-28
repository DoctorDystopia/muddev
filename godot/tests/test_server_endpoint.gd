extends Node
## Unit tests for ServerEndpoint.
##
##     godot --headless --path godot res://tests/test_server_endpoint.tscn

var _failures := 0


func _ready() -> void:
	_a_debug_build_talks_to_localhost()
	_a_release_build_talks_to_production()
	_an_override_wins_everywhere()
	_a_nonsense_override_is_refused_rather_than_dialled()
	_command_line_overrides_are_read_both_ways()
	_query_overrides_are_read_and_decoded()
	_production_is_wss_not_ws()
	_art_is_fetched_from_an_absolute_origin()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: server_endpoint")
	get_tree().quit(0)


func _a_debug_build_talks_to_localhost() -> void:
	# Editor and debug export both mean somebody is developing.
	_expect(ServerEndpoint.resolve("", true) == ServerEndpoint.DEV_URL,
		"a debug build reaches the dev server")


func _a_release_build_talks_to_production() -> void:
	# The line is debug-vs-release rather than a constant somebody has to
	# remember to flip before shipping -- that step gets forgotten once.
	_expect(ServerEndpoint.resolve("", false) == ServerEndpoint.PRODUCTION_URL,
		"a release build reaches production")


func _an_override_wins_everywhere() -> void:
	_expect(ServerEndpoint.resolve("ws://10.0.0.5:4008", true) == "ws://10.0.0.5:4008",
		"an override beats the debug default")
	_expect(ServerEndpoint.resolve("ws://10.0.0.5:4008", false) == "ws://10.0.0.5:4008",
		"and the release default")
	_expect(ServerEndpoint.resolve("  ws://x:1  ", false) == "ws://x:1",
		"surrounding whitespace is trimmed")


func _a_nonsense_override_is_refused_rather_than_dialled() -> void:
	# An override that pointed at http:// or a file would fail in a way that
	# looks exactly like the server being down.
	for bad: String in ["http://x", "file:///etc/passwd", "x", "ws://", ""]:
		_expect(ServerEndpoint.resolve(bad, false) == ServerEndpoint.PRODUCTION_URL,
			"a %s override falls back to the default" % (bad if bad else "(empty)"))

	_expect(not ServerEndpoint.is_valid("ws://"), "a bare scheme is not a URL")
	_expect(ServerEndpoint.is_valid("wss://a"), "wss is accepted")


func _command_line_overrides_are_read_both_ways() -> void:
	# Both spellings, because both are what people type.
	_expect(
		ServerEndpoint.override_from_args(
			PackedStringArray(["--server=ws://a:1"])) == "ws://a:1",
		"--server=<url>")
	_expect(
		ServerEndpoint.override_from_args(
			PackedStringArray(["--server", "ws://b:2"])) == "ws://b:2",
		"--server <url>")
	_expect(
		ServerEndpoint.override_from_args(PackedStringArray(["--other"])).is_empty(),
		"no flag means no override")
	_expect(
		ServerEndpoint.override_from_args(PackedStringArray(["--server"])).is_empty(),
		"a trailing flag with no value is not an override")


func _query_overrides_are_read_and_decoded() -> void:
	_expect(
		ServerEndpoint.override_from_query("?server=ws%3A%2F%2Fx%3A1") == "ws://x:1",
		"a percent-encoded query value is decoded")
	_expect(
		ServerEndpoint.override_from_query("a=1&server=ws://y:2&b=3") == "ws://y:2",
		"it is found among other parameters")
	_expect(ServerEndpoint.override_from_query("").is_empty(), "an empty query")
	_expect(ServerEndpoint.override_from_query("?a=1").is_empty(), "an unrelated query")


func _production_is_wss_not_ws() -> void:
	# A plain ws:// from an HTTPS page is blocked as mixed content and the
	# client silently never connects -- INFRA-0001 §5.1, which cost the
	# webclient exactly this.
	_expect(ServerEndpoint.PRODUCTION_URL.begins_with("wss://"),
		"production is wss, or the browser blocks it as mixed content")


## THE BUG THIS WOULD HAVE CAUGHT, and it went to production because nothing
## here exercised asset_origin at all.
##
## The web branch used to return "", on the reasoning that an empty origin makes
## `url_for` produce a root-relative path the browser resolves against the page.
## The reasoning is right about CORS and wrong about HTTPRequest, which parses
## the URL itself and refuses one with no scheme:
##
##     ERROR: Error parsing URL: '/static/webclient/models/manifest.json'
##     WARNING: ModelLoader: manifest request refused: error 31
##
## The manifest never arrived, so `has_model` answered false for everything and
## every entity in the game drew its family shape -- which looks exactly like
## art that was never packed.
##
## So what is asserted is the property the whole path depends on: whatever
## origin is chosen, the URL built from it can actually be dialled.
func _art_is_fetched_from_an_absolute_origin() -> void:
	var registry := ModelRegistry.new()
	registry.ingest_manifest({"player_character": "characters/x.glb"})

	var cases := {
		"debug": ServerEndpoint.asset_origin(true, true, "https://page.example"),
		"release web": ServerEndpoint.asset_origin(false, true,
			"https://page.example"),
		"release desktop": ServerEndpoint.asset_origin(false, false, ""),
	}

	for label: String in cases:
		var url := registry.url_for(cases[label], "player_character")

		_expect(url.begins_with("http://") or url.begins_with("https://"),
			"%s builds a dialable url (%s)" % [label, url])

	_expect(ServerEndpoint.asset_origin(true, true, "") ==
		ServerEndpoint.ASSET_DEV_ORIGIN,
		"a debug build ignores the page and uses the dev webserver")
	_expect(ServerEndpoint.asset_origin(false, false, "https://page.example") ==
		ServerEndpoint.ASSET_DESKTOP_ORIGIN,
		"a desktop build ignores the page, having none")

	# A trailing slash on the origin and a leading one on MODEL_ROOT would make
	# `//static/...`, which is a protocol-relative URL and not the path meant.
	_expect(ServerEndpoint.asset_origin(false, true, "https://page.example/") ==
		"https://page.example",
		"a trailing slash on the page origin is trimmed")

	# Off the web there is no page to ask, and the answer must be the empty
	# string rather than an error -- every non-web caller passes it straight in.
	_expect(ServerEndpoint.page_origin().is_empty(),
		"page_origin answers empty off the web")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
