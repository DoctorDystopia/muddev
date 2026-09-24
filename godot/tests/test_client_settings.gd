extends Node
## Unit tests for ClientSettings. Writes to a disposable user:// path rather
## than the real profile.
##
##     godot --headless --path godot res://tests/test_client_settings.tscn

const TEST_PATH := "user://test_client_settings.cfg"

var _failures := 0


func _ready() -> void:
	_clean()

	_defaults_apply_when_there_is_no_file()
	_a_choice_survives_a_reload()
	_values_are_clamped_on_the_way_in()
	_a_corrupt_file_falls_back_rather_than_failing()
	_reset_restores_the_shipped_defaults()
	_changed_fires_for_a_real_change_only()
	_the_two_panes_toggle_independently()
	_the_panel_dock_size_is_remembered_and_fenced()
	_each_dock_keeps_its_own_size()
	_an_unknown_skill_detail_mode_falls_back_rather_than_breaking_the_grid()
	_the_sfx_volume_persists_clamps_and_resets()
	_the_xp_tracker_toggles_persist_and_reset()
	_the_movement_animation_persists_and_resets()
	_a_box_the_player_sized_is_remembered()
	_a_box_size_from_a_bad_file_falls_back()
	_the_screen_gives_the_first_scale()

	_clean()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: client_settings")
	get_tree().quit(0)


func _clean() -> void:
	if FileAccess.file_exists(TEST_PATH):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(TEST_PATH))


func _defaults_apply_when_there_is_no_file() -> void:
	# First run is the normal case, not an error.
	_clean()
	var s := ClientSettings.new(TEST_PATH)
	s.load_from_disk()

	_expect(s.font_size == ClientSettings.DEFAULT_FONT_SIZE, "default font size")
	_expect(is_equal_approx(s.ui_scale, ClientSettings.DEFAULT_UI_SCALE),
		"default ui scale")


func _a_choice_survives_a_reload() -> void:
	_clean()
	var first := ClientSettings.new(TEST_PATH)
	first.set_font_size(18)
	first.set_ui_scale(1.25)

	var second := ClientSettings.new(TEST_PATH)
	second.load_from_disk()

	_expect(second.font_size == 18, "font size persists")
	_expect(is_equal_approx(second.ui_scale, 1.25), "ui scale persists")


func _values_are_clamped_on_the_way_in() -> void:
	# A font of size 0 or a 40x scale renders a client the player cannot use to
	# fix the setting that broke it.
	var s := ClientSettings.new(TEST_PATH)

	s.set_font_size(0)
	_expect(s.font_size == ClientSettings.MIN_FONT_SIZE, "a tiny font is clamped up")

	s.set_font_size(9999)
	_expect(s.font_size == ClientSettings.MAX_FONT_SIZE, "a huge font is clamped down")

	s.set_ui_scale(40.0)
	_expect(is_equal_approx(s.ui_scale, ClientSettings.MAX_UI_SCALE),
		"a runaway scale is clamped")


func _a_corrupt_file_falls_back_rather_than_failing() -> void:
	# Clamping on READ, not only on write, is what makes an unusable client
	# unreachable even from a hand-edited config.
	_clean()
	var handle := FileAccess.open(TEST_PATH, FileAccess.WRITE)
	handle.store_string("[display]\nfont_size=0\nui_scale=99.0\n")
	handle.close()

	var s := ClientSettings.new(TEST_PATH)
	s.load_from_disk()

	_expect(s.font_size == ClientSettings.MIN_FONT_SIZE,
		"an out-of-range saved font is clamped on load")
	_expect(is_equal_approx(s.ui_scale, ClientSettings.MAX_UI_SCALE),
		"and so is the scale")


func _reset_restores_the_shipped_defaults() -> void:
	var s := ClientSettings.new(TEST_PATH)
	s.set_font_size(ClientSettings.MAX_FONT_SIZE)
	s.reset()

	_expect(s.font_size == ClientSettings.DEFAULT_FONT_SIZE, "reset restores the font")

	var reloaded := ClientSettings.new(TEST_PATH)
	reloaded.load_from_disk()
	_expect(reloaded.font_size == ClientSettings.DEFAULT_FONT_SIZE,
		"and the reset was written, not just held in memory")

	s.set_show_inventory(false)
	s.set_dock_size(ClientSettings.KEY_CONSOLE_SIZE, Vector2i(500, 300))
	s.set_skill_detail(ClientSettings.SKILL_DETAIL_LOG)
	s.reset()
	_expect(s.show_inventory == ClientSettings.DEFAULT_SHOW_INVENTORY,
		"reset restores the pane toggles")
	_expect(s.console_size == ClientSettings.DEFAULT_CONSOLE_SIZE,
		"and the dock sizes")
	_expect(s.skill_detail == ClientSettings.DEFAULT_SKILL_DETAIL,
		"and where skill detail is shown")


