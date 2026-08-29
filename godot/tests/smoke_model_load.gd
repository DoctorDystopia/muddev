extends Node
## Live smoke test: the whole tier-1 pipeline, end to end.
##
## NEEDS A RUNNING EVENNIA (the webserver on 4001, not the Godot socket). No
## account required — this fetches static files and never logs in.
##
##     godot --headless --path godot res://tests/smoke_model_load.tscn
##
## ## Why this cannot be a unit test
##
## Every interesting step here is I/O or engine internals: an HTTP fetch, a
## glTF parse, and the normalise that depends on what the real file actually
## contains. The measurement that motivated the whole normalise step —
## the packed sword's bounds being 0.33 x 9.80 x 1.02 — is a fact about a file
## on disk, and no amount of hand-built payload would have revealed it.
##
## What IS pure lives in test_family_shapes: the shape table, the builder, and
## the unit-box invariant this test confirms tier 1 also obeys.

const TIMEOUT_SECONDS := 25.0

## Served by Evennia, and named in models/manifest.json.
const KNOWN_ASSET := "rusty_scrap_shortsword"

## The RIGGED one. Carries a skeleton, and is the model whose placement the
## measurement ladder is most easily wrong about.
const RIGGED_ASSET := "player_character"

## The one whose export declares itself transparent and is not.
const TRANSPARENT_ASSET := "floating_eye"

## How far off square a terrain tile's footprint may land, as a ratio.
##
## Tighter than UNIT_TOLERANCE because this is not float slop: a tile is either
## the square the grid stamps it as or it is not, and the difference between
## 1.00 and 0.88 is a visible gap between every pair of tiles in the world.
const SQUARE_TOLERANCE := 0.02

## How far off a unit the longest axis may land. Generous: the normalise divides
## by a measured extent, so this is float slop rather than a tolerance on the
## intent.
const UNIT_TOLERANCE := 0.02

var _failures := 0
var _resolver: MeshResolver

## The two models fetched last, until each has reported. The test finishes when
## this empties, NOT when the first of them lands.
##
## Every fetch gets its own HTTPRequest, so they race, and the eye is the
## smaller file -- so calling _finish() from whichever arrived first quietly
## SKIPPED the character's checks on every run. A skipped assertion looks
## exactly like a passing one in the output, which is the whole reason this
## exists rather than an ordering assumption.
var _outstanding := {}


func _ready() -> void:
	get_tree().create_timer(TIMEOUT_SECONDS).timeout.connect(_give_up)

	# The dev origin explicitly: this test is about the pipeline, not about
	# which build we are. See ServerEndpoint.asset_origin for that decision.
	_resolver = MeshResolver.new(ModelRegistry.new(),
		ServerEndpoint.ASSET_DEV_ORIGIN)
	add_child(_resolver)

	_resolver.manifest_ready.connect(_on_manifest)
	_resolver.start()


func _on_manifest(count: int) -> void:
	print("manifest named %d models" % count)

	_expect(count > 0, "the served manifest names at least one model")
	_expect(_resolver.may_have_art(KNOWN_ASSET),
		"%s is one of them" % KNOWN_ASSET)
	_expect(not _resolver.may_have_art("nothing_is_modelled_as_this"),
		"an unknown key has no art")

	# Before the fetch, art is not to hand -- so an entity still draws, from its
	# family. This is the "renders generics and sharpens" state, asserted rather
	# than assumed.
	var early := _resolver.resolve_entity(KNOWN_ASSET, "weapon")

	_expect(early != null, "an entity resolves even before its art arrives")
	early.free()

	# Scenery is the opposite policy and must stay empty-handed.
	var scenery := _resolver.resolve_scenery("nothing_is_modelled_as_this")

	_expect(scenery == null, "scenery with no art draws nothing at all")

	_resolver.refreshed.connect(_on_refreshed)


