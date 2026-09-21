class_name ModelRegistry
extends RefCounted
## Which assets have real art, where to fetch it, and how to stand it up.
##
## Two facts live here and they come from opposite directions, which is the
## whole design:
##
## **WHICH models exist, and their paths** — fetched from the server, from
## `models/manifest.json`. The model pipeline (`blackout/assets/pipeline`)
## writes it: one model record in `assets/models/<family>/<key>.toml` makes a
## model exist, and no edit in this file is involved. Several asset keys can
## name one file (a record's `aliases`), and [ModelLoader] fetches that file
## one time.
##
## **HOW each one is shown** — [member PRESENTATION], below, hand-written.
## Purely the client's own, and CLAUDE.md is explicit that the model registry
## must never be generated.
##
## A correction to a bad EXPORT is not here. Since 09/18/2026 the build bakes
## it into the served file: the sword that pointed at the camera, the meat
## that lay end-on, the eye with a transparent body, the tiles that said BLEND.
## See the `[fix]` table of a model record. What stays here is a DISPLAY
## choice about a model that is correct as a file.
##
## ## Why fetched and not bundled
##
## Art inside the `.pck` ships **before the login prompt**, and that was
## 12 MiB with 10.9 of it a single character. Fetching at runtime is what keeps
## the `.pck` small and keeps the rule that art never blocks content.
##
## Convention plus a 404 was the other option, and `blackout_models.js` rejected
## it for a reason that still applies: with sixteen items in ITEM_DB and one
## model between them, fifteen 404s are the NORMAL case on every pane open, and
## a real one has nowhere to stand out.
##
## ## Degradation
##
## An asset key with no entry is not an error and never blocks anything — the
## caller draws its family's procedural mesh.
## The same is true before the manifest has arrived at all: [method has_model]
## simply answers false, so the first snapshot renders generics and sharpens
## when the art lands.

## Where the served model tree sits, relative to the game's web root.
const MODEL_ROOT := "/static/webclient/models/"

## The manifest file inside that tree.
const MANIFEST_PATH := MODEL_ROOT + "manifest.json"

## The model credits inside that tree, which [CreditsView] shows. The model
## pipeline writes it beside the manifest.
const CREDITS_PATH := MODEL_ROOT + "credits.json"

## Per-model display choices. PRESENTATION, hand-written, never generated.
##
## Keyed by asset key. Anything absent is drawn as the file is built.
const PRESENTATION := {
	# The eye's pupil sits low in its own bounding box, so centring the box
	# leaves the eye looking down through the floor. A lift in normalised
	# units, applied after the centring.
	"floating_eye": {"offset": Vector3(0.0, 0.16, 0.0)},
	
	# THE ONLY MODEL WHOSE ORIENTATION IS A GAMEPLAY FACT. The download is a
	# skeleton STANDING UP, because that is what a character model is, and it
	# is served as the stand-in for the corpse family (FamilyShapes.MODELS) —
	# so a body that has not been laid down is a skeleton standing on the tile
	# where something died, which reads as a live enemy rather than as loot.
	#
	# -PI/2 rather than +PI/2 puts it on its BACK. The model faces +Z, so the
	# negative turn takes the front to +Y and leaves the ribcage and skull
	# facing the camera; the positive turn buries the face in the sand. Neither
	# is wrong about the file and only a person looking at it can tell.
	#
	# No offset. EntityPool lifts a node by its own lowest point (_rest_offset),
	# so the body sits on the ground once it is flat without a number here.
	"corpse_skeleton": {"rotation": Vector3(-PI / 2.0, 0.0, 0.0)},
	
	# The loader stretches every model until its longest side is one unit.
	# A multiplier on that unit, not a size in meters. Keyed by the file's
	# own key, so every ammunition alias of the clip shrinks with it.
	"heavy_machine_gun_clip": {"scale": 0.4},

	# THE ONLY PLACE A MUTANT TIER IS BIGGER THAN ANOTHER. One goblin stands
	# in for all three tiers today (`assets/models/npcs/mutant_raider.toml`
	# aliases both of these), and the loader normalises every model to one
	# unit — so without these two numbers a Mutant Giant is exactly as tall as
	# the raider it is named against.
	#
	# Size is a look, not a rule. Nothing in combat reads either number, and
	# the stats that make a giant a giant are in `world/npc_defs/hostile.py`.
	# Both entries drop out the day a tier gets art of its own, because a key
	# with its own model record is drawn as that file builds it.
	"mutant_giant": {"scale": 1.6},
	"big_mutant": {"scale": 2.1},
}

