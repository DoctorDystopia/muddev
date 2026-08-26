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

const CONNECT_TEMPLATE := "connect %s %s"
const CREATE_TEMPLATE := "create %s %s"

## Emitted with a whole command a telnet player could have typed.
signal command_requested(command: String)

@onready var _name: LineEdit = %NameField
@onready var _password: LineEdit = %PasswordField
@onready var _connect: Button = %ConnectButton
@onready var _create: Button = %CreateButton
@onready var _paste: Button = %PasteButton
@onready var _message: Label = %Message

var _state: CharState


func _ready() -> void:
	_connect.pressed.connect(_on_connect)
	_create.pressed.connect(_on_create)
	_paste.pressed.connect(_paste_into_password)

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


func _on_char_changed() -> void:
	if _state.has_vitals:
		hide()


func _on_connect() -> void:
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

	# Evennia splits its login commands on whitespace, so a name with a space
	# has to be quoted -- its own connection screen says so. Done here rather
	# than left to the player, because the failure is an unhelpful "unknown
	# command" rather than anything about names.
	if account.contains(" "):
		account = '"%s"' % account

	_password.clear()
	_message.text = ""

	command_requested.emit(template % [account, secret])


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
