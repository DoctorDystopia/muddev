extends Control
## The client shell: the text game on the left, the 3D world on the right.
##
## Owns the connection and the subscription handshake, and nothing else. The
## world pane reads the feed straight off Evennia's signals -- routing every
## payload through here first would make this the file everyone has to edit to
## add a channel, which is the dispatch chain the whole ack-driven design
## exists to avoid.

## Every name the SERVER owns, generated from
## blackout/systems/statefeed/constants.py by systems/statefeed/clientexport.py.
## Preloaded, not autoloaded -- the generated file declares no `extends Node`.
##
## `SUBSCRIBE_ALL` asks for everything. The server answers with the set it
## actually accepted and THAT is what gets bound; a hardcoded channel list here
## would be a second copy of constants.py, free to drift. `CH_SUBSCRIBED` is
## that answer -- the only channel name this client has to know before the
## server has told it anything.
const Const := preload("res://autoload/blackout_constants.gd")

@onready var _output: RichTextLabel = %Output
@onready var _input: LineEdit = %Input
@onready var _hud: PanelContainer = %Hud
@onready var _inventory: InventoryView = %Inventory

var _channels := PackedStringArray()

## The observer's own state -- avatar, vitals, status.
##
## Owned here rather than by the HUD because it is a MODEL and the HUD is a
## view: a second thing that needs to know your hp (a death screen, a combat
## pane) binds to this, and does not have to reach through a widget to find it.
var _char := CharState.new()

## What you are carrying and wearing. Owned here for the same reason _char is:
## it is a model, and the grid that will draw it is a view.
##
## Consumed but NOT YET DRAWN -- routing it now is what stops char_items_list
## logging as an unbound channel while the grid is being built, and it means
## the model is exercised against the live feed before anything depends on it.
var _items := InventoryState.new()


func _ready() -> void:
	Evennia.opened.connect(_on_opened)
	Evennia.closed.connect(_on_closed)
	Evennia.text_received.connect(_on_text)
	Evennia.channel_received.connect(_on_channel)
	_input.text_submitted.connect(_on_submitted)
	_input.grab_focus()
	_hud.bind(_char)
	_inventory.bind(_items)

	# The pane acts only through Evennia.command(), the same as a clicked tile:
	# every command it emits was named by the server and is one a telnet player
	# could type. There is no privileged path from this screen to the game.
	_inventory.command_requested.connect(Evennia.command)

	var err := Evennia.open()

	if err != OK:
		_note("could not open socket: error %d" % err)


func _on_opened() -> void:
	_note("connected to %s:%d" % [Evennia.DEFAULT_HOST, Evennia.DEFAULT_PORT])

	# Deliberately does NOT subscribe here. The socket is accepted by the
	# Portal, which is up whenever the game is reachable at all -- but an
	# inputfunc is handled by the Server, which may still be starting. A
	# subscribe sent now is dropped without a word. The server tells us when it
	# is ready by announcing an empty subscription set; see _on_channel.


func _on_closed(code: int, reason: String) -> void:
	_note("disconnected (%d) %s" % [code, reason])


func _on_text(bbcode: String) -> void:
	# Evennia sends one message per line without a trailing newline.
	_output.append_text(bbcode + "\n")


func _on_submitted(line: String) -> void:
	_input.clear()

	if not line.is_empty():
		Evennia.command(line)


func _on_channel(channel: String, _payload: Dictionary) -> void:
	if channel != Const.CH_SUBSCRIBED:
		# The observer's own three channels. Offered to the model first, and it
		# reports whether it wanted them -- so the channel names live in
		# CharState next to the fields they fill, rather than being restated
		# here in a second match that could disagree with it.
		if _char.ingest(channel, _payload):
			return

		if _items.ingest(channel, _payload):
			return

		if not _channels.has(channel):
			# Printed rather than shown: an outputfunc nobody handles is a
			# developer's problem, and the left pane belongs to the player.
			print("unbound channel: %s" % channel)

		return

	_channels = PackedStringArray(_payload.get("channels", []))

	# An empty set means the server has forgotten us: either it has just
	# finished syncing this session and never saw a subscribe, or a reload
	# wiped the ndb the set lives on. Either way the answer is to ask again,
	# and this is the only signal that we need to.
	if _channels.is_empty():
		_note("server has no subscription for us; subscribing")
		Evennia.send("blackout_subscribe", [], {"channels": Const.SUBSCRIBE_ALL})
		return

	_note("subscribed: %d channels" % _channels.size())


func _note(message: String) -> void:
	_output.append_text("[i][color=gray]-- %s[/color][/i]\n" % message)
