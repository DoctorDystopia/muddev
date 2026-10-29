@tool
class_name WorldVersions
extends RefCounted
## The world versions (Nick, 10/28/2026): a shelf of saved worlds under
## `blackout/world/versions/`, one directory for each version. The Versions
## tab of the terrain editor saves the world as a version, switches the
## world to one, renames one, and removes one. The panel only asks. The
## plugin confirms, and then calls here.
##
## The GDScript twin of `blackout/world/world_versions.py`. Its docstring
## holds the four rules. The two that shape this class:
##
## - **A switch replaces the chunk files, and nothing else.** The world
##   stays in `world/chunks/`, so the game, the tests, and the tile sync
##   read one directory. The database follows after a stop of the server,
##   `scripts/sync_tile_objects.py --apply`, and a start. The World tab
##   names each changed file, as after any edit.
## - **A switch never drops a world that no version holds.**
##   [method current_key] names the version whose files equal the world,
##   by digest ([method TerrainSyncState.file_digest]). With none, the
##   plugin asks first and counts the files that go.
##
## A version is a whole copy: each chunk file, and `version.json` with a
## note and a save time. A directory that a developer copies by hand, with
## no meta file, is a version with no note.
##
## [member shelf] and [member chunks] are the two directories. A test points
## both at a scratch directory under `user://`.

const _Const := preload("res://autoload/blackout_constants.gd")

## The keys of the meta file.
const FORMAT_KEY := "format"
const NOTE_KEY := "note"
const SAVED_KEY := "saved"

## The shelf, as an OS path. The default is the shelf of this repo.
var shelf := ""

## The world chunk directory, as an OS path. The default is the world.
var chunks := ""


func _init(shelf_path := "", chunks_path := "") -> void:
	shelf = world_shelf() if shelf_path.is_empty() else shelf_path
	chunks = ChunkFile.world_directory() if chunks_path.is_empty() else chunks_path


# ─── The paths and the rules ────────────────────────────────────────────────

## The shelf of this repo, as an OS path.
static func world_shelf() -> String:
	var project := ProjectSettings.globalize_path("res://")
	var game := project.path_join(ChunkFile.GAME_DIRECTORY_FROM_PROJECT)

	return game.path_join(_Const.TILE_VERSION_DIRECTORY).simplify_path()


## Why `key` is not a legal version key, or "".
static func key_problem(key: String) -> String:
	if key.is_empty():
		return "A version needs a key."

	if RegEx.create_from_string(_Const.CHUNK_NAME_PATTERN).search(key) == null:
		return "A key uses a-z, 0-9, and _ only."

	return ""


## Why `note` is not a legal note, or "".
static func note_problem(note: String) -> String:
	if note.length() > _Const.TILE_VERSION_NOTE_MAX_CHARS:
		return "A note has at most %d characters." % _Const.TILE_VERSION_NOTE_MAX_CHARS

	if note.contains("\n") or note.contains("\r"):
		return "A note is one line."

	return ""


## The directory of the version `key`.
func path_of(key: String) -> String:
	return shelf.path_join(key)


## True when the shelf holds the version `key`.
func has(key: String) -> bool:
	return DirAccess.dir_exists_absolute(path_of(key))


# ─── Reading the shelf ──────────────────────────────────────────────────────

## Each version of the shelf, sorted by key, as
## `{key, note, saved, chunks, problem}`. A version whose meta file does not
## read lists with its problem and no note.
func list() -> Array[Dictionary]:
	var found: Array[Dictionary] = []

	if not DirAccess.dir_exists_absolute(shelf):
		return found

	var keys := Array(DirAccess.get_directories_at(shelf))

	keys.sort()

	for key: String in keys:
		var row := read_meta(key)

		row["key"] = key
		row["chunks"] = chunk_names(path_of(key)).size()

		if row["problem"].is_empty():
			row["problem"] = key_problem(key)

		found.append(row)

	return found


## The meta of the version `key`: `{note, saved, problem}`. A version with
## no meta file gives an empty note and no save time.
func read_meta(key: String) -> Dictionary:
	var path := path_of(key).path_join(_Const.TILE_VERSION_META_FILE)
	var meta := {"note": "", "saved": "", "problem": ""}

	if not FileAccess.file_exists(path):
		return meta

	var json := JSON.new()
	var problem := "the meta file is not JSON" \
		if json.parse(FileAccess.get_file_as_string(path)) != OK else ""
	var parsed: Variant = json.data

	if problem.is_empty():
		problem = _meta_problem(parsed)

	if not problem.is_empty():
		meta["problem"] = problem
		return meta

	meta["note"] = parsed.get(NOTE_KEY, "")
	meta["saved"] = parsed.get(SAVED_KEY, "")

	return meta


static func _meta_problem(parsed: Variant) -> String:
	if not parsed is Dictionary:
		return "the meta file is not an object"

	if parsed.get(FORMAT_KEY) != float(_Const.TILE_VERSION_FORMAT):
		return "the meta file has format %s, not %d" % [
			parsed.get(FORMAT_KEY), _Const.TILE_VERSION_FORMAT]

	for found: String in parsed:
		if found not in [FORMAT_KEY, NOTE_KEY, SAVED_KEY]:
			return "the meta file has an unknown key: %s" % found

	if not parsed.get(NOTE_KEY, "") is String:
		return "the note is not text"

	if not parsed.get(SAVED_KEY, "") is String:
		return "the save time is not text"

	return note_problem(parsed.get(NOTE_KEY, ""))


