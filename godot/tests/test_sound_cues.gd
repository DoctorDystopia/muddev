extends Node
## Unit tests for SoundCues. Headless runs on the dummy audio driver, so every
## cue is played for real with no speaker attached.
##
##     godot --headless --path godot res://tests/test_sound_cues.tscn

var _failures := 0


func _ready() -> void:
	_the_bus_every_cue_plays_on_exists()
	_every_cue_plays_a_clip_on_that_bus()
	_the_level_up_cue_the_console_names_has_a_clip()
	_an_unknown_cue_plays_nothing()
	_a_volume_setting_reaches_the_bus()

	# A stopped playback is released by the AudioServer's next mix, not by
	# stop() itself, and the mix runs on the audio driver's clock rather than
	# the frame's -- two awaited process frames were measured NOT to be enough.
	# Quitting before it runs reports the playback and its clip as leaked.
	await get_tree().create_timer(0.25).timeout

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: sound_cues")
	get_tree().quit(0)


func _the_bus_every_cue_plays_on_exists() -> void:
	# A player naming a bus the layout does not declare plays on Master and
	# says nothing -- so a renamed bus would quietly take every sound out from
	# under its volume setting.
	var index := AudioServer.get_bus_index(SoundCues.BUS)

	_expect(index != -1, "default_bus_layout.tres declares the %s bus" % SoundCues.BUS)


func _every_cue_plays_a_clip_on_that_bus() -> void:
	# Derived from the table rather than listed here, so a cue added tomorrow
	# is covered with no edit to this file.
	var cues := SoundCues.new()
	add_child(cues)

	for cue: String in SoundCues.cues():
		var player := cues.play(cue)
		var played := player != null

		_expect(played, "%s produces a player" % cue)

		if not played:
			continue

		_expect(player.stream is AudioStream, "%s carries a clip" % cue)
		_expect(player.bus == SoundCues.BUS, "%s plays on %s" % [cue, SoundCues.BUS])
		_expect(player.get_parent() == cues, "%s is parented to the cue node" % cue)

		# Stopped before the free: a playback still mixing when the test quits
		# in this same frame is held by the AudioServer and reported as a leak.
		player.stop()

	cues.free()


func _the_level_up_cue_the_console_names_has_a_clip() -> void:
	# console.gd names this constant; a table that lost its row would make the
	# level-up silent with nothing failing anywhere else.
	_expect(SoundCues.cues().has(SoundCues.LEVEL_UP), "LEVEL_UP has a clip")


func _an_unknown_cue_plays_nothing() -> void:
	var cues := SoundCues.new()
	add_child(cues)

	_expect(cues.play(&"a_cue_nobody_mapped") == null,
		"an unknown cue returns null rather than raising")
	_expect(cues.get_child_count() == 0, "and adds no player")

	cues.free()


func _a_volume_setting_reaches_the_bus() -> void:
	var index := AudioServer.get_bus_index(SoundCues.BUS)

	if index == -1:
		# Already reported by the bus case; reading bus -1 would only error.
		return

	SoundCues.apply_volume(0.5)
	_expect(is_equal_approx(AudioServer.get_bus_volume_db(index), linear_to_db(0.5)),
		"a linear volume is written to the bus as decibels")
	_expect(not AudioServer.is_bus_mute(index), "and leaves the bus audible")

	SoundCues.apply_volume(0.0)
	_expect(AudioServer.is_bus_mute(index),
		"zero mutes the bus rather than writing negative infinity")

	SoundCues.apply_volume(1.0)
	_expect(not AudioServer.is_bus_mute(index), "full volume unmutes it")
	_expect(is_equal_approx(AudioServer.get_bus_volume_db(index), 0.0),
		"at 0 dB, the level the clips were mixed at")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
