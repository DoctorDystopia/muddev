"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/28/2026
Description: One skill, described in full -- as the text sheet a telnet player
             reads and as the plain values a graphical client draws.

             WHY THIS EXISTS. The sheet was written inline in
             systems/menus/skills_menu.py, which meant the only way to see a
             skill's unlocks was to be inside an EvMenu. That was fine while
             the menu was the only reader. It stopped being fine the moment two
             more appeared: `skills <skill>` prints the same sheet without a
             menu, and CHANNEL_CHAR_SKILLS ships the same facts as data. Three
             readers of one description is three chances to disagree about what
             a skill unlocks.

             SO THE ORDER IS THE POINT. `unlock_sections` is built once and
             both outputs walk it, the arrangement systems/statefeed/quests.py
             uses beside `objective_lines`: the prose and the payload come from
             the same reads in the same order, so they cannot describe
             different skills.

             THE FOUR SECTIONS ARE A TABLE, not four hand-rolled loops. Adding
             a fifth skill-gated system means adding one row to
             _UNLOCK_SECTIONS and writing its row builder -- the same shape the
             menu already had, kept, because it is the part that was right.

             EVERY OUTWARD IMPORT IS DEFERRED. This module reaches crafting,
             equipment, auras and gatherables, which is a heavier dependency
             than anything else in systems/progression/skills/ carries. The
             skills package is imported by typeclasses/characters.py at
             startup; a top-level import here would drag the recipe registry
             and the aura package walk into typeclass import time for the
             benefit of a screen nobody has opened yet. Nothing imports this
             module at startup, and it imports nothing at module scope.
