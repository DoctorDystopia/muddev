class_name LoadingVeil
extends PanelContainer
## The screen that stands over the world pane until the world is actually there.
##
## ## What it is for
##
## Godot's boot splash covers the ENGINE starting and is gone before the socket
## opens. [LoginView] covers everything up to a body existing. Between that body
## and a drawable world there was nothing at all — a pane that is empty, then
## half-built, then right, with every click in the window a real command about a
## world the player cannot see. This is that third screen.
##
## ## It covers the WORLD PANE, not the window
##
## Deliberately, and it is the main design decision here.
##
## A full-window veil would hide the game log, which is the one thing that IS
## working: the server's greeting, the MOTD, and any error explaining why the
## rest is slow all land there while this is up. Covering it would turn an
## informative wait into a blank one, and would take the text game away from a
## player who could already be playing it.
##
## What the veil actually buys is the click. The tile grid and the minimap both
## send real commands, and both live under `%WorldPane`; a `PanelContainer`
## filling that pane with the default `MOUSE_FILTER_STOP` eats the misclick that
## the loading window invites. The input box, the log and its tabs stay live.
##
## Hiding the 3D pane entirely (Options -> 3D) hides this with it, which is
## correct with no code: a player in text-only mode is waiting for nothing.
##
## ## Visibility is a function of the model
##
## The same contract [LoginView] answers, and for the same reason: the veil
## never decides for itself that it is finished, it asks
## [SessionReadiness]. Nothing here reads a channel, a socket or a loader.

## Emitted when the player asks to go in without waiting. The console relays it
## rather than this reaching into the model, so the view stays a view.
signal skip_requested

## What each phase says, in the player's terms rather than the feed's.
##
## PRESENTATION, and it lives here for the reason the whole client splits this
## way: [SessionReadiness] owns which fact is missing, this owns what that
## looks like. A phase with no entry falls back to the generic line rather than
## printing an enum name at somebody.
const PHASE_TEXT: Dictionary = {
	SessionReadiness.Phase.PLACING: "Finding you on the grid",
	SessionReadiness.Phase.MAPPING: "Assembling the map",
	SessionReadiness.Phase.ART: "Streaming the world in",
}

const FALLBACK_TEXT := "Loading"

## Appended to the phase line while models are actually in the air, so a stall
## is distinguishable from a slow queue. Singular and plural are both written
## out because "1 assets" is the kind of thing that makes a client look unfinished.
const ONE_ASSET := "%s — 1 asset left"
const MANY_ASSETS := "%s — %d assets left"

## The way out, offered only once the wait has stopped being normal.
const SKIP_TEXT := "Enter anyway"

## How long one full cycle of the pulse takes. Slow on purpose: a fast pulse
## reads as urgency, and nothing here is wrong.
const PULSE_SECONDS := 2.4

## How far the sigil dims at the bottom of the pulse.
const PULSE_FLOOR := 0.55

## The mark, at the size the veil draws it. The pane can be dragged small, so
## this is a ceiling rather than a fixed size; see [method _build].
const MARK_MAX_PX := 148.0

var _mark: TextureRect
var _label: Label
var _skip: Button
var _readiness: SessionReadiness

## Seconds since the veil appeared, for the pulse. Not the same clock as
## [SessionReadiness]'s: that one decides when to stop, this one only animates.
var _elapsed := 0.0


func _ready() -> void:
	_build()
	# Nothing to draw over until a phase says so, and the scene is authored
	# visible so the veil is visible in the editor while it is being laid out.
	visible = false
	set_process(false)


## Follow the model that decides when this is finished.
func bind(readiness: SessionReadiness) -> void:
	_readiness = readiness
	_readiness.changed.connect(_on_phase_changed)
	_on_phase_changed(_readiness.phase())


func _process(delta: float) -> void:
	_elapsed += delta

	# A sine over the alpha rather than a Tween: the veil's lifetime is decided
	# by the model and can end on any frame, and a Tween would have to be
	# created, tracked and killed to match. A value computed from elapsed time
	# needs none of that and is correct the instant drawing stops.
	var wave := (sin(_elapsed * TAU / PULSE_SECONDS) + 1.0) * 0.5
	_mark.modulate.a = PULSE_FLOOR + (1.0 - PULSE_FLOOR) * wave

	# Polled with the pulse rather than bound to a signal, because "the offer
	# has been open long enough" is a fact about TIME and the model publishes
	# only on a phase change -- which, in the stall this exists for, is exactly
	# what is not happening.
	if _readiness != null and not _skip.visible and _readiness.may_skip():
		_skip.visible = true

	_refresh_label()


# ─── Private ─────────────────────────────────────────────────────────────────

## Build the veil's contents in code.
##
## Built here rather than authored in `console.tscn` for the reason the console
## builds its panel bodies the same way: the contents depend on nothing in the
## scene, and a subtree the scene does not describe is one that cannot be
## broken by a scene edit. What the SCENE owns is where the veil sits and that
## it fills the pane, which is exactly the part `smoke_console` can check.
func _build() -> void:
	var column := VBoxContainer.new()
	column.alignment = BoxContainer.ALIGNMENT_CENTER
	column.add_theme_constant_override("separation", 18)
	add_child(column)

	_mark = TextureRect.new()
	_mark.texture = load("res://ui/blackout_mark.png")
	_mark.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_mark.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	# A ceiling, not a size. The world pane is one half of a draggable split and
	# can legitimately be narrower than the mark; EXPAND_IGNORE_SIZE drops the
	# texture's own 512px minimum so the control may shrink, and
	# KEEP_ASPECT_CENTERED scales the art down inside whatever is left rather
	# than forcing the pane wider than the player put it.
	#
	# The height is the only constrained axis. The width must stay FILL: with
	# EXPAND_IGNORE_SIZE the texture no longer contributes a minimum width
	# either, so SHRINK_CENTER collapses the control to zero pixels across and
	# the mark is simply never drawn -- which is exactly what the first render
	# of this screen showed, a label and no sigil.
	_mark.custom_minimum_size = Vector2(0, MARK_MAX_PX)
	_mark.size_flags_horizontal = Control.SIZE_FILL
	column.add_child(_mark)

	_label = Label.new()
	_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	column.add_child(_label)

	_skip = Button.new()
	_skip.text = SKIP_TEXT
	_skip.flat = true
	_skip.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	_skip.visible = false
	_skip.pressed.connect(func(): skip_requested.emit())
	column.add_child(_skip)


func _on_phase_changed(phase: SessionReadiness.Phase) -> void:
	var loading := SessionReadiness.is_loading(phase)

	visible = loading
	set_process(loading)

	if not loading:
		return

	_refresh_label()


## Write the phase line, with a count when there is one worth showing.
##
## Re-read every frame rather than written once per phase change: ART is a
## single phase that can last seconds while the number under it falls, and a
## label written only on the transition would freeze on whatever the count
## happened to be when the phase began.
func _refresh_label() -> void:
	if _readiness == null:
		return

	var base: String = PHASE_TEXT.get(_readiness.phase(), FALLBACK_TEXT)
	var outstanding := _readiness.in_flight()

	if outstanding == 1:
		_label.text = ONE_ASSET % base
	elif outstanding > 1:
		_label.text = MANY_ASSETS % [base, outstanding]
	else:
		_label.text = base
