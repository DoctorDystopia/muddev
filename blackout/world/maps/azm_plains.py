# mygame/world/maps/azm_plains.py



from evennia.contrib.grid.xyzgrid.xymap_legend import MapNode, MapTransitionNode
# Imported for its side effect: the module's @register_spawner decorators must
# have run before this map spawns tiles that reference those spawner keys.
import typeclasses.skill_facilities as skill_facilities  # noqa: F401
from typeclasses.signs import (
    SIGNPOST_DESC_ATTR,
    SIGNPOST_LABEL_ATTR,
    SIGNPOST_ROOM_KEY,
)

# from .legend import BLACKOUT_LEGEND



# The topological layout for the sector
MAPSTR = r'''
                          1 1 1 1 1 1 1 1 1 1 2
    + 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0

   20 #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-†-#-#-#
      |x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|
   19 #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-†-#-#-#
      |x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|
   18 #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-†-#-#-#
      |x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|
   17 #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-†-#-#-#
      |x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|
   16 #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-†-#-#-#
      |x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|
   15 #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-†-#-#-#
      |x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|
   14 #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-†-#-#-#
      |x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|
   13 #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-†-#-#-#
      |x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|
   12 #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-†-#-#-#
      |x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|
   11 #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-†-#-#-#
      |x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|
   10 #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-†-#-#-#
      |x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|
    9 #-#-#-#-#-#-#-#-#-#-#-#-#-#-G-#-#-†-#-#-#
      |x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|
    8 #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-†-#-#-#
      |x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|
    7 #-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-†-#-#-#
      |x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|
    6 #-#-#-#-#-#-#-#-#-#-#-#-G-#-#-#-#-†-#-#-#
      |x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|
    5 #-#-#-#-#-#-#-c-#-#-#-#-#-#-#-#-#-†-#-#-#
      |x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|
    4 #-#-c-#-#-#-#-#-c-#-#-#-#-#-#-#-#-†-#-#-#
      |x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|
    3 #-#-m-#-#-#-#-c-#-#-†-#-#-#-#-#-#-†-#-#-#
       \|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|
    2 T-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-†-#-#-#
       /|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|
    1 #-#-#-#-†-#-#-#-#-†-#-#-#-#-#-#-#-†-#-#-#
      |x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|x|
    0 #-#-#-#-#-#-†-#-#-#-#-#-#-#-#-#-#-†-#-#-#

    + 0 1 2 3 4 5 6 7 8 9 1 1 1 1 1 1 1 1 1 1 2
                          0 1 2 3 4 5 6 7 8 9 0

'''



class CopperPoleNode(MapNode):
    """
    Custom MapNode for Copper Poles.
    Uses a distinct 'P' symbol on the map so rooms at these
    coordinates actually get spawned (prototype must be set).
    """
    display_symbol = "|300†|n"
    prototype = "xyz_room"



# class BankNode(MapNode):
#     """
#     Custom MapNode for banking facilities.
#     """
#     display_symbol = "|#4488FFß|n"
#     prototype = "xyz_room"



# class FurnaceFacilityNode(MapNode):
#     """
#     Custom MapNode for foundry furnaces.
#     """
#     display_symbol = "|520F|n"
#     prototype = "xyz_room"



# class AnvilFacilityNode(MapNode):
#     """
#     Custom MapNode for blacksmith anvils.
#     """
#     display_symbol = "|wA|n"
#     prototype = "xyz_room"



# class RenderingCookerFacilityNode(MapNode):
#     """
#     Custom MapNode for rendering cookers.
#     """
#     display_symbol = "|#cc7722R|n"
#     prototype = "xyz_room"



# class CuringChamberFacilityNode(MapNode):
#     """
#     Custom MapNode for curing chambers.
#     """
#     display_symbol = "|#88aaccC|n"
#     prototype = "xyz_room"



# class GastroWorktableFacilityNode(MapNode):
#     """
#     Custom MapNode for Gastronomy worktables.
#     """
#     display_symbol = "|#ddaa44G|n"
#     prototype = "xyz_room"



# class NPCNode(MapNode):
#     """
#     Custom MapNode for NPC characters.
#     """
#     display_symbol = "|y!|n"
#     prototype = "xyz_room"



