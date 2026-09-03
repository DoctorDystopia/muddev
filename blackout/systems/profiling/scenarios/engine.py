"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/03/2026
Description: Profiling scenarios for the Evennia engine layer -- the tick, the
             combat resolution it drives, and the command dispatch a player's
             input arrives through.

Why the tick is the layer's headline measurement
-------------------------------------------------
TICK_SECONDS is 0.6, and every registered handler is advanced inside one
_tick() call on the reactor thread. A tick that takes longer than its interval
does not queue -- twisted's LoopingCall schedules on a fixed grid, so the
engine's own tick_debug reports the overrun as drift and the game visibly
stutters for every player at once. That makes the tick the one place in the
codebase where a measured duration converts directly into a player-facing
symptom, and it is why the scenarios here report against TICK_SECONDS rather
than against an abstract threshold.

Why the tick scenarios drive _tick directly
--------------------------------------------
The LoopingCall is not started. Letting the reactor drive it would measure
wall-clock intervals rather than the work inside one pass, and would make the
number depend on how long the harness happened to sit between samples.
Calling the private _tick is deliberate: it is the unit whose cost matters, and
a profiling scenario is exactly the caller a private method may have when the
alternative is measuring something else and calling it the tick.
"""

from systems.combat.combat import combat_profile, ensure_combat_handler
from systems.tick.engine import get_tick_engine

from .. import constants as const
from . import scenario


# ─── Private constant definitions ────────────────────────────────────────────

# How many combatants share the room in the crowded-tick scenario. Six is what
# systems/tick/tests/test_query_cost.py settled on as enough to make an O(N*M)
# walk obvious against an O(N) one while keeping the fixture cheap.
_CROWD_SIZE = 6

# Where the crowd stands. A corner of the fixture grid, chosen because it is
# OUTSIDE the radius-3 neighbourhood of the centre (which covers x and y in
# 1..7) that the statefeed scenarios serialise. The tick does not care which
# tile its combatants are on; the scenarios that run afterwards care a great
# deal, and a crowd inside their radius silently changes what they measure.
_CROWD_TILE = (0, 0)

# Ticks driven per measured pass. One tick is a few hundred microseconds of
# work, which is under the timer's useful resolution on Windows.
_TICKS_PER_PASS = 20

_TICK_REPEAT = 10
_PROFILE_REPEAT = 100


# ─── Private helper routines ─────────────────────────────────────────────────

def _arm_crowd(world, size: int) -> list:
    """
    Purpose: Put `size` combatants on the centre tile with live handlers.

    Entry:
        world - a built ProfilingWorld.
        size  - how many combatants to create, including the observer.

    Exit/Returns:
        Returns the list of combatants, each with a registered combat handler.

    Module Globals:
        None.

    Methodology:
        Characters rather than spawned raiders. The mutant raider spawner
        refuses a second raider on one tile, so it hands back None for all but
        the first -- the same trap test_query_cost.py documents and works
        around the same way.

        The crowd stands on a tile AWAY FROM THE CENTRE, and that is the whole
        reason this helper takes a room at all. Scenarios share one world and
        run in layer order, so engine scenarios execute before statefeed ones;
        a crowd left standing on the centre tile is a crowd every subsequent
        serialisation has to walk. Measured, that mistake moved
        `serialize_contents` from 0.015 ms to 0.076 ms and looked exactly like
        a regression in code that had not changed.

        Sharing state between scenarios is accepted and documented in
        harness.py -- a real server is never freshly built either. Silently
        changing the SIZE of the world a later scenario measures is not the
        same thing, and is not accepted.

    Notes/References:
        See harness.py's module header on why one method builds the world once.

    Author: Nick Hobar
    Creation date: 09/03/2026
    """
    from evennia.utils.create import create_object
    from typeclasses.characters import Character

    arena = world.tiles[_CROWD_TILE]
    combatants = []

    for index in range(size):
        fighter = create_object(Character,
                                key=f"profiling_fighter_{index}",
                                location=arena)
        combatants.append(fighter)

    for fighter in combatants:
        ensure_combat_handler(fighter)

    return combatants


# ─── Public routines ─────────────────────────────────────────────────────────

@scenario(name="tick engine, empty registry",
          layer=const.LAYER_ENGINE,
          repeat=_TICK_REPEAT,
          notes=f"{_TICKS_PER_PASS} ticks with nothing registered. The floor "
                "every populated tick is measured against.")
def tick_empty(world):
    """Measure the fixed per-tick overhead with no handlers."""
    engine = get_tick_engine()

    def work():
        for _ in range(_TICKS_PER_PASS):
            engine._tick()

    return work


@scenario(name="tick engine, 6 combatants in one room",
          layer=const.LAYER_ENGINE,
          repeat=_TICK_REPEAT,
          notes=f"{_TICKS_PER_PASS} ticks. Divide the per-pass duration by "
                f"{_TICKS_PER_PASS} and compare against TICK_SECONDS (0.6).")
def tick_crowded(world):
    """Measure a tick carrying a realistic combat load."""
    engine = get_tick_engine()
    _arm_crowd(world, _CROWD_SIZE)

    def work():
        for _ in range(_TICKS_PER_PASS):
            engine._tick()

    return work


@scenario(name="combat_profile for a character",
          layer=const.LAYER_ENGINE,
          repeat=_PROFILE_REPEAT,
          notes="Sums bonuses across every equipped slot. Rebuilt whenever a "
                "handler is ensured.")
def combat_profile_read(world):
    """Measure the equipped-stat aggregation combat reads per fight."""
    character = world.character

    def work():
        combat_profile(character)

    return work


@scenario(name="ensure_combat_handler (already armed)",
          layer=const.LAYER_ENGINE,
          repeat=_PROFILE_REPEAT,
          notes="The lazy create-or-fetch every combat command opens with. "
                "The hot case is the one where a handler already exists.")
def ensure_handler_warm(world):
    """Measure the handler lookup on the path where one already exists."""
    character = world.character
    ensure_combat_handler(character)

    def work():
        ensure_combat_handler(character)

    return work


@scenario(name="command dispatch: look",
          layer=const.LAYER_ENGINE,
          repeat=_TICK_REPEAT,
          notes="Full Evennia command resolution, including cmdset merging "
                "and the room's appearance build.")
def command_look(world):
    """Measure one complete command round trip through Evennia's dispatch."""
    character = world.character

    def work():
        character.execute_cmd("look")

    return work
