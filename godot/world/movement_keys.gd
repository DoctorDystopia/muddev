class_name MovementKeys
extends RefCounted
## Which key means which direction, and nothing about focus.
##
## Pure lookup with no widget in it. The table is worth testing on its own
## because it is the sort of thing that is wrong in one corner — a diagonal
## swapped, a vi key missing — and reads as fine until somebody walks the wrong
## way in a fight.
##
## ## This is the webclient's table, on purpose
##
## `web/static/webclient/js/plugins/hotkeys.js` binds these sixteen keys, and
## `playblackout-site`'s /play page tells every new player "WASDQEZC keys and
## click for movement". Changing the bindings here would make the page wrong
## for whichever client the player happens to be using, so the two halves of
## the compass rose are copied rather than redesigned.
##
## ## Why the command is a bare direction string
##
## It is what a telnet player types, which is the rule the whole client is
## built on — see [method Evennia.command]. The server either has that exit or
## says so. Notably this does NOT reconstruct a direction from grid geometry:
## `WorldState.direction_for()` did that and was deleted for cause in ENG-0006
## Phase 2, because a delta cannot express a one-way exit or a map whose
## geometry and exit names disagree. A keypress is not a geometric claim — it
## is the player naming a direction, exactly as if they had typed it.
##
## ## The mode problem, and where it is solved
##
## The webclient can fire these whenever the player is not typing, because its
## input is one DOM element among many and focus moves off it constantly. In
## Godot the text input owns the keyboard: `Console` grabs it on ready and
## nothing takes it away, so a binding gated on "not typing" would never fire
## once. [Console] resolves that with an explicit mode — Escape leaves the
## input, Enter returns to it — and this class deliberately knows nothing about
## it. It answers one question: what does this key mean.

## Keycode to the command a telnet player would type.
##
## Two overlapping layouts, both from the webclient: WASD with QEZC diagonals,
## and vi keys with yubn diagonals. They share the same eight destinations, so
## a player who knows either finds the other already working.
const BINDINGS := {
	KEY_W: "north",
	KEY_A: "west",
	KEY_S: "south",
	KEY_D: "east",
	KEY_Q: "northwest",
	KEY_E: "northeast",
	KEY_Z: "southwest",
	KEY_C: "southeast",
	
	KEY_KP_8: "north",
	KEY_KP_4: "west",
	KEY_KP_2: "south",
	KEY_KP_6: "east",
	KEY_KP_7: "northwest",
	KEY_KP_9: "northeast",
	KEY_KP_1: "southwest",
	KEY_KP_3: "southeast",

	KEY_K: "north",
	KEY_H: "west",
	KEY_J: "south",
	KEY_L: "east",
	KEY_Y: "northwest",
	KEY_U: "northeast",
	KEY_B: "southwest",
	KEY_N: "southeast",
}

## The eight directions, derived from the table rather than restated.
##
## Deriving it is the point: a binding added below reaches this list with no
## second edit, and the two can never disagree about which directions exist.
static func directions() -> PackedStringArray:
	var found: PackedStringArray = []

	for keycode: int in BINDINGS:
		var command: String = BINDINGS[keycode]

		if not found.has(command):
			found.append(command)

	found.sort()

	return found


## The command a key means, or "" when the key is not a movement key.
##
## Empty rather than null so a caller can test the result directly; there is no
## direction named "" and never will be.
static func command_for(keycode: int) -> String:
	return BINDINGS.get(keycode, "")


## Whether this key is bound to a direction at all.
static func is_movement_key(keycode: int) -> bool:
	return BINDINGS.has(keycode)
