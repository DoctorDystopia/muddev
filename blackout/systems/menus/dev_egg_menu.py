"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: EvMenu nodes for the Moderator Egg -- spawn, god mode, restore,
             teleport, XP, levels, and the delegated account commands.

             PRESENTATION ONLY. Every node here reads a list out of
             systems/devtools/actions.py, asks a question about it, and hands
             the answer back to the same module. No node applies an effect
             itself, and none of them checks a permission -- CmdEgg's lock did
             that before the menu opened.

             Deliberately not part of systems/devtools/. The effects have to
             stay callable from a test, a script or a future command with no
             EvMenu anywhere in sight, and a package that imports EvMenu is a
             package a test has to boot a session to touch.
"""

from dataclasses import dataclass
from typing import Callable

from systems.devtools import actions as dev_actions
from systems.devtools import constants as dev_constants
from systems.devtools import dossier as dev_dossier
from systems.menus.base_menu import back_option, cancel_option, parse_quantity
from systems.menus.constants import CONFIRM_YES_KEYS
from systems.progression.skills import constants as skill_constants
from systems.ui.colors import (
    ERROR_COLOR,
    HIGHLIGHT_COLOR,
    RESET_COLOR,
    TITLE_COLOR,
)


# Public constant definitions

# Spoken by BlackoutEvMenu.close_menu, however the menu is closed.
CLOSING_TEXT = "The egg cools in your hand."


# ─── Private constant definitions ────────────────────────────────────────────

# Attributes stashed on the live EvMenu instance, which is where every
# Blackout menu keeps the state its nodes share (the NPC dialogues do the same
# with `npc`). Never db attributes: a moderator's selected target is scoped to
# one open menu, and a target that outlived the screen it was chosen on is a
# spawn landing on whoever was picked an hour ago.
_TARGET_ATTR = "mod_target"
_RESULT_ATTR = "mod_result"

# The two-pass marker for a typed-input node. First visit renders the prompt
# and arms a _default option that re-enters the node carrying this; the second
# visit is the one that parses. Copied from banking's custom-quantity node,
# which is the idiom that works.
_STATE_KEY = "egg_prompt_state"
_STATE_AWAITING = "awaiting"

_HEADING = f"{TITLE_COLOR}--- Moderator Egg ---{RESET_COLOR}"
_TARGET_LINE = f"Target: {HIGHLIGHT_COLOR}{{target}}{RESET_COLOR}"
_GODMODE_LINE = "God mode: {state}"

_PROMPT_SPAWN = "How many {item_key}? (1-{maximum})"
_PROMPT_NPC = "How many {npc_key}? (1-{maximum}) They spawn live and hostile."
_PROMPT_TELEPORT_PLAYER = "Send {target} to which character?"
_PROMPT_XP = "How much XP for {skill_key}? (1-{maximum})"
_PROMPT_LEVEL = "What level for {skill_key}? ({minimum}-{maximum})"
_PROMPT_ACCOUNT = "Account name, optionally 'name : reason':"
_PROMPT_TARGET = "Whose character? (a name, or blank for yourself)"

_BAD_NUMBER = "Enter a whole number between {minimum} and {maximum}."

_BACK_TO_EGG = "Back to the egg"

# Quest screens.
_QUEST_LIST_ROW = "{quest_key}  ({status})"
_QUEST_DETAIL_TITLE = f"{TITLE_COLOR}{{title}}{RESET_COLOR}"
_QUEST_DETAIL_STATUS = f"Status: {HIGHLIGHT_COLOR}{{status}}{RESET_COLOR}"
_QUEST_DETAIL_STEP = f"Step:   {HIGHLIGHT_COLOR}{{step_key}}{RESET_COLOR}"
_NO_STEP = "-"
_CURRENT_STEP_MARK = f"{HIGHLIGHT_COLOR}(current){RESET_COLOR}"
_NO_QUESTS = (
    "The quest registry is empty. That is either a game with no quests or "
    "every content module failing to import inside the loader -- check "
    "GLOBAL_QUEST_REGISTRY.load_errors."
)
_UNKNOWN_QUEST_OPERATION = "That quest operation does not exist."

# Shown when the target is in no room at all -- a logged-out character, or one
# mid-move. Rare, but every screen that names a destination has to say
# something when there is not one.
_NOWHERE = "nowhere"

# The confirmation. Counts what is about to be destroyed rather than asking
# "are you sure": a moderator who reads the numbers and the name catches a
# wrong target, one who reads "are you sure?" confirms it.
_CLEAR_WARNING = (
    "This DESTROYS {carried} carried and {equipped} equipped items belonging "
    "to {target}. It cannot be undone. Staff items are left alone."
)



# ─── Private helper routines ─────────────────────────────────────────────────

def _menu(caller):
    """Return the live EvMenu instance driving this screen, or None."""
    instance = caller.ndb._evmenu

    return instance


def _set_target(caller, character) -> None:
    """Remember which character the next action applies to."""
    menu = _menu(caller)

    if menu is not None:
        setattr(menu, _TARGET_ATTR, character)


def _target(caller):
    """
    Purpose: Resolve who the moderator's actions currently apply to.

    Entry:
        caller is the moderator's Character.

    Exit/Returns:
        Returns the selected Character, falling back to the caller.

    Module Globals:
        _TARGET_ATTR read.

    Methodology:
        A stored target whose row has been deleted resolves back to the
        caller. Otherwise a moderator whose target logged out and was purged
        would aim every subsequent action at a dead reference and see a
        traceback per menu option.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    menu = _menu(caller)
    stored = getattr(menu, _TARGET_ATTR, None) if menu is not None else None

    if stored is None:
        return caller

    alive_row = getattr(stored, "pk", None) is not None

    if not alive_row:
        return caller

    return stored


