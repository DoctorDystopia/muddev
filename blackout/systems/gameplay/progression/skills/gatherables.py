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
from systems.gameplay.progression.skills.skill_defs.gathering import (
    constants as gather_constants,
)



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

    menu_label is the SHORT name of this cut: the word a right-click row says
    and the word a player types after the `=`. It is not a second name for the
    item -- the item's name is still the ItemDef's, and every line the harvest
    sends uses it -- it is the part of that name which tells this node's cuts
    apart. "mutant raider raw filet" and "mutant raider raw chuck" differ in
    one word, and a menu row reading "Butcher mutant raider raw filet from
    Mutant Raider corpse" names the corpse twice to say it.

    Empty means "use the item's name", so a node with one yield per skill --
    every node but the corpse today -- declares nothing.
    """
    item_key: str
    skill_key: str
    required_level: int
    xp_reward: int
    secondary_xp: dict = field(default_factory=dict)
    menu_label: str = ""



@dataclass(frozen=True)
class GatherChance:
    """
    Purpose: How often one swing yields, for one class of tool.

    A pair, not a number, because the whole point of the OSRS roll is that a
    level changes what a tool is worth. `low` is the numerator at level 0 and
    `high` the numerator at the top of the ladder, both in
    CHANCE_DENOMINATOR units -- so a pair lifted off the wiki means here what
    it meant there, and a designer can check one table against the other
    without arithmetic. See skill_defs/gathering/roll.py for the line drawn
    between them.

    tool_tier is ItemDef.tier, read off the tool the character is holding.
    THE TIER IS THE ONLY THING A TOOL CHANGES. Cadence is a constant
    (gather_constants.SWING_TICKS), because two knobs multiply and a table
    cannot predict how fast the tiers then separate.

    A node declares one of these per tier it wants to distinguish, not one
    per tier that exists. chance_for_tier fills the gaps -- see there for the
    rule, which is what keeps a new axe tier from needing an edit to every
    node in the world.
    """
    tool_tier: int
    low: int
    high: int



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

    # How often a swing yields, one entry per tool tier this node cares to
    # tell apart. See GatherChance, and chance_for_tier for the gap rule.
    chances: tuple = ()

    # The pair a bare-handed swing rolls on. Required of a node that sets
    # bare_hands, refused on one that does not -- the import check below
    # enforces both. It is a separate field rather than a tier of its own
    # because "no tool" is not a worse axe: it is the absence of the thing
    # the tier ladder measures, and a table that encodes it as tier 0 invites
    # a tier 0 axe that silently inherits the bare-handed numbers.
    bare_hand_chance: object = None

    # The chance that a swing which YIELDED also strips the node, per
    # harvester. Rolled only after a success, so a low level never depletes a
    # node faster than a high one -- see roll.depletes.
    #
    # Depletion is PER PLAYER. A spent node stands where it was, keeps its
    # place in the world pane, and offers nothing to the one player who spent
    # it until respawn_seconds have passed. Two players at one pole never
    # compete, and neither of them watches an object vanish under their feet.
    deplete_chance: float = 0.0

    # How long the node stays spent for that player. Meaningless, and refused
    # at import, on a node that cannot deplete.
    respawn_seconds: int = 0


    def chance_for_tier(self, tool_tier) -> object:
        """
        Purpose: The low/high pair a character with this tool rolls on.

        Entry:
            tool_tier is an ItemDef.tier, or None for bare hands.

        Exit/Returns:
            Returns a GatherChance, or None when the node declares no table
            that can serve this caller.

        Module Globals:
            None.

        Methodology:
            None means bare hands, and bare hands read their own pair. There
            is no tier that stands in for "no tool" -- see bare_hand_chance
            for why that separation is load-bearing.

            For a real tool: the HIGHEST declared tier at or below the one in
            hand. That is what lets a node describe three tiers when four
            exist, and it is what keeps a new axe tier from being an edit to
            every node in the world -- a tier nobody has written a row for
            inherits the best row below it rather than falling off the table.

            A tool below every declared tier falls back to the LOWEST row
            rather than to nothing. The node's required_level already decides
            who may work it, and refusing a swing to someone holding a tool
            the table forgot to mention is a second gate nobody declared.

        Notes/References:
            GatherChance carries the units and the reasoning.

        Author: Nick Hobar
        Creation date: 09/20/2026
        """
        if tool_tier is None:
            return self.bare_hand_chance

        if not self.chances:
            return None

        ordered = sorted(self.chances, key=lambda entry: entry.tool_tier)
        eligible = [
            entry for entry in ordered if entry.tool_tier <= tool_tier
        ]

        if eligible:
            return eligible[-1]

        return ordered[0]


    def yields_for_skill(self, skill_key: str) -> list:
        """
        Purpose: Every yield on this node that the named skill produces.

        Entry:
            skill_key is a skill key string.

        Exit/Returns:
            Returns a list of GatherableYield sorted by required_level
            ascending. The sort is stable, so yields that share a level keep
            their declaration order. GatheringSkill._default_yield depends on
            that order to break a tie, so "the last one" is NOT "the best
            one" where two yields share the top level.

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
        # The bootstrap node, and the only source of the first axe. Its
        # numbers are the most forgiving in the table on purpose: a bare
        # handed swing at level 0 lands about one time in six, so the opening
        # lesson costs a player patience rather than a session.
        #
        # It still depletes, briefly. A node that never gives out teaches a
        # new player that nodes never give out, and the first one they meet
        # is the wrong place to teach that.
        bare_hand_chance=GatherChance(
            tool_tier=gather_constants.BARE_HAND_TIER, low=40, high=130),
        chances=(
            GatherChance(tool_tier=0, low=100, high=220),
            GatherChance(tool_tier=1, low=130, high=240),
            GatherChance(tool_tier=2, low=160, high=250),
        ),
        deplete_chance=0.1,
        respawn_seconds=3,
        yields=(
            GatherableYield(
                item_key="rusty_metal_chunk",
                skill_key=skill_constants.SKILL_KEY_CUTTING,
                required_level=0,
                xp_reward=10,
            ),
        ),
    ),

    "metal_pole": GatherableDef(
        key="metal_pole",
        node_name="Metal Pole",
        # No bare_hand_chance, because the node does not set bare_hands. The
        # import check below refuses one without the other, in both
        # directions -- a pair nothing can roll is a number that looks tuned
        # and is dead.
        # chances=(
        #     GatherChance(tool_tier=0, low=60, high=180),
        #     GatherChance(tool_tier=1, low=90, high=210),
        #     GatherChance(tool_tier=2, low=120, high=235),
        # ),
        chances=(
            GatherChance(tool_tier=0, low=80, high=180),
            GatherChance(tool_tier=1, low=110, high=210),
            GatherChance(tool_tier=2, low=140, high=235),
        ),
        deplete_chance=0.1,
        respawn_seconds=8,
        yields=(
            GatherableYield(
                item_key="metal_chunk",
                skill_key=skill_constants.SKILL_KEY_CUTTING,
                required_level=10,
                xp_reward=25,
            ),
        ),
    ),

    "copper_pole": GatherableDef(
        key="copper_pole",
        node_name="Copper Pole",
        # A tier 0 axe can work this node and is bad at it. That is the
        # intended shape: the level gate says who may try, and the chance
        # table says what the attempt is worth. Refusing the low axe outright
        # would be a second gate, and the player who just reached level 20
        # would read it as the level not having counted.
        # chances=(
        #     GatherChance(tool_tier=0, low=35, high=140),
        #     GatherChance(tool_tier=1, low=60, high=175),
        #     GatherChance(tool_tier=2, low=90, high=210),
        # ),
        chances=(
            GatherChance(tool_tier=0, low=60, high=140),
            GatherChance(tool_tier=1, low=90, high=175),
            GatherChance(tool_tier=2, low=120, high=210),
        ),
        deplete_chance=0.1,
        respawn_seconds=12,
        yields=(
            GatherableYield(
                item_key="copper_chunk",
                skill_key=skill_constants.SKILL_KEY_CUTTING,
                required_level=20,
                xp_reward=45,
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
    #
    # DECLARATION ORDER IS THE DEFAULT. Inside one level, the yield declared
    # first is what an unasked harvest gives. Each hide is declared AFTER the
    # cut of its level, so it is available by name and never the default.
    
    "mutant_raider_corpse": GatherableDef(
        key="mutant_raider_corpse",
        node_name="Mutant Raider corpse",
        bare_hands=True,
        # Kinder numbers than any pole. A corpse is soft, and it is also the
        # reward for a fight the player already won -- a channel that makes
        # them stand over a body for half a minute taxes the wrong thing.
        bare_hand_chance=GatherChance(
            tool_tier=gather_constants.BARE_HAND_TIER, low=90, high=200),
        chances=(
            GatherChance(tool_tier=0, low=150, high=245),
            GatherChance(tool_tier=1, low=180, high=250),
            GatherChance(tool_tier=2, low=210, high=255),
        ),
        # DELIBERATELY ZERO. A corpse cannot deplete, because it does not
        # survive the first success: Corpse.consumed_by_harvest deletes it,
        # and consume_node runs before anything could mark it spent. A
        # non-zero value here would be a number that reads as tuned and can
        # never be rolled.
        deplete_chance=0.0,
        respawn_seconds=0,
        yields=(
            GatherableYield(
                item_key="mutant_raider_raw_chuck",
                skill_key=skill_constants.SKILL_KEY_BUTCHERY,
                required_level=0,
                xp_reward=25,
                secondary_xp={skill_constants.SKILL_KEY_CUTTING: 5},
                menu_label="chuck",
            ),
            GatherableYield(
                item_key="mutant_raider_raw_hide",
                skill_key=skill_constants.SKILL_KEY_BUTCHERY,
                required_level=0,
                xp_reward=25,
                secondary_xp={skill_constants.SKILL_KEY_CUTTING: 5},
                menu_label="hide",
            ),
            GatherableYield(
                item_key="mutant_raider_raw_filet",
                skill_key=skill_constants.SKILL_KEY_BUTCHERY,
                required_level=10,
                xp_reward=45,
                secondary_xp={skill_constants.SKILL_KEY_CUTTING: 10},
                menu_label="filet",
            ),
            # The level 10 hide, beside the level 10 cut. Curing turns it
            # into prime sinew, which is the string the tier 2 bow needs --
            # so the projectile chain opens at the same level the food chain
            # does, off the same corpse.
            GatherableYield(
                item_key="mutant_raider_prime_raw_hide",
                skill_key=skill_constants.SKILL_KEY_BUTCHERY,
                required_level=10,
                xp_reward=45,
                secondary_xp={skill_constants.SKILL_KEY_CUTTING: 10},
                menu_label="prime raw hide",
            ),
        ),
    ),

    # The second corpse, one tier up: chuck and hide at Butchery 20, filet and
    # prime raw hide at 30. The same four cuts and the same declaration order
    # as the raider, so a player who learned the first corpse already knows
    # this one.
    #
    # THE PRIME RAW HIDE HAS NO RECIPE YET, on purpose. Curing turns the
    # raider's prime hide into prime sinew and prime cured hide, and the giant
    # tier that needs either one adds those recipes then. A GATHERED material
    # with no recipe is a material a player sells. A CRAFTED item with no
    # recipe is the bug that left both hide capes uncraftable until
    # 09/21/2026 -- see MutantRaiderPrimeCuredHideRecipe.
    "mutant_giant_corpse": GatherableDef(
        key="mutant_giant_corpse",
        node_name="Mutant Giant corpse",
        bare_hands=True,
        # ITS OWN TABLE, HARSHER THAN THE RAIDER'S AT EVERY TIER. A giant hide
        # is thick, so the knife is what does the work here -- bare hands land
        # about one swing in five at level 0 against the raider corpse's one in
        # three. That is the one place in this table where a tool changes a
        # corpse rather than a pole, and it is the reason the giant corpse
        # does not simply reuse the raider's numbers.
        bare_hand_chance=GatherChance(
            tool_tier=gather_constants.BARE_HAND_TIER, low=50, high=150),
        chances=(
            GatherChance(tool_tier=0, low=110, high=210),
            GatherChance(tool_tier=1, low=145, high=230),
            GatherChance(tool_tier=2, low=180, high=245),
        ),
        # Zero for the same reason the raider corpse is zero: a corpse does not
        # survive the first success, so a depletion roll could never fire.
        deplete_chance=0.0,
        respawn_seconds=0,
        yields=(
            GatherableYield(
                item_key="mutant_giant_raw_chuck",
                skill_key=skill_constants.SKILL_KEY_BUTCHERY,
                required_level=20,
                xp_reward=50,
                secondary_xp={skill_constants.SKILL_KEY_CUTTING: 10},
                menu_label="chuck",
            ),
            GatherableYield(
                item_key="mutant_giant_raw_hide",
                skill_key=skill_constants.SKILL_KEY_BUTCHERY,
                required_level=20,
                xp_reward=50,
                secondary_xp={skill_constants.SKILL_KEY_CUTTING: 10},
                menu_label="hide",
            ),
            GatherableYield(
                item_key="mutant_giant_raw_filet",
                skill_key=skill_constants.SKILL_KEY_BUTCHERY,
                required_level=30,
                xp_reward=90,
                secondary_xp={skill_constants.SKILL_KEY_CUTTING: 20},
                menu_label="filet",
            ),
            GatherableYield(
                item_key="mutant_giant_prime_raw_hide",
                skill_key=skill_constants.SKILL_KEY_BUTCHERY,
                required_level=30,
                xp_reward=90,
                secondary_xp={skill_constants.SKILL_KEY_CUTTING: 20},
                menu_label="prime raw hide",
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



# A menu label is what the client sends back after the `=`, so two cuts of one
# node sharing one is a row that cannot say which it meant. Caught at import
# for the same reason the two checks above are: the alternative is a player
# clicking "filet" and being handed a chuck.
_ambiguous_labels = []
for _gatherable_def in GATHERABLE_REGISTRY.values():
    for _skill_key in _gatherable_def.skill_keys():
        _labels = [
            entry.menu_label.lower()
            for entry in _gatherable_def.yields_for_skill(_skill_key)
            if entry.menu_label
        ]

        if len(_labels) != len(set(_labels)):
            _ambiguous_labels.append(f"{_gatherable_def.key}:{_skill_key}")
if _ambiguous_labels:
    raise ValueError(
        f"GATHERABLE_REGISTRY: one skill's yields share a menu_label on: "
        f"{_ambiguous_labels}"
    )



def _chance_faults(gatherable_def) -> list:
    """
    Purpose: Every way one node's roll table is unusable, named.

    Entry:
        gatherable_def is a GatherableDef.

    Exit/Returns:
        Returns a list of fault strings. Empty when the table is sound.

    Module Globals:
        gather_constants.CHANCE_DENOMINATOR read.

    Methodology:
        Reports EVERY fault it finds rather than the first. A table written in
        one sitting usually has the same mistake in three rows, and an
        exception that names one row sends the author round the loop three
        times.

        The checks are the four ways a pair can be meaningless rather than
        merely badly tuned: no table at all, a numerator outside the units, a
        line that slopes downward, and two rows claiming one tier. Balance is
        not checked and must not be -- see CLAUDE.md "Never assert a balance
        value".

    Notes/References:
        Called by the import-time sweep below.

    Author: Nick Hobar
    Creation date: 09/20/2026
    """
    faults = []
    ceiling = gather_constants.CHANCE_DENOMINATOR
    entries = list(gatherable_def.chances)

    if gatherable_def.bare_hand_chance is not None:
        entries.append(gatherable_def.bare_hand_chance)

    if not entries:
        faults.append("declares no chance table")

    tiers = [entry.tool_tier for entry in gatherable_def.chances]

    if len(tiers) != len(set(tiers)):
        faults.append("declares two rows for one tool tier")

    for entry in entries:
        if not 0 <= entry.low <= ceiling:
            faults.append(f"tier {entry.tool_tier} low={entry.low} out of range")

        if not 0 <= entry.high <= ceiling:
            faults.append(f"tier {entry.tool_tier} high={entry.high} out of range")

        if entry.low > entry.high:
            faults.append(f"tier {entry.tool_tier} gets worse as it levels")

    return faults



# A node whose roll table cannot be read is a node the channel swings at
# forever, and the symptom is a player standing at a pole watching nothing
# happen. Caught at import for the same reason the three checks above are.
#
# The bare-hand pair is checked in BOTH directions. A node that grants the
# exemption and declares no pair cannot be worked by the character the
# exemption exists for. A node that declares a pair without the exemption has
# a tuned number nothing can ever roll, which reads as working and is not.
_chance_problems = []
for _gatherable_def in GATHERABLE_REGISTRY.values():
    for _fault in _chance_faults(_gatherable_def):
        _chance_problems.append(f"{_gatherable_def.key}: {_fault}")

    if _gatherable_def.bare_hands and _gatherable_def.bare_hand_chance is None:
        _chance_problems.append(
            f"{_gatherable_def.key}: bare_hands set with no bare_hand_chance")

    if not _gatherable_def.bare_hands and _gatherable_def.bare_hand_chance:
        _chance_problems.append(
            f"{_gatherable_def.key}: bare_hand_chance on a node that refuses "
            f"bare hands")

    if not 0.0 <= _gatherable_def.deplete_chance <= 1.0:
        _chance_problems.append(
            f"{_gatherable_def.key}: deplete_chance is not a probability")

    if _gatherable_def.deplete_chance and _gatherable_def.respawn_seconds <= 0:
        _chance_problems.append(
            f"{_gatherable_def.key}: depletes with no respawn_seconds")
if _chance_problems:
    raise ValueError(
        f"GATHERABLE_REGISTRY: unusable roll table on: {_chance_problems}"
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



def yield_menu_label(gatherable_yield: GatherableYield) -> str:
    """
    Purpose: The short name one cut is offered and asked for by.

    Entry:
        gatherable_yield is a GatherableYield.

    Exit/Returns:
        Returns the yield's menu_label, or the item's display name when it
        declares none.

    Module Globals:
        None.

    Methodology:
        One routine, because three readers need the same answer and any
        disagreement between them is a click that does not work: the
        right-click row a client draws, the command that row sends, and
        GatheringSkill's matching of what a player typed. A label offered in
        a menu that the parser will not accept is worse than no menu.

    Notes/References:
        GatherableYield.menu_label carries why a short name exists at all.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    label = gatherable_yield.menu_label or get_yield_item_name(gatherable_yield)

    return label
