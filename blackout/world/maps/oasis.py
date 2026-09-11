# mygame/world/maps/test_oasis.py



from evennia.contrib.grid.xyzgrid.xymap_legend import MapNode, MapTransitionNode
# Imported for its side effect: the module's @register_spawner decorators must
# have run before this map spawns tiles that reference those spawner keys.
import typeclasses.skill_facilities as skill_facilities  # noqa: F401

# from .legend import BLACKOUT_LEGEND



# The topological layout for the sector
MAPSTR = r'''
                          1
    + 0 1 2 3 4 5 6 7 8 9 0

   10 R   # # C     #-#-#
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
    4 #-----+-#-#---#-#-#-§
       \    | |  \ / \| | |
    3   #-m-#-#   F   #-#-†
        | | | |  / \ /| | |
    2 T-#-#-#-#-#-#-#-#-#-#
        | | | | | | | | | |
    1 #-#-#-#-†-#-#-#-#-†-#
      | | | | | | | | | | |
    0 #-#-!-#-#-#-†-#-#-#-ß

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



class BankNode(MapNode):
    """
    Custom MapNode for banking facilities.
    """
    display_symbol = "|#4488FFß|n"
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



class RenderingCookerFacilityNode(MapNode):
    """
    Custom MapNode for rendering cookers.
    """
    display_symbol = "|#cc7722R|n"
    prototype = "xyz_room"



class CuringChamberFacilityNode(MapNode):
    """
    Custom MapNode for curing chambers.
    """
    display_symbol = "|#88aaccC|n"
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
    display_symbol = "|Y§|n"
    prototype = "xyz_room"



class MutantRaiderNPCNode(MapNode):
    """
    Custom MapNode for Mutant Raider characters.
    """
    display_symbol = "|#afff00m|n"
    prototype = "xyz_room"



class ToOasisOutskirtsNode(MapTransitionNode):
    """
    MapNode to teleport to the Oasis Outskirts.
    """
    display_symbol = "|gT|n"
    target_map_xyz = (8, 10, "oasis_outskirts")
    prototype = None



LEGEND = {
    "†": RustyPoleNode,
    "ß": BankNode,
    "F": FurnaceFacilityNode,
    "A": AnvilFacilityNode,
    "R": RenderingCookerFacilityNode,
    "C": CuringChamberFacilityNode,
    "!": NPCNode,
    "§": ShopNPCNode,
    "m": MutantRaiderNPCNode,
    "T": ToOasisOutskirtsNode,
}



# The PROTOTYPES dictionary allows for map-wide defaults and exact coordinate overrides.
# The '*' characters act as wildcards for (X, Y) nodes and (X, Y, direction) links.
_rusty_pole = {
    "prototype_parent": "xyz_room",
    "typeclass": "typeclasses.rooms.GridTile",
    "key": "Rusty pole clearing",
    "desc": "A rusted pole. Maybe I can cut it down?",
}

_bank = {
    "prototype_parent": "xyz_room",
    "typeclass": "typeclasses.rooms.GridTile",
    "key": "Bank",
    "desc": "A Hegemony secure banking facility with a row of storage terminals.",
}

_furnace = {
    "prototype_parent": "xyz_room",
    "typeclass": "typeclasses.rooms.GridTile",
    "key": "Foundry Furnace Facility",
    "desc": "A roaring hot Foundry.",
}

_anvil = {
    "prototype_parent": "xyz_room",
    "typeclass": "typeclasses.rooms.GridTile",
    "key": "Metalsmith Anvil Facility",
    "desc": "A Metalsmith's heavy steel anvil.",
}

# The facility standing on this tile spawns off the room KEY, matched against
# @register_spawner("Rendering Cooker Facility") in
# typeclasses/skill_facilities.py. That key is the one string here that must not
# be retyped -- a typo leaves a tile that looks like a facility and has no
# cooker on it, with nothing raised either way.
_rendering_cooker = {
    "prototype_parent": "xyz_room",
    "typeclass": "typeclasses.rooms.GridTile",
    "key": "Rendering Cooker Facility",
    "desc": "A rendering cooker, its vat still warm. The smell arrives before you do.",
}

# Not placed in PROTOTYPES -- the coordinate is yours. Put a `C` on MAPSTR and
# add `(x, y): _curing_chamber,` beside the other skill-node overrides below.
#
# Worth putting it within sight of the cooker: a chuck can go straight into the
# chamber OR through the cooker first and into the chamber after, and those two
# routes make two different foods. A player who cannot see both facilities at
# once has no reason to notice the choice exists.
_curing_chamber = {
    "prototype_parent": "xyz_room",
    "typeclass": "typeclasses.rooms.GridTile",
    "key": "Curing Chamber Facility",
    "desc": "A curing chamber, cold and dry, hung with hooks and smelling of salt.",
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
    "desc": "A makeshift market stall shaded by a tattered awning.",
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

    # Gathering node overrides for Rusty Poles
    (6, 0): _rusty_pole,
    (9, 1): _rusty_pole,
    (4, 1): _rusty_pole,
    (10, 3): _rusty_pole,

    # Skill node overrides
    (10, 0): _bank,
    (6, 3): _furnace,
    (4, 6): _anvil,
    (0, 10): _rendering_cooker,
    (4, 10): _curing_chamber,
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
