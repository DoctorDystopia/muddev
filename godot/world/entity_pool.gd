class_name EntityPool
extends Node3D
## The things standing in the room you are standing in.
##
## NOT only your own room. `STATEFEED_ENTITY_RADIUS` is **10**, which is a
## 21x21 neighbourhood — 441 rooms — so the feed reports a great deal the text
## channel does not.
##
## This file used to claim the radius was 0 and place every entity in a ring
## around the observer. Both halves were wrong together, and the second is what
## `serialize_entity` warned about in as many words: *"once the feed reports
## entities the observer is not standing with, a client has no way to place them
## without being told where they are, and would stack the whole neighbourhood
## onto the player's tile."* That is precisely what it did, and it was invisible
## only while every entity was a small identical sphere.
##
## So `coords` is load-bearing and is read. Each entity is placed on ITS OWN
## tile, and the ring exists to separate entities that genuinely share one.
## An entity whose tile cannot be placed yet — its map has not arrived — is
## drawn nowhere rather than somewhere wrong.
##
## A change builds only the nodes it changed. It rebuilt every node until
## 09/22/2026, on the belief that a room holds a handful of entities. At radius
## 10 the pool holds the whole map, and each step of another player is a remove
## and an add. Thus, each step rebuilt every mesh and label in view two times,
## about 43 ms at 250 entities on desktop. Two players who walk together made
## the scene lag. See [method _sync].
##
## ## What an entity looks like is not decided here
##
## Every mesh comes from [MeshResolver], which walks the ladder: the model for
## the asset key, else the family's shape, else a generic block. This file knows
## none of that -- it asks with the two fields the server sent (`asset` and
## `family`, which `serialize_entity` documents as "the two tiers of one
## lookup") and places whatever comes back.
##
## Everything the resolver returns fits a unit box, so one scale is applied here
## and the same number is right for a modelled sword and a procedural figure.
## That is the whole reason the ladder normalises: the browser spread the
## equivalent across ENTITY_SCALE, TILE_PROP_SCALE and ITEM_SCALE in three
## files, and they drifted.
##
## ## The observer occupies a tile this pool cannot see
##
## `emit_room_contents` excludes the observer from their OWN room_players list —
## `CharAvatarPayload` says so in as many words — so the one tile that is never
## empty is the one tile the feed describes as holding one fewer thing than it
## does. Left at that, a ring of one sized itself to radius 0 and a single item
## dropped at your feet was drawn exactly inside you, which is what "everything
## sits in the middle of the tile" looked like from the outside.
##
## So [method stand] is told which tile that is, the observer takes slot 0 of
## its ring, and [signal observer_slot_changed] hands the pane back the offset
## to draw them at. The pane still owns the avatar — it hangs off the marker the
## camera follows — and this pool still draws none of it. All that crosses is
## where the ring left room.

const ENTITY_RADIUS := 0.26     # smallest ring radius within one tile

## How far a ring may grow on a crowded tile.
##
## A tile is one unit across, so half of it is 0.5 and this keeps even a heaving
## room inside its own square. Past this they overlap again — which is the
## honest outcome, because the alternative is one room's occupants standing on
## the next room's floor.
const MAX_RING_RADIUS := 0.44

## How much of a tile one entity fills.
##
## A SCALE, not a radius: everything the resolver hands back is a unit across,
## so this is the single number that sizes a modelled sword and a procedural
## figure alike. Matches the browser's ENTITY_SCALE, and is close to the 0.26
## diameter of the spheres it replaced -- big enough that a silhouette reads,
## small enough that four in a ring do not touch.
const ENTITY_SCALE := 0.5

## How far a ring may be turned from slot 0 pointing at +X, as a share of one
## slot. A ROTATION of the whole ring, not a per-occupant nudge -- see
## [method _slot_position] for why that distinction is the difference between a
## ring that spaces itself and one that only nearly does.
const RING_TURN_SHARE := 0.35
const HIT_FLASH_SECONDS := 0.32

const COLOR_HIT_FLASH := Color.WHITE

## What a hovered entity glows. Dim and neutral: it says "this is what a click
## would take", and anything stronger competes with the hit flash for attention
## during a fight.
const COLOR_HOVER_GLOW := Color(0.6, 0.7, 0.85)
const HOVER_ENERGY := 0.6

const _Const := preload("res://autoload/blackout_constants.gd")

## How far above an entity's own top its label floats, in world units.
##
## Measured from the mesh's TOP rather than from the tile, so a sign, a
## shopkeep and a dropped sword all hold their text the same distance clear of
## themselves — which one constant from the ground could never do, for the same
## reason [method _rest_offset] replaced a fixed lift.
const LABEL_GAP := 0.14

