# mygame/world/maps/test_neo_cairo.py

from evennia.contrib.grid.xyzgrid.xymap_legend import MapNode

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
    6   #-#-#-#   #-#-#-#-#
           \      | | |
    5   #---#-#---#-#-#
       /    |
    4 #-----+-# #---#
       \    | |  \ /
    3   #-#-#-#   #   #
            | |  / \ /
    2       #-#-#---#
            |       |
    1       #-#     #
            |
    0 #-#---#

    + 0 1 2 3 4 5 6 7 8 9 1
                          0

'''

class TradeTownNode(MapNode):
    """
    Custom MapNode for Trade Town.
    Overrides the display symbol to 'X' with a strict visual length of 1.
    """
    display_symbol = "x"

# LEGEND = {
#     **BLACKOUT_LEGEND,
# }
LEGEND = {}

# The PROTOTYPES dictionary allows for map-wide defaults and exact coordinate overrides.
# The '*' characters act as wildcards for (X, Y) nodes and (X, Y, direction) links.
PROTOTYPES = {
    # Default Room Prototype (applies to all undefined coordinates)
    ('*', '*'): {
        "typeclass": "typeclasses.rooms.GridTile",
        "key": "Trade Town Sector 1",
        "desc": "A bustling sector of the trade town.",
    },
    # Default Exit Prototype (applies to all undefined links)
    ('*', '*', '*'): {
        "prototype_parent": "xyz_exit",
        "desc": "A path through the trade town.",
    },
    # Example Override: Customize a specific coordinate (e.g., the SW corner)
    (0, 0): {
        "prototype_parent": "xyz_room",
        "typeclass": "typeclasses.rooms.GridTile",
        "key": "Sector 1 Entrance",
        "desc": "The main gates of Trade Town Sector 1. The city sprawls to the north and east.",
    }
}

# Aggregate all configuration data for the parser
XYMAP_DATA = {
    "zcoord": "trade town sector 1",
    "map": MAPSTR,
    "legend": LEGEND,
    "prototypes": PROTOTYPES,
    "options": {}
}

# XYMAP_DATA_LIST is parsed first by the engine, allowing for multiple maps per module.
XYMAP_DATA_LIST = [
    XYMAP_DATA
]