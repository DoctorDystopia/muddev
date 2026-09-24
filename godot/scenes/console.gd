extends Control
## The client shell: the 3D world, with the game log docked over its
## bottom-left corner and the control panel over its bottom-right.
##
## Owns the connection and the subscription handshake, and nothing else. The
## world pane reads the feed straight off Evennia's signals -- routing every
## payload through here first would make this the file everyone has to edit to
## add a channel, which is the dispatch chain the whole ack-driven design
## exists to avoid.

## Every name the SERVER owns, generated from
## blackout/systems/interface/statefeed/constants.py by systems/interface/statefeed/clientexport.py.
## Preloaded, not autoloaded -- the generated file declares no `extends Node`.
##
## `SUBSCRIBE_ALL` asks for everything. The server answers with the set it
## actually accepted and THAT is what gets bound; a hardcoded channel list here
## would be a second copy of constants.py, free to drift. `CH_SUBSCRIBED` is
## that answer -- the only channel name this client has to know before the
## server has told it anything.
const Const := preload("res://autoload/blackout_constants.gd")

## The three hints in the input. See [method _refresh_input_hint].
##
## Before login, the line that logs in. The form above the log sends the same
## line, and this tells a player who prefers to type it.
const LOGIN_HINT := "connect <name> <password>"

## While the input has the keyboard. It names the way OUT, because Escape is
## the only key that gives the keyboard to the map, and nothing else shows it.
const TYPE_MODE_HINT := "Type a command — Esc to walk with the keyboard"

## While the map has the keyboard. It names both layouts, with their
## diagonals, and the way back. See [MovementKeys].
const MOVE_MODE_HINT := "Movement: Click on tile / WASD + QEZC / HJKL + YUBN — Enter to type a command"

## The game log. Tabbed, and the tabs are the client's own -- see
## [ChatTabs] on why the server names what a line IS and never where it
## goes.
@onready var _chat: ChatView = %Chat
@onready var _input: LineEdit = %Input
@onready var _inventory: InventoryView = %Inventory
@onready var _login: LoginView = %Login

## The box the game log, the login form and the input hang in, over the
## bottom-left corner of the world pane. A [PanelDock], like the control panel.
##
## A sibling of the world pane and not a child of it. The loading veil covers
## the world pane only, so the log stays readable while the world loads. That
## is how the old text column behaved.
@onready var _console_dock: PanelDock = %ConsoleDock

## Where the vitals bars sit, and there are two because one of them can be
## hidden. See [method _place_vitals].
@onready var _world_vitals: MarginContainer = %WorldVitals
@onready var _text_vitals: MarginContainer = %TextVitals

## The box the control panel hangs in, over the world pane.
##
## ALWAYS VISIBLE, and that is a decision rather than an oversight. The panel
## holds Options, and a setting that can hide the screen you change it on is a
## trap. A player who wants the world back drags the dock small instead, and
## the size is remembered. See [PanelDock].
@onready var _dock: PanelDock = %PanelDock

## The control panel. Inventory, worn gear, character sheet, options, help.
@onready var _panel: PanelView = %Panel

## The world pane: the 3D view, the HUD over it, and the control panel's dock.
##
## NEVER HIDDEN, and `show_world` hides what is IN it instead --
## see [method _apply_settings]. It kept its whole column with an invisible
## world before 09/21/2026, because the panel was a second child of that
## column. The panel is inside this pane now, so hiding the pane would take
## Options with it AND give the log the whole window, with the dock over the
## input line.
@onready var _world_pane: Control = %WorldPane

## The 3D pane. Given the models it draws; it reads the entity, combat and
## aura channels off the feed itself.
@onready var _world: Node3D = %World

## The SubViewportContainer that shows [member _world]. Read for one signal:
## the mouse leaving the pane. See [method WorldView.clear_hover].
@onready var _world_view: SubViewportContainer = %WorldView

## The map, drawn small over the corner of the world pane. A second VIEW of
## [member _world_state], never a second copy of it.
@onready var _minimap: MinimapView = %Minimap

## Stands over the world pane between login and a drawable world. LAST child of
## the pane in the scene, so it covers the map, the minimap and the vitals
## rather than sitting under them.
@onready var _veil: LoadingVeil = %LoadingVeil

