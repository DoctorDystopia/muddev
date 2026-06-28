# mygame/world/maps/test_oasis.py

from evennia.contrib.grid.xyzgrid.xymap_legend import MapNode


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
    6   #-#-#-#   #-#-#-#-#
           \      | | |
    5   #---#-#---#-#-#
       /    |
    4 #-----+-# #---#
       \    | |  \ /
    3   #-#-#-#   #   #
            | |  / \ /
    2       #-#-#-#-#
            |       |
    1       #-#-#-#-#-#-P-#
            | | | | | | | |
    0 #-#-#-#-#-#-P-#-#-#-#

    + 0 1 2 3 4 5 6 7 8 9 1
                          0

'''


class RustyPoleNode(MapNode):
    """
    Custom MapNode for Rusty Poles.
    Uses a distinct 'P' symbol on the map so rooms at these
    coordinates actually get spawned (prototype must be set).
    """
    display_symbol = "P"
    prototype = "xyz_room"


class OasisOutskirtsNode(MapNode):
    """
    Custom MapNode for Oasis Outskirts.
    Overrides the display symbol to 'X' with a strict visual length of 1.
    """
    display_symbol = "x"

# Map the default '#' string symbol to our custom OasisOutskirtsNode
# LEGEND = {
#     "#": OasisOutskirtsNode
# }
LEGEND = {
    "P": RustyPoleNode
}

# The PROTOTYPES dictionary allows for map-wide defaults and exact coordinate overrides.
# The '*' characters act as wildcards for (X, Y) nodes and (X, Y, direction) links.
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
    (6, 0): {
        "prototype_parent": "xyz_room",
        "typeclass": "typeclasses.rooms.GridTile",
        "key": "Pole clearing",
        "desc": "A rusted pole. Maybe I can cut it down?",
    },
    (9, 1): {
        "prototype_parent": "xyz_room",
        "typeclass": "typeclasses.rooms.GridTile",
        "key": "Pole clearing",
        "desc": "A rusted pole. Maybe I can cut it down?",
    }
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