def _report(caller, message: str) -> None:
    """Stash one outcome line for the next render of `start` to print."""
    menu = _menu(caller)

    if menu is not None:
        setattr(menu, _RESULT_ATTR, message)


def _take_report(caller) -> str:
    """
    Purpose: Read and clear the pending outcome line.

    Entry:
        caller is the moderator's Character.

    Exit/Returns:
        Returns the stashed message, or "" when there is none.

    Module Globals:
        _RESULT_ATTR read and written.

    Methodology:
        Every action routes home to `start` and prints its result THERE,
        rather than msg()-ing it as it happens. A msg() lands above the node
        text EvMenu is about to redraw, so on a graphical client it scrolls
        off behind the menu; printing it in the header keeps the confirmation
        on screen with the state it changed.

        Cleared on read so the line appears once, not on every redraw.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    menu = _menu(caller)

    if menu is None:
        return ""

    pending = getattr(menu, _RESULT_ATTR, "")
    setattr(menu, _RESULT_ATTR, "")

    return pending or ""


def _parse_bounded_int(raw_string: str, minimum: int, maximum: int) -> tuple:
    """
    Purpose: Read a typed integer that may legitimately be zero.

    Entry:
        raw_string is whatever the moderator typed. minimum and maximum are
        inclusive bounds.

    Exit/Returns:
        Returns (value, error_message); exactly one is non-None.

    Module Globals:
        _BAD_NUMBER read.

    Methodology:
        Separate from base_menu.parse_quantity, which refuses anything below
        1. That refusal is right for "how many do you want" and wrong for
        "what level" -- MIN_BASE_SKILL_LEVEL is 0, and a menu that cannot
        express the bottom of the range cannot undo what it did to the top.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    cleaned = (raw_string or "").strip()

    try:
        value = int(cleaned)
    except (ValueError, TypeError):
        return None, _BAD_NUMBER.format(minimum=minimum, maximum=maximum)

    below = value < minimum
    above = value > maximum

    if below or above:
        return None, _BAD_NUMBER.format(minimum=minimum, maximum=maximum)

    return value, None


# ─── Typed-prompt handlers ───────────────────────────────────────────────────
# Each takes (caller, raw_string, kwargs) and returns (accepted, message).
# `accepted` False re-renders the prompt with the message as an error; True
# stashes the message and drops back to the root.

def _handle_spawn(caller, raw_string: str, kwargs: dict) -> tuple:
    """Parse a spawn count, then deliver the item."""
    maximum = dev_constants.MAX_SPAWN_QUANTITY
    count, parse_error = parse_quantity(raw_string, maximum)

    if parse_error is not None:
        return False, parse_error

    item_key = kwargs.get("item_key", "")
    target = _target(caller)
    succeeded, message = dev_actions.grant_item(caller, target, item_key, count)

    return succeeded, message


def _handle_xp(caller, raw_string: str, kwargs: dict) -> tuple:
    """Parse an XP amount, then grant it."""
    maximum = dev_constants.MAX_XP_GRANT
    amount, parse_error = parse_quantity(raw_string, maximum)

    if parse_error is not None:
        return False, parse_error

    skill_key = kwargs.get("skill_key", "")
    target = _target(caller)
    succeeded, message = dev_actions.grant_xp(caller, target, skill_key, amount)

    return succeeded, message


def _handle_level(caller, raw_string: str, kwargs: dict) -> tuple:
    """Parse a skill level, then set it."""
    minimum = skill_constants.MIN_BASE_SKILL_LEVEL
    maximum = skill_constants.MAX_BASE_SKILL_LEVEL
    level, parse_error = _parse_bounded_int(raw_string, minimum, maximum)

    if parse_error is not None:
        return False, parse_error

    skill_key = kwargs.get("skill_key", "")
    target = _target(caller)
    succeeded, message = dev_actions.set_skill_level(caller, target, skill_key, level)

    return succeeded, message


