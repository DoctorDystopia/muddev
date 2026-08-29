extends Node
## Unit tests for the terrain layer: which map is surfaced with what, and the
## space that placement is measured in. Needs no server and no art -- the model
## a real fetch would produce is hand-built here as the same shape.
##
##     godot --headless --path godot res://tests/test_map_terrain.tscn
##
## Exits 0 when every case passes, 1 on the first failure.
##
## THE BUG THIS FILE EXISTS TO CATCH IS SILENT, twice over. Terrain that is
## measured in one space and placed in another does not raise: the tiles simply
## sink into the slab, or float over it, or -- if a model's meshes are offset
## from each other -- collapse onto one cell. And a map whose terrain is not
## forced opaque draws the whole world into the transparent queue, which looks
## like a sorting bug in everything ELSE.

## How far off two floats may be and still be called equal.
##
## Loose on purpose. Every number here comes out of a Transform3D multiply, so
## the question is whether the maths is right, not whether it is bit-exact.
const TOLERANCE := 0.0001

var _failures := 0


func _ready() -> void:
	_a_map_with_no_terrain_names_none()
	_a_surfaced_map_names_its_art()
	_terrain_is_never_transparent()
	_a_map_is_surfaced_only_once_its_art_could_exist()
	_the_two_palettes_differ_only_where_nobody_chose_a_colour()
	_mesh_parts_answers_in_the_same_space_as_bounds()
	_a_nested_mesh_keeps_its_place_inside_the_model()
	_a_model_with_nothing_to_draw_has_no_parts()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: map_terrain")
	get_tree().quit(0)


# ─── Which map is surfaced ───────────────────────────────────────────────────

## The fallback is the whole reason the table can stay short.
##
## A map nobody has drawn keeps the plain coloured slab, so content ships ahead
## of art here exactly as it does for a tile prop or an unmodelled item.
func _a_map_with_no_terrain_names_none() -> void:
	_expect(MapPalette.tile_model("trade town sector 1").is_empty(),
		"a map with no terrain entry names no art")
	_expect(MapPalette.tile_model("").is_empty(),
		"and neither does no map at all")


## Derived from the table rather than retyped from it.
##
## An assertion spelling "oasis" -> "tile_oasis" as a literal is one that agrees
## with the table because it was copied out of it. What is worth pinning is that
## every row ANSWERS -- a lookup that silently returned "" for a listed map is
## the failure, and it looks identical to a map that was never listed.
func _a_surfaced_map_names_its_art() -> void:
	_expect(not MapPalette.TILE_MODELS.is_empty(),
		"some map is surfaced at all")

	for z: String in MapPalette.TILE_MODELS:
		_expect(not MapPalette.tile_model(z).is_empty(),
			"%s answers with the art it is surfaced by" % z)
		_expect(MapPalette.tile_model(z) == MapPalette.TILE_MODELS[z],
			"and answers the table rather than something else")


## The ground is the one surface everything else is drawn on top of.
##
## A glTF material that declares alphaMode BLEND -- which Blender writes for any
## material carrying an RGBA image, used or not -- puts its mesh in the sorted
## transparent queue. On a prop that is a wasted pass; on the ground it is every
## entity, prop and marker in the pane sorting against the floor beneath them.
## So terrain carries the correction, and it has to carry it per asset key.
func _terrain_is_never_transparent() -> void:
	var registry := ModelRegistry.new()

	for z: String in MapPalette.TILE_MODELS:
		var asset_key: String = MapPalette.TILE_MODELS[z]

		_expect(registry.force_opaque(asset_key),
			"%s is forced opaque, so the ground does not sort" % asset_key)


# ─── Which palette a map is drawn in ─────────────────────────────────────────

## Surfaced means "art could exist for this ground", not "art has arrived".
##
## THE DIFFERENCE IS A SECOND LONG AND IT MATTERS BOTH WAYS. Answering "has it
## arrived" makes an island come up in hashed hues and then change colour when
## the model lands, which reads as a bug. Answering "is it configured" leaves a
## map whose art is never coming -- a failed deploy, a model tree the export
## forgot -- permanently neutral, with nothing left to tell a bank from a
## clearing. `may_have_art` is false before the manifest and false again after a
## failure, so both panes fall back together and neither flickers.
func _a_map_is_surfaced_only_once_its_art_could_exist() -> void:
	for z: String in MapPalette.TILE_MODELS:
		_expect(not MapPalette.is_surfaced(z, null),
			"%s is not surfaced with no resolver at all" % z)

	var meshes := _resolver_naming([])

	for z: String in MapPalette.TILE_MODELS:
		_expect(not MapPalette.is_surfaced(z, meshes),
			"%s is not surfaced before its art is in the manifest" % z)

	meshes.free()
	meshes = _resolver_naming(MapPalette.TILE_MODELS.values())

	for z: String in MapPalette.TILE_MODELS:
		_expect(MapPalette.is_surfaced(z, meshes),
			"%s is surfaced once the manifest names its art" % z)

	# A map with no terrain row stays bare however much art the server has.
	_expect(not MapPalette.is_surfaced("trade town sector 1", meshes),
		"a map with no terrain row is never surfaced")

	meshes.free()


