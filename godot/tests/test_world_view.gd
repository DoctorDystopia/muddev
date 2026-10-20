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
	_every_run_step_turns_the_front_along_the_run()
	_a_bent_run_faces_along_its_slide()
	_a_diagonal_splits_its_two_cardinals()
	_a_far_entity_is_walked_to_first()
	_a_paced_click_walks_to_the_entity_at_that_pace()
	_an_entity_on_your_tile_is_acted_on_directly()
	_an_entity_on_another_island_is_never_walked_to()
	_an_entity_without_coords_is_acted_on_directly()
	_nothing_to_send_stays_nothing()
	_a_walked_to_menu_row_still_reads_as_its_verb()
	_a_self_approaching_command_is_never_walked_to()
	_a_self_approaching_menu_row_is_never_walked_to()
	_a_payload_that_says_nothing_still_walks()
	_the_hover_names_what_a_left_click_does()
	_the_hover_counts_the_other_menu_rows()
	_an_entity_that_affords_nothing_hovers_as_its_name()
	_every_entity_offers_inspect_last()
	_the_inspect_row_is_never_walked_to()
	_an_entity_with_no_verb_inspects()
	_an_inspect_row_the_server_sent_is_not_doubled()
	_a_row_with_no_dbref_has_no_inspect()
	_a_tile_hovers_as_its_menu_row()
	_a_tile_with_no_action_hovers_as_nothing()
	_facing_a_point_turns_the_front_to_it()
	_facing_agrees_with_the_walk()
	_facing_your_own_spot_keeps_the_yaw()
	_a_foe_above_is_faced_along_the_ground()

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

	# The first jump that the slide snaps. The limit comes from StepAnimator,
	# so a change of SNAP_STEPS moves this case with it.
	var past := floori(StepAnimator.SNAP_STEPS) + 1
	var snapped := WorldView.yaw_towards(Vector2i.ZERO, Vector2i(past, 0), 1.25)

	_expect(is_equal_approx(snapped, 1.25), "a jump that snaps keeps the yaw")


## A run moves two tiles in each tick (`RUN_TILES_PER_TICK`). Thus, each
## `room_info` of a run names a tile two squares away. Until 10/05/2026 the yaw
## kept still for a move of two tiles, and a runner never turned.
func _every_run_step_turns_the_front_along_the_run() -> void:
	for direction: String in STEPS:
		var delta: Vector2i = STEPS[direction] * 2
		var yaw := WorldView.yaw_towards(Vector2i.ZERO, delta, 0.0)
		var front := AUTHORED_FRONT.rotated(Vector3.UP, yaw)
		var run := Vector3(delta.x, 0.0, -delta.y).normalized()

		_expect(front.dot(run) > 0.999,
			"a run %s turns the figure %s" % [direction, direction])


## A run of two tiles can bend: east, then northeast. The slide draws the move
## as one straight line, so the figure faces along that line.
func _a_bent_run_faces_along_its_slide() -> void:
	var delta: Vector2i = STEPS["east"] + STEPS["northeast"]
	var yaw := WorldView.yaw_towards(Vector2i.ZERO, delta, 0.0)
	var front := AUTHORED_FRONT.rotated(Vector3.UP, yaw)
	var slide := Vector3(delta.x, 0.0, -delta.y).normalized()

	_expect(front.dot(slide) > 0.999, "a bent run faces along its slide")


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

const Const := preload("res://autoload/blackout_constants.gd")

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


## A Ctrl + left click gives a pace. The walk then carries it in the paced
## template of the server, and the tile and the verb still arrive intact.
func _a_paced_click_walks_to_the_entity_at_that_pace() -> void:
	var pole := _pole_at([4.0, 7.0, HERE_Z])
	var sent := WorldView.approach_command(POLE_COMMAND, pole, HERE, HERE_Z,
		true, Const.GOTO_PACE_RUN)
	var expected := Const.ENTITY_PACED_APPROACH_TEMPLATE \
		.replace("{pace}", Const.GOTO_PACE_RUN) \
		.replace("{x}", "4").replace("{y}", "7") \
		.replace("{command}", POLE_COMMAND)

	_expect(sent == expected, "the paced walk names the pace, the tile and the verb")
	_expect(sent != WorldView.approach_command(POLE_COMMAND, pole, HERE, HERE_Z),
		"and it is not the walk of a plain click")

	var here := WorldView.approach_command(POLE_COMMAND,
		_pole_at([2.0, 3.0, HERE_Z]), HERE, HERE_Z, true, Const.GOTO_PACE_RUN)

	_expect(here == POLE_COMMAND, "a pole on your own tile has no walk to pace")


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


