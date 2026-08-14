"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/08/2026
Description: Summary panel: every skill level at a glance, grouped by category,
             plus the one skill closest to levelling.
"""

from systems.ui.meters import build_xp_meter

from .. import constants as const
from .. import layout
from .base_panel import BasePanel


# Public constant definitions

PANEL_TITLE = "Skills"

LABEL_CLOSEST = "Closest"

# Rendered when every skill has hit the level cap and there is no next level to
# point at anywhere on the character.
ALL_CAPPED_TEXT = "all skills at cap"


class SkillsPanel(BasePanel):
    """
    Purpose: The whole skill roster compressed to one level per skill, plus the
    next level the player is nearest to earning.

    Entry:
        character is a Character with a skills handler.

    Exit/Returns:
        Not applicable -- see render / data.

    Module Globals:
        None.

    Methodology:
        Skill NAMES are printed in full rather than abbreviated. An
        abbreviation table would be a second place that has to learn about
        every new skill, and the registry already carries the one display name
        each skill owns.

        Categories come from the skill classes themselves and are sorted by
        name, exactly as systems/menus/skills_menu.py does, so the two screens
        list the same skills in the same order.

        The "closest to levelling" row is the only thing this panel shows that
        the skills menu cannot: it is a comparison ACROSS the roster, so it is
        computed by the skills handler and merely displayed here.

    Notes/References:
        systems/menus/skills_menu.py remains the place per-skill XP, unlock
        lists and progress detail live. This panel deliberately shows one
        number per skill and links there for the rest.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """

    key = "skills"
    title = PANEL_TITLE
    order = const.PANEL_ORDER_SKILLS
    public = True


    @classmethod
    def _by_category(cls, character: object) -> dict:
        """
        Purpose: Group every registered skill's display name and level by
        category.

        Entry:
            character is a Character with a skills handler.

        Exit/Returns:
            Returns a dict of category name -> list of "Name Level" strings,
            each list in registry order.

        Module Globals:
            None.

        Methodology:
            Deferred import of SKILL_REGISTRY, matching every other module
            outside the skills package -- the registry walks and imports
            skill_defs at first touch, and this module is reachable from a
            command module that loads at startup.

            get_level rather than a raw db.skills read, so a skill added after
            this character was created reports 0 instead of being absent.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        from systems.progression.skills.registry import SKILL_REGISTRY

        categories = {}

        for skill_key, skill_class in SKILL_REGISTRY.items():
            level = character.skills.get_level(skill_key)
            category_name = skill_class.category

            if category_name not in categories:
                categories[category_name] = []

            categories[category_name].append(f"{skill_class.name} {level}")

        return categories


    @classmethod
    def _closest_lines(cls, character: object) -> list:
        """
        Purpose: Render the "closest to levelling" row and its XP meter.

        Entry:
            character is a Character with a skills handler.

        Exit/Returns:
            Returns a list of display lines. One line when every skill is
            capped, two otherwise.

        Module Globals:
            LABEL_CLOSEST, ALL_CAPPED_TEXT read.

        Methodology:
            The handler returns None only when every skill sits at the cap,
            which is a real state worth naming rather than an error.

            The meter is drawn from progress-into-level and the level's own
            threshold -- NOT from cumulative XP. Those two numbers are what
            get_xp_level returns and what build_xp_meter expects; mixing in a
            cumulative figure is what once produced a "1154 / 152" bar.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        from systems.progression.skills.registry import SKILL_REGISTRY

        closest = character.skills.closest_to_level_up()

        if closest is None:
            line = layout.wide_field(LABEL_CLOSEST, ALL_CAPPED_TEXT)

            return [line]

        skill_class = SKILL_REGISTRY.get(closest["skill_key"])
        display_name = getattr(skill_class, "name", closest["skill_key"])
        next_level = closest["level"] + 1
        remaining = closest["remaining_xp"]

        headline = f"{display_name} {closest['level']} -> {next_level}, {remaining:,} XP"
        meter = build_xp_meter(closest["current_xp"], closest["needed_xp"])

        lines = [
            layout.wide_field(LABEL_CLOSEST, headline),
            layout.wide_field("", meter, color=""),
        ]

        return lines


    @classmethod
    def render(cls, character: object) -> list:
        """
        Purpose: Render the skills band.

        Entry:
            character is a Character with a skills handler.

        Exit/Returns:
            Returns a list of display lines.

        Module Globals:
            None.

        Methodology:
            One wrapped row per category, then the closest-to-levelling rows.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        categories = cls._by_category(character)
        lines = []

        for category_name in sorted(categories.keys()):
            entries = categories[category_name]
            lines.extend(layout.wrapped_field(category_name, entries))

        lines.extend(cls._closest_lines(character))

        return lines


    @classmethod
    def data(cls, character: object) -> dict:
        """
        Purpose: Structured form of the skills band.

        Entry:
            character is a Character with a skills handler.

        Exit/Returns:
            Returns a dict of plain JSON-safe values.

        Module Globals:
            None.

        Methodology:
            Levels are keyed by skill KEY, not display name -- a client picking
            an icon needs the stable identifier, and it can render the name it
            was given alongside.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        from systems.progression.skills.registry import SKILL_REGISTRY

        levels = {}

        for skill_key, skill_class in SKILL_REGISTRY.items():
            levels[skill_key] = {
                "name": str(skill_class.name),
                "category": str(skill_class.category),
                "level": int(character.skills.get_level(skill_key)),
            }

        payload = {
            "levels": levels,
            "closest_to_level_up": character.skills.closest_to_level_up(),
        }

        return payload
