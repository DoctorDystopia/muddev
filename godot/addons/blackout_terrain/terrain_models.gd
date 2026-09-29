@tool
class_name TerrainModels
extends RefCounted
## The models that the terrain editor stands on the tiles of the chunk
## objects: the entity of a kind, or its scenery model.
##
## The server names the model of each kind. A kind that stands up an entity
## names it in [code]OBJECT_KIND_PREVIEW[/code]: the asset key and the family
## that the statefeed sends for that entity. A kind with scenery names it in
## [code]OBJECT_KIND_SCENERY[/code]. A primitive draws through
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


## True when `kind` draws a model here: an entity kind, or a kind with
## scenery that is not a primitive.
static func has_model(kind: String) -> bool:
	if _Const.OBJECT_KIND_PREVIEW.has(kind):
		return true

	var scenery: String = _Const.OBJECT_KIND_SCENERY.get(kind, "")

	return not scenery.is_empty() and not scenery in _Const.SCENERY_PRIMITIVES


## The model of one object (`{kind, x, y, rotation}` at world tiles), on the
## ground of its tile and turned as its object. Null for a kind with no
## model, and for scenery with no served model.
func stand(chunks: ChunkSet, thing: Dictionary) -> Node3D:
	var kind: String = thing["kind"]

	if _resolver == null or not has_model(kind):
		return null

	var model: Node3D = null
	var size := TerrainView.SCENERY_SCALE
	var preview: Array = _Const.OBJECT_KIND_PREVIEW.get(kind, [])

	if not preview.is_empty():
		model = _resolver.resolve_entity(preview[0], preview[1])
		size = EntityPool.ENTITY_SCALE
	else:
		model = _resolver.resolve_scenery(_Const.OBJECT_KIND_SCENERY[kind])

	if model == null:
		return null

	var base := TerrainOverlay.ground_point(chunks, Vector2(thing["x"], thing["y"]), 0.0)

	model.scale = Vector3.ONE * size

	# The bounds leave out the transform of the root, so the lift is the
	# unscaled bottom times the scale: the rule of EntityPool._rest_offset.
	var bounds := ModelLoader.bounds_of(model)

	model.position = base + Vector3.UP * (-bounds.position.y * size)
	model.rotation.y = TerrainView.model_yaw(int(thing["rotation"]))

	return model
