extends Node
## Tests for the right-click menu over the world pane.
##
##     godot --headless --path godot res://tests/test_choose_option.tscn
##
## Two things are checked, and they are the two that go silently wrong.
##
## WHICH COMMAND IS SENT. Every row must emit the server's string byte for
## byte. A menu that rebuilds a command from a verb and a name is a client verb
## table wearing a different hat, and this repo has deleted two of those for
## being wrong within a week of being written. Cancel must emit nothing at all,
## which is a separate claim: a Cancel that emitted its own row's text would
## send the literal word "Cancel" at the parser.
##
## WHICH OPTIONS EXIST. [method WorldView.options_for] reads `actions` when the
## server sent one and falls back to `interact` when it did not -- and the
## fallback is the COMMON path, because the server omits `actions` for the
## one-verb case, which is nearly every entity in the world.
##
## What the box LOOKS like is not tested. Where it opens is, because a menu
## that opens off-screen is a menu with no options at all.

const Menu := preload("res://scenes/world/choose_option.gd")

## A corpse as the server serialises one: two verbs, so `actions` is present.
const CORPSE := {
	"id": 40470.0, "name": "Mutant Raider corpse", "kind": "corpse",
	"asset": "mutant_raider", "family": "corpse",
	"interact": "butcher Mutant Raider corpse",
	"actions": [
		{"command": "butcher Mutant Raider corpse", "label": "Butcher"},
		{"command": "get Mutant Raider corpse", "label": "Get"},
	],
	"coords": [5.0, 3.0, "oasis_outskirts"],
}

## A raider as the server serialises one: ONE verb, so no `actions` key at all.
## This is the shape almost every entity has.
const RAIDER := {
	"id": 40469.0, "name": "Mutant Raider", "kind": "npc",
	"asset": "mutant_raider", "family": "npc",
	"interact": "attack Mutant Raider",
	"coords": [5.0, 3.0, "oasis_outskirts"],
}

## Another player: drawn, but affords nothing. Opening combat on one by misclick
## is the thing TARGETED_VERB_BY_KIND deliberately does not allow.
const STRANGER := {
	"id": 40471.0, "name": "someone", "kind": "character",
	"asset": "player_character", "family": "generic", "interact": "",
	"coords": [5.0, 3.0, "oasis_outskirts"],
}

## How big the pretend world pane is, for the placement cases.
const PANE := Vector2(880.0, 700.0)

var _failures := 0
var _sent: Array[String] = []
var _dismissals := 0



func _ready() -> void:
	_a_corpse_offers_every_verb_the_server_listed()
	_an_entity_with_one_verb_falls_back_to_interact()
	_an_entity_that_affords_nothing_offers_nothing()
	_a_repeated_command_is_listed_once()
	_a_malformed_action_is_skipped()

	_rows_read_as_verb_then_target()
	_a_row_with_no_target_is_the_verb_alone()
	_a_label_the_server_omitted_falls_back_to_the_command()

	_the_camera_does_not_want_the_right_button()

	_choosing_a_row_sends_that_rows_command_verbatim()
	_cancel_sends_nothing()
	_an_empty_option_list_opens_nothing()
	_the_box_stays_inside_the_pane()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: choose_option")
	get_tree().quit(0)


# ─── What the options are ────────────────────────────────────────────────────

func _a_corpse_offers_every_verb_the_server_listed() -> void:
	var options := WorldView.options_for(CORPSE)

	_expect(options.size() == 2, "a corpse offers two options")
	_expect(str(options[0]["command"]) == "butcher Mutant Raider corpse",
			"the first option is the one `interact` also names")
	_expect(str(options[1]["command"]) == "get Mutant Raider corpse",
			"the second option is the one only `actions` names")


func _an_entity_with_one_verb_falls_back_to_interact() -> void:
	## Not a legacy path. The server OMITS `actions` whenever it would hold a
	## single command, so this runs for almost every entity in the world.
	var options := WorldView.options_for(RAIDER)

	_expect(options.size() == 1, "a one-verb entity offers one option")
	_expect(str(options[0]["command"]) == "attack Mutant Raider",
			"and it is the `interact` string, verbatim")


func _an_entity_that_affords_nothing_offers_nothing() -> void:
	_expect(WorldView.options_for(STRANGER).is_empty(),
			"an entity with no verb offers no menu")


func _a_repeated_command_is_listed_once() -> void:
	## Deduplicated on the COMMAND, not the label: two rows that send the same
	## string are one option however they are worded.
	var doubled := CORPSE.duplicate(true)
	doubled["actions"] = [
		{"command": "get Mutant Raider corpse", "label": "Get"},
		{"command": "get Mutant Raider corpse", "label": "Take"},
	]

	_expect(WorldView.options_for(doubled).size() == 1,
			"one command listed twice becomes one row")


func _a_malformed_action_is_skipped() -> void:
	## A cosmetic menu must never be the thing that stops a right click
	## working, so a junk entry is dropped rather than raised on.
	var broken := CORPSE.duplicate(true)
	broken["actions"] = [
		"not a dictionary",
		{"label": "Butcher"},
		{"command": "   ", "label": "Blank"},
		{"command": "get Mutant Raider corpse", "label": "Get"},
	]

	var options := WorldView.options_for(broken)

	_expect(options.size() == 1, "junk entries are skipped")
	_expect(str(options[0]["command"]) == "get Mutant Raider corpse",
			"and the good one survives")


