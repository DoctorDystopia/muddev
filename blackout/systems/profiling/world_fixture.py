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

# Grid dimensions. Sized to the PRODUCTION visibility radius, not to a
# comfortable one. statefeed's STATEFEED_ENTITY_RADIUS is 10, and the live maps
# (oasis, oasis_outskirts, neo_cairo) are 59-81 nodes inside a coordinate span
# of roughly 13x12 -- so a radius-10 neighbourhood on any of them is the whole
# map. A 13x13 fixture is that span with room to spare, which makes
# _visible_rooms here return what it returns in the live game rather than a
# fraction of it.
#
# Was 9x9 until 09/03/2026, chosen as the smallest square containing a radius-3
# neighbourhood. That was the right size for the question the harness was
# asking then, and the wrong size for the one it is asking now: at 9x9 a
# radius-10 emit costs 81 tiles instead of the map's 169, which understates
# every crowd measurement by half. The radius-3 scenarios are unaffected --
# they still resolve 49 tiles and 147 objects -- because CENTRE moved with the
# grid.
FIXTURE_WIDTH: int = 13
FIXTURE_HEIGHT: int = 13

# Objects placed on each tile. Three is enough that a per-object query cost
# separates visibly from a per-room one in the captured count.
ITEMS_PER_TILE: int = 3

# The centre tile, where the observing character stands.
CENTRE_X: int = 6
CENTRE_Y: int = 6

# Crowd sizes the scaling scenarios step through. The point of a THREE-point
# ladder rather than a before/after pair is that it separates a linear cost
# from a quadratic one: a cost that doubles from 1 to 8 and doubles again from
# 8 to 24 is per-observer overhead, while one that grows with the SQUARE of
# the step is the fan-out multiplying the payload.
#
# 24 is not a stress number. It is a busy Oasis on a weekend, and it is well
# inside the "comfortable concurrency sits in the tens" that
# statefeed/subscriptions.py cites as Evennia's own envelope.
CROWD_SIZES = (1, 8, 24)

# Where a crowd stands. ONE tile, because a graphical client's worst case is
# everybody in the same room -- which is also what a market, a bank or a quest
# hand-in produces every day.
#
# That tile is a far corner rather than the centre, and for the reason
# scenarios/engine.py's _arm_crowd spells out at length: scenarios share one
# world, pkgutil discovers scenario modules alphabetically, and "crowd" sorts
# before "database" and "statefeed". So the crowd is already standing when the
# radius-3 scenarios are measured, and a crowd on the CENTRE tile would silently
# grow the world those scenarios walk -- which is the one form of shared state
# harness.py does not accept. Radius 3 around (6, 6) covers x and y in 3..9;
# this tile is outside it.
#
# It is also a different corner from _arm_crowd's, so the two crowds do not
# pile onto one tile and change each other's room.contents walks.
CROWD_TILE = (0, FIXTURE_HEIGHT - 1)

# First session id handed to a stand-in client. Well clear of the low ids the
# EvenniaTest fixtures use, so a stub session can never be confused for one of
# theirs while reading a profile.
_CROWD_SESSID_BASE: int = 9000


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
        self._crowd = []


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


    def crowd(self, size: int) -> list:
        """
        Purpose: Hand back `size` player-shaped observers, each with a
                 subscribed client attached, creating them on first request.

        Entry:
            size - how many observers the caller needs. Must not exceed the
                   number a previous call already asked for plus what this one
                   adds; the pool only grows.

        Exit/Returns:
            Returns the first `size` members of the crowd, in creation order.

        Module Globals:
            CROWD_TILE read. FIXTURE-scoped `_crowd` written.

        Methodology:
            The pool GROWS and is never rebuilt. Scenarios run in registration
            order against one shared world, so a ladder that walks 1, 8, 24
            asks for a superset each time -- and tearing the crowd down between
            steps would mean the 24-observer measurement was taken against a
            world that had just done 24 deletions, with the idmapper and the
            contents cache in a state no live server is ever in.

            The consequence a reader has to know: a scenario registered AFTER a
            crowd scenario is measured against a world with that crowd standing
            in it. That is why the crowd stands on the centre tile and why the
            crowd scenarios are registered last -- see scenarios/crowd.py.

            Characters, not NPCs. serialize_entity reads hp/max_hp and the
            interact affordance off a real combatant, so a crowd of Objects
            would produce a smaller payload than a crowd of players and would
            understate exactly the number being measured.

        Notes/References:
            client_stub.attach_client is what makes emit() do work rather than
            return early. Without it every number here would be zero.

        Author: Nick Hobar
        Creation date: 09/03/2026
        """
        from typeclasses.characters import Character

        from .client_stub import attach_client

        arena = self.tiles[CROWD_TILE]

        while len(self._crowd) < size:
            index = len(self._crowd)
            player = create_object(Character,
                                   key=f"profiling_player_{index}",
                                   location=arena)
            attach_client(player, sessid=_CROWD_SESSID_BASE + index)
            self._crowd.append(player)

        return self._crowd[:size]


    def full_map(self) -> list:
        """Hand back every tile, which is what a radius-10 emit resolves to.

        Named for what it MEANS rather than for the radius that produces it.
        STATEFEED_ENTITY_RADIUS is 10 and the live maps are smaller than that
        in every direction, so `_visible_rooms` returns the whole map -- and a
        scenario that said `rooms_within(10)` would read as though the radius
        were the interesting number, when the interesting number is that the
        radius stopped bounding anything.
        """
        return list(self.tiles.values())
