class_name FigurePalette
extends RefCounted
## The palette of each figure: each named color, and each color role
## (DESIGN-0014 section 8.5, Phase W5).
##
## A surface of a part names a color role: `metal`, `trim`, `skin`. A worn
## look gives a role a named color: `copper`. This file gives a named color
## its color and its finish. Thus, one change of `rust` here changes each
## rusty item at one time.
##
## The game and the figure workbench read a palette with this class
## (requirement D6).
##
## ## The file
##
##     format    1
##     colors    named color -> {color, finish}
##     roles     color role -> named color
##     finishes  finish -> {metalness, roughness}
##
## `color` is six hex digits. `finish` is a finish of the `finishes` table,
## or of [MeshPalette]. The writer leaves out a matte finish, because matte
## is the default.
##
## `roles` gives each color role the named color that it has when a worn
## look gives it none.
##
## `finishes` gives each finish its two numbers (ENG-0011, step L4). A
## finish that the table does not have comes from [MeshPalette], so an old
## file reads. A new finish is one row here, and no code.
##
## ## One palette for every entity
##
## [member active] is the palette that each procedural mesh draws with:
## each family shape, each dropped item, each station. [MeshBuilder] asks
## [method shared] for the material of a part. The figure workbench puts
## the palette of its store here, so a change on the Colors tab reaches the
## stand of a family at one time. With no active palette, each named color
## and each finish comes from [MeshPalette], as before the file existed.
##
## ## The color of a surface
##
## [method named_for] finds the named color of one color role, in this
## order:
##
## 1. The colors of the figure: the skin and the hair of one character.
## 2. The color table of the worn look.
## 3. The `roles` table of this palette.
## 4. The role itself, as a named color. A shape can thus name `steel`.
##
## ## A fault does not stop the figure
##
## A named color that this palette does not have takes its color from
## [MeshPalette]. A family shape names its colors there. A name that the
## two do not have draws in the loud color of [MeshPalette], and the figure
## still draws (requirement D7).

## The newest format that this reader knows. It reads each older format.
const FORMAT := 1

## The name of the file in the figure directory.
const FILE_NAME := "palette.json"

## A palette is one file. This is its key in the file store of the
## workbench.
const KEY := "palette"

## A color of the file: six hex digits, in lower case.
const COLOR_PATTERN := "^[0-9a-f]{6}$"

## A name of a color or of a color role: a-z, 0-9, and _, with a letter
## first.
const NAME_PATTERN := "^[a-z][a-z0-9_]*$"

const DEFAULT_FINISH := MeshPalette.FINISH_MATTE

const KEY_FINISHES := "finishes"
const KEY_METALNESS := "metalness"
const KEY_ROUGHNESS := "roughness"

## The two numbers of a finish are each in this range.
const FINISH_LOW := 0.0
const FINISH_HIGH := 1.0

## The palette that every procedural mesh draws with, or null for the
## tables of [MeshPalette]. See the class comment.
static var active: FigurePalette = null

## An empty palette, for [method shared] with no active one.
static var _empty: FigurePalette = null

var data := {}

## Why the palette does not read, or "" for a palette that reads.
var error := ""


## The active palette, or an empty one. Each read of an empty palette
## falls back to [MeshPalette].
static func shared() -> FigurePalette:
	if active != null:
		return active

	if _empty == null:
		_empty = FigurePalette.new()

	return _empty


# ─── Reading and writing ────────────────────────────────────────────────────

## The palette of a parsed palette file. Check [member error] after.
static func from_data(parsed: Variant) -> FigurePalette:
	var palette := FigurePalette.new()

	if typeof(parsed) != TYPE_DICTIONARY or parsed.is_empty():
		palette.error = "a palette file must hold one JSON object"
		return palette

	var canonical: Dictionary = FigureJson.canonical(parsed)

	palette.error = _problem(canonical)

	if palette.error.is_empty():
		palette.data = _normal(canonical)

	return palette


## The palette of a palette file text. Check [member error] after.
static func from_text(text: String) -> FigurePalette:
	return from_data(FigureJson.parse(text))


## Read one palette file. Check [member error] after.
static func read_file(path: String) -> FigurePalette:
	var text := FileAccess.get_file_as_string(path)

	if text.is_empty():
		var refused := FigurePalette.new()

		refused.error = "cannot read %s" % path
		return refused

	return from_text(text)


## The canonical text. The same palette gives the same bytes.
func to_text() -> String:
	return FigureJson.to_text(data)


