extends Node
## Tests for the login form's two jobs that can be wrong: composing the command,
## and knowing when to get out of the way.
##
##     godot --headless --path godot res://tests/test_login_view.tscn

const _Const := preload("res://autoload/blackout_constants.gd")

## A disposable saved login, never the real profile.
const LOGIN_PATH := "user://test_login_view_login.cfg"

## The code of a dropped socket, as Godot reports an unclean close.
const CLOSE_DROPPED := -1

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

	_a_saved_login_logs_in_when_the_server_is_ready()
	_one_socket_gets_one_resume()
	_a_reload_of_a_logged_in_server_sends_no_resume()
	_a_drop_logs_back_in_but_a_quit_does_not()
	_connect_with_an_empty_password_uses_the_saved_login()
	_a_ticked_box_asks_for_a_token_once_the_body_exists()
	_an_unticked_box_drops_the_token()
	_a_refused_token_asks_for_the_password()
	_the_forget_button_drops_the_token()
	_a_spaced_name_is_quoted_in_the_resume()
	DirAccess.remove_absolute(ProjectSettings.globalize_path(LOGIN_PATH))

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


## A fresh form, a fresh character and a fresh saved login, with one stored
## token if `token` is not empty. Returns [view, state, saved, sent].
func _saved_form(account: String, token: String) -> Array:
	DirAccess.remove_absolute(ProjectSettings.globalize_path(LOGIN_PATH))

	var saved := SavedLogin.new(LOGIN_PATH)

	if not token.is_empty():
		saved.ingest(_Const.CH_LOGIN_TOKEN, {
			_Const.LOGIN_ACCOUNT_KEY: account,
			_Const.LOGIN_TOKEN_KEY: token,
		})

	var view: LoginView = load("res://scenes/login/login_view.tscn").instantiate()
	add_child(view)

	var sent: Array = []
	view.command_requested.connect(func(c: String): sent.append(c))

	var state := CharState.new()
	view.bind(state)
	view.bind_saved_login(saved)

	return [view, state, saved, sent]


func _log_in(state: CharState) -> void:
	state.ingest(_Const.CH_CHAR_VITALS, {"hp": 40.0, "max_hp": 40.0})


func _a_saved_login_logs_in_when_the_server_is_ready() -> void:
	var parts := _saved_form("Rook", "tok123")
	var view: LoginView = parts[0]
	var sent: Array = parts[3]

	_expect(sent.is_empty(), "nothing is sent before the server is ready")

	view.server_ready()

	_expect(sent == ["resume Rook tok123"],
		"a ready server gets `resume <name> <token>`")
	view.queue_free()


## A subscription can be confirmed more than once on one socket. One socket
## gets one try, so a refused token never loops.
func _one_socket_gets_one_resume() -> void:
	var parts := _saved_form("Rook", "tok123")
	var view: LoginView = parts[0]
	var sent: Array = parts[3]

	view.server_ready()
	view.server_ready()

	_expect(sent.size() == 1, "two confirmations on one socket send one resume")
	view.queue_free()


func _a_reload_of_a_logged_in_server_sends_no_resume() -> void:
	var parts := _saved_form("Rook", "tok123")
	var view: LoginView = parts[0]
	var sent: Array = parts[3]

	_log_in(parts[1])
	view.server_ready()

	_expect(sent.is_empty(), "a player with a body is not logged in twice")
	view.queue_free()


## A drop is the network. A clean close is the server or the player saying
## stop: `quit`, a boot, a shutdown. A client that logged straight back in
## would make `quit` useless.
func _a_drop_logs_back_in_but_a_quit_does_not() -> void:
	var parts := _saved_form("Rook", "tok123")
	var view: LoginView = parts[0]
	var sent: Array = parts[3]

	view.server_ready()
	view.session_ended(CLOSE_DROPPED)
	view.server_ready()

	_expect(sent.size() == 2, "a new socket after a drop logs in again")

	view.session_ended(LoginView.CLOSE_NORMAL)
	view.server_ready()

	_expect(sent.size() == 2, "a socket after a clean close does not")
	_expect(view._message.text.contains("Press Connect"),
		"and the form says what to press")
	view.queue_free()


func _connect_with_an_empty_password_uses_the_saved_login() -> void:
	var parts := _saved_form("Rook", "tok123")
	var view: LoginView = parts[0]
	var sent: Array = parts[3]

	view.session_ended(LoginView.CLOSE_NORMAL)
	view._name.text = "rook"
	view._password.text = ""
	view._on_connect()

	_expect(sent == ["resume Rook tok123"],
		"Connect with no password resumes, under the saved spelling")
	_expect(view._name.text == "rook", "the name field is left as typed")
	view.queue_free()


func _a_ticked_box_asks_for_a_token_once_the_body_exists() -> void:
	var parts := _saved_form("", "")
	var view: LoginView = parts[0]
	var sent: Array = parts[3]

	view._remember.button_pressed = true
	view._name.text = "Rook"
	view._password.text = "hunter2"
	view._on_connect()

	_expect(sent == ["connect Rook hunter2"], "the login goes out first")

	_log_in(parts[1])

	_expect(sent.size() == 2 and sent[1] == _Const.REMEMBER_COMMAND,
		"`remember` follows once the body exists")

	parts[1].reset()
	_log_in(parts[1])

	_expect(sent.size() == 2, "and only once")
	view.queue_free()


func _an_unticked_box_drops_the_token() -> void:
	var parts := _saved_form("Rook", "tok123")
	var view: LoginView = parts[0]
	var saved: SavedLogin = parts[2]
	var sent: Array = parts[3]

	view._remember.button_pressed = false
	view._name.text = "Rook"
	view._password.text = "hunter2"
	view._on_connect()
	_log_in(parts[1])

	_expect(not saved.has_login(), "an unticked box drops the saved token")
	_expect(not sent.has(_Const.REMEMBER_COMMAND), "and asks for no new one")
	_expect(not saved.remember, "the box state is saved")
	view.queue_free()


## The server answers a bad token with an empty one on the channel.
func _a_refused_token_asks_for_the_password() -> void:
	var parts := _saved_form("Rook", "tok123")
	var view: LoginView = parts[0]
	var saved: SavedLogin = parts[2]

	view.server_ready()
	saved.ingest(_Const.CH_LOGIN_TOKEN, {
		_Const.LOGIN_ACCOUNT_KEY: "Rook",
		_Const.LOGIN_TOKEN_KEY: "",
	})

	_expect(view._message.text.to_lower().contains("password"),
		"a refused token asks for the password")
	_expect(not view._forget.visible, "and the Forget button goes")
	view.queue_free()


func _the_forget_button_drops_the_token() -> void:
	var parts := _saved_form("Rook", "tok123")
	var view: LoginView = parts[0]
	var saved: SavedLogin = parts[2]

	_expect(view._forget.visible, "the Forget button shows with a saved login")

	view._on_forget()

	_expect(not saved.has_login(), "Forget drops the token")
	_expect(not view._forget.visible, "and the button goes")
	view.queue_free()


func _a_spaced_name_is_quoted_in_the_resume() -> void:
	var parts := _saved_form("Two Words", "tok123")
	var view: LoginView = parts[0]
	var sent: Array = parts[3]

	view.server_ready()

	_expect(sent == ['resume "Two Words" tok123'], "a spaced name is quoted")
	view.queue_free()


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
