extends Node
## Unit tests for WorldView's facing maths. Needs no server and no scene --
## `yaw_towards` is static, and every case here is a pair of grid cells.
##
##     godot --headless --path godot res://tests/test_world_view.tscn
##
## Exits 0 when every case passes, 1 on the first failure.
##
## The bug this file exists to catch is SILENT. A sign error in the yaw does not
## raise, does not warn, and does not stop the client coming up -- the figure
## simply walks backwards, or sidles east while heading north. The browser pane
## carried exactly one line of this maths and no test of it.

## The eight compass steps, as the grid delta each one makes.
##
## Grid Y grows NORTHWARD, which is the whole reason this table is worth
## spelling out: it is the fact `_tile_position` flips when it turns a cell into
## a world position, and the fact `yaw_towards` has to flip back.
const STEPS := {
	"north": Vector2i(0, 1),
	"south": Vector2i(0, -1),
	"east": Vector2i(1, 0),
	"west": Vector2i(-1, 0),
	"northeast": Vector2i(1, 1),
	"northwest": Vector2i(-1, 1),
	"southeast": Vector2i(1, -1),
	"southwest": Vector2i(-1, -1),
}

## Which way a character model is authored to face, in its own frame.
##
## Godot spells +Z `BACK` because a Godot NODE looks down -Z. A glTF character
## is authored front-to-+Z and imported unrotated, so the model's front and the
## engine's idea of forward are opposites -- and this constant is named for the
## model, since the model is what the yaw has to turn.
const AUTHORED_FRONT := Vector3.BACK

var _failures := 0


func _ready() -> void:
	_every_step_turns_the_front_along_the_walk()
	_the_eight_steps_face_eight_different_ways()
	_standing_still_keeps_the_yaw()
	_a_teleport_keeps_the_yaw()
	_a_diagonal_splits_its_two_cardinals()
	_a_far_entity_is_walked_to_first()
	_an_entity_on_your_tile_is_acted_on_directly()
	_an_entity_on_another_island_is_never_walked_to()
	_an_entity_without_coords_is_acted_on_directly()
	_nothing_to_send_stays_nothing()
	_a_walked_to_menu_row_still_reads_as_its_verb()
	_a_self_approaching_command_is_never_walked_to()
	_a_self_approaching_menu_row_is_never_walked_to()
	_a_payload_that_says_nothing_still_walks()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: world_view")
	get_tree().quit(0)


# ─── Cases ───────────────────────────────────────────────────────────────────

## The one assertion that matters, and it is deliberately not a table of eight
## expected radians.
##
## A literal-radians test can be copied from a wrong implementation and will
## then agree with it forever. This one derives the expectation from the OTHER
## end of the pipeline instead -- where `_tile_position` actually puts the
## destination tile -- and asserts the relationship between them: after the
## turn, the model's front points along the walk.
func _every_step_turns_the_front_along_the_walk() -> void:
	for direction: String in STEPS:
		var delta: Vector2i = STEPS[direction]
		var yaw := WorldView.yaw_towards(Vector2i.ZERO, delta, 0.0)
		var front := AUTHORED_FRONT.rotated(Vector3.UP, yaw)

		# The same flip _tile_position makes: world X follows grid x, world Z
		# runs OPPOSITE to grid y.
		var walk := Vector3(delta.x, 0.0, -delta.y).normalized()

		_expect(front.dot(walk) > 0.999,
			"a step %s turns the figure %s" % [direction, direction])


## Guards the degenerate implementation the case above cannot catch on its own:
## a `yaw_towards` returning a constant would fail it, but one collapsing the
## diagonals onto their cardinals would not obviously do so.
func _the_eight_steps_face_eight_different_ways() -> void:
	var seen: Array[float] = []

	for direction: String in STEPS:
		var yaw := WorldView.yaw_towards(Vector2i.ZERO, STEPS[direction], 0.0)

		for other: float in seen:
			_expect(absf(angle_difference(yaw, other)) > 0.1,
				"%s faces somewhere no other step does" % direction)

		seen.append(yaw)


## Arriving where you already are is what a relayout and a resync each replay,
## and neither is a turn. Snapping to zero here would spin the figure round to
## face north every time an island finished loading.
func _standing_still_keeps_the_yaw() -> void:
	var kept := WorldView.yaw_towards(Vector2i(3, 7), Vector2i(3, 7), 1.25)

	_expect(is_equal_approx(kept, 1.25), "a zero-length move keeps the yaw")


## A teleport is not a walk. There is no direction in a jump across the map, and
## facing wherever the destination happens to lie would read as the figure
## having turned to watch something that is not there.
func _a_teleport_keeps_the_yaw() -> void:
	var far := WorldView.yaw_towards(Vector2i(0, 0), Vector2i(9, 4), 1.25)

	_expect(is_equal_approx(far, 1.25), "a jump across the map keeps the yaw")

	# Two tiles is already a teleport -- the pane only ever watches single
	# steps, so anything further arrived some other way.
	var two := WorldView.yaw_towards(Vector2i(0, 0), Vector2i(0, 2), 1.25)

	_expect(is_equal_approx(two, 1.25), "even a two-tile jump keeps the yaw")


## Northeast has to sit exactly between north and east, or the four diagonals
## drift a few degrees off and the figure reads as walking crabwise.
func _a_diagonal_splits_its_two_cardinals() -> void:
	var north := WorldView.yaw_towards(Vector2i.ZERO, STEPS["north"], 0.0)
	var east := WorldView.yaw_towards(Vector2i.ZERO, STEPS["east"], 0.0)
	var northeast := WorldView.yaw_towards(Vector2i.ZERO, STEPS["northeast"], 0.0)

	var to_north := angle_difference(northeast, north)
	var to_east := angle_difference(northeast, east)

	_expect(is_equal_approx(absf(to_north), absf(to_east)),
		"northeast is as far from north as it is from east")
	_expect(is_equal_approx(absf(to_north), PI / 4.0),
		"and that distance is an eighth turn")


