@tool
class_name FigurePaletteEdits
extends RefCounted
## The rules of the Colors tab of the figure workbench (DESIGN-0014 Phase
## W5): a new palette, the named colors, the finishes, the color roles, and
## the new name of a named color.
##
## Each routine changes the content of the palette file. The content is the
## dictionary of the `data` member of [FigurePalette]. The caller gives a
## copy, and the routine changes the copy. A routine that can refuse
## returns the reason, or "". Nothing here needs the editor.
##
## [method new_palette] makes the palette that the author starts from. The
## routines after it change a named color or a color role. A named color
## that a look or a color role names stays in the palette.
## [method rename_named_color] gives a named color a new name, and
## [method rename_color_in_look] makes one look follow.


# ─── The Colors tab ─────────────────────────────────────────────────────────

## The palette that the author starts from: each named color of
## [constant FigureShapes.PALETTE_COLORS] with its color of [MeshPalette],
## and each color role of a new body and of a new slot shape.
static func new_palette() -> FigurePalette:
	var colors := {}
	var roles: Dictionary = FigureShapes.BODY_COLORS.duplicate()

	roles.merge(FigureShapes.GEAR_COLORS)

	for color_name: String in FigureShapes.PALETTE_COLORS:
		colors[color_name] = {"color": MeshPalette.COLORS[color_name]}

	return FigurePalette.from_data({"format": FigurePalette.FORMAT, "colors": colors,
		"roles": roles, FigurePalette.KEY_FINISHES: table_finishes()})


## The finishes table of [MeshPalette] as a palette file holds it: finish
## -> `{metalness, roughness}`.
static func table_finishes() -> Dictionary:
	var finishes := {}

	for finish: String in MeshPalette.FINISHES:
		var values: Array = MeshPalette.FINISHES[finish]

		finishes[finish] = {FigurePalette.KEY_METALNESS: values[0],
			FigurePalette.KEY_ROUGHNESS: values[1]}

	return finishes


## Give a finish of a palette its two numbers. A finish that the palette
## does not have joins it.
static func set_finish(palette: Dictionary, finish: String, metalness: float,
		roughness: float) -> String:
	var problem := FigureRigEdits.name_problem(finish)

	if not problem.is_empty():
		return problem

	for number: float in [metalness, roughness]:
		if number < FigurePalette.FINISH_LOW or number > FigurePalette.FINISH_HIGH:
			return "The metalness and the roughness of a finish are each from %s to %s." % [
				FigurePalette.FINISH_LOW, FigurePalette.FINISH_HIGH]

	_palette_table(palette, FigurePalette.KEY_FINISHES)[finish] = {
		FigurePalette.KEY_METALNESS: metalness, FigurePalette.KEY_ROUGHNESS: roughness}

	return ""


## Take a finish out of a palette. A finish that a named color has stays.
## The matte finish stays, because a color with no finish has it.
static func remove_finish(palette: Dictionary, finish: String) -> String:
	if not palette.get(FigurePalette.KEY_FINISHES, {}).has(finish):
		return "The palette has no finish %s." % finish

	if finish == FigurePalette.DEFAULT_FINISH:
		return "The finish %s is the finish of each color with none. It stays." % finish

	var users := PackedStringArray()

	for color_name: String in palette.get("colors", {}):
		if palette["colors"][color_name].get("finish", FigurePalette.DEFAULT_FINISH) == finish:
			users.append(color_name)

	if not users.is_empty():
		return "%d color(s) have the finish %s: %s. Give each one another finish first." \
			% [users.size(), finish, ", ".join(users)]

	palette[FigurePalette.KEY_FINISHES].erase(finish)

	return ""


## The finishes that a finish list of the dock offers: each finish of the
## palette and of [MeshPalette], in sorted order.
static func finish_choices(palette: FigurePalette) -> Array:
	if palette == null:
		return Array(FigurePalette.new().finish_names())

	return Array(palette.finish_names())


## Give a named color of a palette its color. A name that the palette does
## not have joins it, with a matte finish.
static func set_named_color(palette: Dictionary, color_name: String, color: Color) -> String:
	var problem := FigureRigEdits.name_problem(color_name)

	if not problem.is_empty():
		return problem

	var row: Dictionary = _palette_table(palette, "colors").get(color_name, {})

	row["color"] = color.to_html(false)
	palette["colors"][color_name] = row

	return ""


## Give a named color of a palette its finish: a finish of [MeshPalette].
static func set_color_finish(palette: Dictionary, color_name: String,
		finish: String) -> String:
	if not palette.get("colors", {}).has(color_name):
		return "The palette has no color %s." % color_name

	if not palette.get(FigurePalette.KEY_FINISHES, {}).has(finish) \
			and not MeshPalette.FINISHES.has(finish):
		return "No finish has the name %s." % finish

	# The writer leaves out a matte finish, so the content has no key for it.
	if finish == FigurePalette.DEFAULT_FINISH:
		palette["colors"][color_name].erase("finish")
	else:
		palette["colors"][color_name]["finish"] = finish

	return ""