# class ShopNPCNode(MapNode):
#     """
#     Custom MapNode for Shop NPC characters.
#     """
#     display_symbol = "|Y§|n"
#     prototype = "xyz_room"



class MutantRaiderNPCNode(MapNode):
    """
    Custom MapNode for Mutant Raider characters.
    """
    display_symbol = "|#afff00m|n"
    prototype = "xyz_room"



class MutantCrabNPCNode(MapNode):
    """
    Custom MapNode for Mutant Crab characters.
    """
    display_symbol = "|#afff00c|n"
    prototype = "xyz_room"



class MutantGiantNPCNode(MapNode):
    """
    Custom MapNode for Mutant Giant characters.
    """
    display_symbol = "|#8B7355G|n"
    prototype = "xyz_room"



class ToOasisOutskirtsNode(MapTransitionNode):
    """
    MapNode to teleport to the Oasis Outskirts.
    """
    display_symbol = "|gT|n"
    target_map_xyz = (9, 8, "oasis_outskirts")
    prototype = None



LEGEND = {
    "†": CopperPoleNode,
    # "ß": BankNode,
    # "F": FurnaceFacilityNode,
    # "A": AnvilFacilityNode,
    # "R": RenderingCookerFacilityNode,
    # "C": CuringChamberFacilityNode,
    # "G" now belongs to the Mutant Giant, on both maps that hold one. The
    # Gastronomy worktable below needs a different letter when it comes back.
    # "G": GastroWorktableFacilityNode,
    # "!": NPCNode,
    # "§": ShopNPCNode,
    "m": MutantRaiderNPCNode,
    "c": MutantCrabNPCNode,
    "G": MutantGiantNPCNode,
    "T": ToOasisOutskirtsNode,
}



# The PROTOTYPES dictionary allows for map-wide defaults and exact coordinate overrides.
# The '*' characters act as wildcards for (X, Y) nodes and (X, Y, direction) links.
_copper_pole = {
    "prototype_parent": "xyz_room",
    "typeclass": "typeclasses.rooms.GridTile",
    "key": "Copper pole clearing",
    "desc": "A copper pole. Maybe I can cut it down?",
}

# _bank = {
#     "prototype_parent": "xyz_room",
#     "typeclass": "typeclasses.rooms.GridTile",
#     "key": "Bank",
#     "desc": "A Hegemony secure banking facility with a row of storage terminals.",
# }

# _furnace = {
#     "prototype_parent": "xyz_room",
#     "typeclass": "typeclasses.rooms.GridTile",
#     "key": "Foundry Furnace Facility",
#     "desc": "A roaring hot Foundry.",
# }

# _anvil = {
#     "prototype_parent": "xyz_room",
#     "typeclass": "typeclasses.rooms.GridTile",
#     "key": "Metalsmith Anvil Facility",
#     "desc": "A Metalsmith's heavy steel anvil.",
# }

# The facility standing on this tile spawns off the room KEY, matched against
# @register_spawner("Rendering Cooker Facility") in
# typeclasses/skill_facilities.py. That key is the one string here that must not
# be retyped -- a typo leaves a tile that looks like a facility and has no
# cooker on it, with nothing raised either way.
# _rendering_cooker = {
#     "prototype_parent": "xyz_room",
#     "typeclass": "typeclasses.rooms.GridTile",
#     "key": "Rendering Cooker Facility",
#     "desc": "A rendering cooker, its vat still warm. The smell arrives before you do.",
# }

# Sited four tiles east of the cooker, and the proximity is the point: a chuck
# can go straight into the chamber OR through the cooker first and into the
# chamber after, and those two routes make two different foods. A player who
# cannot see both facilities at once has no reason to notice the choice exists.
#
# Same rule as the cooker above -- the facility spawns off the room KEY, matched
# against @register_spawner("Curing Chamber Facility").
# _curing_chamber = {
#     "prototype_parent": "xyz_room",
#     "typeclass": "typeclasses.rooms.GridTile",
#     "key": "Curing Chamber Facility",
#     "desc": "A curing chamber, cold and dry, hung with hooks and smelling of salt.",
# }

