"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: The single owner of every quest-system literal -- the action
             vocabulary, the persisted field names, the status strings and
             the player-facing message templates.
"""

from systems.ui.colors import (
    ERROR_COLOR,
    HIGHLIGHT_COLOR,
    RESET_COLOR,
    SUCCESS_COLOR,
)



# Public constant definitions

# The separator between an action and its argument in a compound target key.
# "talk" + ":" + "lone_android" -> "talk:lone_android".
TARGET_SEPARATOR = ":"


# The global action vocabulary, documented in full in global_quest_actions.md.
# Every quest target's action half MUST be one of these. Before this table
# existed the vocabulary lived only in that markdown file, which meant a
# blueprint could name "interract" and simply never fire -- the same silent
# failure the "Metalsmith"/"Metalsmithing" category typo caused in crafting.
# QuestStep validates against this set at construction, so the typo is now an
# import-time error that the quest loader turns into a test failure.

# Social and NPC interaction.
ACTION_TALK = "talk"
ACTION_GIVE = "give"

# Combat and survival.
ACTION_KILL = "kill"
ACTION_SURVIVE = "survive"

# World and environment.
ACTION_INTERACT = "interact"
ACTION_VISIT = "visit"

# Economy and crafting.
ACTION_GATHER = "gather"
ACTION_CRAFT = "craft"
ACTION_USE = "use"

# Blackout-specific skills and progression.
ACTION_CUT = "cut"
ACTION_MINE = "mine"
ACTION_HARVEST_BRAIN = "harvest_brain"


QUEST_ACTIONS = frozenset({
    ACTION_TALK,
    ACTION_GIVE,
    ACTION_KILL,
    ACTION_SURVIVE,
    ACTION_INTERACT,
    ACTION_VISIT,
    ACTION_GATHER,
    ACTION_CRAFT,
    ACTION_USE,
    ACTION_CUT,
    ACTION_MINE,
    ACTION_HARVEST_BRAIN,
})


# Keys inside the per-quest dict stored in `character.db.active_quests`.
# Named here because the handler, the quest command and the summary panel all
# read the same dict, and a raw "step_index" string in three modules is three
# chances to typo a lookup that fails silently by returning the default.
FIELD_STEP_INDEX = "step_index"
FIELD_PROGRESS = "progress_data"


# The three states a quest can be in for a given character. Returned by
# QuestHandler.status and branched on by dialogue nodes.
STATUS_NOT_STARTED = "not_started"
STATUS_ACTIVE = "active"
STATUS_COMPLETED = "completed"


# Player-facing message templates. The handler formats and sends these; no
# colour literal appears anywhere else in the quest package.
MSG_QUEST_UNKNOWN = (
    f"{ERROR_COLOR}Error: Quest '{{quest_key}}' could not be found "
    f"in the game world.{RESET_COLOR}"
)

MSG_QUEST_ACCEPTED = (
    f"{HIGHLIGHT_COLOR}[NEW QUEST] {{title}}{RESET_COLOR}\n{{description}}"
)

MSG_STEP_ADVANCED = (
    f"{HIGHLIGHT_COLOR}[QUEST UPDATE] Phase completed! "
    f"Next: {{description}}{RESET_COLOR}"
)

MSG_QUEST_COMPLETE = (
    f"{SUCCESS_COLOR}[QUEST COMPLETE] You have completed: "
    f"{{title}}!{RESET_COLOR}"
)

MSG_QUEST_ABANDONED = (
    f"{ERROR_COLOR}[QUEST ABANDONED] You have abandoned: "
    f"{{title}}.{RESET_COLOR}"
)


# Rendered by QuestHandler.objective_lines for one objective. A counted
# objective reads "Raiders repelled: 1/3"; a boolean one reads "[x] Speak to
# the android", because "1/True" is not a sentence.
OBJECTIVE_DONE_MARK = "[x]"
OBJECTIVE_TODO_MARK = "[ ]"

MSG_OBJECTIVE_BOOLEAN = "{mark} {description}"
MSG_OBJECTIVE_COUNTED = "{mark} {description}: {current}/{required}"


# Used when a target carries no authored description and the raw compound key
# has to stand in for one.
UNDESCRIBED_OBJECTIVE = "{target_key}"
