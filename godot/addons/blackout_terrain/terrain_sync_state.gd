@tool
class_name TerrainSyncState
extends RefCounted
## Which chunk files changed since the last tile sync, for the dock.
##
## The GDScript twin of the read half of
## `blackout/systems/core/tilegrid/syncstamp.py`. That module's docstring
## gives the reason: an edit reaches the game only after a stop of the
## server, `sync_tile_objects.py --apply`, and a start. The sync writes the
## stamp. This class compares the chunk files with it.
##
## The digest is SHA-256 of the file text with each CRLF made LF, as in
## Python. `tests/test_terrain_checks.tscn` reads the stamp of the check
## fixtures and must find no change.

const _Const := preload("res://autoload/blackout_constants.gd")

const STATE_NEW := "new"
const STATE_CHANGED := "changed"
const STATE_REMOVED := "removed"

const _STAMP_KEY := "chunks"

const _FILE_NAME_PATTERN := "^chunk_(-?\\d+)_(-?\\d+)_p(\\d+)\\.json$"


## The path of the stamp of the game directory.
static func stamp_path() -> String:
	var project := ProjectSettings.globalize_path("res://")
	var game := project.path_join(ChunkFile.GAME_DIRECTORY_FROM_PROJECT)

	return game.path_join(_Const.TILE_SYNC_STAMP_FILE).simplify_path()


## The digest of one text file, CRLF read as LF.
static func file_digest(path: String) -> String:
	return FileAccess.get_file_as_string(path).replace("\r\n", "\n").sha256_text()


## The digest map of a stamp file, or null when there is none.
static func read_stamp(path: String) -> Variant:
	if not FileAccess.file_exists(path):
		return null

	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))

	if not parsed is Dictionary:
		return null

	return parsed.get(_STAMP_KEY, {})


## Each chunk file that differs from `stamped`, as `[name, state]`, sorted.
static func changed_files(directory: String, stamped: Dictionary) -> Array:
	var now := {}
	var pattern := RegEx.create_from_string(_FILE_NAME_PATTERN)

	for file_name: String in DirAccess.get_files_at(directory):
		if pattern.search(file_name) != null:
			now[file_name] = file_digest(directory.path_join(file_name))

	var names := {}

	names.merge(now)
	names.merge(stamped)

	var sorted_names := names.keys()
	var found := []

	sorted_names.sort()

	for file_name: String in sorted_names:
		if not stamped.has(file_name):
			found.append([file_name, STATE_NEW])
		elif not now.has(file_name):
			found.append([file_name, STATE_REMOVED])
		elif now[file_name] != stamped[file_name]:
			found.append([file_name, STATE_CHANGED])

	return found


## One paragraph for the dock about `directory` and the stamp at `path`.
static func describe(directory: String, path: String) -> String:
	var stamped: Variant = read_stamp(path)

	if stamped == null:
		return "No tile sync on record. Stop the server, run " \
			+ "scripts/sync_tile_objects.py --apply, then start it."

	var found := changed_files(directory, stamped)

	if found.is_empty():
		return "Every chunk file matches the last tile sync."

	var lines := PackedStringArray()

	for row: Array in found:
		lines.append("%s (%s)" % [row[0], row[1]])

	return "Changed: %s. The server shows them after a stop, " % ", ".join(lines) \
		+ "scripts/sync_tile_objects.py --apply, and a start."
