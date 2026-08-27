extends Node
## Tests for the login form's two jobs that can be wrong: composing the command,
## and knowing when to get out of the way.
##
##     godot --headless --path godot res://tests/test_login_view.tscn

const _Const := preload("res://autoload/blackout_constants.gd")

var _failures := 0
var _view: LoginView
var _sent: Array = []


func _ready() -> void:
	_view = load("res://scenes/login/login_view.tscn").instantiate()
	add_child(_view)
	_view.command_requested.connect(func(c: String): _sent.append(c))

	_connect_and_create_send_what_a_telnet_player_types()
	_a_name_with_spaces_is_quoted()
	_an_incomplete_form_sends_nothing()
	_the_password_is_not_kept_after_submitting()
	_it_hides_once_a_body_exists()
	_it_comes_back_when_the_session_is_lost()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: login_view")
	get_tree().quit(0)


func _fill(account: String, secret: String) -> void:
	_view._name.text = account
	_view._password.text = secret


func _connect_and_create_send_what_a_telnet_player_types() -> void:
	# The form is not a privileged path. These are the same two lines the
	# connection screen tells a telnet player to type.
	_sent.clear()
	_fill("Rook", "hunter2")
	_view._on_connect()

	_expect(_sent.size() == 1 and _sent[0] == "connect Rook hunter2",
		"connect sends `connect <name> <password>`")

	_sent.clear()
	_fill("Rook", "hunter2")
	_view._on_create()

	_expect(_sent.size() == 1 and _sent[0] == "create Rook hunter2",
		"create sends `create <name> <password>`")


func _a_name_with_spaces_is_quoted() -> void:
	# Evennia splits its login commands on whitespace and its own connection
	# screen says to quote such a name. Unquoted, the failure is an unhelpful
	# "unknown command" that says nothing about names.
	_sent.clear()
	_fill("Two Words", "pw")
	_view._on_connect()

	_expect(_sent[0] == 'connect "Two Words" pw', "a spaced name is quoted")

	_sent.clear()
	_fill("  Rook  ", "pw")
	_view._on_connect()

	_expect(_sent[0] == "connect Rook pw", "surrounding whitespace is trimmed")


func _an_incomplete_form_sends_nothing() -> void:
	_sent.clear()
	_fill("", "pw")
	_view._on_connect()
	_fill("Rook", "")
	_view._on_connect()

	_expect(_sent.is_empty(), "a half-filled form sends no command")
	_expect(not _view._message.text.is_empty(), "and says why")


func _the_password_is_not_kept_after_submitting() -> void:
	# No reason for a credential to sit in a widget where a screenshot, a crash
	# handler or an idle screen could surface it.
	_fill("Rook", "hunter2")
	_view._on_connect()

	_expect(_view._password.text.is_empty(), "the password field is cleared")
	_expect(_view._name.text == "Rook",
		"the name is kept, so a retry does not retype it")


func _it_hides_once_a_body_exists() -> void:
	# char_vitals is only sent for a PUPPETED character, so its arrival is the
	# server saying login succeeded -- rather than this screen trying to parse
	# success out of the text log.
	var state := CharState.new()
	_view.show()
	_view.bind(state)

	_expect(_view.visible, "the form stays up before login")

	state.ingest(_Const.CH_CHAR_STATUS, {"in_combat": false})
	_expect(_view.visible, "a channel that is not vitals does not dismiss it")

	state.ingest(_Const.CH_CHAR_VITALS, {"hp": 40.0, "max_hp": 40.0})
	_expect(not _view.visible, "vitals mean a body exists, so the form goes")


## The form is a function of whether a body exists, not a one-way dismissal.
##
## A dropped socket ends the Evennia Session, so the reconnect lands on the
## connection screen. If the form stayed hidden the player would have no route
## back in but typing `connect` by hand -- which is the whole reason the form
## exists on the web.
func _it_comes_back_when_the_session_is_lost() -> void:
	var state := CharState.new()
	_view.show()
	_view.bind(state)

	state.ingest(_Const.CH_CHAR_VITALS, {"hp": 40.0, "max_hp": 40.0})
	_expect(not _view.visible, "hidden while puppeted")

	state.reset()
	_expect(_view.visible, "and back once the session is gone")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
