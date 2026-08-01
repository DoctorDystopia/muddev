# mygame/world/maps/test_oasis.py

from evennia.contrib.grid.xyzgrid.xymap_legend import MapNode
import typeclasses.skill_facilities as skill_facilities

# from .legend import BLACKOUT_LEGEND


# The topological layout for the sector
MAPSTR = r'''
                          1
    + 0 1 2 3 4 5 6 7 8 9 0

   10 #   # # #     #-#-#
       \  | | |     |
    9   #-#-#-#     |
        |\    |     |
    8   #-#-#-#-----#-----#
        |     |           |
    7   #-#---#-#-#-#-#   |
        |         | | |   |
    6   #-#-#-A   #-#-#-#-#
           \      | | |
    5   #---#-#---#-#-#
       /    |
    4 #-----+-#-#---#-#-#-S
       \    | |  \ / \| | |
    3   #-M-#-#   F   #-#-P
        | | | |  / \ /| | |
    2 #-#-#-#-#-#-#-#-#-#-#
      | | | | | | | | | | |
    1 #-#-#-#-P-#-#-#-#-P-#
      | | | | | | | | | | |
    0 #-#-!-#-#-#-P-#-#-#-B

    + 0 1 2 3 4 5 6 7 8 9 1
                          0

'''


class OasisOutskirtsNode(MapNode):
    """
    Custom MapNode for Oasis Outskirts.
    Overrides the display symbol to 'X' with a strict visual length of 1.
    """
    display_symbol = "x"

class RustyPoleNode(MapNode):
    """
    Custom MapNode for Rusty Poles.
    Uses a distinct 'P' symbol on the map so rooms at these
    coordinates actually get spawned (prototype must be set).
    """
    display_symbol = "|300P|n"
    prototype = "xyz_room"


class BankNode(MapNode):
    """
    Custom MapNode for banking facilities.
    """
    display_symbol = "|#4488FFB|n"
    prototype = "xyz_room"


class FurnaceFacilityNode(MapNode):
    """
    Custom MapNode for foundry furnaces.
    """
    display_symbol = "|520F|n"
    prototype = "xyz_room"


class AnvilFacilityNode(MapNode):
    """
    Custom MapNode for blacksmith anvils.
    """
    display_symbol = "|wA|n"
    prototype = "xyz_room"


class NPCNode(MapNode):
    """
    Custom MapNode for NPC characters.
    """
    display_symbol = "|y!|n"
    prototype = "xyz_room"


class ShopNPCNode(MapNode):
    """
    Custom MapNode for Shop NPC characters.
    """
    display_symbol = "|YS|n"
    prototype = "xyz_room"


class MutantRaiderNPCNode(MapNode):
    """
    Custom MapNode for Mutant Raider characters.
    """
    display_symbol = "|RM|n"
    prototype = "xyz_room"


LEGEND = {
    "P": RustyPoleNode,
    "B": BankNode,
    "F": FurnaceFacilityNode,
    "A": AnvilFacilityNode,
    "!": NPCNode,
    "S": ShopNPCNode,
    "M": MutantRaiderNPCNode,
}


# The PROTOTYPES dictionary allows for map-wide defaults and exact coordinate overrides.
# The '*' characters act as wildcards for (X, Y) nodes and (X, Y, direction) links.
_rusty_pole = {
    "prototype_parent": "xyz_room",
    "typeclass": "typeclasses.rooms.GridTile",
    "key": "Pole clearing",
    "desc": "A rusted pole. Maybe I can cut it down?",
}

_bank = {
    "prototype_parent": "xyz_room",
    "typeclass": "typeclasses.rooms.GridTile",
    "key": "Bank",
    "desc": "A secure banking facility with rows of storage terminals.",
}

_furnace = {
    "prototype_parent": "xyz_room",
    "typeclass": "typeclasses.rooms.GridTile",
    "key": "Foundry Furnace Facility",
    "desc": "A roaring hot foundry.",
}

_anvil = {
    "prototype_parent": "xyz_room",
    "typeclass": "typeclasses.rooms.GridTile",
    "key": "Metalsmith Anvil Facility",
    "desc": "A Metalsmith's heavy steel anvil.",
}

_npc_lone_android = {
    "prototype_parent": "xyz_room",
    "typeclass": "typeclasses.rooms.GridTile",
    "key": "Lone Android",
    "desc": "An lonely looking android who lives in the wastes of the Sahara.",
}

_npc_shopkeeper = {
    "prototype_parent": "xyz_room",
    "typeclass": "typeclasses.rooms.GridTile",
    "key": "Shopkeeper",
    "desc": "A market stall shaded by a tattered awning, its wares displayed on a cloth.",
}

_npc_mutant_raider = {
    "prototype_parent": "xyz_room",
    "typeclass": "typeclasses.rooms.GridTile",
    "key": "Mutant Raider Tile",
    "desc": "A mutant raider with a crude weapon.",
}

PROTOTYPES = {
    # Default Room Prototype (applies to all undefined coordinates)
    ('*', '*'): {
        "typeclass": "typeclasses.rooms.GridTile",
        "key": "Oasis Outskirts",
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
        "desc": "The main entryway of Oasis Outskirts. The desert sprawls to the north and east.",
    },
    # Gathering node overrides for Rusty Poles
    (6, 0): _rusty_pole,
    (9, 1): _rusty_pole,
    (4, 1): _rusty_pole,
    (10, 3): _rusty_pole,
    # Skill node overrides
    (10, 0): _bank,
    (6, 3): _furnace,
    (4, 6): _anvil,
    (2, 0): _npc_lone_android,
    (10, 4): _npc_shopkeeper,
    (2, 3): _npc_mutant_raider,
}

# Aggregate all configuration data for the parser
XYMAP_DATA = {
    "zcoord": "oasis",
    "map": MAPSTR,
    "legend": LEGEND,
    "prototypes": PROTOTYPES,
    "options": {}
}

# XYMAP_DATA_LIST is parsed first by the engine, allowing for multiple maps per module.
XYMAP_DATA_LIST = [
    XYMAP_DATA
]
