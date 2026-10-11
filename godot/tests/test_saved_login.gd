extends Node
## Tests for SavedLogin: the server decides what the device keeps, and the
## file survives a restart. Writes to a disposable user:// path rather than
## the real profile.
##
##     godot --headless --path godot res://tests/test_saved_login.tscn

const _Const := preload("res://autoload/blackout_constants.gd")

const TEST_PATH := "user://test_saved_login.cfg"

var _failures := 0


func _ready() -> void:
	_clean()

	_a_new_device_has_no_saved_login()
	_the_token_channel_saves_a_login()
	_an_empty_token_forgets_it_and_keeps_the_name()
	_other_channels_are_not_its_business()
	_the_login_survives_a_restart()
	_the_name_match_ignores_case()
	_forget_keeps_the_name_for_the_form()
	_the_box_is_remembered_and_fenced()
	_changed_fires_on_each_change()

	_clean()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: saved_login")
	get_tree().quit(0)


func _clean() -> void:
	DirAccess.remove_absolute(ProjectSettings.globalize_path(TEST_PATH))


func _token(account: String, token: String) -> Dictionary:
	return {_Const.LOGIN_ACCOUNT_KEY: account, _Const.LOGIN_TOKEN_KEY: token}


func _fresh() -> SavedLogin:
	_clean()
	return SavedLogin.new(TEST_PATH)


func _a_new_device_has_no_saved_login() -> void:
	var saved := _fresh()
	saved.load_from_disk()

	_expect(not saved.has_login(), "no file means no saved login")
	_expect(saved.remember == SavedLogin.DEFAULT_REMEMBER, "the box starts at its default")


func _the_token_channel_saves_a_login() -> void:
	var saved := _fresh()
	var taken := saved.ingest(_Const.CH_LOGIN_TOKEN, _token("Rook", "abc"))

	_expect(taken, "the token channel is this model's")
	_expect(saved.has_login(), "a token makes a saved login")
	_expect(saved.account == "Rook" and saved.token == "abc", "and keeps both values")


## The server decides when a token went bad. The client never guesses.
func _an_empty_token_forgets_it_and_keeps_the_name() -> void:
	var saved := _fresh()
	saved.ingest(_Const.CH_LOGIN_TOKEN, _token("Rook", "abc"))
	saved.ingest(_Const.CH_LOGIN_TOKEN, _token("Rook", ""))

	_expect(not saved.has_login(), "an empty token forgets the login")
	_expect(saved.account == "Rook", "the name stays, so the form can show it")


func _other_channels_are_not_its_business() -> void:
	var saved := _fresh()
	var taken := saved.ingest(_Const.CH_CHAR_VITALS, _token("Rook", "abc"))

	_expect(not taken, "a different channel is refused")
	_expect(not saved.has_login(), "and changes nothing")


func _the_login_survives_a_restart() -> void:
	var saved := _fresh()
	saved.ingest(_Const.CH_LOGIN_TOKEN, _token("Two Words", "xyz"))
	saved.set_remember(false)

	var reloaded := SavedLogin.new(TEST_PATH)
	reloaded.load_from_disk()

	_expect(reloaded.account == "Two Words", "the name survives a restart")
	_expect(reloaded.token == "xyz", "the token survives a restart")
	_expect(not reloaded.remember, "the box survives a restart")


## Evennia finds an account by name with no regard to case.
func _the_name_match_ignores_case() -> void:
	var saved := _fresh()
	saved.ingest(_Const.CH_LOGIN_TOKEN, _token("Rook", "abc"))

	_expect(saved.is_for("rook"), "the match ignores case")
	_expect(saved.is_for("  Rook "), "and the space around the name")
	_expect(not saved.is_for("Bishop"), "another name does not match")


func _forget_keeps_the_name_for_the_form() -> void:
	var saved := _fresh()
	saved.ingest(_Const.CH_LOGIN_TOKEN, _token("Rook", "abc"))
	saved.forget()

	var reloaded := SavedLogin.new(TEST_PATH)
	reloaded.load_from_disk()

	_expect(not reloaded.has_login(), "forget reaches the file")
	_expect(reloaded.account == "Rook", "the name stays in the file")


func _the_box_is_remembered_and_fenced() -> void:
	var config := ConfigFile.new()
	config.set_value(SavedLogin.SECTION, SavedLogin.KEY_REMEMBER, "yes please")
	config.save(TEST_PATH)

	var saved := SavedLogin.new(TEST_PATH)
	saved.load_from_disk()

	_expect(saved.remember == SavedLogin.DEFAULT_REMEMBER,
		"a value that is not a bool falls back to the default")


func _changed_fires_on_each_change() -> void:
	var saved := _fresh()
	var fired := [0]
	saved.changed.connect(func(): fired[0] += 1)

	saved.ingest(_Const.CH_LOGIN_TOKEN, _token("Rook", "abc"))
	saved.forget()
	saved.forget()
	saved.set_remember(not saved.remember)
	saved.set_remember(saved.remember)

	_expect(fired[0] == 3, "changed fires for a real change only (got %d)" % fired[0])


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
