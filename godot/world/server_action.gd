class_name ServerAction
extends RefCounted
## One action the SERVER named, read the one way every pane reads it.
##
## An action is `{label, command}`, or a prompted one: an EMPTY `command` with a
## `template` and an `input` block, for the one value only this client holds —
## the amount in Deposit X. The inventory pane read these first. The pop-up
## reads the same shape, so the rules moved here and both panes call them.
## [InventoryState] keeps its two methods as thin wrappers, so nothing that
## already called them changed.
##
## Static and stateless. There is nothing to bind and nothing to reset.

const _Const := preload("res://autoload/blackout_constants.gd")

## Smallest amount a quantity prompt may be set to, whatever the server said.
##
## A floor rather than a trusted value: the server sends a `min` and it is 1,
## but a prompt that could be driven to zero is one where confirming does
## nothing, which reads as a broken dialog rather than as a declined action.
const AMOUNT_FLOOR := 1


## The quantity prompt one of the server's actions asks for, or an empty
## dictionary when it asks for nothing.
##
## Read as a question rather than as a flag so the caller gets the bounds and
## the wording in the same call it learns there is a prompt at all.
static func prompt(action: Dictionary) -> Dictionary:
	var asked: Variant = action.get("input")

	if typeof(asked) != TYPE_DICTIONARY:
		return {}

	if str(asked.get(_Const.ACTION_INPUT_KIND_KEY, "")) \
			!= _Const.ACTION_INPUT_KIND_QUANTITY:
		return {}

	var maximum := int(asked.get(_Const.ACTION_INPUT_MAX_KEY, 1))
	var minimum := int(asked.get(_Const.ACTION_INPUT_MIN_KEY, AMOUNT_FLOOR))

	return {
		_Const.ACTION_INPUT_MIN_KEY: maxi(minimum, AMOUNT_FLOOR),
		_Const.ACTION_INPUT_MAX_KEY: maxi(maximum, minimum),
		_Const.ACTION_INPUT_LABEL_KEY: str(
			asked.get(_Const.ACTION_INPUT_LABEL_KEY, "")),
	}


## What to send for one of the server's actions, given the amount the player
## chose.
##
##     a non-empty `command`  -> send it verbatim, `amount` ignored
##     a prompted action      -> substitute into its `template`
##     anything else          -> "", the server declining
##
## **The empty string is not an error and must never be guessed at.** An action
## with no command is the server saying "do not offer this", exactly as an
## empty tile action is. Returning "" rather than a half-built string is what
## makes the payload's contract degrade safely.
##
## The placeholder is [code]ACTION_AMOUNT_PLACEHOLDER[/code], generated from
## the server's constants, never a literal here.
static func command(action: Dictionary, amount: int = 0) -> String:
	var whole := str(action.get("command", ""))

	if not whole.is_empty():
		return whole

	if prompt(action).is_empty():
		return ""

	var template := str(action.get("template", ""))

	if template.is_empty():
		return ""

	return template.replace(_Const.ACTION_AMOUNT_PLACEHOLDER, str(amount))
