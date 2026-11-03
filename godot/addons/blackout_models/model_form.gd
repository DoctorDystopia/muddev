@tool
class_name ModelForm
extends VBoxContainer
## The Models dock: the GUI of `python -m assets.pipeline add`. The author
## fills one form. The model pipeline then writes the source and the model
## record, and builds the model. Nick asked for it on 11/02/2026, so that
## a new model needs no terminal.
##
## ## The form asks, the pipeline decides
##
## Each change of a field starts a short timer. When the timer ends, the
## form sends [signal check_wanted] with the whole plan, and the plugin
## runs `add-check` on a thread. The answer gives the problem of each
## field, the warnings, the default of each empty field, and the text of
## each file to write. [method show_answer] shows them. Write is on only
## for a plan that is ready. The form decides no rule, so it cannot accept
## what the build refuses.
##
## ## Sections
##
## Each origin shows its own sections ([constant ORIGIN_SECTIONS]). A
## section gives its fields to the plan only while it shows. Thus, a field
## of another origin never reaches the plan.

## The plan changed, and the timer ended. The plugin runs `add-check`.
signal check_wanted(plan: Dictionary)
## The author clicked Write. The plugin runs `add-write`.
signal write_wanted(plan: Dictionary)
## The author clicked Look up. The plugin runs `add-polyhaven`.
signal look_up_wanted(typed: String)
## The lists are stale. The plugin runs `add-options`.
signal options_wanted

const SECTION_UPLOAD := "upload"
const SECTION_POLYHAVEN := "polyhaven"
const SECTION_SOURCE := "source"
const SECTION_LICENSE := "license"
const SECTION_AUTHOR := "author"
const SECTION_CREDIT := "credit"
const SECTION_ALIASES := "aliases"

## The sections of each origin. A fifth origin is one more row.
const ORIGIN_SECTIONS := {
	ModelPipeline.ORIGIN_FILE: [SECTION_UPLOAD, SECTION_LICENSE, SECTION_AUTHOR,
		SECTION_CREDIT, SECTION_ALIASES],
	ModelPipeline.ORIGIN_POLYHAVEN: [SECTION_POLYHAVEN, SECTION_ALIASES],
	ModelPipeline.ORIGIN_SOURCE: [SECTION_SOURCE, SECTION_ALIASES],
	ModelPipeline.ORIGIN_EXPORT: [SECTION_UPLOAD, SECTION_AUTHOR],
}

## The file dialog of each origin with an upload. A new source takes a
## file, a folder or a .zip. An export takes one file.
const UPLOAD_MODES := {
	ModelPipeline.ORIGIN_FILE: FileDialog.FILE_MODE_OPEN_ANY,
	ModelPipeline.ORIGIN_EXPORT: FileDialog.FILE_MODE_OPEN_FILE,
}

## How long the form waits after the last change before a check, in
## seconds.
const CHECK_DELAY := 0.4

const PROBLEM_COLOR := Color(1.0, 0.45, 0.4)
const WARNING_COLOR := Color(1.0, 0.78, 0.3)
const PREVIEW_HEIGHT := 200.0

const DIALOG_TITLE := "Choose a 3D model, a folder of one, or a .zip"
const INTRO :="Add one 3D model to the model pipeline, with no terminal: the steps of " \
	+ "`python -m assets.pipeline add`. Nothing is written before Write."
const ANOTHER_LICENSE := "Another license. The gate refuses it without the reason of an exception"
const NEW_FAMILY := "A new family. It gets the budget of an unlisted family"
const OFFER_HEADING := "Pick a key that the game names, with no model yet (%d)"
const NO_OFFER := "The game names no key without a model"
const DEFAULT_HINT := "Empty gives %s"
const LOOKED_UP := "Found %s, by %s: %s, %d files."
const NO_FILES := "The files show here when each field passes its check."
const WRITTEN := "Wrote %s."
const BUILT := " Built %s. The other editors read the served tree again."
const NOT_BUILT := " Not built. Build it later: python -m assets.pipeline build %s"
const NOT_READY := "Correct each problem first, and tick each warning that you accept."

