class_name FigureOutfit
extends RefCounted
## The worn looks of one figure: the body, then one worn look for each item
## of a worn record (DESIGN-0014 section 8.2, step 3).
##
## A worn record is the map from slot to asset key that the server sends for
## one character. [method looks_for] gives the list that [FigureBuilder]
## builds. The game and the figure workbench use this class (requirement
## D6), so the author sees the fallback that a player sees.
##
## ## Three sources, in this order
##
## 1. **The worn look of the item**: the look with the asset key as its key.
## 2. **The slot shape**: the look with the slot as its key. It draws for
##    each item of that slot with no worn look (decision 7).
## 3. **The family shape**: the shape of [FamilyShapes] for the family of the
##    item, on the default bone of the slot. It draws only when no slot shape
##    exists, so a new slot on the server still shows.
##
## A slot whose rig has no default bone, with no look and no slot shape,
## draws nothing. That does not stop the figure (requirement D7).
##
## ## One look, one time
##
## A figure names each part by its look key and its part name. Thus, a look
## that two slots resolve to goes into the list one time.
##
## ## The kit of a character
##
## A kit part is a worn look with a kit group: one hair shape, one head, one
## beard. A character has one choice for each kit group, or none.
## [method looks_for] puts each chosen kit part after the body.
##
## A kit part can take the place of a part of the body. It then hides the
## region of that part, as a great helm hides the hair.
##
## ## A tier (Phase W5)
##
## A look with a `base` takes the parts of that look. Each look of the list
## is the look that a figure draws ([method FigureLook.resolved]), so the
## builder needs no rule for a tier.

## What draws for one item. See the three sources above.
const SOURCE_LOOK := "look"
const SOURCE_SLOT_SHAPE := "slot_shape"
const SOURCE_FAMILY := "family"
const SOURCE_NOTHING := ""

## The key of a family shape look is this prefix and the slot. No figure
## file has such a key: rule C1 of the checks refuses it.
const FAMILY_KEY_PREFIX := "family_shape__"

const FAMILY_PART := "shape"

## A family shape is about one unit across. A figure is about 1.7 units
## high, so a family shape draws at this part of its size on a figure.
const FAMILY_SCALE := 0.35


## The looks of one figure, in the order that [FigureBuilder] takes: the
## body of the rig first, then one look for each slot of `worn`, in the
## sorted order of the slots.
##
## - `looks` is key -> [FigureLook].
## - `families` is asset key -> family, for the family shape of an item.
## - `kit` is the kit of the character: kit group -> the key of a kit part.
##   The kit parts come after the body, in the sorted order of the groups.
static func looks_for(rig: FigureRig, worn: Dictionary, looks: Dictionary,
		families := {}, kit := {}) -> Array:
	var found := []
	var taken := {}
	var slots := worn.keys()

	if looks.has(rig.key()):
		found.append(looks[rig.key()].resolved(looks))
		taken[rig.key()] = true

	for look: FigureLook in kit_looks(kit, looks):
		if not taken.has(look.key()):
			found.append(look)
			taken[look.key()] = true

	slots.sort()

	for slot: String in slots:
		var look := look_of(rig, slot, worn[slot], looks, families)

		if look != null and not taken.has(look.key()):
			found.append(look)
			taken[look.key()] = true

	return found


## The kit parts of one character, as the looks that a figure draws. `kit`
## is kit group -> the key of a kit part. A key that names no look, or a
## look of another kit group, draws nothing (requirement D7).
static func kit_looks(kit: Dictionary, looks: Dictionary) -> Array:
	var found := []
	var groups := kit.keys()

	groups.sort()

	for group: Variant in groups:
		var look: FigureLook = looks.get(kit[group])

		if look != null and look.kit() == str(group):
			found.append(look.resolved(looks))

	return found


## Kit group -> the keys of its kit parts, in sorted order. `looks` is
## key -> [FigureLook]. The kit groups are the groups that a look names.
static func kit_groups(looks: Dictionary) -> Dictionary:
	var groups := {}
	var keys := looks.keys()

	keys.sort()

	for key: String in keys:
		var group: String = looks[key].kit()

		if group.is_empty():
			continue

		if not groups.has(group):
			groups[group] = PackedStringArray()

		groups[group].append(key)

	return groups


## The look that draws for one item in one slot, or null for nothing.
static func look_of(rig: FigureRig, slot: String, asset_key: String, looks: Dictionary,
		families := {}) -> FigureLook:
	match source_of(rig, slot, asset_key, looks):
		SOURCE_LOOK:
			return looks[asset_key].resolved(looks)
		SOURCE_SLOT_SHAPE:
			return looks[slot].resolved(looks)
		SOURCE_FAMILY:
			return family_look(rig, slot, families.get(asset_key, ""))

	return null


## Which of the three sources draws for one item in one slot: a SOURCE_*
## constant.
static func source_of(rig: FigureRig, slot: String, asset_key: String,
		looks: Dictionary) -> String:
	if asset_key.is_empty():
		return SOURCE_NOTHING

	if looks.has(asset_key):
		return SOURCE_LOOK

	if looks.has(slot):
		return SOURCE_SLOT_SHAPE

	if rig.has_bone(rig.slots().get(slot, "")):
		return SOURCE_FAMILY

	return SOURCE_NOTHING


## The family shape of one slot as a worn look: one part on the default bone
## of the slot. An unknown family gets the generic shape.
static func family_look(rig: FigureRig, slot: String, family: String) -> FigureLook:
	var shapes := []

	for part: Dictionary in FamilyShapes.parts_for(family):
		shapes.append(_file_shape(part))

	return FigureLook.from_data({
		"format": FigureLook.FORMAT,
		"key": FAMILY_KEY_PREFIX + slot,
		"parts": [{
			"name": FAMILY_PART,
			"bone": rig.slots().get(slot, ""),
			"scale": [FAMILY_SCALE, FAMILY_SCALE, FAMILY_SCALE],
			"shapes": shapes,
		}],
	})


## One shape of [FamilyShapes] as a figure file holds it: each vector is an
## `[x, y, z]` array.
static func _file_shape(part: Dictionary) -> Dictionary:
	var out := {}

	for field: String in part:
		if part[field] is Vector3:
			out[field] = FigureJson.from_vector3(part[field])
		else:
			out[field] = part[field]

	return out
