class_name ModelRegistry
extends RefCounted
## Which assets have real art, where to fetch it, and how to stand it up.
##
## Two facts live here and they come from opposite directions, which is the
## whole design:
##
## **WHICH models exist, and their paths** — fetched from the server, from
## `models/manifest.json`, rendered by `assets/pack_model.py`. A build fact:
## adding a row to `assets/model_manifest.json` and repacking is what makes a
## model exist, and no edit in this file is involved.
##
## **HOW each one is oriented** — [member PRESENTATION], below, hand-written.
## Purely the client's own, and CLAUDE.md is explicit that the model registry
## must never be generated: the sword's quarter-turn is a judgement about how a
## blade should read in an inventory cell, not something the server knows.
##
## ## Why fetched and not bundled
##
## The browser client hardcodes its list because it fetches a `.glb` only when
## something needs drawing, so a player who never opens the inventory never
## downloads the sword. A Godot export cannot copy that by bundling: art inside
## the `.pck` ships **before the login prompt**, and that is 12 MiB today with
## 10.9 of it a single character. Fetching at runtime is what keeps the `.pck`
## small and keeps the rule that art never blocks content.
##
## Convention plus a 404 was the other option, and `blackout_models.js` rejected
## it for a reason that still applies: with sixteen items in ITEM_DB and one
## model between them, fifteen 404s are the NORMAL case on every pane open, and
## a real one has nowhere to stand out.
##
## ## Degradation
##
## An asset key with no entry is not an error and never blocks anything — the
## caller draws its family's procedural mesh, exactly as the browser pane does.
## The same is true before the manifest has arrived at all: [method has_model]
## simply answers false, so the first snapshot renders generics and sharpens
## when the art lands.

## Where the served model tree sits, relative to the game's web root.
const MODEL_ROOT := "/static/webclient/models/"

## The manifest file inside that tree.
const MANIFEST_PATH := MODEL_ROOT + "manifest.json"

## Per-model orientation and scale. PRESENTATION, hand-written, never generated.
##
## Keyed by asset key, mirroring the options `blackout_models.js` passes to
## `registerModel`. Anything absent is drawn as the file exports it.
##
## Both panes get put side by side on the same character, so a model that is
## upright in one and face-down in the other reads as a bug — keep these in
## step with the browser's table.
const PRESENTATION := {
	# The export carries a Y-up conversion matrix that leaves the blade running
	# along Z, pointing straight at the camera in an inventory cell, where a
	# sword is a smudge two pixels wide. +PI/2 rather than -PI/2 puts the TIP up
	# and the guard down, matching the procedural weapon the pane's labels and
	# tilt are aimed at.
	"rusty_scrap_shortsword": {"rotation": Vector3(PI / 2.0, 0.0, 0.0)},

	# An export can be WRONG ABOUT ITSELF in a way no measurement catches.
	# Sketchfab's converter wrote the authoring tool's base-colour alpha into
	# the glTF, so the eye's body arrives with alpha 0 against alphaMode BLEND:
	# a fully transparent material on a mesh plainly meant to be seen. Nothing
	# downstream recovers from that -- it loads, reports no error, and draws an
	# invisible body around a floating eyeball.
	#
	# Verified in Godot 08/26/2026, and it is the same two surfaces the browser
	# found: one at albedo alpha 0.0 with transparency ALPHA_DEPTH_PRE_PASS.
	# `blackout_models.js` corrects it with `opaque: true` and this is that same
	# correction, which README rule 5 requires -- a model solid in one pane and
	# see-through in the other reads as a bug.
	"floating_eye": {
		"opaque": true,
		"offset": Vector3(0.0, 0.16, 0.0),
	},
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


## How this model should be rotated once loaded, in radians.
##
## Zero for anything with no entry, which is most of them — a model is drawn as
## exported unless somebody decided otherwise.
func rotation_for(asset_key: String) -> Vector3:
	var entry: Dictionary = PRESENTATION.get(asset_key, {})

	return entry.get("rotation", Vector3.ZERO)


## An extra nudge applied AFTER centring, in normalised units.
##
## For a model whose visible mass is not where its bounding box centre says. The
## eye's pupil sits low in its own box, so centring the box leaves the eye
## looking down through the floor.
func offset_for(asset_key: String) -> Vector3:
	var entry: Dictionary = PRESENTATION.get(asset_key, {})

	return entry.get("offset", Vector3.ZERO)


## Whether this model's materials should be forced solid.
##
## See the `floating_eye` entry: an export can declare itself transparent and be
## wrong, and no measurement catches it because nothing about the file is
## invalid. Only a person looking at it can tell, which is why this is a
## hand-written correction and not something derived.
func force_opaque(asset_key: String) -> bool:
	var entry: Dictionary = PRESENTATION.get(asset_key, {})

	return bool(entry.get("opaque", false))


## Every asset key the server has art for. Sorted, so callers that iterate are
## deterministic rather than depending on dictionary order.
func known_keys() -> PackedStringArray:
	var keys: Array = _paths.keys()
	keys.sort()

	return PackedStringArray(keys)
