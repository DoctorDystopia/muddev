class_name SavedLogin
extends RefCounted
## The login token of this device, saved between runs.
##
## The server gives a token out on `remember` and sends it on
## `CH_LOGIN_TOKEN`. This model keeps it in its own file under `user://`, and
## [LoginView] sends `resume <name> <token>` with it at the next start. The
## password never stays on the device.
##
## ## Why a token and not the password
##
## On the web, `user://` is IndexedDB, and any script on the page origin can
## read it. A stolen token opens one account until it expires, the password
## changes, or the player types `forget all`. A stolen password opens the
## account for good, and it can open the other accounts of the player too.
##
## ## Why its own file
##
## `client.cfg` holds looks, and a player can share it to show a layout. A
## key to the account must not ride along. This file holds the token, the
## name it belongs to, and the state of the "Remember me" box.
##
## ## The server decides
##
## An empty token on the channel means "forget it": `forget` sends one, and
## so does a refused `resume`. The client never guesses that a token went
## bad. It keeps the name, so the form still shows it.

const _Const := preload("res://autoload/blackout_constants.gd")

## Where the file lives. On the web, `user://` is IndexedDB.
const DEFAULT_PATH := "user://login.cfg"

const SECTION := "login"
const KEY_ACCOUNT := "account"
const KEY_TOKEN := "token"
const KEY_REMEMBER := "remember"

## The "Remember me" box starts ticked. The player asked for a client that
## does not need the password each time. The box is the way out on a shared
## computer.
const DEFAULT_REMEMBER := true

## Emitted after any change to the account, the token or the box.
signal changed

## The account name of the saved login. Kept after a token goes, so the form
## can show it.
var account := ""

## The token. Empty means that this device has no saved login.
var token := ""

## The last state of the "Remember me" box.
var remember := DEFAULT_REMEMBER

var _path: String


func _init(path: String = DEFAULT_PATH) -> void:
	# Injectable so a test can write somewhere disposable rather than into the
	# real profile.
	_path = path


## Whether this device can log in with no password.
func has_login() -> bool:
	return not account.is_empty() and not token.is_empty()


## Whether the saved login belongs to this account name.
##
## Evennia finds an account by name with no regard to case, so this does too.
func is_for(account_name: String) -> bool:
	return has_login() and account.to_lower() == account_name.strip_edges().to_lower()


## Take one channel message, if it is the login token channel.
##
## Returns whether the message was this model's, the same contract as
## [method CharState.ingest].
func ingest(channel: String, payload: Dictionary) -> bool:
	if channel != _Const.CH_LOGIN_TOKEN:
		return false

	var named := str(payload.get(_Const.LOGIN_ACCOUNT_KEY, "")).strip_edges()

	if not named.is_empty():
		account = named

	token = str(payload.get(_Const.LOGIN_TOKEN_KEY, ""))
	_commit()
	return true


## Drop the token of this device. The name stays for the form.
func forget() -> void:
	if token.is_empty():
		return

	token = ""
	_commit()


## Record the state of the "Remember me" box.
func set_remember(enabled: bool) -> void:
	if remember == enabled:
		return

	remember = enabled
	_commit()


## Read the file. A missing or bad file gives no saved login.
func load_from_disk() -> void:
	var config := ConfigFile.new()

	if config.load(_path) != OK:
		return

	account = str(config.get_value(SECTION, KEY_ACCOUNT, ""))
	token = str(config.get_value(SECTION, KEY_TOKEN, ""))

	var ticked: Variant = config.get_value(SECTION, KEY_REMEMBER, DEFAULT_REMEMBER)
	remember = ticked if typeof(ticked) == TYPE_BOOL else DEFAULT_REMEMBER

	changed.emit()


## Write the file. Returns the Error, so a caller can report a failure.
func save_to_disk() -> Error:
	var config := ConfigFile.new()
	config.set_value(SECTION, KEY_ACCOUNT, account)
	config.set_value(SECTION, KEY_TOKEN, token)
	config.set_value(SECTION, KEY_REMEMBER, remember)

	return config.save(_path)


func _commit() -> void:
	save_to_disk()
	changed.emit()