def _handle_account(caller, raw_string: str, kwargs: dict) -> tuple:
    """Split 'name : reason' and dispatch the stock account command."""
    separator = dev_constants.ACCOUNT_REASON_SEPARATOR
    typed = (raw_string or "").strip()
    account_name, _found, reason = typed.partition(separator)

    command_key = kwargs.get("command_key", "")
    action = kwargs.get("action", "")
    succeeded, message = dev_actions.delegate_account_command(
        caller,
        command_key,
        account_name,
        action,
        reason,
    )

    return succeeded, message


def _handle_npc(caller, raw_string: str, kwargs: dict) -> tuple:
    """Parse an NPC count, then spawn them into the target's room."""
    maximum = dev_constants.MAX_NPC_SPAWN
    count, parse_error = parse_quantity(raw_string, maximum)

    if parse_error is not None:
        return False, parse_error

    npc_key = kwargs.get("npc_key", "")
    target = _target(caller)
    succeeded, message = dev_actions.spawn_npc(caller, target, npc_key, count)

    return succeeded, message


def _handle_teleport_player(caller, raw_string: str, kwargs: dict) -> tuple:
    """Resolve a named character, then send the target to their room."""
    other, error = _resolve_character(caller, raw_string)

    if other is None:
        return False, error

    target = _target(caller)
    succeeded, message = dev_actions.teleport_to_character(caller, target, other)

    return succeeded, message


def _resolve_character(caller, typed: str) -> tuple:
    """
    Purpose: Turn a typed name into a Character, or explain why not.

    Entry:
        caller is the moderator, whose `search` does the matching. typed is
        whatever they entered.

    Exit/Returns:
        Returns (character, error_message). Exactly one is non-None.

    Module Globals:
        dev_constants.MSG_NO_TARGET read.

    Methodology:
        The match must have progression and combat state on it -- `skills` is
        the cheapest thing only a Character has. Without that check, `search`
        happily returns the sword lying on the floor, and the next action aims
        at it.

    Notes/References:
        Shared by the target picker and the teleport-to-player prompt. They
        ask the same question, and a second copy of the Character test is a
        second place for it to be wrong.

        caller.search messages the caller itself on a miss, so the error
        returned here is a second line rather than the only one. That is
        deliberate: the prompt has to redraw with SOMETHING in its error slot.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    cleaned = (typed or "").strip()

    if not cleaned:
        return None, dev_constants.MSG_NO_TARGET

    found = caller.search(cleaned, global_search=True)

    if found is None:
        return None, dev_constants.MSG_NO_TARGET

    is_character = hasattr(found, "skills")

    if not is_character:
        return None, dev_constants.MSG_NO_TARGET

    return found, None


def _handle_target(caller, raw_string: str, kwargs: dict) -> tuple:
    """
    Purpose: Point the menu at another character.

    Entry:
        raw_string is a typed name, or blank to mean "myself".

    Exit/Returns:
        Returns (accepted, message).

    Module Globals:
        dev_constants.MSG_NO_TARGET read.

    Methodology:
        A blank entry resets to the caller rather than erroring, so backing
        out of a mis-aimed action is one keystroke. That is why this cannot
        just call _resolve_character and be done: a blank name means something
        HERE and means nothing at a teleport prompt.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    typed = (raw_string or "").strip()

    if not typed:
        _set_target(caller, caller)

        return True, _TARGET_LINE.format(target=caller.key)

    found, error = _resolve_character(caller, typed)

    if found is None:
        return False, error

    _set_target(caller, found)

    return True, _TARGET_LINE.format(target=found.key)


# ─── Module globals ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _Prompt:
    """One typed-input screen: where it re-enters, what it asks, who parses.

    Declared as data because all five prompts differ ONLY in those three
    things. Written as five node functions they would be five copies of the
    two-pass _default dance, and the fourth copy is where the cancel option
    stops matching the others.
    """

    node: str
    handler: Callable
    back_node: str = "start"


# The five quest writes, as data. One goto callable dispatches through this
# rather than five near-identical callables differing only in which action they
# call -- which is the shape the fourth copy always drifts out of.
#
# The label is here beside the function on purpose: "Abandon" and "Reset" are
# distinguishable only by what they do to the completion record, and a table
# that pairs each verb with the sentence explaining it is one edit, not two.
_QUEST_OPERATION_ACCEPT = "accept"
_QUEST_OPERATION_ABANDON = "abandon"
_QUEST_OPERATION_COMPLETE = "complete"
_QUEST_OPERATION_RESET = "reset"

