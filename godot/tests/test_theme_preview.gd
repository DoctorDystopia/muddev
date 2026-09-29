extends Node
## Unit tests for ThemePreview, the scene preview of the Theme editor.
##
##     godot --headless --path godot res://tests/test_theme_preview.tscn
##
## Needs nothing running.
##
## The picker of the Theme editor selects the theme type of the control under
## the mouse: the `theme_type_variation` if one is set, else the class. So each
## type that a part owns must have a control with exactly that theme type. A
## type with no control is a type that the picker cannot reach.

const BLACKOUT_SCENE := "res://ui/theme_preview/blackout.tscn"
const GODOT_SCENE := "res://ui/theme_preview/godot.tscn"
const PROBE_TYPE := "PreviewProbe"
const PROBE_BASE := "Label"

var _failures := 0


func _ready() -> void:
	var theme: Theme = load(ThemePreview.THEME_PATH)
	var blackout: ThemePreview = _open(BLACKOUT_SCENE)
	var godot: ThemePreview = _open(GODOT_SCENE)

	_each_part_accounts_for_every_type_it_owns(blackout, theme.get_type_list())
	_each_part_accounts_for_every_type_it_owns(godot, _default_only(theme))
	_every_shown_type_has_a_control_the_picker_can_reach(blackout)
	_every_shown_type_has_a_control_the_picker_can_reach(godot)
	_a_window_type_is_named_and_never_shown(blackout, godot)
	_a_save_keeps_no_sample()
	await _a_new_variation_gets_a_sample(blackout, theme)

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: theme_preview")
	get_tree().quit(0)


func _open(path: String) -> ThemePreview:
	var packed: PackedScene = load(path)
	var preview: ThemePreview = packed.instantiate()
	add_child(preview)

	return preview


## The types of the default theme that the Blackout theme does not set.
func _default_only(theme: Theme) -> PackedStringArray:
	var owned := PackedStringArray()
	var blackout := theme.get_type_list()

	for type_name: String in ThemeDB.get_default_theme().get_type_list():
		if not blackout.has(type_name):
			owned.append(type_name)

	return owned


## Each owned type is shown or named as not shown. Nothing is lost between them.
func _each_part_accounts_for_every_type_it_owns(preview: ThemePreview,
		owned: PackedStringArray) -> void:
	var shown := preview.shown_types()
	var hidden := preview.hidden_types()

	for type_name: String in owned:
		_expect(shown.has(type_name) != hidden.has(type_name),
			"%s part: %s is shown or named, once" % [preview.part, type_name])


func _every_shown_type_has_a_control_the_picker_can_reach(
		preview: ThemePreview) -> void:
	var reached := {}
	_collect_types(preview, reached)

	for type_name: String in preview.shown_types():
		_expect(reached.has(type_name),
			"%s part: the picker reaches %s" % [preview.part, type_name])


func _a_window_type_is_named_and_never_shown(blackout: ThemePreview,
		godot: ThemePreview) -> void:
	_expect(blackout.hidden_types().has("PopupMenu"),
		"PopupMenu is a Window, so the Blackout part names it")
	_expect(not blackout.shown_types().has("PopupMenu"),
		"and does not try to show it")
	_expect(godot.hidden_types().has("PopupPanel"),
		"PopupPanel is a Window, so the Godot part names it")


## The samples have no owner. A save of the scene in the editor must keep
## the root and its settings only.
func _a_save_keeps_no_sample() -> void:
	var preview: ThemePreview = _open(GODOT_SCENE)
	var packed := PackedScene.new()
	packed.pack(preview)

	_expect(preview.get_child_count() > 0, "the preview built its samples")
	_expect(packed.get_state().get_node_count() == 1,
		"and a save keeps only the root")

	preview.queue_free()


func _a_new_variation_gets_a_sample(preview: ThemePreview, theme: Theme) -> void:
	theme.set_type_variation(PROBE_TYPE, PROBE_BASE)
	await get_tree().process_frame

	var reached := {}
	_collect_types(preview, reached)
	_expect(reached.has(PROBE_TYPE), "a variation added to the theme gets a sample")

	theme.remove_type(PROBE_TYPE)


## The theme type that the picker selects for each control under `node`.
func _collect_types(node: Node, into: Dictionary) -> void:
	for child: Node in node.get_children():
		var control := child as Control

		if control != null:
			var variation := String(control.theme_type_variation)
			into[control.get_class() if variation.is_empty() else variation] = true

		_collect_types(child, into)


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
