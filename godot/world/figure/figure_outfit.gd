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
## ## Four sources, in this order
##
## 1. **The served model of the item** (Nick, 10/17/2026). It is the model
##    with the asset key as its key, and it must be in hand. It draws as
##    one part ([constant FigureLook.SERVED_PART]): the whole model in its
##    unit box. A look whose parts name that model is a figure model. That
##    look draws as it is.
## 2. **The worn look of the item**: the look with the asset key as its key.
##    A look with no part and no base gives nothing here: it holds only the
##    place of a served model.
## 3. **The slot shape**: the look with the slot as its key. It draws for
##    each item of that slot with no worn look (decision 7).
## 4. **The family shape**: the shape of [FamilyShapes] for the family of the
##    item, on the default bone of the slot. It draws only when no slot shape
##    exists, so a new slot on the server still shows.
##
## A slot whose rig has no default bone, with no look and no slot shape,
## draws nothing. That does not stop the figure (requirement D7).
##
## ## The place of a served model
##
## Sources 2 to 4 are the stand-in of a served model. The stand-in draws
## while the model is not in hand. It also gives the model its first
## place, in the box of the stand-in. The longest side of the model takes
## the longest side of the box. The middle of the model takes the middle of
## the box. A moved model keeps its place in the `served` row of the look
## of the item ([method FigureLook.served]). The served part takes the hide
## list and the colors of the look of the item and of the stand-in.
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

## What draws for one item. See the four sources above.
const SOURCE_MODEL := "model"
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
## - `models` gives the served model of each item. With no `models`, no
##   served model draws.
static func looks_for(rig: FigureRig, worn: Dictionary, looks: Dictionary,
		families := {}, kit := {}, models: FigureModels = null) -> Array:
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
		var look := look_of(rig, slot, worn[slot], looks, families, models)

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


## The look that draws for one item in one slot, or null for nothing. With
## no `models`, the answer is the stand-in of a served model.
static func look_of(rig: FigureRig, slot: String, asset_key: String, looks: Dictionary,
		families := {}, models: FigureModels = null) -> FigureLook:
	match source_of(rig, slot, asset_key, looks, models):
		SOURCE_MODEL:
			return served_look(rig, slot, asset_key, looks, families, models)
		SOURCE_LOOK:
			return looks[asset_key].resolved(looks)
		SOURCE_SLOT_SHAPE:
			return looks[slot].resolved(looks)
		SOURCE_FAMILY:
			return family_look(rig, slot, families.get(asset_key, ""))

	return null


## Which of the four sources draws for one item in one slot: a SOURCE_*
## constant. With no `models`, no served model draws.
static func source_of(rig: FigureRig, slot: String, asset_key: String,
		looks: Dictionary, models: FigureModels = null) -> String:
	if asset_key.is_empty():
		return SOURCE_NOTHING

	if serves_model(rig, slot, asset_key, looks, models):
		return SOURCE_MODEL

	if _has_parts(looks.get(asset_key)):
		return SOURCE_LOOK

	if looks.has(slot):
		return SOURCE_SLOT_SHAPE

	if rig.has_bone(rig.slots().get(slot, "")):
		return SOURCE_FAMILY

	return SOURCE_NOTHING


## True when the served model of the asset key draws in place of its look.
## The model must be in hand, and a bone must hold it. No part of the look
## of the item can name it.
static func serves_model(rig: FigureRig, slot: String, asset_key: String, looks: Dictionary,
		models: FigureModels) -> bool:
	if models == null or not models.has(asset_key):
		return false

	var own: FigureLook = looks.get(asset_key)

	if own != null and asset_key in own.resolved(looks).model_keys():
		return false

	return not served_bone(rig, slot, asset_key, looks).is_empty()