## How big the text is drawn, and how wide it may run before wrapping.
##
## `LABEL_PIXEL_SIZE` converts font pixels to world units, so a line is
## `LABEL_FONT_SIZE * LABEL_PIXEL_SIZE` tall — 0.16 of a tile here — and
## `LABEL_WRAP_PIXELS` is one tile across at the same conversion. A label wider
## than its own tile reads as belonging to the tile next door, which on a grid
## of rooms is not a cosmetic complaint.
const LABEL_FONT_SIZE := 64
const LABEL_PIXEL_SIZE := 0.0025
const LABEL_WRAP_PIXELS := 800.0

## A dark rim around every glyph, in font pixels. Not decoration: the world
## pane draws sand, steel and night sky behind these, and text with one colour
## and no outline is legible over roughly one of the three.
const LABEL_OUTLINE_SIZE := 14
const COLOR_LABEL_OUTLINE := Color(0.04, 0.05, 0.07, 0.85)

## What each kind of label is drawn in. THE CLIENT'S TABLE, deliberately: the
## server owns which kinds exist and this file owns what they look like, which
## is the boundary CLAUDE.md draws and the reason the kinds are generated into
## [code]blackout_constants.gd[/code] while these colours are not.
##
## A kind absent here is NOT an error — it falls to
## [constant COLOR_LABEL_FALLBACK] and still reads — so the server may name a
## new kind without waiting on a client edit.
##
## The reverse needs no guard, unlike [constant MapPalette.ROOM_KIND_COLORS]
## next door, and the difference is the keys: these are GENERATED constants, so
## a kind renamed or dropped server-side is a GDScript parse error on the next
## export rather than a row quietly colouring nothing. That is the same
## argument `FamilyShapes.MODELS` makes for having only its values checked.
const LABEL_KIND_COLORS := {
	# Warm and paper-like. In the fiction, meant to be believed.
	_Const.LABEL_KIND_SIGN: Color("e8dcc0"),

	# Deliberately synthetic, and deliberately a colour no signage uses. A
	# marker is a note to whoever is BUILDING the game; the first player to
	# mistake one for worldbuilding is the bug this colour exists to prevent.
	_Const.LABEL_KIND_MARKER: Color("ff5fd2"),

	# Aerosol green, and the same argument as the marker one line up: a player
	# reading words in the world has to be able to tell the world speaking from
	# another player speaking, because a scrawl reading "BANK: EAST" is a lie a
	# signpost could not tell.
	_Const.LABEL_KIND_GRAFFITI: Color("7ce06a"),
}

## Drawn for a kind this table has never heard of. See [constant LABEL_KIND_COLORS].
const COLOR_LABEL_FALLBACK := Color("b9c6d2")

## Fired when the observer's own slot on their tile moves, as an offset from
## the tile's centre.
##
## The pool does not draw the observer and must not start: the avatar hangs off
## the marker the camera follows and the aura ring is anchored to it, so moving
## the observer here would drag both off the tile. What crosses is an offset the
## pane applies WITHIN the marker, leaving the anchor where it was.
##
## Emitted on every sync. A sync that finds the observer alone again sends
## [constant Vector3.ZERO].
signal observer_slot_changed(offset: Vector3)

## Fired when the set of TRUE TILES needing a mark changes, as tile positions.
##
## While [StepAnimator] slides a figure between two squares, the figure is not
## standing on the one the server has it on -- and that square is the only one
## any command resolves against. So the pane draws a mark on it for exactly as
## long as the figure is away, and this is how it is told which. See
## [TrueTileMark].
##
## The pool does not draw the marks, for the reason it does not draw the
## observer: a mark is ground and the ground is the pane's. It emits POSITIONS
## the pane gave it through `_locate` in the first place, so nothing here
## re-derives where a tile is.
##
## ONE ENTRY PER TILE, not per entity. Two raiders walking onto the same square
## are two identical coplanar squares, which is z-fighting rather than
## emphasis.
##
## Emitted only when the set CHANGES. The alternative is a MultiMesh rebuilt on
## every frame of every walk, for a set that is empty nearly all the time.
signal true_tiles_changed(origins: Array)

## Which entity the cursor is over. Zero for none, safe because Evennia object
## ids start at 1.
var _hovered := 0

## The tile the observer is standing on, as a tile key, or empty before the
## first room has arrived.
##
## Read only to decide whether a tile's ring has one more occupant than the feed
## named. See the class docstring for why the feed cannot say so itself.
var _observer_tile := ""

## Turns an entity's `coords` into a world position, or null when its map is not
## on screen yet.
##
## A callable rather than a copy of the placement maths: the world pane already
## owns where a tile is, and a second implementation here would be free to
## disagree with the tiles actually drawn — which is a mesh floating beside the
## grid rather than on it.
var _locate: Callable

var _entities: Array[Dictionary] = []
var _nodes: Dictionary = {}     # int id -> Node3D