func _on_refreshed(asset_key: String) -> void:
	if asset_key == RIGGED_ASSET:
		_a_rigged_model_stands_up()
		_reported(asset_key)
		return

	if asset_key == TRANSPARENT_ASSET:
		_an_export_lying_about_transparency_is_corrected()
		_reported(asset_key)
		return

	if MapPalette.TILE_MODELS.values().has(asset_key):
		_a_terrain_tile_is_a_unit_square(asset_key)
		_reported(asset_key)
		return

	if asset_key != KNOWN_ASSET:
		return

	var model := _resolver.resolve_entity(KNOWN_ASSET, "weapon")

	_expect(model != null, "the model resolves once fetched")

	if model == null:
		_finish()
		return

	# The payoff. The file on disk is 9.8 units tall; if this is not ~1 the
	# sword stands ten tiles high and the ladder's tiers are not interchangeable.
	var bounds := _bounds_of(model)
	var longest := maxf(bounds.size.x, maxf(bounds.size.y, bounds.size.z))

	print("normalised bounds: %.3f x %.3f x %.3f"
		% [bounds.size.x, bounds.size.y, bounds.size.z])

	_expect(absf(longest - 1.0) < UNIT_TOLERANCE,
		"the longest axis normalises to one unit (is %.3f)" % longest)
	_expect(bounds.size.y > bounds.size.x,
		"and the sword is still taller than it is wide")

	# THE REGRESSION. Everything above measured the model as handed over, and it
	# was correct -- but every caller then assigns `scale`, and the normalise
	# used to live on that same property, so the assignment silently threw it
	# away and the model drew at raw glTF size. A transition pad the size of the
	# map is what that looks like.
	#
	# Scaling what you were handed must scale a UNIT box, whatever tier it came
	# from. Checked here rather than in the callers so one test covers the seam
	# for all of them.
	var scaled := _resolver.resolve_entity(KNOWN_ASSET, "weapon")

	scaled.scale = Vector3.ONE * 0.34

	var scaled_bounds := _bounds_of(scaled)
	var scaled_longest := maxf(scaled_bounds.size.x,
		maxf(scaled_bounds.size.y, scaled_bounds.size.z))

	print("scaled to 0.34 -> longest %.3f" % scaled_longest)

	_expect(absf(scaled_longest - 0.34) < UNIT_TOLERANCE,
		"a caller's scale multiplies the unit box rather than replacing the "
		+ "normalise (longest is %.3f, wanted 0.34)" % scaled_longest)

	scaled.free()
	model.free()

	# Cached now, so a second ask is synchronous and does not refetch.
	var again := _resolver.resolve_entity(KNOWN_ASSET, "weapon")

	_expect(again != null, "a second ask is served from cache")

	if again != null:
		again.free()

	_scenery_draws_only_what_has_art()

	# Kicks off the character fetch. Finishing waits for it: measuring now
	# would measure the FAMILY SHAPE, which is what the first version of this
	# test did -- it passed while checking the procedural figure, because the
	# tier-2 fallback is what a first ask returns.
	_outstanding = {RIGGED_ASSET: true, TRANSPARENT_ASSET: true}

	var pending := _resolver.resolve_entity(RIGGED_ASSET, "character")
	pending.free()

	var eye := _resolver.resolve_entity(TRANSPARENT_ASSET, "npc")
	eye.free()

	# Every terrain the maps are surfaced with, from the table rather than by
	# name -- a tile added for a third map is covered without an edit here, and
	# the footprint check below is exactly the one a new tile is likely to fail.
	for z: String in MapPalette.TILE_MODELS:
		var terrain_key: String = MapPalette.TILE_MODELS[z]

		# ASKED BEFORE IT IS WAITED ON. Terrain that the served manifest does
		# not name never fetches, so `refreshed` never fires for it and this
		# test would sit out its whole timeout and then report the timeout --
		# which says "is Evennia running?" about a server that is running fine
		# and has simply not had collectstatic run over a new .glb.
		if not _resolver.may_have_art(terrain_key):
			_expect(false, "%s is in the served manifest (surfaces %s). Repack "
				% [terrain_key, z]
				+ "and reload Evennia so collectstatic picks it up")
			continue

		_outstanding[terrain_key] = true

		var ground := _resolver.resolve_scenery(terrain_key)

		if ground != null:
			ground.free()


