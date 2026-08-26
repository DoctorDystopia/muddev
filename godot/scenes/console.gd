extends Control
## The client shell: the text game on the left, the 3D world on the right.
##
## Owns the connection and the subscription handshake, and nothing else. The
## world pane reads the feed straight off Evennia's signals -- routing every
## payload through here first would make this the file everyone has to edit to
## add a channel, which is the dispatch chain the whole ack-driven design
## exists to avoid.

## Every name the SERVER owns, generated from
## blackout/systems/statefeed/constants.py by systems/statefeed/clientexport.py.
## Preloaded, not autoloaded -- the generated file declares no `extends Node`.
##
## `SUBSCRIBE_ALL` asks for everything. The server answers with the set it
## actually accepted and THAT is what gets bound; a hardcoded channel list here
## would be a second copy of constants.py, free to drift. `CH_SUBSCRIBED` is
## that answer -- the only channel name this client has to know before the
## server has told it anything.
const Const := preload("res://autoload/blackout_constants.gd")

@onready var _output: RichTextLabel = %Output
@onready var _input: LineEdit = %Input
@onready var _hud: PanelContainer = %Hud
@onready var _inventory: InventoryView = %Inventory
@onready var _login: LoginView = %Login

var _channels := PackedStringArray()

## The observer's own state -- avatar, vitals, status.
##
## Owned here rather than by the HUD because it is a MODEL and the HUD is a
## view: a second thing that needs to know your hp (a death screen, a combat
## pane) binds to this, and does not have to reach through a widget to find it.
var _char := CharState.new()

## What you are carrying and wearing. Owned here for the same reason _char is:
## it is a model, and the grid that draws it is a view.
var _items := InventoryState.new()

## The dossier. A model like the others; the window that draws it is a view.
var _summary := SummaryState.new()

## What was typed, and where in it the player is. Not a widget: the rules are
## worth testing without a keyboard, and most of them are the sort that feel
## obvious and are wrong in half the clients that implement them.
var _history := CommandHistory.new()

## How big everything looks. Persisted with ConfigFile under user://, which on
## the web is IndexedDB and survives a reload.
var _settings := ClientSettings.new()

## Windows, created in code because they are Windows rather than Controls and
## have no place in the console's layout tree.
var _sheet: SummaryView
var _options: OptionsView
var _help: HelpView
var _find: FindBar


func _ready() -> void:
	Evennia.opened.connect(_on_opened)
	Evennia.closed.connect(_on_closed)
	Evennia.text_received.connect(_on_text)
	Evennia.channel_received.connect(_on_channel)
	_input.text_submitted.connect(_on_submitted)
	_input.grab_focus()
	_hud.bind(_char)
	_inventory.bind(_items)

	# The pane acts only through Evennia.command(), the same as a clicked tile:
	# every command it emits was named by the server and is one a telnet player
	# could type. There is no privileged path from this screen to the game.
	_inventory.command_requested.connect(Evennia.command)

	# Same rule as every other pane: it emits a line a telnet player could type
	# and this sends it. The login form is not a privileged path.
	_login.bind(_char)
	_login.command_requested.connect(Evennia.command)

	_sheet = SummaryView.new()
	add_child(_sheet)
	_sheet.bind(_summary)
	_hud.sheet_requested.connect(_sheet.toggle)

	_options = OptionsView.new()
	add_child(_options)
	_options.bind(_settings)
	_hud.options_requested.connect(_options.toggle)

	_help = HelpView.new()
	add_child(_help)
	_hud.help_requested.connect(_help.toggle)

	# The find bar replaces the placeholder node the scene reserves for it, so
	# the layout slot is authored and the widget is built in code like the
	# other two -- its contents depend on nothing in the scene.
	_find = FindBar.new()
	var slot: Node = %FindBar
	slot.add_sibling(_find)
	slot.queue_free()
	_find.bind(_output)
	_find.dismissed.connect(func(): _input.grab_focus())

	# Up and down in the input walk the history. Connected rather than given
	# the LineEdit its own script: the history belongs to the session, not to
	# the widget, and a second input box would share this one.
	_input.gui_input.connect(_on_input_key)

	# Applied AFTER load, so a saved preference is in effect before the first
	# frame the player sees rather than snapping a moment later.
	_settings.changed.connect(_apply_settings)
	_settings.load_from_disk()
	_apply_settings()

	var err := Evennia.open()

	if err != OK:
		_note("could not open socket: error %d" % err)


