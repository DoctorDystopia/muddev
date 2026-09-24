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
## Font size, UI scale, which panes are shown, how big the player made a box
## and where they put it, where a clicked skill's detail
## is shown, and how loud sound effects play — and
## deliberately nothing else. Everything the client draws from the feed belongs to the
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

## Sound gets its own section: a volume is not a display setting, and a file
## read by hand should say which is which.
const AUDIO_SECTION := "audio"

const KEY_FONT_SIZE := "font_size"
const KEY_UI_SCALE := "ui_scale"
const KEY_SHOW_WORLD := "show_world"
const KEY_SHOW_INVENTORY := "show_inventory"
const KEY_PANEL_SIZE := "panel_size"
const KEY_CONSOLE_SIZE := "console_size"
const KEY_SKILL_DETAIL := "skill_detail"
const KEY_SFX_VOLUME := "sfx_volume"
const KEY_SHOW_XP_DROPS := "show_xp_drops"
const KEY_SHOW_SKILL_RATES := "show_skill_rates"
const KEY_SMOOTH_MOVEMENT := "smooth_movement"
const KEY_AMOUNT_SIZE := "amount_size"
const KEY_POPUP_RECT := "popup_rect"

const DEFAULT_FONT_SIZE := 14
const MIN_FONT_SIZE := 9
const MAX_FONT_SIZE := 28

## Whole-interface zoom, the native answer to what browser zoom did for free.
## `Window.content_scale_factor` scales layout as well as glyphs, so it is a
## real zoom rather than a font change.
const DEFAULT_UI_SCALE := 1.0
const MIN_UI_SCALE := 0.75
const MAX_UI_SCALE := 2.0

## The screen density at a scale of 1, in dots per inch. The scale before the
## player picks one is the DPI of the screen over this. See
## [method ui_scale_for_dpi].
const REFERENCE_DPI := 96.0

## The step of a scale from the screen, so a first run gives 125% and not 127%.
const SCREEN_SCALE_STEP := 0.25

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

## How loud every sound effect plays, LINEAR from silent (0.0) to as mixed (1.0).
##
## Linear and not decibels, because a slider in decibels crowds every audible
## change into its last quarter. Turning this into a bus level is
## [method SoundCues.apply_volume]'s job, not this file's -- this stores what
## the player chose, the bus owner decides what that means to the mixer.
##
## Capped at 1.0 rather than allowing a boost: above the authored mix is where
## clips start to clip, and a louder game is the operating system's slider.
const DEFAULT_SFX_VOLUME := 1.0
const MIN_SFX_VOLUME := 0.0
const MAX_SFX_VOLUME := 1.0

## Whether XP drops, the session tracker and the progress bar are drawn over the
## world.
##
## On by default, as OSRS ships its drops: a player should see what an action
## earned without first finding a setting. Hiding it unsubscribes from nothing --
## the tracker keeps counting, so turning it back on shows the session so far
## rather than one that restarted.
const DEFAULT_SHOW_XP_DROPS := true

## Whether the tracker lists XP per hour for each skill trained this session.
##
## Off by default. The session rate answers "is this worth my time"; a row per
## skill is for a player comparing methods, and on a fight that trains three
## skills it is three more lines over the world.
const DEFAULT_SHOW_SKILL_RATES := false

## Whether a figure SLIDES between tiles instead of appearing on each one.
##
## On by default. A step per tick drawn as a jump per tick is what the client
## did until 09/20/2026, and it reads as teleporting rather than as walking.
##
## ## Why this is one setting and not two
##
## The animation draws a figure away from the square the server has it on, and
## every command a player gives is resolved against that square. So the client
## marks the true tile for as long as a figure is off it -- see [TrueTileMark].
## The mark is not separately switchable, and that is deliberate: it exists to
## repay what the animation costs, so a player who could keep the animation and
## drop the mark would be choosing to be told less than the server says. With
## the animation off there is nothing to repay, and no mark is drawn.
##
## It is a LOOK, which is why it lives here. The server sends one tile per
## tick either way, this client asks for nothing extra, and a player who turns
## it off sees exactly the same facts one frame sooner.
const DEFAULT_SMOOTH_MOVEMENT := true

