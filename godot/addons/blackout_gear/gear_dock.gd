@tool
class_name GearDock
extends FigureDockBase
## The panel of the gear editor (DESIGN-0014 section 22): the worn look of
## each item, in three zones.
##
## 1. **The items** ([GearItemsPanel]): the item catalog with its filters.
##    A picked row dresses each stand in the item.
## 2. **The part editor** ([PartEditor]): a tree of the parts of the look
##    and their shapes, a toolbar, and the fields of the selected part and
##    shape. The basic tools of a shape list live here.
## 3. **The look** ([GearLookPanel]): the actions of the look, its colors,
##    its hide list, and its model, in four folds.
##
## The bar above the zones has the body type, a clip list with the play
## bar, the budget line, the line of the selected item, and the outfit
## bar. The author plays a clip to see the item move with the figure, and
## dresses the other slots to see what the item meets.
##
## The dock changes no figure file itself. Each control sends a signal,
## and the plugin acts. [FigureDockBase] holds the top strip, the bar, the
## status box, the folds, and the two option files. The session file of
## this dock is its own, so the gear editor opens on the row of the last
## session.

const SESSION_PATH := "user://blackout_gear_session.cfg"

var _items := GearItemsPanel.new()
var _editor := PartEditor.new()
var _look := GearLookPanel.new()


func _init() -> void:
	name = "Gear"
	session_path = SESSION_PATH
	_build_strip("Open gear editor", "Open figure workbench")
	_build_bar(true)

	var column := VBoxContainer.new()

	for zone: Control in [_items, _editor, _look]:
		column.add_child(zone)

	add_child(_scroll_page("Gear", column))
	_build_status_box()
	_connect_folds()


func items_panel() -> GearItemsPanel:
	return _items


func part_editor() -> PartEditor:
	return _editor


func look_panel() -> GearLookPanel:
	return _look


## Each fold of the part editor and of the look panel: title -> the fold.
func folds() -> Dictionary:
	var found := _editor.folds()

	found.merge(_look.folds())

	return found