## The text of each field that the author can type, before an answer
## gives its default.
const HINTS := {
	ModelPipeline.FIELD_UPLOAD: "The path of a model file, a folder, or a .zip",
	ModelPipeline.FIELD_POLYHAVEN: "The Poly Haven id, or the URL of its page",
	ModelPipeline.FIELD_AUTHOR: "Who made it? The credits box shows this name",
	ModelPipeline.FIELD_TITLE: "The title of the model",
	ModelPipeline.FIELD_URL: "The URL of the download page",
	ModelPipeline.FIELD_SITE: "The site of the download",
	ModelPipeline.FIELD_NOTES: "Notes for the next person, for example the name of the .zip",
	ModelPipeline.FIELD_SOURCE_ID: "The name of its directory in sources/",
	ModelPipeline.FIELD_ASSET_KEY: "The name of the model in the game and in the client",
	ModelPipeline.FIELD_ALIASES: "More asset keys that draw the same model, with commas",
	ModelPipeline.FIELD_VARIANT: "The asset key of the base, for a second look (a model variant)",
}

var _origin := OptionButton.new()
var _upload := LineEdit.new()
## The filters of the file dialog, from the suffixes that the build reads.
## The dialog itself is made at each Choose, and goes when it closes.
var _filters := PackedStringArray()
var _polyhaven := LineEdit.new()
var _found := Label.new()
var _source := OptionButton.new()
var _use_refused := CheckBox.new()
var _license := OptionButton.new()
var _other_license := LineEdit.new()
var _exception := LineEdit.new()
var _author := LineEdit.new()
var _title := LineEdit.new()
var _url := LineEdit.new()
var _site := LineEdit.new()
var _notes_text := LineEdit.new()
var _source_id := LineEdit.new()
var _model_file := OptionButton.new()
var _family := OptionButton.new()
var _new_family := LineEdit.new()
var _asset_key := LineEdit.new()
var _offered := OptionButton.new()
var _aliases := LineEdit.new()
var _variant := LineEdit.new()
var _keep_unnamed := CheckBox.new()
var _preview := TextEdit.new()
var _build := CheckBox.new()
var _write: Button
var _exception_row: VBoxContainer

## The problem of the whole plan, or the work that runs now.
var _status := Label.new()

## The end of the last write. A check does not clear it.
var _last_write := Label.new()

var _timer := Timer.new()

## Each section by name, and the routine that gives its plan fields.
var _sections := {}
var _section_fields := {}

## The note labels of each plan field. A field can show in two sections.
var _notes := {}

## The text fields that an answer gives a default to, by plan field.
var _defaulted := {}

## The last good answer of `add-polyhaven`, or {}.
var _found_model := {}

## The asset key of each row of the offer list. Row 0 is the heading.
var _offer_keys := PackedStringArray()

var _ready_to_write := false
var _busy := ""


func _init() -> void:
	_build_head()
	_build_sections()
	_build_common()
	_build_foot()
	_timer.one_shot = true
	_timer.wait_time = CHECK_DELAY
	_timer.timeout.connect(check_now)
	add_child(_timer)
	_show_sections()


# ─── The layout ─────────────────────────────────────────────────────────────

func _build_head() -> void:
	var intro := FigureFields.label(INTRO)

	_origin.item_selected.connect(func(_index: int) -> void: _on_origin_changed())
	add_child(intro)
	add_child(FigureFields.button("Read the lists again", func() -> void:
		options_wanted.emit(), "Read the licenses, the families and the sources again."))
	add_child(_row("Where does the model come from?", _origin, ModelPipeline.FIELD_ORIGIN))


