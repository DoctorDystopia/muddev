class_name FloatingBox
extends Control
## A box over the world pane that the player moves and sizes: the pop-up and
## the world map.
##
## ## Why one class
##
## Until 10/19/2026 only the pop-up did this. The world map was a fixed box,
## 24 pixels inside the pane. Nick asked for a world map that acts like the
## pop-up. Thus, the move, the size, the clamp, the first rect and the save are
## one rule here. Each box adds only what it holds.
##
## ## Why a Control over the pane, and not a Window
##
## [SummaryView] records the answer: a native `Window` on the web is an embedded
## subwindow that cannot move beside the game and has no keyboard route to it.
## So this is what [ChooseOption] is: a full-pane Control that OWNS the pane's
## clicks while it shows. A click beside the box must not walk the player to
## the tile under it, and the SubViewportContainer below forwards every mouse
## event it gets into the 3D world. The world behind the box is dim.
##
## ## The player moves it and sizes it
##
## A drag on the title bar moves the box, and a drag on any edge or corner sizes
## it. The rect survives a close and a reopen, and it stays inside the pane when
## the pane itself changes size. This is presentation only, so the server never
## hears of it.
##
## [ResizeGrips] raises the grips: it draws them over every other box. The
## control panel draws over the box on purpose. Until 09/22/2026 it covered
## the only grip of the pop-up. A dock can still cover an edge of the box, but
## not the grip on that edge.
##
## It also survives the CLIENT, in [ClientSettings], because a rect that lives
## only in this node is one a player who moved the bank off their minimap set
## again on every run. Each box keeps its own rect, through
## [method _stored_rect]. The write is debounced for the reason
## [constant HudArranger.SAVE_DELAY] gives: `gui_input` fires for each frame of
## the gesture, and each setter writes the file.
##
## A floating box is not a HUD element of the layout editor. It opens and
## closes, so the editor would have no box to show most of the time. The
## player moves and sizes it where it is.
##
## ## It opens between the docks
##
## The console gives the gap between the log dock and the control panel
## through [method set_dock_gap]. When the gap is wide enough, the first rect
## opens centred in it. In a narrow window the box opens centred in the pane,
## over the docks.
##
## ## What a subclass gives
##
## Call `super()` first in `_init`. Godot 4 calls the `_init` of the parent only
## on that call. Then add the buttons to [member _title_bar], after the title,
## and add the contents to [member _column], under the title bar. To keep the
## rect between runs, override [method _stored_rect] and [method _store_rect].
##
## Author: Nick Hobar
## Creation date: 10/19/2026

## How far the box stays inside the pane, in pixels.
const EDGE_MARGIN := 16.0

## The first size of the box, as a part of the pane, and never more than
## [constant DEFAULT_MAX_SIZE]. The player's own size replaces it after the
## first drag.
const DEFAULT_FRACTION := Vector2(0.8, 0.85)

## The largest first box, in pixels. A bank at 80% of a 2560 x 1440 window is
## a grid of twenty columns. Most of that grid is empty.
const DEFAULT_MAX_SIZE := Vector2(900, 700)

## The narrowest gap between the docks that the first box opens in, in
## pixels. Four slots of a pop-up across. A narrower gap gives a box that fits
## two slots across, so the box opens centred in the pane instead.
const MIN_GAP_WIDTH := 360.0

## The smallest box a drag can make, in pixels. The box's own minimum size wins
## when it is larger.
const MIN_BOX_SIZE := Vector2(260, 180)

## Whether a drag on the title bar moves the box.
const DRAG_NONE := ""
const DRAG_MOVE := "move"

## The dim over the world behind the box.
const BACKDROP_COLOR := Color(0, 0, 0, 0.35)

## The text of the close button. Every box puts it last in its title bar.
const CLOSE_TEXT := "Close"

## Debounce for the write. One shot, restarted by each frame of a drag, so the
## file is written once shortly after the player lets go.
const RECT_SAVE_DELAY := 0.4

var _box: PanelContainer
var _grips: ResizeGrips

## The column inside the box. The title bar is its first child.
var _column: VBoxContainer

## The title, then the buttons of the subclass. A drag on it moves the box.
var _title_bar: HBoxContainer
var _title: Label

## The player's box, in pane pixels, or an empty rect before the first drag.
var _box_rect := Rect2()

