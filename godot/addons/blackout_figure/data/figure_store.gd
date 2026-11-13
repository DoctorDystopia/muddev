@tool
class_name FigureStore
extends RefCounted
## The figure files of one directory, in memory (DESIGN-0014 section 8.1).
## It holds each rig, each worn look, each clip list, the palette, and the
## stance table.
##
##     <directory>/rigs/<body type>.json
##     <directory>/looks/<asset key>.json
##     <directory>/clips/<source id>.json
##     <directory>/palette.json
##     <stances file>
##
## The palette and the stance table are each one file (Phase W5). The key
## of such a file is its kind. The stance table is not in the figure
## directory: it is in the Godot project, beside the clip files that it
## names. A store with no stances file has no stance table.
##
## The workbench reads the directory one time, changes the content in
## memory, and writes each changed file on a save.
##
## A file that does not read stays out of the store. [member errors] names
## it, and [method put] refuses its key. A save thus never writes over it.
##
## A save writes a file only while its text differs from the text on the
## disk. Thus, an undo back to the saved content leaves nothing to save.
##
## ## The directory
##
## [method repo_directory] is `blackout/assets/figure/` of this repository.
## A test gives a scratch directory under `user://`.
##
## ## The look files (ENG-0011, steps L5 and L6)
##
## The family shapes ([FamilyLooks]) and the model presentation
## ([ModelPresentation]) are look files of the client, under
## `res://world/look/`. They are no figure files: the model build does not
## read them, and the game reads them at start. The store holds them so the
## Families tab and the Gear tab change them through the same undo history.
##
## A look file writes on each change, as the Look tab of the terrain editor
## writes. Thus, a look file is never unsaved, and Save and Revert concern
## the figure files only. Each change goes into the cache of [LookFile]
## also, so each reader in the editor draws the change at one time.

## The kinds of a figure file. Each is the name of its directory.
const KIND_RIG := "rigs"
const KIND_LOOK := "looks"
const KIND_CLIPS := "clips"

## The two kinds with one file. The kind is the key of the file also.
const KIND_PALETTE := FigurePalette.KEY
const KIND_STANCES := FigureStances.KEY

## The two look files. The kind is the key of the file also.
const KIND_FAMILY := FamilyLooks.KEY
const KIND_PRESENTATION := ModelPresentation.KEY

const KINDS := [KIND_RIG, KIND_LOOK, KIND_CLIPS, KIND_PALETTE, KIND_STANCES, KIND_FAMILY,
	KIND_PRESENTATION]
const SINGLE_KINDS := [KIND_PALETTE, KIND_STANCES, KIND_FAMILY, KIND_PRESENTATION]
const LOOK_KINDS := [KIND_FAMILY, KIND_PRESENTATION]

## The path of each look file in the cache of [LookFile]: the path that the
## game reads.
const LOOK_CACHE_PATHS := {KIND_FAMILY: FamilyLooks.PATH,
	KIND_PRESENTATION: ModelPresentation.PATH}

## The figure directory, under the game directory.
const FIGURE_DIRECTORY := "assets/figure"

## The sources of the model pipeline, under the game directory. A clip list
## takes its clips from one of them.
const SOURCES_DIRECTORY := "assets/sources"

## The web directory of the game, under the game directory. The model
## pipeline writes the served model tree below it.
const WEB_DIRECTORY := "web"

const FILE_SUFFIX := ".json"

var directory := ""

## Key -> [FigureRig].
var rigs := {}

## Key -> [FigureLook].
var looks := {}

## Source id -> [FigureClipList].
var clip_lists := {}

## The OS path of the stance table, or "" for a store with none.
var stances_path := ""

## The directory of the look files: a `res://` path or an OS path.
var look_directory := LookFile.DIRECTORY

## [constant KIND_PALETTE] -> [FigurePalette], or empty for no palette file.
var _palettes := {}

## [constant KIND_STANCES] -> [FigureStances], or empty for no stance file.
var _stance_tables := {}

## [constant KIND_FAMILY] -> [FamilyLooks], or empty for no family file.
var _family_files := {}

