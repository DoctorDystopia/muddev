class_name ClientSettings
extends RefCounted
## What the player has chosen about how the client looks, saved between runs.
##
## Backed by [ConfigFile] under `user://`, which is Godot's own settings format
## and its own per-platform writable location — including the web export, where
## `user://` is IndexedDB and persists across page loads. Nothing here needed
## inventing; the webclient's equivalent was a plugin plus a server round trip.
##
## ## Only what is genuinely the player's
##
## Font size, UI scale, which panes are shown, where the dividers sit, and
## where a clicked skill's detail is shown — and deliberately nothing else. Everything the client draws from the feed belongs to the
## server, and a setting that duplicated one would be a second owner of it. The
## line is the same one the whole client is built on: the server says what is
## true, the player says how it looks. Hiding a pane does not unsubscribe from
## a channel or change a single fact; it decides what is drawn, which is why it
## belongs here and not in a message to the server.
##
## ## Every value is clamped on the way in
##
## A hand-edited config, or one written by an older build, must not be able to
## produce a font of size 0 or a UI scaled to 40x — both of which render a
## client the player cannot use to fix the setting that broke it. Clamping on
## READ rather than only on write is what makes that unreachable.

## Where the file lives. `user://` resolves per platform, and on web it is
## backed by IndexedDB rather than a filesystem.
const DEFAULT_PATH := "user://client.cfg"

const SECTION := "display"

const KEY_FONT_SIZE := "font_size"
const KEY_UI_SCALE := "ui_scale"
const KEY_SHOW_WORLD := "show_world"
const KEY_SHOW_INVENTORY := "show_inventory"
const KEY_TEXT_SPLIT := "text_split"
const KEY_WORLD_SPLIT := "world_split"
const KEY_SKILL_DETAIL := "skill_detail"

const DEFAULT_FONT_SIZE := 14
const MIN_FONT_SIZE := 9
const MAX_FONT_SIZE := 28

## Whole-interface zoom, the native answer to what browser zoom did for free.
## `Window.content_scale_factor` scales layout as well as glyphs, so it is a
## real zoom rather than a font change.
const DEFAULT_UI_SCALE := 1.0
const MIN_UI_SCALE := 0.75
const MAX_UI_SCALE := 2.0

## Whether the 3D world and inventory panes are drawn at all.
##
## On by default: they are the reason this client exists. Off is the text-only
## mode the webclient had for free — GoldenLayout let a player close the 3D
## pane, and `blackout3d.js` states in its own header that closing it changes
## nothing about play, because the text channel is the authoritative view and
## the panes only mirror it. Godot's layout is authored rather than dockable, so
## that escape hatch has to be built; this is it.
##
## Honest limit: this covers a player who does not WANT the panes, or whose
## machine struggles with them. It is not a recovery from a renderer that
## refuses to start, because Godot itself will not boot without a working
## context — there is no client left at that point to read a setting.
const DEFAULT_SHOW_WORLD := true

## Whether the carried grid and the paper doll are drawn.
##
## SEPARATE from show_world, and it was one bool until 08/28/2026. Hiding
## "the 3D panes" hid the world and the bag together, so a player who wanted
## their inventory without the diorama -- the common case on a slow machine,
## since the world pane redraws every tile every frame and the bag redraws when
## the bag changes -- had no setting at all. Two facts, two bools.
const DEFAULT_SHOW_INVENTORY := true

## Where the two dividers sit, in pixels: the width of the text column, and the
## height of the 3D world above the inventory.
##
## Persisted because the alternative is what shipped -- both offsets authored in
## console.tscn as a literal 300, so every drag was forgotten on the next run.
## The notes for DESIGN-0004 ask for layout experimentation and "perhaps
## multiple configurations depending on player preferences"; a divider that
## remembers where it was put is the floor under that.
const DEFAULT_TEXT_SPLIT := 300
const DEFAULT_WORLD_SPLIT := 300