## How big the player made the amount box, in pixels, or zero on either axis
## before they sized one.
##
## ## Why zero is the default and not a number
##
## The box asks one question with one spin box, and [AcceptDialog] wraps its
## controls: with no remembered size it opens at exactly the size of its own
## contents. A shipped default would be a number somebody picked, and every
## title makes the box a different width. Zero says "let it wrap", which is
## the first-run look the client already had.
##
## ## Why ONE size for every amount box
##
## Deposit X, Withdraw X, Sell X and the pop-up's X button all draw the same
## box with a different title. A size for each verb is a setting the player
## has to find four times to get one look, and none of the four boxes differs
## in what it holds.
##
## The size is read when the box CLOSES, one write for one box. A size read
## from the resize gesture would be a file write for each frame of the drag,
## which is the trap the dividers already document.
const DEFAULT_AMOUNT_SIZE := Vector2i.ZERO

## Where the player put the pop-up box, in the world pane's pixels, or an empty
## rect before the first drag.
##
## The rect survived a close and a reopen, and it died with the client. A player
## who moved the bank off their minimap set it again on every run.
##
## ## Pixels, not a part of the pane
##
## [method PopupView._place_box] already clamps a rect into the pane it has, and
## a rect saved by a wider window comes back too large for a narrow one. That
## clamp is therefore the ONE owner of "the box stays on screen", and it needs
## no help: it runs on every open, on every drag, and whenever the pane is
## resized. A rect stored as a fraction would be a second rule about the same
## thing, and the two would disagree the first time the minimum box size won.
##
## So the bounds below are not that rule. They only keep a hand-edited number
## sane.
const DEFAULT_POPUP_RECT := Rect2()

## The largest pixel figure a saved box may carry, on any axis.
##
## Not a limit on a box the player can make -- the pane is that -- but a fence
## around a number read from a file. A width of 1e9 is a layout pass that
## allocates a rect no monitor can hold.
const MAX_BOX_PIXELS := 4000

## How big the player left the control panel dock, or zero before the first
## drag.
##
## A SIZE and not a rect, because the dock owns the corner it hangs from. See
## [PanelDock]: the box is pinned to the bottom-right of the world pane, so the
## left edge and the top edge are the two the player drags and the position
## follows from the size. A stored position would be a second owner of the one
## fact the dock already decides.
##
## Zero means "never dragged", so a fresh client gets
## [constant PanelDock.DEFAULT_SIZE] and a returning one gets what it left.
## [method PanelDock._place_box] clamps whatever comes back into the pane it
## has, which is the same single owner of "the box stays on screen" that
## [constant DEFAULT_POPUP_RECT] documents.
const DEFAULT_PANEL_SIZE := Vector2i.ZERO

## How big the player left the game log dock, or zero before the first drag.
##
## The same rules as [constant DEFAULT_PANEL_SIZE]. The log hangs from the
## bottom-left corner of the world pane, so the player drags its right edge and
## its top edge.
##
## Until 09/22/2026 the log was the left half of an `HSplitContainer`, and
## `text_split` kept the divider offset. A split can change the width only. The
## log always took the full height, so the player could not give that height
## back to the world.
const DEFAULT_CONSOLE_SIZE := Vector2i.ZERO

## Each dock size, by its key. A key is also the name of its property, so
## [method set_dock_size] and [PanelDock] reach every dock through one path.
const DOCK_SIZE_KEYS: Array[String] = [KEY_PANEL_SIZE, KEY_CONSOLE_SIZE]

## Emitted after any change, so every consumer redraws from one place.
signal changed

var font_size := DEFAULT_FONT_SIZE
var ui_scale := DEFAULT_UI_SCALE