## asset_key -> "family/asset_key.glb", straight from the served manifest.
var _paths: Dictionary = {}

## True once a manifest has been ingested, successfully or not. Distinguishes
## "no art for this key" from "we have not been told yet", which decides whether
## a caller should bother asking again.
var _manifest_seen := false


## Fold the served manifest into the registry.
##
## Returns the number of usable entries. A malformed document is dropped rather
## than raised on: the manifest is a rendering convenience, and a client that
## refuses to start because art metadata is unreadable is worse than one that
## draws generics.
func ingest_manifest(document: Variant) -> int:
	_manifest_seen = true
	_paths = {}

	if typeof(document) != TYPE_DICTIONARY:
		return 0

	for asset_key: Variant in document:
		var relative := str(document[asset_key])

		# A path that escapes the model tree is refused rather than fetched.
		# The manifest is server-rendered and trusted today, but this costs one
		# comparison and means a compromised or hand-edited manifest cannot
		# point the client at an arbitrary URL.
		if relative.is_empty() or relative.begins_with("/") \
				or relative.contains("..") or relative.contains("://"):
			push_warning("ModelRegistry: refusing suspicious path %s" % relative)
			continue

		_paths[str(asset_key)] = relative

	return _paths.size()


## Has the server told us about art for this asset key?
func has_model(asset_key: String) -> bool:
	return _paths.has(asset_key)


## True once a manifest has been ingested, whatever it contained.
func manifest_seen() -> bool:
	return _manifest_seen


## The absolute URL to fetch one model from, or "" when there is no art.
##
## `base` is the game's web origin, e.g. "https://game.playblackout.io". Note
## this is the WEBSERVER, not the websocket: the state feed and the art travel
## over different transports and only the feed goes through the Godot port.
func url_for(base: String, asset_key: String) -> String:
	if not has_model(asset_key):
		return ""

	return base.rstrip("/") + MODEL_ROOT + _paths[asset_key]


## The manifest URL for one origin.
func manifest_url(base: String) -> String:
	return base.rstrip("/") + MANIFEST_PATH


## The credits URL for one origin.
func credits_url(base: String) -> String:
	return base.rstrip("/") + CREDITS_PATH


## How this model should be rotated once loaded, in radians.
##
## Zero for anything with no entry, which is most of them — a model is drawn as
## exported unless somebody decided otherwise.
func rotation_for(asset_key: String) -> Vector3:
	var entry := _presentation(asset_key)

	return entry.get("rotation", Vector3.ZERO)


## A multiplier on the unit box, applied after the normalise.
##
## One for anything with no entry. The normalise makes every model one unit on
## its longest side, which is right for most and wrong for a small thing that
## shares a pane with a large one: a clip beside the gun it feeds.
func scale_for(asset_key: String) -> float:
	var entry := _presentation(asset_key)

	return float(entry.get("scale", 1.0))


## An extra nudge applied AFTER centring, in normalised units.
##
## For a model whose visible mass is not where its bounding box centre says. The
## eye's pupil sits low in its own box, so centring the box leaves the eye
## looking down through the floor.
func offset_for(asset_key: String) -> Vector3:
	var entry := _presentation(asset_key)

	return entry.get("offset", Vector3.ZERO)


## The PRESENTATION entry for one key, or for the file that the key draws.
##
## An alias is a second key for the same file, and the pipeline writes the file
## under its record's own key. The server sends the ITEM key, so without this
## fallback every new ammunition alias of the clip would need its own entry and
## would draw full size until someone added it. The key's own entry wins, so
## two aliases of one file can still differ.
func _presentation(asset_key: String) -> Dictionary:
	if PRESENTATION.has(asset_key):
		return PRESENTATION[asset_key]

	var file_key := str(_paths.get(asset_key, "")).get_file().get_basename()

	return PRESENTATION.get(file_key, {})


## Every asset key the server has art for. Sorted, so callers that iterate are
## deterministic rather than depending on dictionary order.
func known_keys() -> PackedStringArray:
	var keys: Array = _paths.keys()
	keys.sort()

	return PackedStringArray(keys)
