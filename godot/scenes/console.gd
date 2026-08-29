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

## The game log. Tabbed, and the tabs are the client's own -- see
## [ChatTabs] on why the server names what a line IS and never where it
## goes.
@onready var _chat: ChatView = %Chat
@onready var _input: LineEdit = %Input
@onready var _inventory: InventoryView = %Inventory
@onready var _login: LoginView = %Login

## The two dividers, so a dragged one can be remembered. See
## [method _on_split_dragged].
@onready var _split: HSplitContainer = %Split

## Where the vitals bars sit, and there are two because one of them can be
## hidden. See [method _place_vitals].
@onready var _world_vitals: MarginContainer = %WorldVitals
@onready var _text_vitals: MarginContainer = %TextVitals

## The whole right column: the 3D world above, the control panel below.
##
## ALWAYS VISIBLE, and that is a decision rather than an oversight. It used to
## hide when both panes in it were off -- but the panel now holds Options, and a
## setting that can hide the screen you change it on is a trap. A player who
## wants text only drags the divider instead, and the divider is remembered.
@onready var _right: VSplitContainer = %Right

## The control panel. Inventory, character sheet, options, help.
@onready var _panel: PanelView = %Panel

## The world pane and everything drawn over it, hidden as one. The 3D world
## and the inventory used to share one setting, which meant a player who wanted
## the bag without the diorama could have neither.
@onready var _world_pane: Control = %WorldPane

## The 3D pane. Given the models it draws; it reads the entity, combat and
## aura channels off the feed itself.
@onready var _world: Node3D = %World

## The map, drawn small over the corner of the world pane. A second VIEW of
## [member _world_state], never a second copy of it.
@onready var _minimap: MinimapView = %Minimap

## Stands over the world pane between login and a drawable world. LAST child of
## the pane in the scene, so it covers the map, the minimap and the vitals
## rather than sitting under them.
@onready var _veil: LoadingVeil = %LoadingVeil

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

## The dossier. A model like the others; the tab that draws it is a view.
var _summary := SummaryState.new()

## Every skill, its XP curve and what it unlocks. A SEPARATE model from the
## dossier rather than a slice of it: the summary payload's contract is that a
## client iterates panels and never names one, so pulling a skills band out of
## it by key would have broken the rule the dossier is built on. The server
## split the band onto its own channel; this is the other end of that.
var _skills := SkillsState.new()

## What you have taken and how far through it you are. A model like the others.
var _quest_log := QuestState.new()

## The world: every island's grid, the links, and where you are standing.
##
## Owned here rather than by the 3D pane, which built its own until 08/28/2026.
## Two panes now draw the same map, and `blackout_map` arrives in CHUNKS -- so a
## second model would mean reassembling one payload twice and, on a resync, two
## reassemblies briefly disagreeing about which tiles exist. It is the same
## argument the comment on `_char` above makes, with a worse failure.
var _world_state := WorldState.new()

## Which tab a line of game text belongs in, and which tabs have unread lines.
##
## A model like the others, owned here rather than by the tab strip that draws
## it. It holds no text: the lines live in the strip's RichTextLabels, because
## a log big enough to matter must be appended to rather than reassigned, and a
## model that also kept a copy would store every line twice to save nothing.
var _chat_tabs := ChatTabs.new()

## Where every mesh in the client comes from, for BOTH 3D panes.
##
## Owned here rather than by either pane, because a second resolver would mean a
## second model cache: the same `.glb` fetched twice, and a sword that appears in
## the room before it appears in the bag. The world pane used to build its own;
## this is the move its comment said would be needed once the inventory drew
## meshes too.
var _meshes: MeshResolver

## Whether the player can actually play yet. A model like the others, and the
## veil that draws it is a view -- so the rule ("a body, a place, a map, and the
## art gone quiet") can be tested with no scene, no socket and no clock.
##
## Owned here because it is the only place that already holds all three of the
## models it reads.
var _readiness := SessionReadiness.new()

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

## Debounce for a dragged divider.
##
## `dragged` fires every frame of the gesture, and every ClientSettings setter
## writes the file -- so persisting the raw signal would be sixty ConfigFile
## saves a second, which on the web means sixty IndexedDB writes. The offset is
## held here and committed once, shortly after the player lets go. Wanting the
## write DEBOUNCED is not a reason to give ClientSettings a dirty flag: every
## other setter persists, and the gesture is what is chatty.
var _split_timer: Timer
const SPLIT_SAVE_DELAY := 0.4

## Panel bodies, built here because their CONTENTS depend on nothing in the
## scene -- the sheet's rows come from `char_summary`, the options' bounds from
## [ClientSettings] -- and handed to [PanelView], which owns where they sit.
var _sheet: SummaryView
var _skill_grid: SkillsView
var _options: OptionsView
var _help: HelpView
var _quests: QuestsView
var _find: FindBar

