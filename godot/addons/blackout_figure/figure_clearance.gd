@tool
class_name FigureClearance
extends RefCounted
## The clearance of a held item: how near an item in a hand comes to the
## body through one clip (DESIGN-0014, Phase W2).
##
## A clip that moves a hand along a leg puts a sword through that leg. The
## walk pictures of Phase W0 showed it, and Nick asked that it does not
## occur (10/12/2026). This class measures it, so a test and the Clips tab
## find such a clip before a player does.
##
## ## The probe
##
## The check holds a probe in each hand: a straight item along the +Y axis
## of the hand socket, as long as a long sword. A real item is this long or
## shorter. A clip that is clear for the probe is clear for a sword, an
## axe, and a wand.
##
## [method probe_look] gives the same probe as a worn look, so the
## workbench can show it.
##
## ## The measure
##
## The gap is the distance from the surface of the probe to the nearest
## body part, at the worst moment of the clip. A gap below zero says that
## the probe is inside that part. The check leaves out the arm and the hand
## that hold the probe.
##
## A sphere, a cylinder, and a box of a shape list have an exact distance.
## Each other mesh uses its bounding box.
##
## Nothing here needs the editor or the scene tree. The check builds its
## own figure, and it reads each pose through [method FigureClips.pose].

## The key of the worn look of the probes. No figure file has this key.
const PROBE_LOOK := "held_probe"

## The slots whose bone holds a probe.
const HAND_SLOTS := ["main_hand", "off_hand"]

## The regions of the arm that holds an item. The check leaves out a part
## of these regions on a bone above the hand socket.
const ARM_REGIONS := ["arms", "hands"]

## The probe: its length in front of the grip, its length behind the grip,
## and its radius.
const PROBE_LENGTH := 0.9
const PROBE_BACK := 0.1
const PROBE_RADIUS := 0.02

## The check reads the probe at this many points along its length.
const PROBE_POINTS := 41

## The check reads a clip this many times each second.
const SAMPLES_PER_SECOND := 30.0

## The width of the guard of the shown probe, and the depth of its blade.
const PROBE_GUARD := 0.12
const PROBE_DEPTH := 0.012


# ─── The check ──────────────────────────────────────────────────────────────

## The worst moment of one clip for a held item.
##
## Returns `{gap, time, part, hand}`: the gap, the time of that moment, the
## name of the nearest body part, and the hand bone that holds the probe. A
## rig with no hand bone gives an empty dictionary.
static func check(rig: FigureRig, body: FigureLook, clip: Animation) -> Dictionary:
	var figure := FigureBuilder.build(rig, [body])
	var skeleton := FigureBuilder.skeleton_of(figure)
	var worst := {}
	var samples := maxi(int(ceil(clip.length * SAMPLES_PER_SECOND)), 1)

	for sample in samples + 1:
		var time := clip.length * sample / samples

		FigureClips.pose(skeleton, clip, time)

		for hand: String in hand_bones(rig):
			var found := _nearest(figure, rig, body, hand)

			if not found.is_empty() and (worst.is_empty() or found["gap"] < worst["gap"]):
				worst = found
				worst["time"] = time
				worst["hand"] = hand

	figure.free()

	return worst


## True for a result of [method check] with the held item clear of the body.
static func is_clear(result: Dictionary) -> bool:
	return result.is_empty() or result["gap"] >= 0.0


## One line for a result of [method check].
static func line_of(clip_name: String, result: Dictionary) -> String:
	if result.is_empty():
		return "%s: the rig has no hand socket." % clip_name

	if is_clear(result):
		return "%s: a held item stays clear of the body. Nearest: %.3f from %s at %.2f s." \
			% [clip_name, result["gap"], result["part"], result["time"]]

	return "%s: a held item on %s goes %.3f into %s at %.2f s." \
		% [clip_name, result["hand"], -result["gap"], result["part"], result["time"]]


## The bones that hold a probe: the bone of each hand slot of the rig.
static func hand_bones(rig: FigureRig) -> PackedStringArray:
	var bones := PackedStringArray()

	for slot: String in HAND_SLOTS:
		var bone: String = rig.slots().get(slot, "")

		if rig.has_bone(bone) and not bone in bones:
			bones.append(bone)

	return bones