_QUEST_OPERATIONS = {
    _QUEST_OPERATION_ACCEPT: dev_actions.accept_quest,
    _QUEST_OPERATION_ABANDON: dev_actions.abandon_quest,
    _QUEST_OPERATION_COMPLETE: dev_actions.complete_quest,
    _QUEST_OPERATION_RESET: dev_actions.reset_quest,
}

_QUEST_OPERATION_LABELS = (
    (_QUEST_OPERATION_ACCEPT, "Accept (starts it properly, fires step 1)"),
    (_QUEST_OPERATION_ABANDON, "Abandon (drops progress, keeps completion)"),
    (_QUEST_OPERATION_COMPLETE, "Complete (pays rewards)"),
    (_QUEST_OPERATION_RESET, "Reset (clears both, makes it takeable again)"),
)


# Bound after the handlers above, which they name.
_PROMPT_TABLE = {
    "node_spawn_qty": _Prompt(node="node_spawn_qty", handler=_handle_spawn,
                              back_node="node_spawn"),
    "node_npc_qty": _Prompt(node="node_npc_qty", handler=_handle_npc,
                            back_node="node_npc"),
    "node_teleport_player": _Prompt(node="node_teleport_player",
                                    handler=_handle_teleport_player),
    "node_xp_amount": _Prompt(node="node_xp_amount", handler=_handle_xp,
                              back_node="node_xp_skill"),
    "node_level_value": _Prompt(node="node_level_value", handler=_handle_level,
                                back_node="node_level_skill"),
    "node_account_name": _Prompt(node="node_account_name", handler=_handle_account,
                                 back_node="node_account"),
    "node_target": _Prompt(node="node_target", handler=_handle_target),
}



def _typed_node(caller, raw_string: str, prompt_text: str, node_name: str, **kwargs):
    """
    Purpose: Render, and on the second pass parse, one typed-input screen.

    Entry:
        raw_string is what the moderator typed (empty on the first pass).
        prompt_text is the already-formatted question. node_name keys
        _PROMPT_TABLE. kwargs carry whatever the handler needs, plus the
        two-pass marker.

    Exit/Returns:
        Returns a rendered (text, options) tuple -- never a node name. A node
        that returns a bare string prints that string at the player; see the
        EvMenu gotcha in CLAUDE.md.

    Module Globals:
        _PROMPT_TABLE, _STATE_KEY, _STATE_AWAITING read.

    Methodology:
        First visit: draw the question, arm a _default option that re-enters
        this same node with the marker set. Second visit: hand raw_string to
        the prompt's handler. A rejected answer redraws the question with the
        reason; an accepted one stashes the outcome and renders the root.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    prompt = _PROMPT_TABLE[node_name]
    re_entry = dict(kwargs)
    # EvMenu injects this into every node's kwargs and sets it again on the
    # next hop; carrying our own copy back would just shadow the live one.
    re_entry.pop("_current_nodename", None)
    re_entry[_STATE_KEY] = _STATE_AWAITING
    options = (
        {"key": "_default", "goto": (prompt.node, re_entry)},
        cancel_option(prompt.back_node),
    )
    text = f"{_HEADING}\n\n{prompt_text}"
    awaiting = kwargs.get(_STATE_KEY) == _STATE_AWAITING

    if not awaiting:
        return text, options

    accepted, message = prompt.handler(caller, raw_string, kwargs)

    if not accepted:
        return f"{text}\n\n{ERROR_COLOR}{message}{RESET_COLOR}", options

    _report(caller, message)
    rendered = start(caller)

    return rendered


def _key_options(keys, goto_node, extra_key: str) -> list:
    """
    Purpose: Turn a list of registry keys into one menu option each.

    Entry:
        keys is an ordered list of strings. goto_node is where choosing one
        leads -- a node NAME, or a goto callable for a list whose entries act
        immediately. extra_key names the kwarg the chosen key travels in.

    Exit/Returns:
        Returns a list of EvMenu option dicts, auto-numbered.

    Module Globals:
        None.

    Notes/References:
        Every list screen in this menu is this shape -- items, skills, maps --
        because all three are "pick one key out of a registry". The registries
        are read live, so adding an ItemDef, a skill or a map row reaches this
        menu with no edit here.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    options = []

    for key in keys:
        option = {"desc": key, "goto": (goto_node, {extra_key: key})}
        options.append(option)

    return options


# ─── Nodes ───────────────────────────────────────────────────────────────────

