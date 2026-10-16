extends SceneTree
## One-time helper of DESIGN-0014 section 16: give the figure files of the
## repository the low-poly look. Run with
## `--headless --path godot -s <this file>`.
##
## It does three things, through the rules of the workbench:
##
## 1. It gives each arm bone of each rig the distance of
##    `FigureEdits.ARM_PLACES`, times the limb scale of that rig. It
##    changes no other bone.
## 2. It writes the body of each rig again from `FigureEdits.mannequin`.
## 3. It writes each slot shape again from `FigureEdits.slot_shape`, on the
##    first rig.
##
## Steps 2 and 3 drop each change that the author made to those looks. A
## look of an item stays as it is.

## The hips height of the humanoid profile. The limb scale of a rig is its
## hips height over this number.
const PROFILE_HIPS := 0.75

## The girth of the body of each rig. A rig that is not here gets 1.0.
const GIRTHS := {"body_2": 0.9}


func _init() -> void:
	var store := FigureStore.new(FigureStore.repo_directory())
	var catalog := FigureCatalog.read_file()

	store.load_all()

	var rig_keys := store.keys_of(FigureStore.KIND_RIG)

	for key: String in rig_keys:
		var data := _with_arm_places(store.rigs[key])

		print("rig ", key, " ", store.put(FigureStore.KIND_RIG, key, data))

	for key: String in rig_keys:
		var body := FigureEdits.mannequin(store.rigs[key], GIRTHS.get(key, 1.0))

		print("body ", key, " ", store.put(FigureStore.KIND_LOOK, key, body.data))

	for slot: String in catalog.slot_keys():
		print("slot ", slot, " ", store.put(FigureStore.KIND_LOOK, slot,
			FigureEdits.slot_shape(store.rigs[rig_keys[0]], slot).data))

	print("saved ", store.save(), " errors ", store.errors)
	quit()


## The content of a rig with each arm bone at its new distance.
func _with_arm_places(rig: FigureRig) -> Dictionary:
	var data: Dictionary = rig.data.duplicate(true)
	var limb_scale: float = rig.global_rest_of(FigureEdits.HIPS).origin.y / PROFILE_HIPS

	for row: Dictionary in data["bones"]:
		for ending: String in FigureEdits.ARM_PLACES:
			if str(row["name"]).ends_with(ending) and not rig.is_socket(row["name"]):
				var place := FigureJson.vector3(row["position"]).normalized()

				row["position"] = FigureJson.from_vector3(
					place * FigureEdits.ARM_PLACES[ending] * limb_scale)

	return data
