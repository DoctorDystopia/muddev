class_name XpHudView
extends Control
## XP drops, the session tracker, and the progress bar, beside the minimap.
## Drawn from [XpTrackerState], with the level-up line from [SkillsState].
##
## ## Beside the minimap, right-aligned against it
##
## Where OSRS keeps its XP counter: by the map, in the corner a player already
## glances at. The scene anchors this control to the pane's top-right, ending
## just left of the minimap, and every row inside it is right-aligned so the
## strip, the bar and the drops all hug the map's edge. Top-middle was tried
## first and moved on 09/13/2026 -- it put a readout over the part of the world
## a player is actually looking at.
##
## ## What it looks like, and whose call that is
##
## One card. Its top line reads `session 12,345 xp   3,420 xp/hr`. Under it is a
## continuous bar for the skill just trained, and under the bar is
## `strike 42 → 43 · 1,120 to go`. Under the card, when the player asks for it,
## is XP per hour for each skill this session. Each award rises into the bottom
## of that column as one row -- `+25 Butchery +5 Cutting` -- and fades, the way
## OSRS's drops rise into its counter.
##
## The bar is continuous, like the HP bar in [VitalsBars], and it glides to each
## new value. A level-up glides it to full, then it fills again from empty. The
## top edge of the card and the bar take the colour of the skill category.
##
## The client owns every colour, size and duration here. The server sends an
## award and the progress of each skill. The client chooses a bar, not a ring.
## That choice is a look, and thus the script generates nothing below.
##
## ## It never takes a click
##
## The HUD sits over the 3D world, and every node in it ignores the mouse. A
## tracker that swallowed a click would eat a move meant for the tile under it
## -- the rule [VitalsBars] follows for the same reason.
##
## ## Hidden until there is something to show
##
## Before the first award of a session the column is not drawn at all. An empty
## strip reading "session 0 xp" at login is a readout of nothing, and it would
## sit over the world for every player who never opens a fight.
##
## Whether it is drawn at all is the player's setting, applied by the console
## like every other preference; see [method set_skill_rates_shown].

## Presentation constants. All of them are the client's.
const FONT_SIZE := 12
const DROP_FONT_SIZE := 13
const STRIP_SEPARATION := 14
const COLUMN_SEPARATION := 4

## The card that holds the strip, the bar and the next-level line.
const CARD_SEPARATION := 5
const CARD_MARGIN_X := 12.0
const CARD_MARGIN_Y := 6.0
const CARD_ACCENT_WIDTH := 2
const CARD_CORNER := 3
const CARD_SHADOW_SIZE := 6

## The progress bar. The sheen is a pale band on the top part of the fill. The
## head is a bright line at the front edge of the fill.
const BAR_WIDTH := 220.0
const BAR_HEIGHT := 8.0
const BAR_CORNER := 2
const BAR_EDGE_WIDTH := 1
const BAR_SHEEN_SHARE := 0.5
const BAR_HEAD_WIDTH := 2.0
const BAR_HEAD_LIGHTEN := 0.55

## How long the bar takes to glide to a new value. A level-up takes two glides.
const BAR_GLIDE_SECONDS := 0.45

## How far a drop rises, and how long it takes to rise and fade.
const DROP_RISE_PIXELS := 42.0
const DROP_SECONDS := 1.3

## The least time between two drops starting to rise, and the most a drop will
## wait for its turn.
##
## Two awards on one tick -- a swing and an aura pulse, a fight and a cure
## coming due -- would otherwise start at the same pixel and print one on top
## of the other. Queued, they rise one behind the next, the way OSRS stacks its
## drops. The cap is what stops a long backlog drawing an award seconds after
## the log printed it: past it, a drop rises now and overlaps rather than lags.
const DROP_SPACING_SECONDS := 0.35
const DROP_MAX_DELAY_SECONDS := 1.5

## How long the level-up line holds before it fades, and how long the fade is.
const FLARE_HOLD_SECONDS := 1.4
const FLARE_FADE_SECONDS := 0.6

## How often the rates are redrawn with no award arriving. A rate moves with the
## clock, so a tracker that redrew only on an award would show a player who
## stopped fighting the rate they had while they were.
const RATE_REFRESH_SECONDS := 1.0

