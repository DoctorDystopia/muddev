@tool
class_name FigureLookEdits
extends RefCounted
## The rules of a worn look as a whole (DESIGN-0014): the mannequin, the
## slot shape, a look from another look, the copy, the hide list, the
## colors of a look, the kit parts, and the tiers.
##
## Each routine changes the content of one look file. The content is the
## dictionary of the `data` member of [FigureLook]. The caller gives a
## copy, and the routine changes the copy. A routine that can refuse
## returns the reason, or "". Nothing here needs the editor.
##
## ## A new body
##
## [method mannequin] makes a shape list body for a rig, from the part rows
## of [constant FigureShapes.BODY]. Each shape is a prism: a tapered block
## with flat faces. Each limb part reaches into the part before it, so a
## bent joint shows no gap. This is the one art rule of rigid parts
## (DESIGN-0014 section 8.3). The body has its default clothes as color
## roles.
##
## ## A new slot shape, and a new look
##
## [method slot_shape] makes the slot shape of one slot for a rig, from
## [constant FigureShapes.SLOTS]. The Gear tab makes one for each slot, and
## the author then changes it. [method look_from] makes the look of an item
## from the slot shape of its slot, so a new look starts from what the
## figure shows (requirement A6).
##
## The body and each slot shape are a start. The author changes each shape
## in the Body tab or the Gear tab, and a look file keeps that change.
##
## ## The hide list, a tier, and a kit part
##
## [method set_hide] puts a region in the hide list of a look, or takes it
## out. [method make_tier] gives a look a base: the look then takes the
## parts of that base, and it keeps only its own colors
## ([method FigureLook.resolved]). [method new_kit_part] makes a kit part:
## a hair shape, a head, a beard.

## The color role of the skin of a body. [constant FigureShapes.BODY_COLORS]
## gives each role of a new body its color.
const SKIN_ROLE := FigureShapes.ROLE_SKIN

## The color roles of gear (DESIGN-0014 section 8.5). [FigureShapes] owns
## them, with the color that a new look gives each one.
const ROLE_METAL := FigureShapes.ROLE_METAL
const ROLE_TRIM := FigureShapes.ROLE_TRIM
const ROLE_CLOTH := FigureShapes.ROLE_CLOTH
const ROLE_LEATHER := FigureShapes.ROLE_LEATHER

## The name of the one part of a slot shape of a held or a hung item.
const ITEM_PART := "item"

## The keys of a look that [method copy_look] takes from another look.
const COPIED_KEYS := ["parts", "colors", "hides", "fit"]


# ─── A new body ─────────────────────────────────────────────────────────────

## The shape list body of a rig: one part for each part row of
## [constant FigureShapes.BODY] whose bone the rig has. `girth` scales the
## width and the depth of each shape.
static func mannequin(rig: FigureRig, girth := 1.0) -> FigureLook:
	var parts := FigureShapes.parts_for(rig, FigureShapes.BODY, girth)

	return FigureLook.from_data({
		"format": FigureLook.FORMAT,
		"key": rig.key(),
		"colors": FigureShapes.colors_for(parts, FigureShapes.BODY_COLORS),
		"parts": parts,
	})


# ─── The Gear tab ───────────────────────────────────────────────────────────

## The slot shape of one slot for a rig: the worn look that draws for each
## item of that slot with no worn look (decision 7). Its key is the slot.
##
## A slot of [constant FigureShapes.SLOTS] gets the parts of its part rows.
## A slot of [constant FigureShapes.SLOT_HIDES] hides the regions that its
## parts take the place of. Each other slot gets one plain box on its
## default bone, so a new slot of the server shows before anyone gives it a
## shape.
static func slot_shape(rig: FigureRig, slot: String) -> FigureLook:
	var parts := []
	var bone: String = rig.slots().get(slot, "")

	if FigureShapes.SLOTS.has(slot):
		parts = FigureShapes.parts_for(rig, FigureShapes.SLOTS[slot])
	elif rig.has_bone(bone):
		parts.append({"name": ITEM_PART, "bone": bone,
			"shapes": [FigureShapeEdits.new_shape(FamilyShapes.SHAPE_BOX)]})

	return FigureLook.from_data({
		"format": FigureLook.FORMAT,
		"key": slot,
		"hides": FigureShapes.SLOT_HIDES.get(slot, []).duplicate(),
		"colors": FigureShapes.colors_for(parts, FigureShapes.GEAR_COLORS,
			FigureShapes.SLOT_COLORS.get(slot, {})),
		"parts": parts,
	})