def start(caller, **kwargs):
    """
    Purpose: The egg's root screen -- current target, god-mode state, and
        every action it offers.

    Entry:
        caller is the moderator's Character.

    Exit/Returns:
        Returns the (text, options) tuple EvMenu renders.

    Module Globals:
        dev_constants.MSG_GODMODE_STATE_ON / _OFF read.

    Methodology:
        The header names the TARGET on every screen the moderator returns to.
        An egg whose actions silently apply to whoever was selected three
        screens ago is the one failure mode a tool like this must not have,
        and repeating the name is cheaper than any confirmation prompt.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    target = _target(caller)
    enabled = dev_actions.godmode_enabled(target)

    if enabled:
        state = dev_constants.MSG_GODMODE_STATE_ON
    else:
        state = dev_constants.MSG_GODMODE_STATE_OFF

    lines = [_HEADING, _TARGET_LINE.format(target=target.key),
             _GODMODE_LINE.format(state=state)]
    pending = _take_report(caller)

    if pending:
        lines.append("")
        lines.append(pending)

    text = "\n".join(lines)
    options = (
        {"desc": "Inspect (full dossier)", "goto": "node_inspect"},
        {"desc": "Spawn an item", "goto": "node_spawn"},
        {"desc": "Spawn an NPC (into the target's room)", "goto": "node_npc"},
        {"desc": "Toggle god mode", "goto": _goto_godmode},
        {"desc": "Restore (full HP, out of combat)", "goto": _goto_restore},
        {"desc": "Empty inventory (destroys carried AND equipped)",
         "goto": "node_clear_confirm"},
        {"desc": "Teleport to a map", "goto": "node_teleport"},
        {"desc": "Teleport to a player", "goto": "node_teleport_player"},
        {"desc": "Bring target to me", "goto": _goto_bring_here},
        {"desc": "Grant XP", "goto": "node_xp_skill"},
        {"desc": "Set a skill level", "goto": "node_level_skill"},
        {"desc": "Quests", "goto": "node_quest"},
        {"desc": "Boot or ban an account", "goto": "node_account"},
        {"desc": "Change target", "goto": "node_target"},
    )

    return text, options


def node_inspect(caller, **kwargs):
    """
    Purpose: Show the target's full dossier plus the staff addendum.

    Entry:
        caller is the moderator's Character.

    Exit/Returns:
        Returns the (text, options) tuple EvMenu renders.

    Module Globals:
        None.

    Methodology:
        The report IS the node text, not a msg() before it. A screen this long
        printed as a message would be redrawn off the top by the node EvMenu
        renders next; as node text it stays put until the moderator leaves it.

    Notes/References:
        Read-only, and the only node here that is. It still audits -- see
        dossier.render_report.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    target = _target(caller)
    report = dev_dossier.render_report(caller, target)
    options = (back_option(_BACK_TO_EGG, "start"),)

    return report, options


def node_target(caller, raw_string="", **kwargs):
    """Ask who the following actions apply to."""
    rendered = _typed_node(caller, raw_string, _PROMPT_TARGET, "node_target", **kwargs)

    return rendered


def node_spawn(caller, **kwargs):
    """List every item in ITEM_DB."""
    keys = dev_actions.item_keys()
    text = f"{_HEADING}\n\nWhich item?"
    options = _key_options(keys, "node_spawn_qty", "item_key")
    options.append(back_option(_BACK_TO_EGG, "start"))

    return text, tuple(options)


def node_spawn_qty(caller, raw_string="", **kwargs):
    """Ask how many of the chosen item to spawn."""
    item_key = kwargs.get("item_key", "")
    prompt_text = _PROMPT_SPAWN.format(
        item_key=item_key,
        maximum=dev_constants.MAX_SPAWN_QUANTITY,
    )
    rendered = _typed_node(caller, raw_string, prompt_text, "node_spawn_qty", **kwargs)

    return rendered


def node_npc(caller, **kwargs):
    """List every NPC in NPC_DB, to spawn into the target's room."""
    keys = dev_actions.npc_keys()
    room = _target(caller).location
    room_name = room.key if room is not None else _NOWHERE
    text = f"{_HEADING}\n\nSpawn which NPC into {room_name}?"
    options = _key_options(keys, "node_npc_qty", "npc_key")
    options.append(back_option(_BACK_TO_EGG, "start"))

    return text, tuple(options)


def node_npc_qty(caller, raw_string="", **kwargs):
    """Ask how many of the chosen NPC to spawn."""
    prompt_text = _PROMPT_NPC.format(
        npc_key=kwargs.get("npc_key", ""),
        maximum=dev_constants.MAX_NPC_SPAWN,
    )
    rendered = _typed_node(caller, raw_string, prompt_text, "node_npc_qty", **kwargs)

    return rendered


