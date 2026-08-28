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

## Shown in the input while the map has the keyboard. See [method _set_typing].
const MOVE_MODE_HINT := "WASD / hjkl to move — Enter to type"

@onready var _output: RichTextLabel = %Output
@onready var _input: LineEdit = %Input
@onready var _hud: PanelContainer = %Hud
@onready var _inventory: InventoryView = %Inventory
@onready var _login: LoginView = %Login

## The whole 3D half. Hidden as one branch by the text-only setting; see
## [method _apply_settings].
@onready var _right: VSplitContainer = %Right

## The 3D pane, reached for one thing only: to give it the character model so it
## can draw your avatar. Everything else it needs it reads off the feed itself.
@onready var _world: Node3D = %World

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

## Where every mesh in the client comes from, for BOTH 3D panes.
##
## Owned here rather than by either pane, because a second resolver would mean a
## second model cache: the same `.glb` fetched twice, and a sword that appears in
## the room before it appears in the bag. The world pane used to build its own;
## this is the move its comment said would be needed once the inventory drew
## meshes too.
var _meshes: MeshResolver

## What was typed, and where in it the player is. Not a widget: the rules are
## worth testing without a keyboard, and most of them are the sort that feel
## obvious and are wrong in half the clients that implement them.
var _history := CommandHistory.new()

## How big everything looks. Persisted with ConfigFile under user://, which on
## the web is IndexedDB and survives a reload.
var _settings := ClientSettings.new()

## When to redial after a drop. Pure schedule; the Timer below is the clock.
var _reconnect := ReconnectPolicy.new()

## The clock for the above. A Timer node rather than `create_timer().timeout`
## because this one has to be CANCELLABLE: a redial that succeeds while an
## older timer is still pending would otherwise open a second socket on top of
## the working one.
var _retry_timer: Timer

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
	# ServerEndpoint decides where art is fetched from, the same way it decides
	# where the socket dials -- keyed off the build rather than a constant
	# somebody has to remember to flip. The page origin is read here rather than
	# in there because it is the one input that needs a browser; see
	# asset_origin() on why the web case names the page's own host and not a
	# relative path.
	_meshes = MeshResolver.new(ModelRegistry.new(),
		ServerEndpoint.asset_origin(OS.is_debug_build(), OS.has_feature("web"),
			ServerEndpoint.page_origin()))
	add_child(_meshes)

	_hud.bind(_char)
	_inventory.bind(_items, _meshes)

	# The world pane draws YOU, so it needs the model that knows which asset you
	# are. Bound rather than left to read char_avatar itself: CharState already
	# owns that channel, and a second reader of one fact is how three modules
	# came to own db.active_quests.
	_world.bind_char(_char)
	_world.bind_meshes(_meshes)

	# After both panes are bound, so the manifest landing finds consumers ready
	# rather than arriving at a pane that has not been given the resolver yet.
	_meshes.start()

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
	_hud.world_toggled.connect(_settings.set_show_world)

	_retry_timer = Timer.new()
	_retry_timer.one_shot = true
	_retry_timer.timeout.connect(_redial)
	add_child(_retry_timer)

	# The find bar replaces the placeholder node the scene reserves for it, so
	# the layout slot is authored and the widget is built in code like the
	# other two -- its contents depend on nothing in the scene.
	_find = FindBar.new()
	var slot: Node = %FindBar
	slot.add_sibling(_find)
	slot.queue_free()
	_find.bind(_output)
	_find.dismissed.connect(func(): _set_typing(true))

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
	_note("connected to %s" % Evennia.url())

	# A socket that opened is a schedule that no longer applies. Stopping the
	# timer as well as resetting the count matters: a redial that succeeded
	# while a later retry was already pending would otherwise be closed out
	# from under itself by that retry opening a second socket.
	_retry_timer.stop()
	_reconnect.reset()

	# Deliberately does NOT subscribe here. The socket is accepted by the
	# Portal, which is up whenever the game is reachable at all -- but an
	# inputfunc is handled by the Server, which may still be starting. A
	# subscribe sent now is dropped without a word. The server tells us when it
	# is ready by announcing an empty subscription set; see _on_channel.