const COLOR_ACCENT := Color("5dcaa5")
const COLOR_PANEL := Color(0.04, 0.055, 0.075, 0.88)
const COLOR_VALUE := Color(1, 1, 1)
const COLOR_DIM := Color(0.7, 0.74, 0.79)
const COLOR_TRACK := Color("141c25")
const COLOR_TRACK_EDGE := Color("2a3847")
const COLOR_SHEEN := Color(1, 1, 1, 0.22)
const COLOR_SHADOW := Color(0, 0, 0, 0.35)

const TOTAL_TEXT := "session %s xp"
const RATE_TEXT := "%s xp/hr"
const NO_RATE_TEXT := "--"
const NEXT_TEXT := "%s %d → %d · %s to go"
const CAPPED_TEXT := "%s %d · max"
const LEVEL_UP_TEXT := "level up // %s %d"
const DROP_TEXT := "+%s %s"
const SKILL_XP_TEXT := "%s xp"

var _tracker: XpTrackerState
var _skills: SkillsState

var _column: VBoxContainer
var _card_style: StyleBoxFlat
var _total_label: Label
var _rate_label: Label
var _bar: Control
var _next_label: Label

## The styles of the bar. The fill colour changes with the skill, so the view keeps
## the boxes and sets the colour at each draw.
var _track_style: StyleBoxFlat
var _fill_style: StyleBoxFlat
var _sheen_style: StyleBoxFlat

## The fraction that the bar shows now, and the skill, level and fraction that
## it glides to. A change of skill or level decides the shape of the glide.
var _bar_shown := 0.0
var _bar_key := ""
var _bar_level := -1
var _bar_target := 0.0
var _bar_tween: Tween
var _flare_label: Label
var _rates: GridContainer
var _drops: Control
var _flare_tween: Tween

## When, in seconds of engine time, the next drop may start rising.
var _drop_free_at := 0.0

## The theme's monospace face, looked up once the HUD is in the tree. Null
## until then, and every label made before that is given it in [method _ready].
var _font: Font
var _labels: Array[Label] = []


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE

	_column = VBoxContainer.new()
	_column.set_anchors_preset(Control.PRESET_TOP_WIDE)
	_column.add_theme_constant_override("separation", COLUMN_SEPARATION)
	_column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_column.visible = false
	add_child(_column)

	_column.add_child(_build_card())

	_flare_label = _label(COLOR_ACCENT, FONT_SIZE)
	_flare_label.size_flags_horizontal = Control.SIZE_SHRINK_END
	_flare_label.modulate.a = 0.0
	_column.add_child(_flare_label)

	_rates = GridContainer.new()
	_rates.columns = 3
	_rates.add_theme_constant_override("h_separation", STRIP_SEPARATION)
	_rates.size_flags_horizontal = Control.SIZE_SHRINK_END
	_rates.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_rates.visible = false
	_column.add_child(_rates)

	# The LAST row of the column, not a layer over the whole HUD. A drop rises
	# inside this band to its top edge, so it always comes to rest under
	# whatever the column holds above it -- including per-skill rates that were
	# only added this frame. Measuring the column instead read its minimum size
	# before layout had caught up, and drops landed on top of the rate rows.
	_drops = Control.new()
	_drops.custom_minimum_size = Vector2(0.0, DROP_RISE_PIXELS + DROP_FONT_SIZE * 2)
	_drops.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_column.add_child(_drops)

	var refresh := Timer.new()
	refresh.wait_time = RATE_REFRESH_SECONDS
	refresh.autostart = true
	refresh.timeout.connect(_on_refresh)
	add_child(refresh)


func _ready() -> void:
	# Plain strings, not StringName literals: test_theme reads every `&"..."` in
	# a script as a theme variation, and "normal_font" is a font slot, not one.
	_font = get_theme_font("normal_font", "ChatLog")

	for label: Label in _labels:
		label.add_theme_font_override("font", _font)


## Bind to the session and the roster, and follow both.
##
## The ROSTER is here for the level-up line alone. [signal SkillsState.levelled]
## is the one owner of "a level rose" -- the sound cue hangs off it too -- and a
## second comparison of levels on the award payload would be a second answer
## that could disagree with the first.
func bind(tracker: XpTrackerState, skills: SkillsState) -> void:
	_tracker = tracker
	_skills = skills
	_tracker.changed.connect(_redraw)
	_tracker.dropped.connect(_spawn_drop)
	_skills.levelled.connect(_flare)
	_redraw()