def node_clear_confirm(caller, **kwargs):
    """
    Purpose: Require an explicit yes before destroying a character's things.

    Entry:
        caller is the moderator's Character.

    Exit/Returns:
        Returns the (text, options) tuple EvMenu renders.

    Module Globals:
        _CLEAR_WARNING read, CONFIRM_YES_KEYS read.

    Methodology:
        The ONLY confirmation on the egg, because this is the only entry that
        cannot be undone by doing something else. A spawn can be cleared and a
        level can be set back; a deleted item is gone.

        The warning counts what is actually about to be destroyed rather than
        saying "are you sure". A moderator who reads "destroy 31 carried and 4
        equipped items from Bob" catches a wrong target; one who reads "are
        you sure?" confirms it.

    Notes/References:
        Bound to the shared yes key rather than left auto-numbered, so
        confirming is never the digit that meant something else on the last
        screen. See systems/menus/constants.py.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    target = _target(caller)
    carried = target.inventory.count_used()
    equipped = target.equipment.count_equipped()
    warning = _CLEAR_WARNING.format(
        target=target.key,
        carried=carried,
        equipped=equipped,
    )
    text = f"{_HEADING}\n\n{ERROR_COLOR}{warning}{RESET_COLOR}"
    options = (
        {"key": CONFIRM_YES_KEYS, "desc": "Yes, destroy them", "goto": _goto_clear},
        cancel_option("start"),
    )

    return text, options


def node_teleport(caller, **kwargs):
    """List every map the manifest names."""
    zcoords = dev_actions.map_zcoords()
    text = f"{_HEADING}\n\nTeleport {_target(caller).key} to which map?"
    options = _key_options(zcoords, _goto_teleport, "zcoord")
    options.append(back_option(_BACK_TO_EGG, "start"))

    return text, tuple(options)


def node_teleport_player(caller, raw_string="", **kwargs):
    """Ask which character to send the target to."""
    rendered = _typed_node(
        caller,
        raw_string,
        _PROMPT_TELEPORT_PLAYER.format(target=_target(caller).key),
        "node_teleport_player",
        **kwargs,
    )

    return rendered


def node_xp_skill(caller, **kwargs):
    """List every skill in SKILL_REGISTRY, for an XP grant."""
    keys = dev_actions.skill_keys()
    text = f"{_HEADING}\n\nGrant XP in which skill?"
    options = _key_options(keys, "node_xp_amount", "skill_key")
    options.append(back_option(_BACK_TO_EGG, "start"))

    return text, tuple(options)


def node_xp_amount(caller, raw_string="", **kwargs):
    """Ask how much XP to grant."""
    prompt_text = _PROMPT_XP.format(
        skill_key=kwargs.get("skill_key", ""),
        maximum=dev_constants.MAX_XP_GRANT,
    )
    rendered = _typed_node(caller, raw_string, prompt_text, "node_xp_amount", **kwargs)

    return rendered


def node_level_skill(caller, **kwargs):
    """List every skill in SKILL_REGISTRY, for a direct level set."""
    keys = dev_actions.skill_keys()
    text = f"{_HEADING}\n\nSet which skill's level?"
    options = _key_options(keys, "node_level_value", "skill_key")
    options.append(back_option(_BACK_TO_EGG, "start"))

    return text, tuple(options)


def node_level_value(caller, raw_string="", **kwargs):
    """Ask what level to set the chosen skill to."""
    prompt_text = _PROMPT_LEVEL.format(
        skill_key=kwargs.get("skill_key", ""),
        minimum=skill_constants.MIN_BASE_SKILL_LEVEL,
        maximum=skill_constants.MAX_BASE_SKILL_LEVEL,
    )
    rendered = _typed_node(caller, raw_string, prompt_text, "node_level_value", **kwargs)

    return rendered


def node_quest(caller, **kwargs):
    """
    Purpose: List every quest in the registry with the target's standing on it.

    Entry:
        caller is the moderator's Character.

    Exit/Returns:
        Returns the (text, options) tuple EvMenu renders.

    Module Globals:
        _QUEST_LIST_ROW, _NO_QUESTS read.

    Methodology:
        The STATUS goes in the option label, not one screen deeper. Choosing
        which quest to reset means knowing which are already complete, and a
        list that makes you open all six to find out is a list you stop using.

    Notes/References:
        An empty registry gets a message naming what it means. The loader
        swallows a content module's ImportError, so "no quests" and "every
        quest failed to load" look identical from here -- and the second is
        the state the game actually shipped in until 08/25/2026.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    target = _target(caller)
    keys = dev_actions.quest_keys()

    if not keys:
        text = f"{_HEADING}\n\n{ERROR_COLOR}{_NO_QUESTS}{RESET_COLOR}"

        return text, (back_option(_BACK_TO_EGG, "start"),)

    text = f"{_HEADING}\n\nWhich quest, for {target.key}?"
    options = []

    for quest_key in keys:
        label = _QUEST_LIST_ROW.format(
            quest_key=quest_key,
            status=target.quests.status(quest_key),
        )
        options.append({
            "desc": label,
            "goto": ("node_quest_detail", {"quest_key": quest_key}),
        })

    options.append(back_option(_BACK_TO_EGG, "start"))

    return text, tuple(options)