## [constant KIND_PRESENTATION] -> [ModelPresentation], or empty for no
## presentation file.
var _presentations := {}

## One line for each file that does not read.
var errors := PackedStringArray()

## The files that differ from the disk: `"<kind>/<key>"` -> true.
var _changed := {}

## The files that do not read: `"<kind>/<key>"` -> true.
var _unreadable := {}

## The text of each file on the disk: `"<kind>/<key>"` -> text. A file that
## is not on the disk has no entry.
var _on_disk := {}


## The figure directory of this repository.
static func repo_directory() -> String:
	var project := ProjectSettings.globalize_path("res://")
	var game := project.path_join(ChunkFile.GAME_DIRECTORY_FROM_PROJECT)

	return game.path_join(FIGURE_DIRECTORY).simplify_path()


## The sources directory of this repository.
static func repo_sources_directory() -> String:
	var project := ProjectSettings.globalize_path("res://")
	var game := project.path_join(ChunkFile.GAME_DIRECTORY_FROM_PROJECT)

	return game.path_join(SOURCES_DIRECTORY).simplify_path()


## The served model tree of this repository: the directory that holds
## `manifest.json`. A part of a worn look draws a model from it.
static func repo_models_directory() -> String:
	var project := ProjectSettings.globalize_path("res://")
	var game := project.path_join(ChunkFile.GAME_DIRECTORY_FROM_PROJECT)

	return game.path_join(WEB_DIRECTORY).path_join(FigureModels.SERVED_DIRECTORY) \
		.simplify_path()


## `looks_directory` is the directory of the look files. Empty for
## `res://world/look`, the directory of the game.
func _init(figure_directory: String, stances_file := "", looks_directory := "") -> void:
	directory = figure_directory
	stances_path = stances_file

	if not looks_directory.is_empty():
		look_directory = looks_directory


## The palette of the store. A store with no palette file gives an empty
## one, and each named color then comes from [MeshPalette].
func palette() -> FigurePalette:
	return _palettes.get(KIND_PALETTE, FigurePalette.new())


## The stance table of the store. A store with no stance file gives an
## empty one.
func stances() -> FigureStances:
	return _stance_tables.get(KIND_STANCES, FigureStances.new())


## The family shapes of the store. A store with no family file gives an
## empty one, and each family then draws from the table of [FamilyShapes].
func families() -> FamilyLooks:
	return _family_files.get(KIND_FAMILY, FamilyLooks.new())


## The model presentation of the store. A store with no presentation file
## gives an empty one, and each model then draws as the table says.
func presentation() -> ModelPresentation:
	return _presentations.get(KIND_PRESENTATION, ModelPresentation.new())


## The slots that hold an item through one clip. The clip list of the clip
## gives them ([method FigureClipList.held_in]). A clip that no clip list
## names gives [constant FigureClearance.HAND_SLOTS].
func held_in(clip_name: String) -> PackedStringArray:
	for key: String in keys_of(KIND_CLIPS):
		var list: FigureClipList = clip_lists[key]

		if list.clips().has(clip_name):
			return list.held_in(clip_name)

	return PackedStringArray(FigureClearance.HAND_SLOTS)


## Read each file of the directory. This drops each change in memory.
func load_all() -> void:
	rigs.clear()
	looks.clear()
	clip_lists.clear()
	_palettes.clear()
	_stance_tables.clear()
	_family_files.clear()
	_presentations.clear()
	errors.clear()
	_changed.clear()
	_unreadable.clear()
	_on_disk.clear()

	for kind: String in KINDS:
		for file_name: String in _files_of(kind):
			var key := file_name.trim_suffix(FILE_SUFFIX)
			var item := _read(kind, path_of(kind, key))

			if item.error.is_empty():
				_table(kind)[key] = item
				_on_disk[_id(kind, key)] = FileAccess.get_file_as_string(path_of(kind, key))
			else:
				errors.append("%s/%s: %s" % [kind, file_name, item.error])
				_unreadable[_id(kind, key)] = true

	for kind: String in LOOK_KINDS:
		_sync_look_cache(kind)


