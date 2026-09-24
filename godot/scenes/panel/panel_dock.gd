class_name PanelDock
extends Control
## A box over the world, hung from one bottom corner and sized by the player.
##
## Two docks use this script: the control panel (bottom-right) and the game log
## (bottom-left). The node exports four facts: the corner, the setting key,
## the shipped size and the shipped share. A third dock is thus one node in
## `console.tscn` and one key in [constant ClientSettings.DOCK_SIZE_KEYS].
##
## Until 09/21/2026 [PanelView] was the bottom half of a [VSplitContainer], so
## every pixel it had was a pixel the 3D world did not. The panel now floats
## over the world pane and takes its size from the player in BOTH axes, which
## the divider could never give: one offset can only trade height, and the
## width of the whole right column belonged to the other divider. The game log
## followed on 09/22/2026. Its `HSplitContainer` changed the width only, so the
## log always took the full height.
##
## ## It hangs from a corner, and that is the whole geometry
##
## The corner is fixed and the SIZE is the player's, so a stored position would
## be a second owner of a fact this file already decides. The player drags the
## side edge and the top edge -- the two edges that are not the corner -- and
## [method ClientSettings.set_dock_size] keeps what they chose. [ResizeGrips]
## makes the grips on those two edges and on the corner between them.
##
## Only the BOTTOM corners. The minimap owns the top-right of the world pane
## (see `console.tscn`) and the vitals own the top-left.
##
## ## The shipped size follows the pane
##
## Before the first drag, the box takes [member default_size] or
## [member default_share] of the room, whichever is smaller. A fixed size
## that fits a 1920 x 1080 window covers the minimap in a 1280 x 720 window.
## The two docks then leave no gap for a pop-up between them.
##
## ## Two docks never overlap
##
## The log dock draws over the panel dock. A log dragged over the panel thus
## covered the side grip of the panel, and the player could not size the
## panel again. [method keep_clear_of] now stops each box one margin short of
## the other. A dock does not raise its grips as the pop-up does, because a
## raised grip also draws over the loading veil.
##
## ## It is not a [Window], and it is not a pop-up either
##
## [PanelView] explains why the three floating [Window]s went: a web export is
## one canvas, so a Window is an embedded subwindow that cannot leave the game
## area. This is an ordinary [Control] over the world pane, which is what the
## minimap, the vitals, the veil and the right-click menu already are.
##
## A dock draws over the pop-up on purpose: "a pop-up draws no copy of the bag,
## the inventory pane IS the bag". It draws UNDER the right-click menu and the
## loading veil, which cover everything.
##
## **The world pane is never hidden, and this dock is the reason.** `show_world`
## turns off the 3D view and the two HUD pieces over it, not the pane. The panel
## holds Options, so a hidden pane would be a setting that hides the screen you
## change it on.
##
## ## It can fill the space beside another dock
##
## With the 3D world off, nothing is behind the log. [method fill_beside] then
## gives the log the full height. It also gives the log the width that the
## control panel leaves. The player's size stays in the settings, and it comes
## back when the world does.
##
## ## Nothing here knows what is in the box
##
## The dock positions one box and saves one size. What is in the box is the
## business of its content.
##
## Author: Nick Hobar
## Creation date: 09/21/2026

## How far the box stays clear of the pane's edges, in pixels.
const EDGE_MARGIN := 8.0

## The control panel before the player has ever dragged it, in pixels.
##
## Wide enough for the carried grid's four columns and tall enough for several
## of its rows. The default of [member default_size], so the panel needs no
## value in the scene.
const DEFAULT_SIZE := Vector2(460.0, 660.0)

## The most of the room that the control panel takes before the first drag.
##
## The height leaves the minimap clear in a 1280 x 720 window. The width
## leaves a gap between the two docks that a pop-up fits in. The default of
## [member default_share].
const DEFAULT_SHARE := Vector2(0.36, 0.68)

## Floor on the box, before the content's own minimum is taken into account.
##
## The content usually wins: a [TabContainer] reports the widest minimum of any
## tab in it, and the carried grid is four cells across. That is the honest
## bound, and it is the same rule [method PopupView._place_box] follows.
const MIN_SIZE := Vector2(180.0, 80.0)