func _build_sections() -> void:
	_add_section(SECTION_UPLOAD, _upload_section(), func() -> Dictionary:
		return {ModelPipeline.FIELD_UPLOAD: _upload.text.strip_edges()})
	_add_section(SECTION_POLYHAVEN, _polyhaven_section(), _polyhaven_fields)
	_add_section(SECTION_SOURCE, _source_section(), func() -> Dictionary:
		return {ModelPipeline.FIELD_SOURCE_ID: _key_of(_source),
			ModelPipeline.FIELD_USE_REFUSED: _use_refused.button_pressed})
	_add_section(SECTION_LICENSE, _license_section(), _license_fields)
	_add_section(SECTION_AUTHOR, _row("Author", _text(_author, ModelPipeline.FIELD_AUTHOR),
		ModelPipeline.FIELD_AUTHOR), func() -> Dictionary:
		return {ModelPipeline.FIELD_AUTHOR: _author.text.strip_edges()})
	_add_section(SECTION_CREDIT, _credit_section(), _credit_fields)
	_add_section(SECTION_ALIASES, _alias_section(), func() -> Dictionary:
		return {ModelPipeline.FIELD_ALIASES: _aliases.text.strip_edges(),
			ModelPipeline.FIELD_VARIANT: _variant.text.strip_edges()})


func _upload_section() -> Control:
	var line := HBoxContainer.new()

	_text(_upload, ModelPipeline.FIELD_UPLOAD)
	_upload.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	line.add_child(_upload)
	line.add_child(FigureFields.button("Choose", _open_dialog, "Open a file dialog."))

	return _row("Model file, folder or .zip", line, ModelPipeline.FIELD_UPLOAD)


## Open a file dialog for the upload, in the mode of the origin. The
## dialog goes when it closes, so the dock keeps no idle dialog.
func _open_dialog() -> void:
	var dialog := FileDialog.new()

	dialog.title = DIALOG_TITLE
	dialog.access = FileDialog.ACCESS_FILESYSTEM
	dialog.file_mode = upload_mode()
	dialog.filters = _filters
	dialog.file_selected.connect(_on_upload_chosen)
	dialog.dir_selected.connect(_on_upload_chosen)
	dialog.visibility_changed.connect(func() -> void:
		if not dialog.visible:
			dialog.queue_free())
	add_child(dialog)
	dialog.popup_centered_ratio()


## The mode of the file dialog for the chosen origin.
func upload_mode() -> FileDialog.FileMode:
	return UPLOAD_MODES.get(origin(), FileDialog.FILE_MODE_OPEN_FILE)


func _polyhaven_section() -> Control:
	var line := HBoxContainer.new()

	_text(_polyhaven, ModelPipeline.FIELD_POLYHAVEN)
	_polyhaven.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_polyhaven.text_changed.connect(func(_text_now: String) -> void:
		_found_model = {}
		_found.text = "")
	_found.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	line.add_child(_polyhaven)
	line.add_child(FigureFields.button("Look up", func() -> void:
		look_up_wanted.emit(_polyhaven.text.strip_edges()),
		"Read the title, the author and the model file from Poly Haven."))

	return FigureFields.column([_row("Poly Haven model", line, ModelPipeline.FIELD_POLYHAVEN),
		_found])


func _source_section() -> Control:
	_source.item_selected.connect(func(_index: int) -> void: queue_check())
	_use_refused.text = "Use it anyway"
	_use_refused.toggled.connect(func(_on: bool) -> void: queue_check())

	return FigureFields.column([_row("Source in sources/", _source, ModelPipeline.FIELD_SOURCE_ID),
		_use_refused])


func _license_section() -> Control:
	_license.item_selected.connect(func(_index: int) -> void:
		_show_other_license()
		queue_check())
	_text(_other_license, ModelPipeline.FIELD_LICENSE)
	_other_license.placeholder_text = "The license as the page gives it, for example CC-BY-NC-4.0"
	_text(_exception, ModelPipeline.FIELD_EXCEPTION)
	_exception.placeholder_text = "Why can Blackout serve it? The check shows this reason"

	_exception_row = _row("Reason of the exception", _exception, ModelPipeline.FIELD_EXCEPTION)

	return FigureFields.column([
		_row("License that the download page gives", _license, ModelPipeline.FIELD_LICENSE),
		_other_license, _exception_row])