## The bone of the served model of one item, or "" for no bone. The order:
## the bone of its `served` row, the default bone of the slot, and the
## first bone of the stand-in. Each one counts only when the rig has it.
static func served_bone(rig: FigureRig, slot: String, asset_key: String,
		looks: Dictionary) -> String:
	var own: FigureLook = looks.get(asset_key)
	var placed: String = "" if own == null else own.served().get("bone", "")
	var stand_in := look_of(rig, slot, asset_key, looks)
	var bones := [placed, rig.slots().get(slot, "")]

	if stand_in != null:
		for row: Dictionary in stand_in.parts():
			bones.append(row["bone"])

	for bone: String in bones:
		if rig.has_bone(bone):
			return bone

	return ""


## The look that draws the served model of one item. Its one part holds the
## whole model ([constant FigureModels.WHOLE_MODEL]), on the bone of
## [method served_bone]. It is not a look file. This routine sets
## [member FigureLook.data] with no check, as [method FigureLook.resolved]
## does.
static func served_look(rig: FigureRig, slot: String, asset_key: String, looks: Dictionary,
		families: Dictionary, models: FigureModels) -> FigureLook:
	var stand_in := look_of(rig, slot, asset_key, looks, families)
	var own: FigureLook = looks.get(asset_key)
	var placed: Dictionary = {} if own == null else own.served()
	var bone := served_bone(rig, slot, asset_key, looks)
	var row := {"name": FigureLook.SERVED_PART, "bone": bone, "region": "",
		"model": asset_key, "node": FigureModels.WHOLE_MODEL}

	if placed.get("bone", "") == bone:
		for place_key: String in FigureLook.PLACE_KEYS:
			if placed.has(place_key):
				row[place_key] = placed[place_key]
	else:
		FigureLook.set_part_transform(row, fit_place(rig, bone, stand_in, models))

	var look := FigureLook.new()

	look.data = {"format": FigureLook.FORMAT, "key": asset_key, "parts": [row]}
	_take_hides_and_colors(look.data, [stand_in, null if own == null else own.resolved(looks)])

	return look


## The place of a served model on `bone`: the box of the stand-in, in the
## space of the bone. The longest side of the model takes the longest side
## of the box. The middle of the model takes the middle of the box. With
## no box, the model stands on the bone at the size of a family shape.
static func fit_place(rig: FigureRig, bone: String, stand_in: FigureLook,
		models: FigureModels = null) -> Transform3D:
	var box := _box_on_bone(rig, bone, stand_in, models)
	var longest := maxf(box.size.x, maxf(box.size.y, box.size.z))

	if longest <= 0.0:
		return Transform3D(Basis.from_scale(Vector3.ONE * FAMILY_SCALE), Vector3.ZERO)

	return Transform3D(Basis.from_scale(Vector3.ONE * longest), box.get_center())


## The box of the parts of a look, in the space of one bone of the rest
## pose. An empty box for no look, or for a look that draws nothing.
static func _box_on_bone(rig: FigureRig, bone: String, look: FigureLook,
		models: FigureModels) -> AABB:
	if look == null:
		return AABB()

	var item := FigureBuilder.build_item(rig, look, models)
	var box := ModelLoader.bounds_of(item)
	var frame := FigureBuilder.item_frame(rig, look)

	item.free()

	return rig.global_rest_of(bone).affine_inverse() * frame.affine_inverse() * box


## Give the data of a served look the hidden regions and the colors of
## each look of `sources`. A later look wins a color. A null look gives
## nothing.
static func _take_hides_and_colors(data: Dictionary, sources: Array) -> void:
	var hidden := {}
	var colors := {}

	for source: Variant in sources:
		if source == null:
			continue

		colors.merge((source as FigureLook).colors(), true)

		for region: String in (source as FigureLook).hides():
			hidden[region] = true

	if not colors.is_empty():
		data["colors"] = colors

	if not hidden.is_empty():
		data["hides"] = hidden.keys()
		data["hides"].sort()


## True for a look that draws parts: it has parts, or a base that gives
## them. A null look, or a look with only a `served` row, has none.
static func _has_parts(look: FigureLook) -> bool:
	return look != null and (not look.parts().is_empty() or not look.base().is_empty())


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