## The scale before the player picks one, and the scale that Reset gives. See
## [method set_shipped_ui_scale].
var shipped_ui_scale := DEFAULT_UI_SCALE
var show_world := DEFAULT_SHOW_WORLD
var show_inventory := DEFAULT_SHOW_INVENTORY
var skill_detail := DEFAULT_SKILL_DETAIL
var sfx_volume := DEFAULT_SFX_VOLUME
var show_xp_drops := DEFAULT_SHOW_XP_DROPS
var show_skill_rates := DEFAULT_SHOW_SKILL_RATES
var smooth_movement := DEFAULT_SMOOTH_MOVEMENT
var amount_size := DEFAULT_AMOUNT_SIZE
var popup_rect := DEFAULT_POPUP_RECT
var panel_size := DEFAULT_PANEL_SIZE
var console_size := DEFAULT_CONSOLE_SIZE

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
		SECTION, KEY_UI_SCALE, shipped_ui_scale)))
	show_world = bool(config.get_value(
		SECTION, KEY_SHOW_WORLD, DEFAULT_SHOW_WORLD))
	show_inventory = bool(config.get_value(
		SECTION, KEY_SHOW_INVENTORY, DEFAULT_SHOW_INVENTORY))
	skill_detail = _clamp_skill_detail(str(config.get_value(
		SECTION, KEY_SKILL_DETAIL, DEFAULT_SKILL_DETAIL)))
	sfx_volume = _clamp_volume(float(config.get_value(
		AUDIO_SECTION, KEY_SFX_VOLUME, DEFAULT_SFX_VOLUME)))
	show_xp_drops = bool(config.get_value(
		SECTION, KEY_SHOW_XP_DROPS, DEFAULT_SHOW_XP_DROPS))
	show_skill_rates = bool(config.get_value(
		SECTION, KEY_SHOW_SKILL_RATES, DEFAULT_SHOW_SKILL_RATES))
	smooth_movement = bool(config.get_value(
		SECTION, KEY_SMOOTH_MOVEMENT, DEFAULT_SMOOTH_MOVEMENT))
	amount_size = _clamp_box_size(config.get_value(
		SECTION, KEY_AMOUNT_SIZE, DEFAULT_AMOUNT_SIZE))
	popup_rect = _clamp_box_rect(config.get_value(
		SECTION, KEY_POPUP_RECT, DEFAULT_POPUP_RECT))
	panel_size = _clamp_box_size(config.get_value(
		SECTION, KEY_PANEL_SIZE, DEFAULT_PANEL_SIZE))
	console_size = _clamp_box_size(config.get_value(
		SECTION, KEY_CONSOLE_SIZE, DEFAULT_CONSOLE_SIZE))

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
	config.set_value(SECTION, KEY_SKILL_DETAIL, skill_detail)
	config.set_value(AUDIO_SECTION, KEY_SFX_VOLUME, sfx_volume)
	config.set_value(SECTION, KEY_SHOW_XP_DROPS, show_xp_drops)
	config.set_value(SECTION, KEY_SHOW_SKILL_RATES, show_skill_rates)
	config.set_value(SECTION, KEY_SMOOTH_MOVEMENT, smooth_movement)
	config.set_value(SECTION, KEY_AMOUNT_SIZE, amount_size)
	config.set_value(SECTION, KEY_POPUP_RECT, popup_rect)
	config.set_value(SECTION, KEY_PANEL_SIZE, panel_size)
	config.set_value(SECTION, KEY_CONSOLE_SIZE, console_size)

	return config.save(_path)


## Set the font size, clamped, and persist it.
func set_font_size(value: int) -> void:
	var clamped := _clamp_font(value)

	if clamped == font_size:
		return

	font_size = clamped
	save_to_disk()
	changed.emit()


## The scale for a screen of `dpi` dots per inch, in steps of
## [constant SCREEN_SCALE_STEP] and clamped.
##
## A 4K screen at 150% in Windows reports 144 DPI, and a browser reports 96
## times its device pixel ratio. At a scale of 1, such a screen shows the text
## at half or two thirds of its size on a 1080p screen.
static func ui_scale_for_dpi(dpi: int) -> float:
	var scale := snappedf(dpi / REFERENCE_DPI, SCREEN_SCALE_STEP)

	return clampf(scale, MIN_UI_SCALE, MAX_UI_SCALE)


## Set the scale for a player who has not picked one. Call it before
## [method load_from_disk]: a file with a scale in it wins.
##
## It writes nothing. The screen gives this value on every run, and the file
## keeps only what the player saw.
func set_shipped_ui_scale(value: float) -> void:
	shipped_ui_scale = _clamp_scale(value)
	ui_scale = shipped_ui_scale


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


## The size the player left one dock at, or zero before the first drag.
##
## `key` is one of [constant DOCK_SIZE_KEYS]. An unknown key gives zero, which
## the dock reads as "use the shipped size".
func dock_size(key: String) -> Vector2i:
	if not DOCK_SIZE_KEYS.has(key):
		push_warning("ClientSettings: no dock size named %s" % key)
		return Vector2i.ZERO

	return get(key)


## Remember how big the player made one dock, and persist it.
##
## The caller passes the size that the box ENDED at, after
## [method PanelDock._place_box] clamped it into the pane. The number that the
## player can see is the number to keep.
func set_dock_size(key: String, value: Vector2i) -> void:
	if not DOCK_SIZE_KEYS.has(key):
		push_warning("ClientSettings: no dock size named %s" % key)
		return

	var clamped := _clamp_box_size(value)

	if clamped == get(key):
		return

	set(key, clamped)
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


