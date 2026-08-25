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
from systems.menus.base_menu import back_option, cancel_option, parse_quantity
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
_PROMPT_XP = "How much XP for {skill_key}? (1-{maximum})"
_PROMPT_LEVEL = "What level for {skill_key}? ({minimum}-{maximum})"
_PROMPT_ACCOUNT = "Account name, optionally 'name : reason':"
_PROMPT_TARGET = "Whose character? (a name, or blank for yourself)"

_BAD_NUMBER = "Enter a whole number between {minimum} and {maximum}."

_BACK_TO_EGG = "Back to the egg"



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
        out of a mis-aimed action is one keystroke.

        The match must be something with progression and combat state on it --
        `skills` is the cheapest thing only a Character has. Without that
        check, `search` happily returns the sword lying on the floor, and the
        next spawn aims at it.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    typed = (raw_string or "").strip()

    if not typed:
        _set_target(caller, caller)

        return True, _TARGET_LINE.format(target=caller.key)

    found = caller.search(typed, global_search=True)

    if found is None:
        return False, dev_constants.MSG_NO_TARGET

    is_character = hasattr(found, "skills")

    if not is_character:
        return False, dev_constants.MSG_NO_TARGET

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


# Bound after the handlers above, which they name.
_PROMPT_TABLE = {
    "node_spawn_qty": _Prompt(node="node_spawn_qty", handler=_handle_spawn,
                              back_node="node_spawn"),
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
        {"desc": "Spawn an item", "goto": "node_spawn"},
        {"desc": "Toggle god mode", "goto": _goto_godmode},
        {"desc": "Restore (full HP, out of combat)", "goto": _goto_restore},
        {"desc": "Teleport to a map", "goto": "node_teleport"},
        {"desc": "Grant XP", "goto": "node_xp_skill"},
        {"desc": "Set a skill level", "goto": "node_level_skill"},
        {"desc": "Boot or ban an account", "goto": "node_account"},
        {"desc": "Change target", "goto": "node_target"},
    )

    return text, options


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


def node_teleport(caller, **kwargs):
    """List every map the manifest names."""
    zcoords = dev_actions.map_zcoords()
    text = f"{_HEADING}\n\nTeleport {_target(caller).key} to which map?"
    options = _key_options(zcoords, _goto_teleport, "zcoord")
    options.append(back_option(_BACK_TO_EGG, "start"))

    return text, tuple(options)


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


def _goto_teleport(caller, raw_string, **kwargs) -> str:
    """Move the target to the chosen map and return to the root."""
    target = _target(caller)
    zcoord = kwargs.get("zcoord", "")
    _succeeded, message = dev_actions.teleport_to_map(caller, target, zcoord)
    _report(caller, message)

    return "start"
