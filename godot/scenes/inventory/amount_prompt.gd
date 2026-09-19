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

## The client's Theme. An [AcceptDialog] is a Window, and a Window does not
## inherit the theme from the Control that opened it.
const _THEME := preload("res://ui/blackout_theme.tres")

const _Const := preload("res://autoload/blackout_constants.gd")


## Open the box as a child of `parent`, and call `send` with the finished
## command when the player confirms.
##
## Built per prompt and freed on close rather than kept: a stale dialog bound
## to an action from a snapshot ago is a click that moves the wrong thing, and
## every snapshot replaces the rows. Returns the dialog so a test can drive it.
static func ask(parent: Node, action: Dictionary, prompt: Dictionary,
		send: Callable) -> AcceptDialog:
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
	dialog.theme = _THEME
	dialog.add_child(spin)
	dialog.confirmed.connect(func() -> void:
		var command := ServerAction.command(action, int(spin.value))

		if not command.is_empty():
			send.call(command)
	)
	# QUEUE_FREE on close, not hide: the dialog is bound to one action from one
	# snapshot, and the next payload replaces the row it describes.
	dialog.close_requested.connect(dialog.queue_free)
	dialog.confirmed.connect(dialog.queue_free)

	parent.add_child(dialog)
	dialog.popup_centered()

	return dialog
