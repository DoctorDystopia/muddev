class_name ModelLoader
extends Node
## Tier 1 of the mesh ladder: fetch a `.glb`, and stand it up.
##
## The only file in the client that knows HTTP or glTF exist. Everything above
## it asks [MeshResolver] for a mesh and never learns whether one arrived over a
## network — which is what lets tiers 2 and 3 be pure and testable while this
## one is neither.
##
## ## Why fetched and never bundled
##
## Art inside the `.pck` ships BEFORE the login prompt, and that is 12 MiB today
## with most of it a single character. The browser fetches a `.glb` only when
## something needs drawing, so a player who never opens the inventory never
## downloads the sword; a Godot export can only match that by fetching too. See
## [ModelRegistry] on why a served manifest beats convention-plus-404.
##
## ## Every model is normalised into a unit box
##
## Not optional, and not obvious until measured: the packed sword's own bounds
## are 0.33 x **9.80** x 1.02. Left alone it would stand ten tiles tall. Tier 2
## shapes are authored inside a unit box, so normalising here is what makes all
## three tiers interchangeable and lets each caller apply one scale of its own.
##
## The LONGEST axis becomes one unit and the other two follow, so proportions
## survive. Then [method ModelRegistry.rotation_for] applies the orientation a
## bounding box cannot infer — no measurement can tell you which end of a sword
## is the tip.
##
## ## One fetch per asset, however many ask
##
## A prototype cache plus an in-flight set. Ten stacks of the same item cost one
## request rather than ten, and a second ask that arrives mid-flight waits on
## the first rather than starting a second. Callers always get their own copy;
## the cached prototype is never handed out, because callers reparent, scale and
## tint what they receive.

## Emitted when the manifest has been fetched and folded in.
##
## `count` is how many models it named, and zero is a survivable answer: every
## resolve then falls to a family shape, which is the same state the client is
## in before the fetch completes.
signal manifest_ready(count: int)

## Emitted when an asset finishes loading, successfully or not.
##
## `model` is null on failure. Failure is a normal outcome here — the art is a
## convenience and the caller already has a family shape to fall back to.
signal loaded(asset_key: String, model: Node3D)

## How long to wait on one model before giving up.
const TIMEOUT_SECONDS := 20.0

## The longest edge every model is scaled to. Matches the unit box tier 2 is
## authored in; see the class comment.
const UNIT := 1.0

## Below this, a model's bounds are treated as degenerate and left alone rather
## than divided by. A flat plane legitimately has a zero axis; scaling by the
## reciprocal of that is an inf that propagates into the transform.
const MIN_EXTENT := 0.0001

## Where this build fetches art from, as an absolute origin — on the web that is
## the page's own, which is how the fetch stays same-origin; see
## [method ServerEndpoint.asset_origin].
##
## Empty is a FAILURE and not a shorthand for "relative": `HTTPRequest` parses
## the URL and refuses one with no scheme, so an empty origin here means nothing
## is ever fetched and every entity falls back to its family shape.
var _origin := ""

## The registry that knows which keys have art and how each is oriented.
var _registry: ModelRegistry

## asset_key -> Node3D prototype. Never handed out directly.
var _prototypes: Dictionary = {}

## asset_key -> true while a request is in the air.
var _in_flight: Dictionary = {}

## asset_key -> true for a key that was asked for and could not be loaded.
##
## A permanent answer, deliberately. Without it a pane that rebuilds every time
## the room changes would re-request a file that is not coming, once per rebuild,
## forever.
var _failed: Dictionary = {}


func _init(registry: ModelRegistry, origin: String) -> void:
	_registry = registry
	_origin = origin


## Free the cached prototypes.
##
## They are deliberately kept OUT of the scene tree — they are stock to copy
## from, not things to draw — which means nothing frees them automatically and
## the engine reports every one as a leaked instance at shutdown. Orphaned nodes
## are the caller's to free, and this is the caller.
func _exit_tree() -> void:
	for asset_key: String in _prototypes:
		var prototype: Node3D = _prototypes[asset_key]

		if is_instance_valid(prototype):
			prototype.free()

	_prototypes.clear()


## Whether this key can ever produce art.
##
## False for a key with no manifest entry AND for one that has already failed.
## The distinction matters to [MeshResolver.resolve_scenery], which draws
## nothing rather than a fallback — asking it to keep hoping would leave a tile
## permanently waiting for a model that will not arrive.
func can_load(asset_key: String) -> bool:
	if _failed.has(asset_key):
		return false

	return _registry != null and _registry.has_model(asset_key)


## A copy of an already-loaded model, or null.
##
## Synchronous and never fetches. This is what a caller uses when it wants art
## only if it is already to hand — the first draw after a room change should not
## block on a network round trip.
func cached(asset_key: String) -> Node3D:
	var prototype: Node3D = _prototypes.get(asset_key)

	if prototype == null:
		return null

	var copy := prototype.duplicate() as Node3D

	_take_own_materials(copy)

	return copy


