"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/20/2026
Description: The maths behind one swing -- does it yield, and does the node
             give out. Pure functions over numbers.

             NOTHING HERE TOUCHES THE DATABASE, Evennia, or a character. That
             is deliberate and it is what makes the balance of the skill
             testable with a plain unittest.TestCase and plottable by
             analysis/. A roll that needs a live character to evaluate is a
             roll nobody can graph before shipping it.

             Every routine takes its randomness as an argument. See CLAUDE.md
             "Writing tests": a test that reads the global RNG is a test that
             passes until somebody else seeds it.
"""



from systems.gameplay.progression.skills.skill_defs.gathering import (
    constants as gather_constants,
)



def success_chance(level: int, low: int, high: int) -> float:
    """
    Purpose: The probability that one swing yields, for one level and one
    low/high pair.

    Entry:
        level is the character's level in the skill. Values outside
            0..CHANCE_TOP_LEVEL are clamped rather than refused.
        low is the numerator at level 0, in CHANCE_DENOMINATOR units.
        high is the numerator at CHANCE_TOP_LEVEL, in the same units.

    Exit/Returns:
        Returns a float in 0.0..1.0.

    Module Globals:
        gather_constants.CHANCE_TOP_LEVEL and CHANCE_DENOMINATOR read.

    Methodology:
        A straight line between the two ends, which is the OSRS woodcutting
        and mining rule. The numerators stay in 1/255 units all the way to
        the last division, so a pair copied off the wiki means here what it
        means there and a designer can check one against the other.

        THE LEVEL IS CLAMPED, NOT VALIDATED. A level above the ladder's top
        is a rescale that has not reached the table yet, and the correct
        answer for it is the top of the line -- not an exception in the
        middle of a swing. A negative level is the same argument downward.

        Division happens once, at the end. Interpolating in floats and then
        scaling loses the property that an integer pair gives an exact
        multiple of 1/255, which is what lets a test assert the endpoints
        without an epsilon.

    Notes/References:
        The pair itself lives on GatherableDef.chances -- see
        systems/gameplay/progression/skills/gatherables.py.

    Author: Nick Hobar
    Creation date: 09/20/2026
    """
    top = gather_constants.CHANCE_TOP_LEVEL
    bounded = min(max(level, 0), top)
    numerator = (low * (top - bounded)) + (high * bounded)
    denominator = top * gather_constants.CHANCE_DENOMINATOR

    return numerator / denominator



def rolls_success(chance: float, rng) -> bool:
    """
    Purpose: Decide whether one swing yields.

    Entry:
        chance is a probability, normally from success_chance.
        rng is a random.Random, or anything with a random() method.

    Exit/Returns:
        Returns True when the swing yields.

    Module Globals:
        None.

    Methodology:
        Strictly less than, so a chance of 0.0 can never succeed. `<=` would
        let a node declared as impossible yield on the one draw that returns
        exactly zero, which is the kind of bug that surfaces one time a year
        and is never reproduced.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/20/2026
    """
    draw = rng.random()

    return draw < chance



def depletes(deplete_chance: float, rng) -> bool:
    """
    Purpose: Decide whether a node gives out after a swing that yielded.

    Entry:
        deplete_chance is a probability in 0.0..1.0.
        rng is a random.Random, or anything with a random() method.

    Exit/Returns:
        Returns True when the node is spent.

    Module Globals:
        None.

    Methodology:
        Asked ONLY after a swing that produced something, which is the OSRS
        rule: a tree falls because you took a log from it, never because you
        missed. Rolling it on every swing would make a low level deplete
        nodes faster than a high one, which is backwards.

        The same comparison rolls_success uses, so a node declared as
        inexhaustible (0.0) is exactly that.

    Notes/References:
        GatherableDef.deplete_chance carries the per-node value.

    Author: Nick Hobar
    Creation date: 09/20/2026
    """
    outcome = rolls_success(deplete_chance, rng)

    return outcome