## One [StepAnimator] for each entity id. It lives HERE and not on the node,
## because the node does not always survive.
##
## [method _sync] builds a node again when its look changes or its art lands.
## A walk must outlive both. Thus, the record of where the pool DRAWS a figure
## sits beside the nodes, with the id as its key. The sync prunes it, so an
## entity that left the room leaves nothing behind.
var _animators: Dictionary = {}   # int id -> StepAnimator

## int id -> the tile key that entity's true tile is, and tile key -> where
## that tile is. Together they turn "who is moving" into "which squares to
## mark" with no second lookup through `_locate`.
var _tile_of: Dictionary = {}
var _tile_origins: Dictionary = {}

## int id -> how far that node is lifted so its bottom rests on the tile.
##
## [method _node_for_entity] measures it one time, when it builds the node. The
## lift belongs to the MODEL, not to the tile where the model stands. A
## measurement walks the whole subtree of the node, and [method _sync] places
## every entity on every change.
var _lift: Dictionary = {}

## int id -> the fields the node of that entity was built from. See
## [method _look_of]. A row that arrives with the same look keeps its node.
var _looks: Dictionary = {}

## The last set of marks sent on [signal true_tiles_changed]. Kept so a frame
## in which nobody started or stopped moving emits nothing.
var _marked: Array = []

## Whether figures slide between tiles at all. The player's setting, pushed
## down by [WorldView] so the observer and everyone else answer to one switch.
var _animated := true

## One tile, in world units. GIVEN by the pane, because the pane is what lays
## tiles out -- a copy here would be free to disagree with the grid actually
## drawn, which is the same reason `_locate` is a callable.
var _step := 1.0

## Where meshes come from. Injected rather than built here: one resolver serves
## the whole client, so its model cache is shared and an asset fetched for the
## room is already to hand when the inventory asks for it.
var _resolver: MeshResolver


## Give the pool its resolver and its placement. Call before the first entity
## arrives.
func bind(resolver: MeshResolver, locate: Callable, step: float) -> void:
	_resolver = resolver
	_locate = locate
	_step = step

	# Art that lands after an entity was drawn as its family shape redraws the
	# ring. That is the "sharpens in" half of the ladder's contract, and without
	# it a model fetched on arrival would not appear until something else
	# happened to change the room.
	_resolver.refreshed.connect(_on_art_arrived)


## Place everything again. Call when the islands move under them.
##
## Takes no anchor any more: every entity carries its own `coords` and is placed
## from those, so there is no single tile for the pool to be moved to. What DOES
## change is which coords are placeable — a relayout that finally draws an
## island makes every entity standing on it drawable.
##
## The observer's every step calls this. Only WHERE things stand changes, so
## [method _sync] builds nothing unless an island arrived or went away.
func replace_positions() -> void:
	_sync()


## Slide figures between tiles, or draw each one on its tile.
##
## Pushed down by [WorldView] from the player's own setting, so the observer's
## avatar and every NPC answer to one switch. Turning it OFF lands every figure
## on its true tile at once and takes every mark off the screen -- a player who
## switched the animation off is not asking to watch the last walk finish.
func set_animated(value: bool) -> void:
	_animated = value

	for entity_id: int in _animators:
		var animator: StepAnimator = _animators[entity_id]

		animator.set_animated(value)

		if _nodes.has(entity_id):
			_nodes[entity_id].position = animator.drawn()

	_publish_marks()


## Record which tile the observer is standing on. Takes effect on the next
## placement, which is why the world pane calls it immediately before
## [method replace_positions] rather than instead of it.
##
## A pure setter on purpose. Every other route into this file syncs, because
## something that it draws changed. This one changes something that it does NOT
## draw. A sync here would place every entity two times on each step of the
## observer.
##
## `coords` arrives in the same shape an entity carries them, so both sides of
## the comparison are spelled by [method _tile_key] and cannot drift.
func stand(coords: Array) -> void:
	_observer_tile = _tile_key(coords)


## ONE ENTRY PER ID, ALWAYS. The invariant every route below holds.
##
## Nothing in the wire protocol promises that an entity is announced once. It
## does not, and cannot: `room_players` is a whole list sent on arrival and on
## resync, `room_add_player` is a delta, and `room_players_delta` is computed
## against a snapshot of what the SERVER believes this client holds. An entity
## that arrived by one route is legitimately named again by another -- an NPC
## respawning on your tile is announced by `room_add_player`, and then named
## again in the `added` half of the next delta, because the server's snapshot
## of your view was taken before it existed.
##
## Appending both times drew it TWICE, in two slots of the tile's ring, and
## that is a bug with a long tail: [method remove] took only the first match,
## so deleting the entity server-side left the second copy standing there
## permanently, and still clickable. Two mutant raider corpses on a tile where
## one had been butchered, and a click on the survivor sending a command about
## an object that no longer exists.
##
## The fix is an INVARIANT rather than a rule about who may send what: the pool
## holds at most one entry per id, whatever arrives. That is also what makes a
## resync idempotent, which is the property resync exists for.
static func _index_of(entities: Array, entity_id: int) -> int:
	for index: int in entities.size():
		if _id_of(entities[index]) == entity_id:
			return index

	return -1


