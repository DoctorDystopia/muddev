# mygame/world/maps/test_neo_cairo.py

from evennia.contrib.grid.xyzgrid.xymap_legend import MapNode


MAPSTR = r"""

+ 0 1 2

2 #-#-#
     /
1 #-#
  |  \
0 #---#

+ 0 1 2


"""
# use only defaults
LEGEND = {}

# tweak only one room. The 'xyz_room/exit' parents are made available
# by adding the xyzgrid prototypes to settings during installation.
# the '*' are wildcards and allows for giving defaults on this map.
PROTOTYPES = {
    (0, 0): {
        "prototype_parent": "xyz_room",
        "key": "A nice glade",
        "desc": "Sun shines through the branches above.",
    },
    (0, 0, 'e'): {
        "prototype_parent": "xyz_exit",
        "desc": "A quiet path through the foilage",
    },
    ('*', '*'): {
        "prototype_parent": "xyz_room",
        "key": "In a bright forest",
        "desc": "There is green all around.",
    },
    ('*', '*', '*'): {
        "prototype_parent": "xyz_exit",
        "desc": "The path leads further into the forest.",
    },
}

# collect all info for this one map
XYMAP_DATA = {
    "zcoord": "mymap",  # important!
    "map": MAPSTR,
    "legend": LEGEND,
    "prototypes": PROTOTYPES,
    "options": {}
}

# this can be skipped if there is only one map in module
XYMAP_DATA_LIST = [
    XYMAP_DATA
]