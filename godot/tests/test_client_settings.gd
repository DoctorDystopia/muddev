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
	_a_dragged_divider_is_remembered_and_clamped()
	await _the_default_world_split_leaves_the_panel_room()
	_an_unknown_skill_detail_mode_falls_back_rather_than_breaking_the_grid()
	_the_sfx_volume_persists_clamps_and_resets()

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

	s.set_text_split(-99999)
	_expect(s.text_split == ClientSettings.MIN_SPLIT,
		"a runaway divider offset is clamped up")


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
	s.set_text_split(500)
	s.set_skill_detail(ClientSettings.SKILL_DETAIL_LOG)
	s.reset()
	_expect(s.show_inventory == ClientSettings.DEFAULT_SHOW_INVENTORY,
		"reset restores the pane toggles")
	_expect(s.text_split == ClientSettings.DEFAULT_TEXT_SPLIT,
		"and the dividers")
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


## A divider that forgets where it was put is the state this replaced: both
## offsets were authored in console.tscn as a literal 300.
func _a_dragged_divider_is_remembered_and_clamped() -> void:
	_clean()
	var s := ClientSettings.new(TEST_PATH)
	s.set_text_split(420)
	s.set_world_split(-180)

	var reloaded := ClientSettings.new(TEST_PATH)
	reloaded.load_from_disk()
	_expect(reloaded.text_split == 420, "the text divider persists")

	# NEGATIVE, and that is the case that matters: it is the only kind of offset
	# that gives the panel under the world any height. A floor of 120 saved
	# every drag of that divider as "collapsed" until 09/12/2026.
	_expect(reloaded.world_split == -180,
		"and so does the world one, negative as the engine reports it")

	# Clamped on READ, not only on write -- a hand-edited number stays sane.
	var handle := FileAccess.open(TEST_PATH, FileAccess.WRITE)
	handle.store_string("[display]\ntext_split=99999\nworld_split=-99999\n")
	handle.close()

	var repaired := ClientSettings.new(TEST_PATH)
	repaired.load_from_disk()
	_expect(repaired.text_split == ClientSettings.MAX_SPLIT,
		"an out-of-range saved offset is clamped down on load")
	_expect(repaired.world_split == ClientSettings.MIN_SPLIT,
		"and a runaway negative one is clamped up")


## The default is checked against the ENGINE, not against a number, because the
## number was plausible and wrong: 300 laid out the panel under the world at its
## minimum height, the tab strip alone. Built the shape `console.tscn` gives the
## right column -- world expands, panel does not -- so a Godot upgrade that
## changes what an offset means fails here rather than in a player's Options.
func _the_default_world_split_leaves_the_panel_room() -> void:
	const COLUMN_HEIGHT := 1000.0
	const PANEL_MINIMUM := 40.0

	var column := VSplitContainer.new()
	column.size = Vector2(400.0, COLUMN_HEIGHT)

	var world := Control.new()
	world.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(world)

	var panel := Control.new()
	panel.custom_minimum_size = Vector2(0.0, PANEL_MINIMUM)
	column.add_child(panel)

	add_child(column)
	column.split_offset = ClientSettings.DEFAULT_WORLD_SPLIT
	await get_tree().process_frame
	await get_tree().process_frame

	_expect(panel.size.y > PANEL_MINIMUM,
		"the default world split gives the panel more than its tab strip")

	column.queue_free()


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


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