func _credit_section() -> Control:
	return FigureFields.column([
		_row("Title", _text(_title, ModelPipeline.FIELD_TITLE), ModelPipeline.FIELD_TITLE),
		_row("URL", _text(_url, ModelPipeline.FIELD_URL), ModelPipeline.FIELD_URL),
		_row("Site", _text(_site, ModelPipeline.FIELD_SITE), ModelPipeline.FIELD_SITE),
		_row("Notes", _text(_notes_text, ModelPipeline.FIELD_NOTES), ModelPipeline.FIELD_NOTES),
		_row("Source id", _text(_source_id, ModelPipeline.FIELD_SOURCE_ID),
			ModelPipeline.FIELD_SOURCE_ID)])


func _alias_section() -> Control:
	return FigureFields.column([
		_row("Aliases", _text(_aliases, ModelPipeline.FIELD_ALIASES),
			ModelPipeline.FIELD_ALIASES),
		_row("Variant of", _text(_variant, ModelPipeline.FIELD_VARIANT),
			ModelPipeline.FIELD_VARIANT)])


func _build_common() -> void:
	_model_file.item_selected.connect(func(_index: int) -> void: queue_check())
	_family.item_selected.connect(func(_index: int) -> void:
		_new_family.visible = _family.selected >= 0 and _key_of(_family).is_empty()
		queue_check())
	_new_family.placeholder_text = "The name of the new family"
	_new_family.text_changed.connect(func(_text_now: String) -> void: queue_check())
	_new_family.visible = false
	_offered.item_selected.connect(_on_offer_picked)
	_keep_unnamed.text = "Keep the keys that the game does not name"
	_keep_unnamed.toggled.connect(func(_on: bool) -> void: queue_check())
	_keep_unnamed.visible = false
	add_child(_row("Model file in the source", _model_file, ModelPipeline.FIELD_MODEL_FILE))
	add_child(_row("Family", FigureFields.column([_family, _new_family]),
		ModelPipeline.FIELD_FAMILY))
	add_child(_row("Asset key", FigureFields.column([
		_text(_asset_key, ModelPipeline.FIELD_ASSET_KEY), _offered]),
		ModelPipeline.FIELD_ASSET_KEY))
	add_child(_keep_unnamed)


func _build_foot() -> void:
	_preview.editable = false
	_preview.custom_minimum_size.y = PREVIEW_HEIGHT
	_preview.placeholder_text = NO_FILES
	_build.text = "Build the model after the write"
	_build.button_pressed = true
	_build.toggled.connect(func(_on: bool) -> void: queue_check())
	_write = FigureFields.button("Write", func() -> void: write_wanted.emit(plan()),
		"Write the source and the model record, then build when the box is ticked.")
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_last_write.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(FigureFields.fold("Files to write", _preview))
	add_child(_build)
	add_child(_write)
	add_child(_status)
	add_child(_last_write)
	_enable_write()


## A field with its label above and its note below. The note shows the
## problem or the warning of `field`.
func _row(title: String, control: Control, field: String) -> VBoxContainer:
	var note := FigureFields.label("")

	note.visible = false
	_notes[field] = _notes.get(field, []) + [note]

	return FigureFields.column([FigureFields.label(title), control, note])


## A text field that checks the plan when it changes.
func _text(field: LineEdit, plan_field: String) -> LineEdit:
	field.placeholder_text = HINTS.get(plan_field, "")
	field.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	field.text_changed.connect(func(_text_now: String) -> void: queue_check())

	if HINTS.has(plan_field):
		_defaulted[plan_field] = _defaulted.get(plan_field, []) + [field]

	return field


func _add_section(section: String, content: Control, fields: Callable) -> void:
	_sections[section] = content
	_section_fields[section] = fields
	add_child(content)


# ─── The plan ───────────────────────────────────────────────────────────────