# ─── What the rows say ───────────────────────────────────────────────────────

func _rows_read_as_verb_then_target() -> void:
	var options := WorldView.options_for(CORPSE)

	_expect(Menu.row_text(options[0]) == "Butcher Mutant Raider corpse",
			"a row reads as the server's verb, then the entity's name")


func _a_row_with_no_target_is_the_verb_alone() -> void:
	## A tile's action, exactly as _offer_options builds one: no target,
	## because it names no entity, and no label, because `tile_actions` is
	## `{command, kind}` and carries no wording for the client to use.
	_expect(Menu.row_text({"command": "north", "label": ""}) == "North",
			"a targetless row is the verb alone, capitalised")
	_expect(Menu.row_text({"command": "goto (4,3)", "label": ""}) == "Goto (4,3)",
			"and a tile command with an argument keeps the argument")


func _a_label_the_server_omitted_falls_back_to_the_command() -> void:
	## The fallback WorldView.options_for builds for a one-verb entity carries
	## no label, so this is the path every ordinary NPC takes.
	var options := WorldView.options_for(RAIDER)

	_expect(Menu.row_text(options[0]) == "Attack Mutant Raider",
			"a missing label falls back to the command's verb")


# ─── Which button opens it ───────────────────────────────────────────────────

## The right button belongs to the menu alone, and this is the assertion that
## keeps it that way.
##
## OrbitCamera turned the camera on a RIGHT drag until 09/10/2026. Sharing one
## button between "turn the camera" and "ask what this is" cannot be made to
## feel right -- opening on the press pops a menu at the start of every turn,
## and opening on the release pops one at the end of every turn unless a pixel
## threshold separates click from drag, which then has to be tuned and is
## wrong for somebody. The camera moved to MIDDLE instead.
##
## Nothing about that raises if it is undone. The menu simply starts appearing
## every time the player looks around, which reads as the client being twitchy
## rather than as a binding conflict -- so it is checked here by reading the
## camera's own source, the one place the binding actually lives.
func _the_camera_does_not_want_the_right_button() -> void:
	var source := FileAccess.get_file_as_string("res://world/orbit_camera.gd")

	_expect(source.contains("MOUSE_BUTTON_MIDDLE"),
			"the camera orbits on the middle button")
	_expect(not source.contains("MOUSE_BUTTON_RIGHT"),
			"and lays no claim to the right one, which is the menu's")


# ─── What gets sent ──────────────────────────────────────────────────────────

func _choosing_a_row_sends_that_rows_command_verbatim() -> void:
	var menu := _menu()
	menu.open(WorldView.options_for(CORPSE), Vector2(10.0, 10.0))

	_press(menu, "Get Mutant Raider corpse")

	_expect(_sent == ["get Mutant Raider corpse"],
			"the chosen row sends the server's own string")
	_expect(not menu.is_open(), "and the box closes behind it")
	menu.queue_free()


func _cancel_sends_nothing() -> void:
	## Its own text would be a command if it were sent. It must not be.
	var menu := _menu()
	menu.open(WorldView.options_for(CORPSE), Vector2(10.0, 10.0))

	_press(menu, Menu.CANCEL)

	_expect(_sent.is_empty(), "Cancel sends no command at all")
	_expect(_dismissals == 1, "and reports the dismissal")
	_expect(not menu.is_open(), "and closes")
	menu.queue_free()


func _an_empty_option_list_opens_nothing() -> void:
	var menu := _menu()

	menu.open([], Vector2(10.0, 10.0))

	_expect(not menu.is_open(), "an empty list opens no box")
	menu.queue_free()


func _the_box_stays_inside_the_pane() -> void:
	## A right click in the bottom-right corner must not push rows off-screen,
	## which would leave options that exist and cannot be clicked.
	var pane := Control.new()
	pane.size = PANE
	add_child(pane)

	var menu := Menu.new()
	pane.add_child(menu)
	menu.open(WorldView.options_for(CORPSE), PANE)

	var corner := menu.position + menu.size

	_expect(menu.position.x >= 0.0 and menu.position.y >= 0.0,
			"the box does not open off the top or left")
	_expect(corner.x <= PANE.x and corner.y <= PANE.y,
			"the box does not overflow the bottom or right")
	pane.queue_free()


# ─── Helpers ─────────────────────────────────────────────────────────────────

## A menu in the tree with its emissions recorded, and the record cleared.
func _menu() -> ChooseOption:
	_sent.clear()
	_dismissals = 0

	var menu := Menu.new()
	add_child(menu)
	menu.chosen.connect(func(command: String) -> void: _sent.append(command))
	menu.dismissed.connect(func() -> void: _dismissals += 1)

	return menu


## Click the row showing this text. Fails the case if there is no such row,
## which is how a renamed row is caught rather than silently untested.
func _press(menu: ChooseOption, text: String) -> void:
	for row: Node in menu.get_child(0).get_children():
		if row is Button and (row as Button).text == text:
			(row as Button).pressed.emit()
			return

	_expect(false, "a row reading '%s' exists" % text)


func _expect(passed: bool, what: String) -> void:
	if passed:
		print("  ok   %s" % what)
		return

	_failures += 1
	printerr("  FAIL %s" % what)