func _changed_fires_for_a_real_change_only() -> void:
	# Every consumer redraws on this signal; firing it for a no-op set would
	# rebuild the log's fonts on every slider tick that changed nothing.
	var s := ClientSettings.new(TEST_PATH)
	s.set_font_size(16)

	var count := {"n": 0}
	s.changed.connect(func(): count["n"] += 1)

	s.set_font_size(16)
	_expect(count["n"] == 0, "setting the same value fires nothing")

	s.set_font_size(17)
	_expect(count["n"] == 1, "a real change fires once")


## The world pane and the inventory were one bool until 08/28/2026, so a player
## who wanted the bag without the diorama could have neither.
func _the_two_panes_toggle_independently() -> void:
	_clean()
	var s := ClientSettings.new(TEST_PATH)
	s.set_show_world(false)

	_expect(not s.show_world, "the world can be turned off")
	_expect(s.show_inventory, "without taking the inventory with it")

	var reloaded := ClientSettings.new(TEST_PATH)
	reloaded.load_from_disk()
	_expect(not reloaded.show_world and reloaded.show_inventory,
		"and both survive a reload")


## The control panel was the bottom half of a VSplitContainer until 09/21/2026,
## so its height was the `world_split` offset this case replaces. It hangs in
## [PanelDock] now, and the player sizes it in both axes.
func _the_panel_dock_size_is_remembered_and_fenced() -> void:
	_clean()
	var s := ClientSettings.new(TEST_PATH)

	_expect(s.panel_size == Vector2i.ZERO,
		"no remembered dock until the player drags one")

	s.set_dock_size(ClientSettings.KEY_PANEL_SIZE, Vector2i(640, 480))

	var reloaded := ClientSettings.new(TEST_PATH)
	reloaded.load_from_disk()
	_expect(reloaded.panel_size == Vector2i(640, 480), "the dock size persists")

	# Fenced rather than made usable. Keeping the box on screen and no smaller
	# than its content is PanelDock._place_box's job, and it does that on every
	# layout pass. A second rule here would be a second owner of it.
	reloaded.set_dock_size(ClientSettings.KEY_PANEL_SIZE, Vector2i(99999, 99999))
	_expect(reloaded.panel_size
		== Vector2i(ClientSettings.MAX_BOX_PIXELS, ClientSettings.MAX_BOX_PIXELS),
		"and a runaway size is fenced")

	reloaded.reset()
	_expect(reloaded.panel_size == ClientSettings.DEFAULT_PANEL_SIZE,
		"reset forgets the dock")


## Two docks share one setter, so a write to one key must not reach the other.
## An unknown key writes nothing, and it reads as "never dragged".
func _each_dock_keeps_its_own_size() -> void:
	_clean()
	var s := ClientSettings.new(TEST_PATH)
	s.set_dock_size(ClientSettings.KEY_CONSOLE_SIZE, Vector2i(420, 260))

	var reloaded := ClientSettings.new(TEST_PATH)
	reloaded.load_from_disk()
	_expect(reloaded.dock_size(ClientSettings.KEY_CONSOLE_SIZE)
		== Vector2i(420, 260), "the log dock size persists")
	_expect(reloaded.dock_size(ClientSettings.KEY_PANEL_SIZE) == Vector2i.ZERO,
		"and the panel dock keeps its own size")

	var count := {"n": 0}
	reloaded.changed.connect(func(): count["n"] += 1)
	reloaded.set_dock_size("font_size", Vector2i(10, 10))
	_expect(count["n"] == 0 and reloaded.font_size == ClientSettings.DEFAULT_FONT_SIZE,
		"a key that names no dock writes nothing")
	_expect(reloaded.dock_size("font_size") == Vector2i.ZERO,
		"and reads as never dragged")