## The character is measured standing up, whatever its bind pose claims.
##
## THE BUG THIS GUARDS. A rigged model's vertices are stored in bind space and
## placed by bones at draw time, so `mesh.get_aabb()` describes a pose nobody
## sees. The Spider-Man placeholder measured 0.74 x **0.17** x 1.00 that way --
## flat, as if lying down -- against a skeleton spanning 1.04 tall, and
## normalising by the mesh box made the character six times too big and left it
## floating. `ModelLoader.bounds_of` merges the skeleton's box in for that
## reason, and the placement uses it, so this assertion has to as well.
##
## THE CURRENT ASSET DOES NOT REPRODUCE THAT, and the check is written knowing
## it. Quaternius' base character (08/27/2026) is a T-pose whose bind pose is
## the pose -- 1.859 x 1.820 x 0.297 as it comes out of the file -- so its mesh
## box and its merged box agree, and no ratio between them can prove the
## skeleton was read. Asserting they DISAGREE, as this did while the flat model
## was the one served, would now fail on a model measured perfectly correctly.
## (What this function measures is the model AFTER the normalise, so the numbers
## it prints are that box divided by its own longest axis.)
##
## So what is asserted is the property that outlives either asset: the merged
## box is never smaller than the meshes alone -- a merge cannot shrink a box, so
## a violation means bounds_of stopped merging -- and the figure measures far
## taller than it is DEEP. Depth, not width: the T-pose's 1.859 of outstretched
## arms is fractionally wider than it is tall, so "taller than wide" is false
## here for a model that is standing up perfectly straight.
func _a_rigged_model_stands_up() -> void:
	var rigged := _resolver.resolve_entity(RIGGED_ASSET, "character")

	if rigged == null:
		_expect(false, "the character model resolves")
		return

	var bounds := ModelLoader.bounds_of(rigged)
	var mesh_only := _bounds_of(rigged)
	var uprightness := bounds.size.y / maxf(bounds.size.z, 0.0001)

	print("player_character: bounds_of=(%.3f, %.3f, %.3f)  mesh only=(%.3f, %.3f, %.3f)"
		% [bounds.size.x, bounds.size.y, bounds.size.z,
			mesh_only.size.x, mesh_only.size.y, mesh_only.size.z])

	_expect(uprightness > 2.0,
		"a person measures far taller than they are deep (ratio %.2f)"
		% uprightness)

	# A merge cannot make a box smaller. If bounds_of ever reports LESS than the
	# meshes alone it has stopped merging something, which is the failure the
	# skeleton box exists to prevent -- and it is the same assertion whether or
	# not this particular bind pose happens to be honest.
	_expect(bounds.size.y >= mesh_only.size.y - 0.001,
		"and never less than its meshes alone claim (%.3f vs %.3f)"
		% [bounds.size.y, mesh_only.size.y])

	rigged.free()


## An export can be WRONG ABOUT ITSELF, and nothing downstream can tell.
##
## Sketchfab's converter wrote the authoring tool's base-colour alpha into this
## glTF, so the eye's body arrives at alpha 0 against alphaMode BLEND: an
## invisible shell around a floating eyeball. It loads cleanly and reports no
## error, which is exactly why it needs a hand-written correction and a test --
## the only symptom is a person saying it looks wrong.
func _an_export_lying_about_transparency_is_corrected() -> void:
	var eye := _resolver.resolve_entity(TRANSPARENT_ASSET, "npc")

	if eye == null:
		_expect(false, "the eye model resolves")
		return

	var checked := 0
	var stack: Array[Node] = [eye]

	while not stack.is_empty():
		var node: Node = stack.pop_back()
		var instance := node as MeshInstance3D

		if instance != null and instance.mesh != null:
			for surface: int in instance.mesh.get_surface_count():
				var material := instance.get_surface_override_material(
					surface) as StandardMaterial3D

				if material == null:
					continue

				checked += 1
				_expect(material.albedo_color.a > 0.99,
					"%s surface %d is solid, not alpha %.2f"
					% [instance.name, surface, material.albedo_color.a])

		for child: Node in node.get_children():
			stack.append(child)

	# The vacuity guard. Finding no materials at all would pass every check
	# above while proving nothing.
	_expect(checked > 0, "the eye actually has materials to check")

	eye.free()


