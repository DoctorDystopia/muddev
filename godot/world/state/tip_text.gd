class_name TipText
extends RefCounted
## The tip block of a feed row, `{title, lines}`, and the text that a
## tooltip shows for it.
##
## ## One shape for every tip
##
## The server says what a thing IS, as a title and lines of text. The
## client says how a tip looks. The ability row is the first row that
## carries the block (10/20/2026). Nick expects a generic tip over most of
## the game later: an item, an entity, a skill. That tip reads this one
## shape from every row that has it, through [method read], and draws it
## with one look. A row that gains a tip adds the block, and no view
## learns a new field.
##
## Today the look is the tooltip of a [Control]: [method format] joins the
## block into the text of `tooltip_text`. A richer tip later, a box with a
## heading and a body, replaces this one method and keeps [method read].
##
## Author: Nick Hobar
## Creation date: 10/20/2026

## Server-owned names, generated from blackout/systems/interface/statefeed/constants.py.
const _Const := preload("res://autoload/blackout_constants.gd")

## Between the title and the lines, and between the lines.
const LINE_SEPARATOR := "\n"


## Read one tip block from a parsed payload. Anything that is not a
## dictionary is the same as no tip: an empty title and no lines.
static func read(raw: Variant) -> Dictionary:
	var tip := {"title": "", "lines": []}

	if typeof(raw) != TYPE_DICTIONARY:
		return tip

	tip["title"] = str(raw.get(_Const.TIP_TITLE_KEY, ""))

	var lines: Array = []
	var raw_lines: Variant = raw.get(_Const.TIP_LINES_KEY, [])

	if typeof(raw_lines) == TYPE_ARRAY:
		for line: Variant in raw_lines:
			lines.append(str(line))

	tip["lines"] = lines

	return tip


## The text of a tooltip for one tip, as [method read] gives it: the title
## on the first line, then each line. Extra lines go after the block, for
## a fact that the view adds, such as why a row is locked. Empty parts are
## left out, so a tip with no title starts at its first line.
static func format(tip: Dictionary, extra_lines: Array = []) -> String:
	var parts := PackedStringArray()
	var title := str(tip.get("title", ""))

	if not title.is_empty():
		parts.append(title)

	for line: Variant in tip.get("lines", []):
		var text := str(line)

		if not text.is_empty():
			parts.append(text)

	for line: Variant in extra_lines:
		var text := str(line)

		if not text.is_empty():
			parts.append(text)

	return LINE_SEPARATOR.join(parts)
