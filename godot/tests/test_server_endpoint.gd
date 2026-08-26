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


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