## Write the canonical text to an OS path. Makes the directory.
func write_file(path: String) -> Error:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())

	var file := FileAccess.open(path, FileAccess.WRITE)

	if file == null:
		return FileAccess.get_open_error()

	file.store_string(to_text())

	return OK


# ─── The facts of a palette ─────────────────────────────────────────────────

func key() -> String:
	return KEY


## Named color -> `{color, finish}`.
func colors() -> Dictionary:
	return data.get("colors", {})


## Color role -> named color.
func roles() -> Dictionary:
	return data.get("roles", {})


## The named colors, in sorted order.
func color_names() -> PackedStringArray:
	var names := PackedStringArray(colors().keys())

	names.sort()

	return names


## The color roles, in sorted order.
func role_names() -> PackedStringArray:
	var names := PackedStringArray(roles().keys())

	names.sort()

	return names


func has_color(color_name: String) -> bool:
	return colors().has(color_name)


## The six hex digits of one named color, or "" for a name that this
## palette does not have.
func hex_of(color_name: String) -> String:
	return colors().get(color_name, {}).get("color", "")


## The color of one named color. A name that this palette does not have
## takes its color from [MeshPalette].
func color_of(color_name: String) -> Color:
	if has_color(color_name):
		return Color(hex_of(color_name))

	return MeshPalette.color_of(color_name)


## The finish of one named color: a finish of this palette or of
## [MeshPalette].
func finish_of(color_name: String) -> String:
	return colors().get(color_name, {}).get("finish", DEFAULT_FINISH)


## Finish -> `{metalness, roughness}`, from the file only.
func finishes() -> Dictionary:
	return data.get(KEY_FINISHES, {})


## Each finish that a shape can name, in sorted order: the finishes of the
## file, and each finish of [MeshPalette] that the file does not have.
func finish_names() -> PackedStringArray:
	var names := PackedStringArray(finishes().keys())

	for finish: String in MeshPalette.FINISHES:
		if not finish in names:
			names.append(finish)

	names.sort()

	return names


## True for a finish of the file or of [MeshPalette].
func has_finish(finish: String) -> bool:
	return finishes().has(finish) or MeshPalette.FINISHES.has(finish)


## The `[metalness, roughness]` of one finish: from the file, then from
## [MeshPalette], then the matte values.
func finish_values(finish: String) -> Array:
	var row: Variant = finishes().get(finish)

	if typeof(row) == TYPE_DICTIONARY:
		return [float(row.get(KEY_METALNESS, 0.0)), float(row.get(KEY_ROUGHNESS, 0.0))]

	return MeshPalette.FINISHES.get(finish, MeshPalette.FINISHES[DEFAULT_FINISH])


## Each named color with one finish, in sorted order.
func colors_with_finish(finish: String) -> PackedStringArray:
	var found := PackedStringArray()

	for color_name: String in color_names():
		if finish_of(color_name) == finish:
			found.append(color_name)

	return found


## The named color of one color role on one worn look of one figure. See
## the class comment for the order. `look_colors` is the color table of the
## look. `figure_colors` is the table of the figure.
func named_for(role: String, look_colors: Dictionary, figure_colors := {}) -> String:
	if figure_colors.has(role):
		return figure_colors[role]

	if look_colors.has(role):
		return look_colors[role]

	return roles().get(role, role)


## A new material for one color and one finish of the active palette.
static func material_of(color: Color, finish: String) -> StandardMaterial3D:
	return shared().material_with(color, finish)


## A new material for one color and one finish of this palette. A new one
## for each call, as [method MeshPalette.material_for] gives: a tint of one
## then never tints another.
func material_with(color: Color, finish: String) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	var values := finish_values(finish)

	material.albedo_color = color
	material.metallic = values[0]
	material.roughness = values[1]
	# The material is ready for a glow, as each material of MeshPalette is.
	MeshGlow.prepare(material)

	return material


## A new material for one named color of this palette. `finish` is the
## finish of a shape that names one, or "" for the finish of the color.
func material_for(color_name: String, finish := "") -> StandardMaterial3D:
	return material_with(color_of(color_name),
		finish_of(color_name) if finish.is_empty() else finish)