## A drop clears the character and schedules a redial. A deliberate close does
## neither.
##
## The character MUST be cleared. A websocket close ends the Evennia Session,
## so everything `_char`, `_items` and `_summary` hold describes a body that is
## no longer puppeted -- and the reconnect lands on the connection screen, not
## back in the world. Clearing `_char` is also what brings the login form back;
## see [method CharState.reset].
func _on_closed(code: int, reason: String, requested: bool) -> void:
	_note("disconnected (%d) %s" % [code, reason])
	_char.reset()

	if requested:
		return

	var delay := _reconnect.next_delay()

	if _reconnect.at_ceiling():
		_note("reconnecting every %ds until the server answers" % int(delay))
	else:
		_note("reconnecting in %ds (attempt %d)" % [int(delay), _reconnect.attempts])

	_retry_timer.start(delay)


## One redial. Failing to even open the socket is itself a failed attempt, so
## the schedule keeps advancing rather than stalling on an error that never
## produces a `closed` signal to drive it.
func _redial() -> void:
	var err := Evennia.open()

	if err == OK:
		return

	var delay := _reconnect.next_delay()

	_note("could not reopen socket: error %d; retrying in %ds" % [err, int(delay)])
	_retry_timer.start(delay)


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
		return

	# Escape hands the keyboard to the map. See [method _set_typing].
	if key.keycode == KEY_ESCAPE:
		_set_typing(false)
		_input.accept_event()


## Movement keys, and the way back to the input.
##
## Reached only when the focused control did not want the key, which -- since
## the LineEdit consumes essentially everything while focused -- means this
## fires exactly when the player is NOT typing. That is the same condition
## `hotkeys.js` tests for with `document.activeElement`, arrived at through
## focus rather than through a tag name.
func _unhandled_key_input(event: InputEvent) -> void:
	if not (event is InputEventKey):
		return

	var key := event as InputEventKey

	if not key.pressed or key.echo:
		return

	if key.ctrl_pressed and key.keycode == KEY_F:
		_find.open()
		get_viewport().set_input_as_handled()
		return

	if key.keycode == KEY_ENTER or key.keycode == KEY_KP_ENTER:
		_set_typing(true)
		get_viewport().set_input_as_handled()
		return

	# Modifiers excluded so Ctrl+W (close a browser tab) and friends are not
	# quietly turned into a walk north.
	if key.ctrl_pressed or key.alt_pressed or key.meta_pressed:
		return

	var direction := MovementKeys.command_for(key.keycode)

	if direction.is_empty():
		return

	# The same line a telnet player types, through the one path everything in
	# this client acts through. A key is the player NAMING a direction, not a
	# claim about geometry -- which is why this does not consult the map.
	Evennia.command(direction)
	get_viewport().set_input_as_handled()


## Move the keyboard between the input and the map, and say so.
##
## The webclient never needed a mode. Its input is one DOM element among many
## and focus leaves it constantly, so `hotkeys.js` can simply ask "is the player
## typing?" and be right. Here [method _ready] grabs the input and nothing ever
## takes it away, so that question would answer "yes" forever and every movement
## key would be dead code.
##
## **Focus IS the mode.** There is deliberately no `_typing` flag beside it: the
## LineEdit already knows whether it has the keyboard, [method
## _unhandled_key_input] only runs when it does not, and a mirrored bool would
## be a second owner of one fact -- free to disagree with the widget the moment
## anything else moves focus, which the inventory and the find bar both do.
##
## The placeholder is not decoration either. A text field that has silently
## stopped accepting letters looks exactly like a client that has hung, and this
## mode is entered with a key players press for unrelated reasons.
func _set_typing(typing: bool) -> void:
	if typing:
		_input.placeholder_text = ""
		_input.grab_focus()
		return

	_input.placeholder_text = MOVE_MODE_HINT
	_input.release_focus()


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

	# Hiding the branch rather than each pane: a hidden Control is not drawn and
	# its SubViewport stops rendering, which is the point of the setting on a
	# machine that is struggling. Nothing unsubscribes -- the models keep
	# ingesting, so turning the panes back on shows the current world rather
	# than an empty one waiting for the next snapshot.
	_right.visible = _settings.show_world
	_hud.set_world_shown(_settings.show_world)


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
