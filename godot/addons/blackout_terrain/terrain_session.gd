@tool
extends RefCounted
## The session file of the terrain editor: the choices of the author between
## two sessions. The tool, the Build options, the paint values, and the
## marks to show live here.
##
## The file is `user://blackout_terrain_session.cfg`, outside the repo. Thus
## a session leaves no modified file in git. The noise seed, the frequency,
## and the amplitude are not here: they are a shared fact of the world, and
## they stay in `terrain_editor.cfg` beside the plugin.

const PATH := "user://blackout_terrain_session.cfg"


## One value of `section`, or `default` when the file has no such value or
## a value of another type.
static func read(section: String, key: String, default: Variant) -> Variant:
	var config := ConfigFile.new()

	if config.load(PATH) != OK:
		return default

	var value: Variant = config.get_value(section, key, default)

	return value if typeof(value) == typeof(default) else default


## Write each value of `values` into `section`. The other sections stay.
static func write(section: String, values: Dictionary) -> void:
	var config := ConfigFile.new()

	config.load(PATH)

	for key: String in values:
		config.set_value(section, key, values[key])

	config.save(PATH)