## Show or hide XP per hour for each skill. The console calls this from the
## player's setting; the view keeps no copy of the setting itself.
func set_skill_rates_shown(shown: bool) -> void:
	_rates.visible = shown


## The part of the level that the bar glides to, from 0.0 to 1.0. Public so a
## test can read the bar with no render and no wait for the glide.
func bar_fraction() -> float:
	return _bar_target


## The glides that take the bar from [param shown] to [param target], as
## `[from, to]` pairs. Static and pure, so a test reads the rule with no tween.
##
## A new skill fills from empty: its bar never held the value of the old skill.
## A level rise fills to the end, then fills again from empty. Everything else
## is one glide from where the bar is now.
static func glide_legs(shown: float, target: float, same_skill: bool,
		level_rose: bool) -> Array:
	if not same_skill:
		return [[0.0, target]]

	if level_rose:
		return [[shown, 1.0], [0.0, target]]

	return [[shown, target]]


## How long a drop arriving at [param now] waits before it rises, given the
## queue is free again at [param free_at]. Static and pure so the queue rule is
## tested with no clock and no tween.
static func queued_delay(now: float, free_at: float) -> float:
	return clampf(free_at - now, 0.0, DROP_MAX_DELAY_SECONDS)


## A whole number with thousands separators: 12345 -> "12,345".
static func thousands(value: int) -> String:
	var digits := str(absi(value))
	var grouped := ""
	var count := 0

	for index: int in range(digits.length() - 1, -1, -1):
		grouped = digits[index] + grouped
		count += 1

		if count % 3 == 0 and index > 0:
			grouped = "," + grouped

	if value < 0:
		return "-" + grouped

	return grouped


## The card: the session strip, the bar, and the next-level line, in one panel.
func _build_card() -> PanelContainer:
	_card_style = StyleBoxFlat.new()
	_card_style.bg_color = COLOR_PANEL
	_card_style.border_color = COLOR_ACCENT
	_card_style.border_width_top = CARD_ACCENT_WIDTH
	_card_style.set_corner_radius_all(CARD_CORNER)
	_card_style.shadow_color = COLOR_SHADOW
	_card_style.shadow_size = CARD_SHADOW_SIZE
	_card_style.content_margin_left = CARD_MARGIN_X
	_card_style.content_margin_right = CARD_MARGIN_X
	_card_style.content_margin_top = CARD_MARGIN_Y
	_card_style.content_margin_bottom = CARD_MARGIN_Y

	var card := PanelContainer.new()
	card.add_theme_stylebox_override("panel", _card_style)
	card.size_flags_horizontal = Control.SIZE_SHRINK_END
	card.mouse_filter = Control.MOUSE_FILTER_IGNORE

	var body := VBoxContainer.new()
	body.add_theme_constant_override("separation", CARD_SEPARATION)
	body.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_child(body)

	body.add_child(_build_strip())
	body.add_child(_build_bar())

	_next_label = _label(COLOR_DIM, FONT_SIZE)
	body.add_child(_next_label)

	return card


## The session total on the left and the rate on the right.
func _build_strip() -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", STRIP_SEPARATION)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE

	_total_label = _label(COLOR_VALUE, FONT_SIZE)
	_total_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(_total_label)
	_rate_label = _label(COLOR_DIM, FONT_SIZE)
	row.add_child(_rate_label)

	return row


func _build_bar() -> Control:
	_track_style = StyleBoxFlat.new()
	_track_style.bg_color = COLOR_TRACK
	_track_style.border_color = COLOR_TRACK_EDGE
	_track_style.set_border_width_all(BAR_EDGE_WIDTH)
	_track_style.set_corner_radius_all(BAR_CORNER)

	_fill_style = StyleBoxFlat.new()
	_fill_style.set_corner_radius_all(BAR_CORNER)

	_sheen_style = StyleBoxFlat.new()
	_sheen_style.bg_color = COLOR_SHEEN
	_sheen_style.corner_radius_top_left = BAR_CORNER
	_sheen_style.corner_radius_top_right = BAR_CORNER

	_bar = Control.new()
	_bar.custom_minimum_size = Vector2(BAR_WIDTH, BAR_HEIGHT)
	_bar.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_bar.draw.connect(_draw_bar)

	return _bar


