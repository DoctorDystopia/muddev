"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: EvMenu nodes for the combat options screen: pick which combat
             style is active on the currently wielded weapon.

             Rendered FROM systems/gameplay/combat/style_options.py, which is
             also what CHANNEL_CHAR_COMBAT ships to a graphical client -- so
             this menu and the Combat tab cannot describe a style differently.
"""

from systems.gameplay.combat import style_options
from systems.gameplay.combat.combat import held_weapon, set_combat_style
from systems.interface.menus.base_menu import back_option
from systems.interface.ui.colors import (
    ERROR_COLOR,
    HIGHLIGHT_COLOR,
    RESET_COLOR,
    SUCCESS_COLOR,
    TITLE_COLOR,
)


ACTIVE_MARKER = "(active)"

# Spoken by BlackoutEvMenu.close_menu, however the menu is closed.
CLOSING_TEXT = "Closing combat options menu."

# What a style with no boosts or no XP skill reads as.
NONE_TEXT = "(none)"


def _names(entries) -> str:
    """Join skill entries' display names: 'Strike, Brawn'."""
    names = []

    for entry in entries:
        names.append(entry["name"])

    return ", ".join(names) if names else NONE_TEXT


def _boost_text(boosts) -> str:
    """Render boost entries as 'Strike +3, Brawn +1'."""
    parts = []

    for boost in boosts:
        parts.append(f"{boost['name']} +{boost['amount']}")

    return ", ".join(parts) if parts else NONE_TEXT


def _style_line(row: dict) -> str:
    """One style as the menu prints it."""
    marker = f" {SUCCESS_COLOR}{ACTIVE_MARKER}{RESET_COLOR}" if row["active"] else ""
    attack_type = row["attack_type"].title()
    weapon_style = row["weapon_style"].title()
    boost_text = _boost_text(row["boosts"])
    xp_text = _names(row["xp_skills"])

    return (
        f"  {HIGHLIGHT_COLOR}{row['name']}{RESET_COLOR}{marker} "
        f"— {attack_type}. Style: {weapon_style}. "
        f"Boosts: {boost_text}. XP: {xp_text}"
    )


def start(caller: object, **kwargs) -> tuple:
    options = style_options.combat_options(caller)

    if not options.get("armed"):
        text = f"{ERROR_COLOR}You have no weapon equipped.{RESET_COLOR}"
        return text, None

    weapon_name = options["weapon_name"]

    # Only the rows the server would let a player pick. A held item with no
    # styles of its own reports the unarmed style it falls back to, and that
    # row carries no command.
    rows = []

    for row in options["styles"]:
        if row["command"]:
            rows.append(row)

    if not rows:
        text = f"{HIGHLIGHT_COLOR}{weapon_name}{RESET_COLOR} has no combat styles to choose from."
        return text, None

    text_lines = [f"{TITLE_COLOR}--- Combat Options: {weapon_name} ---{RESET_COLOR}"]
    options_list = []

    for row in rows:
        text_lines.append(_style_line(row))

        options_list.append({
            "desc": f"Use {row['name']} style",
            "goto": ("node_set_style", {"style_key": row["key"]}),
        })

    text = "\n".join(text_lines)
    return text, tuple(options_list)


def node_set_style(caller: object, **kwargs) -> tuple:
    style_key = kwargs.get("style_key")

    weapon = held_weapon(caller)
    if weapon is None:
        text = f"{ERROR_COLOR}You no longer have a weapon equipped.{RESET_COLOR}"
        options = (back_option("Back to combat options", "start"),)
        return text, options

    if set_combat_style(weapon, style_key, combatant=caller):
        switched = style_options.STYLE_SWITCHED_TEMPLATE.format(name=style_key.title())
        text = f"{SUCCESS_COLOR}{switched}{RESET_COLOR}"
    else:
        text = f"{ERROR_COLOR}That style is no longer available on {weapon.key}.{RESET_COLOR}"

    options = (back_option("Back to combat options", "start"),)
    return text, options
