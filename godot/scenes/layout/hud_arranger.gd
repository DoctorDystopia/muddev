class_name HudArranger
extends Node
## Places every HUD element over the world pane: the log, the control panel,
## the minimap, the vitals, the XP drops and the hover bar.
##
## ## One owner of where an element sits
##
## Until 09/29/2026 each element placed itself. The two docks each hung from a
## bottom corner (`PanelDock`), and the minimap, the vitals and the XP drops
## had fixed offsets in `console.tscn`. The player could size the docks and
## nothing else. Now this node places all of them from one layout, and the
## [LayoutEditor] changes that layout. An element that places itself would be
## a second owner of its rect, and the editor would fight it.
##
## The arranger runs a placement pass on every resize of the pane and on every
## change of the layout. The pass is the ONE owner of "an element is on the
## screen and no smaller than its content": a layout that a wide window saved
## comes back into a narrow one here. See [method HudLayout.clamp_into].
##
## ## Three facts decide whether an element is drawn
##
## The player hides an element in the editor. A setting in Options turns off
## an element: the 3D world takes the minimap with it. The console calls that
## a gate, through [method set_gate]. An element is drawn only when both say
## yes. The two stay apart, so the minimap comes back where the player put it
## when the world comes back.
##
## ## The log fills the room beside the panel when the world is off
##
## With no world behind it, the log takes the full height and the width that
## the control panel leaves. See [method fill_beside]. The layout of the log
## does not change, and the log returns to it when the world comes back.
##
## ## It writes the layout, and it reads the layout only when told
##
## A drag writes the layout through [method ClientSettings.set_layout], after
## [constant SAVE_DELAY]. The arranger reads the layout again only on
## [signal ClientSettings.layout_replaced]: a load, a reset, or a preset.
##
## Author: Nick Hobar
## Creation date: 09/29/2026

## Emitted after each placement pass. The layout editor moves its frames, and
## the console moves the pop-up gap.
signal placed

## How long after a drag the layout is written, in seconds. A write for each
## frame of a drag is a file write for each frame of a drag.
const SAVE_DELAY := 0.4

## The placement ranks. An element with a shipped rect function reads the
## rects of other elements, so it comes after them. A filled element reads the
## rect of the element it fills beside, so it comes last.
const RANK_PLAIN := 0
const RANK_DEPENDENT := 1
const RANK_FILLED := 2

var _pane: Control
var _settings: ClientSettings

## Every slot, in the order that they were added.
var _slots: Array[HudSlot] = []

## key -> slot.
var _by_key := {}

## The layout of the player: key -> partial entry. See [HudLayout].
var _entries := {}

## key -> the footprint of the last pass, in pane pixels.
var _rects := {}

## key -> false for an element that a setting turns off.
var _gates := {}

## key -> the key of the element it fills beside.
var _fills := {}

## True during a pass. A resize inside the pass does not start a second pass.
var _placing := false

var _save_timer: Timer


func _ready() -> void:
	_save_timer = Timer.new()
	_save_timer.one_shot = true
	_save_timer.timeout.connect(_save)
	add_child(_save_timer)


## Give the arranger the pane that it places elements in, and the settings
## that keep the layout. `settings` can be null in a test that saves nothing.
func bind(pane_control: Control, settings: ClientSettings = null) -> void:
	_pane = pane_control
	_pane.resized.connect(place_all)
	_settings = settings

	if _settings != null:
		_settings.layout_replaced.connect(reload)
		_entries = HudLayout.sanitize(_settings.layout)


## Add one element. The control gets top-left anchors, because the arranger
## gives its position and its size.
func add_slot(slot_item: HudSlot) -> void:
	_slots.append(slot_item)
	_by_key[slot_item.key] = slot_item
	slot_item.control.set_anchors_preset(Control.PRESET_TOP_LEFT)
	slot_item.control.minimum_size_changed.connect(place_all)
	place_all()


