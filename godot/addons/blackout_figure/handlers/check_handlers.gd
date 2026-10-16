@tool
class_name FigureCheckHandlers
extends RefCounted
## The handlers of the Check tab of the figure dock: the check, the
## budgets, and a click on a finding.
##
## "Check the figure files" runs [FigureChecks] on the store. A click on a
## finding shows its file in its tab. The budgets of the Check tab are an
## option of the dock, and they make no undo entry. The check also runs
## by itself, a short time after each change of a file, so the findings
## never go stale (ENG-0011, item 13). The plugin owns that timer, and it
## calls [method run_checks].

var _context: FigureHandlerContext

## The handlers of the Rig tab: a finding on a bone selects the bone.
var _rig: FigureRigHandlers

## The handlers of the Clips tab: a finding on a clip shows the clip.
var _clips: FigureClipHandlers


func _init(context: FigureHandlerContext, rig: FigureRigHandlers,
		clips: FigureClipHandlers) -> void:
	_context = context
	_rig = rig
	_clips = clips


func connect_panel(panel: FigureCheckPanel) -> void:
	panel.check_requested.connect(_on_check_requested)
	panel.finding_chosen.connect(_on_finding_chosen)
	panel.budgets_changed.connect(_on_budgets_changed)


## "Check the figure files": run each rule, and show the findings.
func _on_check_requested() -> void:
	run_checks(true)


## Run each rule, and fill the list of the Check tab. With `announce`, the
## status box gives the counts. The check after a change does not announce,
## so the status of the change stays.
func run_checks(announce: bool) -> void:
	var bench := _context.bench()

	if bench == null:
		return

	var found := bench.run_checks(_context.budgets())
	var faults := FigureChecks.faults_of(found).size()

	_context.dock().check_panel().set_findings(found)

	if announce:
		_context.status("The check found %d finding(s) and %d note(s)."
			% [faults, found.size() - faults])


## A budget of the Check tab changed: keep it, and show the budget line.
func _on_budgets_changed(budgets: Dictionary) -> void:
	_context.set_budgets(budgets)
	_context.dock().save_budgets(budgets)

	if _context.bench() != null:
		_context.refresh_cost()


## A click on a finding: show the file of the finding in its tab, and
## select the part, the bone, or the clip that the finding names.
func _on_finding_chosen(finding: Dictionary) -> void:
	if _context.bench() == null:
		return

	var key: String = finding["key"]
	var part: String = finding["part"]

	_context.status(FigureChecks.describe(finding))

	match finding["kind"]:
		FigureStore.KIND_RIG:
			_show_rig_finding(key, part)
		FigureStore.KIND_LOOK:
			_show_look_finding(key, part)
		FigureChecks.KIND_ITEM:
			_show_gear_row(key, "")
		FigureChecks.KIND_CLIP:
			_context.show_tab(FigureDock.TAB_CLIPS)
			_context.dock().clips_panel().select_clip(key)
			_clips.on_clip_chosen(key)
		FigureStore.KIND_STANCES:
			_context.show_tab(FigureDock.TAB_CLIPS)
			_context.dock().clips_panel().select_stance(part.get_slice("/", 0))
		FigureStore.KIND_PALETTE:
			_context.show_tab(FigureDock.TAB_COLORS)


## Show the Rig tab on one body type, with one bone selected.
func _show_rig_finding(body_key: String, bone: String) -> void:
	var dock := _context.dock()

	if dock.active_body() != body_key:
		dock.select_body(body_key)
		_context.refresh_panels()

	_context.show_tab(FigureDock.TAB_RIG)
	dock.rig_panel().select_bone(bone)
	_rig.on_bone_chosen(dock.rig_panel().selected_bone())


## Show the worn look of a finding: a body or a kit part on the Body tab,
## and each other look on its row of the Gear tab.
func _show_look_finding(look_key: String, part: String) -> void:
	var bench := _context.bench()
	var dock := _context.dock()
	var look: FigureLook = bench.store.looks.get(look_key)
	var is_body := bench.store.has(FigureStore.KIND_RIG, look_key)

	if look == null:
		return

	if not is_body and look.kit().is_empty():
		_show_gear_row(look_key, part)
		return

	if is_body:
		dock.select_body(look_key)

	dock.body_panel().edit_kit("" if is_body else look_key)
	_context.show_tab(FigureDock.TAB_BODY)
	_context.refresh_panels()
	dock.body_panel().select_part(part)
	_context.select_part(look_key, dock.body_panel().selected_part())


## Show one row of the Gear tab, and dress each stand in it. A key that is
## no row of the item catalog shows no row, and the status box has the
## finding.
func _show_gear_row(key: String, part: String) -> void:
	var gear := _context.dock().gear_panel()

	_context.show_tab(FigureDock.TAB_GEAR)
	gear.select_row(key)

	if gear.selected_key() != key:
		return

	_context.bench().wear(gear.selected_slot(), key)
	gear.parts_panel().select_part(part)
	_context.refresh_cost()
	_context.select_part(key, gear.parts_panel().selected_part())
