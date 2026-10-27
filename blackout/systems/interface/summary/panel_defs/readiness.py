"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/08/2026
Description: Summary panel: what this character is currently set up to fight
             with -- weapon, style, and the bonuses a swing actually reads.
"""

from evennia.utils import logger

from systems.gameplay.combat import constants as combat_const
from systems.gameplay.combat.combat import combat_profile, held_weapon

from .. import constants as const
from .. import layout
from .base_panel import BasePanel


# Public constant definitions

PANEL_TITLE = "Combat Readiness"

LABEL_WIELDING = "Wielding"
LABEL_STYLE = "Style"
LABEL_EARNS_XP = "Earns XP"
LABEL_ATTACK = "Attack"
LABEL_STRENGTH = "Strength"
LABEL_DEFENCE = "Defence"

# The bonus keys come from the builders in combat/constants.py, the same
# builders that the swing uses. The strength key comes from the axes of the
# style. Thus, a bow shows the strength bonus of its arrow.
AXES_STRENGTH_KEY = "strength_bonus_key"

# Rendered after the tick count on the weapon row, e.g. "speed 4t".
SPEED_PREFIX = "speed "
SPEED_SUFFIX = "t"

# The one field of the structured band. The Character tab makes its group
# label from this key: "Total Combat Stat Bonuses".
TOTAL_BONUSES_KEY = "total_combat_stat_bonuses"


class ReadinessPanel(BasePanel):
    """
    Purpose: The state a swing resolves against, gathered onto one band.

    Entry:
        character is a Character.

    Exit/Returns:
        Not applicable -- see render / data.

    Module Globals:
        combat_const.UNARMED_WEAPON_NAME, combat_const.MELEE_ATTACK_TYPES read.

    Methodology:
        Everything here is read through combat.combat_profile, which is the ONE
        place that resolves where a combatant's stats come from -- weapon vs
        armour sum vs unarmed fallback. Reading equipment.slots directly would
        make this panel a second, divergent answer to that question, and it
        would get the two-handed case wrong the way the old main-hand-only
        checks did.

        The attack bonus shown is the one for the ACTIVE attack type only.
        Listing all three would be honest but useless: only one of them is
        being read this tick, and which one is exactly what the style row above
        it is telling the player.

    Notes/References:
        systems/interface/menus/combat_options_menu.py remains the place styles are
        CHANGED. This panel is read-only and links there.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """

    key = "readiness"
    title = PANEL_TITLE
    order = const.PANEL_ORDER_READINESS


    @classmethod
    def _weapon_name(cls, character: object) -> str:
        """
        Purpose: Name the wielded weapon, or the unarmed fallback.

        Entry:
            character is a Character.

        Exit/Returns:
            Returns a display name; never empty.

        Module Globals:
            combat_const.UNARMED_WEAPON_NAME read.

        Methodology:
            held_weapon checks the two-handed slot before the main hand, so a
            two-hander is not silently reported as bare hands.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        weapon = held_weapon(character)

        if weapon is None:
            return combat_const.UNARMED_WEAPON_NAME

        return str(weapon.key)


    @classmethod
    def _style_rows(cls, style: dict) -> list:
        """
        Purpose: Build the style and XP-award rows from an active style dict.

        Entry:
            style is an active_combat_style dict as produced by combat_profile.

        Exit/Returns:
            Returns a list of finished display lines.

        Module Globals:
            LABEL_STYLE, LABEL_EARNS_XP read.
            const.EMPTY_VALUE_TEXT read.

        Methodology:
            Both rows are WIDE rows rather than paired cells. "Aggressive /
            Slash" and "Brawn, Fortitude" both run past a value column, and
            layout.fields deliberately does not truncate an overlong value --
            pairing these two pushed the row to 66 columns on a 60-column
            screen.

            Skill keys are resolved to display names through SKILL_REGISTRY,
            deferred-imported for the same reason combat_options_menu defers
            it: this module is reachable during startup, before the registry's
            skill_defs walk is safe to trigger.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        from systems.gameplay.progression.skills.registry import SKILL_REGISTRY

        weapon_style = str(style.get("weapon_style", "")).title()
        attack_type = str(style.get("attack_type", "")).title()

        style_text = f"{weapon_style} / {attack_type}"

        xp_skills = style.get("weapon_style_xp_skill") or ()

        if isinstance(xp_skills, str):
            xp_skills = (xp_skills,)

        names = []
        for skill_key in xp_skills:
            skill_class = SKILL_REGISTRY.get(skill_key)
            display_name = getattr(skill_class, "name", skill_key)
            names.append(str(display_name))

        xp_text = ", ".join(names) or const.EMPTY_VALUE_TEXT
        rows = [
            layout.wide_field(LABEL_STYLE, style_text),
            layout.wide_field(LABEL_EARNS_XP, xp_text),
        ]

        return rows


    @classmethod
    def _defence_items(cls, bonuses: dict) -> list:
        """
        Purpose: Build one "<type> +N" item per melee defence axis.

        Entry:
            bonuses is a combat_stat_bonuses dict.

        Exit/Returns:
            Returns a list of plain strings, one per MELEE_ATTACK_TYPES entry.

        Module Globals:
            combat_const.MELEE_ATTACK_TYPES read.

        Methodology:
            Driven off MELEE_ATTACK_TYPES rather than three hand-written rows,
            so a fourth melee axis appears here the moment it is added there.
            All three ARE shown, unlike the attack side: a defender is hit by
            whatever the attacker chose, so no single one of them is "the
            active" one.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        items = []

        for attack_type in combat_const.MELEE_ATTACK_TYPES:
            bonus_key = combat_const.defense_bonus_key(attack_type)
            value = bonuses.get(bonus_key, 0)
            items.append(f"{attack_type} {value:+d}")

        return items


    @classmethod
    def _swing_bonuses(cls, style: dict, bonuses: dict) -> tuple:
        """
        Purpose: Read the attack and strength bonus that the active style
                 swings with.

        Entry:
            style is the active combat style. bonuses is a
            combat_stat_bonuses dict.

        Exit/Returns:
            Returns (attack_bonus, strength_bonus) as two ints.

        Module Globals:
            AXES_STRENGTH_KEY read.

        Methodology:
            The attack key comes from attack_bonus_key, and the strength key
            from style_combat_axes. ActionContext reads the same two. Thus,
            the band shows the numbers that the swing uses.

        Notes/References:
            A bow reads projectile_strength_bonus. Until 10/21/2026 this
            band read melee_strength_bonus for each style, and it showed +0
            for every bow.

        Author: Nick Hobar
        Creation date: 10/21/2026
        """
        attack_type = str(style.get("attack_type", ""))
        attack_key = combat_const.attack_bonus_key(attack_type)
        axes = combat_const.style_combat_axes(style)
        strength_key = axes[AXES_STRENGTH_KEY]

        attack_bonus = int(bonuses.get(attack_key, 0))
        strength_bonus = int(bonuses.get(strength_key, 0))

        return attack_bonus, strength_bonus


    @classmethod
    def _profile(cls, character: object) -> dict:
        """
        Purpose: Fetch the combat profile, tolerating a resolution failure.

        Entry:
            character is a Character.

        Exit/Returns:
            Returns a combat_profile dict, or None if resolution raised.

        Module Globals:
            None.

        Methodology:
            combat_profile touches the equipment handler and the wielded
            weapon's db. A broken item should cost the player this band, not
            the whole dossier -- service.py's guard would already catch it, but
            catching it here keeps the panel's own contract total.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        try:
            profile = combat_profile(character)
        except Exception as exc:
            logger.log_err(f"ReadinessPanel._profile failed: {exc!r}")

            return None

        return profile


    @classmethod
    def render(cls, character: object) -> list:
        """
        Purpose: Render the combat readiness band.

        Entry:
            character is a Character.

        Exit/Returns:
            Returns a list of display lines, empty if the profile could not be
            resolved.

        Module Globals:
            LABEL_* read, SPEED_PREFIX / SPEED_SUFFIX read.

        Methodology:
            Weapon, style and XP awards each get a wide row -- their values run
            past a value column. Only the attack and strength bonuses, which
            are always short, pair up.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        profile = cls._profile(character)

        if profile is None:
            return []

        style = profile["active_combat_style"]
        bonuses = profile["combat_stat_bonuses"]
        speed = profile["attack_speed"]

        weapon_text = (
            f"{cls._weapon_name(character)} "
            f"({SPEED_PREFIX}{speed}{SPEED_SUFFIX})"
        )

        attack_type = str(style.get("attack_type", ""))
        attack_bonus, strength_bonus = cls._swing_bonuses(style, bonuses)

        pairs = [
            (LABEL_ATTACK, f"{attack_type} {attack_bonus:+d}"),
            (LABEL_STRENGTH, f"{strength_bonus:+d}"),
        ]

        lines = [layout.wide_field(LABEL_WIELDING, weapon_text)]
        lines.extend(cls._style_rows(style))
        lines.extend(layout.fields(pairs))
        lines.extend(
            layout.wrapped_field(LABEL_DEFENCE, cls._defence_items(bonuses))
        )

        return lines


    @classmethod
    def data(cls, character: object) -> dict:
        """
        Purpose: Structured form of the readiness band.

        Entry:
            character is a Character.

        Exit/Returns:
            Returns a dict of plain JSON-safe values, empty if the profile
            could not be resolved.

        Module Globals:
            TOTAL_BONUSES_KEY read.

        Methodology:
            The band sends the full bonuses dict, not the two numbers that
            the text view picks out. A graphical client can draw all of
            them, and the dict holds plain integers.

        Notes/References:
            Until 10/22/2026 the band also sent six more fields: the weapon,
            the attack speed, the attack type, the weapon style, and two
            bonuses. Nick removed them from the Character tab. The Combat
            tab shows the weapon, the speed and the styles. The text view
            keeps its rows.

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        profile = cls._profile(character)

        if profile is None:
            return {}

        bonuses = profile["combat_stat_bonuses"]
        totals = {key: int(value) for key, value in bonuses.items()}

        payload = {TOTAL_BONUSES_KEY: totals}

        return payload