## The corners a box can hang from, and where each puts the box in the free
## room of the pane: 0 is flush left or top, 1 is flush right or bottom.
const CORNER_BOTTOM_RIGHT := "bottom_right"
const CORNER_BOTTOM_LEFT := "bottom_left"
const CORNER_ANCHORS := {
	CORNER_BOTTOM_RIGHT: Vector2(1.0, 1.0),
	CORNER_BOTTOM_LEFT: Vector2(0.0, 1.0),
}

## The edges that the player drags, for each corner: the top edge and the side
## edge away from the corner.
const CORNER_FREE_EDGES := {
	CORNER_BOTTOM_RIGHT: ResizeGrips.TOP | ResizeGrips.LEFT,
	CORNER_BOTTOM_LEFT: ResizeGrips.TOP | ResizeGrips.RIGHT,
}

## How long after a drag the size is written, in seconds. A write for each
## frame of a drag is a file write for each frame of a drag.
const SIZE_SAVE_DELAY := 0.4

## Which corner the box hangs from. One of [constant CORNER_ANCHORS].
@export_enum("bottom_right", "bottom_left") var corner := CORNER_BOTTOM_RIGHT

## Which setting keeps this box's size. One of
## [constant ClientSettings.DOCK_SIZE_KEYS].
@export var size_key := ClientSettings.KEY_PANEL_SIZE

## The box before the player has ever dragged it, in pixels.
@export var default_size := DEFAULT_SIZE

## The largest part of the room, on each axis, that the box takes before the
## first drag.
@export var default_share := DEFAULT_SHARE

## The box itself, authored in `console.tscn` with the content inside it.
@onready var _box: PanelContainer = $Box

var _grips: ResizeGrips

## The box's rect when the drag started. A drag reports its offset from there.
var _drag_start := Rect2()

## The size the player chose, or zero before there is one. See
## [method _player_size].
var _size := Vector2.ZERO

## What the player set. The dock WRITES this one, so it reads the size once and
## never follows `changed` -- see [method PopupView.bind_settings] on why a
## pane that writes a setting must not also be pushed it.
var _settings: ClientSettings

var _size_timer: Timer

## The dock this box fills beside, or null when the player's size applies.
## See [method fill_beside].
var _beside: PanelDock

## The dock this box stops short of, or null. See [method keep_clear_of].
var _clear_of: PanelDock


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	resized.connect(_place_box)

	_grips = ResizeGrips.new(self, _box, CORNER_FREE_EDGES.get(corner,
		CORNER_FREE_EDGES[CORNER_BOTTOM_RIGHT]), false)
	_grips.drag_started.connect(func() -> void: _drag_start = box_rect())
	_grips.dragged.connect(_on_dragged)

	_size_timer = Timer.new()
	_size_timer.one_shot = true
	_size_timer.timeout.connect(_save_size)
	add_child(_size_timer)

	_place_box()


## Give the dock the player's settings. It takes the size from them the first
## time it places the box; see [method _player_size].
func bind_settings(settings: ClientSettings) -> void:
	_settings = settings
	_place_box()


## The box's rect, in this control's pixels.
func box_rect() -> Rect2:
	return Rect2(_box.position, _box.size)


## Size the box as a drag on a grip would. Public so a test can size it with no
## mouse.
##
## The drag itself calls this, so the gesture and the test take one path and
## the write cannot be reached by only one of them.
func resize_box(new_size: Vector2) -> void:
	_size = new_size
	_place_box()
	_remember_size()



## Fill the full height and the width that `other` leaves, or stop when
## `other` is null.
##
## The player cannot drag a filled box, so its grips go. The saved size does
## not change, and the box returns to it when the fill stops. The dock follows
## every resize of `other`'s box, so a drag on the panel moves the log's edge.
func fill_beside(other: PanelDock) -> void:
	if _beside == other:
		return

	_beside = other
	_follow(other)
	_place_box()


