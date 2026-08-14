extends Node
## Phase 1 acceptance test: does the state-feed handshake work over the
## godotwebsocket port?
##
##     godot --headless --path godot res://tests/smoke_handshake.tscn
##
## Exits 0 once the server acks the subscription, 1 on a timeout or a closed
## socket. Needs a running Evennia but NO account -- `blackout_subscribe` is
## answered on an unauthenticated session, which is what makes this runnable
## without touching the dev database.

const _CH_SUBSCRIBED := "blackout_subscribed"
const _TIMEOUT_SECONDS := 10.0


func _ready() -> void:
	Evennia.opened.connect(_on_opened)
	Evennia.closed.connect(_on_closed)
	Evennia.channel_received.connect(_on_channel)
	Evennia.text_received.connect(_on_text)

	var err := Evennia.open()

	if err != OK:
		_fail("open() returned error %d" % err)
		return

	get_tree().create_timer(_TIMEOUT_SECONDS).timeout.connect(_on_timeout)


func _on_opened() -> void:
	# Nothing to send yet -- the server announces an empty subscription set
	# once it is actually able to route an inputfunc. See _on_channel.
	print("connected; waiting for the server to announce")


func _on_text(bbcode: String) -> void:
	# The login banner proves the text path and the contrib's ANSI-to-BBCode
	# conversion in one go.
	print("text: %s" % bbcode)


func _on_channel(channel: String, payload: Dictionary) -> void:
	print("channel %s: %s" % [channel, JSON.stringify(payload)])

	if channel == _CH_SUBSCRIBED:
		var channels: Array = payload.get("channels", [])

		# The empty announcement is the server saying it is ready and has no
		# subscription for us. Answering it is the whole handshake.
		if channels.is_empty():
			print("announced empty; subscribing")
			Evennia.send("blackout_subscribe", [], {"channels": "all"})
			return

		print("PASS: %d channels acked" % channels.size())
		get_tree().quit(0)


func _on_closed(code: int, reason: String) -> void:
	_fail("socket closed (%d) %s" % [code, reason])


func _on_timeout() -> void:
	_fail("no ack within %.0fs" % _TIMEOUT_SECONDS)


func _fail(message: String) -> void:
	printerr("FAIL: %s" % message)
	get_tree().quit(1)
