extends Node
## Tests for the worn look file and its reader (DESIGN-0014 Phase W1):
## [FigureLook].
##
##     godot --headless --path godot res://tests/test_figure_look.tscn
##
## Needs nothing running and no editor. It writes no file. The cases:
##
## 1. A body text that is read and written gives the same bytes.
## 2. The writer leaves out an empty optional key, and it keeps a key that
##    this reader does not know.
## 3. The place of a part goes into its row and comes back.
## 4. A shape of a shape list becomes a shape of [MeshBuilder].
## 5. The reader refuses a file with a bad form, and a newer format.
## 6. A tier takes the parts and the fit of its base (Phase W5). Its colors
##    go over the colors of the base, and it hides each region of the base.
##    A tier of a tier reads the same way.
## 7. A tier whose base is not there, and two tiers that name each other,
##    each draw no part and give a reason. The reader refuses a tier with a
##    part of its own.
## 8. The `served` row reads with its place, and an empty one leaves the
##    file (10/17/2026). The reader refuses a bad row and a part with the
##    name of the served part. A tier keeps its own row.

const TOLERANCE := 0.0001

var _failures := 0


func _ready() -> void:
	_a_body_text_gives_the_same_bytes()
	_the_writer_leaves_out_an_empty_key()
	_a_place_goes_in_and_comes_back()
	_a_shape_becomes_a_builder_shape()
	_the_reader_refuses_a_bad_form()
	_a_tier_takes_the_parts_of_its_base()
	_a_tier_with_no_base_draws_no_part()
	_the_served_row_reads()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: figure_look")
	get_tree().quit(0)


func _expect(condition: bool, what: String) -> void:
	if not condition:
		_failures += 1
		printerr("  failed: " + what)


func _body() -> FigureLook:
	return FigureEdits.mannequin(FigureEdits.rig_from_profile("body_1"))


func _a_body_text_gives_the_same_bytes() -> void:
	var body := _body()
	var text := body.to_text()
	var again := FigureLook.from_text(text)

	_expect(body.error.is_empty(), "the body reads: " + body.error)
	_expect(body.key() == "body_1", "a body has the key of its body type")
	_expect(again.error.is_empty() and again.to_text() == text,
		"a read and a write give the same bytes: " + again.error)
	_expect(body.parts().size() > 0 and body.part_names().size() == body.parts().size(),
		"the body has parts")

	for row: Dictionary in body.parts():
		_expect(not row["region"].is_empty(), "the body part %s has a region" % row["name"])
		_expect(row.has("position") and row.has("rotation") and row.has("scale"),
			"the part %s has its place" % row["name"])

	_expect(body.part("head")["bone"] == "Head", "a part is found by its name")
	_expect(body.part("no_such_part").is_empty(), "an unknown part gives an empty row")


func _the_writer_leaves_out_an_empty_key() -> void:
	var tier := FigureLook.from_data({"format": 1, "key": "copper_helm",
		"base": "scrap_helm", "colors": {"metal": "gold"}, "hides": [], "parts": [],
		"fit": {}})
	var text := tier.to_text()

	_expect(tier.error.is_empty(), "a tier reads: " + tier.error)
	_expect(not text.contains("hides") and not text.contains("parts")
		and not text.contains("fit"), "the writer leaves out each empty key")
	_expect(tier.base() == "scrap_helm" and tier.colors()["metal"] == "gold",
		"a tier keeps its base and its colors")
	_expect(tier.hides().is_empty() and tier.parts().is_empty(),
		"an absent key reads as empty")
	_expect(FigureLook.from_text(text).to_text() == text, "a tier gives the same bytes")

	var later := FigureLook.from_data({"format": 1, "key": "helm", "parts": [
		{"name": "helm", "bone": "Head", "model": "helm_model", "node": "Helm"}]})

	_expect(later.error.is_empty() and later.part("helm")["model"] == "helm_model",
		"a key of a later phase stays in the row: " + later.error)


func _a_place_goes_in_and_comes_back() -> void:
	var row := {"name": "blade", "bone": "hand_r"}
	var basis := Basis.from_euler(Vector3(0.3, -1.1, 0.5)).scaled_local(Vector3(1.0, 2.0, 0.5))
	var place := Transform3D(basis, Vector3(0.1, -0.2, 0.3))

	_expect(FigureLook.part_transform(row).is_equal_approx(Transform3D.IDENTITY),
		"a row with no place is on its bone")
	FigureLook.set_part_transform(row, place)

	var back := FigureLook.part_transform(row)

	_expect(back.origin.distance_to(place.origin) < TOLERANCE, "the position comes back")

	for axis in 3:
		_expect(back.basis[axis].distance_to(place.basis[axis]) < TOLERANCE,
			"axis %d of the turn and the scale comes back" % axis)

	_expect(FigureJson.vector3(row["scale"]).distance_to(Vector3(1.0, 2.0, 0.5)) < TOLERANCE,
		"the row keeps the scale apart from the turn")


