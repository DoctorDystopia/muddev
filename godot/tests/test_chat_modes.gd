extends Node
## Unit tests for ChatModes -- where a typed line goes.
##
##     godot --headless --path godot res://tests/test_chat_modes.tscn
##
## Needs nothing running. The payloads are hand-built in the shape that
## `blackout/systems/interface/statefeed/chat.py` sends.

const Const := preload("res://autoload/blackout_constants.gd")

const SAY := {"key": "say", "label": "Say", "type": "say", "prefix": "say "}
const REPLY := {"key": "reply", "label": "Reply", "type": "page",
	"prefix": "page/reply "}
const PUBLIC := {"key": "channel:public", "label": "Public", "type": "channel",
	"prefix": "@channel Public = "}

var _failures := 0


func _ready() -> void:
	_command_mode_sends_the_line_as_it_is()
	_a_chat_mode_adds_its_prefix()
	_a_slash_is_always_a_command()
	_a_blank_chat_line_sends_nothing()
	_only_its_own_channel_is_read()
	_a_kept_mode_waits_for_the_payload()
	_a_mode_that_goes_away_falls_back_to_command()
	_an_unknown_key_is_refused()
	_the_prompt_names_the_speaker_and_the_mode()
	_modes_are_found_by_message_type()
	_a_row_with_no_prefix_is_dropped()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: chat_modes")
	get_tree().quit(0)


func _loaded() -> ChatModes:
	var modes := ChatModes.new()
	modes.ingest(Const.CH_CHAR_CHAT,
		{"speaker": "Nick", "modes": [SAY, REPLY, PUBLIC]})

	return modes


func _command_mode_sends_the_line_as_it_is() -> void:
	var modes := _loaded()

	_expect(modes.active_key() == ChatModes.COMMAND_KEY, "Command is the default")
	_expect(modes.command_for("look") == "look", "and sends the line as it is")


func _a_chat_mode_adds_its_prefix() -> void:
	var modes := _loaded()
	modes.select(PUBLIC["key"])

	_expect(modes.command_for("hello all") == "@channel Public = hello all",
		"a channel line is the channel command the server named")

	modes.select(SAY["key"])
	_expect(modes.command_for("hi") == "say hi", "and a say line is a say")


func _a_slash_is_always_a_command() -> void:
	var modes := _loaded()
	modes.select(SAY["key"])

	_expect(modes.command_for("/look") == "look",
		"in a chat mode, a leading slash sends a command")

	modes.select(ChatModes.COMMAND_KEY)
	_expect(modes.command_for("/look") == "look",
		"and in Command mode too, so the rule has no exception")


func _a_blank_chat_line_sends_nothing() -> void:
	var modes := _loaded()
	modes.select(SAY["key"])

	_expect(modes.command_for("   ").is_empty(), "a blank chat line sends nothing")


func _only_its_own_channel_is_read() -> void:
	var modes := ChatModes.new()

	_expect(not modes.ingest(Const.CH_CHAR_COMBAT, {"modes": [SAY]}),
		"another channel is not ours")
	_expect(modes.modes.is_empty(), "and changes nothing")


## The settings file loads before the server sends the modes.
func _a_kept_mode_waits_for_the_payload() -> void:
	var modes := ChatModes.new()
	modes.prefer(PUBLIC["key"])

	_expect(modes.active_key() == ChatModes.COMMAND_KEY,
		"before the payload, a kept mode gives Command")
	_expect(modes.command_for("connect a b") == "connect a b",
		"so the login line goes out as it is")

	modes.ingest(Const.CH_CHAR_CHAT, {"speaker": "Nick", "modes": [SAY, PUBLIC]})
	_expect(modes.active_key() == PUBLIC["key"],
		"and the kept mode is in use when the payload lands")


func _a_mode_that_goes_away_falls_back_to_command() -> void:
	var modes := _loaded()
	modes.select(PUBLIC["key"])

	modes.ingest(Const.CH_CHAR_CHAT, {"speaker": "Nick", "modes": [SAY]})
	_expect(modes.active_key() == ChatModes.COMMAND_KEY,
		"a left channel gives Command")
	_expect(modes.wanted_key() == PUBLIC["key"],
		"but the choice is kept for a join later")

	modes.reset()
	_expect(modes.wanted_key() == PUBLIC["key"], "and a dropped socket keeps it too")


func _an_unknown_key_is_refused() -> void:
	var modes := _loaded()

	_expect(not modes.select("channel:nowhere"), "a key that names no mode is refused")
	_expect(modes.active_key() == ChatModes.COMMAND_KEY, "and nothing moves")


func _the_prompt_names_the_speaker_and_the_mode() -> void:
	var modes := _loaded()
	modes.select(PUBLIC["key"])

	_expect(modes.prompt() == "Nick [Public]:", "the prompt reads as in OSRS")

	modes.select(ChatModes.COMMAND_KEY)
	_expect(modes.prompt().contains(ChatModes.COMMAND_LABEL),
		"and names Command in Command mode")


func _modes_are_found_by_message_type() -> void:
	var modes := _loaded()
	var found := modes.modes_for_types([Const.MSG_PAGE, Const.MSG_WHISPER])

	_expect(found.size() == 1 and found[0]["key"] == REPLY["key"],
		"the Private tab types find Reply")
	_expect(modes.modes_for_types([]).size() == 3,
		"and no types, the All tab, finds every mode")


func _a_row_with_no_prefix_is_dropped() -> void:
	var modes := ChatModes.new()
	modes.ingest(Const.CH_CHAR_CHAT, {"modes": [
		{"key": "broken", "label": "Broken", "type": "say", "prefix": ""}, SAY]})

	_expect(modes.modes.size() == 1, "a row with no prefix is dropped")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