## Your hit points, and whatever resources follow them. ONE control, moved
## between two slots -- see [method _place_vitals].
var _vitals: VitalsBars


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

	# Before anything can be printed: _note() below writes into it, and the
	# very first thing this method does after binding is open a socket.
	_chat.bind(_chat_tabs)
	_chat.active_log_changed.connect(_on_active_log_changed)

	_vitals = VitalsBars.new()
	_vitals.bind(_char)

	_inventory.bind(_items, _meshes)

	# The world pane draws YOU, so it needs the model that knows which asset you
	# are. Bound rather than left to read char_avatar itself: CharState already
	# owns that channel, and a second reader of one fact is how three modules
	# came to own db.active_quests.
	_world.bind_char(_char)
	_world.bind_meshes(_meshes)
	_world.bind_world(_world_state)

	# The resolver as well as the state: the minimap draws no meshes, but it
	# does have to know whether this map's ground is drawn as art, and asking
	# the shared resolver is what keeps its palette and the 3D pane's the same.
	_minimap.bind(_world_state, _meshes)

	# Same rule as every other pane: it emits a whole line a telnet player could
	# type, and this sends it. Clicking a minimap cell is the same
	# `WorldState.tile_action` lookup a click on the 3D pane makes.
	_minimap.command_requested.connect(Evennia.command)

	# After both panes are bound, so the manifest landing finds consumers ready
	# rather than arriving at a pane that has not been given the resolver yet.
	_meshes.start()

	# After _meshes, _char and _world_state all exist, and added to the tree
	# because it owns a Timer -- the same reason MeshResolver is a Node.
	_readiness.bind(_char, _world_state, _meshes)
	add_child(_readiness)
	_veil.bind(_readiness)

	# The veil asks; it does not reach into the model. Same rule as every other
	# view on this screen.
	_veil.skip_requested.connect(_readiness.skip)

	# The pane acts only through Evennia.command(), the same as a clicked tile:
	# every command it emits was named by the server and is one a telnet player
	# could type. There is no privileged path from this screen to the game.
	_inventory.command_requested.connect(Evennia.command)

	# Same rule as every other pane: it emits a line a telnet player could type
	# and this sends it. The login form is not a privileged path.
	_login.bind(_char)
	_login.command_requested.connect(Evennia.command)

	# Built, bound, then handed over. The panel adds them to the tree, so
	# nothing here is parented twice.
	_sheet = SummaryView.new()
	_sheet.bind(_summary)
	_panel.add_panel(PanelView.TAB_CHARACTER, _sheet)

	# Given the settings as well as the roster: WHERE a clicked skill's detail
	# is shown -- this pane, the game log, or both -- is a presentation choice,
	# and this is the control that acts on it.
	_skill_grid = SkillsView.new()
	_skill_grid.bind(_skills, _settings)
	_panel.add_panel(PanelView.TAB_SKILLS, _skill_grid)

	# Same rule as every other pane: it emits a whole line a telnet player
	# could type -- the `skills <skill>` command the SERVER named on each row --
	# and this sends it. There is no privileged path from this screen to the
	# game.
	_skill_grid.command_requested.connect(Evennia.command)

	_quests = QuestsView.new()
	_quests.bind(_quest_log)
	_panel.add_panel(PanelView.TAB_QUESTS, _quests)

	_options = OptionsView.new()
	_options.bind(_settings)
	_panel.add_panel(PanelView.TAB_OPTIONS, _options)

	# The Game half of the options pane is the SERVER's, so it asks rather than
	# writes -- the same path a clicked tile and an inventory drag use.
	_options.command_requested.connect(Evennia.command)

	_help = HelpView.new()
	_panel.add_panel(PanelView.TAB_HELP, _help)


	_retry_timer = Timer.new()
	_retry_timer.one_shot = true
	_retry_timer.timeout.connect(_redial)
	add_child(_retry_timer)

	_split_timer = Timer.new()
	_split_timer.one_shot = true
	_split_timer.timeout.connect(_save_splits)
	add_child(_split_timer)

	_split.dragged.connect(_on_split_dragged)
	_right.dragged.connect(_on_split_dragged)

	# The find bar replaces the placeholder node the scene reserves for it, so
	# the layout slot is authored and the widget is built in code like the
	# other two -- its contents depend on nothing in the scene.
	_find = FindBar.new()
	var slot: Node = %FindBar
	slot.add_sibling(_find)
	slot.queue_free()
	_find.bind(_chat.active_log())
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
	_quest_log.reset()
	_skills.reset()

	# A new socket is a new Evennia Session at the connection screen, so the
	# next login has to be waited for again -- including the player's decision
	# to skip, which was about the session that just ended.
	_readiness.reset()

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


