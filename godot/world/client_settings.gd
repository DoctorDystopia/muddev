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
## Font size, UI scale, and whether the 3D panes are shown — and deliberately
## nothing else. Everything the client draws from the feed belongs to the
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

## Emitted after any change, so every consumer redraws from one place.
signal changed

var font_size := DEFAULT_FONT_SIZE
var ui_scale := DEFAULT_UI_SCALE
var show_world := DEFAULT_SHOW_WORLD

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


## Put everything back to the shipped defaults.
##
## Worth having as one call rather than leaving the player to remember two
## numbers: this is the escape hatch from a setting that made the UI unusable.
func reset() -> void:
	font_size = DEFAULT_FONT_SIZE
	ui_scale = DEFAULT_UI_SCALE
	show_world = DEFAULT_SHOW_WORLD
	save_to_disk()
	changed.emit()


func _clamp_font(value: int) -> int:
	return clampi(value, MIN_FONT_SIZE, MAX_FONT_SIZE)


func _clamp_scale(value: float) -> float:
	return clampf(value, MIN_UI_SCALE, MAX_UI_SCALE)