## The key of the chosen origin, or "".
func origin() -> String:
	return _key_of(_origin)


## The whole plan, as `add-check` and `add-write` read it.
func plan() -> Dictionary:
	var made := {
		ModelPipeline.FIELD_FORMAT: ModelPipeline.FORM_FORMAT,
		ModelPipeline.FIELD_ORIGIN: origin(),
		ModelPipeline.FIELD_MODEL_FILE: FigureFields.text_of(_model_file),
		ModelPipeline.FIELD_FAMILY: _family_key(),
		ModelPipeline.FIELD_ASSET_KEY: _asset_key.text.strip_edges(),
		ModelPipeline.FIELD_KEEP_UNNAMED: _keep_unnamed.button_pressed,
		ModelPipeline.FIELD_BUILD: _build.button_pressed,
	}

	for section: String in ORIGIN_SECTIONS.get(origin(), []):
		made.merge(_section_fields[section].call(), true)

	return made


func _polyhaven_fields() -> Dictionary:
	return {ModelPipeline.FIELD_POLYHAVEN: _polyhaven.text.strip_edges(),
		ModelPipeline.FIELD_TITLE: _found_model.get("title", ""),
		ModelPipeline.FIELD_AUTHOR: _found_model.get("author", ""),
		ModelPipeline.FIELD_MODEL_FILE: _found_model.get("model_file", "")}


## The license of a new source. The last row of the list is another
## license, which the author types, with the reason of an exception.
func _license_fields() -> Dictionary:
	var other := _is_other_license()
	var spdx := _other_license.text.strip_edges() if other else _key_of(_license)

	return {ModelPipeline.FIELD_LICENSE: spdx,
		ModelPipeline.FIELD_EXCEPTION: _exception.text.strip_edges() if other else ""}


func _credit_fields() -> Dictionary:
	return {ModelPipeline.FIELD_TITLE: _title.text.strip_edges(),
		ModelPipeline.FIELD_URL: _url.text.strip_edges(),
		ModelPipeline.FIELD_SITE: _site.text.strip_edges(),
		ModelPipeline.FIELD_NOTES: _notes_text.text.strip_edges(),
		ModelPipeline.FIELD_SOURCE_ID: _source_id.text.strip_edges()}


func _family_key() -> String:
	if _family.selected < 0:
		return ""

	var key := _key_of(_family)

	return key if not key.is_empty() else _new_family.text.strip_edges()


func _is_other_license() -> bool:
	return _license.selected >= 0 and _key_of(_license).is_empty()


# ─── The answers ────────────────────────────────────────────────────────────

## Fill the lists from the answer of `add-options`. `output` shows when
## the command gave no answer, for example with no Python.
func show_options(answer: Dictionary, output := "") -> void:
	if answer.is_empty() or not str(answer.get("problem", "")).is_empty():
		_status.text = str(answer.get("problem", output))
		return

	_fill_keyed(_origin, answer.get("origins", []), "key", "label", true)
	_fill_keyed(_license, answer.get("licenses", []), "spdx", "name", false)
	_license.add_item(ANOTHER_LICENSE)
	_fill_keyed(_family, answer.get("families", []), "key", "label", false)
	_family.add_item(NEW_FAMILY)
	_fill_sources(answer.get("sources", []))
	_filters = _upload_filters(answer.get("model_suffixes", []), str(answer.get("zip_suffix", "")))
	_show_sections()
	_status.text = ""
	queue_check()


