"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Action resolution — pick a winner for each seam, run every
             contributor's modifiers, then resolve.
"""

from __future__ import annotations

from evennia.utils import logger

from .rule_defs.base_rules import (
    DEFAULT_ACTION_RULES,
    ACTION_SEAM_NAMES,
    BaseActionRules,
)


# Public constant definitions

# The seam that is not a seam contest. Every contributor's contribute_modifiers
# runs, regardless of priority, so it is excluded from winner resolution.
MODIFIER_SEAM_NAME = "contribute_modifiers"


class ResolvedActionRules:
    """
    Purpose: Present the nine seams as one object, each dispatching to the
    contributor that won it.

    Entry:
        winners - dict mapping every name in ACTION_SEAM_NAMES to the rules
                  instance that owns it. The pipeline fills every key, so no
                  method here has to handle a missing seam.

    Exit/Returns:
        Not applicable — a dispatcher.

    Module Globals:
        None.

    Methodology:
        Each seam is a two-line method that looks up its owner and forwards.
        The verbosity is deliberate: the alternative is a __getattr__ that
        binds arbitrary names, which would turn a typo'd seam call inside a
        rules definition into a silent no-op instead of an AttributeError.

        Winners keep their OWN `self`. That is why dispatch is by explicit
        forwarding rather than by rebinding the winner's function onto this
        object: a definition reading a class attribute off `self` must get its
        own, not this dispatcher's.

    Notes/References:
        A seam calling another seam goes through context.rules, which is this
        object. See BaseActionRules.resolve.

    Author: Nick Hobar
    Creation date: 08/04/2026
    """

    def __init__(self, winners: dict) -> None:
        self._winners = winners

    def owner(self, seam_name: str) -> BaseActionRules:
        """Return the rules instance that won one seam."""
        return self._winners[seam_name]

    def effective_attack_level(self, context) -> int:
        """Dispatch the effective Strike level seam."""
        return self._winners["effective_attack_level"].effective_attack_level(context)

    def effective_strength_level(self, context) -> int:
        """Dispatch the effective Brawn level seam."""
        winner = self._winners["effective_strength_level"]

        return winner.effective_strength_level(context)

    def effective_defense_level(self, context) -> int:
        """Dispatch the effective Defense level seam."""
        winner = self._winners["effective_defense_level"]

        return winner.effective_defense_level(context)

    def max_hit(self, context, eff_str: int) -> int:
        """Dispatch the damage-ceiling seam."""
        return self._winners["max_hit"].max_hit(context, eff_str)

    def accuracy(self, context, eff_atk: int, eff_def: int) -> float:
        """Dispatch the hit-probability seam."""
        winner = self._winners["accuracy"]

        return winner.accuracy(context, eff_atk, eff_def)

    def roll_accuracy(self, context, chance: float) -> bool:
        """Dispatch the accuracy-roll seam."""
        return self._winners["roll_accuracy"].roll_accuracy(context, chance)

    def roll_damage(self, context, result) -> None:
        """Dispatch the damage-roll seam."""
        self._winners["roll_damage"].roll_damage(context, result)

    def resolve(self, context):
        """Dispatch the whole-action seam."""
        return self._winners["resolve"].resolve(context)


# Private helper routines

def _resolve_winners(contributors: tuple) -> ResolvedActionRules:
    """Pick the highest-priority owner of each seam.

    `contributors` arrives sorted lowest priority first, so a later entry
    simply overwrites an earlier one. Seams no contributor claims resolve to
    DEFAULT_ACTION_RULES, which is the plain OSRS behaviour.
    """
    winners = {seam: DEFAULT_ACTION_RULES for seam in ACTION_SEAM_NAMES}

    for rules in contributors:
        overridden = getattr(rules, "_overridden_seams", frozenset())

        for seam_name in overridden:
            if seam_name == MODIFIER_SEAM_NAME:
                continue

            winners[seam_name] = rules

    return ResolvedActionRules(winners)


def _run_modifiers(contributors: tuple, context, bag) -> None:
    """Let every contributor add into one bag, regardless of priority.

    Modifiers are the one thing that never loses a priority contest: a d20
    sword owning the damage roll must not switch off the amulet on the other
    hand. A contributor that raises is logged and skipped so one bad
    definition cannot stop the action.
    """
    for rules in contributors:
        try:
            rules.contribute_modifiers(context, bag)
        except Exception:
            logger.log_trace(
                f"[RULES] {rules.key} contribute_modifiers failed; skipped."
            )


# Public routines

def resolve_action(context):
    """
    Purpose: Resolve one action through the pluggable rules pipeline. This is
    the single entry point ActionAttack calls per swing today, and the entry
    point any future action type (a ranged shot, a gadget use) would call too.

    Entry:
        context - an ActionContext with attacker_rules and defender_rules
                  already populated by collect_contributors. Its bags must be
                  empty; this function fills them.

    Exit/Returns:
        An ActionResult. `damage` is 0 on a miss OR on a connecting action that
        rolled 0; `self_damage` is non-zero only for a rule that hurts its own
        wielder.

    Module Globals:
        DEFAULT_ACTION_RULES read via _resolve_winners.

    Methodology:
        1. Pick a winner per seam. Highest priority wins each seam
           independently -- seams are never chained.
        2. Run EVERY contributor's contribute_modifiers into the owning
           entity's bag. Modifiers do not lose to priority.
        3. Publish the winners on the context so a seam calling another seam
           reaches the actual winner rather than its own default.
        4. Resolve.

        Modifiers run before step 4, not lazily, because a seam may read any
        channel and a half-filled bag would make the result depend on which
        seam happened to read first.

        Seam winners come from the ATTACKER's contributors only. This is the
        attacker's action, and letting a defender's gear replace, say,
        roll_damage would mean the defender chooses how much damage they take.
        The defender still influences the action, through the defender bag:
        their contributors' modifiers fill CHANNEL_DEFENSE_LEVEL and
        CHANNEL_DEFENSE_BONUS, which the accuracy seam reads. When defensive
        seams are wanted (damage reduction, reflect), they belong in a
        defender-side pipeline of their own, not by widening this contest.

    Notes/References:
        With no contributors at all, every seam resolves to DEFAULT_ACTION_RULES
        and both bags stay empty, which makes the appliers the identity and
        this function exactly equivalent to
        combat_calc.resolve_melee_swing -- asserted over fifty seeds by
        tests/test_action_pipeline.TestDefaultRulesMatchTheReference.

    Author: Nick Hobar
    Creation date: 08/04/2026
    """
    resolved = _resolve_winners(context.attacker_rules)

    _run_modifiers(context.attacker_rules, context, context.attacker_bag)
    _run_modifiers(context.defender_rules, context, context.defender_bag)

    context.rules = resolved

    return resolved.resolve(context)
