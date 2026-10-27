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
## ## The served model of a worn item (10/17/2026)
##
## A served model of the asset key wins over the worn look of the item, in
## the hand as in a cell ([FigureOutfit]). [method build] asks the mesh
## ladder for the served model of each worn item. Until the file arrives,
## the worn look stands in. The arrival emits [signal changed], and each
## pane builds its figures again.
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
##
## ## The picture of an item
##
## [method build_item] gives the worn look of one item alone, in the unit
## box of the mesh ladder (10/17/2026). [ItemStage] draws it in a cell of
## the bag, of the doll, and of a pop-up. [EntityPool] draws it on the
## ground. A served model of the asset key wins over the worn look. An item
## with neither draws its family model or its family shape, as before.

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

const ITEM_HOLDER_NAME := "ItemHolder"

## The body type of the rig that an item stands on: none. An item has no
## wearer, so it gets the first rig, as an unknown body type does.
const ITEM_BODY_TYPE := ""

## The meta of a holder of [method build].
const HOLDER_META := "figure_holder"

## The meta of a figure node: the action whose clip it plays.
const ACTION_META := "figure_action"

## The meta of a figure node: the action that the frame asks for, idle or
## walk. A swing goes back to the clip of this action at its end.
const REST_META := "figure_rest_action"

## The meta of a figure node: the clip of the swing that it plays, or "".
const STRIKE_META := "figure_strike_clip"

## The seconds that a swing takes to blend in from the clip before it, and
## to blend out into the clip after it. Without a blend, the figure jumps
## to the first pose of the swing.
const STRIKE_BLEND := 0.12

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
##
## `worn` is the worn record of the character: slot -> asset key. Each item
## draws its served model, its worn look, or the slot shape
## ([method FigureOutfit.looks_for]). An empty record dresses the body with
## nothing.
func build(body_type: String, figure_colors: Dictionary, worn: Dictionary = {}) -> Node3D:
	var rig := _rig_for(body_type)

	if rig == null:
		return null

	_want_worn(worn)

	var looks := FigureOutfit.looks_for(rig, worn, figure_set.looks, {}, {}, models)
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


## The picture of one item: its worn look alone, scaled so that its longest
## side is one unit, and centered on the origin. The holder has no scale and
## no turn, so a pane can set them.
##
## Null when the figure set is not in hand, when no look has the asset key,
## or when the look draws no part: a tier with no base, for example. The
## pane then draws the item through the mesh ladder.
##
## A part with a model draws its shape list until the model is in hand.
## [signal changed] then tells the pane to draw the item again.
##
## Each picture has its own materials, as a figure does. The pool of the
## world draws an item on the ground with it ([EntityPool]). The hover glow
## and the hit flash of the pool write to the materials of one node.
func build_item(asset_key: String) -> Node3D:
	if not has_item_look(asset_key):
		return null

	var looks: Dictionary = figure_set.looks
	var look: FigureLook = looks[asset_key].resolved(looks)
	var item := FigureBuilder.build_item(_rig_for(ITEM_BODY_TYPE), look, models,
		figure_set.palette)

	if item.get_child_count() == 0:
		item.free()
		return null

	var holder := Node3D.new()

	holder.name = ITEM_HOLDER_NAME
	holder.add_child(item)
	ModelLoader.normalise(item)
	_own_materials(item)

	return holder


## True when the figure set is in hand and has a look for the asset key.
## The picture of the key can still be null: a tier with no base gives no
## picture ([method build_item]).
func has_item_look(asset_key: String) -> bool:
	return figure_set != null and figure_set.looks.has(asset_key)


