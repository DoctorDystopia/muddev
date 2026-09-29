"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: The object kinds of the tile grid, one row for each kind.

             An object in a chunk file is `{kind, x, y, rotation}`. The kind
             is a key here, never a typeclass path (CLAUDE.md: "an import path
             belongs in the code"). The Godot editor places from this list,
             through the generated constants.

             ONE KIND FOR EACH VARIANT, EXCEPT THE WORDS OF A SIGN. Each
             shopkeeper is its own kind. OSRS does the same. A signpost is
             one kind, `signpost`, and each placement holds its own words in
             the `text` of its chunk object. The terrain editor edits them.
             Nick chose this on 09/27/2026. On 09/24/2026 he chose one kind
             for each sign, with the words in this table. That kept the words
             out of the editor.

             Each row names the spawner that stands the thing up: a key of
             `SPAWNER_REGISTRY` in `typeclasses/spawners.py`. A kind of the
             category `OBJECT_TEXT_CATEGORY` stands a signpost with the text of
             its object. A test checks every spawner name, so the table cannot
             rot.

             THE ROOM TEXT. A tile room stores no name. `look` on a tile shows
             the `name` and the `desc` of the first kind on it that has a
             name. A tile with no named kind shows the texts of its area.
             `world/tile_text.py` owns the rule. The texts here are the room
             keys and descs of the xyzgrid prototypes, so a player sees the
             same room text as today. A sign has no name, because a sign
             labels a tile and does not name it.

             A TRANSITION has a `target`: the world tile that a walker goes to
             when it steps onto the tile of the transition. It has no spawner,
             because no object stands for it. The maps stay islands until Nick
             joins them (Phase 4 decision, 09/24/2026). Each target is the
             `target_map_xyz` of the xyzgrid node that the kind replaces, at
             the chunk of its map. `world/tests/test_tile_content.py` checks
             that each placed transition lands on an open tile.

             A LANDMARK names its tile and stands nothing up. The respawn
             point is one: world/respawn.py finds its tile by the kind key.
             Like every chunk object, it pins its tile.

             A CLIMB kind is a ladder or stairs (Phase 7). A walker who
             stands on its tile types `climb up` or `climb down`, and lands
             on the same tile one plane up or down. A few kinds serve every
             placement, because the landing needs no target in the row (Nick,
             09/26/2026). Like a landmark, it stands nothing up.

             SCENERY. A kind that stands nothing up is not an entity, so no
             `room_players` row tells the client what to draw. Its `scenery`
             names what the client stands on the tile of each placement. The
             server names, the client draws (CLAUDE.md). A kind that stands
             something up has no scenery, because its entity is already on
             the screen. A kind with no scenery shows nothing, as before. The
             key names a model record in `assets/models/`, or a primitive of
             `SCENERY_PRIMITIVES`: a plain shape until art arrives. The climb
             kinds use the primitives. `world/tests/test_tile_content.py`
             checks these rules.

             This module imports no game code. `clientexport.py` reads it,
             and a typeclass import there loads Evennia into the exporter.

             DESIGN-0011 sections 6.2 and 6.3.
"""

from dataclasses import dataclass

from systems.core.tilegrid import constants as tile_const


@dataclass(frozen=True)
class ObjectKind:
    """
    One object kind. The `key` is the name that a chunk file stores. The
    `category` is one of `OBJECT_CATEGORIES` in the tile grid constants. The
    `spawner` is a key of `SPAWNER_REGISTRY`, or "" when nothing stands up.
    The `name` and the `desc` are the room texts of a tile that holds this
    kind. The `target` is the world tile (x, y) of a transition, or () for
    every other kind. The `climbs` are the directions of a climb kind
    (CLIMB_UP, CLIMB_DOWN), or () for every other kind. The `scenery` is the
    model asset key or the primitive that the client stands on the tile, or
    "" for nothing.
    """

    key: str
    category: str
    spawner: str = ""
    name: str = ""
    desc: str = ""
    target: tuple = ()
    climbs: tuple = ()
    scenery: str = ""


_FACILITY = tile_const.OBJECT_CATEGORY_FACILITY
_GATHERING = tile_const.OBJECT_CATEGORY_GATHERING
_LANDMARK = tile_const.OBJECT_CATEGORY_LANDMARK
_NPC = tile_const.OBJECT_CATEGORY_NPC
_SIGN = tile_const.OBJECT_CATEGORY_SIGN
_TRANSITION = tile_const.OBJECT_CATEGORY_TRANSITION
_CLIMB = tile_const.OBJECT_CATEGORY_CLIMB

# The object kind that marks the respawn point in a chunk file. world/respawn.py
# finds its tile by this key, and the terrain editor check counts it. Here,
# not in respawn.py, because the client export reads this module and
# respawn.py imports Evennia.
RESPAWN_KIND: str = "respawn_point"

# The one signpost kind. Each placement holds its own words in its chunk
# object text.
SIGNPOST_KIND: str = "signpost"

# The teleporter pad that the client stands on each transition tile. The key
# of assets/models/world_objects/map_transition.toml. The xyzgrid maps drew
# the same model on each transition node until Phase 4b.
TRANSITION_SCENERY: str = "map_transition"

_UP = (tile_const.CLIMB_UP,)
_DOWN = (tile_const.CLIMB_DOWN,)
_BOTH = (tile_const.CLIMB_UP, tile_const.CLIMB_DOWN)


def _named(key: str, category: str, spawner: str, desc: str) -> ObjectKind:
    """
    A kind whose room name is its spawner key, as on the xyzgrid maps. There,
    the room key was both the name that a player saw and the key of the
    spawner.
    """
    return ObjectKind(key, category, spawner=spawner, name=spawner, desc=desc)


# Grouped by category, in the order the editor lists them. Each spawner string
# is the room key that a `@register_spawner` decorator declares. The test in
# world/tests/test_tile_content.py checks each against the live registry.
_KIND_ROWS: tuple = (
    _named("bank", _FACILITY, "Bank",
           "A Hegemony secure banking facility with a row of storage "
           "terminals."),
    _named("foundry_furnace", _FACILITY, "Foundry Furnace Facility",
           "A roaring hot Foundry."),
    _named("metalsmith_anvil", _FACILITY, "Metalsmith Anvil Facility",
           "A Metalsmith's heavy steel anvil."),
    _named("rendering_cooker", _FACILITY, "Rendering Cooker Facility",
           "A rendering cooker, its vat still warm. The smell arrives before "
           "you do."),
    _named("curing_chamber", _FACILITY, "Curing Chamber Facility",
           "A curing chamber, cold and dry, hung with hooks and smelling of "
           "salt."),
    _named("gunsmith_bench", _FACILITY, "Gunsmith Bench Facility",
           "A Gunsmith's workbench."),
    _named("gastronomy_worktable", _FACILITY, "Gastronomy Worktable Facility",
           "A scrubbed steel worktable, a pan already warming over a low "
           "flame."),

    _named("rusty_pole", _GATHERING, "Rusty pole clearing",
           "A rusted pole. Maybe I can cut it down?"),
    _named("metal_pole", _GATHERING, "Metal pole clearing",
           "A metal pole. Maybe I can cut it down?"),
    _named("copper_pole", _GATHERING, "Copper pole clearing",
           "A copper pole. Maybe I can cut it down?"),

    _named("lone_android", _NPC, "Lone Android",
           "An lonely looking android who lives in the wastes of the "
           "Sahara."),
    _named("shopkeeper_oasis", _NPC, "Shopkeeper",
           "A makeshift market stall shaded by a tattered awning."),
    _named("mutant_raider", _NPC, "Mutant Raider Tile",
           "A mutant raider with a crude weapon."),
    _named("big_mutant", _NPC, "Big Mutant Tile",
           "A large mutant with a crude weapon."),
    _named("floating_eye", _NPC, "Floating Eye Tile",
           "Terrified of needles."),
    _named("mutant_crab", _NPC, "Mutant Crab Tile",
           "A mutant crab with a hard shell."),
    _named("mutant_giant", _NPC, "Mutant Giant Tile",
           "A mutant giant, slow and enormous."),

    # A signpost. Its words are the `text` of each chunk object.
    ObjectKind(SIGNPOST_KIND, _SIGN),

    # The respawn point. world/respawn.py finds it by this key. The words are
    # those of the xyzgrid room at (0, 0) of the oasis map.
    ObjectKind(RESPAWN_KIND, _LANDMARK, name="Oasis Entrance",
               desc="The main entryway of the Oasis. The desert sprawls to "
                    "the north and east."),

    # The four joins of the three maps. oasis is chunk (0, 0),
    # oasis_outskirts is chunk (1, 0), and azm_plains is chunk (2, 0).
    ObjectKind("transition_oasis_to_outskirts", _TRANSITION,
               target=(72, 10), scenery=TRANSITION_SCENERY),
    ObjectKind("transition_outskirts_to_oasis", _TRANSITION, target=(1, 2),
               scenery=TRANSITION_SCENERY),
    ObjectKind("transition_outskirts_to_azm_plains", _TRANSITION,
               target=(129, 2), scenery=TRANSITION_SCENERY),
    ObjectKind("transition_azm_plains_to_outskirts", _TRANSITION,
               target=(73, 8), scenery=TRANSITION_SCENERY),

    # Ladders and stairs (Phase 7). Generic: every placement shares a kind,
    # because a climb lands on the same tile one plane up or down.
    # A way up draws the ladder or the stairs. A way down draws a hatch. The
    # ladder or the stairs of the plane below reach up to that hatch.
    ObjectKind("ladder_up", _CLIMB, name="Ladder",
               desc="A ladder leads up.", climbs=_UP,
               scenery=tile_const.SCENERY_LADDER),
    ObjectKind("ladder_down", _CLIMB, name="Ladder",
               desc="A ladder leads down.", climbs=_DOWN,
               scenery=tile_const.SCENERY_HATCH),
    ObjectKind("ladder_both", _CLIMB, name="Ladder",
               desc="A ladder leads up and down.", climbs=_BOTH,
               scenery=tile_const.SCENERY_LADDER),
    ObjectKind("stairs_up", _CLIMB, name="Staircase",
               desc="A staircase leads up.", climbs=_UP,
               scenery=tile_const.SCENERY_STAIRS),
    ObjectKind("stairs_down", _CLIMB, name="Staircase",
               desc="A staircase leads down.", climbs=_DOWN,
               scenery=tile_const.SCENERY_HATCH),
)

# key -> ObjectKind, in the order of _KIND_ROWS.
OBJECT_KINDS: dict = {row.key: row for row in _KIND_ROWS}
