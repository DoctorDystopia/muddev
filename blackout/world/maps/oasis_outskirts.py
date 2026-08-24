# mygame/world/maps/test_oasis_outskirts.py



from evennia.contrib.grid.xyzgrid.xymap_legend import MapNode, MapTransitionNode
# Imported for its side effect: the module's @register_spawner decorators must
# have run before this map spawns tiles that reference those spawner keys.
import typeclasses.skill_facilities as skill_facilities  # noqa: F401

# from .legend import BLACKOUT_LEGEND



# The topological layout for the sector
MAPSTR = r'''
                          1
    + 0 1 2 3 4 5 6 7 8 9 0

   10 #   # # #     #-#-T
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
    4 #-#---+-#-#---#-#-#-m
       \|   | |  \ / \| | |
    3 #-#-m-#-#-m-#-#-#-#-†
      | | | | | | | | | | |
    2 #-#-M-M-e-#-m-#-#-#-#
      | | | | | | | | | | |
    1 #-#-#-#-†-#-#-#-#-†-#
      | | | | | | | | | | |
    0 #-#-m-#-#-#-†-#-#-#-m

    + 0 1 2 3 4 5 6 7 8 9 1
                          0

'''



class MetalPoleNode(MapNode):
    """
    Custom MapNode for Metal Poles.
    Uses a distinct 'P' symbol on the map so rooms at these
    coordinates actually get spawned (prototype must be set).
    """
    display_symbol = "|#c0c0c0†|n"
    prototype = "xyz_room"



class MutantRaiderNPCNode(MapNode):
    """
    Custom MapNode for Mutant Raider characters.
    """
    display_symbol = "|#afff00m|n"
    prototype = "xyz_room"



class BigMutantNPCNode(MapNode):
    """
    Custom MapNode for Big Mutant characters.
    """
    display_symbol = "|#73804FM|n"
    prototype = "xyz_room"



class FloatingEyeNPCNode(MapNode):
    """
    Custom MapNode for Floating Eye characters.
    """
    display_symbol = "|#f88379e|n"
    prototype = "xyz_room"



class ToOasisNode(MapTransitionNode):
    """
    MapNode to teleport to the Oasis.
    """
    display_symbol = "|gT|n"
    target_map_xyz = (1, 2, "oasis")
    prototype = None



LEGEND = {
    "†": MetalPoleNode,
    "m": MutantRaiderNPCNode,
    "M": BigMutantNPCNode,
    "e": FloatingEyeNPCNode,
    "T": ToOasisNode,
}



# The PROTOTYPES dictionary allows for map-wide defaults and exact coordinate overrides.
# The '*' characters act as wildcards for (X, Y) nodes and (X, Y, direction) links.
_metal_pole = {
    "prototype_parent": "xyz_room",
    "typeclass": "typeclasses.rooms.GridTile",
    "key": "Metal pole clearing",
    "desc": "A metal pole. Maybe I can cut it down?",
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

_npc_floating_eye = {
    "prototype_parent": "xyz_room",
    "typeclass": "typeclasses.rooms.GridTile",
    "key": "Floating Eye Tile",
    "desc": "Terrified of needles.",
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

    # Gathering node overrides for Metal Poles
    (6, 0): _metal_pole,
    (9, 1): _metal_pole,
    (4, 1): _metal_pole,
    (10, 3): _metal_pole,

    # Hostile NPC node overrides
    (2, 0): _npc_mutant_raider,
    (10, 0): _npc_mutant_raider,
    (6, 2): _npc_mutant_raider,
    (2, 3): _npc_mutant_raider,
    (5, 3): _npc_mutant_raider,
    (10, 4): _npc_mutant_raider,
    (3, 2): _npc_big_mutant,
    (2, 2): _npc_big_mutant,
    (4, 2): _npc_floating_eye,
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
