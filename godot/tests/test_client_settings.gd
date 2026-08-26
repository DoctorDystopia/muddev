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


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
