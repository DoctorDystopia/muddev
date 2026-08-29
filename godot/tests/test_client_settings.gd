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
	_an_unknown_skill_detail_mode_falls_back_rather_than_breaking_the_grid()

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

	s.set_text_split(0)
	_expect(s.text_split == ClientSettings.MIN_SPLIT,
		"a divider dragged to nothing is clamped up")


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
	s.set_world_split(180)

	var reloaded := ClientSettings.new(TEST_PATH)
	reloaded.load_from_disk()
	_expect(reloaded.text_split == 420, "the text divider persists")
	_expect(reloaded.world_split == 180, "and so does the world one")

	# Clamped on READ, not only on write -- an offset saved from a much wider
	# window can leave a pane at zero width, and a pane with no pixels has no
	# divider to drag back.
	var handle := FileAccess.open(TEST_PATH, FileAccess.WRITE)
	handle.store_string("[display]\ntext_split=99999\nworld_split=-40\n")
	handle.close()

	var repaired := ClientSettings.new(TEST_PATH)
	repaired.load_from_disk()
	_expect(repaired.text_split == ClientSettings.MAX_SPLIT,
		"an out-of-range saved offset is clamped down on load")
	_expect(repaired.world_split == ClientSettings.MIN_SPLIT,
		"and a negative one is clamped up")


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


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
