class_name ChatModes
extends RefCounted
## Where a typed line goes: the chat mode, from `char_chat`.
##
## ## The server names every mode, and this client names one
##
## Each row of `char_chat` is `{key, label, type, prefix}`. The prefix is the
## start of a command that a telnet player can type, for example `say ` or
## `@channel Public = `. The client adds the typed text to it and sends the
## result through `Evennia.command`, the one path of this screen. Thus, a chat
## line passes every lock and cooldown of the command.
##
## The one mode that the client owns is Command, the empty key: the line goes
## out as it is. It is the default, and it is not in the payload.
##
## ## A leading slash is always a command
##
## In any mode, a line that starts with [constant RAW_PREFIX] loses the slash
## and goes out as it is. Thus, a player who chats in Public can still type
## `/look`. Nick chose this on 09/29/2026.
##
## ## The chosen key outlives the payload
##
## The settings file keeps the key of the chosen mode. It loads before the
## server sends the modes, and a channel can go away. So the model keeps the
## WANTED key, and [method active_key] gives Command until a mode with that
## key exists.

## Server-owned names, generated from blackout/systems/interface/statefeed/constants.py.
const _Const := preload("res://autoload/blackout_constants.gd")

## The key of the Command mode. Empty, so a settings file with no chat mode
## gives Command.
const COMMAND_KEY := ""

## The label of the Command mode, on the mode button and in the menus.
const COMMAND_LABEL := "Command"

## A line that starts with this goes out as a command in every mode.
const RAW_PREFIX := "/"

## Fired when a payload lands, when the socket drops, and when the player
## picks a mode, so each view redraws from one place.
signal changed

## True once char_chat has arrived.
var has_data := false

## The name that the mode button shows before the mode, as OSRS shows the
## name of the player before the input.
var speaker := ""

## [{key, label, type, prefix}], in the order that the server sent.
var modes: Array = []

var _wanted := COMMAND_KEY


## Fold one feed message into this model.
##
## Returns true when the payload was one of ours, so the console can route
## without restating the channel name in a second match.
func ingest(channel: String, payload: Dictionary) -> bool:
	if channel != _Const.CH_CHAR_CHAT:
		return false

	speaker = str(payload.get("speaker", ""))
	modes = _rows(payload.get("modes", []))
	has_data = true

	changed.emit()

	return true


## Forget the payload. Called when the socket drops. The wanted key stays, so
## the next session opens in the same mode.
func reset() -> void:
	has_data = false
	speaker = ""
	modes = []

	changed.emit()


## Pick a mode by key. [constant COMMAND_KEY] picks Command. Returns false for
## a key that names no mode.
func select(key: String) -> bool:
	if key != COMMAND_KEY and _find(key).is_empty():
		return false

	if key == _wanted:
		return true

	_wanted = key
	changed.emit()

	return true


## Keep a key from the settings file, whether or not the mode exists yet.
func prefer(key: String) -> void:
	if key == _wanted:
		return

	_wanted = key
	changed.emit()


## The key that the player picked. What the settings file keeps.
func wanted_key() -> String:
	return _wanted


## The key of the mode in use: the wanted key when that mode exists, or
## Command.
func active_key() -> String:
	if _find(_wanted).is_empty():
		return COMMAND_KEY

	return _wanted


## The label of the mode in use.
func active_label() -> String:
	return label_of(active_key())


## The label of one mode, or of Command.
func label_of(key: String) -> String:
	var row := _find(key)

	if row.is_empty():
		return COMMAND_LABEL

	return str(row["label"])


## What the mode button shows: `Nick [Public]:`, or `[Command]:` with no
## speaker.
func prompt() -> String:
	var tag := "[%s]:" % active_label()

	if speaker.is_empty():
		return tag

	return "%s %s" % [speaker, tag]


## The whole line to send for a typed line, or "" to send nothing.
##
## A leading [constant RAW_PREFIX] sends the rest as it is, in every mode.
## In a chat mode, a blank line sends nothing, because `say ` with no text
## only gets a refusal.
func command_for(line: String) -> String:
	if line.begins_with(RAW_PREFIX):
		return line.substr(RAW_PREFIX.length())

	var row := _find(active_key())

	if row.is_empty():
		return line

	if line.strip_edges().is_empty():
		return ""

	return str(row["prefix"]) + line


## The modes whose message type is in `types`, in payload order. An empty
## list gives every mode, as the All tab shows every type.
func modes_for_types(types: Array) -> Array:
	if types.is_empty():
		return modes.duplicate()

	var found: Array = []

	for row: Dictionary in modes:
		if types.has(row["type"]):
			found.append(row)

	return found


func _find(key: String) -> Dictionary:
	if key == COMMAND_KEY:
		return {}

	for row: Dictionary in modes:
		if row["key"] == key:
			return row

	return {}


func _rows(raw: Variant) -> Array:
	var rows: Array = []

	if typeof(raw) != TYPE_ARRAY:
		return rows

	for entry: Variant in raw:
		if typeof(entry) != TYPE_DICTIONARY:
			continue

		var key := str(entry.get("key", ""))

		# A row with no key cannot be picked or kept, and a row with no prefix
		# would send the typed text as a command. Both are dropped.
		if key.is_empty() or str(entry.get("prefix", "")).is_empty():
			continue

		rows.append({
			"key": key,
			"label": str(entry.get("label", key)),
			"type": str(entry.get("type", "")),
			"prefix": str(entry.get("prefix", "")),
		})

	return rows
