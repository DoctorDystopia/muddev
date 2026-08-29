class_name MapPalette
extends RefCounted
## What the map LOOKS like: the colour of each room kind, and the order the
## islands sit in.
##
## Extracted from `world_view.gd` on 08/28/2026, when the minimap became a
## second thing that draws the same map. A second copy of either table is
## exactly the failure this repo has already paid for once -- the dead
## `"Pole clearing"` room kind reached two clients and rendered a fallback hue
## in both -- so the tables moved rather than being duplicated.
##
## ## Neither table is generated, and that is deliberate
##
## Both mix a SERVER fact (which room kinds and maps exist) with a CLIENT one
## (what colour, what order). CLAUDE.md names them as the pair that is guarded
## instead of generated, by
## `blackout/systems/statefeed/tests/test_client_constants.py`. The asymmetry
## that guard encodes is the whole design:
##
##     A client key naming NO room kind is a bug -- dead configuration that
##     looks like configuration, while the thing it meant to colour silently
##     gets the fallback.
##
##     A room kind with NO entry here is FINE. It hashes to a stable hue, so
##     adding content never requires a client edit.
##
## **That test reads this file BY PATH, as text.** Moving it, or renaming
## either table, means editing `_ROOM_KIND_TABLE_SOURCES` in the same change --
## the test carries a vacuity guard precisely because "skipped the client it
## could not find" is how it would quietly stop testing anything.
##
## A RefCounted with only static members: it is never instantiated, and exists
## as a class so both panes can reach it by name.

## Where an island sits along world X, for maps that are listed.
##
## Z is a map NAME, not an elevation, and their relative placement cannot be
## computed from the data -- so it is authored. A map not listed still appears,
## after the named ones.
const Z_LAYOUT_ORDER := ["oasis", "oasis_outskirts", "trade town sector 1"]

## The terrain each map's ground is surfaced with, as an asset key.
##
## A map named here draws its own art on top of every tile; a map not named
## keeps the plain coloured slab, which is what every map was before 08/28/2026
## and is still what "trade town sector 1" gets. Same degradation as a tile
## prop, and deliberately: art is a convenience, and a map has to be playable
## the moment it exists rather than the moment somebody draws it.
##
## THE KEY IS A MAP NAME AND THE VALUE IS AN ASSET KEY, and the two are checked
## from opposite ends. `test_client_constants.py` asserts every key names a map
## some module declares and every value names a model
## `assets/model_manifest.json` builds -- because both halves fail SILENTLY.
## A misspelled map draws no terrain on a map that exists; a misspelled asset
## key fetches nothing and leaves the slab, and neither logs anything.
##
## Client-owned, like the two tables below it. WHICH maps exist is the server's
## fact; which of them looks like sand and which looks like an oasis is not
## something the feed says or should.
const TILE_MODELS := {
	# center_h and center_b out of the same desert tileset -- one carries a
	# water pool and some rock, the other is open sand. The oasis is the wet
	# one, which is the entire difference between the two maps in the fiction.
	"oasis": "tile_oasis",
	"oasis_outskirts": "tile_oasis_outskirts",
}

## What a tile with no room kind at all is drawn in.
const COLOR_TILE_DEFAULT := Color("2b3a4a")

## Saturation and lightness a hash-coloured room kind is given.
## Named in ITS colour space -- HSL -- rather than pre-converted, so the pair
## can be compared against blackout3d.js's `setHSL(hue, 0.42, 0.42)` by eye.
const KIND_HSL_SATURATION := 0.42
const KIND_HSL_LIGHTNESS := 0.42

## Must colour the SAME set of room kinds as blackout3d.js, key for key --
## ClientRoomKindTests asserts it in both directions.
const ROOM_KIND_COLORS := {
	"Bank": Color("4488ff"),
	"Foundry Furnace Facility": Color("dd4422"),
	"Metalsmith Anvil Facility": Color("aaaaaa"),
	# Two clearings, not one, and they are told apart by what they yield:
	# oasis grows rusty poles, oasis_outskirts grows metal ones. Coloured for
	# the material rather than for the tile, so the map reads as a gradient
	# from scrap to stock as the player moves out.
	#
	# This said "Pole clearing" until 08/25/2026 -- a key no map has ever
	# declared, copied here from the browser pane before that pane was fixed.
	# Both real clearings rendered the hash colour and nothing errored.
	"Rusty pole clearing": Color("cc6633"),
	"Metal pole clearing": Color("8899a6"),
	"Shopkeeper": Color("ddcc44"),
	"Mutant Raider Tile": Color("8fbf00"),
	"Big Mutant Tile": Color("bf3f00"),
	# Not a prototype key like the rest: the server synthesises this one for a
	# node that spawns no room. It is the way OFF the map, so it is coloured
	# whether or not the teleporter model is there to stand on it.
	#
	# A LITERAL, though Const.ROOM_KIND_TRANSITION holds the same string and
	# blackout_models.js imports it. ClientRoomKindTests reads both clients as
	# TEXT -- that is what lets one test cover two languages without importing
	# either -- so a key written as a constant reference is invisible to it and
	# reads as "this client colours nothing here". blackout3d.js spells it
	# literally for the same reason. Making the scraper resolve constant
	# references would let both use Const; until then the literal is what keeps
	# the guard honest.
	"map_transition": Color("35e0c0"),
}