## Show the answer of `add-check`: the note of each field, each default,
## the model files, the offer, and each file to write.
func show_answer(answer: Dictionary, output := "") -> void:
	var problems: Dictionary = answer.get("problems", {})
	var warnings: Dictionary = answer.get("warnings", {})

	for field: String in _notes:
		_show_note(field, str(problems.get(field, "")), str(warnings.get(field, "")))

	_show_defaults(answer.get("defaults", {}))
	_fill_model_files(answer.get("model_files", []), str(answer.get("model_file", "")))
	_fill_offer(answer.get("offered", []))
	_show_files(answer.get("files", []))
	_keep_unnamed.visible = warnings.has(ModelPipeline.FIELD_ASSET_KEY) \
		or warnings.has(ModelPipeline.FIELD_ALIASES)
	_use_refused.visible = warnings.has(ModelPipeline.FIELD_SOURCE_ID)
	_show_build_problem(str(answer.get("build_problem", "")))
	_ready_to_write = answer.get("ready", false)
	_status.text = _whole_problem(answer, output)
	_enable_write()


## Show the answer of `add-polyhaven`. A model that Poly Haven found goes
## into the plan.
func show_look_up(answer: Dictionary, output := "") -> void:
	_found_model = {}

	if answer.get("ok", false):
		_found_model = answer
		_found.text = LOOKED_UP % [answer["title"], answer["author"], answer["model_file"],
			int(answer["file_count"])]
	else:
		_found.text = str(answer.get("problem", output))

	queue_check()


## Show the end of a write. A good write clears the fields of this model,
## and asks for the lists again, because a source is new.
func show_written(answer: Dictionary, output := "") -> void:
	_busy = ""

	if not answer.get("ok", false):
		_status.text = "\n".join(PackedStringArray([ModelPipeline.problem_text(answer),
			output])).strip_edges()
		_enable_write()
		return

	var key := str(answer.get("asset_key", ""))
	var built := BUILT % key if answer.get("built", false) else NOT_BUILT % key

	_status.text = ""
	_last_write.text = WRITTEN % answer.get("record_path", key) + built
	_clear_model_fields()
	options_wanted.emit()


## Turn Write off while a write runs, and say why.
func set_busy(text: String) -> void:
	_busy = text
	_status.text = text
	_enable_write()


func _whole_problem(answer: Dictionary, output: String) -> String:
	if answer.is_empty():
		return output

	var lines := PackedStringArray([str(answer.get("problem", "")),
		str(answer.get("key_list_problem", ""))])

	return "\n".join(lines).strip_edges()


func _show_note(field: String, problem: String, warning: String) -> void:
	for note: Label in _notes[field]:
		note.text = problem if not problem.is_empty() else warning
		note.visible = not note.text.is_empty()
		note.add_theme_color_override("font_color",
			PROBLEM_COLOR if not problem.is_empty() else WARNING_COLOR)


func _show_defaults(defaults: Dictionary) -> void:
	for field: String in _defaulted:
		var default := str(defaults.get(field, ""))

		for edit: LineEdit in _defaulted[field]:
			edit.placeholder_text = DEFAULT_HINT % default if not default.is_empty() \
				else HINTS[field]


func _show_files(files: Array) -> void:
	var lines := PackedStringArray()

	for row: Dictionary in files:
		var note := str(row.get("note", ""))

		lines.append(str(row["path"]) + ("  " + note if not note.is_empty() else ""))

		for line: String in str(row.get("text", "")).split("\n", false):
			lines.append("    " + line)

	_preview.text = "\n".join(lines)


func _show_build_problem(problem: String) -> void:
	_build.disabled = not problem.is_empty()
	_build.tooltip_text = problem


func _enable_write() -> void:
	var reason := _busy if not _busy.is_empty() else NOT_READY

	FigureFields.enable(_write, _ready_to_write and _busy.is_empty(), reason)


# ─── The lists ──────────────────────────────────────────────────────────────

## Fill a list from rows, with the key of each row as its metadata. The
## chosen key stays chosen. With no chosen key, `pick_first` chooses the
## first row. A license, a family and a source are the choice of the
## author, as in the wizard, so they start with no choice.
static func _fill_keyed(list: OptionButton, rows: Array, key_field: String,
		label_field: String, pick_first: bool) -> void:
	var chosen := _key_of(list)

	list.clear()

	for row: Dictionary in rows:
		list.add_item(str(row[label_field]))
		list.set_item_metadata(list.item_count - 1, str(row[key_field]))

	list.select(-1)
	_select_key(list, chosen)

	if pick_first and list.selected < 0 and list.item_count > 0:
		list.select(0)


