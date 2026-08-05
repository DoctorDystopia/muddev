"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: EvMenu nodes for the combat options screen: pick which combat
             style is active on the currently wielded weapon.
"""

from systems.combat.combat import (
    active_combat_style_key,
    available_combat_styles,
    held_weapon,
    set_combat_style,
)
from systems.ui.colors import (
    ERROR_COLOR,
    HIGHLIGHT_COLOR,
    RESET_COLOR,
    SUCCESS_COLOR,
    TITLE_COLOR,
)


ACTIVE_MARKER = "(active)"


def _skill_names(skill_keys) -> str:
    """Resolve an iterable (or single string) of skill keys to a
    comma-separated list of display names via SKILL_REGISTRY.

    Deferred import for the same reason as combat.py::_labelled_awards: this
    module is reachable from typeclass modules during startup, before the
    registry's skill_defs walk is safe to trigger.
    """
    from systems.progression.skills.registry import SKILL_REGISTRY

    if isinstance(skill_keys, str):
        skill_keys = (skill_keys,)

    names = []
    for skill_key in skill_keys or ():
        skill_class = SKILL_REGISTRY.get(skill_key)
        names.append(getattr(skill_class, "name", skill_key))

    return ", ".join(names) if names else "(none)"


def _boost_text(level_boost: dict) -> str:
    """Render a weapon_style_level_boost dict as 'Strike +3, Brawn +1'."""
    from systems.progression.skills.registry import SKILL_REGISTRY

    parts = []
    for skill_key, amount in (level_boost or {}).items():
        skill_class = SKILL_REGISTRY.get(skill_key)
        display_name = getattr(skill_class, "name", skill_key)
        parts.append(f"{display_name} +{amount}")

    return ", ".join(parts) if parts else "(none)"


def start(caller: object, **kwargs) -> tuple:
    weapon = held_weapon(caller)

    if weapon is None:
        text = f"{ERROR_COLOR}You have no weapon equipped.{RESET_COLOR}"
        options = ({"desc": "Exit", "goto": "node_exit"},)
        return text, options

    styles = available_combat_styles(weapon)

    if not styles:
        text = f"{HIGHLIGHT_COLOR}{weapon.key}{RESET_COLOR} has no combat styles to choose from."
        options = ({"desc": "Exit", "goto": "node_exit"},)
        return text, options

    active_key = active_combat_style_key(weapon)

    text_lines = [f"{TITLE_COLOR}--- Combat Options: {weapon.key} ---{RESET_COLOR}"]
    options_list = []

    for style_key, style in styles.items():
        marker = f" {SUCCESS_COLOR}{ACTIVE_MARKER}{RESET_COLOR}" if style_key == active_key else ""
        attack_type = str(style.get("attack_type", "")).title()
        weapon_style = str(style.get("weapon_style", "")).title()
        boost_text = _boost_text(style.get("weapon_style_level_boost"))
        xp_text = _skill_names(style.get("weapon_style_xp_skill"))

        style_line = (
            f"  {HIGHLIGHT_COLOR}{style_key.title()}{RESET_COLOR}{marker} "
            f"— {attack_type}. Style: {weapon_style}. "
            f"Boosts: {boost_text}. XP: {xp_text}"
        )
        text_lines.append(style_line)

        options_list.append({
            "desc": f"Use {style_key.title()} style",
            "goto": ("node_set_style", {"style_key": style_key}),
        })

    text = "\n".join(text_lines)
    options_list.append({"desc": "Exit", "goto": "node_exit"})
    return text, tuple(options_list)


def node_set_style(caller: object, **kwargs) -> tuple:
    style_key = kwargs.get("style_key")

    weapon = held_weapon(caller)
    if weapon is None:
        text = f"{ERROR_COLOR}You no longer have a weapon equipped.{RESET_COLOR}"
        options = ({"desc": "Back to combat options", "goto": "start"},)
        return text, options

    if set_combat_style(weapon, style_key, combatant=caller):
        text = f"{SUCCESS_COLOR}You switch to {style_key.title()} style.{RESET_COLOR}"
    else:
        text = f"{ERROR_COLOR}That style is no longer available on {weapon.key}.{RESET_COLOR}"

    options = (
        {"desc": "Back to combat options", "goto": "start"},
        {"desc": "Exit", "goto": "node_exit"},
    )
    return text, options


def node_exit(caller: object, **kwargs) -> tuple:
    text = "Closing combat options menu."
    return text, None
