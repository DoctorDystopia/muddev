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


# ─── Public routines ─────────────────────────────────────────────────────────

def find_path(grid, start: tuple, goal: tuple,
              max_expanded: int = const.PATH_MAX_EXPANDED,
              walk_limit=const.WALK_LIMIT):
    """
    Purpose: Find a shortest walk from `start` to `goal` on the tile grid.

    Entry:
        grid         - a grid.TileGrid.
        start, goal  - (x, y) global tile coordinates.
        max_expanded - the most tiles that the search may expand.
        walk_limit   - passed to TileGrid.check_step.

    Exit/Returns:
        A list of (x, y) tiles, one for each step, ending at `goal`. The start
        tile is not in it. [] if start == goal. None if no path exists, or if
        the search hit `max_expanded` first.

    Module Globals:
        _NEIGHBOUR_OFFSETS, _STEP_COST read.

    Methodology:
        1. Push the start tile with its heuristic.
        2. Pop the tile with the lowest estimate. A tie goes to the tile
           nearer the goal, then to the tile pushed first.
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
    if start == goal:
        return []

    flags_at = grid.flags_at
    tile_height = grid.tile_height
    has_limit = walk_limit is not None
    first_estimate = _chebyshev(start, goal)
    frontier = [(first_estimate, first_estimate, 0, start)]
    cost_so_far = {start: 0}
    came_from = {}
    pushed = 1
    expanded = 0

    while frontier and expanded < max_expanded:
        _estimate, _remaining, _order, node = heapq.heappop(frontier)

        if node == goal:
            return _walk_back(came_from, goal)

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

            remaining = _chebyshev(neighbour, goal)
            cost_so_far[neighbour] = next_cost
            came_from[neighbour] = node
            heapq.heappush(frontier,
                           (next_cost + remaining, remaining, pushed, neighbour))
            pushed += 1

    return None
