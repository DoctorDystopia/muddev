"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/26/2026
Description: The sweep of the tile rooms: give back each empty room on a
             clock, for the moves that do not give it back themselves.

Why a sweep, and not a hook on the departure
--------------------------------------------
`movement.step` and `movement.place` give the room behind them back at once.
Three other ways to leave a room do not:

1. A teleport, and a death respawn, call `move_to` with no tile code.
2. A logout sets `location = None`. Evennia runs no move hook for it.
3. A delete takes the object out of the room. No move hook runs.

A room hook (`at_object_leave`) sees only the first, and it runs while the
mover is still in the room. One sweep sees all three. An empty room costs one
row and one index entry until the sweep, so a delay of 60 seconds is fine.

Who starts it
-------------
`world.get_world` calls `attach` when it loads the world. The sweep thus
starts with the world that it sweeps. It is not a manager of
`systems/core/managers.py`, because it has no Script: a bootstrap there must
return the Script that it starts.

The sweep reads `loaded_world`, not `get_world`, so the tick never reads the
chunk files. A test world from `set_world` attaches nothing.
"""

from . import constants as const
from .world import loaded_world


# ─── Module globals ──────────────────────────────────────────────────────────

# The ticks since the last sweep.
_ticks_since_sweep = 0

# True after the tick hook is attached. A second attach does nothing.
_attached = False


# ─── Public routines ─────────────────────────────────────────────────────────

def sweep_loaded_world() -> int:
    """
    Sweep the rooms of every plane of the loaded world. Return how many
    rooms went back.
    """
    world = loaded_world()

    if world is None:
        return 0

    return world.sweep_rooms()


def on_tick() -> None:
    """
    Purpose: Count one tick, and sweep when SWEEP_EVERY_TICKS have passed.

    Entry:
        No conditions. The tick engine calls it on PHASE_START.

    Exit/Returns:
        None.

    Module Globals:
        _ticks_since_sweep written. const.SWEEP_EVERY_TICKS read.

    Methodology:
        A counter, not the tick number of the engine, so this module needs
        no handle on the engine.

    Notes/References:
        PHASE_START runs before the handlers. A room given back there cannot
        be the source of a move that the statefeed has not sent yet.

    Author: Nick Hobar
    Creation date: 09/26/2026
    """
    global _ticks_since_sweep

    _ticks_since_sweep += 1

    if _ticks_since_sweep < const.SWEEP_EVERY_TICKS:
        return

    _ticks_since_sweep = 0
    sweep_loaded_world()


def attach() -> None:
    """
    Attach `on_tick` to the tick, one time for each process. The engine
    import is here, not at module scope: the tile grid must not need the
    tick to load.
    """
    global _attached

    if _attached:
        return

    from systems.core.tick.engine import PHASE_START, register_phase_hook

    register_phase_hook(PHASE_START, on_tick)
    _attached = True