## A terrain tile comes out a UNIT SQUARE, not merely a unit box.
##
## THE TRAP THIS GUARDS, and it is a trap laid by the normalise rather than by
## any tile. `_normalise` divides by the model's LONGEST axis, which is the
## right rule for a sword and the wrong assumption to carry into a tileset: the
## desert set's `block_a` is a 2x2 tile with a rock lip hanging 0.28 past its
## south edge, so its longest axis is 2.28 and normalising it leaves a footprint
## of 0.877. Stamped on a grid whose spacing assumes 1.0, that is a visible gap
## between every pair of tiles in the world -- and it is silent, because the
## model loaded perfectly and is exactly one unit on the axis it was measured by.
##
## The flat `center_*` tiles this ships with are square to the millimetre and
## pass. The check is here for the day somebody picks a prettier tile.
##
## Y IS DELIBERATELY NOT CHECKED. A terrain tile is nearly flat -- these are
## about 0.015 units tall once normalised -- and the pane rests it on the slab
## by measurement, so its thickness is not something anything depends on.
func _a_terrain_tile_is_a_unit_square(asset_key: String) -> void:
	var ground := _resolver.resolve_scenery(asset_key)

	if ground == null:
		_expect(false, "%s resolves once fetched" % asset_key)
		return

	var bounds := ModelLoader.bounds_of(ground)
	var footprint := maxf(bounds.size.x, bounds.size.z)

	print("%s footprint: %.3f x %.3f, %.3f thick"
		% [asset_key, bounds.size.x, bounds.size.z, bounds.size.y])

	_expect(absf(bounds.size.x - 1.0) < SQUARE_TOLERANCE
			and absf(bounds.size.z - 1.0) < SQUARE_TOLERANCE,
		"%s fills a whole tile (%.3f x %.3f)"
		% [asset_key, bounds.size.x, bounds.size.z])
	_expect(absf(footprint - 1.0) < SQUARE_TOLERANCE,
		"%s is not normalised by an overhang (footprint %.3f)"
		% [asset_key, footprint])
	_expect(not ModelLoader.mesh_parts(ground).is_empty(),
		"%s has meshes for the terrain layer to stamp" % asset_key)

	ground.free()


## The tile-prop path, which is the OTHER policy on the same ladder.
##
## `map_transition` is a room kind with real art, so scenery must produce it —
## while a kind with none must still produce nothing. Both halves matter: the
## first is the feature, and the second is what keeps every ordinary tile from
## sprouting a grey cube.
func _scenery_draws_only_what_has_art() -> void:
	var Const := preload("res://autoload/blackout_constants.gd")

	_expect(_resolver.may_have_art(Const.ROOM_KIND_TRANSITION),
		"the transition room kind has art")

	# First ask starts the fetch and correctly answers "nothing yet"; the pane
	# redraws on `refreshed`. Asserting that here rather than waiting, because
	# it is the behaviour a tile actually sees on the first frame.
	var pending := _resolver.resolve_scenery(Const.ROOM_KIND_TRANSITION)

	if pending != null:
		pending.free()

	_expect(_resolver.resolve_scenery(Const.ROOM_KIND_DEFAULT) == null,
		"an ordinary tile kind never draws a prop, however long it waits")


## Mark one of the last two fetches done, and finish once neither is left.
func _reported(asset_key: String) -> void:
	_outstanding.erase(asset_key)

	if _outstanding.is_empty():
		_finish()


func _finish() -> void:
	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: model_load")
	get_tree().quit(0)


func _give_up() -> void:
	printerr("FAIL: timed out after %.0fs. Is Evennia's webserver on 4001?"
		% TIMEOUT_SECONDS)
	get_tree().quit(1)


## Bounds in the node's own space, accumulating transforms by hand because
## nothing here is in the scene tree. Same reasoning as ModelLoader._bounds_of.
func _bounds_of(root: Node3D) -> AABB:
	var bounds := AABB()
	var found := false
	var stack: Array = [[root, root.transform]]

	while not stack.is_empty():
		var entry: Array = stack.pop_back()
		var node: Node = entry[0]
		var to_root: Transform3D = entry[1]
		var instance := node as MeshInstance3D

		if instance != null and instance.mesh != null:
			var box: AABB = to_root * instance.mesh.get_aabb()

			bounds = box if not found else bounds.merge(box)
			found = true

		for child: Node in node.get_children():
			var spatial := child as Node3D
			var child_transform := to_root

			if spatial != null:
				child_transform = to_root * spatial.transform

			stack.append([child, child_transform])

	return bounds


func _expect(condition: bool, what: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("  not true: %s" % what)
