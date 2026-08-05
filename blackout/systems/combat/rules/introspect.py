"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Human-readable report of which rules definition owns which seam
             for a given combatant.

Not a convenience. An action resolves nine seams by priority across up to eleven
equipment slots, so its behaviour is spread over several classes with no single
place to read it. Logging a collision at resolution time is not an option --
that code path fires roughly a hundred times a minute per combatant -- which
leaves an on-demand report as the only practical debugging surface.
"""

from __future__ import annotations

from systems.combat import constants as const

from .contributors import collect_contributors
from .pipeline import MODIFIER_SEAM_NAME, _resolve_winners
from .rule_defs.base_rules import ACTION_SEAM_NAMES, DEFAULT_ACTION_RULES


# Private constant definitions

# Shown for a seam no contributor claimed.
_DEFAULT_LABEL = "default"

# Shown when a combatant carries no rules at all.
_NO_CONTRIBUTORS = "  (none — plain OSRS action)"


# Private helper routines

def _contributor_lines(contributors: tuple) -> list:
    """One line per contributor: name, priority tier, and what it replaces."""
    if not contributors:
        return [_NO_CONTRIBUTORS]

    lines = []

    for rules in contributors:
        seams = getattr(rules, "_overridden_seams", frozenset())
        owned = ", ".join(sorted(seams)) or "nothing"
        lines.append(
            f"  |y{rules.name}|n (|w{rules.key}|n, priority {rules.priority})"
            f"\n      overrides: {owned}"
        )

    return lines


def _seam_lines(contributors: tuple) -> list:
    """One line per seam, naming its winner.

    Reuses the pipeline's own winner resolution rather than reimplementing
    the contest, so the report cannot disagree with what actually happens.
    """
    resolved = _resolve_winners(contributors)
    lines = []

    for seam_name in ACTION_SEAM_NAMES:
        if seam_name == MODIFIER_SEAM_NAME:
            continue

        winner = resolved.owner(seam_name)

        if winner is DEFAULT_ACTION_RULES:
            lines.append(f"  {seam_name:<26} {_DEFAULT_LABEL}")
            continue

        lines.append(f"  {seam_name:<26} |g{winner.key}|n")

    return lines


# Public routines

def describe_action_rules(entity) -> str:
    """
    Purpose: Render which rules definitions an entity carries and which of
    them owns each action seam.

    Entry:
        entity - a CombatEntity. May be a Character with equipment or an NPC
                 carrying its rules on itself.

    Exit/Returns:
        A multi-line ANSI-tagged string ready for entity.msg(...).

    Module Globals:
        ACTION_SEAM_NAMES read.
        DEFAULT_ACTION_RULES read.

    Methodology:
        Collects contributors fresh rather than reading the handler's ndb
        cache. The report is for diagnosing what SHOULD happen from the
        current gear; reading the cache would hide the exact bug -- a stale
        cache -- that someone running this command is most likely hunting.

        contribute_modifiers is excluded from the seam table because it is
        not a contest: every contributor's modifiers run. Listing a single
        "winner" for it would state the opposite of the truth.

    Notes/References:
        Modifier CHANNELS are not shown. A channel's contents depend on the
        defender and the rng, so they only exist during an action; showing an
        empty bag here would read as "this amulet does nothing".

    Author: Nick Hobar
    Creation date: 08/04/2026
    """
    contributors = collect_contributors(entity)
    label = getattr(entity, "key", entity)

    lines = [f"|wAction rules for {label}|n", "", "|wContributors|n"]
    lines.extend(_contributor_lines(contributors))
    lines.extend(["", "|wSeam owners|n"])
    lines.extend(_seam_lines(contributors))

    return "\n".join(lines)


def describe_registry() -> str:
    """
    Purpose: List every registered rules definition and what it replaces.

    Entry:
        No conditions.

    Exit/Returns:
        A multi-line ANSI-tagged string.

    Module Globals:
        None.

    Methodology:
        Sorted by priority then key so the reading order matches the order
        the pipeline applies them in.

    Notes/References:
        The import is deferred so this module can be imported by the command
        layer without pulling the whole rule_defs tree at startup.

    Author: Nick Hobar
    Creation date: 08/04/2026
    """
    from .registry import RULES_REGISTRY

    if not RULES_REGISTRY:
        return "No action rules are registered."

    ordered = sorted(RULES_REGISTRY.values(),
                     key=lambda rules: (rules.priority, rules.key))
    lines = ["|wRegistered action rules|n"]

    for rules in ordered:
        seams = getattr(rules, "_overridden_seams", frozenset())
        owned = ", ".join(sorted(seams)) or "nothing"
        lines.append(f"  |y{rules.name}|n (|w{rules.key}|n)")
        lines.append(f"      priority {rules.priority} — overrides: {owned}")
        lines.append(f"      {rules.description}")

    return "\n".join(lines)