## Add an entity, or replace the entry already holding its id.
##
## Replace and not skip: the later announcement is the fresher one. An entity
## re-sent after it moved, took damage or gained an action carries the new
## values, and keeping the first copy would pin the client to whatever it
## happened to hear first.
func _upsert(entities: Array, entity: Dictionary) -> void:
	var at := _index_of(entities, _id_of(entity))

	if at < 0:
		entities.append(entity)
		return

	entities[at] = entity


## Replace everything visible. `room_players` is the full list, sent on arrival
## and on resync; the add/remove channels carry the deltas in between.
func replace_all(entities: Array) -> void:
	_entities.clear()

	for entity: Dictionary in entities:
		_upsert(_entities, entity)

	_sync()


func add(entity: Dictionary) -> void:
	if entity.is_empty():
		return

	_upsert(_entities, entity)
	_sync()


## Drop every entry holding this id, not merely the first.
##
## Belt and braces beside the upsert above: the two together mean a duplicate
## cannot be created and could not survive one removal if it somehow were. This
## half is what was actually observed failing -- a doubled corpse lost one copy
## when it was butchered and kept the other.
func remove(entity_id: int) -> void:
	var kept: Array[Dictionary] = []

	for entity: Dictionary in _entities:
		if _id_of(entity) != entity_id:
			kept.append(entity)

	if kept.size() == _entities.size():
		return

	_entities = kept
	_sync()


## Apply one batched change to the visible list: `removed` ids drop out,
## `added` entities come in, and the pool syncs ONE time at the end.
##
## `room_players_delta` is a batch for this reason. Each [method add] and each
## [method remove] syncs, and a sync places every entity in view. The server
## sends the change that the observer's own movement caused as one batch.
## Single-entity add and remove still carry everything else.
##
## Removals are applied before additions. The two sets are disjoint by
## construction on the server — an id cannot both arrive and depart in one diff
## — so the order cannot change the result, and doing removals first keeps the
## intermediate array smaller.
##
## A delta with nothing in it is not sent, but is harmless if one ever is: the
## early return skips the rebuild rather than redrawing the same scene.
func apply_delta(added: Array, removed: Array) -> void:
	if added.is_empty() and removed.is_empty():
		return

	if not removed.is_empty():
		var dropped := {}

		# int() on every id, and untyped loop variables throughout: these
		# arrived as JSON, and Godot parses every JSON number as a float. A
		# `for id: int in removed` would fail its type check on the first one,
		# and a float key would never match the int `_id_of` returns. The
		# existing CH_PLAYER_REMOVE path int()s for the same reason.
		for entity_id in removed:
			dropped[int(entity_id)] = true

		var kept: Array[Dictionary] = []

		for entity: Dictionary in _entities:
			if not dropped.has(_id_of(entity)):
				kept.append(entity)

		_entities = kept

	for entity in added:
		if entity is Dictionary and not entity.is_empty():
			_upsert(_entities, entity)

	_sync()


## The entity nearest a point on screen, or 0 for nothing within reach.
##
## Screen-space rather than a physics raycast: there are no collision bodies in
## this scene and adding them would mean a second representation of every
## entity to keep in step. Picking by cursor distance also does the more
## obliging thing when two entities overlap -- it takes whichever LOOKS closest
## to the cursor.
##
## Zero is a safe "nothing" because Evennia object ids start at 1.
func pick(camera: Camera3D, screen_point: Vector2, reach: float) -> int:
	var nearest := reach
	var found := 0

	for entity_id: int in _nodes:
		var node: Node3D = _nodes[entity_id]

		if camera.is_position_behind(node.global_position):
			continue

		var distance := camera.unproject_position(node.global_position).distance_to(screen_point)

		if distance < nearest:
			nearest = distance
			found = entity_id

	return found


## The node drawn for one entity, or null when it is not on screen.
##
## Null is a real answer and not only an error: an entity whose map has not
## arrived is deliberately drawn nowhere, so "known but not drawn" is a state
## callers have to be able to see.
func node_for(entity_id: int) -> Node3D:
	return _nodes.get(entity_id)


## The payload an id was built from, or an empty dictionary.
func entity(entity_id: int) -> Dictionary:
	for candidate: Dictionary in _entities:
		if _id_of(candidate) == entity_id:
			return candidate

	return {}