func _on_opened() -> void:
	_note("connected to %s:%d" % [Evennia.DEFAULT_HOST, Evennia.DEFAULT_PORT])

	# Deliberately does NOT subscribe here. The socket is accepted by the
	# Portal, which is up whenever the game is reachable at all -- but an
	# inputfunc is handled by the Server, which may still be starting. A
	# subscribe sent now is dropped without a word. The server tells us when it
	# is ready by announcing an empty subscription set; see _on_channel.


func _on_closed(code: int, reason: String) -> void:
	_note("disconnected (%d) %s" % [code, reason])


func _on_text(bbcode: String) -> void:
	# Evennia sends one message per line without a trailing newline.
	_output.append_text(bbcode + "\n")


func _on_submitted(line: String) -> void:
	_input.clear()
	_history.push(line)

	if not line.is_empty():
		Evennia.command(line)


## Up and down walk the history; everything else is the LineEdit's own.
##
## `accept_event` matters: without it the key also reaches the default UI focus
## navigation and moves focus out of the input, which reads as the field going
## dead on the first up-arrow.
func _on_input_key(event: InputEvent) -> void:
	if not (event is InputEventKey):
		return

	var key := event as InputEventKey

	if not key.pressed:
		return

	if key.keycode == KEY_UP:
		_input.text = _history.previous(_input.text)
		_input.caret_column = _input.text.length()
		_input.accept_event()
		return

	if key.keycode == KEY_DOWN:
		_input.text = _history.next(_input.text)
		_input.caret_column = _input.text.length()
		_input.accept_event()
		return

	# Ctrl+F from the input opens find. Handled here rather than as a global
	# shortcut because the input is where the keyboard already is, and a global
	# binding would fire while the player is typing `f` into a find box.
	if key.ctrl_pressed and key.keycode == KEY_F:
		_find.open()
		_input.accept_event()


## Turn preferences into pixels. The ONLY place that does.
##
## content_scale_factor scales layout as well as glyphs, which is what makes it
## a real zoom rather than a font change -- the native answer to the one thing
## browser zoom gave the webclient for free.
func _apply_settings() -> void:
	var size_px := _settings.font_size

	for control: Control in [_output, _input]:
		control.add_theme_font_size_override("font_size", size_px)

	# RichTextLabel keeps a font size per style, so setting only `font_size`
	# leaves bold and italic text at the default and the log ends up ragged.
	for style: String in ["normal_font_size", "bold_font_size",
			"italics_font_size", "mono_font_size"]:
		_output.add_theme_font_size_override(style, size_px)

	get_window().content_scale_factor = _settings.ui_scale


func _on_channel(channel: String, _payload: Dictionary) -> void:
	if channel != Const.CH_SUBSCRIBED:
		# The observer's own channels. Each model is OFFERED the message and
		# reports whether it wanted it, so every channel name lives in the file
		# holding the fields it fills rather than being restated here in a
		# second match that could disagree with them.
		if _char.ingest(channel, _payload):
			return

		if _items.ingest(channel, _payload):
			return

		if _summary.ingest(channel, _payload):
			return

		if not _channels.has(channel):
			# Printed rather than shown: an outputfunc nobody handles is a
			# developer's problem, and the left pane belongs to the player.
			print("unbound channel: %s" % channel)

		return

	_channels = PackedStringArray(_payload.get("channels", []))

	# An empty set means the server has forgotten us: either it has just
	# finished syncing this session and never saw a subscribe, or a reload
	# wiped the ndb the set lives on. Either way the answer is to ask again,
	# and this is the only signal that we need to.
	if _channels.is_empty():
		_note("server has no subscription for us; subscribing")
		Evennia.send("blackout_subscribe", [], {"channels": Const.SUBSCRIBE_ALL})
		return

	_note("subscribed: %d channels" % _channels.size())


func _note(message: String) -> void:
	_output.append_text("[i][color=gray]-- %s[/color][/i]\n" % message)