## The sorted chunk file names of a directory, or none.
static func chunk_names(directory: String) -> PackedStringArray:
	var names := PackedStringArray()

	if not DirAccess.dir_exists_absolute(directory):
		return names

	for file_name: String in DirAccess.get_files_at(directory):
		if ChunkFile.is_chunk_file_name(file_name):
			names.append(file_name)

	names.sort()

	return names


## File name to digest, for each chunk file of a directory.
static func digests(directory: String) -> Dictionary:
	var found := {}

	for file_name: String in chunk_names(directory):
		found[file_name] = TerrainSyncState.file_digest(directory.path_join(file_name))

	return found


## Each chunk file of the world that differs from the version `key`, as
## `[name, state]` in the words of [TerrainSyncState]: a file the version
## lacks is `new`, a file the world lacks is `removed`.
func differences(key: String) -> Array:
	return TerrainSyncState.changed_files(chunks, digests(path_of(key)))


## The key of the version that equals the world, or "".
func current_key() -> String:
	for row: Dictionary in list():
		if differences(row["key"]).is_empty():
			return row["key"]

	return ""


# ─── Writing the shelf ──────────────────────────────────────────────────────

## Save the world chunk files as the version `key`, with `note`. A version
## that exists needs `overwrite`. Returns `{problem, count}`: the reason
## that nothing was saved, or "" and the number of chunk files.
func save(key: String, note: String, overwrite := false) -> Dictionary:
	var problem := key_problem(key)

	if problem.is_empty():
		problem = note_problem(note)

	if problem.is_empty() and has(key) and not overwrite:
		problem = "The version %s exists. Pick another key, or overwrite it." % key

	if problem.is_empty() and chunk_names(chunks).is_empty():
		problem = "The world has no chunk file to save."

	if not problem.is_empty():
		return {"problem": problem, "count": 0}

	var target := path_of(key)
	var names := _copy_chunks(chunks, target)

	if names.is_empty():
		return {"problem": "Could not write %s." % target, "count": 0}

	_remove_chunks(target, names)

	var meta := {FORMAT_KEY: _Const.TILE_VERSION_FORMAT, NOTE_KEY: note,
		SAVED_KEY: Time.get_datetime_string_from_system(true) + "Z"}
	var file := FileAccess.open(target.path_join(_Const.TILE_VERSION_META_FILE),
		FileAccess.WRITE)

	if file == null:
		return {"problem": "Could not write the meta file of %s." % key, "count": 0}

	file.store_string(JSON.stringify(meta, " ", true) + "\n")
	file.close()

	return {"problem": "", "count": names.size()}


## Make the world chunk files the files of the version `key`. The world of
## now must equal a version, or `drop` must be true. Returns
## `{problem, changed}`: the reason that nothing changed, or "" and the
## `[name, state]` rows of [method differences] before the switch.
func switch_to(key: String, drop := false) -> Dictionary:
	if not has(key):
		return {"problem": "The shelf has no version %s." % key, "changed": []}

	var changed := differences(key)

	if changed.is_empty():
		return {"problem": "", "changed": []}

	if not drop and current_key().is_empty():
		return {"problem": "No version holds the world of now. Save it as a version "
			+ "first, or drop it: %d chunk file(s) differ." % changed.size(), "changed": []}

	var names := _copy_chunks(path_of(key), chunks)

	if names.size() != chunk_names(path_of(key)).size():
		return {"problem": "Could not copy every chunk file of %s. The world keeps "
			% key + "each old file.", "changed": []}

	_remove_chunks(chunks, names)

	return {"problem": "", "changed": changed}


## Give the version `old` the key `new`. Returns the problem, or "".
func rename(old: String, new: String) -> String:
	var problem := key_problem(new)

	if not problem.is_empty():
		return problem

	if not has(old):
		return "The shelf has no version %s." % old

	if has(new):
		return "The version %s exists." % new

	if DirAccess.rename_absolute(path_of(old), path_of(new)) != OK:
		return "Could not rename %s." % old

	return ""


## Delete the version `key` with every file of it. Returns the problem,
## or "".
func remove(key: String) -> String:
	if not has(key):
		return "The shelf has no version %s." % key

	var directory := path_of(key)

	for file_name: String in DirAccess.get_files_at(directory):
		DirAccess.remove_absolute(directory.path_join(file_name))

	if DirAccess.remove_absolute(directory) != OK:
		return "Could not remove %s: a file stays in it." % directory

	return ""


## Copy each chunk file of `source` into `target`. Returns the names that
## copied, in order, so a short list means a copy failed.
static func _copy_chunks(source: String, target: String) -> PackedStringArray:
	var copied := PackedStringArray()

	DirAccess.make_dir_recursive_absolute(target)

	for file_name: String in chunk_names(source):
		var from := FileAccess.open(source.path_join(file_name), FileAccess.READ)
		var to := FileAccess.open(target.path_join(file_name), FileAccess.WRITE)

		if from == null or to == null:
			break

		to.store_buffer(from.get_buffer(from.get_length()))
		to.close()
		from.close()
		copied.append(file_name)

	return copied


## Delete each chunk file of `directory` that is not in `keep`.
static func _remove_chunks(directory: String, keep: PackedStringArray) -> void:
	for file_name: String in chunk_names(directory):
		if file_name not in keep:
			DirAccess.remove_absolute(directory.path_join(file_name))
