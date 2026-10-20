@tool
class_name TerrainPalette
extends RefCounted
## The terrain palette: what the ground, the water, the walls, and the
## primitive props look like. One look file, `terrain_palette.json`, and
## one reader. [FloorPalette], [WallPalette], and [PropMeshBuilder] ask
## here first, and each keeps its old table as the fallback.
##
## The file holds:
##
## | Key | Holds |
## |---|---|
## | `floors` | Floor type name to the hex colour of its ground |
## | `cliff` | The hex colour of a cliff face |
## | `water` | The hex colour of the water surface |
## | `props` | Prop key to the hex colour of a primitive: `ladder`, `crate`, ... |
## | `walls` | Wall style name to `{color, height}`. The height is in height steps, 16 steps are one tile |
## | `wall_top_lighten` | How much lighter the top of a wall is than its sides |
##
## The wall height lives here and not in `blackout/world/wall_styles.py`
## since 10/13/2026. No server rule reads it: a wall blocks a step at any
## height, and sight does not read it. It is a look, so the client owns it.
##
## The Look tab of the terrain editor writes the file through the `set_*`
## routines, and the block rebuilds, so the author sees each change on the
## ground.

const PATH := LookFile.DIRECTORY + "/terrain_palette.json"

const KEY_FLOORS := "floors"
const KEY_CLIFF := "cliff"
const KEY_WATER := "water"
const KEY_PROPS := "props"
const KEY_WALLS := "walls"
const KEY_WALL_COLOR := "color"
const KEY_WALL_HEIGHT := "height"
const KEY_WALL_TOP_LIGHTEN := "wall_top_lighten"

## The props of [PropMeshBuilder] that take a colour, in the order of the
## Look tab.
const PROP_KEYS := ["ladder", "stairs", "hatch", "hatch_frame", "crate", "crate_lid",
	"table", "lamp_post", "lamp", "oil_lamp", "oil_lamp_glass", "torch", "torch_flame"]


static func data() -> Dictionary:
	return LookFile.read(PATH)


# ─── Reading ────────────────────────────────────────────────────────────────

## The hex colour of a floor type in the file, or "" for no row.
static func floor_hex(floor_name: String) -> String:
	return _hex(data().get(KEY_FLOORS, {}), floor_name)


static func cliff_hex() -> String:
	return _hex(data(), KEY_CLIFF)


static func water_hex() -> String:
	return _hex(data(), KEY_WATER)


static func prop_hex(prop: String) -> String:
	return _hex(data().get(KEY_PROPS, {}), prop)


static func wall_hex(style: String) -> String:
	return _hex(_wall_row(style), KEY_WALL_COLOR)


## The height of a wall style in height steps, or -1 for no row.
static func wall_height(style: String) -> int:
	var row := _wall_row(style)
	var height: Variant = row.get(KEY_WALL_HEIGHT, -1)

	return int(height) if typeof(height) in [TYPE_INT, TYPE_FLOAT] else -1


## How much lighter the top of a wall is, or -1.0 for no row.
static func wall_top_lighten() -> float:
	var value: Variant = data().get(KEY_WALL_TOP_LIGHTEN, -1.0)

	return float(value) if typeof(value) in [TYPE_INT, TYPE_FLOAT] else -1.0


static func _wall_row(style: String) -> Dictionary:
	var walls: Variant = data().get(KEY_WALLS, {})

	if typeof(walls) != TYPE_DICTIONARY:
		return {}

	var row: Variant = walls.get(style, {})

	return row if typeof(row) == TYPE_DICTIONARY else {}


static func _hex(table: Variant, key: String) -> String:
	if typeof(table) != TYPE_DICTIONARY:
		return ""

	var value: Variant = table.get(key, "")

	return value if typeof(value) == TYPE_STRING and Color.html_is_valid(value) else ""


# ─── Writing ────────────────────────────────────────────────────────────────

static func set_floor(floor_name: String, color: Color) -> Error:
	return _put_in(KEY_FLOORS, floor_name, LookFile.hex_of(color))


static func set_cliff(color: Color) -> Error:
	return _put(KEY_CLIFF, LookFile.hex_of(color))


static func set_water(color: Color) -> Error:
	return _put(KEY_WATER, LookFile.hex_of(color))


static func set_prop(prop: String, color: Color) -> Error:
	return _put_in(KEY_PROPS, prop, LookFile.hex_of(color))


static func set_wall(style: String, color: Color, height: int) -> Error:
	return _put_in(KEY_WALLS, style, {KEY_WALL_COLOR: LookFile.hex_of(color),
		KEY_WALL_HEIGHT: height})


static func set_wall_top_lighten(amount: float) -> Error:
	return _put(KEY_WALL_TOP_LIGHTEN, amount)


## Write the whole palette at one time. The Look tab calls it after a
## change. `floors` and `props` map a name to a Color. `walls` maps a style
## to `[Color, height]`.
static func save_palette(floors: Dictionary, cliff: Color, water: Color,
		props: Dictionary, walls: Dictionary, top_lighten: float) -> Error:
	var content := {"format": LookFile.FORMAT, KEY_FLOORS: {}, KEY_PROPS: {}, KEY_WALLS: {},
		KEY_CLIFF: LookFile.hex_of(cliff), KEY_WATER: LookFile.hex_of(water),
		KEY_WALL_TOP_LIGHTEN: top_lighten}

	for floor_name: String in floors:
		content[KEY_FLOORS][floor_name] = LookFile.hex_of(floors[floor_name])

	for prop: String in props:
		content[KEY_PROPS][prop] = LookFile.hex_of(props[prop])

	for style: String in walls:
		content[KEY_WALLS][style] = {KEY_WALL_COLOR: LookFile.hex_of(walls[style][0]),
			KEY_WALL_HEIGHT: int(walls[style][1])}

	return LookFile.write(PATH, content)


## Take every row out of the file. Each reader then draws its old table.
static func reset() -> Error:
	return LookFile.write(PATH, {"format": LookFile.FORMAT})


static func _put(key: String, value: Variant) -> Error:
	var content := data().duplicate(true)

	content["format"] = LookFile.FORMAT
	content[key] = value

	return LookFile.write(PATH, content)


static func _put_in(table_key: String, key: String, value: Variant) -> Error:
	var content := data().duplicate(true)
	var table: Variant = content.get(table_key, {})

	if typeof(table) != TYPE_DICTIONARY:
		table = {}

	table[key] = value
	content["format"] = LookFile.FORMAT
	content[table_key] = table

	return LookFile.write(PATH, content)
