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
## Entities are rebuilt wholesale on every change rather than pooled. There are
## rarely more than a handful in a room, the ring position of each depends on
## how many there are, and the browser pane does the same -- pooling would be
## machinery bought with nothing.
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

## Fired when the observer's own slot on their tile moves, as an offset from
## the tile's centre.
##
## The pool does not draw the observer and must not start: the avatar hangs off
## the marker the camera follows and the aura ring is anchored to it, so moving
## the observer here would drag both off the tile. What crosses is an offset the
## pane applies WITHIN the marker, leaving the anchor where it was.
##
## Emitted on every rebuild, including the one that finds the observer standing
## alone again and hands back [constant Vector3.ZERO].
signal observer_slot_changed(offset: Vector3)

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

## Where meshes come from. Injected rather than built here: one resolver serves
## the whole client, so its model cache is shared and an asset fetched for the
## room is already to hand when the inventory asks for it.
var _resolver: MeshResolver


## Give the pool its resolver and its placement. Call before the first entity
## arrives.
func bind(resolver: MeshResolver, locate: Callable) -> void:
	_resolver = resolver
	_locate = locate

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
func replace_positions() -> void:
	_rebuild()


## Record which tile the observer is standing on. Takes effect on the next
## placement, which is why the world pane calls it immediately before
## [method replace_positions] rather than instead of it.
##
## A pure setter on purpose. Every other route into this file rebuilds because
## something it draws changed; this one changes something it does NOT draw, and
## rebuilding here would mean two full rebuilds on every step the observer takes.
##
## `coords` arrives in the same shape an entity carries them, so both sides of
## the comparison are spelled by [method _tile_key] and cannot drift.
func stand(coords: Array) -> void:
	_observer_tile = _tile_key(coords)


## Replace everything visible. `room_players` is the full list, sent on arrival
## and on resync; the add/remove channels carry the deltas in between.
func replace_all(entities: Array) -> void:
	_entities.clear()

	for entity: Dictionary in entities:
		_entities.append(entity)

	_rebuild()


func add(entity: Dictionary) -> void:
	if entity.is_empty():
		return

	_entities.append(entity)
	_rebuild()


func remove(entity_id: int) -> void:
	for index: int in _entities.size():
		if _id_of(_entities[index]) == entity_id:
			_entities.remove_at(index)
			_rebuild()
			return


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
		material.emission_enabled = lit
		material.emission = COLOR_HOVER_GLOW
		material.emission_energy_multiplier = HOVER_ENERGY


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

func _rebuild() -> void:
	for child: Node in get_children():
		remove_child(child)
		child.queue_free()

	_nodes.clear()

	# The lit node has just been freed, so the id is stale. Left set, the next
	# hover() on the same id would return early and the new node would never
	# light up -- an entity that stops responding to the cursor after any change
	# to the room, which is most of the time.
	_hovered = 0

	# Grouped by TILE first. The ring separates things standing in the same
	# place; entities in different rooms are in different places and must not
	# share one. Grouping also makes each ring's size depend on how many are
	# actually on that tile, rather than on how many the feed happened to send.
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

	var observer_offset := Vector3.ZERO

	for key: String in by_tile:
		var group: Dictionary = by_tile[key]
		var here: Array = group["entities"]

		# Sorted by id rather than left in arrival order. The slot INDEX is what
		# keeps a thing in the same place between frames, and arrival order does
		# not: removing the first of three entities used to shuffle the other
		# two around the ring for no reason the player could see. Ids are stable
		# and total, so the same occupants always produce the same ring.
		here.sort_custom(_by_id)

		# The observer is drawn by the world pane, not here, but they OCCUPY
		# their tile -- so they take slot 0 and everything standing with them
		# rings around from slot 1. Slot 0 and not their id's place in the sort,
		# because this file is never told what their id is and does not need to
		# be: one reserved slot is as stable as a sorted one.
		var shared := key == _observer_tile
		var occupants := here.size() + (1 if shared else 0)
		var first := 1 if shared else 0

		for index: int in here.size():
			var entity: Dictionary = here[index]
			var node := _build(entity)

			node.position = _slot_position(
				group["origin"], key, first + index, occupants)
			node.position.y += _rest_offset(node)
			add_child(node)
			_nodes[_id_of(entity)] = node

		if shared:
			# An OFFSET, so the origin is zero: the pane adds this inside the
			# marker, which is already standing on the tile this ring is drawn
			# around.
			observer_offset = _slot_position(Vector3.ZERO, key, 0, occupants)

	observer_slot_changed.emit(observer_offset)


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
## Rebuilds the whole ring rather than swapping one node, for the same reason
## every other change here does: there are rarely more than a handful, and the
## alternative is a second code path that places a single entity and can drift
## from the one that places them all.
func _on_art_arrived(asset_key: String) -> void:
	for entity: Dictionary in _entities:
		if str(entity.get("asset", "")) == asset_key:
			_rebuild()
			return


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