## Flash one entity white and fade it back. Called on a landed swing.
##
## Every material under the node, not one: an entity is now a small hierarchy
## rather than a single sphere, and flashing only the root would leave a
## three-part figure with one white head. Each material is safe to write to
## because every mesh handed out owns its own -- see
## [method ModelLoader._take_own_materials] for why that is not free.
func flash(entity_id: int) -> void:
	var node: Node3D = _nodes.get(entity_id)

	if node == null:
		return

	# Must finish inside the 0.6s server tick, so the world is never mid-tween
	# when the next state arrives.
	var tween := create_tween()
	var tweened := false

	for material: StandardMaterial3D in _materials_of(node):
		var base := material.albedo_color

		material.albedo_color = COLOR_HIT_FLASH

		# parallel() so several materials fade together rather than in sequence,
		# which would run the flash well past the tick budget on a model with
		# four surfaces.
		if tweened:
			tween.parallel()

		tween.tween_property(material, "albedo_color", base, HIT_FLASH_SECONDS)
		tweened = true

	if not tweened:
		tween.kill()


## Light one entity and put the last one back. Zero means none.
##
## Emission rather than albedo, deliberately: the hit flash already owns
## albedo_color, and a hover that wrote the same property would either be
## overwritten mid-swing or would restore the WRONG colour when the mouse moved
## away during a flash. Two effects, two properties, no ordering to get right.
##
## The glow is written as colour and energy ONLY, never by switching emission on
## and off. Emission is part of which shader draws a material, so toggling it
## compiled a shader on every hover -- ~1.9 s for a fetched model's first on the
## web. [MeshGlow] owns that rule and why.
func hover(entity_id: int) -> void:
	if entity_id == _hovered:
		return

	_light(_hovered, false)
	_hovered = entity_id
	_light(_hovered, true)


func _light(entity_id: int, lit: bool) -> void:
	var node: Node3D = _nodes.get(entity_id)

	if node == null:
		return

	for material: StandardMaterial3D in _materials_of(node):
		if lit:
			MeshGlow.light(material, COLOR_HOVER_GLOW, HOVER_ENERGY)
		else:
			MeshGlow.rest(material)


## Every writable material under one entity.
##
## Covers both tiers: a procedural part carries its material on
## `material_override`, while a fetched model carries one per surface. Asking
## for both here is what lets [method flash] stay one routine.
static func _materials_of(root: Node3D) -> Array:
	var found: Array = []
	var stack: Array[Node] = [root]

	while not stack.is_empty():
		var node: Node = stack.pop_back()
		var instance := node as MeshInstance3D

		if instance != null:
			var override := instance.material_override as StandardMaterial3D

			if override != null:
				found.append(override)

			for surface: int in instance.get_surface_override_material_count():
				var material := instance.get_surface_override_material(
					surface) as StandardMaterial3D

				if material != null:
					found.append(material)

		for child: Node in node.get_children():
			stack.append(child)

	return found


# ─── Private helpers ─────────────────────────────────────────────────────────

## Slide every figure one frame closer to the tile the server put it on.
##
## The only per-frame work the pool does, and it does none at all while the
## animation is off: every figure is then already on its tile, and nothing
## moves it but a sync.
func _process(delta: float) -> void:
	if not _animated:
		return

	for entity_id: int in _nodes:
		var animator: StepAnimator = _animators.get(entity_id)

		if animator == null:
			continue

		_nodes[entity_id].position = animator.advance(delta)

	_publish_marks()


## Tell the pane which true tiles to mark, when that set has changed.
##
## Grouped by TILE on the way out, so two figures crossing onto one square ask
## for one mark. The comparison against the last list is what keeps this from
## rebuilding a MultiMesh sixty times a second for a set that is empty whenever
## nobody is walking.
func _publish_marks() -> void:
	var origins: Array = []
	var seen: Dictionary = {}

	for entity_id: int in _animators:
		var animator: StepAnimator = _animators[entity_id]

		if not animator.is_travelling():
			continue

		var key: String = _tile_of.get(entity_id, "")

		if seen.has(key) or not _tile_origins.has(key):
			continue

		seen[key] = true
		origins.append(_tile_origins[key])

	if origins == _marked:
		return

	_marked = origins
	true_tiles_changed.emit(origins)


## Every drawn entity, grouped by the tile it stands on.
##
## The ring separates things standing in the same place. Entities in different
## rooms are in different places and must not share one. Grouping also makes
## each ring's size depend on how many are actually on that tile, rather than
## on how many the feed happened to send.
##
## Each group is sorted by id rather than left in arrival order. The slot INDEX
## is what keeps a thing in the same place between frames, and arrival order
## does not: removing the first of three entities used to shuffle the other two
## around the ring for no reason the player could see. Ids are stable and
## total, so the same occupants always produce the same ring.
##
## Read by [method _sync] and by [method _prune]. Thus, the set of entities
## that get a node and the set that get a slot cannot differ.
func _group_by_tile() -> Dictionary:
	var by_tile: Dictionary = {}

	for entity: Dictionary in _entities:
		var coords: Array = entity.get("coords", [])
		var where: Variant = _locate.call(coords)

		# Drawn nowhere rather than somewhere wrong. Its map has not arrived, so
		# there is no honest position to give it; the relayout that places the
		# island calls back here.
		if where == null:
			continue

		var key := _tile_key(coords)

		if not by_tile.has(key):
			by_tile[key] = {"origin": where, "entities": []}

		by_tile[key]["entities"].append(entity)

	for key: String in by_tile:
		by_tile[key]["entities"].sort_custom(_by_id)

	return by_tile