## The two palettes agree about authored kinds and part company about the rest.
##
## That is the entire behaviour change, stated once: a bank is worth marking on
## any map, and the hue "Oasis" happens to hash to is worth marking on none that
## draws its own ground. Asserted as the RELATIONSHIP rather than against
## literal colours, so re-tuning either table cannot make this test wrong.
func _the_two_palettes_differ_only_where_nobody_chose_a_colour() -> void:
	for kind: String in MapPalette.ROOM_KIND_COLORS:
		_expect(MapPalette.tile_colour(kind, true)
				== MapPalette.tile_colour(kind, false),
			"an authored kind (%s) is the same colour on either map" % kind)

	# "Oasis" is the case this was built for: the ground of a surfaced map, and
	# a kind no table names.
	var unlisted := "Oasis"

	_expect(not MapPalette.ROOM_KIND_COLORS.has(unlisted),
		"%s is genuinely unauthored, so this case tests something" % unlisted)
	_expect(MapPalette.tile_colour(unlisted, true)
			!= MapPalette.tile_colour(unlisted, false),
		"an unauthored kind is NOT hashed on a map that draws its own ground")
	_expect(MapPalette.tile_colour(unlisted, true)
			== MapPalette.COLOR_TILE_DEFAULT,
		"it falls to the same neutral a kindless tile already used")


# ─── The space placement is measured in ──────────────────────────────────────

## The invariant the whole placement rests on.
##
## `_build_terrain` measures the model with `bounds_of` to decide how far to
## lift it, then stamps its meshes with the transforms `mesh_parts` reports. If
## those two answered in different spaces the lift would be computed against one
## model and applied to another, and nothing would say so -- the terrain would
## simply sit at the wrong height.
##
## Asserted as a RELATIONSHIP: the part transforms applied to their own meshes
## have to reproduce the bounds, because that is the only thing the placement
## actually needs to be true.
func _mesh_parts_answers_in_the_same_space_as_bounds() -> void:
	var model := _model_of([
		[Vector3(2.0, 0.5, 2.0), Transform3D(Basis.IDENTITY, Vector3(0.0, 1.0, 0.0))],
	])
	var measured := ModelLoader.bounds_of(model)
	var rebuilt := _bounds_from_parts(model)

	_expect(_boxes_match(measured, rebuilt),
		"the parts rebuild the bounds they were measured beside")

	model.free()


## The same claim, for a model whose meshes do NOT all sit at its origin.
##
## One mesh cannot tell the two spaces apart -- if every part transform were
## returned as identity the case above would still pass, because a single mesh
## centred on the model's own origin is the same box either way. Two meshes at
## different depths and different offsets is what makes the accumulation
## observable, and an accumulation that is dropped shows up here as both meshes
## landing on the same spot.
func _a_nested_mesh_keeps_its_place_inside_the_model() -> void:
	var model := _model_of([
		[Vector3.ONE, Transform3D(Basis.IDENTITY, Vector3(-2.0, 0.0, 0.0))],
		[Vector3.ONE, Transform3D(Basis.IDENTITY, Vector3(2.0, 0.0, 0.0))],
	])
	var parts := ModelLoader.mesh_parts(model)

	_expect(parts.size() == 2, "both meshes are reported")

	var origins: Array = []

	for part: Array in parts:
		var placement: Transform3D = part[1]
		origins.append(placement.origin.x)

	origins.sort()

	_expect(origins.size() == 2 and absf(origins[0] + 2.0) < TOLERANCE
			and absf(origins[1] - 2.0) < TOLERANCE,
		"and each keeps the offset it has inside the model")

	_expect(_boxes_match(ModelLoader.bounds_of(model), _bounds_from_parts(model)),
		"so the two answers still agree about the whole")

	model.free()


## A model that draws nothing is not an error, and must not be treated as one.
##
## `resolve_scenery` already answers null for art that has not arrived; this is
## the other shape of the same state -- art that arrived and turned out to hold
## no mesh. The pane builds an empty Terrain node, which draws nothing, which is
## what a map with no art looks like anyway.
func _a_model_with_nothing_to_draw_has_no_parts() -> void:
	var empty := Node3D.new()

	empty.add_child(Node3D.new())

	_expect(ModelLoader.mesh_parts(empty).is_empty(),
		"a model with no meshes reports no parts")

	empty.free()


# ─── Fixtures ────────────────────────────────────────────────────────────────

## A resolver that has been told about exactly these asset keys.
##
## Fed through `ingest_manifest` rather than fetched, so this needs no server:
## the registry is the whole of what `may_have_art` consults before anything has
## been requested.
func _resolver_naming(asset_keys: Array) -> MeshResolver:
	var document := {}

	for asset_key: String in asset_keys:
		document[asset_key] = "tiles/%s.glb" % asset_key

	var meshes := MeshResolver.new(ModelRegistry.new(), "https://example.invalid")

	meshes.ingest_manifest(document)

	return meshes



## A stand-in for a fetched model, in the shape ModelLoader hands one back.
##
## A wrapper whose transform stays identity, holding a scene node that carries
## the normalising scale, holding the meshes. Built by hand rather than loaded,
## so this file needs no art and no network -- and so the nesting is explicit,
## which is the thing being tested.
func _model_of(boxes: Array) -> Node3D:
	var wrapper := Node3D.new()
	var scene := Node3D.new()

	wrapper.add_child(scene)

	for entry: Array in boxes:
		var box := BoxMesh.new()
		var instance := MeshInstance3D.new()

		box.size = entry[0]
		instance.mesh = box
		instance.transform = entry[1]
		scene.add_child(instance)

	return wrapper


## The bounds of a model, computed the long way round: from its parts.
func _bounds_from_parts(model: Node3D) -> AABB:
	var bounds := AABB()
	var found := false

	for part: Array in ModelLoader.mesh_parts(model):
		var mesh: Mesh = part[0]
		var placement: Transform3D = part[1]
		var box := placement * mesh.get_aabb()

		bounds = box if not found else bounds.merge(box)
		found = true

	return bounds


func _boxes_match(left: AABB, right: AABB) -> bool:
	return left.position.distance_to(right.position) < TOLERANCE \
		and left.size.distance_to(right.size) < TOLERANCE


# ─── Harness ─────────────────────────────────────────────────────────────────

func _expect(condition: bool, what: String) -> void:
	if condition:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