# ─── Hover text ──────────────────────────────────────────────────────────────

## The bar and the right-click menu must word the default action the same way.
## Asserted against ChooseOption.row_text, not against a literal, so a change
## to the menu's wording cannot make the two disagree.
func _the_hover_names_what_a_left_click_does() -> void:
	var pole := _pole_at([4.0, 7.0, HERE_Z])
	var first: Dictionary = WorldView.options_for(pole)[0]

	_expect(WorldView.entity_hover_text(pole) == ChooseOption.row_text(first),
		"the hover text is the menu's first row")


func _the_hover_counts_the_other_menu_rows() -> void:
	var corpse := {
		"name": "Mutant Raider corpse",
		"interact": "butcher #75931",
		"actions": [
			{"label": "Butcher", "command": "butcher #75931"},
			{"label": "Get", "command": "get #75931"},
			{"label": "Search", "command": "search #75931"}],
	}

	var text := WorldView.entity_hover_text(corpse)

	_expect(text.begins_with("Butcher Mutant Raider corpse"),
		"the default action comes first: %s" % text)
	_expect(text.ends_with(WorldView.MORE_OPTIONS_TEXT % 2),
		"and the two other rows are counted")

	corpse["actions"].pop_back()

	_expect(WorldView.entity_hover_text(corpse).ends_with(
		WorldView.ONE_MORE_OPTION_TEXT), "one other row reads as singular")


## A row with no dbref affords nothing, not even Inspect. A click there does
## nothing, but the bar still names what it is.
func _an_entity_that_affords_nothing_hovers_as_its_name() -> void:
	var player := {"name": "Nick", "interact": ""}

	_expect(WorldView.entity_hover_text(player) == "Nick",
		"an entity with no action hovers as its name")


# ─── Inspect ─────────────────────────────────────────────────────────────────

## Every entity with a dbref offers Inspect, LAST, after whatever the server
## named. Asserted by what the command must carry, the dbref, and against the
## server's own template, which the generated constants hold.
func _every_entity_offers_inspect_last() -> void:
	var pole := _pole_at([4.0, 7.0, HERE_Z])
	pole["id"] = 75931.0

	var rows := WorldView.options_for(pole)
	var last: Dictionary = rows[rows.size() - 1]

	_expect(rows.size() == 2, "the verb of the server, then Inspect")
	_expect(str(rows[0]["command"]) == POLE_COMMAND,
		"the verb of the server stays first")
	_expect(str(last["command"]) == WorldView.inspect_command(pole),
		"Inspect is the last row")
	_expect(str(last["command"]).contains("75931"),
		"the Inspect row carries the dbref")
	_expect(str(last["command"]).begins_with(
		Const.ENTITY_INSPECT_TEMPLATE.split(" ")[0]),
		"the Inspect row sends the verb of the server")

	var raider := {
		"name": "Mutant Raider",
		"id": 75931.0,
		"interact": RAIDER_COMMAND,
		"actions": [
			{"label": "Attack", "command": RAIDER_COMMAND},
			{"label": "Talk", "command": "talk"}],
	}
	var raider_rows := WorldView.options_for(raider)

	_expect(raider_rows.size() == 3, "a listed entity gets Inspect too")
	_expect(str(raider_rows[2]["command"]) == WorldView.inspect_command(raider),
		"and it is last there too")


## Inspect reads from where the player stands, at any distance the server
## draws. So the row is never wrapped in the walk.
func _the_inspect_row_is_never_walked_to() -> void:
	var pole := _pole_at([4.0, 7.0, HERE_Z])
	pole["id"] = 75931.0

	var rows := WorldView.approach_options(WorldView.options_for(pole), pole,
		HERE, HERE_Z)
	var last: Dictionary = rows[rows.size() - 1]

	_expect(str(last["command"]) == WorldView.inspect_command(pole),
		"a far entity is inspected from here")
	_expect(not WorldView.walks_there(WorldView.options_for(pole)[1]),
		"and the row says so")