## XP drops, the session tracker and the progress bar, just left of the minimap.
## A view of [member _xp_tracker].
@onready var _xp_hud: XpHudView = %XpHud
@onready var _choose: ChooseOption = %ChooseOption

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

## Your weapon, its styles and which one is active. A model like the others; the
## Combat tab is a view of it.
var _combat_options := CombatOptionsState.new()

## What you have taken and how far through it you are. A model like the others.
var _quest_log := QuestState.new()

## The pop-up the server holds open over the world pane: the bank today. A
## model like the others; [PopupView] is the view of it.
var _popup := PopupState.new()

## Every XP award this session, and how fast. A model like the others -- and
## the one whose SESSION is the client's own reading rather than a server fact;
## see [XpTrackerState].
var _xp_tracker := XpTrackerState.new()

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

## What the game sounds like. A Node because every cue is a player it parents.
## Cues hang off MODEL signals, never off a line of text -- see [SoundCues].
var _sounds := SoundCues.new()

## When to redial after a drop. Pure schedule; the Timer below is the clock.
var _reconnect := ReconnectPolicy.new()

## The clock for the above. A Timer node rather than `create_timer().timeout`
## because this one has to be CANCELLABLE: a redial that succeeds while an
## older timer is still pending would otherwise open a second socket on top of
## the working one.
var _retry_timer: Timer

## Panel bodies, built here because their CONTENTS depend on nothing in the
## scene -- the sheet's rows come from `char_summary`, the options' bounds from
## [ClientSettings] -- and handed to [PanelView], which owns where they sit.
var _equipment: EquipmentView
var _sheet: SummaryView
var _combat_tab: CombatOptionsView
var _skill_grid: SkillsView
var _options: OptionsView
var _help: HelpView
var _quests: QuestsView
var _find: FindBar
var _popup_view: PopupView

## The model credits box, opened from the Options pane.
var _credits: CreditsView

## What a left click in the world would act on, along the bottom of the world
## pane. The same [HoverBar] the bag and the pop-up use.
var _world_hover: HoverBar

## How far the world hover bar stays inside the pane's edges, in pixels. The
## same margin the vitals and the minimap keep in console.tscn.
const WORLD_HOVER_MARGIN := 8

## Your hit points, and whatever resources follow them. ONE control, moved
## between two slots -- see [method _place_vitals].
var _vitals: VitalsBars


