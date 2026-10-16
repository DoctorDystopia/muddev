@tool
class_name FigureFamilyHandlers
extends RefCounted
## The handlers of the Families tab of the figure dock, and of the
## presentation fields of the Gear tab: the shape of a family, its model,
## and the offset, the turn, and the scale of a served model.
##
## A family row and a presentation row are both rows of one file, so the
## first change of each makes the file ([method FigureHistory.change_or_new]).

## The content of a look file with no row: the start of the first change.
const EMPTY_FAMILIES := {"format": FamilyLooks.FORMAT, FamilyLooks.KEY_FAMILIES: {},
	FamilyLooks.KEY_MODELS: {}}
const EMPTY_PRESENTATION := {"format": ModelPresentation.FORMAT,
	ModelPresentation.KEY_MODELS: {}}

var _context: FigureHandlerContext


func _init(context: FigureHandlerContext) -> void:
	_context = context


func connect_panel(panel: FigureFamiliesPanel) -> void:
	panel.family_chosen.connect(_on_family_chosen)
	panel.row_requested.connect(_on_family_shape_requested)
	panel.row_removed.connect(_on_family_shape_removed)
	panel.model_changed.connect(_on_family_model_changed)


## The presentation fields sit on the Gear tab, beside the row of the model.
func connect_presentation(panel: FigureGearPanel) -> void:
	panel.presentation_changed.connect(_on_presentation_changed)


## A picked family shows on the family stand, as the game draws it.
func _on_family_chosen(family: String) -> void:
	var bench := _context.bench()

	if bench != null:
		bench.show_entity("", family)


## "New shape from the fallback": the row of the family starts from the
## parts that it draws now, from the table or the generic block.
func _on_family_shape_requested(family: String) -> void:
	if family.is_empty():
		return

	_context.history().change_or_new(FigureStore.KIND_FAMILY, FigureStore.KIND_FAMILY,
		EMPTY_FAMILIES, "new shape for the family " + family,
		func(content: Dictionary) -> String:
			if content.get(FamilyLooks.KEY_FAMILIES, {}).has(family):
				return "The family %s has a row. Change its parts below." % family

			FamilyLooks.put_look(content, family, FamilyLooks.row_from_parts(
				FamilyShapes.parts_for(family)))
			return "")


## "Remove shape": the family draws its table again.
func _on_family_shape_removed(family: String) -> void:
	_context.history().change(FigureStore.KIND_FAMILY, FigureStore.KIND_FAMILY,
		"remove the shape of the family " + family, func(content: Dictionary) -> String:
			if not content.get(FamilyLooks.KEY_FAMILIES, {}).has(family):
				return "The family %s has no row in the file." % family

			FamilyLooks.remove_row(content, family)
			return "")


## The model that stands in for the whole family changed.
func _on_family_model_changed(family: String, model_key: String) -> void:
	if family.is_empty():
		return

	_context.history().change_or_new(FigureStore.KIND_FAMILY, FigureStore.KIND_FAMILY,
		EMPTY_FAMILIES, "set the model of the family " + family,
		func(content: Dictionary) -> String:
			FamilyLooks.put_model(content, family, model_key)
			return "")


## The offset, the turn, or the scale of a served model changed. One drag
## of a field is one entry. The look file writes at once, and the family
## stand draws the model again.
func _on_presentation_changed(model_key: String, offset: Vector3, turn: Vector3, scale: float,
		field: String) -> void:
	_context.history().change_or_new(FigureStore.KIND_PRESENTATION,
		FigureStore.KIND_PRESENTATION, EMPTY_PRESENTATION,
		"set the %s of the model %s" % [field, model_key],
		func(content: Dictionary) -> String:
			return ModelPresentation.set_model(content, model_key, offset, turn, scale), true)
