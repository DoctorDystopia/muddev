class_name AreaEnvironment
extends WorldEnvironment
## Draws the fog and the light of the area that the player stands in.
##
## [AreaLook] holds the table. This node applies one row of it to the
## environment and the sun. It does three things:
##
## 1. On an area change, it blends from the old look to the new look over
##    [constant BLEND_SECONDS]. The first area snaps, because a login is not a
##    walk.
## 2. On each frame, it moves the depth fog with the length of the camera arm.
##    Godot measures fog from the camera, and the table measures from the
##    player. See [method AreaLook.fog_depth].
## 3. It stops the sun shadows at the fog end. A shadow inside the fog is a
##    cost that nobody sees.
##
## The background colour is the fog colour. The far edge of the fog then melts
## into the background, and that edge is the horizon.

## Emitted when the area changes, with the look that the blend moves TO.
##
## [EntityPool] tints a new figure in from this fog colour. It gets the target
## and not each blended frame, because a figure that arrives during a blend is
## already in the new area.
signal look_changed(look: Dictionary)

## How long an area change takes, in seconds.
const BLEND_SECONDS := 1.0

## The smallest change in a fog distance, in world units, that the node
## writes. A smaller change is not visible, and each write costs a uniform
## upload.
const FOG_EPSILON := 0.01

## Depth fog at full strength: at the fog end, the fog hides everything.
const FOG_FULL_DENSITY := 1.0

@export var sun: DirectionalLight3D
@export var arm: SpringArm3D

## The area of the player. Empty until the first room arrives.
var _area := ""

## The blend: the look it started from, the look it moves to, and the time
## since it started. A finished blend holds `_elapsed >= BLEND_SECONDS`.
var _from: Dictionary = {}
var _to: Dictionary = {}
var _elapsed := BLEND_SECONDS

## The look on screen now. Kept, because a second area change in the middle
## of a blend must start from what the player sees.
var _drawn: Dictionary = {}

## The last fog distances written. Compared each frame, so a still camera
## writes nothing.
var _fog_written := Vector2(-1.0, -1.0)


func _ready() -> void:
	_to = AreaLook.look_for("")
	_from = _to
	_drawn = _to
	environment.fog_enabled = true
	environment.fog_mode = Environment.FOG_MODE_DEPTH
	environment.fog_density = FOG_FULL_DENSITY
	_apply_look(_drawn)


## Tell the node which area the player stands in. The same area again does
## nothing.
func set_area(next_area: String) -> void:
	if next_area == _area:
		return

	var first := _area.is_empty()

	_area = next_area
	_to = AreaLook.look_for(next_area)
	look_changed.emit(_to)

	if first:
		_snap_to(_to)
		return

	_from = _drawn
	_elapsed = 0.0


## The area that the node draws now. Empty before the first room.
func area() -> String:
	return _area


## The look on screen now, part of the way through a blend or not.
func drawn_look() -> Dictionary:
	return _drawn


func _process(delta: float) -> void:
	_advance_blend(delta)
	_follow_arm()


func _snap_to(look: Dictionary) -> void:
	_from = look
	_drawn = look
	_elapsed = BLEND_SECONDS
	_apply_look(_drawn)


func _advance_blend(delta: float) -> void:
	if _elapsed >= BLEND_SECONDS:
		return

	_elapsed = minf(_elapsed + delta, BLEND_SECONDS)

	var weight := _elapsed / BLEND_SECONDS

	_drawn = AreaLook.blend(_from, _to, weight)
	_apply_look(_drawn)


## Put the fog distances where the arm and the look say, and stop the sun
## shadows at the fog end.
func _follow_arm() -> void:
	var arm_length := 0.0

	if arm != null:
		arm_length = arm.get_hit_length()

	var depth := AreaLook.fog_depth(_drawn, arm_length)

	if depth.distance_to(_fog_written) < FOG_EPSILON:
		return

	_fog_written = depth
	environment.fog_depth_begin = depth.x
	environment.fog_depth_end = depth.y

	if sun != null:
		sun.directional_shadow_max_distance = depth.y


## Write one look to the environment and the sun. The fog distances are not
## here, because [method _follow_arm] owns them.
func _apply_look(look: Dictionary) -> void:
	var fog_color: Color = look["fog_color"]

	environment.fog_light_color = fog_color
	environment.background_color = fog_color
	environment.ambient_light_color = look["ambient_color"]
	environment.ambient_light_energy = look["ambient_energy"]

	# The fog distances change with the look too. Clear the record, so the
	# next frame writes them.
	_fog_written = Vector2(-1.0, -1.0)

	if sun == null:
		return

	var elevation := deg_to_rad(float(look["sun_elevation"]))
	var azimuth := deg_to_rad(float(look["sun_azimuth"]))

	sun.light_color = look["sun_color"]
	sun.light_energy = look["sun_energy"]
	# A light shines down its own -Z. A negative pitch points it at the ground,
	# and the yaw turns it about the vertical axis.
	sun.rotation = Vector3(-elevation, azimuth, 0.0)