## Where a clicked skill's detail is shown: in the pane, in the game log, or
## both.
##
## THIS IS A PRESENTATION CHOICE, WHICH IS WHY IT IS HERE. The two destinations
## show the same facts from the same server description — the pane draws the
## structured `char_skills` row, the log prints the `skills <skill>` sheet the
## server renders. Neither is a different truth, so choosing between them is
## the player saying how it looks, which is the line every setting in this file
## sits on.
##
## Both by default. A player who has never opened Options should discover both
## halves exist; someone who finds the log noisy turns it off, and someone who
## reads mostly text turns the pane off. The middle case — a player who wants
## neither — is not offered, because a click that does nothing is a broken
## grid rather than a preference.
##
## `pane` SENDS NOTHING, and it has to be that way rather than "send anyway and
## draw the sheet too". The server cannot be asked for a skill quietly: the
## command that produces the sheet produces it IN THE LOG, which is the thing
## `pane` exists to avoid. So the mode is not "where is the answer shown" but
## "which answer is asked for", and each mode asks for exactly what it will
## show.
##
## The honest cost is that `pane` draws from the last `char_skills` snapshot,
## so its XP figures are as current as the last level change, resync or
## `skills`. That is affordable only because the server ships each row COMPLETE
## -- levels, curve and the whole unlock ladder -- which is the same reason a
## click needs no round trip at all. A mode that had to fetch would be a mode
## that could show a spinner.
const SKILL_DETAIL_PANE := "pane"
const SKILL_DETAIL_LOG := "log"
const SKILL_DETAIL_BOTH := "both"

## Every legal value, in the order Options offers them. A value outside this is
## clamped to the default on read; see [method _clamp_skill_detail].
const SKILL_DETAIL_MODES: Array[String] = [
	SKILL_DETAIL_BOTH, SKILL_DETAIL_PANE, SKILL_DETAIL_LOG]

const DEFAULT_SKILL_DETAIL := SKILL_DETAIL_BOTH

## Bounds on a divider. Clamped for the same reason the font is: an offset saved
## from a much wider window, or typed into the file by hand, can leave a pane at
## zero width -- and a pane with no pixels has no divider to drag back.
const MIN_SPLIT := 120
const MAX_SPLIT := 4000

## Emitted after any change, so every consumer redraws from one place.
signal changed

var font_size := DEFAULT_FONT_SIZE
var ui_scale := DEFAULT_UI_SCALE
var show_world := DEFAULT_SHOW_WORLD
var show_inventory := DEFAULT_SHOW_INVENTORY
var text_split := DEFAULT_TEXT_SPLIT
var world_split := DEFAULT_WORLD_SPLIT
var skill_detail := DEFAULT_SKILL_DETAIL

var _path: String


func _init(path: String = DEFAULT_PATH) -> void:
	# Injectable so a test can write somewhere disposable rather than into the
	# real profile.
	_path = path


## Read the file, falling back to defaults for anything missing or unusable.
##
## A missing file is the normal first-run case and is not an error. A CORRUPT
## file is also not an error: the player gets defaults and can set them again,
## which is a better outcome than a client that refuses to start because of a
## font size.
func load_from_disk() -> void:
	var config := ConfigFile.new()

	if config.load(_path) != OK:
		return

	font_size = _clamp_font(int(config.get_value(
		SECTION, KEY_FONT_SIZE, DEFAULT_FONT_SIZE)))
	ui_scale = _clamp_scale(float(config.get_value(
		SECTION, KEY_UI_SCALE, DEFAULT_UI_SCALE)))
	show_world = bool(config.get_value(
		SECTION, KEY_SHOW_WORLD, DEFAULT_SHOW_WORLD))
	show_inventory = bool(config.get_value(
		SECTION, KEY_SHOW_INVENTORY, DEFAULT_SHOW_INVENTORY))
	text_split = _clamp_split(int(config.get_value(
		SECTION, KEY_TEXT_SPLIT, DEFAULT_TEXT_SPLIT)))
	world_split = _clamp_split(int(config.get_value(
		SECTION, KEY_WORLD_SPLIT, DEFAULT_WORLD_SPLIT)))
	skill_detail = _clamp_skill_detail(str(config.get_value(
		SECTION, KEY_SKILL_DETAIL, DEFAULT_SKILL_DETAIL)))

	changed.emit()