# ─── The probe as a worn look ───────────────────────────────────────────────

## The worn look that shows the probe in each hand of a rig.
static func probe_look(rig: FigureRig) -> FigureLook:
	var parts := []
	var length := PROBE_LENGTH + PROBE_BACK
	var middle := (PROBE_LENGTH - PROBE_BACK) * 0.5

	for hand: String in hand_bones(rig):
		parts.append({
			"name": "probe_" + hand,
			"bone": hand,
			"shapes": [
				{"shape": FamilyShapes.SHAPE_BOX,
					"size": [PROBE_RADIUS * 2.0, length, PROBE_DEPTH],
					"offset": [0.0, middle, 0.0], "color": MeshPalette.STEEL,
					"finish": MeshPalette.FINISH_METAL},
				{"shape": FamilyShapes.SHAPE_BOX,
					"size": [PROBE_GUARD, PROBE_RADIUS, PROBE_RADIUS],
					"offset": [0.0, PROBE_RADIUS * 2.0, 0.0], "color": MeshPalette.WOOD},
			],
		})

	return FigureLook.from_data({"format": FigureLook.FORMAT, "key": PROBE_LOOK,
		"parts": parts})


# ─── The distance ───────────────────────────────────────────────────────────

## The body part that is nearest to the probe of one hand, in the pose that
## the skeleton has now: `{gap, part}`.
static func _nearest(figure: Node3D, rig: FigureRig, body: FigureLook,
		hand: String) -> Dictionary:
	var skeleton := FigureBuilder.skeleton_of(figure)
	var grip := FigureClips.global_pose(skeleton, skeleton.find_bone(hand))
	var arm := _bones_above(rig, hand)
	var best := {}

	for node: Node3D in FigureBuilder.part_nodes(figure):
		var row := body.part(FigureBuilder.part_id(node)[1])

		if row["bone"] in arm and row.get("region", "") in ARM_REGIONS:
			continue

		var place := FigureClips.global_pose(skeleton, skeleton.find_bone(row["bone"])) \
			* node.transform
		var gap := _gap_to_part(grip, place, node)

		if best.is_empty() or gap < best["gap"]:
			best = {"gap": gap, "part": row["name"]}

	return best


## The gap between the probe at `grip` and one part node at `place`.
static func _gap_to_part(grip: Transform3D, place: Transform3D, part: Node3D) -> float:
	var nearest := INF

	for child: Node in part.get_children():
		var instance := child as MeshInstance3D

		if instance == null or instance.mesh == null:
			continue

		var to_shape := (place * instance.transform).affine_inverse()

		for point in PROBE_POINTS:
			var along := -PROBE_BACK + (PROBE_LENGTH + PROBE_BACK) * point / (PROBE_POINTS - 1)
			var local := to_shape * (grip * Vector3(0.0, along, 0.0))

			nearest = minf(nearest, _distance_to_mesh(instance.mesh, local))

	return nearest - PROBE_RADIUS


## The distance from a point to the surface of a mesh, in the space of the
## mesh. A point inside the mesh gives zero.
static func _distance_to_mesh(mesh: Mesh, point: Vector3) -> float:
	if mesh is SphereMesh:
		return maxf(point.length() - (mesh as SphereMesh).radius, 0.0)

	if mesh is CylinderMesh:
		var cylinder := mesh as CylinderMesh
		var radius := maxf(cylinder.top_radius, cylinder.bottom_radius)
		var side := maxf(Vector2(point.x, point.z).length() - radius, 0.0)
		var end := maxf(absf(point.y) - cylinder.height * 0.5, 0.0)

		return Vector2(side, end).length()

	var box := mesh.get_aabb()
	var from_centre := (point - box.get_center()).abs() - box.size * 0.5

	return from_centre.max(Vector3.ZERO).length()


## A bone and each bone above it, up to the root.
static func _bones_above(rig: FigureRig, bone: String) -> PackedStringArray:
	var found := PackedStringArray()
	var walk := bone

	# A parent loop in a bad file must not hang the editor.
	for _step in rig.bones().size():
		if not rig.has_bone(walk):
			break

		found.append(walk)
		walk = rig.bone(walk)["parent"]

	return found