# Not placed in PROTOTYPES -- the coordinate is yours. Put a `G` on MAPSTR and
# add `(x, y): _gastro_worktable,` beside the other skill-node overrides below.
#
# This one wants to sit with the cooker and the chamber rather than near the
# corpses: every Gastronomy recipe consumes two things that came out of those
# two facilities, so the worktable is where a player ENDS a circuit, not where
# they start one.
#
# Same rule as the two above -- the facility spawns off the room KEY, matched
# against @register_spawner("Gastronomy Worktable Facility").
# _gastro_worktable = {
#     "prototype_parent": "xyz_room",
#     "typeclass": "typeclasses.rooms.GridTile",
#     "key": "Gastronomy Worktable Facility",
#     "desc": "A scrubbed steel worktable, a pan already warming over a low flame.",
# }

# Not placed in PROTOTYPES -- the coordinates are yours. A signpost needs no new
# MAPSTR symbol and no tile of its own, so there are two ways to place one and
# they go beside the skill-node overrides below:
#
#     (1, 0): _signpost("OASIS\nBANK: EAST\nFORGE: NORTH"),
#     (6, 3): _signed(_furnace, "FOUNDRY\nNO NAKED FLAMES"),
#
# The first is a tile that is ONLY a sign. The second labels a tile that is
# already something else -- the furnace keeps its key, its desc, its minimap
# colour and its facility, and the sign stands beside it in the tile's ring.
# Both take an optional last argument describing the post itself, for when the
# stock board on a rusted pole is not what is standing there.
#
# Worth spending on arrival tiles, junctions and the facilities a new player has
# to be taught to recognise. A sign that says something a player could have
# worked out teaches them to stop reading the next one.
def _signed(prototype, label, desc=""):
    """
    Purpose: Any tile prototype, with a signpost standing on it.

    Entry:
        prototype - an existing prototype dict from this module.
        label     - what the sign reads. Capped and cleaned by the spawner, so
                    a line authored over the limit is cut rather than refused.
        desc      - what the POST looks like, when the stock description is
                    not what is standing there.

    Exit/Returns:
        Returns a NEW prototype dict. The one passed in is not touched.

    Module Globals:
        SIGNPOST_LABEL_ATTR and SIGNPOST_DESC_ATTR read.

    Methodology:
        COPIES rather than mutates, and this is the whole reason the helper
        exists instead of a line adding `attrs` at the call site. Every
        facility prototype in this file is ONE dict shared by every coordinate
        that names it -- `_copper_pole` is at four -- so mutating one to sign a
        single tile would sign all of them, and the symptom would be four
        identical signs appearing on a rebuild nobody asked to change.

        Existing `attrs` are merged rather than replaced, for the same reason:
        a prototype that already declares one keeps it. Nothing in this file
        declares one today, which is exactly when a merge is cheap to write
        and impossible to remember later.

        The sign dispatches off the ATTRIBUTE, not the room key, so the tile
        keeps whatever it already was -- its key, its desc, its minimap colour
        and whatever its key spawner stands up. That is the difference between
        labelling a facility and replacing it.

    Notes/References:
        typeclasses/signs.py spawn_signpost consumes both attributes and
        re-asserts them on every rebuild, so this file stays their owner.

    Author: Nick Hobar
    Creation date: 09/12/2026
    """
    signed = dict(prototype)
    attrs = list(signed.get("attrs", []))

    attrs.append((SIGNPOST_LABEL_ATTR, label))

    if desc:
        attrs.append((SIGNPOST_DESC_ATTR, desc))

    signed["attrs"] = attrs

    return signed


# A tile whose only purpose is the sign standing on it. The key is what gives
# it a name in `look` and a colour on the minimap; the sign itself arrives the
# same way it does on a furnace.
_bare_signpost = {
    "prototype_parent": "xyz_room",
    "typeclass": "typeclasses.rooms.GridTile",
    "key": SIGNPOST_ROOM_KEY,
    "desc": "A signpost leans out of the sand, bolted to a rusted pole.",
}


