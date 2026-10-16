@tool
class_name FigureCheckPanel
extends VBoxContainer
## The Check tab of the figure workbench (DESIGN-0014 section 8.6, Phase
## W6): the findings of the last check, and the budgets.
##
## "Check the figure files" runs each rule of [FigureChecks]. The list then
## has one row for each finding. A click on a row selects the file of the
## finding in its tab: the row of a worn look, a bone, or a clip.
##
## ## The budgets
##
## A budget is a limit that the author sets: the triangles of a worn look
## of one slot, the triangles of a body, and the triangles and the draws of
## a dressed figure. The slot table gives one slot another number. A field
## with 0 there takes the number of each slot.
##
## The budgets are an option of the workbench, and no figure file. The dock
## keeps them in its options file.
##
## This panel runs no check itself. Each control sends a signal, and the
## plugin acts.

signal check_requested
signal finding_chosen(finding: Dictionary)
signal budgets_changed(budgets: Dictionary)

const FINDING_LIST_HEIGHT := 260.0

## The highest budget that a field takes.
const BUDGET_HIGH := 100000.0

const HELP := "A figure file with a fault still draws, with a part that is not " \
	+ "there. The check finds each such fault. A note is no fault."

const NO_CHECK := "No check ran in this session."

## The budget fields with one number, in the order of the tab: the key of
## [FigureChecks], and the label.
const BUDGET_FIELDS := [
	[FigureChecks.BUDGET_SLOT, "Triangles of a worn look of each slot"],
	[FigureChecks.BUDGET_BODY, "Triangles of a body"],
	[FigureChecks.BUDGET_TRIANGLES, "Triangles of a dressed figure"],
	[FigureChecks.BUDGET_DRAWS, "Draws of a dressed figure"],
]

var _summary := Label.new()
var _findings := ItemList.new()
var _notes := CheckBox.new()
var _slots := GridContainer.new()

## Budget key -> the field of that budget.
var _fields := {}

## Slot -> the field of that slot.
var _slot_fields := {}

## Each finding of the last check.
var _found: Array[Dictionary] = []

## The findings of the rows of the list.
var _shown: Array[Dictionary] = []

## The slots of the slot table, as one text.
var _shown_slots := ""


func _init() -> void:
	add_child(FigureFields.label(HELP))
	add_child(FigureFields.button("Check the figure files", check_requested.emit))
	_summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_summary.text = NO_CHECK
	add_child(_summary)
	_notes.text = "Show each note also"
	_notes.button_pressed = true
	_notes.toggled.connect(func(_on: bool) -> void: _fill())
	add_child(_notes)
	_findings.custom_minimum_size.y = FINDING_LIST_HEIGHT
	_findings.auto_height = false
	_findings.item_selected.connect(func(row: int) -> void:
		finding_chosen.emit(_shown[row]))
	add_child(_findings)
	_build_budget_rows()


## Show the findings of a check.
func set_findings(found: Array[Dictionary]) -> void:
	var faults := FigureChecks.faults_of(found).size()

	_found = found
	_summary.text = "%d finding(s), %d note(s)." % [faults, found.size() - faults]

	if found.is_empty():
		_summary.text = "The check found nothing."

	_fill()


## The findings of the last check.
func findings() -> Array[Dictionary]:
	return _found


## Show a budget table. `slots` names each slot of the slot table. The
## panel sends no signal.
func set_budgets(budgets: Dictionary, slots: PackedStringArray) -> void:
	var full := FigureChecks.with_defaults(budgets)

	_fill_slots(slots)

	for budget_key: String in _fields:
		(_fields[budget_key] as SpinBox).set_value_no_signal(full[budget_key])

	for slot: String in _slot_fields:
		(_slot_fields[slot] as SpinBox).set_value_no_signal(
			full[FigureChecks.BUDGET_SLOTS].get(slot, 0))


## The budget table of the fields.
func budgets() -> Dictionary:
	var table := {FigureChecks.BUDGET_SLOTS: {}}

	for budget_key: String in _fields:
		table[budget_key] = int((_fields[budget_key] as SpinBox).value)

	for slot: String in _slot_fields:
		var triangles := int((_slot_fields[slot] as SpinBox).value)

		if triangles >= 1:
			table[FigureChecks.BUDGET_SLOTS][slot] = triangles

	return table


# ─── Building the panel ─────────────────────────────────────────────────────

func _build_budget_rows() -> void:
	add_child(FigureFields.label("Budgets"))

	for pair: Array in BUDGET_FIELDS:
		_fields[pair[0]] = _new_budget_field(1.0)
		add_child(FigureFields.label(pair[1]))
		add_child(_fields[pair[0]])

	_slots.columns = 2
	add_child(FigureFields.label("Triangles of one slot (0 is the number of each slot)"))
	add_child(_slots)


func _new_budget_field(low: float) -> SpinBox:
	var field := FigureFields.spin(low, BUDGET_HIGH, 1.0)

	field.value_changed.connect(func(_value: float) -> void:
		budgets_changed.emit(budgets()))

	return field


## Give the slot table one row for each slot. A table with the same slots
## keeps its rows.
func _fill_slots(slots: PackedStringArray) -> void:
	if ",".join(slots) == _shown_slots:
		return

	_shown_slots = ",".join(slots)
	_slot_fields.clear()

	for child: Node in _slots.get_children():
		_slots.remove_child(child)
		child.queue_free()

	for slot: String in slots:
		_slot_fields[slot] = _new_budget_field(0.0)
		_slots.add_child(FigureFields.cell_label(slot))
		_slots.add_child(_slot_fields[slot])


## Fill the list from the findings, with or with no note.
func _fill() -> void:
	_findings.clear()
	_shown.clear()

	for finding: Dictionary in _found:
		if FigureChecks.is_note(finding) and not _notes.button_pressed:
			continue

		_shown.append(finding)
		_findings.add_item(FigureChecks.describe(finding))
		_findings.set_item_tooltip(_findings.item_count - 1, FigureChecks.describe(finding))