func _an_unknown_skill_detail_mode_falls_back_rather_than_breaking_the_grid() -> void:
	# Clamped on READ as well as on write, which is the same rule the font size
	# follows and for a sharper reason: a mode outside the three would leave
	# every click in the skills grid doing nothing, and a grid that ignores
	# clicks reads as broken rather than as a setting somebody can undo.
	var config := ConfigFile.new()
	config.set_value(ClientSettings.SECTION,
		ClientSettings.KEY_SKILL_DETAIL, "somewhere_else")
	config.save(TEST_PATH)

	var s := ClientSettings.new(TEST_PATH)
	s.load_from_disk()

	_expect(s.skill_detail == ClientSettings.DEFAULT_SKILL_DETAIL,
		"a mode written by hand or by an older build falls back")

	s.set_skill_detail("nonsense")
	_expect(s.skill_detail == ClientSettings.DEFAULT_SKILL_DETAIL,
		"and so does one set through the setter")

	s.set_skill_detail(ClientSettings.SKILL_DETAIL_LOG)
	_expect(not s.skill_detail_in_pane(), "log mode opens no sheet")
	_expect(s.skill_detail_in_log(), "and prints one")

	s.set_skill_detail(ClientSettings.SKILL_DETAIL_PANE)
	_expect(s.skill_detail_in_pane(), "pane mode opens a sheet")
	_expect(not s.skill_detail_in_log(), "and prints none")

	s.set_skill_detail(ClientSettings.SKILL_DETAIL_BOTH)
	_expect(s.skill_detail_in_pane() and s.skill_detail_in_log(),
		"and both does both")

	_clean()


func _the_sfx_volume_persists_clamps_and_resets() -> void:
	_clean()
	var s := ClientSettings.new(TEST_PATH)
	_expect(is_equal_approx(s.sfx_volume, ClientSettings.DEFAULT_SFX_VOLUME),
		"default sound effects volume")

	s.set_sfx_volume(0.3)
	var reloaded := ClientSettings.new(TEST_PATH)
	reloaded.load_from_disk()
	_expect(is_equal_approx(reloaded.sfx_volume, 0.3), "the volume persists")

	s.set_sfx_volume(0.0)
	_expect(is_equal_approx(s.sfx_volume, 0.0),
		"silent is a real setting, not clamped away")

	s.set_sfx_volume(5.0)
	_expect(is_equal_approx(s.sfx_volume, ClientSettings.MAX_SFX_VOLUME),
		"a boost above the mix is clamped down")

	s.set_sfx_volume(-1.0)
	_expect(is_equal_approx(s.sfx_volume, ClientSettings.MIN_SFX_VOLUME),
		"a negative volume is clamped up")

	# Clamped on READ, like every other value here.
	var handle := FileAccess.open(TEST_PATH, FileAccess.WRITE)
	handle.store_string("[audio]\nsfx_volume=7.0\n")
	handle.close()

	var repaired := ClientSettings.new(TEST_PATH)
	repaired.load_from_disk()
	_expect(is_equal_approx(repaired.sfx_volume, ClientSettings.MAX_SFX_VOLUME),
		"an out-of-range saved volume is clamped on load")

	repaired.reset()
	_expect(is_equal_approx(repaired.sfx_volume, ClientSettings.DEFAULT_SFX_VOLUME),
		"and reset restores the default")

	_clean()


func _the_xp_tracker_toggles_persist_and_reset() -> void:
	_clean()
	var s := ClientSettings.new(TEST_PATH)

	_expect(s.show_xp_drops, "XP drops are on by default")
	_expect(not s.show_skill_rates, "per-skill rates are off by default")

	s.set_show_xp_drops(false)
	s.set_show_skill_rates(true)

	var reloaded := ClientSettings.new(TEST_PATH)
	reloaded.load_from_disk()
	_expect(not reloaded.show_xp_drops, "hiding the drops persists")
	_expect(reloaded.show_skill_rates, "and so does asking for per-skill rates")

	reloaded.reset()
	_expect(reloaded.show_xp_drops == ClientSettings.DEFAULT_SHOW_XP_DROPS
		and reloaded.show_skill_rates == ClientSettings.DEFAULT_SHOW_SKILL_RATES,
		"and reset restores both")

	_clean()


## On by default, because a step drawn as a jump is what the client did before
## the animation existed and it reads as teleporting. A player who wants that
## back has to be able to keep it between runs.
func _the_movement_animation_persists_and_resets() -> void:
	_clean()
	var s := ClientSettings.new(TEST_PATH)

	_expect(s.smooth_movement, "figures slide between tiles by default")

	s.set_smooth_movement(false)

	var reloaded := ClientSettings.new(TEST_PATH)
	reloaded.load_from_disk()
	_expect(not reloaded.smooth_movement, "turning the animation off persists")

	reloaded.reset()
	_expect(reloaded.smooth_movement == ClientSettings.DEFAULT_SMOOTH_MOVEMENT,
		"and reset restores it")

	_clean()