func _ready() -> void:
	Evennia.opened.connect(_on_opened)
	Evennia.closed.connect(_on_closed)
	Evennia.text_received.connect(_on_text)
	Evennia.channel_received.connect(_on_channel)
	_input.text_submitted.connect(_on_submitted)

	# The hint follows focus from ANY source, not only from _set_typing. The
	# bag and the find bar take focus too, and the map then has the keyboard.
	_input.focus_entered.connect(_refresh_input_hint)
	_input.focus_exited.connect(_refresh_input_hint)
	_input.grab_focus()
	# ServerEndpoint decides where art is fetched from, the same way it decides
	# where the socket dials -- keyed off the build rather than a constant
	# somebody has to remember to flip. The page origin is read here rather than
	# in there because it is the one input that needs a browser; see
	# asset_origin() on why the web case names the page's own host and not a
	# relative path.
	var asset_origin := ServerEndpoint.asset_origin(OS.is_debug_build(),
		OS.has_feature("web"), ServerEndpoint.page_origin())
	var registry := ModelRegistry.new()
	_meshes = MeshResolver.new(registry, asset_origin)
	add_child(_meshes)

	# The credits come from the same origin as the models they credit. Over
	# the whole console, not the world pane, so the box still opens with the
	# 3D world turned off.
	_credits = CreditsView.new()
	_credits.bind(registry.credits_url(asset_origin))
	add_child(_credits)

	# Before anything can be printed: _note() below writes into it, and the
	# very first thing this method does after binding is open a socket.
	_chat.bind(_chat_tabs)
	_chat.active_log_changed.connect(_on_active_log_changed)

	_vitals = VitalsBars.new()
	_vitals.bind(_char)

	_inventory.bind(_items, _meshes)

	# One fact is read there, and its cells read it: how big the player left
	# the amount box. See [AmountPrompt].
	_inventory.bind_settings(_settings)

	# The world pane draws YOU, so it needs the model that knows which asset you
	# are. Bound rather than left to read char_avatar itself: CharState already
	# owns that channel, and a second reader of one fact is how three modules
	# came to own db.active_quests.
	_world.bind_char(_char)
	_world.bind_meshes(_meshes)
	_world.bind_world(_world_state)

	# The settings as well, and only one of them is read there: whether a
	# figure slides between tiles. Given to the pane rather than applied here,
	# because _apply_settings turns a preference into a PIXEL and this one is a
	# rule about a 3D scene the console does not otherwise reach into.
	_world.bind_settings(_settings)

	# The resolver as well as the state: the minimap draws no meshes, but it
	# does have to know whether this map's ground is drawn as art, and asking
	# the shared resolver is what keeps its palette and the 3D pane's the same.
	_minimap.bind(_world_state, _meshes)

	# Same rule as every other pane: it emits a whole line a telnet player could
	# type, and this sends it. Clicking a minimap cell is the same
	# `WorldState.tile_action` lookup a click on the 3D pane makes.
	_minimap.command_requested.connect(Evennia.command)

	# The right-click menu. The 3D pane raises the question and the menu is a
	# sibling Control over the pane rather than a child of the Node3D, so the
	# 3D scene stays 3D and the box can be tested with no camera.
	#
	# The chosen row goes straight to Evennia.command(), like every other
	# affordance on this screen -- the string was composed by the server and is
	# one a telnet player could type, so a click can do nothing a typed line
	# cannot and every lock and cooldown still applies with nothing to audit.
	_world.options_requested.connect(_choose.open)
	_choose.chosen.connect(Evennia.command)

	# The pop-up, over the world pane and UNDER the right-click menu and the
	# veil, so both still cover it. Built in code for the reason the panel
	# bodies are: its contents depend on nothing in the scene. Every slot and
	# button sends a line the server named, through the one path everything on
	# this screen uses.
	_popup_view = PopupView.new()
	_popup_view.bind(_popup, _meshes)

	# The box the player moved and sized, and the amount box its slots open.
	# The pane WRITES this one, so it reads the rect here and never again --
	# see [method PopupView.bind_settings].
	_popup_view.bind_settings(_settings)
	_world_pane.add_child(_popup_view)
	# UNDER the dock, not under the right-click menu, and that is the pop-up's
	# own rule rather than a layout detail: "a pop-up draws no copy of the bag,
	# the inventory pane IS the bag". A bank that covered the bag would make
	# every Deposit action on it unreachable.
	_world_pane.move_child(_popup_view, _dock.get_index())
	_popup_view.command_requested.connect(Evennia.command)
	_popup_view.keyboard_released.connect(func(): _set_typing(true))

	_build_world_hover()

	# After both panes are bound, so the manifest landing finds consumers ready
	# rather than arriving at a pane that has not been given the resolver yet.
	_meshes.start()

	# After _meshes, _char and _world_state all exist, and added to the tree
	# because it owns a Timer -- the same reason MeshResolver is a Node.
	_readiness.bind(_char, _world_state, _meshes)
	add_child(_readiness)
	_veil.bind(_readiness)

	# Every model is fetched and drawn once, out of sight, the first time the
	# veil goes up -- so shader compiles freeze the loading screen rather than
	# the first corpse. At the veil and not at _meshes.start(): a compile
	# freezes the whole window, and the login form is not a screen to freeze
	# while somebody types a password. See MeshResolver.prefetch_all.
	_readiness.changed.connect(
		func(phase: SessionReadiness.Phase) -> void:
			if SessionReadiness.is_loading(phase):
				_meshes.prefetch_all())

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

	# Login and logout move the hint as well. The login form hides on the
	# same fact, so the hint and the form cannot disagree.
	_char.changed.connect(_refresh_input_hint)
	_refresh_input_hint()

	# Built, bound, then handed over. The panel adds them to the tree, so
	# nothing here is parented twice.
	#
	# Combat first, so it sits beside Inventory: a style is chosen for the
	# weapon worn there. A clicked style emits the `combatoptions <style>` line
	# the server named on its row, and this sends it like every other pane.
	_combat_tab = CombatOptionsView.new()
	_combat_tab.bind(_combat_options)
	_panel.add_panel(PanelView.TAB_COMBAT, _combat_tab)
	_combat_tab.command_requested.connect(Evennia.command)

	# Beside Inventory, because the two halves of one bag belong side by side in
	# the strip even though only one is drawn at a time. It shares the console's
	# resolver and the console's settings with the carried grid, so a `.glb` is
	# fetched once for both panes and an amount box is the size the player left
	# it in either.
	_equipment = EquipmentView.new()
	_equipment.bind(_items, _meshes)
	_equipment.bind_settings(_settings)
	_panel.add_panel(PanelView.TAB_EQUIPMENT, _equipment)

	# Same rule as every other pane: the command was named by the server and is
	# one a telnet player could type.
	_equipment.command_requested.connect(Evennia.command)

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

	# The roster says a level rose; the client decides that sounds like a
	# jingle. Off the model rather than the `[LEVEL_UP]` line in the log, so a
	# copy edit on the server cannot silence it.
	add_child(_sounds)
	_skills.levelled.connect(func(_skill_key: String, _level: int):
		_sounds.play(SoundCues.LEVEL_UP))

	# The roster as well as the tracker, for the level-up line: SkillsState is
	# the one owner of "a level rose", and the jingle above already hangs off it.
	_xp_hud.bind(_xp_tracker, _skills)

	_quests = QuestsView.new()
	_quests.bind(_quest_log)
	_panel.add_panel(PanelView.TAB_QUESTS, _quests)

	_options = OptionsView.new()
	_options.bind(_settings)
	_panel.add_panel(PanelView.TAB_OPTIONS, _options)

	# The Game half of the options pane is the SERVER's, so it asks rather than
	# writes -- the same path a clicked tile and an inventory drag use.
	_options.command_requested.connect(Evennia.command)

	# The XP session is the client's own reading, so starting it over asks the
	# model directly -- there is nothing on the server to tell.
	_options.xp_session_reset_requested.connect(_xp_tracker.reset)

	# The credits box is the client's own, so it opens with no server round
	# trip. Raised to the top, so it draws over every pane built after it.
	_options.credits_requested.connect(func():
		move_child(_credits, get_child_count() - 1)
		_credits.open())

	_help = HelpView.new()
	_panel.add_panel(PanelView.TAB_HELP, _help)


	_retry_timer = Timer.new()
	_retry_timer.one_shot = true
	_retry_timer.timeout.connect(_redial)
	add_child(_retry_timer)

	# The size the player dragged each dock to. Bound AFTER the settings exist
	# and before the file lands, which is the arrangement the dock's own
	# `_player_size` is written for.
	_dock.bind_settings(_settings)
	_console_dock.bind_settings(_settings)

	# The log dock draws over the panel dock, so a log dragged over the panel
	# covers the side grip of the panel. Each box stops one margin short of the
	# other. See [method PanelDock.keep_clear_of].
	_dock.keep_clear_of(_console_dock)
	_console_dock.keep_clear_of(_dock)

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
	# The scale of a first run comes from the screen, so a high-density screen
	# does not open at half size. A saved scale wins.
	_settings.set_shipped_ui_scale(
		ClientSettings.ui_scale_for_dpi(DisplayServer.screen_get_dpi()))
	_settings.load_from_disk()
	_apply_settings()

	var err := Evennia.open()

	if err != OK:
		_note("could not open socket: error %d" % err)