## Give one copy materials of its own, so tinting it tints only it.
##
## `duplicate()` copies nodes but SHARES the resources they point at, and a
## glTF's materials live on the Mesh rather than on the instance — so every copy
## of an asset key starts out painted by one material. Flashing a single mutant
## raider white would flash every mutant raider in the neighbourhood.
##
## This is the same problem three.js's `takeOwnMaterials` solves on the browser
## side, and the same trade: materials are duplicated, the MESH and its textures
## stay shared, which is the expensive half. Tier 2 needs none of this —
## [MeshBuilder] already builds a fresh material per part — so the cost is paid
## only where it is real.
static func _take_own_materials(root: Node3D) -> void:
	var stack: Array[Node] = [root]

	while not stack.is_empty():
		var node: Node = stack.pop_back()
		var instance := node as MeshInstance3D

		if instance != null and instance.mesh != null:
			for surface: int in instance.mesh.get_surface_count():
				var material := instance.mesh.surface_get_material(surface)

				if material != null:
					instance.set_surface_override_material(
						surface, material.duplicate())

		for child: Node in node.get_children():
			stack.append(child)


## Fetch the served manifest and fold it into the registry.
##
## Until this completes the registry knows about no art at all, so every resolve
## falls through to a family shape. That is a correct intermediate state and not
## an error: the first snapshot renders generics and sharpens when the manifest
## lands. A failed fetch simply leaves the client in that state permanently,
## which is a degraded look rather than a broken game.
func fetch_manifest() -> void:
	var url := _registry.manifest_url(_origin)
	var http := HTTPRequest.new()

	http.timeout = TIMEOUT_SECONDS
	add_child(http)

	http.request_completed.connect(
		func(result: int, code: int, _headers: PackedStringArray,
				body: PackedByteArray):
			http.queue_free()
			_finish_manifest(result, code, body))

	var err := http.request(url)

	if err != OK:
		http.queue_free()
		push_warning("ModelLoader: manifest request refused: error %d" % err)
		manifest_ready.emit(0)


