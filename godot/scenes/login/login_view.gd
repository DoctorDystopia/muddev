class_name LoginView
extends PanelContainer
## The first screen: name, password, connect or create.
##
## ## Why this exists at all, when the text input already worked
##
## A player could always type `connect <name> <password>` into the game input,
## and on desktop that is fine. On the WEB it is the single worst moment in the
## client, because pasting a password into a canvas is the one browser
## affordance Godot cannot simply inherit — see the class comment on
## [method _paste_into_password] for exactly what was measured.
##
## A form gives that problem somewhere to be solved once. It also gives the
## password field `secret = true`, which the shared game input can never have.
##
## ## It is not a privileged path
##
## The buttons send `connect <name> <password>` and `create <name> <password>` —
## the same two lines a telnet player types, through the same
## [method Evennia.command]. This screen knows no more about authentication than
## the input box it replaces, and the server treats it identically.
##
## ## How it knows to go away
##
## It hides when [CharState] reports vitals. Those channels are only sent for a
## PUPPETED character, so their arrival means login succeeded and a body
## exists — which is a fact from the server rather than this screen trying to
## parse success out of the text log.
##
## ## The saved login
##
## With "Remember me" ticked, a login by password sends `remember` once the
## body exists. The server answers with a token on `CH_LOGIN_TOKEN`, and
## [SavedLogin] keeps it. When the server is ready on a later socket, this form
## sends `resume <name> <token>` by itself. That is a command of the
## connection screen too, so the form is still not a privileged path.
##
## A clean close by the server stops the auto-login until the player presses
## Connect. A quit and a boot both close with code 1000. A client that logged
## straight back in would make both of them useless. Connect sends `resume`
## again, with an empty password and the saved name.

const CONNECT_TEMPLATE := "connect %s %s"
const CREATE_TEMPLATE := "create %s %s"

## The close code of a WebSocket that the server closed on purpose: `quit`,
## a boot, a shutdown. A dropped network gives some other code.
const CLOSE_NORMAL := 1000

const _Const := preload("res://autoload/blackout_constants.gd")

const _MSG_RESUMING := "Logging in as %s..."
const _MSG_WAITING := "Saved login for %s. Waiting for the server..."
const _MSG_SAVED := "Saved login for %s. Press Connect."
const _MSG_FORGOTTEN := "This device no longer keeps your login."
const _MSG_EXPIRED := "Saved login expired. Enter your password."
const _HINT_SAVED := "Saved. Leave empty."

## Emitted with a whole command a telnet player could have typed.
signal command_requested(command: String)

@onready var _name: LineEdit = %NameField
@onready var _password: LineEdit = %PasswordField
@onready var _connect: Button = %ConnectButton
@onready var _create: Button = %CreateButton
@onready var _paste: Button = %PasteButton
@onready var _remember: CheckBox = %RememberBox
@onready var _forget: Button = %ForgetButton
@onready var _message: Label = %Message

var _state: CharState
var _saved: SavedLogin

## True while the form may send `resume` by itself. A clean close by the
## server clears it, and a press of Connect sets it again.
var _resume_armed := true

## True once this socket carried a `resume`. One try for each socket.
var _resume_sent := false

## True while a `resume` waits for its answer: a body, or a refusal.
var _resume_pending := false

## True after a login by password with the box ticked, until the body exists.
var _remember_pending := false


func _ready() -> void:
	_connect.pressed.connect(_on_connect)
	_create.pressed.connect(_on_create)
	_paste.pressed.connect(_paste_into_password)
	_remember.toggled.connect(_on_remember_toggled)
	_forget.pressed.connect(_on_forget)

	# Both belong to a saved login, so they show only once one is bound.
	_remember.visible = false
	_forget.visible = false

	# Enter in either field submits, so the form behaves like every other login
	# form rather than requiring a trip to the mouse.
	_name.text_submitted.connect(func(_t): _password.grab_focus())
	_password.text_submitted.connect(func(_t): _on_connect())

	# The paste button is a WEB affordance. On desktop Ctrl+V is native and an
	# extra button would be clutter.
	_paste.visible = OS.has_feature("web")

	_name.grab_focus()


## Follow the character state, so the form can dismiss itself.
func bind(state: CharState) -> void:
	_state = state
	_state.changed.connect(_on_char_changed)


## Follow the saved login of this device. Optional: with none bound, the form
## is the plain password form it always was.
func bind_saved_login(saved: SavedLogin) -> void:
	_saved = saved
	_saved.changed.connect(_on_saved_changed)
	_remember.button_pressed = _saved.remember
	_remember.visible = true
	_on_saved_changed()


## The server can take a command now. The console calls this when the server
## confirms a subscription, which proves that the Server half is up.
##
## Sends `resume` at most once for each socket, and only with no body yet. A
## reload of a logged-in server confirms the subscription again, and must not
## log the player in twice.
func server_ready() -> void:
	if _saved == null or not _saved.has_login():
		return

	if not _resume_armed or _resume_sent:
		return

	if _state != null and _state.has_vitals:
		return

	_send_resume()


## The socket closed. Called by the console with the close code.
func session_ended(code: int) -> void:
	_resume_sent = false
	_resume_pending = false
	_remember_pending = false

	if code == CLOSE_NORMAL:
		_resume_armed = false

	# The text of the last socket ("Logging in as...") no longer applies.
	_message.text = ""

	if _saved != null:
		_on_saved_changed()


func _send_resume() -> void:
	_resume_sent = true
	_resume_pending = true
	_message.text = _MSG_RESUMING % _saved.account

	var line: String = _Const.LOGIN_RESUME_TEMPLATE.format({
		"account": _quoted(_saved.account),
		"token": _saved.token,
	})
	command_requested.emit(line)