## Put the world's [HoverBar] along the bottom of the world pane.
##
## Bottom-left and not top-left as in OSRS, because the vitals hold the top
## left of this pane. It stands UNDER the pop-up, the right-click menu and the
## veil, so each of them covers it. It ignores the mouse, so a click through it
## still reaches the world.
##
## The pane gets no mouse motion after the mouse leaves it, so the leave clears
## the hover. Without that, the bar names a tile that the mouse left behind.
func _build_world_hover() -> void:
	_world_hover = HoverBar.new()
	_world_hover.outline()
	_world_hover.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE,
		Control.PRESET_MODE_MINSIZE, WORLD_HOVER_MARGIN)
	_world_hover.grow_vertical = Control.GROW_DIRECTION_BEGIN
	_world_pane.add_child(_world_hover)
	_world_pane.move_child(_world_hover, _popup_view.get_index())

	_world.hover_text_changed.connect(_world_hover.show_text)
	_world_view.mouse_exited.connect(_world.clear_hover)

	# The two docks cover the bottom corners. The bar and the pop-up follow
	# the gap between them. `item_rect_changed` and not `resized`: a window
	# resize moves the box of the panel, and its size can stay the same.
	_console_dock.get_node("Box").item_rect_changed.connect(_fit_dock_gap)
	_dock.get_node("Box").item_rect_changed.connect(_fit_dock_gap)


