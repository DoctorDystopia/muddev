class_name ChooseOption
extends Control
## The right-click menu over the world pane: every verb the server said a thing
## affords, listed at the cursor.
##
## Modelled on OSRS's Choose Option box, and for the same reason it exists
## there: one thing in the world can be several things to you at once. A mutant
## raider corpse can be butchered where it lies or picked up and carried off,
## and a left click can only ever mean one of those. Left click still performs
## the default -- the first option, which is what the server puts in `interact`
## -- and right click asks.
##
## THERE IS DELIBERATELY NO VERB TABLE HERE, and that is the whole contract
## this file has to keep. Every row's command is a string the server composed,
## sent verbatim by [signal chosen], and every row's WORDING comes from the
## `label` the server sent beside it. This client decides how the list looks --
## the capitalisation, the ordering on screen, the colour of the target's name
## -- and decides nothing about what any of it does.
##
## [WorldView] documents what that rule cost the two previous clients that
## broke it. This is the third menu written over that payload and the first one
## that cannot go stale: a corpse that gains a Brain Farming yield grows a row
## here with no edit in this file.
##
## WHY THIS IS A FULL-PANE CONTROL WITH THE BOX INSIDE IT, and not just the box.
## The menu stands over a [SubViewportContainer], which forwards every mouse
## event it is given into the 3D pane. So while the box was only the box, a
## click anywhere else in the pane went to the world -- and two things followed
## from that, both of which players saw. The box never closed, because a
## dismissal that waits for `_unhandled_input` waits for an event the container
## has already eaten; and the click that should have closed it walked the
## player instead. A right click then left the client with a stale menu
## floating over the world, listing verbs for a corpse that might be gone.
##
## The transparent backdrop is the fix and it is what every context menu in
## every toolkit does: while the menu is open it OWNS the pane's clicks. It
## draws nothing, it sits above the container in the scene so GUI picking
## reaches it first, and it is invisible -- and therefore unpickable -- the
## rest of the time.

## Emitted with the exact command string to send. The caller is what talks to
## the server, so this stays a plain Control that a test can drive with no
## connection.
signal chosen(command: String)

## Emitted when the box closed without a choice -- Cancel, Escape, or a click
## anywhere else. Separate from [signal chosen] so a caller can restore hover
## state without having to infer "nothing happened" from silence.
signal dismissed

## The header OSRS puts above the list. Not a label for any one option, and not
## clickable.
const TITLE := "Choose Option"

## The last row, always. It is not an option the server sent and never becomes
## a command -- it is the way out for a player who right-clicked by accident,
## which is most right-clicks.
const CANCEL := "Cancel"

## How far the box is nudged from the cursor, so the pointer does not sit on
## top of the first row and pre-highlight it.
const CURSOR_OFFSET := Vector2(2.0, 2.0)

## How far inside the pane's edge the box must stay, so it never opens with
## half its rows off-screen. A right click near the bottom of the pane flips
## the box UP instead of overflowing -- the same thing every context menu does.
const EDGE_MARGIN := 4.0

## The box itself. Public so a test can read where it landed and how big it is
## -- which is what [method _placement] is judged on -- without reaching
## through a private name.
var box: PanelContainer

var _rows: VBoxContainer



func _init() -> void:
	visible = false

	# The backdrop fills its parent, so a click anywhere in the world pane is a
	# click on the menu while the menu is open.
	set_anchors_preset(Control.PRESET_FULL_RECT)

	# STOP on both, and for two different reasons. On the BOX, so a click on a
	# row is a click on the MENU -- without it the press falls through to the
	# world pane behind and walks the player to whatever tile happens to be
	# under the row they were aiming at. On the BACKDROP, so a click anywhere
	# else is a dismissal rather than a move order.
	mouse_filter = Control.MOUSE_FILTER_STOP

	box = PanelContainer.new()
	# Explicit, because a Container defaults to PASS rather than to Control's
	# STOP: without this a click on the box's own border or on the gap beside
	# the title would fall through to the backdrop and read as "clicked
	# somewhere else", closing the menu the player was aiming at.
	box.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(box)

	_rows = VBoxContainer.new()
	_rows.add_theme_constant_override("separation", 0)
	box.add_child(_rows)



## Show the options at a point in the parent's coordinate space.
##
## `options` are `{command, label, target}` dictionaries, in the order the
## server listed them -- the first is the default a left click would have sent.
## `target` is the entity's name and may be empty, which is what a tile's
## action looks like.
##
## Opening with an empty list closes the box rather than showing an empty one,
## because "this affords nothing" and "here is nothing" read very differently
## to a player mid-click.
func open(options: Array, at: Vector2) -> void:
	if options.is_empty():
		close()
		return

	_clear()
	_rows.add_child(_title_row())

	for option: Dictionary in options:
		_rows.add_child(_option_row(option))

	_rows.add_child(_cancel_row())

	visible = true
	# Immediately, not next frame: the box has to be placed before it is drawn,
	# and reset_size() takes the size the children just declared rather than
	# the stale one from the last time it was open.
	box.reset_size()
	box.position = _placement(at)


func close() -> void:
	if not visible:
		return

	visible = false
	_clear()


func is_open() -> bool:
	return visible