## The amount box and the pop-up box are built fresh every time they open, so
## the size the player dragged them to has nowhere to live but this file. Both
## were forgotten on every close before 09/21/2026.
func _a_box_the_player_sized_is_remembered() -> void:
	_clean()
	var s := ClientSettings.new(TEST_PATH)

	_expect(s.amount_size == Vector2i.ZERO,
		"no remembered amount box until the player sizes one")
	_expect(not s.popup_rect.has_area(),
		"and no remembered pop-up box until a drag")

	s.set_amount_size(Vector2i(420, 260))
	s.set_popup_rect(Rect2(40, 60, 700, 500))

	var reloaded := ClientSettings.new(TEST_PATH)
	reloaded.load_from_disk()
	_expect(reloaded.amount_size == Vector2i(420, 260),
		"the amount box size persists")
	_expect(reloaded.popup_rect == Rect2(40, 60, 700, 500),
		"and so does the whole pop-up rect, position included")

	# A box dragged off the top-left of the pane. Kept as it is: the pop-up
	# clamps a rect into the pane it has on every open, and a second rule here
	# would be a second owner of that.
	reloaded.set_popup_rect(Rect2(-50, -20, 300, 200))
	_expect(reloaded.popup_rect.position == Vector2(-50, -20),
		"a negative position is a real rect, not clamped away")

	reloaded.set_amount_size(Vector2i(99999, 99999))
	_expect(reloaded.amount_size
		== Vector2i(ClientSettings.MAX_BOX_PIXELS, ClientSettings.MAX_BOX_PIXELS),
		"a runaway size is fenced")

	reloaded.reset()
	_expect(reloaded.amount_size == ClientSettings.DEFAULT_AMOUNT_SIZE
		and reloaded.popup_rect == ClientSettings.DEFAULT_POPUP_RECT,
		"and reset forgets both boxes")

	_clean()


## Clamped on READ, like every other value here, and by TYPE as well as by
## range: [ConfigFile] gives back whatever Variant it stored, and these two are
## the first values in the file that are not a number, a bool or a string.
func _a_box_size_from_a_bad_file_falls_back() -> void:
	_clean()
	var config := ConfigFile.new()
	config.set_value(ClientSettings.SECTION,
		ClientSettings.KEY_AMOUNT_SIZE, "420x260")
	config.set_value(ClientSettings.SECTION,
		ClientSettings.KEY_POPUP_RECT, 7)
	config.save(TEST_PATH)

	var s := ClientSettings.new(TEST_PATH)
	s.load_from_disk()

	_expect(s.amount_size == ClientSettings.DEFAULT_AMOUNT_SIZE,
		"a size of the wrong type gives the wrapped box back")
	_expect(s.popup_rect == ClientSettings.DEFAULT_POPUP_RECT,
		"and a rect of the wrong type gives the centred box back")

	_clean()


## A dense screen opens at a scale that suits it, not at half size. A scale in
## the file wins, and Reset goes back to the scale of the screen.
func _the_screen_gives_the_first_scale() -> void:
	var reference := int(ClientSettings.REFERENCE_DPI)

	_expect(is_equal_approx(ClientSettings.ui_scale_for_dpi(reference), 1.0),
		"a screen at the reference density gives a scale of 1")
	_expect(is_equal_approx(ClientSettings.ui_scale_for_dpi(reference * 3 / 2), 1.5),
		"a screen at one and a half times it gives 1.5")
	_expect(is_equal_approx(ClientSettings.ui_scale_for_dpi(reference * 4),
		ClientSettings.MAX_UI_SCALE), "a very dense screen stops at the largest scale")
	_expect(is_equal_approx(ClientSettings.ui_scale_for_dpi(10),
		ClientSettings.MIN_UI_SCALE), "a thin screen stops at the smallest scale")

	_clean()
	var first := ClientSettings.new(TEST_PATH)
	first.set_shipped_ui_scale(1.5)
	first.load_from_disk()
	_expect(is_equal_approx(first.ui_scale, 1.5),
		"with no file, the screen gives the scale")

	first.set_ui_scale(1.25)
	var second := ClientSettings.new(TEST_PATH)
	second.set_shipped_ui_scale(1.5)
	second.load_from_disk()
	_expect(is_equal_approx(second.ui_scale, 1.25), "a scale in the file wins")

	second.reset()
	_expect(is_equal_approx(second.ui_scale, 1.5),
		"and Reset goes back to the scale of the screen")

	_clean()


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
