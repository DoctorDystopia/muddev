"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/05/2026
Description: Single source of truth for gathering-node skill unlocks -- which
             skill works a node, at what level, for what item and what XP.
             Mirrors world/item_database.py's data-table pattern (ItemDef +
             ITEM_DB) so gathering and crafting expose their unlocks through
             the same shape, letting both feed the skills menu's "Unlocks"
             listing.

             A node declares a LIST of yields rather than one item. That is
             what the mutant raider corpse needs and the rusty pole does not:
             one corpse is worked by Butchery for a cut of meat and by Brain
             Farming for its brain, and Butchery itself yields a different cut
             as the skill levels. Collapsing that back to one item per node
             would need either a node per cut standing in the same room or a
             dispatch chain inside the skill, and the whole point of this
             registry is that adding content is a dict entry.
"""



from dataclasses import dataclass, field

from world.item_database import ITEM_DB

import systems.gameplay.progression.skills.constants as skill_constants



@dataclass
class GatherableYield:
    """
    Purpose: One thing a node can be worked for, by one skill, at one level.

    A yield is identified by its item_key. Nothing usefully yields the same
    item by two routes off one node, so a second identifier would only be a
    second thing to keep in step with the first -- the same reasoning
    ItemDef.key follows.

    secondary_xp is the "cutting + butchery XP" arrow on the skill-tree map:
    a harvest teaches the skill that owns it AND, in smaller measure, the
    other gathering skills the motion has in common. It is a plain
    {skill_key: xp} dict rather than a fraction of xp_reward, so a chain that
    wants an unusual split says so instead of the split being computed from a
    rule nobody can see in the table.
    """
    item_key: str
    skill_key: str
    required_level: int
    xp_reward: int
    secondary_xp: dict = field(default_factory=dict)



@dataclass
class GatherableDef:
    key: str
    node_name: str
    yields: tuple

    # Whether this node can be worked with bare hands, at the cost of
    # BARE_HAND_HP_COST hit points. XP is unaffected -- the exemption opens
    # the bootstrap deadlock, it doesn't also make the harvest worthless.
    #
    # Without this, gathering deadlocks the game: cutting requires an axe, the
    # only axe is crafted from scrap metal, and the only scrap metal comes
    # from cutting. A brand-new character in the wastes has no way in. The
    # opening quest turns that deadlock into its first lesson -- the player
    # tears a chunk off a rusty pole with their hands, bleeds for it, and the
    # android teaches them the skill they just did badly.
    #
    # Default False, so the exemption is granted per node rather than assumed.
    bare_hands: bool = False


    def yields_for_skill(self, skill_key: str) -> list:
        """
        Purpose: Every yield on this node that the named skill produces.

        Entry:
            skill_key is a skill key string.

        Exit/Returns:
            Returns a list of GatherableYield sorted by required_level
            ascending, so a caller picking "the best one unlocked" walks it
            backwards and one picking "the first one" gets the starter cut.

        Module Globals:
            None.

        Methodology:
            Filter and sort. The sort is here rather than at each call site
            because two readers already need the order and disagreeing about
            it would give the player a different cut from the command than the
            skills panel promised.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/10/2026
        """
        matches = [
            entry for entry in self.yields if entry.skill_key == skill_key
        ]

        matches.sort(key=lambda entry: entry.required_level)

        return matches


    def skill_keys(self) -> tuple:
        """
        Purpose: Which gathering skills can work this node at all.

        Entry:
            No conditions.

        Exit/Returns:
            Returns a tuple of skill key strings, in first-declared order and
            without duplicates.

        Module Globals:
            None.

        Methodology:
            Declaration order, deliberately, not sorted: the table's author
            decides which skill a node is mainly for, and that order is what
            a tie-break falls back on when the player carries no tool at all.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 09/10/2026
        """
        ordered = []

        for entry in self.yields:
            if entry.skill_key not in ordered:
                ordered.append(entry.skill_key)

        return tuple(ordered)



# Every gatherable node in the world. Adding a node type means adding one
# entry here -- the typeclass and its skill def read everything they need from
# this dict instead of each restating their own constants.
#
# Note there is deliberately no per-instance level/XP override any more. Both
# used to be stamped onto the spawned node as db.required_level and
# db.xp_reward "so a per-spawn override remains possible", and nothing ever
# overrode them. With a list of yields the override would have to be a list
# too, and a second copy of the table living in object rows is exactly the
# thing CLAUDE.md's "an import path belongs in the code, never in a database
# row" warns about, one step removed.
GATHERABLE_REGISTRY: dict[str, GatherableDef] = {
    "rusty_pole": GatherableDef(
        key="rusty_pole",
        node_name="Rusty Pole",
        bare_hands=True,
        yields=(
            GatherableYield(
                item_key="rusty_metal_chunk",
                skill_key=skill_constants.CUTTING_SKILL_KEY,
                required_level=0,
                xp_reward=10,
            ),
        ),
    ),
    "metal_pole": GatherableDef(
        key="metal_pole",
        node_name="Metal Pole",
        yields=(
            GatherableYield(
                item_key="metal_chunk",
                skill_key=skill_constants.CUTTING_SKILL_KEY,
                required_level=10,
                xp_reward=25,
            ),
        ),
    ),

    # ─── Corpses ──────────────────────────────────────────────────────────
    # A corpse is a node like any other here, which is the point: it is left
    # by NpcDef.corpse_key rather than spawned onto a tile, but everything
    # downstream -- the skill, the command, the skills panel, the client's
    # affordance list -- reads it through this same table.
    #
    # Butchery owns the cuts and teaches most of the XP; the cutting arrow on
    # the skill-tree map is the secondary award. Level 0 gets the chuck, and
    # the filet opens at 10 -- from then on both are offered and the player
    # picks (see GatheringSkill._choose_yield).
    "mutant_raider_corpse": GatherableDef(
        key="mutant_raider_corpse",
        node_name="Mutant Raider corpse",
        bare_hands=True,
        yields=(
            GatherableYield(
                item_key="mutant_raider_chuck",
                skill_key=skill_constants.BUTCHERY_SKILL_KEY,
                required_level=0,
                xp_reward=25,
                secondary_xp={skill_constants.CUTTING_SKILL_KEY: 5},
            ),
            GatherableYield(
                item_key="mutant_raider_filet",
                skill_key=skill_constants.BUTCHERY_SKILL_KEY,
                required_level=10,
                xp_reward=45,
                secondary_xp={skill_constants.CUTTING_SKILL_KEY: 10},
            ),
        ),
    ),
}


# Fail at import time if a def points at an item that doesn't exist, rather
# than a player discovering it the moment they successfully gather the node.
_missing_items = [
    f"{gatherable_def.key}:{entry.item_key}"
    for gatherable_def in GATHERABLE_REGISTRY.values()
    for entry in gatherable_def.yields
    if entry.item_key not in ITEM_DB
]
if _missing_items:
    raise KeyError(
        f"GATHERABLE_REGISTRY: item_key not found in ITEM_DB for: {_missing_items}"
    )


# A node with no yields affords nothing and would serve a client an empty
# action list while still rendering as a gathering node. Caught here for the
# same reason the missing-item check is: at import, not at the harvest.
_empty_nodes = [
    gatherable_def.key
    for gatherable_def in GATHERABLE_REGISTRY.values()
    if not gatherable_def.yields
]
if _empty_nodes:
    raise ValueError(
        f"GATHERABLE_REGISTRY: no yields declared for: {_empty_nodes}"
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



def get_gatherable_for_node(node: object) -> GatherableDef | None:
    """
    Purpose: Resolve the definition behind a spawned gathering node.

    Entry:
        node is any live object. It need not be a gathering node.

    Exit/Returns:
        Returns the GatherableDef, or None when the object is not a node or
        carries a key no longer in the registry.

    Module Globals:
        GATHERABLE_REGISTRY read.

    Methodology:
        db.gatherable_key is the one thing that makes an object a gathering
        node, and it is read through `attributes.get` so this is safe on an
        object that has no such attribute at all -- which is most of them,
        because every failed `cut <something>` lands here first.

        This routine is what replaced the per-skill `is_cutting_node()` /
        `is_butchery_node()` predicates. Those were a method on the typeclass
        per gathering skill, so adding Butchery meant editing every node
        typeclass to answer a second question about itself. What actually
        decides whether Butchery works a thing is the registry, not the
        typeclass.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/10/2026
    """
    attributes = getattr(node, "attributes", None)

    if attributes is None:
        return None

    gatherable_key = attributes.get("gatherable_key", default=None)

    if not gatherable_key:
        return None

    return GATHERABLE_REGISTRY.get(gatherable_key)



def get_gatherables_for_skill(skill_key: str) -> list:
    """
    Purpose: Every (node, yield) pair a given skill unlocks.

    Entry:
        skill_key is a skill key string to match against
        GatherableYield.skill_key.

    Exit/Returns:
        Returns a list of (GatherableDef, GatherableYield) tuples, sorted by
        (required_level, node_name) so the skills menu lists easier unlocks
        first.

    Module Globals:
        GATHERABLE_REGISTRY read.

    Methodology:
        Flattens node -> yields, because a node is no longer one unlock: the
        corpse is two rows in Butchery's panel (chuck at 0, filet at 10) and
        one more in Brain Farming's. Returning defs alone would have made the
        panel show one row per node at whichever level happened to be first.

        Mirrors systems.gameplay.crafting.crafting_service.get_recipes_for_skill.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/05/2026
    """
    matches = [
        (gatherable_def, entry)
        for gatherable_def in GATHERABLE_REGISTRY.values()
        for entry in gatherable_def.yields
        if entry.skill_key == skill_key
    ]

    matches.sort(key=lambda pair: (pair[1].required_level, pair[0].node_name))

    return matches



def get_yield_item_name(gatherable_yield: GatherableYield) -> str:
    """
    Purpose: Resolve the display name of the item a yield produces.

    Entry:
        gatherable_yield is a GatherableYield whose item_key is a valid
        ITEM_DB key.

    Exit/Returns:
        Returns the item's display name string.

    Module Globals:
        ITEM_DB read.

    Methodology:
        Single ITEM_DB lookup, so an item's display name stays owned solely
        by its ItemDef rather than duplicated onto the yield.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/05/2026
    """
    item_name = ITEM_DB[gatherable_yield.item_key].name

    return item_name
