class_name FigureLibrary
extends Node
## The figure set of the game, and the figure of each player character
## (DESIGN-0014 section 20).
##
## The server sends the body type and the figure colors of each player
## character. This class builds the figure from them, through
## [FigureBuilder] and the same `figure.json` that the figure workbench
## writes. Thus, what the author sees is what the player sees.
##
## ## Where the figure set comes from
##
## [method fetch] gets `figure.json` from the origin of the models
## ([method ModelRegistry.figure_url]). On the web, that is the page origin,
## as for each model. The console calls it at the start, and again each time
## the loading veil goes up. A reconnect thus gets each change that a save
## in the workbench made, with no new client.
##
## ## The model of a part
##
## A part can name a node of a served model (Phase W4). This class asks the
## mesh ladder for each model that a look names, and it gives the bytes to
## [FigureModels] when the file arrives. The fetch is the fetch of the mesh
## ladder, so one file costs one request. Until the model is in hand, the
## part draws its shape list.
##
## ## The node of a figure
##
##     FigureHolder (Node3D), the node that a pane places, turns, and scales
##       Figure (Node3D), of [method FigureBuilder.build], at the size of
##       FIGURE_HEIGHT
##
## The holder knows its box ([constant ModelLoader.BOUNDS_META]). The feet
## are at its origin, so a pane puts the holder on the tile with no lift.
##
## Each figure has its own materials. The hit flash and the hover glow of
## [EntityPool] write to the materials of one node, and a shared material
## would flash each figure.
##
## ## This is the attached version
##
## Each figure is one [FigureBuilder] node: one draw for each surface of
## each part. Section 20 of DESIGN-0014 gives the crowd numbers that permit
## it for the count of players of today, and the count at which the shared
## version must replace it.

## Emitted when the figure set arrives, or when a model of a part arrives.
## Each pane then builds its figures again.
signal changed

## The height of a figure in the world: a model of the mesh ladder is one
## unit on its longest side, so a figure is as tall as the models beside it.
const FIGURE_HEIGHT := 1.0

## The socket at the top of the head. Its rest gives the height of a rig.
const TOP_BONE := "head_top"

## The height of a rig with no top socket, in figure units.
const FALLBACK_TOP := 1.7

## Half the width of the box of a figure, in figure units. The pool reads
## the box for the lift and for the label, and neither reads the width.
const HALF_WIDTH := 0.35

const HOLDER_NAME := "FigureHolder"

## The meta of a holder of [method build].
const HOLDER_META := "figure_holder"

## The meta of a figure node: the action whose clip it plays.
const ACTION_META := "figure_action"

## Why a figure set with no rig does not serve: no figure can stand.
const NO_RIG := "it has no rig"

## How many more times to ask for `figure.json` after a failure.
const RETRIES := 2

## The figure set, or null until it arrives.
var figure_set: FigureSet = null

## The meshes of the models that the parts name.
var models := FigureModels.new()

var _resolver: MeshResolver
var _url := ""

## The text of the figure set in hand.
var _text := ""

## True when this figure set asked for the manifest again.
var _manifest_asked := false
var _fetching := false
var _attempts := 0

## Model key -> true, for each model that a look names and that is not in
## hand yet.
var _wanted := {}

## World units for each figure unit. One scale for each rig, so a shorter
## body type stands shorter.
var _scale := 1.0

## The stance table, read one time.
static var _stances: FigureStances = null


## Give the library the mesh ladder and the URL of `figure.json`.
func bind(resolver: MeshResolver, url: String) -> void:
	_resolver = resolver
	_url = url
	_resolver.refreshed.connect(_on_art_arrived)
	_resolver.manifest_ready.connect(_on_manifest_ready)


## Ask for `figure.json`. A second call while a fetch is in the air does
## nothing.
func fetch() -> void:
	if _fetching or _url.is_empty():
		return

	_fetching = true
	_attempts = 0
	_start()


## True when the figure set is in hand.
func has_set() -> bool:
	return figure_set != null


## Take a figure set as text. Returns false for a text that does not read.
## The set then stays as it was. [method fetch] ends here, and a test calls
## it directly.
func take_text(text: String) -> bool:
	# A fetch at each veil gets the same text most of the time. The same
	# text builds no figure again.
	if figure_set != null and text == _text:
		return true

	var read := FigureSet.from_text(text)

	if not read.error.is_empty() or read.rigs.is_empty():
		push_warning("FigureLibrary: figure.json does not read: %s"
			% (NO_RIG if read.error.is_empty() else read.error))
		return false

	for line: String in read.errors:
		push_warning("FigureLibrary: " + line)

	figure_set = read
	_text = text
	_manifest_asked = false
	_scale = FIGURE_HEIGHT / _tallest(read.rigs.values())
	_want_models()
	changed.emit()

	return true


## The figure of one player character, or null when the figure set is not
## in hand. A body type with no rig gets the first rig: a person who looks
## like another body type is better than a block (requirement D7).
func build(body_type: String, figure_colors: Dictionary) -> Node3D:
	var rig := _rig_for(body_type)

	if rig == null:
		return null

	var looks := FigureOutfit.looks_for(rig, {}, figure_set.looks)
	var figure := FigureBuilder.build(rig, looks, models, figure_set.palette, figure_colors)
	var holder := Node3D.new()
	var top := _top_of(rig) * _scale
	var half := HALF_WIDTH * _scale

	holder.name = HOLDER_NAME
	holder.set_meta(HOLDER_META, true)
	figure.scale = Vector3.ONE * _scale
	holder.add_child(figure)
	holder.set_meta(ModelLoader.BOUNDS_META,
		AABB(Vector3(-half, 0.0, -half), Vector3(half * 2.0, top, half * 2.0)))
	_own_materials(figure)
	play(holder, FigureStances.ACTION_IDLE)

	return holder


