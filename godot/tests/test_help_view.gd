extends Node
## Unit tests for HelpView -- the pane that tells the player what the client does.
##
##     godot --headless --path godot res://tests/test_help_view.tscn
##
## Needs nothing running. This file is about width: the player sizes the pane,
## and the interface scale moves its width too. At any width, every line of
## every entry must wrap inside the pane, and none may hold the dock open.

## The height of the view in every case. Only the width changes between cases.
const HEIGHT := 600.0

## The two margins of the pane (12 px each), which the dock floor includes.
const PANE_MARGINS := 24.0

var _failures := 0
var _view: HelpView


func _ready() -> void:
	_no_entry_breaks_a_sentence_by_hand()
	await _the_content_asks_for_no_width()
	await _every_label_stays_inside_the_pane()
	await _a_long_text_wraps_in_a_narrow_pane()
	await _the_rows_stack_when_narrow_and_not_when_wide()
	await _the_same_view_follows_a_resize_both_ways()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: help_view")
	get_tree().quit(0)


## The pane widths, from the narrowest the layout allows to a wide one. The
## narrowest is the dock floor less the margins of the pane.
func _widths() -> Array[float]:
	var shipped: Vector2 = HudElements.ROWS[HudElements.PANEL][HudSlot.ROW_SIZE]
	var narrowest := HudElements.DOCK_MIN_SIZE.x - PANE_MARGINS

	return [narrowest, narrowest * 1.5, 300.0, shipped.x, 900.0, 2000.0]


## A fresh view of `width`, in the tree, with its layout done. A view that is
## not in the tree has no theme, so it would measure the wrong font.
func _fresh(width: float) -> void:
	if _view != null:
		_view.queue_free()

	_view = HelpView.new()
	_view.size = Vector2(width, HEIGHT)
	add_child(_view)
	await _settle()


## Layout runs on idle, and a label that wraps changes its height after it has
## its width. A few frames let that chain end.
func _settle() -> void:
	for _frame in 3:
		await get_tree().process_frame


func _labels() -> Array[Label]:
	var found: Array[Label] = []

	for row: BoxContainer in _view._rows.get_children():
		for cell: Label in row.get_children():
			found.append(cell)

	return found


## The old text had a line break in the middle of a sentence. No width can
## change where it falls. A `\n` is for a paragraph, so a full stop precedes it.
func _no_entry_breaks_a_sentence_by_hand() -> void:
	for entry: Array in HelpView.ENTRIES:
		var text := str(entry[1])
		var at := text.find("\n")

		while at != -1:
			_expect(at > 0 and text[at - 1] == ".",
				"%s: a line break follows a full stop" % entry[0])
			at = text.find("\n", at + 1)


## The bug: a fixed minimum width on the second column, plus the first column,
## was wider than a narrow pane. A scroll container with no horizontal scroll
## counts that width in its own minimum. Thus, the control panel stayed wide,
## and the right edge of the text was cut off.
func _the_content_asks_for_no_width() -> void:
	for width: float in _widths():
		await _fresh(width)

		var asked: float = _view._rows.get_combined_minimum_size().x
		_expect(asked <= HudElements.DOCK_MIN_SIZE.x - PANE_MARGINS,
			"at %d px the rows ask for %d px, less than the narrowest pane" % [
				width, asked])


func _every_label_stays_inside_the_pane() -> void:
	for width: float in _widths():
		await _fresh(width)

		var edge: float = _view._rows.get_global_rect().end.x

		for cell: Label in _labels():
			_expect(cell.get_global_rect().end.x <= edge + 0.5,
				"at %d px the label '%s' ends inside the pane" % [
					width, cell.text.left(16)])
			_expect(cell.get_line_count() <= cell.get_visible_line_count(),
				"at %d px the label '%s' shows every line" % [
					width, cell.text.left(16)])


## Proves that a label wraps at all, and that headless runs measure real
## glyphs. A dummy text server gives every label one line, and the cases above
## would pass for the wrong reason.
func _a_long_text_wraps_in_a_narrow_pane() -> void:
	await _fresh(_widths()[0])

	var most := 0

	for cell: Label in _labels():
		most = maxi(most, cell.get_line_count())

	_expect(most > 1, "in the narrowest pane a long text takes more than one line")


func _the_rows_stack_when_narrow_and_not_when_wide() -> void:
	var shipped: Vector2 = HudElements.ROWS[HudElements.PANEL][HudSlot.ROW_SIZE]

	await _fresh(_widths()[0])
	_expect(_all_rows(true), "the narrowest pane stacks every row")

	await _fresh(shipped.x)
	_expect(_all_rows(false), "the shipped pane keeps two columns")


## Whether every row has `vertical` as its value.
func _all_rows(vertical: bool) -> bool:
	for row: BoxContainer in _view._rows.get_children():
		if row.vertical != vertical:
			return false

	return true


## One view, resized down and up again. The gaps and the stack both follow, and
## a row that stacked comes back.
func _the_same_view_follows_a_resize_both_ways() -> void:
	await _fresh(2000.0)
	_expect(_all_rows(false), "the wide view has two columns")

	_view.size = Vector2(_widths()[0], HEIGHT)
	await _settle()
	_expect(_all_rows(true), "the same view stacks when it is made narrow")

	_view.size = Vector2(2000.0, HEIGHT)
	await _settle()
	_expect(_all_rows(false), "and has two columns again when it is made wide")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
