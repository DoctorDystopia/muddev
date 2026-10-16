class_name FigureJson
extends RefCounted
## The text form of each figure file: a rig, a worn look, and the palette
## (DESIGN-0014 section 8.1).
##
## One writer gives one text for one content (requirements D1 and D2):
##
## - The keys are in sorted order.
## - Each number is on its own line, so a git diff shows one line for each
##   changed number.
## - Each number keeps five digits after the point. A number that a gizmo
##   made then gives the same text on each save.
##
## ## A parsed number is a float
##
## The JSON parser of Godot gives each number back as a float. A count such
## as `format` then prints as `1.0` after one read and one write, and the
## bytes differ (DESIGN-0014 section 12.4). Thus [method canonical] gives
## each key of [constant INT_KEYS] back as an integer.

## The digits that a figure file keeps of each number.
const ROUND_STEP := 0.00001

const INDENT := "\t"

## The keys whose number is a count, not a measure.
const INT_KEYS := ["format", "segments", "rings"]

const VECTOR_SIZE := 3
const QUATERNION_SIZE := 4


## The text of one figure file.
static func to_text(data: Dictionary) -> String:
	return JSON.stringify(canonical(data), INDENT, true) + "\n"


## The content of a figure file text, in the canonical form. An empty
## dictionary for a text that is not one JSON object.
static func parse(text: String) -> Dictionary:
	# A parser object gives its error as a value. `JSON.parse_string` prints
	# the error of a bad text to the log.
	var parser := JSON.new()

	if parser.parse(text) != OK or typeof(parser.data) != TYPE_DICTIONARY:
		return {}

	return canonical(parser.data)


## A deep copy of `value` in the canonical form: each count is an integer,
## and each other number is a rounded float. `key` is the key that holds
## `value`. An array gives its key to each element.
static func canonical(value: Variant, key := "") -> Variant:
	match typeof(value):
		TYPE_DICTIONARY:
			var out := {}

			for name: Variant in value:
				out[str(name)] = canonical(value[name], str(name))

			return out
		TYPE_ARRAY:
			var items := []

			for item: Variant in value:
				items.append(canonical(item, key))

			return items
		TYPE_INT, TYPE_FLOAT:
			if key in INT_KEYS:
				return int(round(value))

			return _rounded(value)

	return value


## The vector of a `[x, y, z]` array, or `fallback` for another value.
static func vector3(value: Variant, fallback := Vector3.ZERO) -> Vector3:
	if not is_numbers(value, VECTOR_SIZE):
		return fallback

	return Vector3(value[0], value[1], value[2])


## The `[x, y, z]` array of a vector.
static func from_vector3(vector: Vector3) -> Array:
	return [_rounded(vector.x), _rounded(vector.y), _rounded(vector.z)]


## The rotation of a `[x, y, z, w]` array, or no rotation for another value.
static func quaternion(value: Variant) -> Quaternion:
	if not is_numbers(value, QUATERNION_SIZE):
		return Quaternion.IDENTITY

	return Quaternion(value[0], value[1], value[2], value[3]).normalized()


## The `[x, y, z, w]` array of a rotation.
static func from_quaternion(turn: Quaternion) -> Array:
	return [_rounded(turn.x), _rounded(turn.y), _rounded(turn.z), _rounded(turn.w)]


## True when `value` is an array of `count` numbers.
static func is_numbers(value: Variant, count: int) -> bool:
	if typeof(value) != TYPE_ARRAY or value.size() != count:
		return false

	for item: Variant in value:
		if typeof(item) != TYPE_INT and typeof(item) != TYPE_FLOAT:
			return false

	return true


## True when `value` is an array of strings.
static func is_strings(value: Variant) -> bool:
	if typeof(value) != TYPE_ARRAY:
		return false

	for item: Variant in value:
		if typeof(item) != TYPE_STRING:
			return false

	return true


## One number with the digits of a figure file. A negative zero becomes
## zero, so the text never holds `-0.0`.
static func _rounded(value: float) -> float:
	var kept := snappedf(value, ROUND_STEP)

	# A negative zero is equal to zero, so this test finds the two.
	return 0.0 if kept == 0.0 else kept
