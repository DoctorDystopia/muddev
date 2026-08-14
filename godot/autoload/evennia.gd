extends Node
## The only node in the client that touches the socket.

## Wire format is Evennia's outputfunc form, `[name, args, kwargs]`, both ways.
## See `evennia/server/portal/webclient.py` -- `send_default` serialises every
## outputfunc that way and `onMessage` unpacks inbound frames the same way.

## Port 4008 is the `godotwebsocket` contrib. It subclasses the browser
## websocket protocol and overrides ONE method, `send_text`, to convert ANSI to
## BBCode. Everything else -- including `send_default`, which is what carries
## the entire Blackout state feed -- is inherited unchanged. That is why this
## file needs no per-channel knowledge and why the server needed no changes to
## feed a Godot client.

## Socket is up. Nothing has been sent yet.
signal opened
## Socket is down. `code` is -1 when the close was not clean.
signal closed(code: int, reason: String)
## One line of game output, already BBCode, ready for a RichTextLabel.
signal text_received(bbcode: String)
## One structured state-feed message. `channel` is the outputfunc name
## (`room_info`, `blackout_map`, ...); see blackout/systems/statefeed/constants.py.
signal channel_received(channel: String, payload: Dictionary)

const DEFAULT_HOST := "127.0.0.1"
const DEFAULT_PORT := 4008

## Evennia's `clean_senddata` stamps this key into EVERY outputfunc's kwargs.
## It is transport bookkeeping rather than payload, so it is dropped here once
## instead of being ignored by every consumer.
const _OPTIONS_KEY := "options"

var _socket := WebSocketPeer.new()
var _open := false


func _ready() -> void:
	# Nothing to poll until open() is called.
	set_process(false)


## Open the connection. Returns OK, or the error that stopped it.
func open(host: String = DEFAULT_HOST, port: int = DEFAULT_PORT) -> Error:
	var err := _socket.connect_to_url("ws://%s:%d" % [host, port])

	if err == OK:
		set_process(true)

	return err


func close() -> void:
	_socket.close()


## Send one outputfunc. Every outbound frame in the client goes through here.
func send(func_name: String, args: Array = [], kwargs: Dictionary = {}) -> void:
	if not _open:
		push_warning("Evennia: dropped %s, socket not open." % func_name)
		return

	_socket.send_text(JSON.stringify([func_name, args, kwargs]))


## Send a player command.

## This is deliberately the ONLY way this client acts on the world: clicking a
## tile sends the same `north` a telnet player types. There is no privileged
## client channel that bypasses a Command, so every lock, cooldown and
## permission keeps working with nothing to re-audit.
func command(line: String) -> void:
	send("text", [line])


func _process(_delta: float) -> void:
	_socket.poll()

	match _socket.get_ready_state():
		WebSocketPeer.STATE_OPEN:
			if not _open:
				_open = true
				opened.emit()

			while _socket.get_available_packet_count() > 0:
				# UTF-8, not ASCII. The contrib's own README example uses
				# get_string_from_ascii(), which mangles the box-drawing the
				# dossier and every section rule in the game are built from.
				_dispatch(_socket.get_packet().get_string_from_utf8())

		WebSocketPeer.STATE_CLOSED:
			set_process(false)
			_open = false
			closed.emit(_socket.get_close_code(), _socket.get_close_reason())


func _dispatch(raw: String) -> void:
	var frame: Variant = JSON.parse_string(raw)

	if typeof(frame) != TYPE_ARRAY or frame.size() != 3:
		push_warning("Evennia: unparseable frame: %s" % raw)
		return

	var func_name: String = frame[0]

	# `text` is the only outputfunc whose payload lives in args rather than
	# kwargs. Blackout sends no `prompt` -- the char_vitals channel is what a
	# graphical client draws a prompt from -- so one branch covers game output.
	if func_name == "text":
		for line: Variant in frame[1]:
			text_received.emit(str(line))
		return

	var payload: Dictionary = frame[2]
	payload.erase(_OPTIONS_KEY)
	channel_received.emit(func_name, payload)


func _exit_tree() -> void:
	_socket.close()
