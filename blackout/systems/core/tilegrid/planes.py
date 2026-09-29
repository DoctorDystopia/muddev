"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/26/2026
Description: The room Z of each plane of the tile world, and the plane of a
             room Z.

Why a Z for each plane
----------------------
DESIGN-0011 Phase 7. A tile room carries the three xyzgrid tags. The Z tag of
plane 0 is the world name, `tile_world`, as it was before planes. Plane p > 0
gets `tile_world_p<p>`. Thus:

- No room of plane 0 needed a migration.
- A different plane is a different Z. Reach and sight already refuse a
  different Z, so no shot crosses planes.
- Each plane has its own pool, `<plane Z>_pool`, which no plane Z matches.

This module holds no Evennia import, so any reader of a Z can use it.
"""

from . import constants as const


# ─── Public routines ─────────────────────────────────────────────────────────

def plane_z(plane: int, world_z: str = const.WORLD_Z) -> str:
    """Return the room Z of a plane of the world."""
    if plane == const.GROUND_PLANE:
        return world_z

    return const.PLANE_Z_TEMPLATE.format(world=world_z, plane=plane)


def plane_of_z(z, world_z: str = const.WORLD_Z):
    """
    Purpose: Return the plane of a room Z, or None for a Z that is not a
             plane of this world.

    Entry:
        z       - a room Z tag value. Any value, None too.
        world_z - the name of the world.

    Exit/Returns:
        An int from GROUND_PLANE to PLANE_MAX, or None. A pool Z gives None:
        a pooled room is on no plane.

    Module Globals:
        const.GROUND_PLANE, const.PLANE_MAX read.

    Methodology:
        Compare with the Z of each plane. There are PLANE_MAX + 1 of them, so
        a loop is cheaper to read than a parse, and it cannot accept a Z
        that plane_z never makes.

    Notes/References:
        `world/tile_travel.on_tile_world` and every reader of `room.xyz`
        on the tile world call this.

    Author: Nick Hobar
    Creation date: 09/26/2026
    """
    for plane in range(const.GROUND_PLANE, const.PLANE_MAX + 1):
        if z == plane_z(plane, world_z):
            return plane

    return None
