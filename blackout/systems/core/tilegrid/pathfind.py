"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: A* on the tile grid, on demand, with a limit on the tiles that one
             search may expand.

Why on demand, and not a table
------------------------------
The xyzgrid contrib solves the path between every pair of nodes on a map when
the map is built. DESIGN-0011 section 5 measured that table at 320 MiB for one
64 x 64 map. A contiguous world cannot hold it. One A* search for each `goto`
costs nothing until a player asks, and it crosses chunk edges, because the
grid has no edges of its own.

The cost of a step
------------------
Every step costs 1, a diagonal step too. One step is one tick, as in OSRS. The
heuristic is thus the Chebyshev distance, which never overestimates the cost.
A* with that heuristic returns a shortest path.

Why the Manhattan key
---------------------
On open ground, many walks have the same length. A walk of 6 tiles east can
go 3 tiles north-east and 3 tiles south-east, in 6 ticks also. Each tile of
that walk has the same estimate and the same Chebyshev distance to the goal.
Thus, the push order alone broke the tie, and north-east is first in that
order. The player walked a tent shape north of the straight line (11/16/2026).

The heap now compares the Manhattan distance to the goal after the Chebyshev
distance. A tile past the row or the column of the goal has a larger Manhattan
distance, so it loses the tie. The walk goes diagonally until it is in line
with the goal, then straight. The key comes after the estimate, so the path
stays a shortest path. `tests/test_pathfind.py` checks that a walk on open
ground stays in the box of its start and its goal.

Why the limit
-------------
A goal that nothing can reach makes A* expand every tile it can reach. The
limit bounds that cost. A search that hits the limit returns None, the same as
a goal with no path, because the player sees the same result: no walk.

Why the loop reads the flags itself
-----------------------------------
The spike search called `TileGrid.check_step` 820,000 times for one walled-off
goal. Most of those steps touch no wall and no unwalkable tile. Such a step
is legal if its slope is in the walk limit. Thus, the loop reads the flags of
each tile that a step touches, and it compares the two tile heights itself.
It calls `check_step` only when a tile has a wall bit or an unwalkable bit.

The slope test is the same test as `TileGrid._check_slope`: the tile height
of the end against the tile height of the start. A diagonal step tests no
side tile for slope, in both places.

`check_step` stays the one owner of the rule. The fast path accepts only the
steps that `check_step` accepts. `tests/test_pathfind.py` compares the search
with a search that calls `check_step` for every step.

The nearest tile
----------------
This is an OSRS rule (Nick, 11/16/2026). A click on a sealed tile walks the
player to the nearest tile that a walk reaches. `find_nearest_path` is that
rule. A search with no path looks at a square around the goal. The square
has PATH_FALLBACK_RADIUS tiles on each side of the goal: 21 x 21, as in
OSRS. The rule picks the reached tile of that square that is nearest the
goal in a straight line. A tie goes to the shorter walk, then to the west,
then to the south. That is the OSRS order.