## Fit two things to the gap between the two docks: the [HoverBar] of the
## world, and the first rect of the pop-up.
##
## The text of the bar starts at the left edge of the bar. With the bar under
## the log dock, the player cannot see the start of the text.
func _fit_dock_gap() -> void:
	var left := _console_dock.box_rect().end.x
	var right := _dock.box_rect().position.x

	_world_hover.offset_left = left + WORLD_HOVER_MARGIN
	_world_hover.offset_right = right - WORLD_HOVER_MARGIN - _world_pane.size.x
	_popup_view.set_dock_gap(left, right)


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
	_combat_options.reset()
	_xp_tracker.reset()
	_popup.reset()

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
## mode is entered with a key players press for unrelated reasons. The focus
## signals keep it current. See [method _refresh_input_hint].
func _set_typing(typing: bool) -> void:
	if typing:
		_input.grab_focus()
		return

	_input.release_focus()


## Put the hint in the input that fits the session and the mode.
##
## The hint follows two facts, and this owns neither of them.
## [member CharState.has_vitals] tells whether a body exists. Focus tells who
## has the keyboard. Until
## 09/22/2026 only [method _set_typing] wrote it. The login hint from the scene
## thus stayed after login, until the player pressed Enter and then Escape.
##
## Before login the hint is the login line whatever the focus. The movement
## keys do nothing on the connection screen.
func _refresh_input_hint() -> void:
	if not _char.has_vitals:
		_input.placeholder_text = LOGIN_HINT
		return

	if _input.has_focus():
		_input.placeholder_text = TYPE_MODE_HINT
		return

	_input.placeholder_text = MOVE_MODE_HINT


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

	# The bus, not each player: every cue plays on SFX, so one write reaches a
	# sound already playing as well as the next one.
	SoundCues.apply_volume(_settings.sfx_volume)

	# A hidden Control is not drawn and its SubViewport stops rendering, which is
	# the point of the world setting on a machine that is struggling.
	#
	# The INVENTORY setting is now about clutter rather than cost: a
	# TabContainer draws only its current tab, so the item stage already stops
	# rendering whenever the player is looking at another tab. What the setting
	# buys is a strip without a tab you never use.
	# What `show_world` turns off is the DIORAMA: the 3D view that redraws every
	# tile every frame, and the two HUD pieces that only make sense over it. The
	# pane itself stays, because the control panel hangs in it -- see
	# [member _world_pane].
	#
	# Nothing unsubscribes. The models keep ingesting, so turning the view back
	# on shows the current world rather than an empty one waiting for a
	# snapshot.
	_world_view.visible = _settings.show_world
	_minimap.visible = _settings.show_world

	# BOTH halves of the bag. They were one pane until 09/21/2026, and a setting
	# that hid the carried grid while leaving the doll in the strip would be a
	# setting that half worked.
	var bag_hidden := not _settings.show_inventory
	_panel.set_panel_hidden(PanelView.TAB_INVENTORY, bag_hidden)
	_panel.set_panel_hidden(PanelView.TAB_EQUIPMENT, bag_hidden)
	_place_vitals()

	# Hidden, not unbound: the tracker keeps counting underneath, so turning the
	# HUD back on shows the session so far. Off with the 3D view as well as on
	# its own setting, because XP drops are drawn over the world and there is no
	# world to draw them over.
	_xp_hud.visible = _settings.show_xp_drops and _settings.show_world
	_xp_hud.set_skill_rates_shown(_settings.show_skill_rates)

	# With no world behind it, the log takes the full height and the width that
	# the control panel leaves. The docks are NOT pushed their sizes here. A
	# dock WRITES that setting, and a pane pushed the setting it writes is how a
	# slider in Options came to collapse the pane it sat in.
	_console_dock.fill_beside(null if _settings.show_world else _dock)


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

		if _combat_options.ingest(channel, _payload):
			return

		if _quest_log.ingest(channel, _payload):
			return

		if _popup.ingest(channel, _payload):
			return

		if _xp_tracker.ingest(channel, _payload):
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
