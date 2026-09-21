"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/20/2026
Description: Test support for the gathering channel. No tests live here.

A harvest is a CHANNEL since 09/20/2026: the command opens it, and a
GatheringHandler on the global tick takes a swing every SWING_TICKS ticks.
Nearly every gathering test in this package asks a question about the SWING --
which cut it gave, what it taught, what it cost -- and none of them wants to
wait for a real tick to ask it.

So the tests drive one swing directly, with a scripted RNG. Two things fall
out of that and both are deliberate:

  * A test that asks about a cut is not also a test of the tick engine. The
    engine has its own tests, and coupling every content assertion to a live
    LoopingCall makes a content change able to fail a timing test.
  * A scripted draw is the only way to assert on a roll at all. See CLAUDE.md,
    "Writing tests": inject a seeded random.Random or a scripted stub, and
    never let a test read the global RNG.
"""



# A draw of exactly 0.0 succeeds against any chance above zero, and 1.0 fails
# against every chance including a certainty. They are the two ends, named, so
# a test reads "hit, then do not deplete" rather than two bare floats.
DRAW_HIT: float = 0.0
DRAW_MISS: float = 1.0

# One swing that lands and leaves the node standing. The commonest script by
# far: it is what every test asking "which cut did I get" wants.
DRAWS_YIELD_ONLY: tuple = (DRAW_HIT, DRAW_MISS)

# One swing that lands and takes the node with it.
DRAWS_YIELD_AND_DEPLETE: tuple = (DRAW_HIT, DRAW_HIT)

# One swing that produces nothing.
DRAWS_MISS: tuple = (DRAW_MISS,)



class ScriptedRandom:
    """A random.Random stand-in that returns a written-down sequence.

    Exhausting the script REPEATS the last draw rather than raising. A test
    that scripts two draws and gets three is asking a question about the
    swing, not about how many times the code rolled, and an exception there
    would make every roll count part of the contract.
    """

    def __init__(self, draws=DRAWS_YIELD_ONLY) -> None:
        self._draws = list(draws)
        self._index = 0


    def random(self) -> float:
        """Return the next scripted draw."""
        if not self._draws:
            return DRAW_MISS

        index = min(self._index, len(self._draws) - 1)
        self._index += 1

        return self._draws[index]



def channel_is_open(character) -> bool:
    """Whether this character has a live gathering channel.

    What a test uses to tell "the command started something" from "the
    command refused". A refusal is a complete answer on its own, and driving
    a swing after one would test a node the player was told they may not
    work.
    """
    from systems.gameplay.progression.skills.skill_defs.gathering import (
        gather_handler,
    )

    handler = gather_handler.get_gathering_handler(character)

    return handler is not None



def swing_once(character, skill, node, wanted: str = "",
               draws=DRAWS_YIELD_ONLY) -> tuple:
    """
    Purpose: Take exactly one swing and hand back what the player read.

    Entry:
        character is the gatherer. skill is a GatheringSkill instance.
        node is the node being worked. wanted is an explicit yield choice.
        draws is the scripted RNG sequence -- see the DRAWS_* constants.

    Exit/Returns:
        Returns (text, stop_reason). `text` is every line the swing sent,
        joined by newlines. `stop_reason` is what attempt_swing returned.

    Module Globals:
        None.

    Methodology:
        Captures by wrapping the character's own msg, rather than reading a
        session's buffer. EvenniaCommandTest's `self.call` only captures what
        a COMMAND sends, and a swing happens outside one -- so a test that
        used `self.call` alone saw the channel's opening line and nothing
        else.

        The original is restored in a finally block, and restored to what it
        WAS -- an instance attribute if there was one, otherwise nothing at
        all, so the class method comes back. A bare `del` gets that wrong for
        a character something else has already wrapped, and a test that
        leaves a wrapper on a fixture hands the next test a msg that is a
        closure over a dead list. That failure surfaces somewhere else
        entirely.

        The real msg is still called, so anything downstream that depends on
        the message actually being delivered keeps working.

    Notes/References:
        GatheringSkill.attempt_swing is what this drives.

    Author: Nick Hobar
    Creation date: 09/20/2026
    """
    lines = []
    original = character.msg
    had_own = "msg" in character.__dict__

    def capture(text=None, **kwargs):
        """Record the line, then deliver it as normal."""
        body = text

        if isinstance(body, tuple):
            body = body[0]

        if body is not None:
            lines.append(str(body))

        return original(text, **kwargs)

    character.msg = capture

    try:
        stop_reason = skill.attempt_swing(
            character, node, wanted, rng=ScriptedRandom(draws))
    finally:
        character.__dict__.pop("msg", None)

        if had_own:
            character.msg = original

    return "\n".join(lines), stop_reason
