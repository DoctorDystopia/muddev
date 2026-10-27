@tool
class_name TerrainModels
extends RefCounted
## The models that the terrain editor stands on the tiles of the chunk
## objects: the entity of a kind, or its scenery model.
##
## The server names the model of each kind. A kind that stands up an entity
## names it in [code]OBJECT_KIND_PREVIEW[/code]: the asset key and the family
## that the statefeed sends for that entity. A kind with scenery names it in
## [method TileTables.scenery_of]. A primitive draws through
## [PropMeshBuilder], so it is not a model here.
##
## ## The same model as the game
##
## A [MeshResolver] of [method MeshResolver.from_directory] gives each model,
## through the same ladder as the game: the served model, the model of the
## family, the family shape, then the generic block. An entity always draws.
## A scenery key with no served model draws nothing, as in the game. The
## scale, the rest on the ground, and the turn are those of [EntityPool] and
## [TerrainView]. Thus, what an author sees is what a player sees.
##
## ## The cost
##
## None in the game: the game never makes this class. In the editor, the
## first draw of a key reads and builds its file one time. Each redraw after
## that copies a cached model.

const _Const := preload("res://autoload/blackout_constants.gd")

## The web directory of the game, under the game directory. The model
## pipeline writes the served tree under it: `static/webclient/models/`.
const WEB_DIRECTORY := "web"

var _resolver: MeshResolver


## Models from the served tree of this repo. A missing manifest gives
## family shapes for the entities and no scenery.
static func for_repo() -> TerrainModels:
	return TerrainModels.new(repo_origin())


## The directory that holds the served `static/` tree of this repo.
static func repo_origin() -> String:
	var project := ProjectSettings.globalize_path("res://")
	var game := project.path_join(ChunkFile.GAME_DIRECTORY_FROM_PROJECT)

	return game.path_join(WEB_DIRECTORY).simplify_path()


func _init(origin: String) -> void:
	_resolver = MeshResolver.from_directory(origin)


## Free the models. Call this before the set goes: the resolver is a node
## outside the tree, so nothing else frees it.
func release() -> void:
	if _resolver == null:
		return

	_resolver.free_models()
	_resolver.free()
	_resolver = null


## True when `kind` draws a model here: an entity kind, an item spawn, or a
## kind with scenery that is not a primitive.
static func has_model(kind: String) -> bool:
	if _Const.OBJECT_KIND_PREVIEW.has(kind) or TerrainChecks.takes_spawn(kind):
		return true

	var scenery: String = TileTables.scenery_of(kind)

	return not scenery.is_empty() and not scenery in _Const.SCENERY_PRIMITIVES


## The model of one object (`{kind, x, y, rotation, look, spawn}` at world
## tiles), on the ground of its tile, turned as its object, and scaled,
## tilted, and nudged by its look (10/16/2026). Null for a kind with no
## model, and for scenery with no served model.
func stand(chunks: ChunkSet, thing: Dictionary) -> Node3D:
	var kind: String = thing["kind"]

	if _resolver == null or not has_model(kind):
		return null

	var model: Node3D = null
	var size := TerrainView.SCENERY_SCALE
	var preview: Array = preview_of(kind, thing.get("spawn", {}))
	var look: Dictionary = thing.get("look", {})
	var tile := Vector2i(thing["x"], thing["y"])
	var variant_seed := ObjectLook.seed_of(tile, chunks.plane)

	if not preview.is_empty():
		model = _resolver.resolve_entity(preview[0], preview[1], look, variant_seed)
		size = EntityPool.ENTITY_SCALE
	else:
		model = _resolver.resolve_scenery(TileTables.scenery_of(kind), look, variant_seed)

	if model == null:
		return null

	var base := TerrainOverlay.ground_point(chunks, Vector2(tile), 0.0)

	ObjectLook.apply(model, look, size, TerrainView.model_yaw(int(thing["rotation"])))
	model.position = base + Vector3.UP * ObjectLook.rest_lift(model) + ObjectLook.offset_of(look)

	return model


## The entity of an object: `[asset key, family]`, or an empty Array for an
## object that stands no entity. An item spawn draws its item as the client
## draws an item on the ground: the item key and the family of the item
## ([SpawnItems], 10/21/2026). Every other kind has its
## [code]OBJECT_KIND_PREVIEW[/code] row.
static func preview_of(kind: String, spawn: Dictionary) -> Array:
	if not spawn.is_empty():
		var item: String = spawn[_Const.SPAWN_ITEM_KEY]

		return [item, SpawnItems.game().family(item)]

	return _Const.OBJECT_KIND_PREVIEW.get(kind, [])


## The model key of a kind: the entity of a kind with a preview, or its
## scenery model. "" for a kind with no model, and for a primitive.
static func model_key_of(kind: String) -> String:
	var preview: Array = _Const.OBJECT_KIND_PREVIEW.get(kind, [])

	if not preview.is_empty():
		return preview[0]

	var scenery: String = TileTables.scenery_of(kind)

	return "" if scenery in _Const.SCENERY_PRIMITIVES else scenery


## The variant keys of the model of a kind, from the served variant map.
## Empty for a kind with no model, and for a model with no variant.
func variants_for(kind: String) -> PackedStringArray:
	var key := model_key_of(kind)

	if _resolver == null or key.is_empty():
		return PackedStringArray()

	return _resolver.variants_of(key)
