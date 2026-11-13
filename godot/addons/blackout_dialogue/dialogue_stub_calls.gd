@tool
class_name DialogueStubCalls
extends RefCounted
## Finds each yes or no query that a dialogue script asks (DESIGN-0017), so
## the test scene can show one switch for each of them.
##
## A query is a call of the dialogue vocabulary whose answer [DialogueStub]
## gives as a flag, for example `quest.is_active("augmentation_intro")`.
## Only a call with literal arguments is in the list, because the switch
## needs the exact text of the call.
##
## The input is the `lines` of a compiled dialogue, in the format of the
## Dialogue Manager compiler. `expressions.py` in the game reads the same
## token trees.

const FIELD_EXPRESSION := "expression"

## The fields of a line that hold one expression.
const EXPRESSION_FIELDS: Array[String] = ["condition", "mutation"]

## The fields of a line that hold a list of `{expression}`.
const REPLACEMENT_FIELDS: Array[String] = ["text_replacements", "character_replacements"]

const FIELD_CASES := "cases"

const TOKEN_VARIABLE := "variable"
const TOKEN_DOT := "dot"
const TOKEN_FUNCTION := "function"
const TOKEN_GROUP := "group"
const TOKEN_PARENS_CLOSE := "parens_close"

## The token types that carry their own value.
const LITERAL_TOKENS: Array[String] = ["string", "number", "bool"]


## The call text of each yes or no query in the lines of one compiled
## dialogue, in the order of the script, with no call two times.
static func flag_calls(lines: Dictionary) -> Array[String]:
	var found: Array[String] = []
	var line_ids := lines.keys()

	line_ids.sort_custom(func(a: String, b: String) -> bool: return a.to_float() < b.to_float())

	for line_id: String in line_ids:
		for tokens: Array in _expressions_of(lines[line_id]):
			_collect(tokens, found)

	return found


## Each token list of one line.
static func _expressions_of(line: Dictionary) -> Array[Array]:
	var found: Array[Array] = []

	for field: String in EXPRESSION_FIELDS:
		_append_expression(line.get(field), found)

	for case: Variant in line.get(FIELD_CASES, []):
		_append_expression(case.get("condition"), found)

	for field: String in REPLACEMENT_FIELDS:
		for replacement: Variant in line.get(field, []):
			_append_expression(replacement, found)

	return found


static func _append_expression(holder: Variant, found: Array[Array]) -> void:
	if holder is Dictionary and holder.get(FIELD_EXPRESSION) is Array:
		found.append(holder[FIELD_EXPRESSION])


## Walk one token list. Add each flag call with literal arguments to `found`.
static func _collect(tokens: Array, found: Array[String]) -> void:
	for index: int in tokens.size():
		var token: Dictionary = tokens[index]
		var type: String = token.get("type", "")

		if type == TOKEN_GROUP:
			_collect(token.get("value", []), found)
		elif type == TOKEN_FUNCTION:
			for argument: Variant in token.get("value", []):
				_collect(argument, found)

			_add_call(tokens, index, found)


## The token at `index` is a function. If a namespace and a dot stand before
## it, and the stub answers the name as a flag, add its call text.
static func _add_call(tokens: Array, index: int, found: Array[String]) -> void:
	if index < 2 or tokens[index - 1].get("type") != TOKEN_DOT \
			or tokens[index - 2].get("type") != TOKEN_VARIABLE:
		return

	var function: Dictionary = tokens[index]
	var name := "%s.%s" % [tokens[index - 2].get("value"), function.get("function")]

	if DialogueStub.KINDS.get(name) != DialogueStub.KIND_FLAG:
		return

	var arguments := []

	for argument: Variant in function.get("value", []):
		var literal := _literal_of(argument)

		if literal.is_empty():
			if _has_content(argument):
				return

			continue

		arguments.append(literal[0])

	var asked := DialogueStub.call_text(name, arguments)

	if not found.has(asked):
		found.append(asked)


## The tokens of one argument without the closing bracket that the compiler
## leaves in the last argument.
static func _content_of(argument: Array) -> Array:
	return argument.filter(
		func(token: Dictionary) -> bool: return token.get("type") != TOKEN_PARENS_CLOSE)


static func _has_content(argument: Array) -> bool:
	return not _content_of(argument).is_empty()


## `[value]` for an argument that is one literal, and `[]` for each other
## argument. An Array, so a literal `false` is not "no literal".
static func _literal_of(argument: Array) -> Array:
	var content := _content_of(argument)

	if content.size() != 1 or not LITERAL_TOKENS.has(content[0].get("type")):
		return []

	return [content[0].get("value")]
