@tool
class_name SourceTable
extends RefCounted
## A row of a fallback table in a GDScript file of the client, for a rename
## or a removal on the Tables tab (10/14/2026).
##
## Each look reader keeps a client table as its fallback, for example
## `AreaLook.LOOKS` or `FloorPalette.COLORS`. A key of such a table must name
## a server row: `test_client_constants.py` fails on a key that names
## nothing. Thus, a rename of an area renames its row in `LOOKS` too, and a
## removal takes the row out.
##
## ## The shape of a table
##
## A table is a `const NAME := {` block that ends at a line that is only
## `}`. Each row starts at a line of one tab and a quoted key, for example
## `\t"sand": Color("c2a06b"),`. A row ends on its own line. A row whose
## first line ends in `{` ends at the next line that is only `\t},`. The
## comment lines straight above a row belong to it. The Python guards read
## the same shapes.
##
## A file or a table with no such row stays as it is.

## The text before the key at the start of a row line.
const _ROW_START := "\t\"%s\":"

## The line that ends a row of more than one line.
const _ROW_END := "\t},"


## `text` with the row `old` of the table `table` renamed to `new`.
static func rename_key(text: String, table: String, old: String, new: String) -> String:
	var lines := text.split("\n")
	var span := _block(lines, table)
	var start := _ROW_START % old

	for index: int in range(span.x, span.y):
		if lines[index].begins_with(start):
			lines[index] = (_ROW_START % new) + lines[index].substr(start.length())
			return "\n".join(lines)

	return text


## `text` with the row `key` of the table `table` taken out, with its
## comment lines.
static func erase_key(text: String, table: String, key: String) -> String:
	var lines := text.split("\n")
	var span := _block(lines, table)
	var first := _row_line(lines, span, key)

	if first < 0:
		return text

	var last := _row_end(lines, span, first)

	while first > span.x and lines[first - 1].strip_edges().begins_with("#"):
		first -= 1

	var kept := lines.slice(0, first)

	kept.append_array(lines.slice(last + 1))

	return "\n".join(kept)


## Rename a row in the file at `path`. Returns true when the file changed.
static func rename_in_file(path: String, table: String, old: String, new: String) -> bool:
	return _rewrite(path, func(text: String) -> String:
		return rename_key(text, table, old, new))


## Take a row out of the file at `path`. Returns true when the file changed.
static func erase_in_file(path: String, table: String, key: String) -> bool:
	return _rewrite(path, func(text: String) -> String:
		return erase_key(text, table, key))


## True when the table `table` of `text` has a row `key`.
static func has_key(text: String, table: String, key: String) -> bool:
	var lines := text.split("\n")

	return _row_line(lines, _block(lines, table), key) >= 0


# ─── The lines ──────────────────────────────────────────────────────────────

## The first line after the opening of the table, and the line of its
## closing brace. (0, 0) for a text with no such table.
static func _block(lines: PackedStringArray, table: String) -> Vector2i:
	var opening := -1

	for index: int in lines.size():
		var line := lines[index].strip_edges(false, true)

		if opening < 0:
			if line.begins_with("const %s " % table) and line.ends_with("{"):
				opening = index
		elif line == "}":
			return Vector2i(opening + 1, index)

	return Vector2i.ZERO


static func _row_line(lines: PackedStringArray, span: Vector2i, key: String) -> int:
	for index: int in range(span.x, span.y):
		if lines[index].begins_with(_ROW_START % key):
			return index

	return -1


## The last line of the row that starts at `first`.
static func _row_end(lines: PackedStringArray, span: Vector2i, first: int) -> int:
	if not lines[first].strip_edges(false, true).ends_with("{"):
		return first

	for index: int in range(first + 1, span.y):
		if lines[index].strip_edges(false, true) == _ROW_END:
			return index

	return first


static func _rewrite(path: String, change: Callable) -> bool:
	if not FileAccess.file_exists(path):
		return false

	var text := FileAccess.get_file_as_string(path)
	var changed: String = change.call(text)

	if changed == text:
		return false

	var file := FileAccess.open(path, FileAccess.WRITE)

	if file == null:
		return false

	file.store_string(changed)
	file.close()

	return true
