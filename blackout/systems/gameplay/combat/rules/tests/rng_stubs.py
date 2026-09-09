"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Deterministic random.Random stand-ins for action rules tests.

Deliberately NOT named test_*, so Django's discovery treats it as a helper
module rather than trying to collect it as a test case.
"""


# Public constant definitions

# Message raised when a scripted sequence runs dry. Spelled out because the
# whole point of the stub is that exhaustion is LOUD: a test that quietly fell
# back to real randomness would pass or fail at random.
_EXHAUSTED = (
    "ScriptedRandom ran out of scripted {kind} draws. The code under test "
    "drew more values than the test scripted, so the assertion below would "
    "have been measuring real randomness."
)


class ScriptedRandom:
    """
    Purpose: A random.Random stand-in that returns a queued sequence.

    Entry:
        randints - values returned by successive randint calls, in order.
        randoms  - values returned by successive random calls, in order.

    Exit/Returns:
        Not applicable — a test double.

    Module Globals:
        _EXHAUSTED read.

    Methodology:
        Raises on exhaustion rather than cycling or falling back. A stub that
        silently returned real randomness once its script ran out would turn
        an over-drawing regression into a flaky test instead of a failing one.

        randint IGNORES its bounds and returns the scripted value verbatim,
        so a test can assert that a d20 seam is not being clamped by the OSRS
        max hit. The recorded bounds are kept for the tests that care.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/04/2026
    """

    def __init__(self, randints=(), randoms=()) -> None:
        self._randints = list(randints)
        self._randoms = list(randoms)
        self.randint_calls = []
        self.random_calls = 0

    def randint(self, low: int, high: int) -> int:
        """Return the next scripted integer, recording the bounds asked for."""
        self.randint_calls.append((low, high))

        if not self._randints:
            raise AssertionError(_EXHAUSTED.format(kind="randint"))

        return self._randints.pop(0)

    def random(self) -> float:
        """Return the next scripted float."""
        self.random_calls += 1

        if not self._randoms:
            raise AssertionError(_EXHAUSTED.format(kind="random"))

        return self._randoms.pop(0)


class RecordingRandom:
    """
    Purpose: Wrap a real Random and record the ORDER of draws made through it.

    Entry:
        source - the random.Random to delegate to.

    Exit/Returns:
        Not applicable — a test double.

    Module Globals:
        None.

    Methodology:
        Seeded reproducibility depends on the number and order of draws, not
        just the seed. This records a "random"/"randint" trace so a test can
        pin that accuracy is drawn before damage, which is the property that
        keeps the pipeline byte-equivalent to combat_calc.resolve_melee_swing.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/04/2026
    """

    def __init__(self, source) -> None:
        self._source = source
        self.trace = []

    def randint(self, low: int, high: int) -> int:
        """Delegate a randint draw and record it."""
        self.trace.append("randint")

        return self._source.randint(low, high)

    def random(self) -> float:
        """Delegate a random draw and record it."""
        self.trace.append("random")

        return self._source.random()