## The OS path of one file.
func path_of(kind: String, key: String) -> String:
	if kind == KIND_PALETTE:
		return directory.path_join(FigurePalette.FILE_NAME)

	if kind == KIND_STANCES:
		return stances_path

	if kind == KIND_FAMILY:
		return look_directory.path_join(FamilyLooks.FILE_NAME)

	if kind == KIND_PRESENTATION:
		return look_directory.path_join(ModelPresentation.FILE_NAME)

	return directory.path_join(kind).path_join(key + FILE_SUFFIX)


## The name of one file for a report: `"<kind>/<key>.json"`, or the file
## name of a kind with one file.
func name_of(kind: String, key: String) -> String:
	if kind in SINGLE_KINDS:
		return path_of(kind, key).get_file()

	return _id(kind, key) + FILE_SUFFIX


## The kind of a file name of [method name_of].
static func kind_of_name(file_name: String) -> String:
	if file_name.contains("/"):
		return file_name.get_slice("/", 0)

	return file_name.trim_suffix(FILE_SUFFIX)


## The keys of one kind, in sorted order.
func keys_of(kind: String) -> PackedStringArray:
	var keys := PackedStringArray(_table(kind).keys())

	keys.sort()

	return keys


func has(kind: String, key: String) -> bool:
	return _table(kind).has(key)


## The item of one file: a [FigureRig], a [FigureLook], or a
## [FigureClipList]. Null for no file.
func item_of(kind: String, key: String) -> RefCounted:
	return _table(kind).get(key)


## A copy of the content of one file, or an empty dictionary for no file.
## A caller changes the copy and gives it to [method put].
func data_of(kind: String, key: String) -> Dictionary:
	if not has(kind, key):
		return {}

	return _table(kind)[key].data.duplicate(true)


## Why [method put] refuses every content for one key, or "". The plugin
## asks before it records an undo entry: an entry whose put the store
## refuses would report a change that nothing made.
func refusal(kind: String, key: String) -> String:
	if _unreadable.has(_id(kind, key)):
		return "the file %s does not read. Correct it first" % path_of(kind, key)

	if kind in SINGLE_KINDS and (key != kind or path_of(kind, key).is_empty()):
		return "this store has no file for %s" % key

	return ""


## Give one file its content. An empty dictionary removes the file from the
## store, and the next save deletes it from the disk. Returns the reason for
## a content that does not read, or "".
func put(kind: String, key: String, data: Dictionary) -> String:
	var refused := refusal(kind, key)

	if not refused.is_empty():
		return refused

	if data.is_empty():
		_table(kind).erase(key)
		_mark(kind, key)
		return ""

	var item := item_from(kind, data)

	if not item.error.is_empty():
		return item.error

	if item.key() != key:
		return "the key %s is not the file name %s" % [item.key(), key]

	_table(kind)[key] = item

	if kind in LOOK_KINDS:
		_write_look(kind, key)
	else:
		_mark(kind, key)

	return ""


## Write a look file now, and put its content in the cache of [LookFile].
## A look file is never unsaved: see the class comment.
func _write_look(kind: String, key: String) -> void:
	var path := path_of(kind, key)
	var item: RefCounted = _table(kind)[key]

	if item.write_file(path) != OK:
		errors.append("cannot write %s" % path)
	else:
		_on_disk[_id(kind, key)] = item.to_text()

	_sync_look_cache(kind)


## Put the content of one look file in the cache of [LookFile], under the
## path that the game reads. A store with no such file drops the cache, so
## each reader draws its table.
func _sync_look_cache(kind: String) -> void:
	var cache_path: String = LOOK_CACHE_PATHS[kind]

	if has(kind, kind):
		LookFile.put(cache_path, _table(kind)[kind].data)
	else:
		LookFile.forget(cache_path)


## Record whether one file differs from the disk now.
func _mark(kind: String, key: String) -> void:
	var id := _id(kind, key)
	var text: String = _table(kind)[key].to_text() if has(kind, key) else ""

	if text == _on_disk.get(id, ""):
		_changed.erase(id)
	else:
		_changed[id] = true


func has_unsaved_changes() -> bool:
	return not _changed.is_empty()


