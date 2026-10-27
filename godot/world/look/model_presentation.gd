@tool
class_name ModelPresentation
extends RefCounted
## The display choice of each served model as a look file:
## `presentation.json` under `res://world/look/` (ENG-0011, step L6). It
## holds the offset, the turn, and the scale of a model by its asset key.
##
## [ModelRegistry] asks this file first, and it keeps its old table
## ([constant ModelRegistry.PRESENTATION]) as the fallback. A model with no
## row draws as the file is built.
##
## ## The file
##
##     format  1
##     models  asset key -> {offset, turn, scale}
##
## `offset` is `[x, y, z]` in normalised units, after the centring. `turn`
## is `[x, y, z]` in degrees, in the order of [member Node3D.rotation]. The
## file holds degrees, because the author types them. `scale` is a
## multiplier on the unit box. Each key is optional.
##
## The Gear tab of the figure workbench writes the file. The Python guard
## checks that each key names a model that the build can produce.

const PATH := LookFile.DIRECTORY + "/presentation.json"

const FORMAT := 1

## The key of the file in the file store of the workbench. It is the name
## of the file also.
const KEY := "presentation"

const FILE_NAME := KEY + ".json"

const KEY_MODELS := "models"
const KEY_OFFSET := "offset"
const KEY_TURN := "turn"
const KEY_SCALE := "scale"

## The keys of an entry of [constant ModelRegistry.PRESENTATION].
const ENTRY_OFFSET := "offset"
const ENTRY_ROTATION := "rotation"
const ENTRY_SCALE := "scale"

## The smallest scale that a row can hold.
const SCALE_LOW := 0.01

var data := {}

## Why the file does not read, or "" for a file that reads.
var error := ""


# ─── Reading and writing ────────────────────────────────────────────────────

## The presentation of a parsed file. Check [member error] after.
static func from_data(parsed: Variant) -> ModelPresentation:
	var presentation := ModelPresentation.new()

	if typeof(parsed) != TYPE_DICTIONARY or parsed.is_empty():
		presentation.error = "a presentation file must hold one JSON object"
		return presentation

	var canonical: Dictionary = FigureJson.canonical(parsed)

	presentation.error = _problem(canonical)

	if presentation.error.is_empty():
		presentation.data = _normal(canonical)

	return presentation


static func from_text(text: String) -> ModelPresentation:
	return from_data(FigureJson.parse(text))


## Read one presentation file. Check [member error] after.
static func read_file(path: String) -> ModelPresentation:
	var text := FileAccess.get_file_as_string(path)

	if text.is_empty():
		var refused := ModelPresentation.new()

		refused.error = "cannot read %s" % path
		return refused

	return from_text(text)


func to_text() -> String:
	return FigureJson.to_text(data)


## Write the canonical text to a path. Makes the directory.
func write_file(path: String) -> Error:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(path).get_base_dir())

	return LookFile.write(path, data)


# ─── The facts of the file ──────────────────────────────────────────────────

func key() -> String:
	return KEY


## Asset key -> `{offset, turn, scale}`.
func models() -> Dictionary:
	return data.get(KEY_MODELS, {})


func has_model(asset_key: String) -> bool:
	return models().has(asset_key)


## The row of one model, or an empty dictionary.
func row_of(asset_key: String) -> Dictionary:
	return models().get(asset_key, {})


# ─── The rows as the registry reads them ────────────────────────────────────

## The entry of [constant ModelRegistry.PRESENTATION] for one row of the
## file: the offset as a [Vector3], the rotation as a [Vector3] of radians,
## and the scale as a float. A key that the row lacks is not in the entry.
static func entry_of(row: Variant) -> Dictionary:
	var entry := {}

	if typeof(row) != TYPE_DICTIONARY:
		return entry

	if FigureJson.is_numbers(row.get(KEY_OFFSET), FigureJson.VECTOR_SIZE):
		entry[ENTRY_OFFSET] = FigureJson.vector3(row[KEY_OFFSET])

	if FigureJson.is_numbers(row.get(KEY_TURN), FigureJson.VECTOR_SIZE):
		var degrees := FigureJson.vector3(row[KEY_TURN])

		entry[ENTRY_ROTATION] = Vector3(deg_to_rad(degrees.x), deg_to_rad(degrees.y),
			deg_to_rad(degrees.z))

	if typeof(row.get(KEY_SCALE)) in [TYPE_INT, TYPE_FLOAT]:
		entry[ENTRY_SCALE] = float(row[KEY_SCALE])

	return entry