"""

from systems.progression.skills import constants as skill_constants
from systems.ui.colors import (
    HIGHLIGHT_COLOR,
    RESET_COLOR,
    SKILL_COLOR,
    SUCCESS_COLOR,
    TITLE_COLOR,
)
from systems.ui.meters import build_xp_meter


# Public constant definitions

# Headings for the sheet's field rows. One spelling each, shared by the text
# sheet and by nothing else -- the structured form ships keys, not labels,
# because a client owns what it calls a number.
LABEL_CATEGORY = "Category"
LABEL_LEVEL = "Level"
LABEL_XP = "XP"
LABEL_NEXT_LEVEL = "Next level at"
LABEL_REMAINING = "Remaining"
LABEL_PROGRESS = "Progress"
LABEL_STATUS = "Status"

# What the two unlock states are called on the sheet.
STATUS_UNLOCKED = "Unlocked"
STATUS_LOCKED = "Locked"

# Section headings, in the order they are rendered. Public so a test can assert
# the structured form carries the same titles the text sheet prints.
SECTION_RECIPES = "Unlocks"
SECTION_GATHERABLES = "Gathering Unlocks"
SECTION_EQUIPMENT = "Equipment Unlocks"
SECTION_ABILITIES = "Ability Unlocks"

# Printed when a player names something that is not a skill.
UNKNOWN_SKILL_TEXT = "There is no skill called '{name}'."


# ─── Private helper routines ─────────────────────────────────────────────────

def _recipe_rows(skill_key: str) -> list:
    """
    Purpose: Build unlock rows for every recipe this skill unlocks.

    Entry:
        skill_key is a valid skill key string.

    Exit/Returns:
        Returns a list of (name, required_level, note) tuples, where note names
        the required materials or is "" for a recipe that needs none.

    Module Globals:
        None.

    Methodology:
        One row per entry from crafting_service.get_recipes_for_skill. Deferred
        import; see the module docstring.

    Notes/References:
        Moved here from systems/menus/skills_menu.py on 08/28/2026 unchanged.

    Author: Nick Hobar
    Creation date: 08/05/2026
    """
    from systems.crafting.crafting_service import (
        get_material_summary,
        get_recipes_for_skill,
    )

    rows = []

    for _recipe_key, recipe_cls in get_recipes_for_skill(skill_key):
        material_summary = get_material_summary(recipe_cls)

        if material_summary:
            note = f"requires {material_summary}"
        else:
            note = ""

        rows.append((recipe_cls.name, recipe_cls.required_level, note))

    return rows


def _gatherable_rows(skill_key: str) -> list:
    """
    Purpose: Build unlock rows for every gathering node this skill unlocks.

    Entry:
        skill_key is a valid skill key string.

    Exit/Returns:
        Returns a list of (name, required_level, note) tuples, where note names
        the yielded item.

    Module Globals:
        None.

    Methodology:
        One row per entry from gatherables.get_gatherables_for_skill.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/05/2026
    """
    from systems.progression.skills.gatherables import (
        get_gatherable_item_name,
        get_gatherables_for_skill,
    )

    rows = []

    for gatherable_def in get_gatherables_for_skill(skill_key):
        item_name = get_gatherable_item_name(gatherable_def)
        note = f"yields {item_name}"
        rows.append((gatherable_def.node_name, gatherable_def.required_level, note))

    return rows


def _equippable_rows(skill_key: str) -> list:
    """
    Purpose: Build unlock rows for every equippable item this skill unlocks.

    Entry:
        skill_key is a valid skill key string.

    Exit/Returns:
        Returns a list of (name, required_level, note) tuples, note always "".

    Module Globals:
        None.

    Methodology:
        One row per entry from skill_requirements.get_equippables_for_skill.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/05/2026
    """
    from items.equipment.skill_requirements import get_equippables_for_skill

    rows = []

    for item_def in get_equippables_for_skill(skill_key):
        rows.append((item_def.name, item_def.req_level, ""))

    return rows


def _aura_rows(skill_key: str) -> list:
    """
    Purpose: Build unlock rows for every ability this skill unlocks.

    Entry:
        skill_key is a valid skill key string.

    Exit/Returns:
        Returns a list of (name, required_level, note) tuples, note always "".

    Module Globals:
        None.

    Methodology:
        One row per entry from auras.registry.get_auras_for_skill.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/05/2026
    """
    from systems.combat.auras.registry import get_auras_for_skill

    rows = []

    for aura in get_auras_for_skill(skill_key):
        rows.append((aura.name, aura.unlock_level, ""))

    return rows


# Every skill-gated system, and how to ask it what this skill opens.
#
# A TABLE rather than four calls in a row, so a fifth gated system is one entry
# plus one builder and reaches both the text sheet and the feed at once. The
# order is the order both outputs render in.
_UNLOCK_SECTIONS: tuple = (
    (SECTION_RECIPES, _recipe_rows),
    (SECTION_GATHERABLES, _gatherable_rows),
    (SECTION_EQUIPMENT, _equippable_rows),
    (SECTION_ABILITIES, _aura_rows),
)


def _section_text(title: str, current_level: int, rows: list) -> str:
    """
    Purpose: Render one "<Title>:" block of skill-gated unlocks.

    Entry:
        title is the section heading.
        current_level is the reader's level in the skill being described.
        rows is a list of (name, required_level, note) tuples.

    Exit/Returns:
        Returns the block as a string, or "" when rows is empty -- a section
        with nothing in it costs no lines.

    Module Globals:
        HIGHLIGHT_COLOR, SKILL_COLOR, SUCCESS_COLOR, RESET_COLOR read.

    Methodology:
        A row the reader has already earned is coloured as reached, which is
        what turns the list into a progress ladder rather than a catalogue.

    Notes/References:
        Moved here from skills_menu._format_unlock_section unchanged.

    Author: Nick Hobar
    Creation date: 08/05/2026
    """
    if not rows:
        return ""

    lines = [f"\n\n{HIGHLIGHT_COLOR}{title}:{RESET_COLOR}"]

    for name, required_level, note in rows:
        is_reached = current_level >= required_level

        if is_reached:
            level_color = SUCCESS_COLOR
        else:
            level_color = HIGHLIGHT_COLOR

        line = (
            f"  {SKILL_COLOR}{name}{RESET_COLOR} "
            f"({level_color}Level {required_level}{RESET_COLOR})"
        )

        if note:
            line += f" - {note}"

        lines.append(line)

    return "\n".join(lines)


# ─── Public routines ─────────────────────────────────────────────────────────

def resolve_skill_key(text: str) -> str:
    """
    Purpose: Turn something a player typed into a registered skill key.

    Entry:
        text is whatever the player wrote after the command. May be empty.

    Exit/Returns:
        Returns the skill key, or "" when nothing matches.

    Module Globals:
        None.

    Methodology:
        Key first, then display name, then a unique prefix of either -- both
        compared case-folded. An AMBIGUOUS prefix returns "" rather than
        guessing: two skills starting "for" is a question only the player can
        answer, and picking one would silently show the wrong sheet.

        Prefix matching exists because the display name is what the player has
        just read off a screen, and "brain" is what they will type for Brain
        Farming.

    Notes/References:
        Callers treat "" as "not a skill" and are free to fall back to some
        other lookup -- CmdSkills falls back to searching for a character.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    from systems.progression.skills.registry import SKILL_REGISTRY

    wanted = text.strip().lower()

    if not wanted:
        return ""

    for skill_key, skill_class in SKILL_REGISTRY.items():
        is_exact = wanted in (skill_key.lower(), str(skill_class.name).lower())

        if is_exact:
            return skill_key

    matches = []

    for skill_key, skill_class in SKILL_REGISTRY.items():
        starts = (skill_key.lower().startswith(wanted)
                  or str(skill_class.name).lower().startswith(wanted))

        if starts:
            matches.append(skill_key)

    if len(matches) == 1:
        return matches[0]

    return ""