func _redraw() -> void:
	if _tracker == null:
		return

	_column.visible = _tracker.has_data

	if not _tracker.has_data:
		_clear(_rates)
		_reset_bar()
		return

	var focus := _tracker.focus_row()

	_total_label.text = TOTAL_TEXT % thousands(_tracker.total_xp)
	_rate_label.text = RATE_TEXT % _rate_text(_tracker.session_rate())
	_next_label.text = _next_text(focus)
	_card_style.border_color = _category_colour(focus)
	_follow_bar(focus)
	_redraw_rates()


## Start a glide when the focus skill, its level or its fraction moved. The
## clock redraw calls this every second, and then nothing moved.
func _follow_bar(row: Dictionary) -> void:
	var key := str(row.get("skill_key", ""))
	var level := int(row.get("level", 0))
	var target := SkillsState.level_fraction(row) if not row.is_empty() else 0.0
	var moved := key != _bar_key or level != _bar_level \
		or not is_equal_approx(target, _bar_target)

	if not moved:
		return

	var same_skill := key == _bar_key
	var level_rose := same_skill and level > _bar_level
	var legs := glide_legs(_bar_shown, target, same_skill, level_rose)

	_bar_key = key
	_bar_level = level
	_bar_target = target
	_glide(legs)


func _glide(legs: Array) -> void:
	if _bar_tween != null:
		_bar_tween.kill()

	if not is_inside_tree():
		_set_bar_shown(legs.back()[1])
		return

	_bar_tween = create_tween()

	for leg: Array in legs:
		_bar_tween.tween_method(_set_bar_shown, leg[0], leg[1], BAR_GLIDE_SECONDS) \
			.set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)


func _set_bar_shown(fraction: float) -> void:
	_bar_shown = fraction
	_bar.queue_redraw()


## A new session: the first award fills the bar from empty.
func _reset_bar() -> void:
	if _bar_tween != null:
		_bar_tween.kill()

	_bar_key = ""
	_bar_level = -1
	_bar_target = 0.0
	_set_bar_shown(0.0)


## The clock moved. Only the rates depend on it, and only a drawn HUD needs them.
func _on_refresh() -> void:
	if not is_visible_in_tree() or _tracker == null or not _tracker.has_data:
		return

	_redraw()


func _redraw_rates() -> void:
	_clear(_rates)

	for row: Dictionary in _tracker.skill_rows():
		var colour := SkillPalette.color_for(str(row.get("category", "")))
		var key := str(row.get("skill_key", ""))

		_rates.add_child(_label_with(str(row.get("name", key)), colour))
		_rates.add_child(_label_with(
			SKILL_XP_TEXT % thousands(int(row.get("xp", 0))), COLOR_DIM))
		_rates.add_child(_label_with(
			RATE_TEXT % _rate_text(_tracker.skill_rate(key)), COLOR_DIM))


## The track, then the fill, the sheen on the fill, and the head of the fill.
func _draw_bar() -> void:
	var track := Rect2(Vector2.ZERO, _bar.size)
	var width := roundf(track.size.x * clampf(_bar_shown, 0.0, 1.0))

	_bar.draw_style_box(_track_style, track)

	if width <= 0.0:
		return

	var row := _tracker.focus_row() if _tracker != null else {}
	var colour := _category_colour(row)
	var height := track.size.y

	_fill_style.bg_color = colour
	_bar.draw_style_box(_fill_style, Rect2(0.0, 0.0, width, height))
	_bar.draw_style_box(_sheen_style,
		Rect2(0.0, 0.0, width, height * BAR_SHEEN_SHARE))

	if width < track.size.x:
		var head_x := maxf(width - BAR_HEAD_WIDTH, 0.0)
		var head := Rect2(head_x, 0.0, BAR_HEAD_WIDTH, height)
		_bar.draw_rect(head, colour.lightened(BAR_HEAD_LIGHTEN))


## The colour of the skill category. With no skill yet, the HUD accent.
func _category_colour(row: Dictionary) -> Color:
	if row.is_empty():
		return COLOR_ACCENT

	return SkillPalette.color_for(str(row.get("category", "")))


