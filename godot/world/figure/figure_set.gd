class_name FigureSet
extends RefCounted
## The figure set: each rig and each worn look of the game, as the model
## build serves them in one file (DESIGN-0014 section 8.1).
##
## The figure workbench writes one file for each rig and for each worn look.
## The model build puts the content of each one into `figure.json`, beside
## the served models. A new worn look then reaches a player with no client
## export, and the client makes one fetch for all of them (decision 3).
##
## ## The file
##
##     format   1
##     rigs     body type -> the content of its rig file
##     looks    asset key -> the content of its worn look file
##     palette  the content of the palette file (Phase W5)
##
## [FigureRig], [FigureLook], and [FigurePalette] read each entry. They are
## the readers of the workbench also (requirement D6). A file with no
## `palette` gives an empty palette, and each named color then comes from
## [MeshPalette].
##
## ## A fault does not stop the set
##
## An entry that does not read stays out of the set, and [member errors]
## names it. Each other entry reads (requirement D7).

## The newest format that this reader knows. It reads each older format.
const FORMAT := 1

## The name of the file in the served model tree.
const FILE_NAME := "figure.json"

## Body type -> [FigureRig].
var rigs := {}

## Asset key -> [FigureLook].
var looks := {}

## The palette of the set.
var palette := FigurePalette.new()

## One line for each entry that does not read.
var errors := PackedStringArray()

## Why the file does not read, or "" for a file that reads.
var error := ""


## The figure set of a parsed `figure.json`. Check [member error] after.
static func from_data(parsed: Variant) -> FigureSet:
	var figure_set := FigureSet.new()

	if typeof(parsed) != TYPE_DICTIONARY or parsed.is_empty():
		figure_set.error = "a figure set file must hold one JSON object"
		return figure_set

	var format: Variant = FigureJson.canonical(parsed.get("format"), "format")

	if typeof(format) != TYPE_INT or format < 1:
		figure_set.error = "a figure set file needs a format number"
	elif format > FORMAT:
		figure_set.error = "format %d is newer than this reader (format %d)" % [format, FORMAT]
	elif typeof(parsed.get("rigs", {})) != TYPE_DICTIONARY \
			or typeof(parsed.get("looks", {})) != TYPE_DICTIONARY \
			or typeof(parsed.get("palette", {})) != TYPE_DICTIONARY:
		figure_set.error = "rigs, looks, and palette must each be a table"
	else:
		figure_set._read(parsed.get("rigs", {}), parsed.get("looks", {}))
		figure_set._read_palette(parsed.get("palette", {}))

	return figure_set


## The figure set of a `figure.json` text. Check [member error] after.
static func from_text(text: String) -> FigureSet:
	return from_data(FigureJson.parse(text))


## Read one `figure.json` file. Check [member error] after.
static func read_file(path: String) -> FigureSet:
	var text := FileAccess.get_file_as_string(path)

	if text.is_empty():
		var refused := FigureSet.new()

		refused.error = "cannot read %s" % path
		return refused

	return from_text(text)


func _read(rig_table: Dictionary, look_table: Dictionary) -> void:
	for key: String in rig_table:
		var rig := FigureRig.from_data(rig_table[key])

		if _reads("rigs", key, rig.error, rig.key()):
			rigs[key] = rig

	for key: String in look_table:
		var look := FigureLook.from_data(look_table[key])

		if _reads("looks", key, look.error, look.key()):
			looks[key] = look


## A palette that does not read stays out of the set, and the set keeps its
## empty palette.
func _read_palette(content: Dictionary) -> void:
	if content.is_empty():
		return

	var read := FigurePalette.from_data(content)

	if read.error.is_empty():
		palette = read
	else:
		errors.append("palette: " + read.error)


## True for an entry that reads and has its key as its name. Each other
## entry gets a line in [member errors].
func _reads(kind: String, key: String, problem: String, own_key: String) -> bool:
	if problem.is_empty() and own_key != key:
		problem = "the key %s is not the name %s" % [own_key, key]

	if not problem.is_empty():
		errors.append("%s/%s: %s" % [kind, key, problem])

	return problem.is_empty()
