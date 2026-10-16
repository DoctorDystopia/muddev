extends Node
## Tests for the stance table (DESIGN-0014 Phase W5): [FigureStances], and
## the tool types of [FigureCatalog].
##
##     godot --headless --path godot res://tests/test_figure_stances.tscn
##
## Needs nothing running and no editor. It writes no file. It reads the
## stance table and the clip files of the repository. The cases:
##
## 1. A stance text that is read and written gives the same bytes. The
##    writer leaves out an action with no clip, and a stance with no action.
## 2. The reader refuses a file with a bad form, and a newer format.
## 3. An action takes the clip of its stance, then the clip of the default
##    clip set, then no clip.
## 4. The first worn item whose tool type has a stance decides the stance
##    of a figure.
## 5. The item catalog gives each tool type, and the tool types of an
##    outfit in the order of the slots.
## 6. The stance table of the repository reads, and it is in its canonical
##    text. Each clip that it names is a clip of the clip library. Rule C7
##    of the checks has its other half in `test_figure_files.py`: the tool
##    types of the server.

var _failures := 0


func _ready() -> void:
	_a_stance_text_gives_the_same_bytes()
	_the_reader_refuses_a_bad_form()
	_an_action_takes_its_clip_in_order()
	_the_first_item_with_a_stance_decides()
	_the_catalog_gives_the_tool_types()
	_the_repository_stances_read()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: figure_stances")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


## A stance table with a default clip set and the stance of a spear.
func _table() -> FigureStances:
	return FigureStances.from_data({"format": 1,
		"default": {"idle": "idle", "walk": "walk"},
		"stances": {"spear": {"walk": "spear_walk", "attack": "spear_thrust"}}})


func _a_stance_text_gives_the_same_bytes() -> void:
	var table := _table()
	var text := table.to_text()
	var again := FigureStances.from_text(text)

	_expect(table.error.is_empty(), "a stance table reads: " + table.error)
	_expect(again.error.is_empty() and again.to_text() == text,
		"a read and a write give the same bytes: " + again.error)
	_expect(table.key() == FigureStances.KEY, "a stance table has the key of its one file")
	_expect(table.tool_types() == PackedStringArray(["spear"]) and table.has_stance("spear")
		and not table.has_stance("bow"), "the table names each tool type with a stance")

	var loose := FigureStances.from_data({"format": 1,
		"default": {"idle": "idle", "run": ""},
		"stances": {"bow": {"walk": ""}, "spear": {"walk": "spear_walk"}}})

	_expect(loose.error.is_empty() and loose.default_set() == {"idle": "idle"}
		and loose.tool_types() == PackedStringArray(["spear"]),
		"the writer leaves out an action with no clip, and a stance with no action")
	_expect(FigureStances.from_data({"format": 1}).to_text().contains("default")
		and FigureStances.new().default_set().is_empty(),
		"a table with no clip reads, and it keeps its two tables")


func _the_reader_refuses_a_bad_form() -> void:
	var bad := [
		[{"default": {}}, "a stance table needs a format"],
		[{"format": FigureStances.FORMAT + 1}, "a newer format does not read"],
		[{"format": 1, "default": []}, "the default clip set is a table"],
		[{"format": 1, "stances": []}, "stances is a table"],
		[{"format": 1, "stances": {"spear": "walk"}}, "a stance is a table"],
		[{"format": 1, "stances": {"Spear": {}}}, "a tool type is plain"],
		[{"format": 1, "default": {"Walk": "walk"}}, "an action is plain"],
		[{"format": 1, "default": {"walk": 3}}, "a clip is a name"],
	]

	_expect(not FigureStances.from_text("[]").error.is_empty(), "a list is no stance table")

	for pair: Array in bad:
		_expect(not FigureStances.from_data(pair[0]).error.is_empty(), pair[1])


func _an_action_takes_its_clip_in_order() -> void:
	var table := _table()

	_expect(table.clip_for("spear", "walk") == "spear_walk", "the clip of the stance is first")
	_expect(table.clip_for("spear", "idle") == "idle",
		"an action that the stance does not name takes the clip of the default clip set")
	_expect(table.clip_for("bow", "walk") == "walk" and table.clip_for("", "walk") == "walk",
		"a tool type with no stance, and empty hands, each take the default clip set")
	_expect(table.clip_for("spear", "run").is_empty(), "an action with no clip gives no clip")
	_expect(table.own_clip("spear", "idle").is_empty() and table.own_clip("", "idle") == "idle",
		"a stance names only its own clips")
	_expect(table.clip_set_of("spear")
		== {"idle": "idle", "walk": "spear_walk", "attack": "spear_thrust"},
		"the clip set of a tool type has each action with a clip")
	_expect(table.clip_names()
		== PackedStringArray(["idle", "spear_thrust", "spear_walk", "walk"]),
		"the table names each clip one time, in sorted order")


func _the_first_item_with_a_stance_decides() -> void:
	var table := _table()

	_expect(table.stance_of(["helmet", "spear", "bow"]) == "spear",
		"the first tool type with a stance decides")
	_expect(table.stance_of(["helmet", "bow"]).is_empty() and table.stance_of([]).is_empty(),
		"no worn item with a stance gives the default clip set")


func _the_catalog_gives_the_tool_types() -> void:
	var catalog := FigureCatalog.from_data({"format": 1,
		"slots": [{"key": "main_hand", "label": "Main hand", "clears": []},
			{"key": "head", "label": "Head", "clears": []},
			{"key": "neck", "label": "Neck", "clears": []}],
		"items": [
			{"key": "iron_helm", "name": "iron helm", "slot": "head", "tool_type": "helmet",
				"tier": 1, "family": "armor"},
			{"key": "iron_spear", "name": "iron spear", "slot": "main_hand",
				"tool_type": "spear", "tier": 1, "family": "weapon"},
			{"key": "wood_spear", "name": "wood spear", "slot": "main_hand",
				"tool_type": "spear", "tier": 0, "family": "weapon"},
			{"key": "charm", "name": "charm", "slot": "neck", "tool_type": "", "tier": 0,
				"family": "generic"}]})

	_expect(catalog.error.is_empty(), "the catalog reads: " + catalog.error)
	_expect(catalog.tool_types() == PackedStringArray(["helmet", "spear"]),
		"the catalog gives each tool type one time, in sorted order")
	_expect(catalog.tool_type_of("iron_spear") == "spear" and catalog.tool_type_of("charm").is_empty()
		and catalog.tool_type_of("no_such_item").is_empty(),
		"an item gives its tool type, and an item with none gives no text")
	_expect(catalog.outfit_tool_types({"head": "iron_helm", "main_hand": "iron_spear",
		"neck": "charm"}) == ["spear", "helmet"],
		"an outfit gives its tool types in the order of the slots")
	_expect(_table().stance_of(catalog.outfit_tool_types({"head": "iron_helm",
		"main_hand": "wood_spear"})) == "spear", "an outfit with a spear takes the stance of a spear")


func _the_repository_stances_read() -> void:
	var path := ProjectSettings.globalize_path(FigureStances.STANCES_PATH)
	var table := FigureStances.read_file()
	var clips := FigureClips.names_of(FigureClips.library())

	_expect(table.error.is_empty(), "the stance table of the repository reads: " + table.error)
	_expect(FileAccess.get_file_as_string(path).replace("\r\n", "\n") == table.to_text(),
		"the stance table of the repository is in its canonical text")
	_expect(not table.clip_names().is_empty(), "the stance table names a clip")

	for clip_name: String in table.clip_names():
		_expect(clip_name in clips, "the clip %s of the stance table is a clip file" % clip_name)
