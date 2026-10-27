"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/12/2026
Description: Render the item catalog of the figure workbench.

             The figure workbench (godot/addons/blackout_figure/) dresses a
             figure in the items of the game. It needs the name, the slot,
             the tool type, the tier, and the family of each item that a
             character can equip. Only Python knows these facts, and
             GDScript cannot import ITEM_DB. Thus, this module renders them
             as one JSON file, and the workbench reads the file.

             The file is an editor table, as OBJECT_KIND_PREVIEW is for the
             terrain editor. The game client never reads it: the web export
             leaves out the whole plugin directory. A player gets the worn
             record of a character from the server (DESIGN-0014 section 11).

             PURE, as clientexport.py is. render() returns a string and
             writes nothing. scripts/export_client_constants.py writes the
             file, and test_figure_files.py compares the file in git with a
             new render. A stale file thus fails the suite.

             THE FILE:

                 format          1
                 slots           [{key, label, clears}, ...], in display
                                 order
                 items           [{key, name, slot, tool_type, tier,
                                 family}, ...], sorted by key
                 tool_types      each tool type of the server, sorted
                 npcs            [{key, name, outfit}, ...], sorted by key
                 attack_actions  each action that a swing can name,
                                 sorted

             `clears` names each other slot that an item in this slot
             empties (SLOT_CONFLICTS). The outfit bar of the workbench
             follows it, so the author cannot dress a figure in an outfit
             that no character can wear.

             `tool_types` is each key of the two skill maps, and the tool
             type of each item (Phase W6). A stance of the client has a tool
             type as its key. The workbench reads the list, so its check
             gives the answer that the test of rule C7 gives.

             `npcs` has one row for each NpcDef with an outfit (Phase W6,
             DESIGN-0014 decision 8). `outfit` is slot -> item key. The
             server owns the outfit. The workbench only shows it.
             outfit_problems() gives the rules of an outfit.

             `attack_actions` is each action that the swing of a weapon, of
             bare hands, or of an NPC can name (10/25/2026). The Clips tab
             shows one row for each, so the author gives each one a clip.
             The same two reads name the action of a live swing
             (events._figure_action).

             THE STANCE TABLE (Phase W5) is a file of the Godot project that
             names a server fact: each stance has a tool_type as its key.
             stances_path() and clips_directory() give the two paths that
             the test of rule C7 reads. They are here, beside the other path
             into the Godot project.