## Show what the device keeps: the name, the Forget button, the hint in the
## empty password field.
##
## A token that goes while a `resume` is out means that the server refused
## it. The form then asks for the password.
func _on_saved_changed() -> void:
	var saved := _saved.has_login()

	_forget.visible = saved
	_password.placeholder_text = _HINT_SAVED if saved else ""

	if _name.text.strip_edges().is_empty():
		_name.text = _saved.account

	if saved:
		if _message.text.is_empty():
			var template := _MSG_WAITING if _resume_armed else _MSG_SAVED
			_message.text = template % _saved.account
		return

	if _resume_pending:
		_resume_pending = false
		_message.text = _MSG_EXPIRED
		_password.grab_focus()


func _on_remember_toggled(enabled: bool) -> void:
	if _saved != null:
		_saved.set_remember(enabled)


func _on_forget() -> void:
	_saved.forget()
	_message.text = _MSG_FORGOTTEN


## Visibility is a FUNCTION of whether a body exists, not a one-way dismissal.
##
## It used to only ever hide, which was right while a session could only be
## gained. Now that a dropped socket is reconnected, the form has to come back
## too: a new socket is a new Evennia Session at the connection screen, and a
## player facing that with the form still hidden has no route to log in but
## typing the command by hand. [method CharState.reset] is what clears the flag.
func _on_char_changed() -> void:
	visible = not _state.has_vitals

	if _state.has_vitals:
		_resume_pending = false

	if _state.has_vitals and _remember_pending:
		_remember_pending = false
		command_requested.emit(_Const.REMEMBER_COMMAND)


func _on_connect() -> void:
	# A press of Connect means that the player wants to be in. Thus, a drop
	# after this logs back in by itself.
	_resume_armed = true

	var account := _name.text.strip_edges()

	if _password.text.is_empty() and _saved != null and _saved.is_for(account):
		_send_resume()
		return

	_submit(CONNECT_TEMPLATE)


func _on_create() -> void:
	_submit(CREATE_TEMPLATE)


## Build and emit one login command, then forget the password.
##
## The field is cleared immediately. The command itself is what a telnet player
## types and goes over the same socket, but there is no reason for the
## credential to sit in a widget afterwards where a later screenshot, a crash
## handler or an idle player could surface it.
func _submit(template: String) -> void:
	var account := _name.text.strip_edges()
	var secret := _password.text

	if account.is_empty() or secret.is_empty():
		_message.text = "Both a name and a password are needed."
		return

	_password.clear()
	_message.text = ""
	_note_remember_choice()

	command_requested.emit(template % [_quoted(account), secret])


## Act on the "Remember me" box at a login by password.
##
## Ticked: ask for a token once the body exists, because `remember` is a
## command of the account and fails before login. Not ticked: drop any token
## this device holds, because the player said not to keep one.
func _note_remember_choice() -> void:
	if _saved == null:
		return

	_remember_pending = _remember.button_pressed

	if not _remember_pending:
		_saved.forget()


## Quote a name that holds a space. Evennia splits its login commands on
## whitespace, and its own connection screen says to quote such a name. The
## form does it for the player. Unquoted, the failure is an "unknown command"
## that says nothing about names.
static func _quoted(account: String) -> String:
	if account.contains(" "):
		return '"%s"' % account

	return account


## Ask the browser for the clipboard, on a real click.
##
## MEASURED, 08/25/2026, and this is why the button exists:
##
##   - Godot's web export DOES listen for the DOM `paste` event, but the
##     engine's `clipboard_get` reads `navigator.clipboard.readText()` -- the
##     PERMISSION-GATED path -- and swallows a rejection in an empty catch. So
##     a refused read is indistinguishable from an empty clipboard.
##   - Without user activation that read is refused in both engines. Chromium:
##     `NotAllowedError`. Firefox 154: `NotAllowedError: blocked due to lack of
##     user activation`, and it does not support the `clipboard-read`
##     permission at all, so there is nothing to grant once.
##
## A BUTTON PRESS IS USER ACTIVATION. That is the whole trick: the same read
## that fails silently on a keystroke succeeds from a click, and in Firefox the
## click is what its paste prompt attaches to. It costs one click in the worst
## case, on one field, once per session.
##
## Ctrl+V is untouched and still works wherever it works; this is a floor, not
## a replacement.
func _paste_into_password() -> void:
	if not OS.has_feature("web"):
		return

	var window := JavaScriptBridge.get_interface("window")

	if window == null:
		_message.text = "Clipboard unavailable; type the password instead."
		return

	# Handed a callback rather than awaited: readText() returns a Promise, and
	# GDScript cannot block on one. The callback is kept as a member for as
	# long as the page lives -- a local would be freed and the promise would
	# resolve into nothing.
	_paste_callback = JavaScriptBridge.create_callback(_on_clipboard_text)
	window.__godotPasteInto = _paste_callback
	JavaScriptBridge.eval("""
		(function () {
			navigator.clipboard.readText()
				.then(function (t) { window.__godotPasteInto(t); })
				.catch(function (e) { window.__godotPasteInto(""); });
		})();
	""", true)


## Held for the lifetime of the view; see _paste_into_password.
var _paste_callback: JavaScriptObject


func _on_clipboard_text(args: Array) -> void:
	var text := "" if args.is_empty() else str(args[0])

	if text.is_empty():
		# Firefox shows its paste prompt on the click; a refusal lands here.
		_message.text = "Clipboard not shared. Use Ctrl+V, or type it."
		return

	_password.text = text
	_password.grab_focus()
	_password.caret_column = _password.text.length()
	_message.text = ""