## The row of the file for one entry of [constant ModelRegistry.PRESENTATION].
static func row_of_entry(entry: Dictionary) -> Dictionary:
	var rotation: Vector3 = entry.get(ENTRY_ROTATION, Vector3.ZERO)

	return row_from(entry.get(ENTRY_OFFSET, Vector3.ZERO),
		Vector3(rad_to_deg(rotation.x), rad_to_deg(rotation.y), rad_to_deg(rotation.z)),
		float(entry.get(ENTRY_SCALE, 1.0)))


## A row of the file. `turn` is in degrees.
static func row_from(offset: Vector3, turn: Vector3, scale: float) -> Dictionary:
	return {KEY_OFFSET: FigureJson.from_vector3(offset), KEY_TURN: FigureJson.from_vector3(turn),
		KEY_SCALE: scale}


## The row of the file for one model, read from the cache of [LookFile].
## An empty dictionary for no row.
static func file_row(asset_key: String) -> Dictionary:
	var model_rows: Variant = LookFile.read(PATH).get(KEY_MODELS, {})

	if typeof(model_rows) != TYPE_DICTIONARY:
		return {}

	var row: Variant = model_rows.get(asset_key, {})

	return row if typeof(row) == TYPE_DICTIONARY else {}


## The row that the Gear tab shows for one model: the row of the file, or
## the entry of the table, or the identity. `content` is the content of a
## presentation file, or empty for the cache of [LookFile].
static func shown_row(asset_key: String, content := {}) -> Dictionary:
	var row: Variant = content.get(KEY_MODELS, {}).get(asset_key, {}) if not content.is_empty() \
		else file_row(asset_key)
	var full := row_of_entry(ModelRegistry.PRESENTATION.get(asset_key, {}))

	if typeof(row) == TYPE_DICTIONARY:
		full.merge(row, true)

	return full


## Give one model its row in `content`: the content of a presentation file.
static func set_model(content: Dictionary, asset_key: String, offset: Vector3, turn: Vector3,
		scale: float) -> String:
	if asset_key.is_empty():
		return "The row has no model."

	if scale < SCALE_LOW:
		return "The scale must be at least %s." % SCALE_LOW

	if not content.has(KEY_MODELS):
		content[KEY_MODELS] = {}

	content["format"] = FORMAT
	content[KEY_MODELS][asset_key] = row_from(offset, turn, scale)

	return ""


# ─── The form of a presentation file ────────────────────────────────────────

static func _problem(parsed: Dictionary) -> String:
	var format: Variant = parsed.get("format")

	if typeof(format) != TYPE_INT or format < 1:
		return "a presentation file needs a format number"

	if format > FORMAT:
		return "format %d is newer than this reader (format %d)" % [format, FORMAT]

	if typeof(parsed.get(KEY_MODELS, {})) != TYPE_DICTIONARY:
		return "models must be a table"

	for asset_key: String in parsed.get(KEY_MODELS, {}):
		var problem := _row_problem(asset_key, parsed[KEY_MODELS][asset_key])

		if not problem.is_empty():
			return problem

	return ""


static func _row_problem(asset_key: String, row: Variant) -> String:
	if typeof(row) != TYPE_DICTIONARY:
		return "the model %s needs a table" % asset_key

	for vector_key: String in [KEY_OFFSET, KEY_TURN]:
		if row.has(vector_key) and not FigureJson.is_numbers(row[vector_key], FigureJson.VECTOR_SIZE):
			return "the %s of the model %s must be [x, y, z]" % [vector_key, asset_key]

	if row.has(KEY_SCALE):
		if not typeof(row[KEY_SCALE]) in [TYPE_INT, TYPE_FLOAT] or row[KEY_SCALE] < SCALE_LOW:
			return "the scale of the model %s must be a number of at least %s" % [asset_key,
				SCALE_LOW]

	return ""


static func _normal(parsed: Dictionary) -> Dictionary:
	var out := parsed.duplicate(true)

	if not out.has(KEY_MODELS):
		out[KEY_MODELS] = {}

	return out
