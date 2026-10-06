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
	_the_layout_is_remembered_and_fenced()
	_a_layout_preset_saves_loads_and_deletes()
	_the_presets_have_a_limit()
	_an_old_dock_size_moves_into_the_layout()
	_an_unknown_skill_detail_mode_falls_back_rather_than_breaking_the_grid()
	_the_sfx_volume_persists_clamps_and_resets()
	_the_xp_tracker_toggles_persist_and_reset()
	_the_movement_animation_persists_and_resets()
	_the_camera_keys_persist_and_reset()
	_hide_roofs_persists_and_resets()
	_the_map_settings_persist_clamp_and_reset()
	_a_box_the_player_sized_is_remembered()
	_a_box_size_from_a_bad_file_falls_back()
	_the_screen_gives_the_first_scale()
	_the_chat_choices_persist_fence_and_reset()

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
	s.set_layout({HudElements.LOG: {HudLayout.KEY_SIZE: Vector2(500, 300)}})
	s.save_layout_preset("Mine", s.layout)
	s.set_skill_detail(ClientSettings.SKILL_DETAIL_LOG)
	s.reset()
	_expect(s.show_inventory == ClientSettings.DEFAULT_SHOW_INVENTORY,
		"reset restores the pane toggles")
	_expect(s.layout.is_empty(), "and the layout")
	_expect(s.layout_presets.has("Mine"),
		"but keeps the presets, which are the work of the player")
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


## The layout survives a reload, and a runaway number in it is fenced. Keeping
## an element on the screen is the job of the arranger, on every pass. A second
## rule here would be a second owner of it.
func _the_layout_is_remembered_and_fenced() -> void:
	_clean()
	var s := ClientSettings.new(TEST_PATH)

	_expect(s.layout.is_empty(), "no layout until the player edits one")

	var entry := {
		HudLayout.KEY_ANCHOR: Vector2(1, 0),
		HudLayout.KEY_OFFSET: Vector2(-20, 30),
		HudLayout.KEY_SIZE: Vector2(99999, 300),
		HudLayout.KEY_OPACITY: 0.5,
	}
	s.set_layout({HudElements.MINIMAP: entry})

	var reloaded := ClientSettings.new(TEST_PATH)
	reloaded.load_from_disk()
	var saved: Dictionary = reloaded.layout.get(HudElements.MINIMAP, {})

	_expect(saved.get(HudLayout.KEY_OFFSET) == Vector2(-20, 30), "the layout persists")
	_expect(is_equal_approx(saved.get(HudLayout.KEY_OPACITY, 0.0), 0.5),
		"with its opacity")
	_expect((saved.get(HudLayout.KEY_SIZE) as Vector2).x == HudLayout.MAX_PIXELS,
		"and a runaway size is fenced")

	var count := {"n": 0}
	reloaded.layout_replaced.connect(func(): count["n"] += 1)
	reloaded.set_layout({})
	_expect(count["n"] == 0,
		"a write from the arranger does not tell the arranger to read again")


## A preset keeps a layout by name. Loading it replaces the layout and tells
## the arranger. Deleting it leaves the layout alone.
func _a_layout_preset_saves_loads_and_deletes() -> void:
	_clean()
	var s := ClientSettings.new(TEST_PATH)
	var wide := {HudElements.LOG: {HudLayout.KEY_SIZE: Vector2(900, 300)}}

	_expect(s.save_layout_preset("  Wide log  ", wide), "a preset saves")
	_expect(s.layout_preset_names() == ["Wide log"],
		"under its name without the spaces at its ends")
	_expect(not s.save_layout_preset("   ", wide), "an empty name saves nothing")

	var count := {"n": 0}
	s.layout_replaced.connect(func(): count["n"] += 1)
	_expect(s.apply_layout_preset("Wide log"), "the preset loads")
	_expect(s.layout == wide and count["n"] == 1,
		"and becomes the layout, and the arranger hears it")
	_expect(not s.apply_layout_preset("No such preset"), "a missing preset loads nothing")

	var reloaded := ClientSettings.new(TEST_PATH)
	reloaded.load_from_disk()
	_expect(reloaded.layout_presets.has("Wide log"), "the preset survives a reload")

	reloaded.delete_layout_preset("Wide log")
	_expect(reloaded.layout_preset_names().is_empty(), "a deleted preset goes")
	_expect(reloaded.layout == wide, "and the layout stays")


## The player can keep [constant ClientSettings.MAX_LAYOUT_PRESETS] presets. A
## new name past that is refused, and a save over an old name is not.
func _the_presets_have_a_limit() -> void:
	_clean()
	var s := ClientSettings.new(TEST_PATH)

	for index: int in ClientSettings.MAX_LAYOUT_PRESETS:
		s.save_layout_preset("Layout %d" % index, {})

	_expect(not s.save_layout_preset("One more", {}), "a new preset past the limit is refused")
	_expect(s.save_layout_preset("Layout 0", {}), "but a save over an old one is not")


