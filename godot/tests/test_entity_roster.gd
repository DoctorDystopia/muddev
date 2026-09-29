extends Node
## Unit tests for EntityRoster, the model of the entities near the observer.
##
##     godot --headless --path godot res://tests/test_entity_roster.tscn
##
## Needs nothing running. The payloads are hand-built, with every number a
## FLOAT, as Godot parses the feed.

const Const := preload("res://autoload/blackout_constants.gd")

var _failures := 0


func _ready() -> void:
	_a_whole_list_replaces_the_rows()
	_a_later_announcement_replaces_the_earlier_one()
	_a_delta_drops_then_adds()
	_a_remove_drops_one_row()
	_each_message_fires_its_own_signal_and_changed()
	_other_channels_are_not_taken()
	_the_tile_and_the_z_of_a_row()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: entity_roster")
	get_tree().quit(0)


func _a_whole_list_replaces_the_rows() -> void:
	var roster := EntityRoster.new()

	roster.ingest(Const.CH_ROOM_PLAYERS, {"entities": [_row(1), _row(2)]})
	roster.ingest(Const.CH_ROOM_PLAYERS, {"entities": [_row(3)]})

	_expect(roster.rows().size() == 1 and not roster.row(3).is_empty(),
		"room_players replaces every row")


func _a_later_announcement_replaces_the_earlier_one() -> void:
	var roster := EntityRoster.new()

	roster.ingest(Const.CH_PLAYER_ADD, {"entity": _row(1, 4)})
	roster.ingest(Const.CH_PLAYER_ADD, {"entity": _row(1, 9)})

	_expect(roster.rows().size() == 1, "one row for one id")
	_expect(EntityRoster.tile_of(roster.row(1)) == Vector2i(9, 0),
		"and it is the later one")


func _a_delta_drops_then_adds() -> void:
	var roster := EntityRoster.new()

	roster.ingest(Const.CH_ROOM_PLAYERS, {"entities": [_row(1), _row(2)]})
	roster.ingest(Const.CH_ROOM_PLAYERS_DELTA,
		{"added": [_row(5)], "removed": [1.0]})

	_expect(roster.row(1).is_empty(), "a removed id goes, as a float id")
	_expect(not roster.row(5).is_empty(), "an added row comes")
	_expect(roster.rows().size() == 2, "and nothing else changes")


func _a_remove_drops_one_row() -> void:
	var roster := EntityRoster.new()

	roster.ingest(Const.CH_ROOM_PLAYERS, {"entities": [_row(1), _row(2)]})
	roster.ingest(Const.CH_PLAYER_REMOVE, {"entity_id": 2.0})

	_expect(roster.rows().size() == 1 and roster.row(2).is_empty(),
		"room_remove_player drops its id")


func _each_message_fires_its_own_signal_and_changed() -> void:
	var roster := EntityRoster.new()
	var heard: Array[String] = []

	roster.replaced.connect(func(_e): heard.append("replaced"))
	roster.delta.connect(func(_a, _r): heard.append("delta"))
	roster.added.connect(func(_e): heard.append("added"))
	roster.removed.connect(func(_i): heard.append("removed"))
	roster.changed.connect(func(): heard.append("changed"))

	roster.ingest(Const.CH_ROOM_PLAYERS, {"entities": []})
	roster.ingest(Const.CH_ROOM_PLAYERS_DELTA, {"added": [], "removed": []})
	roster.ingest(Const.CH_PLAYER_ADD, {"entity": _row(1)})
	roster.ingest(Const.CH_PLAYER_REMOVE, {"entity_id": 1.0})

	_expect(heard == ["replaced", "changed", "delta", "changed", "added",
		"changed", "removed", "changed"],
		"each channel fires its own signal, then changed")


func _other_channels_are_not_taken() -> void:
	var roster := EntityRoster.new()

	_expect(not roster.ingest(Const.CH_ROOM_INFO, {}),
		"room_info is not an entity channel")


func _the_tile_and_the_z_of_a_row() -> void:
	_expect(EntityRoster.tile_of(_row(1, 7)) == Vector2i(7, 0),
		"the tile is an int vector")
	_expect(EntityRoster.tile_of({}) == null, "a row with no coords has no tile")
	_expect(EntityRoster.z_of(_row(1)) == Const.TILE_WORLD_Z, "the z is a string")


func _row(id: int, x: int = 0) -> Dictionary:
	return {"id": float(id), "kind": Const.FAMILY_NPC,
		"coords": [float(x), 0.0, Const.TILE_WORLD_Z]}


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