func _finish_manifest(result: int, code: int, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or code != 200:
		push_warning("ModelLoader: manifest http %d (result %d)" % [code, result])
		manifest_ready.emit(0)
		return

	var document: Variant = JSON.parse_string(body.get_string_from_utf8())
	var count := _registry.ingest_manifest(document)

	manifest_ready.emit(count)


## Ask for a model. The [signal loaded] signal carries the answer.
##
## Safe to call repeatedly for the same key: an already-cached asset replies on
## the next frame, an in-flight one is folded into the request already running,
## and a failed one replies null immediately rather than trying again.
func request(asset_key: String) -> void:
	if _prototypes.has(asset_key):
		loaded.emit.call_deferred(asset_key, cached(asset_key))
		return

	if _in_flight.has(asset_key):
		return

	if not can_load(asset_key):
		loaded.emit.call_deferred(asset_key, null)
		return

	var url := _registry.url_for(_origin, asset_key)

	if url.is_empty():
		_fail(asset_key, "no path in the manifest")
		return

	_in_flight[asset_key] = true
	_start(asset_key, url)


# ─── Private ─────────────────────────────────────────────────────────────────

func _start(asset_key: String, url: String) -> void:
	var http := HTTPRequest.new()
	http.timeout = TIMEOUT_SECONDS
	add_child(http)

	http.request_completed.connect(
		func(result: int, code: int, _headers: PackedStringArray,
				body: PackedByteArray):
			http.queue_free()
			_finish(asset_key, result, code, body))

	var err := http.request(url)

	if err != OK:
		http.queue_free()
		_fail(asset_key, "request refused: error %d" % err)


func _finish(asset_key: String, result: int, code: int,
		body: PackedByteArray) -> void:
	_in_flight.erase(asset_key)

	if result != HTTPRequest.RESULT_SUCCESS or code != 200:
		# The likeliest cause on the web is a cross-origin refusal, which the
		# browser reports to the page and not to us -- so name it here rather
		# than leaving a bare status code to be puzzled over at 2am.
		_fail(asset_key, "http %d (result %d); if this is a web build, check "
			% [code, result] + "that the art is served from the page's origin")
		return

	var model := _build(asset_key, body)

	if model == null:
		_fail(asset_key, "could not be read as glTF")
		return

	_prototypes[asset_key] = model
	loaded.emit(asset_key, cached(asset_key))


## Bytes to a scene, normalised into the unit box and oriented.
func _build(asset_key: String, body: PackedByteArray) -> Node3D:
	var document := GLTFDocument.new()
	var state := GLTFState.new()

	if document.append_from_buffer(body, "", state) != OK:
		return null

	var scene := document.generate_scene(state) as Node3D

	if scene == null:
		return null

	# WRAPPED, and this is load-bearing. The normalise below writes `scale` and
	# `position`, and every caller then sets `scale` on what it was handed --
	# EntityPool to ENTITY_SCALE, the world pane to TILE_PROP_SCALE. Handing
	# back the scene itself meant that assignment OVERWROTE the normalisation,
	# so a model drew at its raw glTF size times the caller's scale. The
	# transition pad is enormous, and it looked exactly like that.
	#
	# The wrapper's transform stays identity, so a caller may set scale,
	# position and rotation freely -- the same contract MeshBuilder already
	# offers, which is why tier 2 never had this bug.
	var wrapper := Node3D.new()

	wrapper.add_child(scene)
	_normalise(scene)
	_orient(asset_key, scene)

	return wrapper


## Scale so the longest axis is one unit, and centre on the origin.
func _normalise(scene: Node3D) -> void:
	var bounds := bounds_of(scene)
	var longest := maxf(bounds.size.x, maxf(bounds.size.y, bounds.size.z))

	if longest < MIN_EXTENT:
		return

	var factor := UNIT / longest

	scene.scale = Vector3.ONE * factor
	# After scaling, because the centre being corrected is the SCALED one.
	scene.position = -bounds.get_center() * factor


## Apply every correction a bounding box cannot infer.
##
## Three of them, all hand-written in [ModelRegistry] and none derivable: which
## way is up, where the visible mass actually sits, and whether the export is
## lying about being transparent.
func _orient(asset_key: String, scene: Node3D) -> void:
	var rotation := _registry.rotation_for(asset_key)

	if rotation != Vector3.ZERO:
		scene.rotation = rotation

	# AFTER the normalise centred it, and in normalised units, so the number
	# means the same thing whatever size the source model happened to be.
	scene.position += _registry.offset_for(asset_key)

	if _registry.force_opaque(asset_key):
		_force_opaque(scene)


## Make every material in one model solid.
##
## Written on the MESH's materials rather than as instance overrides, because
## this runs once on the prototype and every copy should inherit it -- unlike a
## hit flash, which is per copy and is why [method _take_own_materials] exists at
## all. Both alpha and the transparency MODE are reset: leaving the mode on
## ALPHA_DEPTH_PRE_PASS keeps the surface in the transparent queue, sorting
## badly against itself, even at full opacity.
static func _force_opaque(root: Node3D) -> void:
	var stack: Array[Node] = [root]

	while not stack.is_empty():
		var node: Node = stack.pop_back()
		var instance := node as MeshInstance3D

		if instance != null and instance.mesh != null:
			for surface: int in instance.mesh.get_surface_count():
				var material := instance.mesh.surface_get_material(
					surface) as StandardMaterial3D

				if material == null:
					continue

				material.transparency = BaseMaterial3D.TRANSPARENCY_DISABLED
				material.albedo_color.a = 1.0

		for child: Node in node.get_children():
			stack.append(child)


## The combined bounds of every mesh under a node, in the ROOT's space.
##
## Public because the world pane needs the same measurement to rest a prop ON a
## tile rather than through it: a normalised model fills the unit box on its
## LONGEST axis only, so half a prop's height is not half its scale.
##
## Transforms are accumulated by hand rather than read from `global_transform`,
## because a freshly generated glTF scene is not in the tree yet — outside it
## `global_transform` is just the local one, so anything nested more than a
## level deep would be measured in the wrong space and a model with a rigged
## hierarchy would normalise to the wrong size.
static func bounds_of(root: Node3D) -> AABB:
	var bounds := _mesh_bounds(root)

	# SKINNED meshes measure wrong, and badly. A rigged model's vertices are
	# stored in bind space and placed by bones at draw time, so `mesh.get_aabb()`
	# describes the bind pose rather than anything you can see. Measured
	# 08/26/2026 on the Spider-Man placeholder player_character carried until
	# 08/27/2026: its mesh box is 0.74 x **0.17** x 1.00 while its skeleton spans
	# 1.04 tall. Normalising by the mesh box therefore made the character about
	# six times too big, and centring that box left it floating.
	#
	# The base character that replaced it does NOT reproduce that -- its bind
	# pose is the pose, so the two boxes agree. The merge stays because the
	# failure is a property of rigged glTF and not of one download, and because
	# nothing about a file announces which kind it is.
	#
	# Bone origins are a floor on the real extent, not the whole of it -- the top
	# of a head reaches past the head bone. It is an approximation, and a far
	# better one than being wrong by 6x. The exact answer needs the skinning
	# baked into the mesh, which belongs in `assets/pack_model.py`: these models
	# carry skinning attributes for ZERO animations, so the rig is dead weight
	# that also breaks measurement.
	var skeleton := _skeleton_bounds(root)

	if skeleton != AABB():
		bounds = bounds.merge(skeleton)

	return bounds


## Bounds of the meshes alone, in the root's space.
static func _mesh_bounds(root: Node3D) -> AABB:
	var bounds := AABB()
	var found := false

	# Each entry pairs a node with its transform relative to root. Root's own
	# transform is deliberately excluded: the bounds wanted here are the ones
	# _normalise is about to overwrite.
	var stack: Array = [[root, Transform3D.IDENTITY]]

	while not stack.is_empty():
		var entry: Array = stack.pop_back()
		var node: Node = entry[0]
		var to_root: Transform3D = entry[1]
		var instance := node as MeshInstance3D

		if instance != null and instance.mesh != null:
			var box := _instance_bounds(instance, to_root)

			bounds = box if not found else bounds.merge(box)
			found = true

		for child: Node in node.get_children():
			var spatial := child as Node3D
			var child_transform := to_root

			if spatial != null:
				child_transform = to_root * spatial.transform

			stack.append([child, child_transform])

	return bounds


## One mesh's extent in the root's space, read as tightly as it honestly can be.
##
## Two ways, and the MESH picks which -- not the caller, and not a cost budget.
##
## A STATIC mesh is measured VERTEX BY VERTEX. `to_root * mesh.get_aabb()`
## measures the transformed BOX rather than the geometry inside it, and a
## rotated box has corners its contents do not: the gatherable's rock is one
## part tilted by (0.5, 0.3, 0.2) radians, and its box reaches 0.164 further
## down than any vertex in it. Everything in this client rests on the BOTTOM of
## this number, so that 0.164 was a gathering node hovering a twelfth of a tile
## over its own ground -- measured 08/27/2026, and it was the reported bug.
##
## A SKINNED mesh is measured by its box, because its vertices are stored in
## bind space and put where you see them by bones at draw time. Reading 38,000
## of them precisely would be 38,000 precise readings of a pose nobody renders;
## the crude box is all they support, and [method _skeleton_bounds] is what
## corrects for it. See [method bounds_of].
static func _instance_bounds(instance: MeshInstance3D,
		to_root: Transform3D) -> AABB:
	if instance.skin != null:
		return to_root * instance.mesh.get_aabb()

	var bounds := AABB()
	var found := false

	for surface: int in instance.mesh.get_surface_count():
		var arrays: Array = instance.mesh.surface_get_arrays(surface)

		if arrays.is_empty():
			continue

		var vertices: Variant = arrays[Mesh.ARRAY_VERTEX]

		if typeof(vertices) != TYPE_PACKED_VECTOR3_ARRAY:
			continue

		for vertex: Vector3 in vertices as PackedVector3Array:
			var point := to_root * vertex

			if not found:
				bounds = AABB(point, Vector3.ZERO)
				found = true
			else:
				bounds = bounds.expand(point)

	# A mesh that hands out no vertex array at all -- an ImmediateMesh, or one
	# whose surfaces this build cannot read back. The box is wrong in the way
	# described above and is still better than measuring nothing.
	if not found:
		return to_root * instance.mesh.get_aabb()

	return bounds


func _fail(asset_key: String, why: String) -> void:
	_in_flight.erase(asset_key)
	_failed[asset_key] = true

	push_warning("ModelLoader: %s -- %s" % [asset_key, why])
	loaded.emit(asset_key, null)


## Where a model's bones sit, in the root's space, or an empty AABB.
##
## Only meaningful for a rigged model; a static one has no Skeleton3D and this
## answers empty, which [method bounds_of] then ignores. REST poses are read
## rather than current ones because nothing here is animated -- and because the
## prototype being measured is not in the tree, where a current pose would not
## have been resolved anyway.
static func _skeleton_bounds(root: Node3D) -> AABB:
	var bounds := AABB()
	var found := false
	var stack: Array = [[root, Transform3D.IDENTITY]]

	while not stack.is_empty():
		var entry: Array = stack.pop_back()
		var node: Node = entry[0]
		var to_root: Transform3D = entry[1]
		var skeleton := node as Skeleton3D

		if skeleton != null:
			for bone: int in skeleton.get_bone_count():
				var point: Vector3 = (to_root
					* skeleton.get_bone_global_rest(bone)).origin

				if not found:
					bounds = AABB(point, Vector3.ZERO)
					found = true
				else:
					bounds = bounds.expand(point)

		for child: Node in node.get_children():
			var spatial := child as Node3D
			var child_transform := to_root

			if spatial != null:
				child_transform = to_root * spatial.transform

			stack.append([child, child_transform])

	return bounds