## Read the layout from the settings again, and place every element.
func reload() -> void:
	if _save_timer != null:
		_save_timer.stop()

	if _settings != null:
		_entries = HudLayout.sanitize(_settings.layout)

	place_all()


## Place every element from the layout.
func place_all() -> void:
	if _placing or _pane == null:
		return

	var pane_extent := _pane.size

	# Zero for one frame before the first layout pass.
	if pane_extent.x <= 0.0 or pane_extent.y <= 0.0:
		return

	_placing = true

	for slot_item: HudSlot in _ordered_slots():
		var rect := _resolve(slot_item, pane_extent)
		_rects[slot_item.key] = rect
		_apply(slot_item, rect)

	_placing = false
	placed.emit()


## Every slot, in the order that they were added.
func slots() -> Array[HudSlot]:
	return _slots


## The slot of `key`, or null.
func slot(key: String) -> HudSlot:
	return _by_key.get(key, null)


## The pane that the elements sit in.
func pane() -> Control:
	return _pane


## The size of the pane that the elements sit in.
func pane_size() -> Vector2:
	return _pane.size if _pane != null else Vector2.ZERO


## Where `key` sits on the screen, in pane pixels, from the last pass.
func footprint(key: String) -> Rect2:
	return _rects.get(key, Rect2())


## The footprints of every drawn element but `key`. A drag snaps to them.
##
## An element that follows other elements is not in the list. The hover bar
## ships one margin right of the log. A snap to one gap left of the hover bar
## put the edge of the log 2 pixels behind itself, and each mouse step pulled
## the edge back: the log jittered on each resize. After the player places the
## hover bar, it follows nothing, and a drag snaps to it again.
func others(key: String) -> Array[Rect2]:
	var rects: Array[Rect2] = []

	for slot_item: HudSlot in _slots:
		if slot_item.key == key or not is_drawn(slot_item.key):
			continue

		if not _follows_others(slot_item):
			rects.append(footprint(slot_item.key))

	return rects


## The smallest footprint that `key` can have: its minimum, times its scale.
func smallest_footprint(key: String) -> Vector2:
	var slot_item: HudSlot = slot(key)

	if slot_item == null:
		return Vector2.ZERO

	return _smallest(slot_item) * element_scale(key)


## True when the player did not hide `key`.
func is_shown(key: String) -> bool:
	var slot_item: HudSlot = slot(key)

	if slot_item == null or not slot_item.can_hide:
		return true

	return bool(_entry(key).get(HudLayout.KEY_SHOWN, true))


## True when a setting turns `key` off. See [method set_gate].
func is_gated_off(key: String) -> bool:
	return not bool(_gates.get(key, true))


## True when `key` is on the screen: shown, and not gated off.
func is_drawn(key: String) -> bool:
	return is_shown(key) and not is_gated_off(key)


## True when `key` fills the room beside another element, and so has no place
## of its own to drag.
func is_filled(key: String) -> bool:
	return _fills.has(key)


func opacity(key: String) -> float:
	var slot_item: HudSlot = slot(key)
	var value := float(_entry(key).get(HudLayout.KEY_OPACITY, HudLayout.DEFAULT_OPACITY))

	if slot_item == null:
		return value

	return maxf(value, slot_item.min_opacity)


func element_scale(key: String) -> float:
	return float(_entry(key).get(HudLayout.KEY_SCALE, HudLayout.DEFAULT_SCALE))


## A copy of the layout, for a preset.
func layout() -> Dictionary:
	return _entries.duplicate(true)


## Put `key` at the footprint `rect`, in pane pixels. The layout editor calls
## this for each step of a move or a resize.
##
## The anchor comes from the rect: see [method HudLayout.nearest_anchor]. The
## size that the entry keeps is the footprint without the scale.
func set_rect(key: String, rect: Rect2) -> void:
	if slot(key) == null or is_filled(key):
		return

	var entry := _entry(key).duplicate()
	_pin(entry, HudLayout.clamp_into(rect, pane_size()), element_scale(key))
	_store(key, entry)