## Take a named color out of a palette. A color that a color role or a
## worn look names stays. `looks` is key -> [FigureLook].
static func remove_named_color(palette: Dictionary, color_name: String,
		looks: Dictionary) -> String:
	if not palette.get("colors", {}).has(color_name):
		return "The palette has no color %s." % color_name

	for role: String in palette.get("roles", {}):
		if palette["roles"][role] == color_name:
			return "The color role %s has the color %s. Give the role another color first." \
				% [role, color_name]

	var users := looks_with_color(looks, color_name)

	if not users.is_empty():
		return "%d look(s) name the color %s: %s. Give each one another color first." \
			% [users.size(), color_name, ", ".join(users)]

	palette["colors"].erase(color_name)

	return ""


## Give a named color of a palette a new name. Each color role of the
## palette that has the color follows. [method rename_color_in_look] does
## the same for one worn look.
static func rename_named_color(palette: Dictionary, color_name: String,
		new_name: String) -> String:
	var problem := FigureRigEdits.name_problem(new_name)

	if not problem.is_empty():
		return problem

	if not palette.get("colors", {}).has(color_name):
		return "The palette has no color %s." % color_name

	if palette["colors"].has(new_name):
		return "The palette has a color with the name %s." % new_name

	if palette.get("roles", {}).has(new_name):
		return "The palette has a color role with the name %s." % new_name

	palette["colors"][new_name] = palette["colors"][color_name]
	palette["colors"].erase(color_name)

	for role: String in palette.get("roles", {}):
		if palette["roles"][role] == color_name:
			palette["roles"][role] = new_name

	return ""


## Give each use of one named color in a worn look the new name of that
## color. Returns true when the look changed.
##
## A look names a color in its color table. A shape names a color when its
## `color` is no color role: `roles` names each role of the palette, and
## the color table of the look has the others.
static func rename_color_in_look(look: Dictionary, color_name: String, new_name: String,
		roles := PackedStringArray()) -> bool:
	var changed := false
	var colors: Dictionary = look.get("colors", {})

	for role: String in colors:
		if colors[role] == color_name:
			colors[role] = new_name
			changed = true

	if colors.has(color_name) or color_name in roles:
		return changed

	for part: Dictionary in look.get("parts", []):
		for shape: Dictionary in part.get("shapes", []):
			if shape.get("color", "") == color_name:
				shape["color"] = new_name
				changed = true

	return changed


## Give a color role of a palette its named color: the color that the role
## has on a look that gives it none. A role that the palette does not have
## joins it.
static func set_role_color(palette: Dictionary, role: String, color_name: String) -> String:
	var problem := FigureRigEdits.name_problem(role)

	if not problem.is_empty():
		return problem

	if not palette.get("colors", {}).has(color_name):
		return "The palette has no color %s." % color_name

	_palette_table(palette, "roles")[role] = color_name

	return ""


## Take a color role out of a palette. A role stays while a shape of a look
## names it and the color table of that look gives it no color.
static func remove_role(palette: Dictionary, role: String, looks: Dictionary) -> String:
	if not palette.get("roles", {}).has(role):
		return "The palette has no color role %s." % role

	var users := looks_needing_role(looks, role)

	if not users.is_empty():
		return "%d look(s) take the color of the color role %s from the palette: %s." \
			% [users.size(), role, ", ".join(users)]

	palette["roles"].erase(role)

	return ""


## The key of each look that names one named color, in sorted order. A look
## names a color in its color table, or as the color of a shape with no
## entry in that table.
static func looks_with_color(looks: Dictionary, color_name: String) -> PackedStringArray:
	var found := PackedStringArray()

	for look_key: String in looks:
		var look: FigureLook = looks[look_key]
		var direct := color_name in _shape_colors(look) and not look.colors().has(color_name)

		if color_name in look.colors().values() or direct:
			found.append(look_key)

	found.sort()

	return found


## The key of each look that takes the color of one color role from the
## palette, in sorted order: a shape names the role, and the color table of
## the look does not.
static func looks_needing_role(looks: Dictionary, role: String) -> PackedStringArray:
	var found := PackedStringArray()

	for look_key: String in looks:
		var look: FigureLook = looks[look_key]

		if role in _shape_colors(look) and not look.colors().has(role):
			found.append(look_key)

	found.sort()

	return found


## The `color` of each shape of a look.
static func _shape_colors(look: FigureLook) -> Array:
	var found := []

	for part: Dictionary in look.parts():
		for shape: Dictionary in part.get("shapes", []):
			if shape.has("color") and not shape["color"] in found:
				found.append(shape["color"])

	return found


## The names that a color list of the dock offers: each named color of the
## palette, in sorted order. With no palette, or with an empty one, the
## list has each color of [MeshPalette].
static func color_choices(palette: FigurePalette) -> Array:
	var names: Array = [] if palette == null else Array(palette.color_names())

	if names.is_empty():
		names = MeshPalette.COLORS.keys()
		names.sort()

	return names


## One table of a palette. A palette with no such table gets an empty one.
static func _palette_table(palette: Dictionary, table: String) -> Dictionary:
	if not palette.has(table):
		palette[table] = {}

	return palette[table]