## The key of the chosen row of a list, or "".
static func _key_of(list: OptionButton) -> String:
	if list.selected < 0:
		return ""

	var key: Variant = list.get_item_metadata(list.selected)

	return str(key) if key != null else ""


static func _select_key(list: OptionButton, key: String) -> void:
	for index: int in list.item_count:
		if str(list.get_item_metadata(index)) == key and not key.is_empty():
			list.select(index)
			return


## Each source, with a row that cannot be chosen for a source with a
## problem. The problem is its tooltip.
func _fill_sources(rows: Array) -> void:
	_fill_keyed(_source, rows, "id", "label", false)

	for index: int in _source.item_count:
		var problem := str(rows[index].get("problem", ""))

		_source.set_item_disabled(index, not problem.is_empty())
		_source.set_item_tooltip(index, problem)

	if _source.selected >= 0 and _source.is_item_disabled(_source.selected):
		_source.select(-1)


func _fill_model_files(files: Array, chosen: String) -> void:
	FigureFields.fill(_model_file, files)

	if not chosen.is_empty():
		FigureFields.select_text(_model_file, chosen)


## The offer: each key that the game names and no model draws yet. A pick
## puts the key in the asset key field. Row 0 is a heading.
func _fill_offer(rows: Array) -> void:
	var keys := PackedStringArray()

	for row: Dictionary in rows:
		keys.append(str(row["key"]))

	if keys == _offer_keys.slice(1) and _offered.item_count > 0:
		return

	_offered.clear()
	_offered.add_item(OFFER_HEADING % rows.size() if not rows.is_empty() else NO_OFFER)
	_offer_keys = PackedStringArray([""])

	for row: Dictionary in rows:
		var look := "  (it has a worn look)" if row.get("worn_look", false) else ""

		_offered.add_item("%s  %s  %s%s" % [row["key"], row["kind"], row["name"], look])
		_offer_keys.append(str(row["key"]))

	_offered.select(0)


func _on_offer_picked(index: int) -> void:
	if index <= 0 or index >= _offer_keys.size():
		return

	_asset_key.text = _offer_keys[index]
	_offered.select(0)
	queue_check()


static func _upload_filters(suffixes: Array, zip_suffix: String) -> PackedStringArray:
	var patterns := PackedStringArray()

	for suffix: String in suffixes:
		patterns.append("*" + suffix)

	var filters := PackedStringArray([", ".join(patterns) + " ; 3D models"])

	if not zip_suffix.is_empty():
		filters.append("*%s ; Zip files" % zip_suffix)

	return filters


# ─── The changes ────────────────────────────────────────────────────────────

## Check the plan when the author stops typing.
func queue_check() -> void:
	if is_inside_tree():
		_timer.start()


## Check the plan now.
func check_now() -> void:
	_timer.stop()
	check_wanted.emit(plan())


func _on_origin_changed() -> void:
	_show_sections()
	queue_check()


func _on_upload_chosen(path: String) -> void:
	_upload.text = path
	queue_check()


## Show the sections of the chosen origin, and hide the rest.
func _show_sections() -> void:
	var shown: Array = ORIGIN_SECTIONS.get(origin(), [])

	for section: String in _sections:
		_sections[section].visible = section in shown

	_show_other_license()


func _show_other_license() -> void:
	var other := _is_other_license()

	_other_license.visible = other
	_exception_row.visible = other


## Clear the fields of one model after its write. The origin, the
## license, the author and the family stay for the next model.
func _clear_model_fields() -> void:
	for edit: LineEdit in [_upload, _polyhaven, _title, _url, _site, _notes_text, _source_id,
			_asset_key, _aliases, _variant]:
		edit.text = ""

	_found_model = {}
	_found.text = ""
	_keep_unnamed.button_pressed = false
	_use_refused.button_pressed = false