## Show or hide `key`. An element that the player must not hide stays shown.
func set_shown(key: String, shown: bool) -> void:
	var slot_item: HudSlot = slot(key)

	if slot_item == null or not slot_item.can_hide:
		return

	var entry := _entry(key).duplicate()
	entry[HudLayout.KEY_SHOWN] = shown
	_store(key, entry)


func set_opacity(key: String, value: float) -> void:
	if slot(key) == null:
		return

	var entry := _entry(key).duplicate()
	entry[HudLayout.KEY_OPACITY] = value
	_store(key, entry)


## Scale `key`. The anchored corner of the element stays where it is.
##
## The current rect is pinned into the entry first. Otherwise an element at
## its shipped place would take a new place from the shipped offset and the
## new footprint, and it could jump.
func set_element_scale(key: String, value: float) -> void:
	if slot(key) == null:
		return

	var entry := _entry(key).duplicate()

	if not is_filled(key):
		_pin(entry, footprint(key), element_scale(key))

	entry[HudLayout.KEY_SCALE] = value
	_store(key, entry)


## Put `key` back where it ships, at the shipped size, shown, opaque, and at
## scale 1.
func reset_element(key: String) -> void:
	if not _entries.has(key):
		return

	_entries.erase(key)
	place_all()
	_save_later()


## Put every element back where it ships.
func reset_all() -> void:
	_entries = {}
	place_all()
	_save_later()


## Turn `key` on or off for a reason outside the layout: a setting in Options.
## The layout of the element does not change.
func set_gate(key: String, open: bool) -> void:
	var was_open := not is_gated_off(key)

	if was_open == open:
		return

	_gates[key] = open
	place_all()


## Make `key` fill the room beside `other`, or stop with an empty `other`.
## See the class notes.
func fill_beside(key: String, other: String) -> void:
	if _fills.get(key, "") == other:
		return

	if other.is_empty():
		_fills.erase(key)
	else:
		_fills[key] = other

	place_all()


## Write the layout now, and do not wait for the timer. For a test, and for
## the editor when it closes.
func save_now() -> void:
	if _save_timer != null:
		_save_timer.stop()

	_save()


func _entry(key: String) -> Dictionary:
	return _entries.get(key, {})


func _store(key: String, entry: Dictionary) -> void:
	_entries[key] = HudLayout.sanitize_entry(entry)
	place_all()
	_save_later()


## Write the anchor, the offset and the size of the footprint `rect` into
## `entry`.
func _pin(entry: Dictionary, rect: Rect2, scale_value: float) -> void:
	var pane_extent := pane_size()
	var anchor := HudLayout.nearest_anchor(rect, pane_extent)
	entry[HudLayout.KEY_ANCHOR] = anchor
	entry[HudLayout.KEY_OFFSET] = HudLayout.offset_for(anchor, rect.position, rect.size, pane_extent)
	entry[HudLayout.KEY_SIZE] = rect.size / scale_value


func _ordered_slots() -> Array[HudSlot]:
	var ordered := _slots.duplicate()
	ordered.sort_custom(func(first: HudSlot, second: HudSlot) -> bool:
		return _rank(first) < _rank(second))

	return ordered


## True when the place of the element comes from other elements: it fills
## beside one, or it is at a shipped rect that reads their rects.
func _follows_others(slot_item: HudSlot) -> bool:
	if is_filled(slot_item.key):
		return true

	return slot_item.default_rect.is_valid() \
		and not _entry(slot_item.key).has(HudLayout.KEY_ANCHOR)


func _rank(slot_item: HudSlot) -> int:
	if is_filled(slot_item.key):
		return RANK_FILLED

	if slot_item.default_rect.is_valid():
		return RANK_DEPENDENT

	return RANK_PLAIN