"""

import json
import os

from items.equipment.constants import (
    SLOT_CONFLICTS,
    SLOT_DISPLAY_ORDER,
    WieldLocation,
)
from items.equipment.skill_requirements import (
    ARMOR_SKILL_MAP,
    WEAPON_SKILL_MAP,
)
from systems.gameplay.combat import constants as combat_const
from world.item_database import ITEM_DB
from world.npc_database import NPC_DB

from . import constants as const


# ─── Private constant definitions ────────────────────────────────────────────

# The format number of the catalog file. A reader refuses a newer one.
_FORMAT: int = 1

# One tab for each level, as the figure files of the workbench have.
_INDENT: str = "\t"

# The tool type of an item that declares none.
_NO_TOOL_TYPE: str = ""

# The game dir (blackout/), three levels up from this file.
_GAME_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

# The repo root. The Godot client is a sibling of the game dir.
_REPO_ROOT: str = os.path.dirname(_GAME_DIR)

# Where the catalog goes: beside the plugin that reads it.
_OUTPUT_PATH: str = os.path.join(
    _REPO_ROOT, "godot", "addons", "blackout_figure", "item_catalog.json")

# The figure directory of the Godot project: the stance table, and one clip
# file for each clip. The figure workbench writes the two.
_GODOT_FIGURE_DIR: str = os.path.join(_REPO_ROOT, "godot", "world", "figure")
_STANCES_PATH: str = os.path.join(_GODOT_FIGURE_DIR, "stances.json")
_CLIPS_DIR: str = os.path.join(_GODOT_FIGURE_DIR, "clips")


# ─── Private helper routines ─────────────────────────────────────────────────

def _slot_rows() -> list:
    """
    Purpose: Give one row for each equipment slot, in display order.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a list of {key, label, clears} dicts.

    Module Globals:
        SLOT_DISPLAY_ORDER and SLOT_CONFLICTS read.

    Author: Nick Hobar
    Creation date: 10/12/2026
    """
    rows = []

    for slot in SLOT_DISPLAY_ORDER:
        clears = [other.value for other in SLOT_CONFLICTS.get(slot, ())]
        row = {"key": slot.value, "label": slot.label, "clears": clears}

        rows.append(row)

    return rows


def _item_rows() -> list:
    """
    Purpose: Give one row for each item that a character can equip.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a list of {key, name, slot, tool_type, tier, family} dicts,
        sorted by key. An item with no use_slot has no row.

    Module Globals:
        ITEM_DB read.

    Author: Nick Hobar
    Creation date: 10/12/2026
    """
    rows = []

    for key in sorted(ITEM_DB):
        item_def = ITEM_DB[key]

        if item_def.use_slot is None:
            continue

        rows.append({
            "key": key,
            "name": item_def.name,
            "slot": item_def.use_slot.value,
            "tool_type": item_def.tool_type or _NO_TOOL_TYPE,
            "tier": item_def.tier,
            "family": family_of(item_def),
        })

    return rows


def _npc_rows() -> list:
    """
    Purpose: Give one row for each NPC def that has an outfit.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a list of {key, name, outfit} dicts, sorted by key. `outfit`
        is slot value -> item key. A def with no outfit has no row.

    Module Globals:
        NPC_DB read.

    Author: Nick Hobar
    Creation date: 10/13/2026
    """
    rows = []

    for key in sorted(NPC_DB):
        npc_def = NPC_DB[key]

        if not npc_def.outfit:
            continue

        outfit = {slot.value: item_key
                  for slot, item_key in npc_def.outfit.items()}

        rows.append({"key": key, "name": npc_def.name, "outfit": outfit})

    return rows


def _swing_kinds() -> set:
    """
    Purpose: Give each pair of hands and attack type that a swing can have.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a set of (hands, attack_type) tuples.

    Module Globals:
        ITEM_DB, NPC_DB, combat_const.UNARMED_COMBAT_STYLES,
        combat_const.ATTACK_HANDS_BY_SLOT read.

    Methodology:
        Three sources of a combat style: bare hands, an item in a hand slot,
        and the combat block of an NPC def. An NPC holds no item, so its
        swing is a swing of bare hands. An item in another slot is not a
        held weapon (combat.held_weapon), so its styles never swing.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    unarmed = combat_const.ATTACK_HANDS_UNARMED
    kinds = {(unarmed, style["attack_type"])
             for style in combat_const.UNARMED_COMBAT_STYLES.values()}

    for item_def in ITEM_DB.values():
        if item_def.use_slot not in combat_const.ATTACK_HANDS_BY_SLOT:
            continue

        hands = combat_const.attack_hands(item_def.use_slot)
        styles = (item_def.combat_styles or {}).values()
        kinds.update((hands, style["attack_type"]) for style in styles)

    for npc_def in NPC_DB.values():
        styles = getattr(npc_def.combat, "combat_styles", None) or {}
        kinds.update((unarmed, style["attack_type"]) for style in styles.values())

    return kinds


# ─── Public interface ────────────────────────────────────────────────────────

def tool_types() -> list:
    """
    Purpose: Give each tool type that the server has.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a sorted list of names: each key of the two skill maps, and
        the tool type of each item.

    Module Globals:
        WEAPON_SKILL_MAP, ARMOR_SKILL_MAP, ITEM_DB read.

    Methodology:
        A stance of the client has a tool type as its key. The test of rule
        C7 and the check of the workbench compare a stance with this list.
        Thus, the two cannot disagree.

    Author: Nick Hobar
    Creation date: 10/13/2026
    """
    found = set(WEAPON_SKILL_MAP) | set(ARMOR_SKILL_MAP)
    found.update(item_def.tool_type for item_def in ITEM_DB.values()
                 if item_def.tool_type)

    return sorted(found)


