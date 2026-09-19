"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: EvMenu nodes for the profile of a character: the dossier, the
             skill levels and the records of ANY character, yours included.

             Three commands open it, each at its own page:

               profile <character>   the dossier
               skills <character>    the skill levels
               stats <character>     the records

             A click on another player in the Godot world pane sends one of
             those three lines, and BlackoutEvMenu shows the menu there as a
             pop-up. A telnet player gets the same pages as text.

             Everything on a profile is public. There is no narrower "public"
             view of the dossier: another player reads the same screen that
             the owner reads with `score`.
"""

from evennia.objects.models import ObjectDB

from systems.gameplay.progression.skills.registry import SKILL_REGISTRY
from systems.interface.summary.panel_defs.records import RecordsPanel
from systems.interface.summary.service import render_summary
from systems.interface.ui.colors import ERROR_COLOR, RESET_COLOR, TITLE_COLOR
from systems.interface.ui.meters import build_xp_meter

from . import constants as menu_const
from .base_menu import start_blackout_menu


# Public constant definitions

MENU_PATH = "systems.interface.menus.profile_menu"

# The menu attribute that holds the id of the character on show. EvMenu makes
# each extra launch kwarg an attribute of the menu, and the nodes read it
# back. An id and not the object, so a node never holds a deleted object.
TARGET_ID_ATTR = "profile_target_id"

# The three pages: (node name, option label). The node names live in
# menus/constants.py, because the commands that open a page read them too.
NODE_DOSSIER = menu_const.PROFILE_NODE_DOSSIER
NODE_SKILLS = menu_const.PROFILE_NODE_SKILLS
NODE_RECORDS = menu_const.PROFILE_NODE_RECORDS

PAGES = (
    (NODE_DOSSIER, "Dossier"),
    (NODE_SKILLS, "Skills"),
    (NODE_RECORDS, "Records"),
)

REFRESH_DESC = "Refresh"

HEADER_TEMPLATE = "{title}--- Profile: {name} ---{reset}"
SKILLS_HEADER_TEMPLATE = "{title}--- {name}'s Skills ---{reset}"
NO_SKILLS_TEXT = "{name} has not acquired any skills yet."
TARGET_GONE_TEXT = "That character is no longer there to read."

# Spoken by BlackoutEvMenu.close_menu, however the menu is closed.
CLOSING_TEXT = "Closing profile."


# ─── Private helper routines ─────────────────────────────────────────────────

def _target(caller: object):
    """The character on show, or None when it no longer exists.

    Looked up by id on every node, so a character deleted while the menu is
    open ends the menu with a message and not a traceback.
    """
    menu = getattr(caller.ndb, "_evmenu", None)
    target_id = getattr(menu, TARGET_ID_ATTR, None)

    if target_id is None:
        return None

    found = ObjectDB.objects.filter(id=target_id).first()

    return found


def _page_options(current: str) -> tuple:
    """One option for each OTHER page, then Refresh.

    Refresh goes back to the current page, which builds it again. Every
    number on a profile is read live, so the page is current after it.
    """
    options = []

    for node, label in PAGES:
        if node == current:
            continue

        options.append({"desc": label, "goto": node})

    options.append({"desc": REFRESH_DESC, "goto": current})

    return tuple(options)


def _gone() -> tuple:
    """The node result for a target that no longer exists. Ends the menu."""
    return f"{ERROR_COLOR}{TARGET_GONE_TEXT}{RESET_COLOR}", None


def _skill_lines(target: object) -> list:
    """
    Purpose: One line for each skill of `target`: its name, level and meter.

    Entry:
        target - a character with a skills handler.

    Exit/Returns:
        Returns the display lines. Empty when the character has no skills.

    Module Globals:
        SKILL_REGISTRY read.

    Methodology:
        Moved here from CmdSkills, which printed it for `skills <character>`
        before the profile menu existed. The levels are read through the
        handler of the target, so a skill added after the character was made
        shows level 0, not a gap.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 06/02/2026
    """
    skills_dict = target.db.skills or {}
    lines = []

    for skill_key, skill_data in skills_dict.items():
        if skill_key not in SKILL_REGISTRY:
            continue

        skill_class = SKILL_REGISTRY[skill_key]
        current_xp, total_xp_needed, _remaining = (
            target.skills.get_xp_level(skill_key))
        xp_meter = build_xp_meter(current_xp, total_xp_needed)
        level = skill_data["level"]

        lines.append(f"|w{skill_class.name}:|n Level {level} {xp_meter}")

    return lines


# ─── Public routines ─────────────────────────────────────────────────────────

def start_profile_menu(caller: object, target: object,
                       startnode: str = NODE_DOSSIER) -> object:
    """
    Purpose: Open the profile of `target` for `caller`.

    Entry:
        caller    - the character who reads.
        target    - the character to read. May be the caller.
        startnode - one of the NODE_* names: the page to open at.

    Exit/Returns:
        Returns the running BlackoutEvMenu, or None when it did not open.

    Module Globals:
        MENU_PATH, TARGET_ID_ATTR read.

    Methodology:
        The one way in, for all three commands. The target rides in as a
        launch kwarg, which EvMenu stores on the menu before it enters the
        start node.

    Notes/References:
        No state-feed send here. A graphical client gets the menu itself as
        a pop-up, through BlackoutEvMenu.display_nodetext.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    launch = {TARGET_ID_ATTR: target.id}
    menu = start_blackout_menu(caller, MENU_PATH, startnode=startnode, **launch)

    return menu


def start(caller: object, **kwargs) -> tuple:
    """The dossier page: the same screen the owner reads with `score`."""
    target = _target(caller)

    if target is None:
        return _gone()

    header = HEADER_TEMPLATE.format(
        title=TITLE_COLOR, name=target.key, reset=RESET_COLOR)
    screen = render_summary(target)
    text = f"{header}\n{screen}"

    return text, _page_options(NODE_DOSSIER)


def node_skills(caller: object, **kwargs) -> tuple:
    """The skills page: every skill of the target, with its level."""
    target = _target(caller)

    if target is None:
        return _gone()

    header = SKILLS_HEADER_TEMPLATE.format(
        title=TITLE_COLOR, name=target.key, reset=RESET_COLOR)
    lines = _skill_lines(target)

    if not lines:
        lines = [NO_SKILLS_TEXT.format(name=target.key)]

    text = "\n".join([header] + lines)

    return text, _page_options(NODE_SKILLS)


def node_records(caller: object, **kwargs) -> tuple:
    """The records page: the full `stats` sheet of the target."""
    target = _target(caller)

    if target is None:
        return _gone()

    text = RecordsPanel.sheet(target)

    return text, _page_options(NODE_RECORDS)
