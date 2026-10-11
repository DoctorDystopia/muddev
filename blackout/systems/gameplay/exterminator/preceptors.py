"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: PreceptorDef, the shape of one Preceptor, and PRECEPTOR_DB.

             A Preceptor gives a task and teaches buffs. Each Preceptor
             lists the creature types that it gives, with a weight and a
             task size range for each type (Nick, 10/06/2026: one range for
             each creature type, as in OSRS).

             The NPC in the world is a typeclass in typeclasses/npcs.py. Its
             class attribute names a key here. This table owns the rules of
             the Preceptor, so a change here reaches the NPC that already
             stands in the world. DESIGN-0012, Phase 2.
"""

from dataclasses import dataclass

from systems.gameplay.exterminator import constants
from world import creature_types



# ─── Preceptor keys ─────────────────────────────────────────────────────────
PRECEPTOR_ATTICUS_QUIN: str = "atticus_quin"
PRECEPTOR_ATUM_MUSA: str = "atum_musa"



@dataclass(frozen=True)
class Assignment:
    """
    One creature type that a Preceptor gives. `weight` is the relative
    chance of the type in a draw. A task of this type needs from
    `min_size` to `max_size` kills, both included. The par time of the task
    is its total kills times `par_seconds_per_kill`.
    """

    creature_type: str
    weight: int
    min_size: int
    max_size: int
    par_seconds_per_kill: int = constants.DEFAULT_PAR_SECONDS_PER_KILL



@dataclass(frozen=True)
class PoolEntry:
    """
    One buff that a Preceptor teaches. Two Preceptors can list the same buff.

    buff_key - a key of BUFF_REGISTRY.
    weight   - the relative chance of the buff in a draw of cards.
    name     - the name that this Preceptor gives the buff. Empty: the plain
               name of the buff class shows.
    line     - what the Preceptor says about the buff. Stored, and shown
               nowhere yet (Nick, 10/07/2026).
    """

    buff_key: str
    weight: int
    name: str = ""
    line: str = ""



@dataclass(frozen=True)
class PreceptorDef:
    """
    One Preceptor.

    `key` is the stable name that a task stores. `name` is the display name.
    `assignments` is a tuple of Assignment. `base_points` is what a
    completed task gives before the streak multiplier. `required_level` is
    the Exterminator level that a player needs before this Preceptor gives a
    task. `buff_pool` is a tuple of PoolEntry: the buffs that the Preceptor
    teaches.
    """

    key: str
    name: str
    assignments: tuple
    base_points: int
    required_level: int = 0
    buff_pool: tuple = ()



# Every buff in the pool of Quin has the same chance in a draw. TBD.
_QUIN_BUFF_WEIGHT: int = 1

_ATTICUS_QUIN = PreceptorDef(
    key=PRECEPTOR_ATTICUS_QUIN,
    name="Atticus Quin",
    # Every hostile creature type in the game today (Nick, 10/06/2026).
    # Weights and sizes are TBD.
    assignments=(
        Assignment(creature_types.CREATURE_TYPE_MUTANT, 1, 15, 30),
        Assignment(creature_types.CREATURE_TYPE_CRAB, 1, 10, 20),
        Assignment(creature_types.CREATURE_TYPE_EYE, 1, 10, 20),
        Assignment(creature_types.CREATURE_TYPE_GIANT, 1, 5, 15),
    ),
    base_points=10,      # TBD (Nick, 10/06/2026: start with 10 per task)
    required_level=0,    # He is the first Preceptor.
    # The seven buffs that work with the combat code of today (Nick,
    # 10/06/2026). Equal weights, TBD. The names are the plain names of the
    # buff classes for now. Each line is the example from the vault note:
    # TBD text, Nick writes the final lines.
    buff_pool=(
        PoolEntry(constants.BUFF_ACCURACY_VS_TYPE, _QUIN_BUFF_WEIGHT,
                  line="The eye finds the flaw. The hand only follows."),
        PoolEntry(constants.BUFF_DEFENSE_SEAL, _QUIN_BUFF_WEIGHT,
                  line="Wax and scripture. Let them bite through both."),
        PoolEntry(constants.BUFF_MILESTONE_GROWTH, _QUIN_BUFF_WEIGHT,
                  line="Each page you survive is a page you keep."),
        PoolEntry(constants.BUFF_LOW_HP_MAX_HIT, _QUIN_BUFF_WEIGHT,
                  line="Mercy is a door. Close it."),
        PoolEntry(constants.BUFF_BEST_OF_TWO_ROLLS, _QUIN_BUFF_WEIGHT,
                  line="Say it twice. The second time, mean it."),
        PoolEntry(constants.BUFF_DAMAGE_FOR_DEFENSE, _QUIN_BUFF_WEIGHT,
                  line="Pain is the tithe. Pay it gladly."),
        PoolEntry(constants.BUFF_PAR_TIME_POINTS, _QUIN_BUFF_WEIGHT,
                  line="The sand does not wait for you."),
    ),
)


# The second Preceptor (Nick, 10/09/2026). All lore is TBD. For now Musa
# gives the tasks of Quin and teaches the pool of Quin, so each value comes
# from the def of Quin. The pool keeps the buffs and the weights, and drops the
# lines, because each line is the voice of Quin.
_ATUM_MUSA = PreceptorDef(
    key=PRECEPTOR_ATUM_MUSA,
    name="Atum Musa",
    assignments=_ATTICUS_QUIN.assignments,
    base_points=_ATTICUS_QUIN.base_points,
    required_level=_ATTICUS_QUIN.required_level,
    buff_pool=tuple(PoolEntry(entry.buff_key, entry.weight)
                    for entry in _ATTICUS_QUIN.buff_pool),
)


# key -> PreceptorDef.
PRECEPTOR_DB: dict = {
    _ATTICUS_QUIN.key: _ATTICUS_QUIN,
    _ATUM_MUSA.key: _ATUM_MUSA,
}



# ─── Public routines ────────────────────────────────────────────────────────

def pool_entry(preceptor_key, buff_key: str):
    """The PoolEntry of one buff in the pool of one Preceptor, or None."""
    preceptor = PRECEPTOR_DB.get(preceptor_key)

    if preceptor is None:
        return None

    for entry in preceptor.buff_pool:
        if entry.buff_key == buff_key:
            return entry

    return None


def assignment_for(preceptor_key, creature_type: str):
    """The Assignment of one creature type of one Preceptor, or None."""
    preceptor = PRECEPTOR_DB.get(preceptor_key)

    if preceptor is None:
        return None

    for assignment in preceptor.assignments:
        if assignment.creature_type == creature_type:
            return assignment

    return None