func _a_shape_becomes_a_builder_shape() -> void:
	var plain := FigureLook.builder_shape({"shape": FamilyShapes.SHAPE_SPHERE,
		"radius": 0.1, "offset": [0.0, 0.5, 0.0], "color": "skin"},
		{"skin": MeshPalette.CHARACTER})

	_expect(plain["offset"] == Vector3(0.0, 0.5, 0.0), "an offset becomes a vector")
	_expect(plain["color"] == MeshPalette.CHARACTER, "a color role takes its color of the look")
	_expect(plain["segments"] == FigureLook.DEFAULT_SEGMENTS
		and plain["rings"] == FigureLook.DEFAULT_RINGS[FamilyShapes.SHAPE_SPHERE],
		"a shape with no count gets the low count")

	var named := FigureLook.builder_shape({"shape": FamilyShapes.SHAPE_CYLINDER,
		"segments": 16, "rings": 3, "color": MeshPalette.STEEL}, {})

	_expect(named["segments"] == 16 and named["rings"] == 3, "a named count stays")
	_expect(named["color"] == MeshPalette.STEEL, "a role with no color of the look stays")
	_expect(not FigureLook.builder_shape({"shape": FamilyShapes.SHAPE_BOX}, {}).has("rings"),
		"a box gets no rings")

	var low := MeshBuilder.build_part(plain)
	var high := MeshBuilder.build_part({"shape": FamilyShapes.SHAPE_SPHERE, "radius": 0.1,
		"color": MeshPalette.STEEL})

	_expect((low.mesh as SphereMesh).rings == plain["rings"], "the mesh takes the rings")
	_expect((high.mesh as SphereMesh).rings == SphereMesh.new().rings,
		"a part with no rings keeps the count of Godot")
	_expect(low.mesh.get_faces().size() < high.mesh.get_faces().size(),
		"the low count gives fewer triangles")
	low.free()
	high.free()


func _the_reader_refuses_a_bad_form() -> void:
	var part := {"name": "head", "bone": "Head", "shapes": [{"shape": "sphere"}]}

	_expect(not FigureLook.from_text("[]").error.is_empty(), "a list is not a look")
	_expect(not _look({"key": "a"}).error.is_empty(), "a look needs a format")
	_expect(not _look({"format": FigureLook.FORMAT + 1, "key": "a"}).error.is_empty(),
		"a newer format does not read")
	_expect(not _look({"format": 1}).error.is_empty(), "a look needs a key")
	_expect(_look({"format": 1, "key": "a"}).error.is_empty(), "a look with no part reads")
	_expect(_look({"format": 1, "key": "a", "parts": [part]}).error.is_empty(),
		"a look with one part reads")
	_expect(not _look({"format": 1, "key": "a", "parts": [part, part]}).error.is_empty(),
		"two parts cannot share a name")
	_expect(not _look({"format": 1, "key": "a", "parts": [{"name": "head"}]}).error.is_empty(),
		"a part needs a bone")
	_expect(not _look({"format": 1, "key": "a", "hides": "hair"}).error.is_empty(),
		"hides is a list")
	_expect(not _look({"format": 1, "key": "a", "parts": [{"name": "head", "bone": "Head",
		"position": [1.0]}]}).error.is_empty(), "a position is three numbers")
	_expect(not _look({"format": 1, "key": "a", "parts": [{"name": "head", "bone": "Head",
		"shapes": [{"radius": 1.0}]}]}).error.is_empty(), "a shape needs a shape name")
	_expect(not _look({"format": 1, "key": "a", "parts": [{"name": "head", "bone": "Head",
		"shapes": [{"shape": "box", "size": 1.0}]}]}).error.is_empty(),
		"a size is three numbers")


func _look(data: Dictionary) -> FigureLook:
	return FigureLook.from_data(data)


## Three looks: a helm with one part, a tier of it, and a tier of that tier.
func _tiers() -> Dictionary:
	var helm := _look({"format": 1, "key": "rusty_helm", "hides": ["hair"],
		"colors": {"metal": "rust", "trim": "iron_dark"},
		"parts": [{"name": "dome", "bone": "Head", "shapes": [{"shape": "box",
			"color": "metal"}]}],
		"fit": {"body_2": [{"part": "dome", "scale": [0.9, 0.9, 0.9]}]}})
	var scrap := _look({"format": 1, "key": "scrap_helm", "base": "rusty_helm",
		"colors": {"metal": "iron"}})
	var copper := _look({"format": 1, "key": "copper_helm", "base": "scrap_helm",
		"colors": {"trim": "copper_dark"}, "hides": ["head"]})

	return {"rusty_helm": helm, "scrap_helm": scrap, "copper_helm": copper}


