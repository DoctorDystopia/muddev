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
##
## `requested` distinguishes a close this client asked for from one the network
## or the server did. It is the whole difference between "the player is leaving"
## and "the player was dropped", and only the second should be reconnected —
## a client that dialled back in after its own [method close] would be
## impossible to shut down.
signal closed(code: int, reason: String, requested: bool)
## One line of game output, already BBCode, ready for a RichTextLabel.
##
## `kwargs` is the outputfunc's OWN keyword payload, and for `text` that is
## where the routing tag lives: `msg(text=(line, {"type": "combat"}))` reaches
## here as `{"type": "combat"}`. The contrib pops `options` server-side before
## it sends, so what arrives is the game's own kwargs and nothing else.
##
## Emitted even when empty, so a consumer has one signature to bind rather than
## two. What an absent `type` MEANS is the consumer's business -- see
## [ChatLog], which supplies the default; a client that dropped an untagged
## line would lose everything Evennia's own commands say.
signal text_received(bbcode: String, kwargs: Dictionary)
## One structured state-feed message. `channel` is the outputfunc name
## (`room_info`, `blackout_map`, ...); see blackout/systems/statefeed/constants.py.
signal channel_received(channel: String, payload: Dictionary)

## Where this build connects, decided by [ServerEndpoint]: an explicit
## override, else the dev server for a debug build and production for a release
## one. Resolved once, on first use, so every log line and reconnect names the
## same place.
var _url := ""

## Evennia's `clean_senddata` stamps this key into EVERY outputfunc's kwargs.
## It is transport bookkeeping rather than payload, so it is dropped here once
## instead of being ignored by every consumer.
const _OPTIONS_KEY := "options"

var _socket := WebSocketPeer.new()
var _open := false

## Set by [method close] and cleared by [method open], so the `closed` signal
## can say which kind of close this was.
var _close_requested := false


func _ready() -> void:
	# Nothing to poll until open() is called.
	set_process(false)


## Open the connection. Returns OK, or the error that stopped it.
##
## Takes no host: WHICH server to reach is a property of the build and its
## arguments, not of the caller, and threading it through every call site would
## give that fact more than one owner.
## Reconnecting is a supported call, not just a first one — see
## [ReconnectPolicy]. A FRESH peer every time, because a WebSocketPeer that has
## reached STATE_CLOSED carries the previous close code and reason, and reusing
## one makes a failed redial report the reason the LAST socket died. Building a
## new one costs nothing next to a TCP handshake and removes the whole class of
## stale-state question.
func open() -> Error:
	_socket = WebSocketPeer.new()
	_open = false
	_close_requested = false

	var err := _socket.connect_to_url(url())

	if err == OK:
		set_process(true)

	return err


## The endpoint this client uses, resolved once and remembered.
func url() -> String:
	if _url.is_empty():
		_url = ServerEndpoint.resolve(_override(), OS.is_debug_build())

	return _url


## An explicit endpoint from wherever this platform puts one.
##
## On the web that is the page's query string, which is how a tester points a
## deployed build at a different server without a rebuild. On desktop it is the
## command line. Neither exists on the other, so both are consulted and the
## empty one costs nothing.
func _override() -> String:
	if OS.has_feature("web"):
		# Explicitly Variant: eval() has no return type, and an inferred
		# `:=` is a parse error under this project's warning settings.
		var location: Variant = JavaScriptBridge.eval("window.location.search", true)

		if typeof(location) == TYPE_STRING:
			return ServerEndpoint.override_from_query(str(location))

		return ""

	return ServerEndpoint.override_from_args(OS.get_cmdline_args())


## Close deliberately. The `closed` signal will report `requested = true`.
func close() -> void:
	_close_requested = true
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
			closed.emit(_socket.get_close_code(), _socket.get_close_reason(),
				_close_requested)


func _dispatch(raw: String) -> void:
	var frame: Variant = JSON.parse_string(raw)

	if typeof(frame) != TYPE_ARRAY or frame.size() != 3:
		push_warning("Evennia: unparseable frame: %s" % raw)
		return

	var func_name: String = frame[0]

	var payload: Dictionary = frame[2]
	payload.erase(_OPTIONS_KEY)

	# `text` is the only outputfunc whose payload lives in args rather than
	# kwargs. Blackout sends no `prompt` -- the char_vitals channel is what a
	# graphical client draws a prompt from -- so one branch covers game output.
	#
	# The kwargs go out WITH the line rather than being dropped here. They were
	# dropped until 08/28/2026, which is why the routing tag five call sites
	# were already sending had never reached a pane.
	if func_name == "text":
		for line: Variant in frame[1]:
			text_received.emit(str(line), payload)
		return

	channel_received.emit(func_name, payload)


func _exit_tree() -> void:
	_socket.close()
