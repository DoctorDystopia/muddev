"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Pluggable action rules — the seams and modifier channels that let
             an item change how combat math is done without editing the math.

An action resolves through NINE named seams (effective levels, max hit, accuracy,
the accuracy roll, the damage roll, and the whole resolution) plus a set of
named MODIFIER CHANNELS. Two different mechanisms, deliberately separate:

    seams     — overridable methods. Highest-priority contributor wins a seam
                outright; seams are never chained.
    channels  — named stat accumulators. EVERY contributor's modifiers are
                summed, regardless of priority.

That asymmetry is the point. "This weapon rolls a d20 instead" is a seam. "+1
Brawn per 5 surplus Brawn" is a channel, and it must still apply while some
other item owns the damage roll.

`combat_calc` is untouched by all of this: it stays the pure OSRS reference and
BaseActionRules delegates to it, so the default path is provably the old path
(see tests/test_action_pipeline.TestDefaultRulesMatchTheReference).

Package shape mirrors systems/combat/auras/ — a package-walk registry over a
`*_defs/` directory, instances stored, one file per definition. It is the same
idiom, not a new one.
"""