## The content of a new worn look with the key `key`: the parts, the colors,
## and the hide list of `source`. A new look of an item starts from the slot
## shape of its slot (requirement A6).
static func look_from(key: String, source: FigureLook) -> Dictionary:
	var data := {"format": FigureLook.FORMAT, "key": key}

	copy_look(data, source.data)

	return data


## Give a look the parts, the colors, and the hide list of another look
## (requirement A7). The look keeps its key. A tier becomes a look with
## parts of its own, so it loses its base.
static func copy_look(look: Dictionary, source: Dictionary) -> String:
	if source.get("parts", []).is_empty():
		return "The look %s has no part to copy." % source.get("key", "")

	look.erase("base")

	for copied_key: String in COPIED_KEYS:
		look.erase(copied_key)

		if source.has(copied_key):
			look[copied_key] = source[copied_key].duplicate(true)

	return ""


## Put a region in the hide list of a look, or take it out. The parts of
## each other look in that region then do not draw.
static func set_hide(look: Dictionary, region: String, hidden: bool) -> String:
	if region.is_empty():
		return "Select a region first."

	var hides: Array = look.get("hides", []).duplicate()

	hides.erase(region)

	if hidden:
		hides.append(region)

	hides.sort()
	look["hides"] = hides

	# The writer leaves out an empty hide list, so the content has no key.
	if hides.is_empty():
		look.erase("hides")

	return ""


## Give a color role of a look its color: a named color of `palette`, or a
## color of [MeshPalette]. A role that the look does not have joins its
## color table. On a tier, the color goes over the color of the base.
static func set_color(look: Dictionary, role: String, color: String,
		palette: FigurePalette = null) -> String:
	var problem := FigureRigEdits.name_problem(role)
	var known := MeshPalette.COLORS.has(color) \
		or (palette != null and palette.has_color(color))

	if not problem.is_empty():
		return problem

	if not known:
		return "The palette has no color %s." % color

	if not look.has("colors"):
		look["colors"] = {}

	look["colors"][role] = color

	return ""


## Take a color role out of the color table of a look. The role then has
## the color that `palette` gives it, on each shape that names it.
##
## A role that a shape names stays when the palette has no color for it.
## The shape would draw in the loud color of a missing name.
static func remove_color(look: Dictionary, role: String,
		palette: FigurePalette = null) -> String:
	if not look.get("colors", {}).has(role):
		return "The look has no color role %s." % role

	var from_palette := palette != null \
		and (palette.roles().has(role) or palette.has_color(role))

	for part: Dictionary in look.get("parts", []):
		for shape: Dictionary in part.get("shapes", []):
			if shape.get("color", "") == role and not from_palette:
				return "A shape of the part %s has the color role %s, " % [part["name"], role] \
					+ "and the palette has no color for that role. Give the role a " \
					+ "color on the Colors tab, or give the shape another color."

	look["colors"].erase(role)

	return ""


## Each color role that a look can give a color to, in sorted order: the
## roles of its color table, the role of each shape, and the name of each
## surface of each part with a model. `models` gives the surfaces, or null.
##
## A name of a shape that is a named color of `palette`, and no role, is
## not in the list.
static func roles_of_look(look: FigureLook, models: FigureModels = null,
		palette: FigurePalette = null) -> PackedStringArray:
	var found := {}

	for role: String in look.colors():
		found[role] = true

	for row: Dictionary in look.parts():
		for shape: Dictionary in row.get("shapes", []):
			found[shape.get("color", MeshPalette.GENERIC)] = true

		if models != null and row.has("model"):
			for surface: String in models.material_names(row["model"], row.get("node", "")):
				found[surface] = true

	var roles := PackedStringArray()
	var plain := RegEx.create_from_string(FigureRigEdits.NAME_PATTERN)

	for role: String in found:
		var is_color := not look.colors().has(role) and palette != null \
			and palette.has_color(role) and not palette.roles().has(role)

		if plain.search(role) != null and not is_color:
			roles.append(role)

	roles.sort()

	return roles