## How one tile's ring is laid out: who takes which slot, and how many there
## are in total.
##
## The observer is drawn by the world pane, not here, but they OCCUPY their
## tile -- so they take slot 0 and everything standing with them rings around
## from slot 1. Slot 0 and not their id's place in the sort, because this file
## is never told what their id is and does not need to be: one reserved slot is
## as stable as a sorted one.
func _ring_of(key: String, count: int) -> Dictionary:
	var shared := key == _observer_tile

	return {
		"shared": shared,
		"first": 1 if shared else 0,
		"occupants": count + (1 if shared else 0),
	}


## Make the drawn scene match `_entities`, and build only what changed.
##
## Every change to the pool comes here: an entity added or removed, a delta, a
## whole list, a step of the observer. The routine does three things:
##
## 1. It frees the node of each entity that left, or whose look changed.
## 2. It builds a node for each entity that has none.
## 3. It aims every entity at its ring slot.
##
## Step 3 touches every entity, because one arrival can resize a ring. It is
## one lookup and one aim per entity. Steps 1 and 2 touch only the changed
## entities, and they hold the whole cost: a mesh, its own materials, a label,
## and two walks of the subtree for its bounds.
##
## Nothing about a step of another player changes a look. Thus, that step
## builds one node at most, where it built every node in view two times.
func _sync() -> void:
	var by_tile := _group_by_tile()

	_prune(by_tile)

	var observer_offset := Vector3.ZERO

	# Made new and swapped in at the end. This prunes the animator of an
	# entity that left the room.
	var animators: Dictionary = {}

	_tile_of.clear()
	_tile_origins.clear()

	for key: String in by_tile:
		var group: Dictionary = by_tile[key]
		var here: Array = group["entities"]
		var ring := _ring_of(key, here.size())

		_tile_origins[key] = group["origin"]

		for index: int in here.size():
			var entity: Dictionary = here[index]
			var entity_id := _id_of(entity)
			var node := _node_for_entity(entity)
			var slot := _slot_position(
				group["origin"], key, ring["first"] + index, ring["occupants"])

			slot.y += _lift.get(entity_id, 0.0)
			animators[entity_id] = _aim(entity_id, slot)
			_tile_of[entity_id] = key

			# The DRAWN position, not the slot. A sync in the middle of a walk
			# must not move everybody to their destination in one frame.
			node.position = animators[entity_id].drawn()

		if ring["shared"]:
			# An OFFSET, so the origin is zero. The pane adds it inside the
			# marker, and the marker already stands on this tile.
			observer_offset = _slot_position(
				Vector3.ZERO, key, 0, ring["occupants"])

	_animators = animators

	observer_slot_changed.emit(observer_offset)
	_publish_marks()


## Free every node and build them all again.
##
## [method _sync] does this for only the changed nodes. This form is for a
## test that forces a state the public API does not permit.
func _rebuild() -> void:
	for entity_id: int in _nodes.keys():
		_drop_node(entity_id)

	_sync()


## Free each node whose entity left, went off the map, or changed its look.
##
## `by_tile` holds only the entities that have a place. An entity whose island
## went away thus loses its node here, and it gets a node again when the
## island comes back.
func _prune(by_tile: Dictionary) -> void:
	var wanted: Dictionary = {}

	for key: String in by_tile:
		for entity: Dictionary in by_tile[key]["entities"]:
			wanted[_id_of(entity)] = entity

	for entity_id: int in _nodes.keys():
		var entity: Dictionary = wanted.get(entity_id, {})

		if entity.is_empty() or _looks.get(entity_id) != _look_of(entity):
			_drop_node(entity_id)


## Free one node and forget what was measured on it.
##
## A hover on the freed node is forgotten too. Left set, the next hover() on
## the same id returns early, and the new node never lights up.
func _drop_node(entity_id: int) -> void:
	var node: Node3D = _nodes.get(entity_id)

	if node != null:
		remove_child(node)
		node.queue_free()

	_nodes.erase(entity_id)
	_looks.erase(entity_id)
	_lift.erase(entity_id)

	if _hovered == entity_id:
		_hovered = 0


## The node of this entity. Built, measured and labelled when it has none.
##
## Two entries with one id share one node. [method _upsert] keeps that from
## happening, and this makes sure that it cannot draw a second copy.
func _node_for_entity(entity: Dictionary) -> Node3D:
	var entity_id := _id_of(entity)
	var existing: Node3D = _nodes.get(entity_id)

	if existing != null:
		return existing

	var node := _build(entity)

	# The lift is measured BEFORE the label is attached. Both read the bounds
	# of the node. A label attached first counts as part of the mesh, and it
	# lifts the entity off the ground by the height of its own text.
	_lift[entity_id] = _rest_offset(node)
	_attach_label(node, entity)
	add_child(node)

	_nodes[entity_id] = node
	_looks[entity_id] = _look_of(entity)

	return node


