@tool
class_name DialogueStub
extends RefCounted
## GENERATED FILE. Do not edit it. To write it again, run from blackout/:
##
##     python -m systems.gameplay.dialogue --write-stub
##
## The dialogue vocabulary of the server as GDScript, for the Godot editor
## (DESIGN-0017). The server owns each name
## (`blackout/systems/gameplay/dialogue/vocab_defs/`). This file only lets
## the editor use the names with no server:
##
## - The test scene of the Dialogue tab gives one DialogueStub to the runtime
##   of Dialogue Manager. Thus, the Run button works on a dialogue script.
## - The Dialogue tab reads this file for its list of names.
##
## No name here reads the game. A yes or no query gives the answer that the
## author set in the test scene, and false before that. A text gives its
## call in angle brackets. An action only records its call.

const KIND_FLAG := "flag"
const KIND_TEXT := "text"
const KIND_OTHER := "other"
const KIND_ACTION := "action"

## How the stub answers each name of the vocabulary.
const KINDS := {
	"message.success": "action",
	"npc.description": "text",
	"npc.header": "text",
	"npc.heading": "text",
	"npc.name": "text",
	"player.name": "text",
	"quest.accept": "action",
	"quest.accept_prompt": "text",
	"quest.is_active": "flag",
	"quest.is_available": "flag",
	"quest.is_complete": "flag",
	"quest.objectives": "text",
	"quest.on_step": "flag",
	"quest.report": "action",
	"quest.reported": "flag",
	"quest.talk": "action",
	"quest.title": "text",
	"recipe.name": "text",
}

## The answer that the author set for a call, by its call text. Change it in
## place. Each namespace holds this same Dictionary.
var answers: Dictionary = {}

## Each action that the script ran, as its call text, in order.
var actions: Array[String] = []

var message := MessageNames.new(answers, actions)
var npc := NpcNames.new(answers, actions)
var player := PlayerNames.new(answers, actions)
var quest := QuestNames.new(answers, actions)
var recipe := RecipeNames.new(answers, actions)


## The text of one call, as an author writes it:
## `quest.on_step("a", "b")`.
static func call_text(name: String, arguments: Array) -> String:
	var parts: Array[String] = []

	for argument: Variant in arguments:
		parts.append(JSON.stringify(argument))

	return "%s(%s)" % [name, ", ".join(parts)]


## The part that each namespace shares: the answers, and one helper for each
## kind of answer.
class Names extends RefCounted:
	var _answers: Dictionary
	var _actions: Array[String]


	func _init(answers: Dictionary, actions: Array[String]) -> void:
		_answers = answers
		_actions = actions


	func _flag(asked: String) -> bool:
		return bool(_answers.get(asked, false))


	func _text(asked: String) -> String:
		return str(_answers.get(asked, "<%s>" % asked))


	func _other(asked: String) -> Variant:
		return _answers.get(asked)


	func _do(asked: String) -> void:
		_actions.append(asked)


class MessageNames extends Names:
	## Send one line to the log of the player, in the success colour.
	func success(text: Variant) -> void:
		_do(DialogueStub.call_text("message.success", [text]))


class NpcNames extends Names:
	## The description of the NPC, as `look` shows it.
	var description: String:
		get:
			return _text("npc.description")


	## The name of the NPC as a heading, and its description below it.
	var header: String:
		get:
			return _text("npc.header")


	## The name of the NPC as a heading.
	var heading: String:
		get:
			return _text("npc.heading")


	## The name of the NPC that speaks.
	var name: String:
		get:
			return _text("npc.name")


class PlayerNames extends Names:
	## The name of the player character.
	var name: String:
		get:
			return _text("player.name")


class QuestNames extends Names:
	## The player takes the quest.
	func accept(quest_key: Variant) -> void:
		_do(DialogueStub.call_text("quest.accept", [quest_key]))


	## The line that asks the player to take the quest, with its title.
	func accept_prompt(quest_key: Variant) -> String:
		return _text(DialogueStub.call_text("quest.accept_prompt", [quest_key]))


	## True while the player has the quest and it is not done.
	func is_active(quest_key: Variant) -> bool:
		return _flag(DialogueStub.call_text("quest.is_active", [quest_key]))


	## True if the player can take the quest now.
	func is_available(quest_key: Variant) -> bool:
		return _flag(DialogueStub.call_text("quest.is_available", [quest_key]))


	## True after the player completed the quest.
	func is_complete(quest_key: Variant) -> bool:
		return _flag(DialogueStub.call_text("quest.is_complete", [quest_key]))


	## The objective lines of the quest, under a heading.
	func objectives(quest_key: Variant) -> String:
		return _text(DialogueStub.call_text("quest.objectives", [quest_key]))


	## True while the player is on this step of the quest.
	func on_step(quest_key: Variant, step_key: Variant) -> bool:
		return _flag(DialogueStub.call_text("quest.on_step", [quest_key, step_key]))


	## Report a target of any quest action to one quest, for example a chore.
	func report(quest_key: Variant, action_name: Variant, target: Variant) -> void:
		_do(DialogueStub.call_text("quest.report", [quest_key, action_name, target]))


	## True if the current step already has this target.
	func reported(quest_key: Variant, action_name: Variant, target: Variant) -> bool:
		return _flag(DialogueStub.call_text("quest.reported", [quest_key, action_name, target]))


	## Report a talk target to one quest. The step that waits for it advances.
	func talk(quest_key: Variant, target: Variant) -> void:
		_do(DialogueStub.call_text("quest.talk", [quest_key, target]))


	## The title of the quest.
	func title(quest_key: Variant) -> String:
		return _text(DialogueStub.call_text("quest.title", [quest_key]))


class RecipeNames extends Names:
	## The name of a recipe, as the craft menu shows it.
	func name(recipe_key: Variant) -> String:
		return _text(DialogueStub.call_text("recipe.name", [recipe_key]))