## One text for what a figure looks like: the body type, the colors, and the
## worn record. A pane builds a figure again only when this text changes.
static func look_key(body_type: String, figure_colors: Dictionary, worn: Dictionary = {}) -> String:
	return "%s|%s|%s" % [body_type, JSON.stringify(figure_colors, "", true),
		JSON.stringify(worn, "", true)]


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
##
## A pane calls this on each frame. A swing that plays ([method strike])
## stays until its end. The action of the frame then follows it.
static func play(holder: Node3D, action: String) -> void:
	var figure := figure_of(holder)

	if figure == null:
		return

	figure.set_meta(REST_META, action)

	if figure.get_meta(ACTION_META, "") == action:
		return

	var clip := _rest_clip(action)

	if _striking(figure):
		_queue_after_strike(figure, clip)
		return

	figure.set_meta(ACTION_META, action)
	figure.set_meta(STRIKE_META, "")

	# The queue of a swing starts this clip at the end of the swing, with a
	# blend. A new start would cut that blend.
	if not _plays(figure, clip):
		FigureClips.play(figure, clip)


## Play the clip of one attack action on a figure, one time: one swing
## (`figure_action` of `blackout_combat`, 10/25/2026). An action with no
## clip of its own plays the clip of `attack`. A figure with neither clip
## keeps what it plays.
##
## A second swing starts again from the start of its clip. At the end of a
## swing, the player goes on with the clip of the action of the frame, from
## a queue. Thus, a figure that no pane plays on each frame also goes back.
static func strike(holder: Node3D, action: String) -> void:
	var figure := figure_of(holder)

	if figure == null:
		return

	var clip := _stance_table().attack_clip_for("", action)

	if clip.is_empty() or not FigureClips.play(figure, clip, 1.0, STRIKE_BLEND):
		return

	var rest: String = figure.get_meta(REST_META, FigureStances.ACTION_IDLE)

	figure.set_meta(ACTION_META, action)
	figure.set_meta(STRIKE_META, clip)
	_queue_after_strike(figure, _rest_clip(rest))


## True while a figure plays a swing that has not ended. A clip that loops
## never ends, so it is no swing: the action of the next frame replaces it.
static func is_striking(holder: Node3D) -> bool:
	var figure := figure_of(holder)

	return figure != null and _striking(figure)


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


## Ask the mesh ladder for the served model of each item of a worn record.
## A model in hand goes to [member models] now. A key that the manifest does
## not name has no served model, so nothing asks for it.
func _want_worn(worn: Dictionary) -> void:
	if _resolver == null:
		return

	for value: Variant in worn.values():
		var asset_key := str(value)

		if asset_key.is_empty() or models.has(asset_key) \
				or not _resolver.may_have_art(asset_key) or _take_model(asset_key):
			continue

		_wanted[asset_key] = true
		_resolver.want(asset_key)


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


## The clip of an action of the frame. An action with no clip idles.
static func _rest_clip(action: String) -> String:
	var clip := _stance_table().clip_for("", action)

	return _stance_table().clip_for("", FigureStances.ACTION_IDLE) if clip.is_empty() else clip


## True while the player of a figure plays the clip of a swing, and the clip
## does not loop.
static func _striking(figure: Node3D) -> bool:
	var clip: String = figure.get_meta(STRIKE_META, "")
	var player := FigureClips.player_of(figure)

	if clip.is_empty() or not player.is_playing() or player.current_animation != clip:
		return false

	return player.get_animation(clip).loop_mode == Animation.LOOP_NONE


## Start `clip` at the end of the swing that a figure plays, with a blend.
## The queue holds one clip: a new one takes the place of the old one.
static func _queue_after_strike(figure: Node3D, clip: String) -> void:
	var player := FigureClips.player_of(figure)
	var strike_clip: String = figure.get_meta(STRIKE_META, "")

	player.clear_queue()

	if not player.has_animation(clip):
		return

	player.set_blend_time(strike_clip, clip, STRIKE_BLEND)
	player.queue(clip)


## True when the player of a figure plays `clip` now.
static func _plays(figure: Node3D, clip: String) -> bool:
	var player := FigureClips.player_of(figure)

	return player.is_playing() and player.current_animation == clip


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