# ─── The Body tab: a kit part ───────────────────────────────────────────────

## The content of a new kit part: a worn look with the key `key` in the kit
## group `group`, with one prism on `bone`. [method kit_problem] gives the
## reason for a refusal.
##
## The kit part hides the region of its bone. A hair shape on the head top
## thus takes the place of the hair of the body. The author changes the
## hide list after.
##
## A role of `palette` can have the name of the group. The prism then has
## that color role, so a hair shape starts in the hair color.
static func new_kit_part(key: String, group: String, rig: FigureRig, bone: String,
		palette: FigurePalette = null) -> Dictionary:
	var data := {"format": FigureLook.FORMAT, "key": key, "kit": group}

	FigurePartEdits.add_part(data, rig, bone)

	if palette != null and palette.roles().has(group):
		data["parts"][0]["shapes"][0]["color"] = group

	if not rig.region_of(bone).is_empty():
		set_hide(data, rig.region_of(bone), true)

	return data


## Why a new kit part cannot have the key `key` in the kit group `group`,
## or "". `taken` names each key that another file or an item has.
static func kit_problem(key: String, group: String, rig: FigureRig, bone: String,
		taken: PackedStringArray) -> String:
	var problem := FigureRigEdits.name_problem(key)

	if problem.is_empty():
		problem = FigureRigEdits.name_problem(group)

	if not problem.is_empty():
		return problem

	if key in taken:
		return "The key %s names a look, an item, a slot, or a body type." % key

	if rig == null or not rig.has_bone(bone):
		return "Select the bone of the first part of the kit part."

	return ""


## Put a look in a kit group, or take it out for "".
static func set_kit(look: Dictionary, group: String) -> String:
	if group.is_empty():
		look.erase("kit")
		return ""

	var problem := FigureRigEdits.name_problem(group)

	if problem.is_empty():
		look["kit"] = group

	return problem


# ─── The Gear tab: a tier ───────────────────────────────────────────────────

## Make a look a tier of another look: it then takes the parts and the fit
## of `base_key`. `looks` is key -> [FigureLook], for each look of the
## store.
##
## The look loses its own parts and its fit. It keeps each color that
## differs from the color of the base, and each hidden region that the base
## does not hide. A new tier of an item is thus a file of three lines.
static func make_tier(look: Dictionary, base_key: String, looks: Dictionary) -> String:
	var key: String = look.get("key", "")

	if base_key == key:
		return "A look cannot be its own base."

	if not looks.has(base_key):
		return "No look has the key %s." % base_key

	var base_look: FigureLook = looks[base_key]

	for above: FigureLook in base_look.base_chain(looks):
		if above.key() == key:
			return "The look %s takes its parts from %s. Two looks cannot name each other." \
				% [base_key, key]

	if not base_look.base_problem(looks).is_empty():
		return "The look %s has no parts to give: %s." % [base_key,
			base_look.base_problem(looks)]

	var based := base_look.resolved(looks)
	var colors := {}
	var hides := []

	for role: String in look.get("colors", {}):
		if based.colors().get(role, "") != look["colors"][role]:
			colors[role] = look["colors"][role]

	for region: String in look.get("hides", []):
		if not region in based.hides():
			hides.append(region)

	for own_key: String in ["parts", "fit", "colors", "hides"]:
		look.erase(own_key)

	look["base"] = base_key

	if not colors.is_empty():
		look["colors"] = colors

	if not hides.is_empty():
		look["hides"] = hides

	return ""


## The key of each look that has `key` as its base, in sorted order.
static func tiers_of(looks: Dictionary, key: String) -> PackedStringArray:
	var found := PackedStringArray()

	for look_key: String in looks:
		if looks[look_key].base() == key:
			found.append(look_key)

	found.sort()

	return found