The search that failed gives the reached tiles, so the rule costs no second
search. A search that hit the limit can leave a tile at its edge with a cost
that is not the lowest. The walk to that tile is still legal.
"""

import heapq

from . import constants as const


# ─── Private constant definitions ────────────────────────────────────────────

# The cost of one step, in ticks.
_STEP_COST: int = 1

# The eight neighbour offsets, in a fixed order. A fixed order makes the path
# the same on every run when two paths are equally short.
_NEIGHBOUR_OFFSETS: tuple = tuple(const.DIRECTION_OFFSETS.values())

# A target tile with one of these bits is never a step. A tile off the loaded
# grid reads as blocked, so this also stops a walk off the world.
_UNWALKABLE: int = const.FLAGS_UNWALKABLE

# A step that touches a tile with one of these bits goes to check_step.
_SLOW_PATH_FLAGS: int = const.FLAGS_WALLS | const.FLAGS_UNWALKABLE


# ─── Private helper routines ─────────────────────────────────────────────────

def _chebyshev(start: tuple, goal: tuple) -> int:
    """Return the number of steps from start to goal on an open grid."""
    return max(abs(goal[0] - start[0]), abs(goal[1] - start[1]))


def _walk_back(came_from: dict, goal: tuple) -> list:
    """Return the path to `goal`, without the start tile, in walk order."""
    path = []
    node = goal

    while node in came_from:
        path.append(node)
        node = came_from[node]

    path.reverse()

    return path


def _squared_distance(tile: tuple, goal: tuple) -> int:
    """Return the square of the straight-line distance between two tiles."""
    dx = goal[0] - tile[0]
    dy = goal[1] - tile[1]

    return (dx * dx) + (dy * dy)


def _nearest_reached(cost_so_far: dict, goal: tuple, radius: int):
    """
    Return the reached tile in the square of `radius` around `goal` with the
    lowest (squared distance, cost, x, y), or None if the search reached no
    tile of that square. The module docstring, "The nearest tile".
    """
    span_x = range(goal[0] - radius, goal[0] + radius + 1)
    span_y = range(goal[1] - radius, goal[1] + radius + 1)
    square = ((x, y) for x in span_x for y in span_y)
    ranked = [(_squared_distance(tile, goal), cost_so_far[tile], tile)
              for tile in square if tile in cost_so_far]

    if not ranked:
        return None

    _distance, _cost, nearest = min(ranked)

    return nearest


# ─── Public routines ─────────────────────────────────────────────────────────

def find_path(grid, start: tuple, goal: tuple,
              max_expanded: int = const.PATH_MAX_EXPANDED,
              walk_limit=const.WALK_LIMIT):
    """
    Return a shortest walk from `start` to `goal`: a list of (x, y) tiles,
    one for each step, ending at `goal`, without the start tile. [] if
    start == goal. None if no path exists, or if the search hit
    `max_expanded` first. `_search` holds the method.
    """
    path, _cost_so_far, _came_from = _search(grid, start, goal, max_expanded,
                                             walk_limit)

    return path


def find_nearest_path(grid, start: tuple, goal: tuple,
                      radius: int = const.PATH_FALLBACK_RADIUS,
                      max_expanded: int = const.PATH_MAX_EXPANDED,
                      walk_limit=const.WALK_LIMIT):
    """
    Purpose: Find a shortest walk to `goal`, or else a walk to the nearest
             tile that a walk reaches, as in OSRS.

    Entry:
        grid         - a grid.TileGrid.
        start, goal  - (x, y) global tile coordinates.
        radius       - how far from the goal the nearest tile may be, on
                       each axis.
        max_expanded - the most tiles that the search may expand.
        walk_limit   - passed to TileGrid.check_step.

    Exit/Returns:
        (path, reached). `path` is a list of (x, y) tiles as find_path
        gives. `reached` is True if the path ends at `goal`. A path of []
        with reached False means that the start is the nearest tile. None
        if the search reached no tile in the square around the goal.

    Module Globals:
        None.

    Methodology:
        1. Search as find_path does.
        2. Return a path to the goal at once.
        3. Else pick the nearest reached tile (`_nearest_reached`), and walk
           back to it through the moves that the search recorded.

    Notes/References:
        The module docstring, "The nearest tile". `goto` and the walk of
        `attack` call this.

    Author: Nick Hobar
    Creation date: 11/16/2026
    """
    path, cost_so_far, came_from = _search(grid, start, goal, max_expanded,
                                           walk_limit)

    if path is not None:
        return (path, True)

    nearest = _nearest_reached(cost_so_far, goal, radius)

    if nearest is None:
        return None

    path = _walk_back(came_from, nearest)

    return (path, nearest == goal)


def _search(grid, start: tuple, goal: tuple, max_expanded: int, walk_limit):
    """
    Purpose: Search a shortest walk from `start` to `goal` on the tile grid
             with A*.

    Entry:
        grid         - a grid.TileGrid.
        start, goal  - (x, y) global tile coordinates.
        max_expanded - the most tiles that the search may expand.
        walk_limit   - passed to TileGrid.check_step.

    Exit/Returns:
        (path, cost_so_far, came_from). `path` is the list that find_path
        returns, or None. `cost_so_far` maps each reached tile to the steps
        to it. `came_from` maps each reached tile but the start to the tile
        before it. find_nearest_path reads the two maps when `path` is None.

    Module Globals:
        _NEIGHBOUR_OFFSETS, _STEP_COST read.

    Methodology:
        1. Push the start tile with its heuristic.
        2. Pop the tile with the lowest estimate. A tie goes to the tile
           nearer the goal by the Chebyshev distance, then by the Manhattan
           distance, then to the tile pushed first (module docstring).
        3. Return the path when the popped tile is the goal.
        4. Push each neighbour that the step rule allows and that this route
           reaches for less than any route before it. A step that touches no
           flagged tile skips TileGrid.check_step (module docstring).
        5. Stop with None when the heap is empty or the limit is hit.

    Notes/References:
        DESIGN-0011 section 6.1, step 5. The loop is long on purpose: a call
        for each neighbour is the cost that the inline read removes.

    Author: Nick Hobar
    Creation date: 09/24/2026
    """
    cost_so_far = {start: 0}
    came_from = {}

    if start == goal:
        return ([], cost_so_far, came_from)

    flags_at = grid.flags_at
    tile_height = grid.tile_height
    has_limit = walk_limit is not None
    goal_x, goal_y = goal
    first_estimate = _chebyshev(start, goal)
    frontier = [(first_estimate, first_estimate, 0, 0, start)]
    pushed = 1
    expanded = 0

    while frontier and expanded < max_expanded:
        _estimate, _remaining, _manhattan, _order, node = heapq.heappop(
            frontier)

        if node == goal:
            path = _walk_back(came_from, goal)

            return (path, cost_so_far, came_from)

        expanded += 1
        next_cost = cost_so_far[node] + _STEP_COST
        x, y = node
        node_flags = flags_at(x, y)
        node_height = tile_height(x, y) if has_limit else 0

        for dx, dy in _NEIGHBOUR_OFFSETS:
            neighbour = (x + dx, y + dy)
            known_cost = cost_so_far.get(neighbour)

            if known_cost is not None and known_cost <= next_cost:
                continue

            neighbour_flags = flags_at(x + dx, y + dy)

            if neighbour_flags & _UNWALKABLE:
                continue

            # After the unwalkable test: a tile off the grid reads as
            # blocked, and it has no height to read.
            if has_limit and abs(tile_height(x + dx, y + dy)
                                 - node_height) > walk_limit:
                continue

            touched = node_flags | neighbour_flags

            if dx and dy:
                touched |= flags_at(x + dx, y) | flags_at(x, y + dy)

            if touched & _SLOW_PATH_FLAGS and grid.check_step(
                    node, neighbour, walk_limit) != const.STEP_OK:
                continue

            # Both distances from one pair of offsets, with no call.
            across = abs(goal_x - x - dx)
            along = abs(goal_y - y - dy)
            remaining = max(across, along)
            cost_so_far[neighbour] = next_cost
            came_from[neighbour] = node
            heapq.heappush(frontier, (next_cost + remaining, remaining,
                                      across + along, pushed, neighbour))
            pushed += 1

    return (None, cost_so_far, came_from)