## Give the animator of this entity its new slot, and make one if it has none.
##
## A first sighting places. An entity announced in this frame must appear on
## its tile, not slide in from the world origin. After that, each new slot is
## a walk. A slot that moved because the RING grew slides too: something that
## steps aside for a newcomer moves less than one step.
func _aim(entity_id: int, slot: Vector3) -> StepAnimator:
	var animator: StepAnimator = _animators.get(entity_id)

	if animator == null:
		animator = StepAnimator.new(_step, _Const.TICK_SECONDS)
		animator.set_animated(_animated)
		animator.place(slot)

		return animator

	animator.aim(slot)

	return animator


## The fields that decide what the node of an entity looks like.
##
## [method _build] reads `asset` and `family`. [method _attach_label] reads
## `label` and `label_kind`. A new field that either one reads goes here too,
## or a changed row keeps its old node.
static func _look_of(entity: Dictionary) -> Array:
	return [
		str(entity.get("asset", "")),
		str(entity.get("family", "")),
		str(entity.get("label", "")),
		str(entity.get("label_kind", "")),
	]


## One entity's mesh, from the ladder.
##
## `asset` and `family` are passed through exactly as the server sent them; this
## file decides nothing about what a thing looks like. An entity ALWAYS gets a
## mesh -- resolve_entity never returns null -- because something unmodelled
## still has to be visible and clickable.
func _build(entity: Dictionary) -> Node3D:
	var node := _resolver.resolve_entity(
		str(entity.get("asset", "")), str(entity.get("family", "")))

	node.scale = Vector3.ONE * ENTITY_SCALE

	return node


## Hang the server's text over one entity, when it sent any.
##
## The `label` field is not a sign's field. Any entity may carry one — a
## signpost today, a nameplate or a shop's name tomorrow — so this reads it the
## same blind way [method _build] reads `asset` and `family`, and gains every
## future case with no edit. An entity without one costs a dictionary lookup
## and returns, which is nearly all of them.
##
## ## Why the scale is undone
##
## The mesh is scaled to [constant ENTITY_SCALE] and a child inherits that, so
## a label left alone would be drawn half size on a small entity and would
## shrink again if that constant were ever tuned. Text size is a READABILITY
## decision, not a function of how big the thing under it is, so the scale is
## divided back out and [constant LABEL_FONT_SIZE] is the whole of the answer.
##
## Placed from the mesh's own top rather than a fixed height, for the reason
## [method _rest_offset] exists: one number cannot clear a sword, a figure and
## a rigged character at once.
func _attach_label(node: Node3D, entity: Dictionary) -> void:
	var text := str(entity.get("label", ""))

	if text.is_empty():
		return

	var label := Label3D.new()
	label.text = text
	label.font_size = LABEL_FONT_SIZE
	label.pixel_size = LABEL_PIXEL_SIZE
	label.width = LABEL_WRAP_PIXELS
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	label.outline_size = LABEL_OUTLINE_SIZE
	label.outline_modulate = COLOR_LABEL_OUTLINE
	label.modulate = _label_colour(str(entity.get("label_kind", "")))

	# Y-only billboard: the text turns to face the orbit camera as it swings
	# around, but never tips. A fully billboarded label lies flat on its back
	# when the camera looks down, which is the angle this game is played at.
	label.billboard = BaseMaterial3D.BILLBOARD_FIXED_Y

	# Cut rather than blended. Transparent text sorts against every other
	# transparent surface in the scene and picks a fight it loses somewhere on
	# a crowded tile; discarding the transparent pixels takes it out of that
	# queue entirely.
	label.alpha_cut = Label3D.ALPHA_CUT_DISCARD

	var bounds := ModelLoader.bounds_of(node)
	var top := bounds.position.y + bounds.size.y

	label.scale = Vector3.ONE / ENTITY_SCALE
	label.position.y = top + LABEL_GAP / ENTITY_SCALE
	node.add_child(label)


## What one kind of label is drawn in, or the fallback for a kind this client
## has never heard of. See [constant LABEL_KIND_COLORS] for why the unknown
## case is not an error.
func _label_colour(kind: String) -> Color:
	if LABEL_KIND_COLORS.has(kind):
		return LABEL_KIND_COLORS[kind]

	return COLOR_LABEL_FALLBACK