## The box's rect when a grip drag started. A drag reports its offset from
## there.
var _drag_start := Rect2()

## The gap between the two docks, in pane pixels. The left end is the right
## edge of the log dock, and the right end is the left edge of the control
## panel. Both are zero before the console gives them. See
## [method set_dock_gap].
var _gap_left := 0.0
var _gap_right := 0.0

## What the player set. The rect comes out of it on the first placement, and
## goes back into it after a drag.
var _settings: ClientSettings

var _rect_timer: Timer

## One of the DRAG_* values.
var _drag := DRAG_NONE


func _init() -> void:
	visible = false
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	resized.connect(_place_box)

	var backdrop := ColorRect.new()
	backdrop.color = BACKDROP_COLOR
	backdrop.mouse_filter = Control.MOUSE_FILTER_IGNORE
	backdrop.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(backdrop)

	_box = PanelContainer.new()
	_box.theme_type_variation = &"PopupBox"
	_box.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_box)

	var margin := MarginContainer.new()
	margin.theme_type_variation = &"PaneMargin"
	_box.add_child(margin)

	_column = VBoxContainer.new()
	margin.add_child(_column)
	_column.add_child(_build_title_bar())

	# Raised, so no dock covers them. See the class notes.
	_grips = ResizeGrips.new(self, _box, ResizeGrips.ALL_EDGES, true)
	_grips.drag_started.connect(func() -> void: _drag_start = box_rect())
	_grips.dragged.connect(_on_grip_dragged)

	_rect_timer = Timer.new()
	_rect_timer.one_shot = true
	_rect_timer.timeout.connect(_save_box_rect)
	add_child(_rect_timer)


## Give the box the player's settings. The box takes its rect from them the
## first time it is placed -- see [method _player_rect].
##
## `changed` is deliberately NOT followed for the rect. Every other setting the
## console applies is one the pane draws from, and this one the box WRITES: a
## rect pushed back in on every `changed` is how a slider in Options came to
## collapse the pane it sat in. So **Reset in Options moves the box home on the
## next run, not at the click.** The alternative is a compare on every change,
## which loses a drag made inside the write delay.
func bind_settings(settings: ClientSettings) -> void:
	_settings = settings
	_place_box()


## Give the box the gap between the two docks, in pane pixels. The first rect
## opens in it. See [method _default_rect].
func set_dock_gap(left: float, right: float) -> void:
	_gap_left = left
	_gap_right = right
	_place_box()


## The grips of the box. For tests.
func grips() -> ResizeGrips:
	return _grips


func title_text() -> String:
	return _title.text


## The box's rect in the pane. For tests.
func box_rect() -> Rect2:
	return Rect2(_box.position, _box.size)


## Size the box as a drag on the grip would. Public so a test can size it with
## no mouse.
##
## The drag itself calls this, so the gesture and the test take one path and
## the write cannot be reached by only one of them.
func resize_box(new_size: Vector2) -> void:
	_box_rect = Rect2(_box.position, new_size)
	_place_box()
	_remember_box()


## Move the box as a drag on the title bar would. For tests.
func move_box(new_position: Vector2) -> void:
	_box_rect = Rect2(new_position, _box.size)
	_place_box()
	_remember_box()


# ─── For a subclass ──────────────────────────────────────────────────────────

## The rect that the settings keep for this box, or an empty rect before the
## first drag. The settings are bound when this runs. A box that keeps no
## rect between runs keeps this one.
func _stored_rect() -> Rect2:
	return Rect2()


## Keep the rect that the box ended at in the settings. A box that keeps no
## rect between runs keeps this one, which writes nothing.
func _store_rect(_rect: Rect2) -> void:
	pass


## Add the close button at the end of the title bar. Call it after every other
## button, so that each box puts it in the same place.
func _add_close_button(on_press: Callable) -> Button:
	var close := Button.new()

	close.text = CLOSE_TEXT
	close.pressed.connect(on_press)
	_title_bar.add_child(close)

	return close


# ─── Building ────────────────────────────────────────────────────────────────