## The footprint of one element in a pane_extent of `pane_extent` pixels.
func _resolve(slot_item: HudSlot, pane_extent: Vector2) -> Rect2:
	var key := slot_item.key
	var entry := _entry(key)
	var scale_value := element_scale(key)

	if is_filled(key):
		return _fill_rect(key, pane_extent)

	var size: Vector2 = entry.get(HudLayout.KEY_SIZE, _default_size(slot_item, pane_extent))
	var position := Vector2.ZERO
	var footprint_size := (size.max(_smallest(slot_item)) * scale_value).min(pane_extent)

	if entry.has(HudLayout.KEY_ANCHOR):
		position = HudLayout.position_for(entry[HudLayout.KEY_ANCHOR],
			entry[HudLayout.KEY_OFFSET], footprint_size, pane_extent)
	elif slot_item.default_rect.is_valid():
		var shipped: Rect2 = slot_item.default_rect.call(pane_extent)
		size = entry.get(HudLayout.KEY_SIZE, shipped.size)
		footprint_size = (size.max(_smallest(slot_item)) * scale_value).min(pane_extent)
		position = shipped.position
	else:
		position = HudLayout.position_for(slot_item.default_anchor,
			slot_item.default_offset, footprint_size, pane_extent)

	return HudLayout.clamp_into(Rect2(position, footprint_size), pane_extent)


## The shipped size: the row size, no more than its share of the room.
func _default_size(slot_item: HudSlot, pane_extent: Vector2) -> Vector2:
	var room := (pane_extent - Vector2.ONE * HudLayout.EDGE_MARGIN * 2.0).max(Vector2.ONE)
	var size := slot_item.default_size

	if size == Vector2.ZERO:
		return _smallest(slot_item)

	if slot_item.default_share.x > 0.0:
		size.x = minf(size.x, room.x * slot_item.default_share.x)

	if slot_item.default_share.y > 0.0:
		size.y = minf(size.y, room.y * slot_item.default_share.y)

	return size


## The floor on the size of an element: its row floor or the minimum of its
## control, whichever is larger.
func _smallest(slot_item: HudSlot) -> Vector2:
	return slot_item.min_size.max(slot_item.control.get_combined_minimum_size())


## The full height, and the width on the wider side of the element that `key`
## fills beside.
func _fill_rect(key: String, pane_extent: Vector2) -> Rect2:
	var margin := HudLayout.EDGE_MARGIN
	var room := Rect2(Vector2.ONE * margin, (pane_extent - Vector2.ONE * margin * 2.0).max(Vector2.ONE))
	var other := footprint(str(_fills[key]))

	if not other.has_area():
		return room

	var left_width := other.position.x - margin - room.position.x
	var right_start := other.end.x + margin
	var right_width := room.end.x - right_start

	if left_width >= right_width:
		return Rect2(room.position, Vector2(maxf(left_width, 1.0), room.size.y))

	return Rect2(Vector2(right_start, room.position.y), Vector2(maxf(right_width, 1.0), room.size.y))


## Give the control its footprint, its scale, its opacity and its visibility.
func _apply(slot_item: HudSlot, rect: Rect2) -> void:
	var control := slot_item.control
	var scale_value := element_scale(slot_item.key)
	var alpha := opacity(slot_item.key)

	control.scale = Vector2.ONE * scale_value
	control.size = rect.size / scale_value
	control.position = rect.position - _origin_of(control)
	control.visible = is_drawn(slot_item.key)

	if slot_item.fade_background:
		control.self_modulate.a = alpha
	else:
		control.modulate.a = alpha


## Where the parent of `control` starts, in pane pixels. The log dock is not a
## child of the world pane, so its parent can start somewhere else.
func _origin_of(control: Control) -> Vector2:
	var parent := control.get_parent() as Control

	if parent == null or parent == _pane or not parent.is_inside_tree():
		return Vector2.ZERO

	return parent.global_position - _pane.global_position


func _save_later() -> void:
	if _settings != null and _save_timer != null:
		_save_timer.start(SAVE_DELAY)


func _save() -> void:
	if _settings != null:
		_settings.set_layout(_entries)