## One line of game output.
##
## The routing tag rides in the outputfunc's kwargs -- `msg(text=(line,
## {"type": "combat"}))` on the server reaches here as `{"type": "combat"}` --
## and an ABSENT tag is the normal case for everything Evennia says on its own
## behalf. Read as "" and resolved by [ChatTabs]; nothing is dropped.
func _on_text(bbcode: String, kwargs: Dictionary) -> void:
	# Evennia sends one message per line without a trailing newline.
	_chat.append(bbcode, str(kwargs.get(Const.MESSAGE_TYPE_KEY, "")))


## Ctrl+F follows the tab the player is looking at.
##
## Rebound rather than searching every tab: a find that spanned tabs would have
## to scroll one the player cannot see, and "3 of 40" would count matches in
## logs they are not reading.
func _on_active_log_changed(pane: RichTextLabel) -> void:
	if _find != null:
		_find.bind(pane)


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

	# Ctrl+Tab walks the chat tabs WITHOUT leaving the input, which is the
	# whole point of binding it here as well as below: a player mid-sentence
	# can check the combat log and keep typing.
	if key.ctrl_pressed and key.keycode == KEY_TAB:
		_chat.cycle(not key.shift_pressed)
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

	if key.ctrl_pressed and key.keycode == KEY_TAB:
		_chat.cycle(not key.shift_pressed)
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

	_input.add_theme_font_size_override("font_size", size_px)

	# Every tab, and every font style within each -- see
	# [method ChatView.apply_font_size] on why one property is not enough.
	_chat.apply_font_size(size_px)

	get_window().content_scale_factor = _settings.ui_scale

	# A hidden Control is not drawn and its SubViewport stops rendering, which is
	# the point of the world setting on a machine that is struggling. Nothing
	# unsubscribes -- the models keep ingesting, so turning the pane back on
	# shows the current world rather than an empty one waiting for a snapshot.
	#
	# The INVENTORY setting is now about clutter rather than cost: a
	# TabContainer draws only its current tab, so the item stage already stops
	# rendering whenever the player is looking at another tab. What the setting
	# buys is a strip without a tab you never use.
	_world_pane.visible = _settings.show_world
	_panel.set_panel_hidden(
		PanelView.TAB_INVENTORY, not _settings.show_inventory)
	_place_vitals()

	# Assigning an offset does not emit `dragged`, so this cannot loop back into
	# the debounce below.
	_split.split_offset = _settings.text_split
	_right.split_offset = _settings.world_split


## Put the vitals bars wherever the player can still see them.
##
## Over the world pane when it is drawn, and in a strip above the log when it is
## not. ONE control moved between two slots rather than two views of one model:
## the bars are the same bars, and a second copy would be a second thing to keep
## in step with a resource added later.
##
## This is not tidiness. `show_world` hides the whole world branch, so bars
## simply parented to the pane they overlay would vanish with it -- and hit
## points are the one number a MUD player cannot play without. A player turning
## the 3D off on a struggling machine would have lost them.
func _place_vitals() -> void:
	var target := _world_vitals if _settings.show_world else _text_vitals

	# The strip above the log takes no space at all when the bars are not in
	# it, so the log keeps every pixel it had.
	_text_vitals.visible = not _settings.show_world

	if _vitals.get_parent() == target:
		return

	if _vitals.get_parent() != null:
		_vitals.get_parent().remove_child(_vitals)

	target.add_child(_vitals)


## A divider was dragged. Remember it, shortly.
##
## Both dividers share one handler and one timer, and the offset is READ back
## off the containers when the timer fires rather than carried in the signal:
## the player may drag one, then the other, inside the same window, and a
## handler that trusted its argument would save whichever fired last twice.
func _on_split_dragged(_offset: int) -> void:
	_split_timer.start(SPLIT_SAVE_DELAY)


func _save_splits() -> void:
	_settings.set_text_split(_split.split_offset)
	_settings.set_world_split(_right.split_offset)


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

		if _skills.ingest(channel, _payload):
			return

		if _quest_log.ingest(channel, _payload):
			return

		if _world_state.ingest(channel, _payload):
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


## The CLIENT talking, rather than the game.
##
## Tagged as the server would tag it, so connection notices file under System
## beside the server's own. This is the one place the client writes into the
## log at all, and it names a generated constant rather than a literal for the
## same reason every call site on the server does.
func _note(message: String) -> void:
	_chat.append("[i][color=gray]-- %s[/color][/i]" % message, Const.MSG_SYSTEM)