## Set the sound effects volume, clamped, and persist it.
##
## Clamped for the same reason the font is, with a quieter failure: a volume
## saved far above 1.0 would clip every clip, and one below zero is meaningless
## to the mixer.
func set_sfx_volume(value: float) -> void:
	var clamped := _clamp_volume(value)

	if is_equal_approx(clamped, sfx_volume):
		return

	sfx_volume = clamped
	save_to_disk()
	changed.emit()


## Show or hide the XP drops and tracker, and persist it.
func set_show_xp_drops(value: bool) -> void:
	if value == show_xp_drops:
		return

	show_xp_drops = value
	save_to_disk()
	changed.emit()


## Show or hide XP per hour for each skill, and persist it.
func set_show_skill_rates(value: bool) -> void:
	if value == show_skill_rates:
		return

	show_skill_rates = value
	save_to_disk()
	changed.emit()


## Slide figures between tiles, or draw each one on its tile, and persist it.
func set_smooth_movement(value: bool) -> void:
	if value == smooth_movement:
		return

	smooth_movement = value
	save_to_disk()
	changed.emit()


## Remember how big the player made the amount box, and persist it.
##
## Called when the box closes, so a resize drag writes the file one time. A
## zero on either axis clears the memory and gives the next box its wrapped
## size, which is what [method reset] uses.
func set_amount_size(value: Vector2i) -> void:
	var clamped := _clamp_box_size(value)

	if clamped == amount_size:
		return

	amount_size = clamped
	save_to_disk()
	changed.emit()


## Remember where the player put the pop-up box, and persist it.
##
## The caller passes the rect the box ENDED at, after
## [method PopupView._place_box] clamped it. The number that the player can
## see is the number to keep.
func set_popup_rect(value: Rect2) -> void:
	var clamped := _clamp_box_rect(value)

	if clamped == popup_rect:
		return

	popup_rect = clamped
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
	ui_scale = shipped_ui_scale
	show_world = DEFAULT_SHOW_WORLD
	show_inventory = DEFAULT_SHOW_INVENTORY
	skill_detail = DEFAULT_SKILL_DETAIL
	sfx_volume = DEFAULT_SFX_VOLUME
	show_xp_drops = DEFAULT_SHOW_XP_DROPS
	show_skill_rates = DEFAULT_SHOW_SKILL_RATES
	smooth_movement = DEFAULT_SMOOTH_MOVEMENT
	amount_size = DEFAULT_AMOUNT_SIZE
	popup_rect = DEFAULT_POPUP_RECT
	panel_size = DEFAULT_PANEL_SIZE
	console_size = DEFAULT_CONSOLE_SIZE
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


func _clamp_volume(value: float) -> float:
	return clampf(value, MIN_SFX_VOLUME, MAX_SFX_VOLUME)


## A saved box size, or zero when the file holds something else.
##
## Typed, because [ConfigFile] gives back whatever Variant it stored and a
## hand-edited line can say anything. A wrong TYPE is the same case as a wrong
## number: the player gets the wrapped box and can size it again.
func _clamp_box_size(value: Variant) -> Vector2i:
	if typeof(value) != TYPE_VECTOR2I:
		return DEFAULT_AMOUNT_SIZE

	var size: Vector2i = value

	return Vector2i(
		clampi(size.x, 0, MAX_BOX_PIXELS), clampi(size.y, 0, MAX_BOX_PIXELS))


## A saved box rect, or an empty one when the file holds something else.
##
## A negative position is legal and saved as it is. The pop-up clamps a rect
## into its pane on every open, so a box saved half off a wide window comes
## back inside a narrow one rather than being refused here.
func _clamp_box_rect(value: Variant) -> Rect2:
	if typeof(value) != TYPE_RECT2:
		return DEFAULT_POPUP_RECT

	var rect: Rect2 = value

	return Rect2(
		clampf(rect.position.x, -MAX_BOX_PIXELS, MAX_BOX_PIXELS),
		clampf(rect.position.y, -MAX_BOX_PIXELS, MAX_BOX_PIXELS),
		clampf(rect.size.x, 0.0, MAX_BOX_PIXELS),
		clampf(rect.size.y, 0.0, MAX_BOX_PIXELS))
