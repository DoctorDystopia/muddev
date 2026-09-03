"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/03/2026
Description: The synthetic world every scenario is measured against.

Why a synthetic world and not the live one
------------------------------------------
CLAUDE.md's first warning is that blackout/scripts/ acts on the live
development database, and that a loop over the game's modules once deleted 347
grid rooms. A profiling harness pointed at that database would be the same
class of tool: it spawns NPCs, moves characters and issues writes, and it wants
to do so hundreds of times. So it does not go near it. Every scenario runs
inside a Django test database that is created for the run and thrown away
after it, and this module is what fills that empty database with something
worth measuring.

Why the world is a parameterised grid rather than a real map
------------------------------------------------------------
world/maps/*.py describes maps whose size is a content decision. Profiling
against one couples the audit's numbers to whichever map an author last edited,
so the fixture takes its dimensions as arguments and the scenarios declare what
they need. A radius-3 serialisation is 49 tiles whether the live game currently
has a 49-tile map or not.

Why the counts are deliberately larger than today's game
--------------------------------------------------------
The bug this harness exists to catch is invisible at development scale -- the
exact words systems/tick/tests/test_query_cost.py uses about the O(N*M) walk it
guards. One player in a room with two items profiles as flat no matter how the
code is written. The fixture is therefore sized to where the game is going, not
where it is, and the sizes are named constants so that a future run can say
what it assumed.
"""

from evennia.utils.create import create_object

from typeclasses.rooms import GridTile


# ─── Public constant definitions ─────────────────────────────────────────────

# The z-coordinate every fixture tile is built on. A string, because xyzgrid
# stores the map name there and coordinates are string Tags underneath.
FIXTURE_MAP_NAME = "profiling_fixture"

# Grid dimensions. 9x9 is the smallest square that fully contains a radius-3
# neighbourhood around a centre tile with a margin, so a radius-3 scenario is
# measuring 49 real rooms rather than 49 requests that fall off the edge.
FIXTURE_WIDTH: int = 9
FIXTURE_HEIGHT: int = 9

# Objects placed on each tile. Three is enough that a per-object query cost
# separates visibly from a per-room one in the captured count.
ITEMS_PER_TILE: int = 3

# The centre tile, where the observing character stands.
CENTRE_X: int = 4
CENTRE_Y: int = 4


# ─── Public routines ─────────────────────────────────────────────────────────

class ProfilingWorld:
    """A built grid, its occupants, and the observer standing in the middle.

    Constructed once per harness run and handed to every scenario factory.
    Holding the objects rather than re-resolving them is deliberate: a scenario
    that had to look its own room up would be measuring the lookup.
    """

    def __init__(self, width: int = FIXTURE_WIDTH,
                 height: int = FIXTURE_HEIGHT,
                 items_per_tile: int = ITEMS_PER_TILE):
        self.width = width
        self.height = height
        self.items_per_tile = items_per_tile
        self.tiles = {}
        self.items = []
        self.character = None
        self.centre = None


    def build(self) -> "ProfilingWorld":
        """
        Purpose: Create every tile, item and character the scenarios need.

        Entry:
            A Django test database must already be in place and empty of this
            fixture. Calling twice on one instance would duplicate the world.

        Exit/Returns:
            Returns self, so a caller can build and bind in one statement.

        Module Globals:
            FIXTURE_MAP_NAME read.

        Methodology:
            Tiles first, then contents, then the observer -- because an item
            created with `location=tile` needs the tile to exist, and because
            the observer must be placed last so that scenarios excluding it
            from a serialisation are excluding the object they think they are.

            create_object with a location, NOT move_to. CLAUDE.md records that
            the two differ in whether at_object_receive fires, and the fixture
            wants the cheap one: these are scenery for a serialiser to walk,
            not items entering an inventory.

        Notes/References:
            GridTile.create rather than XYZRoom.create -- see
            systems/combat/auras/tests/test_aura_targeting.py for why the
            subclass is the one that matches filter_family().

        Author: Nick Hobar
        Creation date: 09/03/2026
        """
        self._build_tiles()
        self._build_contents()
        self._build_observer()

        return self


    def _build_tiles(self) -> None:
        """Create the width x height grid of GridTiles."""
        for x in range(self.width):
            for y in range(self.height):
                tile = GridTile.create(key=f"tile_{x}_{y}",
                                       xyz=(x, y, FIXTURE_MAP_NAME))[0]
                self.tiles[(x, y)] = tile

        self.centre = self.tiles[(CENTRE_X, CENTRE_Y)]


    def _build_contents(self) -> None:
        """Place items_per_tile objects on every tile.

        The typeclass is passed explicitly. create_object's first positional
        IS the typeclass, and omitting it here resolved to None rather than to
        a default -- a TypeError deep inside the fixture rather than at the
        call, which is worth the one extra import to avoid.
        """
        from typeclasses.objects import Object

        for (x, y), tile in self.tiles.items():
            for index in range(self.items_per_tile):
                item = create_object(Object,
                                     key=f"scrap_{x}_{y}_{index}",
                                     location=tile)
                self.items.append(item)


    def _build_observer(self) -> None:
        """Place the observing character on the centre tile."""
        from typeclasses.characters import Character

        self.character = create_object(Character,
                                       key="profiling_observer",
                                       location=self.centre)


    def rooms_within(self, radius: int) -> list:
        """
        Purpose: Hand back the tiles a radius-N neighbourhood covers.

        Entry:
            radius - non-negative. Zero returns the centre tile alone.

        Exit/Returns:
            Returns a list of GridTile objects, always including the centre.

        Module Globals:
            CENTRE_X and CENTRE_Y read.

        Methodology:
            Resolved from the fixture's own dict rather than through
            targeting.rooms_within_radius, so that a scenario measuring a
            SERIALISER is handed its input directly and does not fold the
            targeting query into the number. The scenario that means to
            measure targeting calls the real function itself.

        Notes/References:
            The box is trimmed to the grid, so a radius wider than the fixture
            returns every tile rather than raising.

        Author: Nick Hobar
        Creation date: 09/03/2026
        """
        found = []

        for x in range(CENTRE_X - radius, CENTRE_X + radius + 1):
            for y in range(CENTRE_Y - radius, CENTRE_Y + radius + 1):
                tile = self.tiles.get((x, y))

                if tile is not None:
                    found.append(tile)

        return found