def unlock_sections(skill_key: str) -> list:
    """
    Purpose: Everything one skill opens, section by section.

    Entry:
        skill_key is a registered skill key. An unregistered one yields empty
        sections rather than raising -- every builder simply finds nothing.

    Exit/Returns:
        Returns a list of (title, rows) tuples in _UNLOCK_SECTIONS order, where
        rows is a list of (name, required_level, note) tuples. Sections with no
        rows are INCLUDED; dropping them is the caller's choice, and the feed
        and the text sheet make it differently.

    Module Globals:
        _UNLOCK_SECTIONS read.

    Methodology:
        One walk of the table. This is the single read of "what does this skill
        unlock" that both outputs share.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    sections = []

    for title, builder in _UNLOCK_SECTIONS:
        sections.append((title, builder(skill_key)))

    return sections


def skill_detail(character: object, skill_key: str) -> dict:
    """
    Purpose: One skill's whole sheet as plain JSON-safe values.

    Entry:
        character is a Character with a skills handler.
        skill_key is a registered skill key.

    Exit/Returns:
        Returns the detail dict, or {} when the key names no skill.

    Module Globals:
        skill_constants.MAX_BASE_SKILL_LEVEL read.
        SECTION_* read via unlock_sections.

    Methodology:
        `current_xp` / `needed_xp` are progress INTO the level and that level's
        own threshold, which is what get_xp_level returns and what an XP bar
        wants. `total_xp` is the cumulative figure. Mixing the two is what once
        produced a "1154 / 152" bar, so both are shipped under names that say
        which they are and no client has to derive either.

        `command` is the line a telnet player would type to read this sheet.
        The SERVER names it, for the reason serialize_entity names `interact`:
        a client that composed it would be spelling a command, and a client
        verb table has been deleted twice here for being wrong within a week.

        An unlock section with no rows is DROPPED here, unlike in
        unlock_sections. A client draws headings from what it is sent, and a
        heading with nothing under it is a client-side branch the server can
        simply not create.

    Notes/References:
        Consumed by systems/statefeed/skills.py. Every value must survive
        json.dumps -- see systems/statefeed/payloads.py.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    from systems.progression.skills.registry import SKILL_REGISTRY

    skill_class = SKILL_REGISTRY.get(skill_key)

    if skill_class is None:
        return {}

    level = character.skills.get_level(skill_key)
    current_xp, needed_xp, remaining_xp = character.skills.get_xp_level(skill_key)
    total_xp = character.skills.get_total_xp(skill_key)
    skill_instance = skill_class()

    sections = []

    for title, rows in unlock_sections(skill_key):
        if not rows:
            continue

        entries = []

        for name, required_level, note in rows:
            entries.append({
                "name": str(name),
                "level": int(required_level),
                "note": str(note),
            })

        sections.append({"title": str(title), "rows": entries})

    detail = {
        "key": str(skill_key),
        "name": str(skill_class.name),
        "category": str(skill_class.category),
        "description": str(skill_class.description),
        "level": int(level),
        "max_level": int(skill_constants.MAX_BASE_SKILL_LEVEL),
        "current_xp": int(current_xp),
        "needed_xp": int(needed_xp),
        "remaining_xp": int(remaining_xp),
        "total_xp": int(total_xp),
        "next_level_at": int(total_xp + remaining_xp),
        "unlocked": bool(skill_instance.get_unlock_requirements(character)),
        "command": command_for(skill_key),
        "unlocks": sections,
    }

    return detail