## An entity the server named no verb for still inspects. The hover bar names
## that row, and a left click sends it.
func _an_entity_with_no_verb_inspects() -> void:
	var player := {"name": "Nick", "id": 12.0, "interact": ""}
	var rows := WorldView.options_for(player)

	_expect(rows.size() == 1, "Inspect is the one row")
	_expect(WorldView.entity_hover_text(player) == ChooseOption.row_text(rows[0]),
		"the hover text is the Inspect row")
	_expect(WorldView.entity_hover_text(player).begins_with("Inspect Nick"),
		"and it reads as Inspect: %s" % WorldView.entity_hover_text(player))


## A server that lists Inspect itself one day does not get a second row.
func _an_inspect_row_the_server_sent_is_not_doubled() -> void:
	var pole := _pole_at([4.0, 7.0, HERE_Z])
	pole["id"] = 75931.0
	pole["actions"] = [
		{"label": "Cut", "command": POLE_COMMAND},
		{"label": "Inspect", "command": WorldView.inspect_command(pole)}]

	var rows := WorldView.options_for(pole)

	_expect(rows.size() == 2, "the row of the server is the Inspect row")
	_expect(str(rows[1]["label"]) == "Inspect",
		"and it keeps the label of the server")


## A row with no dbref gets no Inspect command.
func _a_row_with_no_dbref_has_no_inspect() -> void:
	_expect(WorldView.inspect_command({"name": "Nick"}).is_empty(),
		"no dbref, no Inspect")


func _a_tile_hovers_as_its_menu_row() -> void:
	var text := WorldView.tile_hover_text({"command": "north", "kind": "exit"})

	_expect(text == "North", "a tile hovers as its action: %s" % text)


func _a_tile_with_no_action_hovers_as_nothing() -> void:
	_expect(WorldView.tile_hover_text({}).is_empty(),
		"a tile the server named no action for shows no text")


# ─── Facing a foe ────────────────────────────────────────────────────────────

## The same relationship as the walk case, for a point: after the turn, the
## front of the model points from the one figure to the other. Eight points
## round a figure, on and off the axes.
func _facing_a_point_turns_the_front_to_it() -> void:
	var me := Vector3(2.0, 0.0, -3.0)

	for direction: String in STEPS:
		var step: Vector2i = STEPS[direction]
		# A world offset, so the Z term is already flipped: a step north is
		# a step to -Z.
		var foe := me + Vector3(float(step.x), 0.0, float(-step.y)) * 0.37
		var yaw := WorldView.yaw_facing(me, foe, 0.0)
		var front := AUTHORED_FRONT.rotated(Vector3.UP, yaw)
		var line := (foe - me).normalized()

		_expect(front.distance_to(line) < 0.001,
			"facing a foe to the %s points the front at it" % direction)


## A foe one step away, and a step to that foe, turn the figure one way.
## Two routines with one job cannot disagree.
func _facing_agrees_with_the_walk() -> void:
	for direction: String in STEPS:
		var step: Vector2i = STEPS[direction]
		var walk := WorldView.yaw_towards(Vector2i.ZERO, step, 0.0)
		var foe := Vector3(float(step.x), 0.0, float(-step.y))
		var faced := WorldView.yaw_facing(Vector3.ZERO, foe, 0.0)

		_expect(is_zero_approx(angle_difference(walk, faced)),
			"a foe to the %s is faced the way a step there turns" % direction)


func _facing_your_own_spot_keeps_the_yaw() -> void:
	var spot := Vector3(1.0, 0.0, 1.0)

	_expect(is_equal_approx(WorldView.yaw_facing(spot, spot, 1.25), 1.25),
		"a foe on the same point keeps the yaw")


## Only the ground plane counts. A raider on the roof above is faced along
## the ground, and a raider straight above keeps the yaw.
func _a_foe_above_is_faced_along_the_ground() -> void:
	var me := Vector3.ZERO
	var up_and_east := Vector3(1.0, 4.0, 0.0)
	var east := WorldView.yaw_facing(me, Vector3(1.0, 0.0, 0.0), 0.0)

	_expect(is_equal_approx(WorldView.yaw_facing(me, up_and_east, 0.0), east),
		"a foe above and to the east is faced east")
	_expect(is_equal_approx(WorldView.yaw_facing(me, Vector3(0.0, 4.0, 0.0), 1.25), 1.25),
		"a foe straight above keeps the yaw")


# ─── Harness ─────────────────────────────────────────────────────────────────

func _expect(condition: bool, what: String) -> void:
	if condition:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