def node_quest_detail(caller, **kwargs):
    """
    Purpose: Show one quest's state on the target, and offer every write.

    Entry:
        caller is the moderator's Character. kwargs carries quest_key.

    Exit/Returns:
        Returns the (text, options) tuple EvMenu renders.

    Module Globals:
        _QUEST_OPERATIONS, _QUEST_DETAIL_* read.

    Methodology:
        Every option is offered whether or not it currently applies. The
        effects each refuse with a message naming the precondition that
        failed, and a screen that hides "Abandon" on an inactive quest teaches
        nothing about why -- while a refusal that says "not active, accept it
        first" teaches exactly that.

        Abandon and Reset are labelled with what they do to the COMPLETION
        RECORD, because that is the entire difference between them and the
        one thing a moderator picking between them needs to know.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    target = _target(caller)
    quest_key = kwargs.get("quest_key", "")
    handler = target.quests
    step_key = handler.current_step_key(quest_key)

    lines = [
        _HEADING,
        "",
        _QUEST_DETAIL_TITLE.format(title=dev_actions.quest_title(quest_key)),
        _QUEST_DETAIL_STATUS.format(status=handler.status(quest_key)),
        _QUEST_DETAIL_STEP.format(step_key=step_key or _NO_STEP),
    ]

    for line in handler.objective_lines(quest_key):
        lines.append(f"  {line}")

    # Carried here by _goto_quest_op and _goto_quest_step. Printed as node
    # text rather than msg()-ed, so it sits above the status it just changed
    # instead of scrolling off behind the redraw.
    outcome = kwargs.get("result", "")

    if outcome:
        lines.append("")
        lines.append(outcome)

    text = "\n".join(lines)
    options = []

    for operation, label in _QUEST_OPERATION_LABELS:
        options.append({
            "desc": label,
            "goto": (_goto_quest_op, {"quest_key": quest_key, "operation": operation}),
        })

    options.append({
        "desc": "Jump to a step",
        "goto": ("node_quest_step", {"quest_key": quest_key}),
    })
    options.append(back_option("Back to the quest list", "node_quest"))

    return text, tuple(options)


def node_quest_step(caller, **kwargs):
    """
    Purpose: List one quest's steps, in blueprint order, to jump to.

    Entry:
        caller is the moderator's Character. kwargs carries quest_key.

    Exit/Returns:
        Returns the (text, options) tuple EvMenu renders.

    Module Globals:
        None.

    Methodology:
        Ordered, never sorted -- a quest's steps are a sequence, and an
        alphabetical list makes "back up one step" a puzzle. The current step
        is marked, so jumping back is a matter of counting upward from a
        visible position rather than remembering one.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    target = _target(caller)
    quest_key = kwargs.get("quest_key", "")
    step_keys = dev_actions.quest_step_keys(quest_key)
    current = target.quests.current_step_key(quest_key)

    text = f"{_HEADING}\n\nJump {target.key} to which step of '{quest_key}'?"
    options = []

    for step_key in step_keys:
        label = step_key

        if step_key == current:
            label = f"{step_key} {_CURRENT_STEP_MARK}"

        options.append({
            "desc": label,
            "goto": (_goto_quest_step, {"quest_key": quest_key, "step_key": step_key}),
        })

    options.append(back_option("Back to the quest", ("node_quest_detail",
                                                    {"quest_key": quest_key})))

    return text, tuple(options)