## Write the file. Returns the Error, so a caller can report a failure.
##
## Never raises on a read-only location: a client that cannot save a preference
## should still run with it for this session.
func save_to_disk() -> Error:
	var config := ConfigFile.new()
	config.set_value(SECTION, KEY_FONT_SIZE, font_size)
	config.set_value(SECTION, KEY_UI_SCALE, ui_scale)
	config.set_value(SECTION, KEY_SHOW_WORLD, show_world)
	config.set_value(SECTION, KEY_SHOW_INVENTORY, show_inventory)
	config.set_value(SECTION, KEY_TEXT_SPLIT, text_split)
	config.set_value(SECTION, KEY_WORLD_SPLIT, world_split)
	config.set_value(SECTION, KEY_SKILL_DETAIL, skill_detail)

	return config.save(_path)


## Set the font size, clamped, and persist it.
func set_font_size(value: int) -> void:
	var clamped := _clamp_font(value)

	if clamped == font_size:
		return

	font_size = clamped
	save_to_disk()
	changed.emit()


## Set the interface scale, clamped, and persist it.
func set_ui_scale(value: float) -> void:
	var clamped := _clamp_scale(value)

	if is_equal_approx(clamped, ui_scale):
		return

	ui_scale = clamped
	save_to_disk()
	changed.emit()


## Show or hide the 3D panes, and persist it.
##
## No clamp, because a bool has nowhere unusable to go — which is the whole
## reason the other two setters have one.
func set_show_world(value: bool) -> void:
	if value == show_world:
		return

	show_world = value
	save_to_disk()
	changed.emit()


## Show or hide the inventory, and persist it.
func set_show_inventory(value: bool) -> void:
	if value == show_inventory:
		return

	show_inventory = value
	save_to_disk()
	changed.emit()


## Move the divider between the text column and the 3D half.
func set_text_split(value: int) -> void:
	var clamped := _clamp_split(value)

	if clamped == text_split:
		return

	text_split = clamped
	save_to_disk()
	changed.emit()


## Move the divider between the world pane and the inventory.
func set_world_split(value: int) -> void:
	var clamped := _clamp_split(value)

	if clamped == world_split:
		return

	world_split = clamped
	save_to_disk()
	changed.emit()


## Choose where a clicked skill's detail is shown, and persist it.
##
## Clamped like the numbers are, and for the same reason: a config written by
## an older build, or by hand, must not be able to leave every click doing
## nothing — which is a grid that looks broken and gives no hint that a setting
## caused it.
func set_skill_detail(value: String) -> void:
	var clamped := _clamp_skill_detail(value)

	if clamped == skill_detail:
		return

	skill_detail = clamped
	save_to_disk()
	changed.emit()


## True when a clicked skill should open the detail view inside the pane.
##
## Two readers ask this rather than comparing against a mode string, so the
## three-way setting has one interpretation instead of one per call site.
func skill_detail_in_pane() -> bool:
	return skill_detail != SKILL_DETAIL_LOG


## True when a clicked skill should print the server's sheet into the log.
func skill_detail_in_log() -> bool:
	return skill_detail != SKILL_DETAIL_PANE


## Put everything back to the shipped defaults.
##
## Worth having as one call rather than leaving the player to remember two
## numbers: this is the escape hatch from a setting that made the UI unusable.
func reset() -> void:
	font_size = DEFAULT_FONT_SIZE
	ui_scale = DEFAULT_UI_SCALE
	show_world = DEFAULT_SHOW_WORLD
	show_inventory = DEFAULT_SHOW_INVENTORY
	text_split = DEFAULT_TEXT_SPLIT
	world_split = DEFAULT_WORLD_SPLIT
	skill_detail = DEFAULT_SKILL_DETAIL
	save_to_disk()
	changed.emit()


func _clamp_font(value: int) -> int:
	return clampi(value, MIN_FONT_SIZE, MAX_FONT_SIZE)


func _clamp_skill_detail(value: String) -> String:
	if SKILL_DETAIL_MODES.has(value):
		return value

	return DEFAULT_SKILL_DETAIL


func _clamp_scale(value: float) -> float:
	return clampf(value, MIN_UI_SCALE, MAX_UI_SCALE)


func _clamp_split(value: int) -> int:
	return clampi(value, MIN_SPLIT, MAX_SPLIT)