## Whether a map's ground is drawn as art rather than as bare colour.
##
## THE ONE OWNER OF THAT QUESTION, because two panes ask it and a pane that
## answered differently would colour the same map two ways -- the exact failure
## the colour table was moved into this file to prevent.
##
## `meshes` is the console's resolver, shared by every pane, and the question
## put to it is "could this key EVER produce art" rather than "has it arrived".
## Those differ for one network round trip and the difference matters both ways:
##
##   - Asking "has it arrived" makes a map come up in hashed hues and then
##     change colour a second later when the art lands. A whole island changing
##     colour after it is already on screen reads as a bug.
##   - Asking "is it configured" would keep the neutral palette on a map whose
##     art is never coming -- a failed deploy, a model tree the export forgot --
##     and there the hashed hues are the only thing left telling a bank from a
##     clearing.
##
## `may_have_art` answers false before the manifest lands and false again for a
## key that failed, so both panes fall back together and neither flickers.
##
## A null resolver answers false. The panes bind it after their own _ready, so
## there is a window where a redraw can arrive before it exists.
static func is_surfaced(z: String, meshes: MeshResolver) -> bool:
	if meshes == null:
		return false

	var asset_key := tile_model(z)

	if asset_key.is_empty():
		return false

	return meshes.may_have_art(asset_key)


## What one tile is drawn in, on a map that is or is not surfaced.
##
## Two palettes and one chooser. Callers pass the answer to [method is_surfaced]
## rather than the resolver, so an island is decided once per redraw instead of
## once per cell.
static func tile_colour(kind: String, surfaced: bool) -> Color:
	if surfaced:
		return kind_tint(kind)

	return kind_colour(kind)


## What a tile is coloured on a map whose ground is drawn as art.
##
## The same table as [method kind_colour], minus its fallback. On a bare map the
## hashed hue is the whole point -- every room kind is visually distinct with no
## edit here. On a SURFACED map it is the opposite of the point: the arbitrary
## hue assigned to "Oasis" would frame every square metre of ground in it, and
## the one thing that colour is guaranteed not to mean is anything about sand.
##
## So an authored kind keeps its colour -- a bank is worth marking on any map --
## and everything else falls to the neutral the pane already uses for a tile
## with no kind at all. In the 3D pane what is left reads as a border around the
## art; on the minimap it reads as ground, with the landmarks standing out of it
## rather than competing with a field of colour.
static func kind_tint(kind: String) -> Color:
	if ROOM_KIND_COLORS.has(kind):
		return ROOM_KIND_COLORS[kind]

	return COLOR_TILE_DEFAULT


## The asset key holding one map's terrain, or "" when it has none.
##
## Static and public for the same reason [method kind_colour] is: a pane asks
## it, and a test can ask it without booting one.
static func tile_model(z: String) -> String:
	if not TILE_MODELS.has(z):
		return ""

	return TILE_MODELS[z]


## The colour a room kind is drawn in.
##
## Static and public so the browser-parity claim above can actually be tested.
## Anything not in the table gets a stable hue, so a room type added to the game
## is visually distinct with no edit here.
static func kind_colour(kind: String) -> Color:
	if kind.is_empty():
		return COLOR_TILE_DEFAULT

	if ROOM_KIND_COLORS.has(kind):
		return ROOM_KIND_COLORS[kind]

	var hue := float(stable_hash(kind) % 360) / 360.0

	# Godot has no from_hsl, and HSV is not HSL -- feeding the browser's
	# saturation and lightness straight into from_hsv would give a different
	# colour for the same hue. This is the closed-form conversion, not a
	# match by eye.
	var value := KIND_HSL_LIGHTNESS + KIND_HSL_SATURATION * minf(
		KIND_HSL_LIGHTNESS, 1.0 - KIND_HSL_LIGHTNESS
	)

	if value <= 0.0:
		return Color.BLACK

	return Color.from_hsv(hue, 2.0 * (1.0 - KIND_HSL_LIGHTNESS / value), value)


## The browser pane's string hash, reproduced bit for bit.
##
## NOT Godot's `hash()`. Most of Blackout's room kinds are not in the colour
## table above -- "Oasis", "Oasis Outskirts", "Trade Town Sector 1" -- so this
## number is what colours most of the world, and the two panes are routinely
## put side by side on the same character. Different hashes would mean two
## differently coloured deserts and no way to tell a rendering bug from a
## rendering difference.
##
## This is JS's classic 31-multiply (`(h << 5) - h + c`) with ToInt32 applied
## every iteration, which is what `hashString` in blackout3d.js implements. The
## mask reproduces that truncation; the fold at the end reproduces JS's SIGNED
## result, which its Math.abs is applied to.
static func stable_hash(text: String) -> int:
	var value := 0

	for code: int in text.to_utf8_buffer():
		value = ((value << 5) - value + code) & 0xFFFFFFFF

	if value >= 0x80000000:
		value -= 0x100000000

	return absi(value)
