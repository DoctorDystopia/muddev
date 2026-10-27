extends Node
## The avatar turns to the thing that it acts on (10/20/2026).
##
##     godot --headless --path godot res://tests/test_avatar_facing.tscn
##
## Needs nothing running. The world pane is built from its real scene, because
## the rule lives between three of its parts: the face event, the slide of the
## avatar, and the step of the walk. A plain node stands in for the figure of
## the avatar, and a pool row stands in for the furnace.
##
## The furnace stands one tile east of where the avatar stops. The avatar
## slides there from the southwest, so a yaw read from where it is DRAWN
## points northeast, and only a yaw read from where it STANDS points east.

## Which way a model is authored to face, in its own frame. The same constant
## as test_world_view.gd, for the reason that file gives.
const AUTHORED_FRONT := Vector3.BACK

const ME := 7
const FURNACE_ID := 20760

const FURNACE := {"id": 20760.0, "name": "Foundry Furnace", "kind": "station",
	"asset": "generic", "family": "station", "interact": "craft",
	"coords": [1.0, 0.0, "oasis"]}

## Where the avatar stops, and where it slides from.
const STOP := Vector3.ZERO
const START := Vector3(-0.7, 0.0, 0.7)

## A yaw that no case expects, so a face that turns nothing shows.
const ALONG_THE_WALK := 2.5

var _failures := 0
var _view: WorldView

var _tile_positions := {
	str(FURNACE["coords"]): Vector3(1.0, 0.0, 0.0),
}


func _locate(coords: Array) -> Variant:
	return _tile_positions.get(str(coords))


func _ready() -> void:
	_view = load("res://scenes/world.tscn").instantiate()
	add_child(_view)

	# No frame runs while the cases run, and each case moves the slide by
	# hand. A _process between two lines would move it for them.
	_view.set_process(false)

	var resolver := MeshResolver.new(ModelRegistry.new(), "")

	add_child(resolver)
	_view._entities.bind(resolver, _locate, WorldView.STEP)
	_view._entities.set_animated(false)
	_view._entities.replace_all([FURNACE])

	_view._char = CharState.new()
	_view._char.entity_id = ME
	_view._avatar = Node3D.new()
	_view._avatar_root.add_child(_view._avatar)

	_view._state = WorldState.new()
	_view._state.current_z = "oasis"
	_view._facing_z = "oasis"

	_a_standing_avatar_turns_to_the_furnace_at_once()
	_a_sliding_avatar_turns_when_it_stands()
	_the_yaw_is_read_from_where_the_avatar_stops()
	_a_step_drops_a_face_that_waits()
	_a_redraw_on_the_same_tile_keeps_the_face()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: avatar_facing")
	get_tree().quit(0)


# ─── Cases ───────────────────────────────────────────────────────────────────

## A typed `craft` beside the furnace. Nothing slides, so the turn starts in
## the same call.
func _a_standing_avatar_turns_to_the_furnace_at_once() -> void:
	_stand_at(STOP)
	_view._face_toward(ME, FURNACE_ID)

	_expect(_faces_east(_view._avatar_yaw),
		"a standing avatar turns to the furnace at once")
	_expect(_view._avatar_facing == null, "and no face waits")


## A walk that ends in `then craft`. The last step slides, and the step keeps
## the turn until the avatar stands.
func _a_sliding_avatar_turns_when_it_stands() -> void:
	_slide(START, STOP)
	_view._face_toward(ME, FURNACE_ID)

	_expect(is_equal_approx(_view._avatar_yaw, ALONG_THE_WALK),
		"a sliding avatar keeps the turn of its step")
	_expect(_view._avatar_facing != null, "and the face waits")

	_arrive()

	_expect(_faces_east(_view._avatar_yaw),
		"the avatar turns to the furnace when it stands")
	_expect(_view._avatar_facing == null, "and the face no longer waits")


## The point that matters. From START, the furnace is to the northeast.
## From STOP, where the avatar stops, it is to the east.
func _the_yaw_is_read_from_where_the_avatar_stops() -> void:
	_slide(START, STOP)
	_view._face_toward(ME, FURNACE_ID)

	var waiting: Variant = _view._avatar_facing

	_expect(waiting != null and _faces_east(waiting),
		"the face is read from where the avatar stops, not where it is drawn")

	_arrive()


## The player walks away before the slide ends. The new step drops the
## face, so the avatar faces its walk, not the thing that it left.
func _a_step_drops_a_face_that_waits() -> void:
	_slide(START, STOP)
	_view._face_toward(ME, FURNACE_ID)
	_view._facing_cell = Vector2i(0, 0)
	_view._state.current_cell = Vector2i(0, 1)
	_view._turn_avatar()

	_expect(_view._avatar_facing == null, "a new step drops the waiting face")

	_arrive()

	_expect(not _faces_east(_view._avatar_yaw),
		"and the avatar does not turn to the furnace when it stands")


## A chunk that lands calls the same routine as a step, with no move. That
## is no step, and it must not drop the face.
func _a_redraw_on_the_same_tile_keeps_the_face() -> void:
	_slide(START, STOP)
	_view._face_toward(ME, FURNACE_ID)
	_view._facing_cell = Vector2i(0, 0)
	_view._state.current_cell = Vector2i(0, 0)
	_view._turn_avatar()

	_expect(_view._avatar_facing != null, "a redraw keeps the waiting face")

	_arrive()

	_expect(_faces_east(_view._avatar_yaw), "and the avatar turns when it stands")


# ─── Helpers ─────────────────────────────────────────────────────────────────

## The avatar stands at `point`, with no slide and no face.
func _stand_at(point: Vector3) -> void:
	_view._animator.set_animated(true)
	_view._animator.place(point)
	_view._draw_avatar()
	_view._avatar_yaw = ALONG_THE_WALK
	_view._avatar_facing = null


## The avatar is on `from`, and the server has put it on `to`. The pane
## turns it along the step, as _turn_avatar does.
func _slide(from: Vector3, to: Vector3) -> void:
	_stand_at(from)
	_view._animator.aim(to)
	_view._draw_avatar()


## The slide ends, and the pane takes the face, as one frame does.
func _arrive() -> void:
	_view._animator.advance(10.0)
	_view._draw_avatar()
	_view._take_facing()


## Whether a yaw turns the front of a model to +X, where the furnace is.
func _faces_east(yaw: float) -> bool:
	var front := AUTHORED_FRONT.rotated(Vector3.UP, yaw)

	return front.dot(Vector3.RIGHT) > 0.999


func _expect(condition: bool, label: String) -> void:
	if condition:
		print("  ok   %s" % label)
		return

	_failures += 1
	printerr("  FAIL %s" % label)