## True when the directory differs from what the store read. A file that
## another editor wrote counts, and so does a new file or a deleted file.
## The gear editor and the figure workbench write the same files. Thus, a
## save in one makes the store of the other stale. This reads each file,
## and it changes nothing.
func disk_differs() -> bool:
	var seen := {}

	for kind: String in KINDS:
		for file_name: String in _files_of(kind):
			var key := file_name.trim_suffix(FILE_SUFFIX)
			var id := _id(kind, key)

			seen[id] = true

			if _unreadable.has(id):
				continue

			if FileAccess.get_file_as_string(path_of(kind, key)) != _on_disk.get(id, ""):
				return true

	for id: String in _on_disk:
		if not seen.has(id):
			return true

	return false


## The name of each file that differs from the disk ([method name_of]), in
## sorted order. The Save button counts them, and the revert question
## names them.
func unsaved_names() -> PackedStringArray:
	var names := PackedStringArray()

	for id: String in _changed:
		names.append(name_of(id.get_slice("/", 0), id.get_slice("/", 1)))

	names.sort()

	return names


## Write each changed file, and delete each removed one. Returns the name
## of each file ([method name_of]).
func save() -> PackedStringArray:
	var saved := PackedStringArray()
	var ids := _changed.keys()

	ids.sort()

	for id: String in ids:
		var kind := id.get_slice("/", 0)
		var key := id.get_slice("/", 1)
		var path := path_of(kind, key)

		if has(kind, key):
			if _table(kind)[key].write_file(path) != OK:
				errors.append("cannot write %s" % path)
				continue

			_on_disk[id] = _table(kind)[key].to_text()
		else:
			if FileAccess.file_exists(path):
				DirAccess.remove_absolute(path)

			_on_disk.erase(id)

		saved.append(name_of(kind, key))
		_changed.erase(id)

	return saved


func _table(kind: String) -> Dictionary:
	match kind:
		KIND_RIG:
			return rigs
		KIND_CLIPS:
			return clip_lists
		KIND_PALETTE:
			return _palettes
		KIND_STANCES:
			return _stance_tables
		KIND_FAMILY:
			return _family_files
		KIND_PRESENTATION:
			return _presentations

	return looks


## The item of one kind for the content of a file. Check its `error` after.
static func item_from(kind: String, data: Dictionary) -> RefCounted:
	match kind:
		KIND_RIG:
			return FigureRig.from_data(data)
		KIND_CLIPS:
			return FigureClipList.from_data(data)
		KIND_PALETTE:
			return FigurePalette.from_data(data)
		KIND_STANCES:
			return FigureStances.from_data(data)
		KIND_FAMILY:
			return FamilyLooks.from_data(data)
		KIND_PRESENTATION:
			return ModelPresentation.from_data(data)

	return FigureLook.from_data(data)


static func _read(kind: String, path: String) -> RefCounted:
	match kind:
		KIND_RIG:
			return FigureRig.read_file(path)
		KIND_CLIPS:
			return FigureClipList.read_file(path)
		KIND_PALETTE:
			return FigurePalette.read_file(path)
		KIND_STANCES:
			return FigureStances.read_file(path)
		KIND_FAMILY:
			return FamilyLooks.read_file(path)
		KIND_PRESENTATION:
			return ModelPresentation.read_file(path)

	return FigureLook.read_file(path)


static func _id(kind: String, key: String) -> String:
	return "%s/%s" % [kind, key]


## The file names of one kind, in sorted order. A kind with one file gives
## `"<kind>.json"` when its file is there, so the key of the file is the
## kind.
func _files_of(kind: String) -> PackedStringArray:
	var found := PackedStringArray()
	var folder := directory.path_join(kind)

	if kind in SINGLE_KINDS:
		if FileAccess.file_exists(path_of(kind, kind)):
			found.append(kind + FILE_SUFFIX)

		return found

	if not DirAccess.dir_exists_absolute(folder):
		return found

	for file_name: String in DirAccess.get_files_at(folder):
		if file_name.ends_with(FILE_SUFFIX):
			found.append(file_name)

	found.sort()

	return found
