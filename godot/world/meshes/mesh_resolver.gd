class_name MeshResolver
extends Node
## The mesh ladder. Given what the server said a thing is, give back something
## to draw.
##
##     asset has art?    -- yes -->  the model                    tier 1
##            | no
##     family has art?   -- yes -->  the family's model           tier 2
##            | no
##     family has parts? -- yes -->  the family's shape           tier 3
##            | no
##                                   the generic block            tier 4
##
## Tier 2 is the one that is not per-entity. It exists because an asset key
## names one specific thing and some families are better described whole: every
## corpse in the game is a body, and its asset key is the key of whichever NPC
## left it, so art aimed at the key would have to be drawn once per creature
## before any corpse stopped being a box. [member FamilyShapes.MODELS] is that
## table and the reasoning is written there.
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
##
## ## Every model is fetched and warmed behind the veil
##
## A model's first draw compiles its shaders, and on the web that compile is
## synchronous: measured 09/13/2026 in a Chromium WebGL 2 export, 13.5 s of
## frozen frames to draw today's twenty models once, most of it six compiles of
## 1-5 s each. Left to happen on first SIGHT, those freezes land mid-play -- a
## corpse dropping, a new NPC walking in.
##
## So [method prefetch_all] asks for every model the manifest names the first
## time the loading veil goes up, and [ShaderWarmer] draws each arrival once
## where no camera the player looks through can see it. The veil already waits
## on [method in_flight_count]; warming counts as in flight, so it waits for the
## compiles too and the player meets the freezes as loading, not as lag. The
## rest of the ladder is unchanged: resolves still answer at once, and a model
## still sharpens in if a room draws it before its fetch completes.

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

## What the manifest's absence counts as in [method in_flight_count], while a
## prefetch is waiting on it.
const _AWAITED_MANIFEST := 1

var _registry: ModelRegistry
var _loader: ModelLoader

## Draws arrivals once out of sight so their shaders compile early. Bound by the
## world pane, which owns the World3D the drawing has to happen in; null until
## then, and an arrival is simply freed.
var _warmer: ShaderWarmer

## Set by [method prefetch_all]. The veil can go up before the manifest has
## landed, so the ask is remembered and served when it does.
var _prefetch_wanted := false

## Whether the manifest fetch has finished, successfully or not. A failed fetch
## settles it too: a prefetch waiting on a manifest that is never coming would
## hold the veil up until its ceiling.
var _manifest_settled := false


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
	_loader.manifest_ready.connect(_on_manifest_ready)
	add_child(_loader)


## Something that must always be visible: an entity, an inventory item.
##
## Never returns null. Falls back through the family's model and the family's
## shape to the generic block, so an asset key nobody has modelled and a family
## nobody has drawn both still put something clickable in the room. That
## degradation is the whole reason content can be added to the game without
## waiting on art.
func resolve_entity(asset_key: String, family: String) -> Node3D:
	var model := _art_for(asset_key)

	if model != null:
		return model

	# The family's stand-in, for a family art describes better than primitives
	# do. Asked for the same way as the key's own art, so it is fetched on
	# demand, cached once for every entity sharing the family, and absent
	# rather than fatal until it arrives.
	var family_key := FamilyShapes.model_for(family)

	if not family_key.is_empty():
		var stand_in := _art_for(family_key)

		if stand_in != null:
			return stand_in

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


## Whether art arriving for `arrived_key` changes how this entity is drawn.
##
## For a caller handling [signal refreshed]: it holds entities, the signal names
## a key, and the two only match at tier 1. Comparing them directly was correct
## while the ladder had one model tier and stopped being correct the moment it
## had two — a corpse's asset key is the NPC's, so `corpse_skeleton` landing
## matched nothing and every body on screen stayed a grey box until something
## unrelated redrew the room.
##
## Asked HERE because the ladder lives here. The alternative is every pool
## restating the tiers, which is the arrangement that made tier 2 invisible.
##
## Slightly generous: an entity whose own art is already in hand is reported as
## affected when its family's model arrives, which costs one redraw that changes
## nothing. Being wrong the other way costs a mesh nobody ever sees replaced.
func redraws_for(asset_key: String, family: String, arrived_key: String) -> bool:
	if asset_key == arrived_key:
		return true

	return FamilyShapes.model_for(family) == arrived_key


## How much art work is still outstanding: fetches in the air, models waiting
## to be warmed, and a manifest a prefetch is waiting on.
##
## One count rather than three, because its one reader -- [SessionReadiness] --
## asks one question: is it safe to lift the veil yet. A model fetched but not
## yet drawn is not finished, because its compile is still ahead of the player.
## See [method ModelLoader.in_flight_count] for why it is a count and not a
## signal.
func in_flight_count() -> int:
	var fetching := _loader.in_flight_count()
	var warming := 0

	if _warmer != null:
		warming = _warmer.pending_count()

	var awaiting := 0

	if _prefetch_wanted and not _manifest_settled:
		awaiting = _AWAITED_MANIFEST

	return fetching + warming + awaiting


## Start fetching what the server has art for.
##
## Call once, when the client comes up. Until it completes [method may_have_art]
## answers false for everything and every resolve falls to a family shape —
## a correct intermediate state rather than a broken one, and the reason nothing
## in the client has to wait on it.
func start() -> void:
	_loader.fetch_manifest()


## Fetch, and warm, every model the manifest names. Call when the veil goes up.
##
## Once per client run: the prototypes it fills are kept for the whole run, and
## so are the shaders they hold alive -- see [method ModelLoader._prepare_materials].
## A reconnect has nothing left to do.
##
## Called at the VEIL and never at [method start], deliberately. Parsing a glTF
## and compiling its shaders both freeze the whole window, not just the pane, and
## the login form is not a screen to freeze while somebody types a password.
func prefetch_all() -> void:
	if _prefetch_wanted:
		return

	_prefetch_wanted = true

	if _manifest_settled:
		_request_everything()


## Draw arrivals once, out of sight, before anyone sees them. Called by the
## world pane, which owns the world the warmer has to draw in.
##
## Also hands it one procedural block to KEEP. Every palette material shares one
## shader, and like any shader it is freed the moment nothing uses it -- a room
## drawn entirely from fetched art leaves the next primitive to compile it again.
func bind_warmer(warmer: ShaderWarmer) -> void:
	_warmer = warmer

	var block := MeshBuilder.build(FamilyShapes.parts_for(_Const.FAMILY_GENERIC))

	_warmer.warm(block, true)


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


## Ask for every key the manifest named that is not already in hand.
##
## Skipping what is loaded is not only thrift: [method ModelLoader.request]
## answers a cached key by emitting `loaded` again, which would redraw every
## pane for art they already show.
func _request_everything() -> void:
	var keys := _registry.known_keys()

	for asset_key: String in keys:
		var loaded := _loader.is_loaded(asset_key)

		if not loaded:
			_loader.request(asset_key)


func _on_manifest_ready(count: int) -> void:
	_manifest_settled = true
	manifest_ready.emit(count)

	if _prefetch_wanted:
		_request_everything()


func _on_loaded(asset_key: String, model: Node3D) -> void:
	if model == null:
		return

	# The copy handed to this signal is nobody's. With a warmer bound it is
	# drawn once out of sight first -- compiling its shaders now rather than on
	# the frame a player first sees the thing -- and the warmer frees it after.
	# Callers ask for their own copies through resolve_*.
	if _warmer == null:
		model.queue_free()
	else:
		_warmer.warm(model)

	refreshed.emit(asset_key)