## One text for what a figure looks like: the body type and the colors. A
## pane builds a figure again only when this text changes.
static func look_key(body_type: String, figure_colors: Dictionary) -> String:
	return body_type + "|" + JSON.stringify(figure_colors, "", true)


## The figure node of a holder of [method build], or null for another node.
## The meta finds a holder, not the name: a parent with several figures
## gives each new one another name.
static func figure_of(holder: Node3D) -> Node3D:
	if holder == null or not holder.has_meta(HOLDER_META):
		return null

	return holder.get_node_or_null(FigureBuilder.FIGURE_NAME) as Node3D


## Play the clip of one action on a figure: idle, walk. The clip comes from
## the default clip set of the stance table. A figure that plays the clip of
## that action already goes on with it.
static func play(holder: Node3D, action: String) -> void:
	var figure := figure_of(holder)

	if figure == null or figure.get_meta(ACTION_META, "") == action:
		return

	var clip := _stance_table().clip_for("", action)

	if clip.is_empty():
		clip = _stance_table().clip_for("", FigureStances.ACTION_IDLE)

	figure.set_meta(ACTION_META, action)
	FigureClips.play(figure, clip)


# ─── Private ────────────────────────────────────────────────────────────────

func _start() -> void:
	var http := ModelLoader.new_request()

	add_child(http)
	http.request_completed.connect(
		func(result: int, code: int, _headers: PackedStringArray,
				body: PackedByteArray) -> void:
			http.queue_free()
			_finish(result, code, body))

	if http.request(_url) != OK:
		http.queue_free()
		_fetching = false
		push_warning("FigureLibrary: the request for %s was refused" % _url)


## A fetch ended. A failure that can pass asks again. Each other failure
## keeps the figure set as it was, and each figure draws as it drew.
func _finish(result: int, code: int, body: PackedByteArray) -> void:
	var passed := result == HTTPRequest.RESULT_SUCCESS and code == 200

	if not passed and _attempts < RETRIES \
			and (result != HTTPRequest.RESULT_SUCCESS
				or code >= HTTPClient.RESPONSE_INTERNAL_SERVER_ERROR):
		_attempts += 1
		_start()
		return

	_fetching = false

	if not passed:
		push_warning("FigureLibrary: %s gave http %d (result %d)" % [_url, code, result])
		return

	take_text(body.get_string_from_utf8())


## Ask the mesh ladder for each model that a look names. A model already in
## hand goes to [member models] now.
func _want_models() -> void:
	_wanted.clear()

	for look: FigureLook in figure_set.looks.values():
		for model_key: String in look.model_keys():
			if not models.has(model_key):
				_wanted[model_key] = true

	_ask_for_wanted()


## Ask the mesh ladder for each wanted model. A model that the manifest does
## not name is newer than the manifest. The manifest then comes again, one
## time for each figure set, and [method _on_manifest_ready] asks again.
## Before the first manifest, nothing comes again: its arrival asks.
func _ask_for_wanted() -> void:
	var unknown := false

	for model_key: String in _wanted.keys():
		if _take_model(model_key) or _resolver == null:
			continue

		if _resolver.may_have_art(model_key):
			_resolver.want(model_key)
		else:
			unknown = true

	if unknown and not _manifest_asked and _resolver.has_manifest():
		_manifest_asked = true
		_resolver.refresh_manifest()


func _on_manifest_ready(_count: int) -> void:
	_ask_for_wanted()


## Give the bytes of one model to [member models]. Returns true when the
## model is in hand after.
func _take_model(model_key: String) -> bool:
	if _resolver == null:
		return false

	var body := _resolver.model_body(model_key)

	if body.is_empty() or not models.put_buffer(model_key, body):
		return false

	_wanted.erase(model_key)

	return true


func _on_art_arrived(asset_key: String) -> void:
	if _wanted.has(asset_key) and _take_model(asset_key):
		changed.emit()


func _rig_for(body_type: String) -> FigureRig:
	if figure_set == null:
		return null

	if figure_set.rigs.has(body_type):
		return figure_set.rigs[body_type]

	var keys := figure_set.rigs.keys()

	keys.sort()

	return figure_set.rigs[keys[0]]


## The height of the tallest rig, in figure units.
static func _tallest(rigs: Array) -> float:
	var tallest := 0.0

	for rig: FigureRig in rigs:
		tallest = maxf(tallest, _top_of(rig))

	return tallest if tallest > 0.0 else FALLBACK_TOP


static func _top_of(rig: FigureRig) -> float:
	if not rig.has_bone(TOP_BONE):
		return FALLBACK_TOP

	return rig.global_rest_of(TOP_BONE).origin.y


static func _stance_table() -> FigureStances:
	if _stances == null:
		_stances = FigureStances.read_file()

	return _stances


## Give each surface of a figure a material of its own. A shape of a shape
## list has a new material already. A surface of a model shares the
## material of its model, or one material of the cache of the builder.
static func _own_materials(root: Node) -> void:
	for child: Node in root.get_children():
		var instance := child as MeshInstance3D

		if instance != null and instance.mesh != null and instance.material_override == null:
			for surface in instance.mesh.get_surface_count():
				var material := instance.get_surface_override_material(surface)

				if material == null:
					material = instance.mesh.surface_get_material(surface)

				if material != null:
					var own := material.duplicate() as Material

					MeshGlow.prepare(own as BaseMaterial3D)
					instance.set_surface_override_material(surface, own)

		_own_materials(child)
