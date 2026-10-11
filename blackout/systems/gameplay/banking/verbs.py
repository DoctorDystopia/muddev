"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/08/2026
Description: The layout verbs of the `bank` command: tabs, view, move, swap,
             name, placeholders and release.

             `bank` alone opens the vault. `bank <verb> ...` changes its
             layout. The Godot pop-up sends these same lines for a tab click,
             a drag and a menu entry. Thus, a telnet player can do all of it
             by hand, and every lock on the terminal still applies.

             Each verb is one routine in one table, (caller, rest) -> line.
             The handler does the work and gives the reason for a refusal.
             This module only reads the arguments and words the result.
"""

from . import constants as bank_const
from . import layout as vault_layout


# ─── Public constant definitions ─────────────────────────────────────────────

USAGE: str = (
    "Usage: bank | bank tabs | bank view <tab> | bank move <item> = <tab|new> | "
    "bank swap <item> = <item> | bank name <tab> [= <name>] | "
    "bank placeholders <on|off> | bank release <item|all>")

MSG_VIEW: str = "You look at {tab}."
MSG_MOVE: str = "You move {item} to {tab}."
MSG_SWAP: str = "You swap {first} and {second}."
MSG_NAMED: str = "{tab} is now called '{name}'."
MSG_UNNAMED: str = "{tab} shows the icon of its first item again."
MSG_PLACEHOLDERS: str = "Placeholders are {state}."
MSG_RELEASED_ONE: str = "You release the placeholder for {item}."
MSG_RELEASED_ALL: str = "You release {count} placeholder(s)."
MSG_NOTHING_TO_RELEASE: str = "You have no placeholders."

LABEL_MAIN_TAB: str = "the main tab"
LABEL_TAB: str = "tab {index}"
LABEL_PLACEHOLDER: str = " (placeholder)"
LIST_HEADING: str = "Your vault tabs ({state} placeholders):"
LIST_ROW: str = "{marker}{label}: {items}"
LIST_VIEWED_MARKER: str = "* "
LIST_OTHER_MARKER: str = "  "
LIST_EMPTY: str = "nothing"


# ─── Private helper routines ─────────────────────────────────────────────────

def _split_pair(rest: str) -> tuple:
    """Split "<left> = <right>" into two stripped strings. The right side is
    "" when there is no separator."""
    left, _separator, right = rest.partition(bank_const.ARG_SEPARATOR)

    return left.strip(), right.strip()


def _tab_number(text: str):
    """Return the tab number `text` names, or None. Digits only, so "0" is
    the main tab and nothing else is."""
    stripped = text.strip()

    return int(stripped) if stripped.isdigit() else None


def _tab_label(index: int, names: list) -> str:
    """Name one tab in a line: "the main tab", "tab 2", or "tab 2 (Ores)"."""
    if index == bank_const.MAIN_TAB:
        label = LABEL_MAIN_TAB
    else:
        label = LABEL_TAB.format(index=index)

    if 0 <= index < len(names) and names[index]:
        label = f"{label} ({names[index]})"

    return label


def _switch_state(keep: bool) -> str:
    """Spell a placeholder switch the way the player types it."""
    return bank_const.SWITCH_ON_WORD if keep else bank_const.SWITCH_OFF_WORD


def _tab_line(current, index: int) -> str:
    """One line of `bank tabs`: the tab and the items in it, in order."""
    items = []

    for name in current.tabs[index]:
        shown = vault_layout.display_key(current, name)

        if vault_layout.is_placeholder(current, name):
            shown += LABEL_PLACEHOLDER

        items.append(shown)

    viewed = index == current.viewed
    marker = LIST_VIEWED_MARKER if viewed else LIST_OTHER_MARKER
    label = _tab_label(index, current.names).capitalize()

    return LIST_ROW.format(marker=marker, label=label,
                           items=", ".join(items) or LIST_EMPTY)


# ─── The verbs ───────────────────────────────────────────────────────────────

def _verb_tabs(caller, rest: str) -> str:
    """List every tab and its items, the main tab first as the vault shows it."""
    current = caller.bank.layout()
    state = _switch_state(current.keep_placeholders)
    lines = [LIST_HEADING.format(state=state)]

    for index in range(bank_const.MAIN_TAB, len(current.tabs)):
        lines.append(_tab_line(current, index))

    return "\n".join(lines)


def _verb_view(caller, rest: str) -> str:
    """`bank view <tab>`: look at one tab."""
    index = _tab_number(rest)

    if index is None:
        return USAGE

    refusal = caller.bank.view_tab(index)

    if refusal:
        return refusal

    names = caller.bank.layout().names

    return MSG_VIEW.format(tab=_tab_label(index, names))


def _verb_move(caller, rest: str) -> str:
    """`bank move <item> = <tab|new>`: move one slot to the end of a tab."""
    needle, target_text = _split_pair(rest)
    target = target_text.lower()

    if target != bank_const.NEW_TAB_WORD:
        target = _tab_number(target_text)

    if not needle or target is None:
        return USAGE

    refusal = caller.bank.move_to_tab(needle, target)

    if refusal:
        return refusal

    current = caller.bank.layout()
    name = vault_layout.resolve(current, needle)
    index = vault_layout.tab_of(current, name)

    return MSG_MOVE.format(item=vault_layout.display_key(current, name),
                           tab=_tab_label(index, current.names))


def _verb_swap(caller, rest: str) -> str:
    """`bank swap <item> = <item>`: swap the places of two slots."""
    first, second = _split_pair(rest)

    if not first or not second:
        return USAGE

    refusal = caller.bank.swap_slots(first, second)

    if refusal:
        return refusal

    current = caller.bank.layout()
    first_key = vault_layout.display_key(current, vault_layout.resolve(current, first))
    second_key = vault_layout.display_key(current, vault_layout.resolve(current, second))

    return MSG_SWAP.format(first=first_key, second=second_key)


def _verb_name(caller, rest: str) -> str:
    """`bank name <tab> = <name>` names a tab. With no name, the tab shows
    its item icon again."""
    index_text, text = _split_pair(rest)
    index = _tab_number(index_text)

    if index is None:
        return USAGE

    refusal = caller.bank.rename_tab(index, text)

    if refusal:
        return refusal

    names = caller.bank.layout().names
    label = _tab_label(index, []).capitalize()

    if not names[index]:
        return MSG_UNNAMED.format(tab=label)

    return MSG_NAMED.format(tab=label, name=names[index])


def _verb_placeholders(caller, rest: str) -> str:
    """`bank placeholders <on|off>`: keep a placeholder when an item leaves."""
    switch = rest.strip().lower()

    if switch not in (bank_const.SWITCH_ON_WORD, bank_const.SWITCH_OFF_WORD):
        return USAGE

    keep = switch == bank_const.SWITCH_ON_WORD
    caller.bank.set_keep_placeholders(keep)

    return MSG_PLACEHOLDERS.format(state=_switch_state(keep))


def _verb_release(caller, rest: str) -> str:
    """`bank release <item|all>`: free the slot of a placeholder."""
    needle = rest.strip()

    if not needle:
        return USAGE

    if needle.lower() == bank_const.RELEASE_ALL_WORD:
        freed = caller.bank.release_placeholders()

        return MSG_RELEASED_ALL.format(count=freed) if freed else MSG_NOTHING_TO_RELEASE

    current = caller.bank.layout()
    name = vault_layout.resolve(current, needle)
    refusal = caller.bank.release_placeholder(needle)

    if refusal:
        return refusal

    return MSG_RELEASED_ONE.format(item=vault_layout.display_key(current, name))


_VERBS: dict = {
    bank_const.VERB_TABS: _verb_tabs,
    bank_const.VERB_VIEW: _verb_view,
    bank_const.VERB_MOVE: _verb_move,
    bank_const.VERB_SWAP: _verb_swap,
    bank_const.VERB_NAME: _verb_name,
    bank_const.VERB_PLACEHOLDERS: _verb_placeholders,
    bank_const.VERB_RELEASE: _verb_release,
}


# ─── Public routines ─────────────────────────────────────────────────────────

def perform(caller, args: str) -> str:
    """
    Purpose: Run one layout verb of the `bank` command.

    Entry:
        caller - a Character with a bank handler.
        args   - the text after `bank`, for example "move iron ore = 2".

    Exit/Returns:
        Returns the line to send the caller. Plain text, for the reason
        banking/messages.py gives.

    Module Globals:
        _VERBS, USAGE read.

    Methodology:
        The first word picks the verb from the table. The rest of the line
        goes to the verb as it is.

    Notes/References:
        A new verb is one routine and one row in _VERBS.

    Author: Nick Hobar
    Creation date: 10/08/2026
    """
    verb, _space, rest = args.strip().partition(" ")
    handler = _VERBS.get(verb.lower())

    if handler is None:
        return USAGE

    return handler(caller, rest)
