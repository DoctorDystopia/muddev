class_name MeshResolver
extends Node
## The mesh ladder. Given what the server said a thing is, give back something
## to draw.
##
##     asset has art?    -- yes -->  the model                    tier 1
##            | no
##     family has parts? -- yes -->  the family's shape           tier 2
##            | no
##                                   the generic block            tier 3
##
## This is the only file that knows the ORDER, and the only one panes talk to.
## [ModelLoader] knows how to fetch, [FamilyShapes] knows what a weapon looks
## like, [MeshBuilder] knows how to make a mesh, and none of them knows about
## the others.
##
## ## Two named methods, not one method with a flag
##
## The browser has `hasModel()` and `resolve()`, and the rule binding them lives
## in the caller's memory: ask the first before the second for a tile prop,
## because a tile with no art must stay a plain slab while an entity must always
## draw SOMETHING. That is a policy, and a policy that has to be remembered is
## one that gets forgotten.
##
## Here it is two methods with the policy in their names —
## [method resolve_entity] and [method resolve_scenery]. A boolean parameter
## would have been the same mistake in a different shape.
##
## ## Art sharpens in, it never blocks
##
## Every resolve answers IMMEDIATELY, from the family shape if the model is not
## in hand yet, and emits [signal refreshed] later if art arrives. A caller
## redraws or ignores it. Nothing waits on a network round trip to put an entity
## on screen, which is the same guarantee the browser gives and the reason a
## room full of unmodelled content is playable.

## Emitted when art arrives for a key that was previously drawn as a fallback.
##
## Carries the key, not the mesh: a caller usually has several instances of it
## and asks for its own copies rather than sharing one. Nothing is emitted for a
## key whose art was already cached at resolve time.
signal refreshed(asset_key: String)

## Emitted once the manifest has landed. `count` is how many models it named.
##
## NOT named `ready`: Node already has a signal by that name, and shadowing it
## is a collision waiting to be debugged at the worst possible moment.
signal manifest_ready(count: int)

## Server-owned names, generated from the statefeed constants.
const _Const := preload("res://autoload/blackout_constants.gd")

var _registry: ModelRegistry
var _loader: ModelLoader


## Build a resolver and its loader.
##
## `origin` is where art is fetched from — see
## [method ServerEndpoint.asset_origin]. Taken as a parameter rather than read
## here so a test can point it anywhere and so the whole "which build am I"
## decision keeps one owner.
func _init(registry: ModelRegistry, origin: String) -> void:
	_registry = registry
	_loader = ModelLoader.new(registry, origin)
	_loader.loaded.connect(_on_loaded)
	_loader.manifest_ready.connect(manifest_ready.emit)
	add_child(_loader)


## Something that must always be visible: an entity, an inventory item.
##
## Never returns null. Falls back through the family's shape to the generic
## block, so an asset key nobody has modelled and a family nobody has drawn both
## still put something clickable in the room. That degradation is the whole
## reason content can be added to the game without waiting on art.
func resolve_entity(asset_key: String, family: String) -> Node3D:
	var model := _art_for(asset_key)

	if model != null:
		return model

	return MeshBuilder.build(FamilyShapes.parts_for(family))


## Scenery: drawn only if it has real art.
##
## Returns null when there is none, and that is the point. The world pane draws
## a prop ON a tile that has art and NOTHING on one that does not, because a
## generic block on every unmodelled tile is scenery nobody asked for — every
## tile in the game would sprout a grey cube.
func resolve_scenery(asset_key: String) -> Node3D:
	return _art_for(asset_key)


## Whether this key could ever have art, without fetching it.
##
## For a caller deciding whether to bother asking — a tile that will never have
## a prop should not be revisited on every rebuild.
func may_have_art(asset_key: String) -> bool:
	return _loader.can_load(asset_key)


## Start fetching what the server has art for.
##
## Call once, when the client comes up. Until it completes [method may_have_art]
## answers false for everything and every resolve falls to a family shape —
## a correct intermediate state rather than a broken one, and the reason nothing
## in the client has to wait on it.
func start() -> void:
	_loader.fetch_manifest()


## Fold in a manifest directly, without fetching. For tests and for a caller
## that already has the document in hand.
func ingest_manifest(document: Variant) -> int:
	return _registry.ingest_manifest(document)


# ─── Private ─────────────────────────────────────────────────────────────────

## A copy of this key's art if it is to hand, starting a fetch if it is not.
##
## The asymmetry is deliberate: asking never blocks, but it does start the work
## that makes the next ask succeed.
func _art_for(asset_key: String) -> Node3D:
	# "generic" is the server's way of saying it has no specific asset for this
	# thing, so there is nothing to look up and nothing to fetch. FAMILY_GENERIC
	# is the client-facing name for that same string.
	if asset_key.is_empty() or asset_key == _Const.FAMILY_GENERIC:
		return null

	var cached := _loader.cached(asset_key)

	if cached != null:
		return cached

	if _loader.can_load(asset_key):
		_loader.request(asset_key)

	return null


func _on_loaded(asset_key: String, model: Node3D) -> void:
	if model == null:
		return

	# The copy handed to this signal is nobody's, so it is freed rather than
	# leaked. Callers ask for their own through resolve_*.
	model.queue_free()
	refreshed.emit(asset_key)