## Build one row's text: the verb the server named, then what it acts on.
##
## Static and public so a test can assert the wording without building a scene,
## and so the one piece of presentation in this file has a name.
##
## THE VERB IS USED AS SENT. `serialize_entity` capitalises it, exactly as
## `INVENTORY_ACTION_EQUIP` is ("Equip", "equip {slot}") -- one rule for the
## same field, so this menu and the inventory's cannot end up spelling their
## rows differently.
##
## JOINING is this file's job and not the server's, and that split is the whole
## of what is decided here. The entity's name is already on the row it belongs
## to; sending it again inside every label would put a third copy of the same
## string on `room_players`, the largest payload the feed sends and the one
## already measured against a ceiling.
##
## A row with no target is the verb alone, which is what a tile's `goto (4,3)`
## reads as. A label the server did not send falls back to the command's first
## word -- the verb by construction, since every command here is one a telnet
## player could type.
static func row_text(option: Dictionary) -> String:
	var label := str(option.get("label", "")).strip_edges()
	var command := str(option.get("command", "")).strip_edges()
	var target := str(option.get("target", "")).strip_edges()

	if target.is_empty():
		# Nothing is going to be appended, so the fallback is the WHOLE
		# command rather than its verb -- a tile's `goto (4,3)` reads as
		# "Goto (4,3)", where taking the first word alone would silently
		# offer "Goto" and drop the only part that says where.
		return _capitalised(label if not label.is_empty() else command)

	if label.is_empty():
		# The target supplies the rest of the line, so here the verb alone is
		# exactly right: "attack Mutant Raider" plus "Mutant Raider" would
		# otherwise name the raider twice.
		label = command.split(" ")[0]

	return "%s %s" % [_capitalised(label), target]


## Upper-case the first letter and leave the rest alone.
##
## Not String.capitalize(), which title-cases every word and rewrites
## snake_case into spaced words -- it would turn "goto (4,3)" into something
## it was not asked to, and a command is not prose. Idempotent, so applying it
## to a label the server already capitalised changes nothing.
static func _capitalised(text: String) -> String:
	if text.is_empty():
		return text

	return text.substr(0, 1).to_upper() + text.substr(1)


# ─── Input ───────────────────────────────────────────────────────────────────

## A click on the backdrop -- anywhere in the pane but the box -- closes.
##
## _gui_input and not _unhandled_input, and that is the fix rather than a
## tidy-up. Unhandled input never arrives here at all: the SubViewportContainer
## under this one takes every mouse event the GUI hands it and forwards it into
## the 3D pane, so the click that should dismiss the menu used to walk the
## player instead and leave the box standing. Arriving here means the backdrop
## itself was picked, which is exactly "the player clicked somewhere that is
## not a row" -- and because it was picked, the world never sees it.
func _gui_input(event: InputEvent) -> void:
	if not visible:
		return

	if event is InputEventMouseButton and (event as InputEventMouseButton).pressed:
		_dismiss()
		accept_event()


## Escape closes too, from anywhere.
##
## Still _unhandled_input, because a key press is not picked by position and
## nothing in the world pane claims this one. The mouse half of this used to
## live here as well; see [method _gui_input] for why it could not stay.
func _unhandled_input(event: InputEvent) -> void:
	if not visible:
		return

	if event.is_action_pressed("ui_cancel"):
		_dismiss()
		get_viewport().set_input_as_handled()


# ─── Private ─────────────────────────────────────────────────────────────────

func _dismiss() -> void:
	close()
	dismissed.emit()


func _clear() -> void:
	for child in _rows.get_children():
		_rows.remove_child(child)
		child.queue_free()


func _title_row() -> Control:
	var title := Label.new()
	title.text = TITLE
	title.mouse_filter = Control.MOUSE_FILTER_IGNORE

	return title


func _option_row(option: Dictionary) -> Control:
	var command := str(option.get("command", "")).strip_edges()
	var button := Button.new()
	button.text = row_text(option)
	button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	button.flat = true
	button.pressed.connect(func() -> void: _choose(command))

	return button


func _cancel_row() -> Control:
	var button := Button.new()
	button.text = CANCEL
	button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	button.flat = true
	button.pressed.connect(_dismiss)

	return button


func _choose(command: String) -> void:
	close()

	if command.is_empty():
		return

	chosen.emit(command)


## Where the box goes, given where the cursor is.
##
## Clamped into the parent rather than the window: this sits over the world
## pane, and a menu that escaped into the chat log beside it would be drawn
## somewhere the player was not looking. A box taller than the space below the
## cursor is moved up rather than shrunk, so no row is ever unreachable.
##
## The room is measured from the PANE -- this control's own parent -- and not
## from the backdrop, even though the backdrop covers exactly the same
## rectangle. A full-rect anchor is resolved by a layout pass, and open() runs
## between the right click and that pass; the backdrop's own size is still
## whatever it was last frame, which on the first right click of a session is
## zero, and every row would land in the top-left corner.
func _placement(at: Vector2) -> Vector2:
	var parent := get_parent() as Control

	if parent == null:
		return at + CURSOR_OFFSET

	# box.size is valid here because open() calls box.reset_size() first.
	var room := parent.size
	var wanted := at + CURSOR_OFFSET
	var most := room - box.size - Vector2(EDGE_MARGIN, EDGE_MARGIN)

	return Vector2(
		clampf(wanted.x, EDGE_MARGIN, maxf(EDGE_MARGIN, most.x)),
		clampf(wanted.y, EDGE_MARGIN, maxf(EDGE_MARGIN, most.y)))