# ─── Approach ────────────────────────────────────────────────────────────────

const POLE_COMMAND := "cut rusty pole"
# A dbref, because that is how the server names a target that has to be
# exactly the one clicked. See DBREF_TARGET_VERBS.
const RAIDER_COMMAND := "attack #75931"
const HERE := Vector2i(2, 3)
const HERE_Z := "oasis"


static func _pole_at(coords: Array) -> Dictionary:
	return {"name": "Rusty Pole", "interact": POLE_COMMAND, "coords": coords}


## The case the feature exists for. Asserted by what the command must CARRY --
## the destination tile and the verb, untouched -- rather than against a copy of
## the template, which would agree with a wrong template forever.
func _a_far_entity_is_walked_to_first() -> void:
	var sent := WorldView.approach_command(POLE_COMMAND,
		_pole_at([4.0, 7.0, HERE_Z]), HERE, HERE_Z)

	_expect(sent != POLE_COMMAND, "a pole two tiles off is not cut from here")
	_expect(sent.contains("(4,7)"), "the walk names the pole's tile")
	_expect(sent.ends_with(POLE_COMMAND), "and the verb arrives intact")


func _an_entity_on_your_tile_is_acted_on_directly() -> void:
	var sent := WorldView.approach_command(POLE_COMMAND,
		_pole_at([2.0, 3.0, HERE_Z]), HERE, HERE_Z)

	_expect(sent == POLE_COMMAND, "a pole on your own tile is cut at once")


## (4,7) on another island is a different room on this one. Wrapping it would
## walk the player to a tile they never clicked.
func _an_entity_on_another_island_is_never_walked_to() -> void:
	var sent := WorldView.approach_command(POLE_COMMAND,
		_pole_at([4.0, 7.0, "azm plains"]), HERE, HERE_Z)

	_expect(sent == POLE_COMMAND, "a pole on another map is sent as it was named")


func _an_entity_without_coords_is_acted_on_directly() -> void:
	var sent := WorldView.approach_command(POLE_COMMAND,
		{"interact": POLE_COMMAND}, HERE, HERE_Z)

	_expect(sent == POLE_COMMAND, "an unplaced entity is sent as it was named")


func _nothing_to_send_stays_nothing() -> void:
	var sent := WorldView.approach_command("", _pole_at([4.0, 7.0, HERE_Z]),
		HERE, HERE_Z)

	_expect(sent.is_empty(), "an entity affording nothing still affords nothing")


## Without the label the wrap keeps, the menu row is worded from the wrapped
## command's first word and every far entity reads as "Goto".
func _a_walked_to_menu_row_still_reads_as_its_verb() -> void:
	var pole := _pole_at([4.0, 7.0, HERE_Z])
	var rows := WorldView.approach_options(WorldView.options_for(pole), pole,
		HERE, HERE_Z)

	_expect(rows.size() == 1, "one verb, one row")

	var row: Dictionary = rows[0]
	var text := ChooseOption.row_text(row)

	_expect(str(row["command"]).ends_with(POLE_COMMAND), "the row walks, then cuts")
	_expect(not text.to_lower().begins_with("goto"),
		"the row reads as the verb, not the walk: %s" % text)


## The bug the `approach` field exists for. A bow reaches seven tiles, so the
## wrap walked the archer onto the raider before firing a shot that was already
## legal from where it stood. How far a weapon carries is a rule, so the SERVER
## decides, and CmdAttack walks by itself when it has to.
func _a_self_approaching_command_is_never_walked_to() -> void:
	var raider := {
		"name": "Mutant Raider",
		"interact": RAIDER_COMMAND,
		"coords": [4.0, 7.0, HERE_Z],
		"approach": false,
	}

	var sent := WorldView.approach_command(RAIDER_COMMAND, raider, HERE, HERE_Z,
		WorldView.walks_there(raider))

	_expect(sent == RAIDER_COMMAND, "a far raider is attacked from here")


func _a_self_approaching_menu_row_is_never_walked_to() -> void:
	var raider := {
		"name": "Mutant Raider",
		"interact": RAIDER_COMMAND,
		"coords": [4.0, 7.0, HERE_Z],
		"approach": false,
	}

	var rows := WorldView.approach_options(WorldView.options_for(raider), raider,
		HERE, HERE_Z)

	_expect(rows.size() == 1, "one verb, one row")
	_expect(str(rows[0]["command"]) == RAIDER_COMMAND,
		"the menu row attacks from here too")


## ABSENT MEANS WALK. Every other verb acts where it stands, the server sends
## the key only to say otherwise, and a payload from a server that never heard
## of the field has to keep the behaviour this pane always had.
func _a_payload_that_says_nothing_still_walks() -> void:
	var pole := _pole_at([4.0, 7.0, HERE_Z])

	_expect(WorldView.walks_there(pole), "an entity that says nothing is walked to")

	var rows := WorldView.approach_options(WorldView.options_for(pole), pole,
		HERE, HERE_Z)

	_expect(str(rows[0]["command"]) != POLE_COMMAND, "and its menu row walks")


# ─── Harness ─────────────────────────────────────────────────────────────────

func _expect(condition: bool, what: String) -> void:
	if condition:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
