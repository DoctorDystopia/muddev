"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/05/2026
Description: Single source of truth for gathering-node skill unlocks -- the
             required skill/level and yielded item for every resource node
             in the world. Mirrors world/item_database.py's data-table
             pattern (ItemDef + ITEM_DB) so gathering and crafting expose
             their unlocks through the same shape, letting both feed the
             skills menu's "Unlocks" listing.
"""



from dataclasses import dataclass

from world.item_database import ITEM_DB



@dataclass
class GatherableDef:
    key: str
    node_name: str
    skill_key: str
    required_level: int
    item_key: str
    xp_reward: int


# Every gatherable node in the world. Adding a node type means adding one
# entry here -- the typeclass and its skill def read required_level/xp_reward
# from this dict instead of each restating their own constants.
GATHERABLE_REGISTRY: dict[str, GatherableDef] = {
    "rusty_pole": GatherableDef(
        key="rusty_pole",
        node_name="Rusty Pole",
        skill_key="cutting",
        required_level=0,
        item_key="rusty_metal_chunk",
        xp_reward=10,
    ),
}


# Fail at import time if a def points at an item that doesn't exist, rather
# than a player discovering it the moment they successfully gather the node.
_missing_items = [
    gatherable_def.key
    for gatherable_def in GATHERABLE_REGISTRY.values()
    if gatherable_def.item_key not in ITEM_DB
]
if _missing_items:
    raise KeyError(
        f"GATHERABLE_REGISTRY: item_key not found in ITEM_DB for: {_missing_items}"
    )



def get_gatherable(key: str) -> GatherableDef | None:
    """
    Purpose: Look up a single gatherable definition by its registry key.

    Entry:
        key is a string, expected to match a GATHERABLE_REGISTRY key.

    Exit/Returns:
        Returns the matching GatherableDef, or None if key is unregistered.

    Module Globals:
        GATHERABLE_REGISTRY read.

    Methodology:
        Plain dict lookup.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/05/2026
    """
    gatherable_def = GATHERABLE_REGISTRY.get(key)

    return gatherable_def


def get_gatherables_for_skill(skill_key: str) -> list[GatherableDef]:
    """
    Purpose: Get every gatherable node that unlocks under a given skill.

    Entry:
        skill_key is a skill key string to match against GatherableDef.skill_key.

    Exit/Returns:
        Returns a list of GatherableDef, sorted by (required_level, node_name).

    Module Globals:
        GATHERABLE_REGISTRY read.

    Methodology:
        Filters the registry by skill_key, then sorts ascending by required
        level so the skills menu lists easier unlocks first. Mirrors
        systems.crafting.crafting_service.get_recipes_for_skill.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/05/2026
    """
    matches = [
        gatherable_def
        for gatherable_def in GATHERABLE_REGISTRY.values()
        if gatherable_def.skill_key == skill_key
    ]

    matches.sort(key=lambda entry: (entry.required_level, entry.node_name))

    return matches


def get_gatherable_item_name(gatherable_def: GatherableDef) -> str:
    """
    Purpose: Resolve the display name of the item a gatherable node yields.

    Entry:
        gatherable_def is a GatherableDef whose item_key is a valid ITEM_DB key.

    Exit/Returns:
        Returns the item's display name string.

    Module Globals:
        ITEM_DB read.

    Methodology:
        Single ITEM_DB lookup, so an item's display name stays owned solely
        by its ItemDef rather than duplicated onto GatherableDef.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/05/2026
    """
    item_name = ITEM_DB[gatherable_def.item_key].name

    return item_name
