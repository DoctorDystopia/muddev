class_name TextPrompt
extends RefCounted
## The box that asks for the one line of text the server left blank: the name
## of a bank tab.
##
## The text twin of [AmountPrompt]. The server named the verb, the longest
## text and the question. This builds a box for them and substitutes through
## [method ServerAction.command_with_text], which owns the placeholder.
##
## Built per prompt and freed on close, for the reason [AmountPrompt] gives: a
## stale box bound to an action from an older snapshot names the wrong tab.

const _Const := preload("res://autoload/blackout_constants.gd")


## Open the box as a child of `parent`, and call `send` with the finished
## command when the player confirms. Enter in the text field confirms too.
## Returns the dialog so a test can drive it.
static func ask(parent: Node, action: Dictionary, prompt: Dictionary,
		send: Callable) -> AcceptDialog:
	var field := LineEdit.new()
	field.max_length = int(prompt.get(_Const.ACTION_INPUT_MAX_KEY, 0))
	field.select_all_on_focus = true

	var dialog := AcceptDialog.new()
	dialog.title = str(action.get("label", ""))
	dialog.dialog_text = str(prompt.get(_Const.ACTION_INPUT_LABEL_KEY, ""))
	dialog.unresizable = false
	dialog.add_child(field)
	dialog.register_text_enter(field)

	dialog.confirmed.connect(func() -> void:
		var command := ServerAction.command_with_text(action, field.text)

		if not command.is_empty():
			send.call(command)
	)
	dialog.close_requested.connect(dialog.queue_free)
	dialog.confirmed.connect(dialog.queue_free)

	parent.add_child(dialog)
	dialog.popup_centered()
	field.grab_focus.call_deferred()

	return dialog


## Send one of the server's actions from `parent`: ask for text or an amount
## first when the action is prompted. One routine, so the slot, the tab button
## and the footer cannot read a prompted action differently.
static func perform(parent: Node, action: Dictionary, send: Callable,
		settings: ClientSettings = null) -> void:
	var text := ServerAction.text_prompt(action)

	if not text.is_empty():
		ask(parent, action, text, send)
		return

	var amount := ServerAction.prompt(action)

	if not amount.is_empty():
		AmountPrompt.ask(parent, action, amount, send, settings)
		return

	var command := ServerAction.command(action)

	if command.is_empty():
		return

	send.call(command)
