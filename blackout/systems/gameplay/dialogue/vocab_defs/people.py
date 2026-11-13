"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/11/2026
Description: The `player.*`, `npc.*`, and `message.*` names of the dialogue
             vocabulary (DESIGN-0017): the two sides of a conversation, and
             a line to the log of the player.

             The NPC can be absent. A test can run a script with no NPC, and
             a staff command can open one. Each `npc.*` name then gives a
             safe text and does not raise.
"""

from systems.gameplay.dialogue.vocabulary import action, value
from systems.interface.statefeed import constants as feed_const
from systems.interface.ui.colors import RESET_COLOR, SUCCESS_COLOR, title


# ─── Private constant definitions ────────────────────────────────────────────

# A line that a script sends to the log is something that happens in a
# conversation, so it goes to the tab of the dialogue lines.
_MSG_DIALOGUE = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_DIALOGUE}


# ─── Private helper routines ─────────────────────────────────────────────────

def _npc_description(context: object) -> str:
    """What `look` shows for the NPC, or an empty text."""
    if context.npc is None:
        return ""

    # get_display_desc, not db.desc: the NpcDef owns the description.
    description = context.npc.get_display_desc(context.caller)

    return description or ""


# ─── The values ──────────────────────────────────────────────────────────────

@value("player.name", "The name of the player character.")
def _player_name(context: object) -> str:
    return str(context.caller.key)


@value("npc.name", "The name of the NPC that speaks.")
def _name(context: object) -> str:
    return context.npc_name()


@value("npc.description", "The description of the NPC, as `look` shows it.")
def _description(context: object) -> str:
    return _npc_description(context)


@value("npc.heading", "The name of the NPC as a heading.")
def _heading(context: object) -> str:
    heading = title(context.npc_name())

    return heading


@value("npc.header", "The name of the NPC as a heading, and its description below it.")
def _header(context: object) -> str:
    heading = title(context.npc_name())
    description = _npc_description(context)

    if not description:
        return heading

    return f"{heading}\n{description}"


# ─── The actions ─────────────────────────────────────────────────────────────

@action("message.success", "Send one line to the log of the player, in the success colour.")
def _message_success(context: object, text: str) -> None:
    # The line goes to the log, not into the beat. Thus, it stays on the
    # screen after the next beat takes the place of this one.
    context.caller.msg((f"{SUCCESS_COLOR}{text}{RESET_COLOR}", _MSG_DIALOGUE))
