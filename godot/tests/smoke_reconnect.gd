extends Node
## Live smoke test: a closed socket can be reopened.
##
## NEEDS A RUNNING EVENNIA. No account required -- this never logs in; it only
## proves the socket can be dialled twice.
##
##     godot --headless --path godot res://tests/smoke_reconnect.tscn
##
## ## Why this is a live test and not a unit test
##
## [ReconnectPolicy] covers the schedule and is pure. What it cannot cover is
## the part that actually broke things elsewhere: whether `Evennia.open()` is
## callable a second time at all. A [WebSocketPeer] that has reached
## STATE_CLOSED is a used object, and the fix -- building a fresh peer per
## open -- is exactly the kind of change that looks obviously correct and can
## only be confirmed against a real server.
##
## It also pins the second half of the contract: the `closed` signal must
## report `requested` truthfully, because that flag is the only thing standing
## between "the player quit" and an unkillable client that redials its own
## shutdown.

## Give up rather than hang a CI run forever.
const TIMEOUT_SECONDS := 15.0

var _opens := 0
var _closes := 0
var _requested_flags: Array[bool] = []
var _failures := 0


func _ready() -> void:
	Evennia.opened.connect(_on_opened)
	Evennia.closed.connect(_on_closed)

	get_tree().create_timer(TIMEOUT_SECONDS).timeout.connect(_give_up)

	var err := Evennia.open()

	if err != OK:
		printerr("FAIL: could not open socket at all: error %d" % err)
		get_tree().quit(1)


func _on_opened() -> void:
	_opens += 1
	print("open #%d to %s" % [_opens, Evennia.url()])

	if _opens == 1:
		# A deliberate close, which must NOT be reported as a drop.
		Evennia.close()
		return

	_finish()


func _on_closed(code: int, _reason: String, requested: bool) -> void:
	_closes += 1
	_requested_flags.append(requested)
	print("close #%d (code %d, requested=%s)" % [_closes, code, requested])

	if _closes == 1:
		# The redial. Called straight from the signal on purpose: if a fresh
		# peer were not built per open, this is the call that would fail.
		var err := Evennia.open()

		if err != OK:
			printerr("FAIL: redial refused: error %d" % err)
			get_tree().quit(1)


func _finish() -> void:
	_expect(_opens == 2, "the socket opened twice")
	_expect(_closes == 1, "and closed once in between")
	_expect(_requested_flags == [true],
		"the deliberate close reported requested=true, not a drop")

	Evennia.close()

	if _failures > 0:
		printerr("FAIL: %d case(s)" % _failures)
		get_tree().quit(1)
		return

	print("PASS: reconnect reopens a closed socket")
	get_tree().quit(0)


func _give_up() -> void:
	printerr("FAIL: timed out after %.0fs with %d open(s), %d close(s). "
		% [TIMEOUT_SECONDS, _opens, _closes]
		+ "Is Evennia running?")
	get_tree().quit(1)


func _expect(condition: bool, what: String) -> void:
	if condition:
		return

	_failures += 1
	printerr("  not true: %s" % what)
