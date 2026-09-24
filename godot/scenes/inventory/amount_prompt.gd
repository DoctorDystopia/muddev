class_name AmountPrompt
extends RefCounted
## The box that asks for the one value the server left blank: the amount in
## Deposit X, Withdraw X, and the pop-up's X button.
##
## The server named the verb, the bounds and the question. This builds a box
## for them and substitutes through [method ServerAction.command], which owns
## the placeholder. There is no verb here and no arithmetic.
##
## It moved out of [InventorySlotCell] when the pop-up needed the same box. One
## box means one set of bounds rules, and a fix to one reaches both.
##
## ## It remembers the size the player gave it
##
## A box is built per prompt and freed on close, so the size has to live
## somewhere that outlives the box: [ClientSettings], with every other thing
## the player set. One size serves every verb -- see
## [constant ClientSettings.DEFAULT_AMOUNT_SIZE].
##
## ## It gets the theme from the project
##
## An [AcceptDialog] is a Window, and a Window does not get the theme from the
## Control that opens it. The project setting `gui/theme/custom` reaches it.

const _Const := preload("res://autoload/blackout_constants.gd")


## Open the box as a child of `parent`, and call `send` with the finished
## command when the player confirms.
##
## Built per prompt and freed on close rather than kept: a stale dialog bound
## to an action from a snapshot ago is a click that moves the wrong thing, and
## every snapshot replaces the rows. Returns the dialog so a test can drive it.
##
## `settings` is how a box built per prompt keeps a size the player set on an
## earlier one. It is optional, and a null gives the wrapped box with no
## memory: three call sites open this, and a test drives two of them with no
## profile to write to.
static func ask(parent: Node, action: Dictionary, prompt: Dictionary, send: Callable,
		settings: ClientSettings = null) -> AcceptDialog:
	var minimum := int(prompt.get(_Const.ACTION_INPUT_MIN_KEY, 1))
	var maximum := int(prompt.get(_Const.ACTION_INPUT_MAX_KEY, minimum))

	var spin := SpinBox.new()
	spin.min_value = minimum
	spin.max_value = maximum
	spin.value = minimum
	spin.step = 1
	spin.select_all_on_focus = true

	var dialog := AcceptDialog.new()
	dialog.title = str(action.get("label", ""))
	dialog.dialog_text = str(prompt.get(_Const.ACTION_INPUT_LABEL_KEY, ""))
	# Stated rather than left to the engine's default, because the whole point
	# of remembering a size is that the player can set one.
	dialog.unresizable = false
	dialog.add_child(spin)
	dialog.confirmed.connect(func() -> void:
		var command := ServerAction.command(action, int(spin.value))

		if not command.is_empty():
			send.call(command)
	)
	# Connected BEFORE the frees below, because a callback list runs in
	# connection order and the size has to be read while the dialog still
	# holds one.
	if settings != null:
		var remember := func() -> void: settings.set_amount_size(dialog.size)
		dialog.close_requested.connect(remember)
		dialog.confirmed.connect(remember)

	# QUEUE_FREE on close, not hide: the dialog is bound to one action from one
	# snapshot, and the next payload replaces the row it describes.
	dialog.close_requested.connect(dialog.queue_free)
	dialog.confirmed.connect(dialog.queue_free)

	parent.add_child(dialog)
	_open_at(dialog, settings)

	return dialog


## The size to open the box at, or zero to let it wrap its contents.
##
## Static and public because it is the DECISION, and a headless run cannot
## check the outcome: the dummy display is 64 pixels square, so any real box
## centres at a negative position and the engine refuses to spawn it. This is
## the seam [ChooseOption] uses for the same reason -- assert what the code
## decided, where the platform will not show what it did.
static func wanted_size(settings: ClientSettings) -> Vector2i:
	if settings == null:
		return Vector2i.ZERO

	var wanted := settings.amount_size

	if wanted.x <= 0 or wanted.y <= 0:
		return Vector2i.ZERO

	return wanted


## Open the box at the size the player left it at, or at its own.
##
## `popup_centered` with no size wraps the contents, which is the first-run
## look. With a size it centres that size instead, and [AcceptDialog] still
## grows the box when its contents need more -- so a size saved by a build with
## a shorter question cannot cut the question off.
static func _open_at(dialog: AcceptDialog, settings: ClientSettings) -> void:
	var wanted := wanted_size(settings)

	if wanted == Vector2i.ZERO:
		dialog.popup_centered()
		return

	dialog.popup_centered(wanted)