def command_for(skill_key: str) -> str:
    """
    Purpose: Name the line a player would type to read one skill's sheet.

    Entry:
        skill_key is a registered skill key.

    Exit/Returns:
        Returns the command string.

    Module Globals:
        None.

    Methodology:
        Composed HERE and nowhere else, so the command a graphical client sends
        and the command a telnet player types are the same string by
        construction. The key rather than the display name, because a key never
        contains a space and never changes when a name is reworded.

        The deferred import is what stops this module and the command module
        importing each other at load time -- CmdSkills reads this module for
        its argument branch.

    Notes/References:
        CLAUDE.md §"The webclient": the server names, the client draws.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    from commands.progression_cmds import CmdSkills

    command = f"{CmdSkills.key} {skill_key}"

    return command


def render_detail(character: object, skill_key: str) -> str:
    """
    Purpose: One skill's whole sheet as the text a player reads.

    Entry:
        character is a Character with a skills handler.
        skill_key is a registered skill key.

    Exit/Returns:
        Returns the sheet, or "" when the key names no skill.

    Module Globals:
        LABEL_* , STATUS_* read.
        SKILL_COLOR, TITLE_COLOR, SUCCESS_COLOR, HIGHLIGHT_COLOR,
        RESET_COLOR read.

    Methodology:
        Reads the structured form and renders it, rather than reading the
        handler a second time. That is what makes "the sheet and the payload
        cannot disagree" true by construction instead of by discipline -- and
        it is why the two live in one module at all.

    Notes/References:
        The XP meter is drawn from progress-into-level against that level's
        threshold, never from the cumulative figure.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    detail = skill_detail(character, skill_key)

    if not detail:
        return ""

    if detail["unlocked"]:
        status = f"{SUCCESS_COLOR}{STATUS_UNLOCKED}{RESET_COLOR}"
    else:
        status = f"{HIGHLIGHT_COLOR}{STATUS_LOCKED}{RESET_COLOR}"

    meter = build_xp_meter(detail["current_xp"], detail["needed_xp"])

    text = (
        f"{SKILL_COLOR}{detail['name']}{RESET_COLOR}\n"
        f"{LABEL_CATEGORY}: {detail['category']}\n"
        f"{LABEL_LEVEL}: {TITLE_COLOR}{detail['level']}{RESET_COLOR}\n"
        f"{LABEL_XP}: {detail['total_xp']}\n"
        f"{LABEL_NEXT_LEVEL}: {detail['next_level_at']}\n"
        f"{LABEL_REMAINING}: {detail['remaining_xp']}\n"
        f"{LABEL_PROGRESS}: {meter}\n"
        f"{LABEL_STATUS}: {status}\n\n"
        f"{detail['description']}"
    )

    for section in detail["unlocks"]:
        rows = [(row["name"], row["level"], row["note"])
                for row in section["rows"]]
        text += _section_text(section["title"], detail["level"], rows)

    return text