## A new material for one color role of a part with no worn look: a family
## shape, or a part of [MeshBuilder] with no material of its own. The role
## gives its named color through the `roles` table, and the named color
## gives its color and its finish. A role that the table does not have is
## a named color itself, as [constant MeshPalette.STEEL] is.
func material_for_role(role: String, finish := "") -> StandardMaterial3D:
	var named := named_for(role, {})

	return material_for(named, finish)


## One text for the color and the finish of one named color. Two names
## with one text can share one material.
func material_key(color_name: String) -> String:
	return "%s|%s" % [color_of(color_name).to_html(false), finish_of(color_name)]


## One number for the content of this palette. A figure draws its parts
## again when the number changes.
func stamp() -> int:
	return data.hash()


# ─── The form of a palette file ─────────────────────────────────────────────

## Why a parsed palette file has a bad form, or "".
static func _problem(parsed: Dictionary) -> String:
	var format: Variant = parsed.get("format")

	if typeof(format) != TYPE_INT or format < 1:
		return "a palette file needs a format number"

	if format > FORMAT:
		return "format %d is newer than this reader (format %d)" % [format, FORMAT]

	if typeof(parsed.get("colors", {})) != TYPE_DICTIONARY \
			or typeof(parsed.get("roles", {})) != TYPE_DICTIONARY \
			or typeof(parsed.get(KEY_FINISHES, {})) != TYPE_DICTIONARY:
		return "colors, roles, and finishes must each be a table"

	var problem := _finishes_problem(parsed.get(KEY_FINISHES, {}))

	if problem.is_empty():
		problem = _colors_problem(parsed.get("colors", {}), parsed.get(KEY_FINISHES, {}))

	if problem.is_empty():
		problem = _roles_problem(parsed.get("roles", {}))

	return problem


## Why the colors table has a bad form, or "". `finish_table` is the
## finishes table of the same file. A finish of it is legal. A finish of
## [MeshPalette] is legal also.
static func _colors_problem(table: Dictionary, finish_table: Dictionary) -> String:
	var hex := RegEx.create_from_string(COLOR_PATTERN)
	var plain := RegEx.create_from_string(NAME_PATTERN)

	for color_name: String in table:
		var row: Variant = table[color_name]

		if plain.search(color_name) == null:
			return "the color name %s must use only a-z, 0-9, and _" % color_name

		if typeof(row) != TYPE_DICTIONARY or typeof(row.get("color")) != TYPE_STRING \
				or hex.search(row["color"]) == null:
			return "the color %s needs six hex digits in lower case" % color_name

		var finish: Variant = row.get("finish", DEFAULT_FINISH)

		if typeof(finish) != TYPE_STRING \
				or (not finish_table.has(finish) and not MeshPalette.FINISHES.has(finish)):
			return "the color %s has no finish %s" % [color_name, finish]

	return ""


## Why the finishes table has a bad form, or "". Each finish has a plain
## name. Each finish has two numbers in the range.
static func _finishes_problem(table: Dictionary) -> String:
	var plain := RegEx.create_from_string(NAME_PATTERN)

	for finish: String in table:
		var row: Variant = table[finish]

		if plain.search(finish) == null:
			return "the finish name %s must use only a-z, 0-9, and _" % finish

		if typeof(row) != TYPE_DICTIONARY:
			return "the finish %s needs a metalness and a roughness" % finish

		for number_key: String in [KEY_METALNESS, KEY_ROUGHNESS]:
			var number: Variant = row.get(number_key)

			if not typeof(number) in [TYPE_INT, TYPE_FLOAT] \
					or number < FINISH_LOW or number > FINISH_HIGH:
				return "the %s of the finish %s must be a number from %s to %s" % [number_key,
					finish, FINISH_LOW, FINISH_HIGH]

	return ""


static func _roles_problem(table: Dictionary) -> String:
	var plain := RegEx.create_from_string(NAME_PATTERN)

	for role: String in table:
		if plain.search(role) == null:
			return "the color role %s must use only a-z, 0-9, and _" % role

		if typeof(table[role]) != TYPE_STRING or table[role].is_empty():
			return "the color role %s needs a named color" % role

	return ""


## `parsed` as the writer gives it: the two tables, and no matte finish.
static func _normal(parsed: Dictionary) -> Dictionary:
	var out := parsed.duplicate(true)

	for table: String in ["colors", "roles", KEY_FINISHES]:
		if not out.has(table):
			out[table] = {}

	for color_name: String in out["colors"]:
		if out["colors"][color_name].get("finish", "") == DEFAULT_FINISH:
			out["colors"][color_name].erase("finish")

	return out