## One award, rising into the bottom of the column and fading.
##
## One ROW per award rather than one per skill, because that is how it was
## earned and how the log line prints it. Each skill is coloured by its
## category, so a fight's two combat skills read as one colour and a butcher's
## Butchery and Cutting read as the same band they sit in on the Skills tab.
func _spawn_drop(_kind: String, awards: Array) -> void:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", STRIP_SEPARATION)
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE

	for award: Dictionary in awards:
		var text := DROP_TEXT % [thousands(int(award["amount"])), award["name"]]
		var colour := SkillPalette.color_for(str(award["category"]))
		row.add_child(_label(colour, DROP_FONT_SIZE, text))

	_drops.add_child(row)

	# Right-aligned on the HUD's own width, which the scene anchors, rather than
	# the band's: the band may not have been laid out yet on the first award.
	var width := row.get_combined_minimum_size().x
	row.position = Vector2(size.x - width, DROP_RISE_PIXELS)

	if not is_inside_tree():
		return

	var now := Time.get_ticks_msec() / 1000.0
	var delay := queued_delay(now, _drop_free_at)
	_drop_free_at = now + delay + DROP_SPACING_SECONDS

	var tween := row.create_tween()

	# A queued drop is hidden where it will start, then shown as its turn comes,
	# so it never sits visibly on top of the drop ahead of it.
	if delay > 0.0:
		row.modulate.a = 0.0
		tween.tween_interval(delay)
		tween.tween_callback(func(): row.modulate.a = 1.0)

	tween.tween_property(row, "position:y", 0.0, DROP_SECONDS) \
		.set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tween.parallel().tween_property(row, "modulate:a", 0.0, DROP_SECONDS) \
		.set_ease(Tween.EASE_IN)
	tween.tween_callback(row.queue_free)


## A level rose: say so under the bar, then fade.
func _flare(skill_key: String, level: int) -> void:
	_flare_label.text = LEVEL_UP_TEXT % [_skill_name(skill_key).to_lower(), level]
	_flare_label.modulate.a = 1.0

	if not is_inside_tree():
		return

	if _flare_tween != null:
		_flare_tween.kill()

	_flare_tween = create_tween()
	_flare_tween.tween_interval(FLARE_HOLD_SECONDS)
	_flare_tween.tween_property(_flare_label, "modulate:a", 0.0, FLARE_FADE_SECONDS)


## The name the roster gives a skill, else the name its latest award gave it,
## else the key -- so a level-up line always says something readable.
func _skill_name(skill_key: String) -> String:
	var row := _skills.row_for(skill_key) if _skills != null else {}

	if not row.is_empty():
		return str(row["name"])

	for tracked: Dictionary in _tracker.skill_rows():
		if str(tracked["skill_key"]) == skill_key:
			return str(tracked["name"])

	return skill_key


func _next_text(row: Dictionary) -> String:
	if row.is_empty():
		return ""

	var name := str(row.get("name", "")).to_lower()
	var level := int(row.get("level", 0))
	var needed := int(row.get("needed_xp", 0))

	if needed <= 0:
		return CAPPED_TEXT % [name, level]

	var remaining := needed - int(row.get("current_xp", 0))

	return NEXT_TEXT % [name, level, level + 1, thousands(maxi(remaining, 0))]


static func _rate_text(rate: int) -> String:
	if rate == XpTrackerState.NO_RATE:
		return NO_RATE_TEXT

	return thousands(rate)


func _label(colour: Color, font_size: int, text: String = "") -> Label:
	var label := Label.new()
	label.text = text
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.add_theme_color_override("font_color", colour)
	label.add_theme_font_size_override("font_size", font_size)

	if _font != null:
		label.add_theme_font_override("font", _font)
	else:
		_labels.append(label)

	return label


func _label_with(text: String, colour: Color) -> Label:
	return _label(colour, FONT_SIZE, text)


## Empty a container NOW, without leaving its old children in the layout.
##
## `remove_child` before `queue_free`, for the reason [SkillsView] gives: the
## rows are rebuilt every second, and two generations sharing a frame would
## double the grid for that frame.
func _clear(container: Node) -> void:
	for child: Node in container.get_children():
		container.remove_child(child)
		child.queue_free()