def attack_actions() -> list:
    """
    Purpose: Give each action that a swing can name for a figure.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a sorted list of names, for example attack_one_hand_slash.

    Module Globals:
        const.FIGURE_ATTACK_ACTION_TEMPLATE read.

    Methodology:
        The template and combat_const.attack_hands give the spelling, as
        they do for a live swing (events._figure_action). The Clips tab of
        the workbench shows one row for each name. The stance check refuses
        an attack action of the stance table that no swing names.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    template = const.FIGURE_ATTACK_ACTION_TEMPLATE
    found = {template.format(hands=hands, attack_type=attack_type)
             for hands, attack_type in _swing_kinds()}

    return sorted(found)


def outfit_problems(outfit) -> list:
    """
    Purpose: Give each fault of the outfit of one NPC def.

    Entry:
        outfit is the `outfit` of an NpcDef: a dict of WieldLocation -> item
        key, or None.

    Exit/Returns:
        Returns a list of lines. An empty list means that a character can
        wear the outfit.

    Module Globals:
        ITEM_DB, SLOT_CONFLICTS read.

    Methodology:
        An outfit must be one that a character can wear, because the figure
        of an NPC is the figure of a player. Thus, each slot is a
        WieldLocation, each item goes in its slot, and no item sits in a
        slot that another item of the outfit clears.

    Author: Nick Hobar
    Creation date: 10/13/2026
    """
    problems = []
    slots = set((outfit or {}).keys())

    for slot, item_key in (outfit or {}).items():
        if not isinstance(slot, WieldLocation):
            problems.append("%r is not a WieldLocation" % (slot,))
            continue

        item_def = ITEM_DB.get(item_key)

        if item_def is None:
            problems.append("%s: no ItemDef has the key %r"
                            % (slot.value, item_key))
        elif item_def.use_slot is not slot:
            problems.append("%s: %s does not go in that slot"
                            % (slot.value, item_key))

        for cleared in SLOT_CONFLICTS.get(slot, ()):
            if cleared in slots:
                problems.append("%s clears %s, and the outfit fills the two"
                                % (slot.value, cleared.value))

    return problems


def family_of(item_def) -> str:
    """
    Purpose: Name the family that the client resolves an item to.

    Entry:
        item_def is an ItemDef.

    Exit/Returns:
        Returns one of const.ITEM_FAMILY_PRIORITY, or ITEM_FAMILY_GENERIC
        for an item with no family tag.

    Module Globals:
        const.ITEM_FAMILY_PRIORITY and const.ITEM_FAMILY_GENERIC read.

    Methodology:
        Walk the priority tuple, not the tags, as serializers._item_family
        does for a live object. An item with two families then gets the same
        answer here and on the wire.

    Notes/References:
        Public since 10/21/2026: the item list of the terrain editor
        (`spawn_items.py`) gives the same family.

    Author: Nick Hobar
    Creation date: 10/12/2026
    """
    categories = {category for _key, category in item_def.tags}

    for family in const.ITEM_FAMILY_PRIORITY:
        if family in categories:
            return str(family)

    return const.ITEM_FAMILY_GENERIC


def build() -> dict:
    """
    Purpose: Give the content of the item catalog.

    Entry:
        No conditions.

    Exit/Returns:
        Returns {format, slots, items, tool_types, npcs, attack_actions}.
        The module docstring gives each key.

    Module Globals:
        _FORMAT read.

    Author: Nick Hobar
    Creation date: 10/12/2026
    """
    catalog = {
        "format": _FORMAT,
        "slots": _slot_rows(),
        "items": _item_rows(),
        "tool_types": tool_types(),
        "npcs": _npc_rows(),
        "attack_actions": attack_actions(),
    }

    return catalog


def render() -> str:
    """
    Purpose: Render the item catalog as the text of its file.

    Entry:
        No conditions.

    Exit/Returns:
        Returns JSON text with sorted keys and a newline at the end. Writes
        nothing.

    Module Globals:
        _INDENT read.

    Methodology:
        One fact on each line and sorted keys, so a git diff shows one line
        for each changed fact. The same content gives the same bytes.

    Author: Nick Hobar
    Creation date: 10/12/2026
    """
    text = json.dumps(build(), indent=_INDENT, sort_keys=True,
                      ensure_ascii=False)

    return text + "\n"


def output_path() -> str:
    """
    Purpose: Give the path of the catalog file.

    Entry:
        No conditions.

    Exit/Returns:
        Returns an absolute path.

    Module Globals:
        _OUTPUT_PATH read.

    Notes/References:
        The table is here, not in the export script, for the reason that
        clientexport._OUTPUT_PATHS gives: the test cannot import
        blackout/scripts/.

    Author: Nick Hobar
    Creation date: 10/12/2026
    """
    return _OUTPUT_PATH


def stances_path() -> str:
    """
    Purpose: Give the path of the stance table of the Godot project.

    Entry:
        No conditions.

    Exit/Returns:
        Returns an absolute path. The file does not need to exist.

    Module Globals:
        _STANCES_PATH read.

    Author: Nick Hobar
    Creation date: 10/13/2026
    """
    return _STANCES_PATH


def clips_directory() -> str:
    """
    Purpose: Give the directory of the clip files of the Godot project.

    Entry:
        No conditions.

    Exit/Returns:
        Returns an absolute path. Each clip is one file there, and the file
        name is the clip name.

    Module Globals:
        _CLIPS_DIR read.

    Author: Nick Hobar
    Creation date: 10/13/2026
    """
    return _CLIPS_DIR
