@tool
class_name FigureDock
extends FigureDockBase
## The panel of the figure workbench (DESIGN-0014 section 8.6). It has
## six tabs:
##
## - **Rig**: the bones, the sockets, and the slot table ([FigureRigPanel]).
## - **Body**: the parts of the body and their shape lists
##   ([FigureBodyPanel]).
## - **Colors**: the palette, and the colors of the character on the stands
##   ([FigureColorsPanel]). Phase W5.
## - **Families**: the shape of each item family with no art
##   ([FigureFamiliesPanel]). ENG-0011, step L5.
## - **Clips**: the clip library, the stances, and the clip lists
##   ([FigureClipsPanel]). Phase W2.
## - **Check**: the findings of the last check, and the budgets
##   ([FigureCheckPanel]). Phase W6.
##
## The worn look of an item is the work of the gear editor
## ([GearDock], DESIGN-0014 section 22). The Gear tab left this dock with
## it. The outfit bar stays, so the author dresses the figure for the
## reference body and for an NPC def.
##
## [FigureDockBase] holds the top strip, the bar, the outfit bar, the
## status box, the folds, and the two option files.

const SESSION_PATH := "user://blackout_figure_session.cfg"

## The titles of the tabs, in the order of the dock.
const TAB_RIG := "Rig"
const TAB_BODY := "Body"
const TAB_COLORS := "Colors"
const TAB_FAMILIES := "Families"
const TAB_CLIPS := "Clips"
const TAB_CHECK := "Check"

var _tabs := TabContainer.new()
var _rig_panel := FigureRigPanel.new()
var _body_panel := FigureBodyPanel.new()
var _colors_panel := FigureColorsPanel.new()
var _families_panel := FigureFamiliesPanel.new()
var _clips_panel := FigureClipsPanel.new()
var _check_panel := FigureCheckPanel.new()


func _init() -> void:
	name = "Figure"
	session_path = SESSION_PATH
	_build_strip("Open workbench", "Open gear editor")
	_build_bar(false)
	_tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(_tabs)
	_tabs.add_child(_scroll_page(TAB_RIG, _rig_panel))
	_tabs.add_child(_scroll_page(TAB_BODY, _body_panel))
	_tabs.add_child(_scroll_page(TAB_COLORS, _colors_panel))
	_tabs.add_child(_scroll_page(TAB_FAMILIES, _families_panel))
	_tabs.add_child(_scroll_page(TAB_CLIPS, _clips_panel))
	_tabs.add_child(_scroll_page(TAB_CHECK, _check_panel))
	_build_status_box()
	_connect_folds()


func rig_panel() -> FigureRigPanel:
	return _rig_panel


func body_panel() -> FigureBodyPanel:
	return _body_panel


func colors_panel() -> FigureColorsPanel:
	return _colors_panel


func families_panel() -> FigureFamiliesPanel:
	return _families_panel


func clips_panel() -> FigureClipsPanel:
	return _clips_panel


func check_panel() -> FigureCheckPanel:
	return _check_panel


## The title of the tab that the dock shows.
func shown_tab() -> String:
	return _tabs.get_tab_title(_tabs.current_tab)


## Show one tab by its title: a TAB_* constant.
func show_tab(title: String) -> void:
	for index in _tabs.get_tab_count():
		if _tabs.get_tab_title(index) == title:
			_tabs.current_tab = index


## Each fold of the Body tab and of the Families tab: "tab/title" -> the
## fold. The two tabs share the titles of the part editor, so the key
## carries the tab.
func folds() -> Dictionary:
	var found := {}

	for pair: Array in [[TAB_BODY, _body_panel.folds()],
			[TAB_FAMILIES, _families_panel.folds()]]:
		for title: String in pair[1]:
			found["%s/%s" % [pair[0], title]] = pair[1][title]

	return found