## Even slots around the ring, the whole ring rotated by a hash of the TILE.
##
## The rotation exists so two rooms holding the same number of things do not
## produce identical rings. Seeded on the tile and applied once, so every
## occupant turns together: it used to be hashed per entity, which let two
## neighbours drift up to a third of a slot TOWARDS each other and undid the
## spacing _ring_radius had just worked out — four things sized to stand 0.500
## apart arrived 0.496 apart, which is a ring that overlaps for no reason but
## its own decoration. A rigid turn buys the same variety and costs nothing.
##
## The slot ORDER, which is what keeps a thing in the same place between frames,
## still comes from the index alone.
func _slot_position(origin: Vector3, tile: String, index: int,
		total: int) -> Vector3:
	var spread := maxi(total, 1)
	var turn := float(MapPalette.stable_hash(tile) % 100) / 100.0
	var angle := (float(index) + turn * RING_TURN_SHARE) / float(spread) * TAU
	var radius := _ring_radius(spread)

	# No lift here: _rest_offset puts each node's bottom on the tile, per node,
	# which one constant could never do for a normalised model, a procedural
	# figure and a rigged character at once.
	return origin + Vector3(
		cos(angle) * radius,
		0.0,
		sin(angle) * radius
	)


## How far to lift one node so its BOTTOM sits on the tile.
##
## Replaces a fixed ENTITY_LIFT, which could only ever be right for one shape.
## Every tier centres what it produces on the origin, but by different amounts —
## a normalised model's bottom is at -0.5 while the procedural figure's is at
## -0.47 — and a rigged model is different again. Measuring each is the only
## answer that is right for all three, and it is the same thing the world pane
## does to rest a prop on a tile.
##
## Measured UNSCALED and multiplied, because [method ModelLoader.bounds_of]
## excludes the root's own transform: that is what makes the number independent
## of the scale just applied.
func _rest_offset(node: Node3D) -> float:
	var bounds := ModelLoader.bounds_of(node)

	return -bounds.position.y * ENTITY_SCALE


## How far out to place a ring of `total` occupants.
##
## Grows with the count instead of being fixed, and the number it grows by is
## the CHORD between neighbours rather than the circumference. Those are not the
## same sum: `total * ENTITY_SCALE / TAU` measures the arc, which always
## overstates how far apart two neighbours actually are, and it overstates it
## worst on the small rings — it called a ring of three roomy while its
## occupants sat 0.45 apart and 0.5 wide. Solving the chord instead
## (`2r·sin(π/total) >= ENTITY_SCALE`) is the same intent done honestly, and it
## is what lets five things share a tile without touching where the arc maths
## started piling them up at three.
##
## Still capped, so a crowded tile spreads within its own square rather than
## sprawling across its neighbours. Five is what fits inside that cap; a sixth
## occupant starts the overlapping again — which is the honest outcome, because
## the alternative is one room's occupants standing on the next room's floor.
func _ring_radius(total: int) -> float:
	if total <= 1:
		return 0.0

	# maxf keeps a small ring at the authored spacing rather than letting two
	# occupants sit closer than the constant intends.
	var needed := ENTITY_SCALE / (2.0 * sin(PI / float(total)))

	return minf(maxf(ENTITY_RADIUS, needed), MAX_RING_RADIUS)


## Redraw when art lands for something currently on screen.
##
## Frees the node of each entity that the art redraws, and then syncs. The sync
## builds those nodes again, and it places them the same way as every other
## node.
##
## Whether a row cares about the key is [method MeshResolver.redraws_for]'s to
## answer, not this file's: an entity is drawn by its asset key OR by its
## family's model, and only the resolver knows that ladder.
func _on_art_arrived(asset_key: String) -> void:
	var redrawn := false

	for entity: Dictionary in _entities:
		var asset := str(entity.get("asset", ""))
		var family := str(entity.get("family", ""))

		if _resolver.redraws_for(asset, family, asset_key):
			_drop_node(_id_of(entity))
			redrawn = true

	if redrawn:
		_sync()


## The key one tile is grouped under.
##
## Rendered from ints rather than being `str(coords)`, because every number in a
## parsed payload is a float: an entity's tile stringifies as
## `[7.0, 1.0, "oasis"]` while the observer's, built from a Vector2i, would come
## out as `[7, 1, "oasis"]`, and the two would never group together.
##
## Coords too short to name a tile — an off-grid room sends `[]` — key as the
## empty string. No real tile can be that, so it never matches `_observer_tile`
## in the window before the first room has arrived.
static func _tile_key(coords: Array) -> String:
	if coords.size() < 3:
		return ""

	return "%d:%d:%s" % [int(coords[0]), int(coords[1]), str(coords[2])]


## Ring order. A named function because `sort_custom` takes a Callable and a
## lambda here would be rebuilt for every tile on every rebuild.
static func _by_id(first: Dictionary, second: Dictionary) -> bool:
	return _id_of(first) < _id_of(second)


## Entity ids arrive as floats, like every other number Godot parses out of
## JSON. Converted here, at the point of use, because this is where they become
## dictionary keys -- and a key of 20743.0 never matches one written as 20743.
static func _id_of(entity: Dictionary) -> int:
	return int(entity.get("id", 0))
