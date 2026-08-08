# mygame/world/maps/test_oasis_outskirts.py

from evennia.contrib.grid.xyzgrid.xymap_legend import MapNode
# Imported for its side effect: the module's @register_spawner decorators must
# have run before this map spawns tiles that reference those spawner keys.
import typeclasses.skill_facilities as skill_facilities  # noqa: F401

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
    6   #-#-#-#-#-#-#-#-#-#
           \  | | | | | | |
    5   #---#-#-#-#-#-#-#-#
       /    | | |   | | | |
    4 #-#---+-#-#---#-#-#-M
       \|   | |  \ / \| | |
    3 #-#-M-#-#-M-#-#-#-#-†
      | | | | | | | | | | |
    2 #-#-#-H-#-#-M-#-#-#-#
      | | | | | | | | | | |
    1 #-#-#-#-†-#-#-#-#-†-#
      | | | | | | | | | | |
    0 #-#-M-#-#-#-†-#-#-#-M

    + 0 1 2 3 4 5 6 7 8 9 1
                          0

'''


class RustyPoleNode(MapNode):
    """
    Custom MapNode for Rusty Poles.
    Uses a distinct 'P' symbol on the map so rooms at these
    coordinates actually get spawned (prototype must be set).
    """
    display_symbol = "|300†|n"
    prototype = "xyz_room"


class MutantRaiderNPCNode(MapNode):
    """
    Custom MapNode for Mutant Raider characters.
    """
    display_symbol = "|#afff00M|n"
    prototype = "xyz_room"

class BigMutantNPCNode(MapNode):
    """
    Custom MapNode for Big Mutant characters.
    """
    display_symbol = "|#73804FH|n"
    prototype = "xyz_room"


LEGEND = {
    "†": RustyPoleNode,
    "M": MutantRaiderNPCNode,
    "H": BigMutantNPCNode,
}


# The PROTOTYPES dictionary allows for map-wide defaults and exact coordinate overrides.
# The '*' characters act as wildcards for (X, Y) nodes and (X, Y, direction) links.
_rusty_pole = {
    "prototype_parent": "xyz_room",
    "typeclass": "typeclasses.rooms.GridTile",
    "key": "Pole clearing",
    "desc": "A rusted pole. Maybe I can cut it down?",
}

_npc_mutant_raider = {
    "prototype_parent": "xyz_room",
    "typeclass": "typeclasses.rooms.GridTile",
    "key": "Mutant Raider Tile",
    "desc": "A mutant raider with a crude weapon.",
}

_npc_big_mutant = {
    "prototype_parent": "xyz_room",
    "typeclass": "typeclasses.rooms.GridTile",
    "key": "Big Mutant Tile",
    "desc": "A large mutant with a crude weapon.",
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
        "key": "Oasis Outskirts Entrance",
        "desc": "The main entryway of the Oasis Outskirts. The desert sprawls to the north and east.",
    },

    # Gathering node overrides for Rusty Poles
    (6, 0): _rusty_pole,
    (9, 1): _rusty_pole,
    (4, 1): _rusty_pole,
    (10, 3): _rusty_pole,

    # Hostile NPC node overrides
    (2, 0): _npc_mutant_raider,
    (10, 0): _npc_mutant_raider,
    (6, 2): _npc_mutant_raider,
    (2, 3): _npc_mutant_raider,
    (5, 3): _npc_mutant_raider,
    (10, 4): _npc_mutant_raider,
    (3, 2): _npc_big_mutant,
}

# Aggregate all configuration data for the parser
XYMAP_DATA = {
    "zcoord": "oasis_outskirts",
    "map": MAPSTR,
    "legend": LEGEND,
    "prototypes": PROTOTYPES,
    "options": {}
}

# XYMAP_DATA_LIST is parsed first by the engine, allowing for multiple maps per module.
XYMAP_DATA_LIST = [
    XYMAP_DATA
]