## The title bar: the title, and the handle a drag moves the box by.
func _build_title_bar() -> HBoxContainer:
	_title_bar = HBoxContainer.new()
	_title_bar.mouse_filter = Control.MOUSE_FILTER_STOP
	_title_bar.mouse_default_cursor_shape = Control.CURSOR_MOVE
	_title_bar.gui_input.connect(_on_header_input)

	_title = Label.new()
	_title.theme_type_variation = &"PanelHeading"
	_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_title_bar.add_child(_title)

	return _title_bar


# ─── Moving and sizing the box ───────────────────────────────────────────────

## Put the box at the player's rect, or at the default, kept inside the pane.
## The grips follow the box by themselves.
func _place_box() -> void:
	var pane := size

	# The grips are null while _init still builds the box.
	if _grips == null or pane.x <= 0.0 or pane.y <= 0.0:
		return

	var rect := _player_rect()
	var inset := Vector2.ONE * EDGE_MARGIN
	var room := (pane - inset * 2.0).max(Vector2.ONE)
	var smallest := _smallest(room)

	if not rect.has_area():
		rect = _default_rect(pane, _gap_left, _gap_right)

	rect.size = rect.size.clamp(smallest, room)
	rect.position = rect.position.clamp(inset, pane - rect.size - inset)

	_box.position = rect.position
	_box.size = rect.size


## The floor on the box: the box's own minimum or [constant MIN_BOX_SIZE], and
## never more than the room.
func _smallest(room: Vector2) -> Vector2:
	return MIN_BOX_SIZE.max(_box.get_combined_minimum_size()).min(room)


## The player's rect, taken from the settings the first time there is one.
##
## Read LAZILY rather than at bind time, because the console binds every pane
## BEFORE it loads the file: a rect read in [method bind_settings] would always
## be the shipped empty one. An empty rect means "no drag yet", so the read
## repeats until there is something to read, and the first placement after the
## file lands gets it.
func _player_rect() -> Rect2:
	if _box_rect.has_area():
		return _box_rect

	if _settings != null:
		_box_rect = _stored_rect()

	return _box_rect


## The first rect. It is a part of the pane, and no larger than
## [constant DEFAULT_MAX_SIZE]. It is centred in the gap between the docks.
##
## A gap narrower than [constant MIN_GAP_WIDTH] leaves the box centred in the
## pane. The box then opens over the docks, and its raised grips stay in reach.
static func _default_rect(pane: Vector2, gap_left: float, gap_right: float) -> Rect2:
	var box_size := (pane * DEFAULT_FRACTION).min(DEFAULT_MAX_SIZE)
	var gap_width := gap_right - gap_left - EDGE_MARGIN * 2.0
	var centre := pane / 2.0

	if gap_width >= MIN_GAP_WIDTH:
		box_size.x = minf(box_size.x, gap_width)
		centre.x = (gap_left + gap_right) / 2.0

	return Rect2(centre - box_size / 2.0, box_size)


## Move one or two edges of the box to where the drag of a grip puts them.
## The edges that the grip does not name stay where they are.
func _on_grip_dragged(edges: int, offset: Vector2) -> void:
	var inset := Vector2.ONE * EDGE_MARGIN
	var room := Rect2(inset, (size - inset * 2.0).max(Vector2.ONE))

	_box_rect = ResizeGrips.dragged_rect(_drag_start, edges, offset,
		_smallest(room.size), room)
	_place_box()
	_remember_box()


## A left press on the title bar starts a move, motion moves the box, and the
## release ends it. The title bar gets the motion until the release, so the
## drag follows the mouse off it.
func _on_header_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var click := event as InputEventMouseButton

		if click.button_index == MOUSE_BUTTON_LEFT:
			_drag = DRAG_MOVE if click.pressed else DRAG_NONE
			accept_event()

		return

	if not (event is InputEventMouseMotion) or _drag != DRAG_MOVE:
		return

	var motion := (event as InputEventMouseMotion).relative
	move_box(_box.position + motion)
	accept_event()


## Write the rect the box ENDED at, shortly.
##
## The clamped rect off `_box`, not `_box_rect`: a drag past the edge leaves
## the raw rect outside the pane, and the number worth keeping is the one the
## player can see. [method HudArranger.set_rect] follows the same rule.
func _remember_box() -> void:
	if _settings == null:
		return

	_rect_timer.start(RECT_SAVE_DELAY)


func _save_box_rect() -> void:
	if _settings == null:
		return

	_store_rect(Rect2(_box.position, _box.size))