## Stop this box one margin short of `other`'s box, or stop no box when
## `other` is null.
##
## Only the width: both docks hang from the bottom edge, so they can overlap
## only across it. The dock follows every resize of `other`'s box. A dock that
## `other` fills beside is not clear of it, because the fill already leaves
## the room.
func keep_clear_of(other: PanelDock) -> void:
	_clear_of = other
	_follow(other)
	_place_box()


## Place the box again after each resize of `other`'s box. Connected one time,
## because [method fill_beside] and [method keep_clear_of] can both name the
## same dock.
func _follow(other: PanelDock) -> void:
	if other == null or other._box.resized.is_connected(_place_box):
		return

	other._box.resized.connect(_place_box)


## Put the box in its corner, at whatever size fits.
##
## Runs on every resize of the pane as well as on every drag, so it is the ONE
## owner of "the box is on screen and no smaller than its content". A size
## saved by a wide window comes back into a narrow one here rather than being
## refused on the way in.
func _place_box() -> void:
	var pane := size

	# Null while the scene is still being built, and zero for one frame before
	# the first layout pass.
	if _box == null or _grips == null or pane.x <= 0.0 or pane.y <= 0.0:
		return

	var inset := Vector2.ONE * EDGE_MARGIN
	var room := (pane - inset * 2.0).max(Vector2.ONE)
	var smallest := _smallest(room)
	var largest := _largest(room).max(smallest)
	var box_size := _wanted_size(room).clamp(smallest, largest)

	_box.size = box_size
	_box.position = inset + (room - box_size) * _anchor()

	# A filled box has no size of the player's to drag.
	_grips.set_shown(_beside == null)


## The floor on the box: the content's minimum or [constant MIN_SIZE], and
## never more than the room.
func _smallest(room: Vector2) -> Vector2:
	return MIN_SIZE.max(_box.get_combined_minimum_size()).min(room)


## The ceiling on the box: the room, less the width of the dock it keeps clear
## of.
func _largest(room: Vector2) -> Vector2:
	if _clear_of == null or _clear_of._beside == self:
		return room

	var taken := _clear_of.box_rect().size.x + EDGE_MARGIN

	return Vector2(room.x - taken, room.y)


## The size to place: the room beside the other dock, the player's size, or
## the shipped size.
func _wanted_size(room: Vector2) -> Vector2:
	if _beside != null:
		var taken := _beside.box_rect().size.x + EDGE_MARGIN
		return Vector2(room.x - taken, room.y)

	var chosen := _player_size()

	if chosen != Vector2.ZERO:
		return chosen

	return default_size.min(room * default_share)


## The player's size, taken from the settings the first time there is one, or
## zero before the first drag.
##
## Read LAZILY rather than at bind time, because the console binds every pane
## BEFORE it loads the file: a size read in [method bind_settings] would always
## be the shipped zero. Zero means "no drag yet", so the read repeats until
## there is something to read. [method PopupView._player_rect] is the same
## arrangement.
func _player_size() -> Vector2:
	if _size == Vector2.ZERO and _settings != null:
		_size = Vector2(_settings.dock_size(size_key))

	return _size


## Where the box sits in the free room, from [constant CORNER_ANCHORS].
func _anchor() -> Vector2:
	return CORNER_ANCHORS.get(corner, CORNER_ANCHORS[CORNER_BOTTOM_RIGHT])


## Size the box to the rect that the drag gives. Only the size is kept: the
## corner decides where the box sits, and a grip moves only the free edges.
func _on_dragged(edges: int, offset: Vector2) -> void:
	var inset := Vector2.ONE * EDGE_MARGIN
	var room := Rect2(inset, (size - inset * 2.0).max(Vector2.ONE))
	var dragged := ResizeGrips.dragged_rect(_drag_start, edges, offset,
		_smallest(room.size), room)

	resize_box(dragged.size)

## Write the size the box ENDED at, shortly.
##
## Read off `_box` and not off `_size`, because a drag past the minimum leaves
## the raw size smaller than anything the player can see. The number to keep
## is the one on screen.
func _remember_size() -> void:
	if _settings == null:
		return

	_size_timer.start(SIZE_SAVE_DELAY)


func _save_size() -> void:
	if _settings == null or _beside != null:
		return

	_settings.set_dock_size(size_key, Vector2i(_box.size))