def node_account(caller, **kwargs):
    """
    Purpose: Offer the three stock account commands the egg delegates to.

    Entry:
        caller is the moderator's Character.

    Exit/Returns:
        Returns the (text, options) tuple EvMenu renders.

    Module Globals:
        dev_constants.ACCOUNT_COMMAND_*, ACTION_BOOT, ACTION_BAN, ACTION_UNBAN
        read.

    Methodology:
        These name an ACCOUNT, not the selected character target -- an account
        can be banned while nothing of theirs is logged in, which is most of
        the time a ban is wanted.

    Notes/References:
        `ban` and `unban` carry Evennia's own Developer lock. An Admin holding
        the egg reaches this screen, picks one, and is refused by the command
        itself with its own wording. That refusal is deliberately not
        pre-empted here: one owner for the permission, and it is Evennia's.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    text = f"{_HEADING}\n\nWhich account command?"
    options = (
        {
            "desc": "Boot (disconnect)",
            "goto": ("node_account_name", {
                "command_key": dev_constants.ACCOUNT_COMMAND_BOOT,
                "action": dev_constants.ACTION_BOOT,
            }),
        },
        {
            "desc": "Ban",
            "goto": ("node_account_name", {
                "command_key": dev_constants.ACCOUNT_COMMAND_BAN,
                "action": dev_constants.ACTION_BAN,
            }),
        },
        {
            "desc": "Unban",
            "goto": ("node_account_name", {
                "command_key": dev_constants.ACCOUNT_COMMAND_UNBAN,
                "action": dev_constants.ACTION_UNBAN,
            }),
        },
        back_option(_BACK_TO_EGG, "start"),
    )

    return text, options


def node_account_name(caller, raw_string="", **kwargs):
    """Ask which account, and optionally why."""
    rendered = _typed_node(
        caller,
        raw_string,
        _PROMPT_ACCOUNT,
        "node_account_name",
        **kwargs,
    )

    return rendered


# ─── Goto callables ──────────────────────────────────────────────────────────
# Unlike a node, a goto callable is EXPECTED to return a node name. These are
# the actions with nothing to ask: they fire and go home.

def _goto_godmode(caller, raw_string, **kwargs) -> str:
    """Flip the target's damage immunity and return to the root."""
    target = _target(caller)
    enabled = dev_actions.godmode_enabled(target)
    _succeeded, message = dev_actions.set_godmode(caller, target, not enabled)
    _report(caller, message)

    return "start"


def _goto_restore(caller, raw_string, **kwargs) -> str:
    """Heal the target to full, drop them out of combat, return to the root."""
    target = _target(caller)
    _succeeded, message = dev_actions.restore(caller, target)
    _report(caller, message)

    return "start"


def _goto_bring_here(caller, raw_string, **kwargs) -> str:
    """Pull the target into the moderator's own room.

    The same action teleport-to-player runs, with the arguments swapped: the
    moderator IS the destination. Worth its own root option rather than making
    someone select themselves as a destination they are already standing in.
    """
    target = _target(caller)
    _succeeded, message = dev_actions.teleport_to_character(caller, target, caller)
    _report(caller, message)

    return "start"


def _goto_clear(caller, raw_string, **kwargs) -> str:
    """Destroy the target's belongings, after the confirmation node."""
    target = _target(caller)
    _succeeded, message = dev_actions.clear_inventory(caller, target)
    _report(caller, message)

    return "start"


def _goto_teleport(caller, raw_string, **kwargs) -> str:
    """Move the target to the chosen map and return to the root."""
    target = _target(caller)
    zcoord = kwargs.get("zcoord", "")
    _succeeded, message = dev_actions.teleport_to_map(caller, target, zcoord)
    _report(caller, message)

    return "start"


def _goto_quest_op(caller, raw_string, **kwargs):
    """
    Purpose: Apply one of the four whole-quest writes, then redraw the quest.

    Entry:
        kwargs carries quest_key and operation, the latter a key of
        _QUEST_OPERATIONS.

    Exit/Returns:
        Returns (node name, kwargs) -- the form EvMenu accepts from a goto
        callable that needs to carry state onward. Landing back on the quest's
        own screen rather than the root is what makes "accept, then jump to
        step three" two keystrokes instead of six.

    Module Globals:
        _QUEST_OPERATIONS read.

    Methodology:
        The outcome travels forward in kwargs and is printed by the node it
        lands on, not msg()-ed here and not stashed in _report. _report is
        `start`'s channel, and a quest write that returns to the quest screen
        would leave its line sitting there until the moderator happened to
        visit the root -- reporting a completion three actions after it
        happened.

    Notes/References:
        An unknown operation cannot happen from the menu, whose options come
        from the same table. It is still handled, because a goto callable that
        raises leaves the player in a menu that will not move.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    quest_key = kwargs.get("quest_key", "")
    operation = kwargs.get("operation", "")
    action = _QUEST_OPERATIONS.get(operation)

    if action is None:
        _report(caller, f"{ERROR_COLOR}{_UNKNOWN_QUEST_OPERATION}{RESET_COLOR}")

        return "start"

    target = _target(caller)
    _succeeded, message = action(caller, target, quest_key)

    return "node_quest_detail", {"quest_key": quest_key, "result": message}


def _goto_quest_step(caller, raw_string, **kwargs):
    """Move the target to the chosen step and redraw the quest screen."""
    quest_key = kwargs.get("quest_key", "")
    step_key = kwargs.get("step_key", "")
    target = _target(caller)
    _succeeded, message = dev_actions.set_quest_step(caller, target, quest_key, step_key)

    return "node_quest_detail", {"quest_key": quest_key, "result": message}