func _a_tier_takes_the_parts_of_its_base() -> void:
	var looks := _tiers()
	var helm: FigureLook = looks["rusty_helm"]
	var scrap: FigureLook = looks["scrap_helm"].resolved(looks)
	var copper: FigureLook = looks["copper_helm"].resolved(looks)

	_expect(helm.resolved(looks) == helm, "a look with no base is the look that a figure draws")
	_expect(scrap.key() == "scrap_helm" and scrap.parts() == helm.parts()
		and scrap.fit() == helm.fit(), "a tier has its own key, and the parts and the fit of its base")
	_expect(scrap.colors() == {"metal": "iron", "trim": "iron_dark"},
		"the colors of a tier go over the colors of its base")
	_expect(scrap.hides() == ["hair"], "a tier hides each region that its base hides")
	_expect(copper.parts() == helm.parts()
		and copper.colors() == {"metal": "iron", "trim": "copper_dark"}
		and copper.hides() == ["hair", "head"],
		"a tier of a tier takes each base in its order")
	_expect(copper.place_of("dome", "body_2").basis.get_scale().is_equal_approx(
		Vector3(0.9, 0.9, 0.9)), "a tier has the fit of its base on each body type")
	_expect(looks["copper_helm"].base_chain(looks).size() == 3
		and looks["copper_helm"].base_problem(looks).is_empty(),
		"the chain of a tier ends at the look with the parts")
	_expect(looks["scrap_helm"].to_text().count("\n") < helm.to_text().count("\n") / 4,
		"a tier is a small file")


func _a_tier_with_no_base_draws_no_part() -> void:
	var lost := _look({"format": 1, "key": "lost", "base": "no_such_look",
		"colors": {"metal": "gold"}})
	var first := _look({"format": 1, "key": "first", "base": "second"})
	var second := _look({"format": 1, "key": "second", "base": "first"})
	var looks := {"lost": lost, "first": first, "second": second}

	_expect(lost.error.is_empty() and lost.resolved(looks).parts().is_empty()
		and lost.resolved(looks).colors() == {"metal": "gold"},
		"a tier whose base is not there draws no part")
	_expect(lost.base_problem(looks).contains("no_such_look"),
		"the reason names the base that is not there")
	_expect(first.resolved(looks).parts().is_empty()
		and not first.base_problem(looks).is_empty()
		and not second.base_problem(looks).is_empty(),
		"two tiers that name each other draw no part, and each one gives a reason")

	var part := {"name": "dome", "bone": "Head"}

	_expect(not _look({"format": 1, "key": "a", "base": "b", "parts": [part]}).error.is_empty(),
		"a tier has no part of its own")
	_expect(not _look({"format": 1, "key": "a", "base": "b",
		"fit": {"body_2": [{"part": "dome"}]}}).error.is_empty(), "a tier has no fit of its own")
	_expect(not _look({"format": 1, "key": "a", "base": "a"}).error.is_empty(),
		"a look cannot be its own base")


func _the_served_row_reads() -> void:
	var sword := _look({"format": 1, "key": "sword",
		"served": {"bone": "hand_r", "position": [0.0, 0.2, 0.0]}})
	var empty := _look({"format": 1, "key": "sword", "served": {}})
	var tier := _look({"format": 1, "key": "copper_sword", "base": "sword",
		"served": {"bone": "hand_l"}})
	var looks := {"sword": sword, "copper_sword": tier}
	var again := FigureLook.from_text(sword.to_text())

	_expect(sword.error.is_empty() and sword.served()["bone"] == "hand_r"
		and sword.served()["scale"] == [1.0, 1.0, 1.0], "a served row reads, with its place")
	_expect(FigureLook.part_transform(sword.served()).origin.is_equal_approx(
		Vector3(0.0, 0.2, 0.0)), "the place of a served row is a part place")
	_expect(again.error.is_empty() and again.to_text() == sword.to_text(),
		"a served row gives the same bytes again")
	_expect(empty.error.is_empty() and not empty.to_text().contains("served"),
		"the writer leaves out an empty served row")
	_expect(tier.error.is_empty() and tier.resolved(looks).served()["bone"] == "hand_l",
		"a tier keeps its own served row")

	for bad: Variant in [[], {"position": [0.0, 0.0, 0.0]}, {"bone": ""},
			{"bone": "hand_r", "scale": [1.0]}]:
		_expect(not _look({"format": 1, "key": "sword", "served": bad}).error.is_empty(),
			"the reader refuses the served row %s" % [bad])

	_expect(not _look({"format": 1, "key": "sword",
		"parts": [{"name": FigureLook.SERVED_PART, "bone": "hand_r"}]}).error.is_empty(),
		"a part cannot have the name of the served part")