## A build before 09/29/2026 saved a size for each dock. The first load takes
## each one into the layout, as a size only, so the dock keeps its corner.
func _an_old_dock_size_moves_into_the_layout() -> void:
	_clean()
	var handle := FileAccess.open(TEST_PATH, FileAccess.WRITE)
	handle.store_string("[display]\npanel_size=Vector2i(640, 480)\nconsole_size=Vector2i(0, 0)\n")
	handle.close()

	var s := ClientSettings.new(TEST_PATH)
	s.load_from_disk()
	var panel: Dictionary = s.layout.get(HudElements.PANEL, {})

	_expect(panel.get(HudLayout.KEY_SIZE) == Vector2(640, 480),
		"the old panel size is now the size of the panel element")
	_expect(not panel.has(HudLayout.KEY_ANCHOR), "and the panel keeps its shipped corner")
	_expect(not s.layout.has(HudElements.LOG), "a zero size moves nothing")


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


## Off by default, so W is north, as the website and the help say.
func _the_camera_keys_persist_and_reset() -> void:
	_clean()
	var s := ClientSettings.new(TEST_PATH)

	_expect(not s.camera_relative_keys, "W is north by default")

	s.set_camera_relative_keys(true)

	var reloaded := ClientSettings.new(TEST_PATH)
	reloaded.load_from_disk()
	_expect(reloaded.camera_relative_keys, "turning the keys with the camera persists")

	reloaded.reset()
	_expect(reloaded.camera_relative_keys
		== ClientSettings.DEFAULT_CAMERA_RELATIVE_KEYS, "and reset restores it")

	_clean()


## On by default (Nick, 09/26/2026), as the OSRS setting of the same name.
func _hide_roofs_persists_and_resets() -> void:
	_clean()
	var s := ClientSettings.new(TEST_PATH)

	_expect(s.hide_roofs, "roofs hide by default")

	s.set_hide_roofs(false)

	var reloaded := ClientSettings.new(TEST_PATH)
	reloaded.load_from_disk()
	_expect(not reloaded.hide_roofs, "showing the roofs persists")

	reloaded.reset()
	_expect(reloaded.hide_roofs == ClientSettings.DEFAULT_HIDE_ROOFS,
		"and reset restores it")

	_clean()


## The zoom of the minimap and the walk path toggle (09/28/2026).
func _the_map_settings_persist_clamp_and_reset() -> void:
	_clean()
	var s := ClientSettings.new(TEST_PATH)
	var steps := MinimapView.ZOOM_RADII

	_expect(s.minimap_radius == ClientSettings.DEFAULT_MINIMAP_RADIUS,
		"the minimap starts at the shipped zoom")
	_expect(not s.show_walk_path, "the walk path is off by default")

	s.set_minimap_radius(steps[0])
	s.set_show_walk_path(true)

	var reloaded := ClientSettings.new(TEST_PATH)
	reloaded.load_from_disk()
	_expect(reloaded.minimap_radius == steps[0], "the zoom persists")
	_expect(reloaded.show_walk_path, "the walk path toggle persists")

	reloaded.set_minimap_radius(9999)
	_expect(reloaded.minimap_radius == steps[steps.size() - 1],
		"a radius past the widest step is clamped")

	reloaded.reset()
	_expect(reloaded.minimap_radius == ClientSettings.DEFAULT_MINIMAP_RADIUS
		and not reloaded.show_walk_path, "and reset restores both")

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
	@warning_ignore("integer_division")
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


## The chat mode and the tabs hidden from All (09/29/2026). A bad file gives
## Command and nothing hidden, never a broken strip.
func _the_chat_choices_persist_fence_and_reset() -> void:
	_clean()
	var s := ClientSettings.new(TEST_PATH)
	s.set_chat_mode("channel:public")
	s.set_chat_hidden_from_all(PackedStringArray(["combat", "combat", "game"]))

	var back := ClientSettings.new(TEST_PATH)
	back.load_from_disk()
	_expect(back.chat_mode == "channel:public", "the chat mode survives a reload")
	_expect(back.chat_hidden_from_all == PackedStringArray(["combat", "game"]),
		"and the hidden tabs too, each one time")

	var config := ConfigFile.new()
	config.set_value(ClientSettings.CHAT_SECTION, ClientSettings.KEY_CHAT_MODE, 42)
	config.set_value(ClientSettings.CHAT_SECTION, ClientSettings.KEY_CHAT_HIDDEN,
		"not a list")
	config.save(TEST_PATH)

	var bad := ClientSettings.new(TEST_PATH)
	bad.load_from_disk()
	_expect(bad.chat_mode == ClientSettings.DEFAULT_CHAT_MODE,
		"a chat mode that is not text gives Command")
	_expect(bad.chat_hidden_from_all.is_empty(),
		"and hidden tabs that are not a list give none")

	back.reset()
	_expect(back.chat_mode == ClientSettings.DEFAULT_CHAT_MODE
		and back.chat_hidden_from_all.is_empty(), "reset clears both")
	_clean()


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