def _signpost(label, desc=""):
    """
    Purpose: A tile that is only a signpost.

    Entry:
        label - what the sign reads.
        desc  - what the POST looks like, optionally.

    Exit/Returns:
        Returns a prototype dict, for a coordinate row in PROTOTYPES below.

    Module Globals:
        _bare_signpost read.

    Methodology:
        Defined THROUGH _signed rather than beside it. The two differ only in
        which tile the sign lands on, so writing the attribute list twice would
        be two places to get the attribute names right -- and the copy is what
        keeps `_bare_signpost` from accumulating every label ever authored.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    return _signed(_bare_signpost, label, desc)


# _npc_lone_android = {
#     "prototype_parent": "xyz_room",
#     "typeclass": "typeclasses.rooms.GridTile",
#     "key": "Lone Android",
#     "desc": "An lonely looking android who lives in the wastes of the Sahara.",
# }

# _npc_shopkeeper = {
#     "prototype_parent": "xyz_room",
#     "typeclass": "typeclasses.rooms.GridTile",
#     "key": "Shopkeeper",
#     "desc": "A makeshift market stall shaded by a tattered awning.",
# }

_npc_mutant_raider = {
    "prototype_parent": "xyz_room",
    "typeclass": "typeclasses.rooms.GridTile",
    "key": "Mutant Raider Tile",
    "desc": "A mutant raider with a crude weapon.",
}


_npc_mutant_crab = {
    "prototype_parent": "xyz_room",
    "typeclass": "typeclasses.rooms.GridTile",
    "key": "Mutant Crab Tile",
    "desc": "A mutant crab with a hard shell.",
}


_npc_mutant_giant = {
    "prototype_parent": "xyz_room",
    "typeclass": "typeclasses.rooms.GridTile",
    "key": "Mutant Giant Tile",
    "desc": "A mutant giant, slow and enormous.",
}



PROTOTYPES = {
    # Default Room Prototype (applies to all undefined coordinates)
    ('*', '*'): {
        "typeclass": "typeclasses.rooms.GridTile",
        "key": "Oasis",
        "desc": "sand...everywhere.",
    },
    # Default Exit Prototype (applies to all undefined links)
    ('*', '*', '*'): {
        "prototype_parent": "xyz_exit",
        "desc": "A path through the oasis.",
    },
    # Example Override: Customize a specific coordinate (e.g., the SW corner)
    (0, 0): {
        "prototype_parent": "xyz_room",
        "typeclass": "typeclasses.rooms.GridTile",
        "key": "Oasis Entrance",
        "desc": "The main entryway of the Oasis. The desert sprawls to the north and east.",
    },

    # Gathering node overrides for Copper Poles
    (6, 0): _copper_pole,
    (9, 1): _copper_pole,
    (4, 1): _copper_pole,
    (10, 3): _copper_pole,

    # Skill node overrides
    # (10, 0): _bank,
    # (10, 0): _signed(_bank, "Bank"),
    # (6, 3): _furnace,
    # (6, 3): _signed(_furnace, "Foundry Furnace"),
    # (4, 6): _anvil,
    # (4, 6): _signed(_anvil, "Metalsmith Anvil"),
    # (0, 10): _rendering_cooker,
    # (0, 10): _signed(_rendering_cooker, "Rendering Cooker"),
    # (4, 10): _curing_chamber,
    # (4, 10): _signed(_curing_chamber, "Curing Chamber"),
    # (2, 10): _gastro_worktable,
    # (2, 10): _signed(_gastro_worktable, "Gastronomy Worktable"),
    # (2, 0): _npc_lone_android,
    # (10, 4): _npc_shopkeeper,
    (2, 3): _npc_mutant_raider,

    (7, 3): _npc_mutant_crab,
    (7, 5): _npc_mutant_crab,
    (8, 4): _npc_mutant_crab,

    # The two giants stand deep in the plains, well past the crabs and the
    # entrance at (0, 2). A player walks to this tier rather than meeting it.
    (12, 6): _npc_mutant_giant,
    (14, 9): _npc_mutant_giant,
}



# Aggregate all configuration data for the parser
XYMAP_DATA = {
    "zcoord": "azm_plains",
    "map": MAPSTR,
    "legend": LEGEND,
    "prototypes": PROTOTYPES,
    "options": {}
}



# XYMAP_DATA_LIST is parsed first by the engine, allowing for multiple maps per module.
XYMAP_DATA_LIST = [
    XYMAP_DATA
]
