extends Node
## Builds the real console scene and checks it came up whole.
##
##     godot --headless --path godot res://tests/smoke_console.tscn
##
## The ONLY test that instantiates `console.tscn`, and it exists for one class
## of failure nothing else can see: a `%UniqueName` that resolves to null, or a
## resource the scene references that no longer loads. Every other test builds
## its subject in code, so a scene edit -- a renamed node, a dropped
## `unique_name_in_owner`, a moved theme -- is invisible to all of them and
## shows up as a client that crashes on the first frame a player sees.
##
## It is a SMOKE test, not a unit test: it asserts the shell exists, not that
## anything in it is right. The socket it opens is expected to fail; there is no
## server in a headless test run, and `_on_closed` schedules a redial that this
## scene is torn down long before.

const CONSOLE := "res://scenes/console.tscn"

## Every node the console reaches for by unique name, and what it must be.
##
## A table rather than a run of asserts so a name added to the scene is one row
## here -- and so a failure names the node instead of a line number.
const REQUIRED := {
	"Chat": "TabContainer",
	"Input": "LineEdit",
	"Inventory": "VBoxContainer",
	"Panel": "TabContainer",
	"Login": "Control",
	"Split": "HSplitContainer",
	"Right": "VSplitContainer",
	"WorldPane": "Control",
	"WorldView": "SubViewportContainer",
	"WorldVitals": "MarginContainer",
	"Minimap": "Control",
	"TextVitals": "MarginContainer",
	"World": "Node3D",
}

var _failures := 0


func _ready() -> void:
	var packed: PackedScene = load(CONSOLE)

	if packed == null:
		printerr("FAIL: %s did not load" % CONSOLE)
		get_tree().quit(1)
		return

	var console: Node = packed.instantiate()
	add_child(console)

	_every_unique_name_resolves(console)
	_the_theme_reached_the_tree(console)

	console.queue_free()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: console")
	get_tree().quit(0)


func _every_unique_name_resolves(console: Node) -> void:
	for unique_name: String in REQUIRED:
		var node: Node = console.get_node_or_null("%" + unique_name)

		if node == null:
			_fail("%%%s resolves" % unique_name)
			continue

		_expect(node.is_class(REQUIRED[unique_name]),
			"%%%s is a %s" % [unique_name, REQUIRED[unique_name]])


## The theme has to be on the ROOT, because propagation is what carries it to
## every pane built in code -- a theme assigned further down would style the
## scene's own nodes and none of the windows the console makes itself.
func _the_theme_reached_the_tree(console: Node) -> void:
	var control := console as Control

	if control == null:
		_fail("the console root is a Control")
		return

	_expect(control.theme != null, "the console root carries the theme")


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_fail(what)


func _fail(what: String) -> void:
	_failures += 1
	printerr("  FAIL %s" % what)
