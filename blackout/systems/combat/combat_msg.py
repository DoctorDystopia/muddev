"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Inline ANSI-tagged combat message builders (no Evennia imports).
"""

# ─── Color palette ─────────────────────────────────────────────────────────
# Follows the codebase convention (see systems/menus/base_menu.py,
# systems/progression/skills/logic.py:285). Evennia parses these inline |x
# tags at send time, so the formatter module stays free of evennia imports
# and remains unit-testable.
#
# Color theory per the research doc §"Combat Logging and ANSI Formatting":
#   incoming damage  → bold red    (|r)   — danger, drawn to the eye
#   outgoing damage  → green/white (|g|w) — positive feedback for the player
#   miss / zero dmg  → muted gray   (|x)  — fail-state, low visual weight
#   death            → bright red   (|R)  — terminal event
TAG_INCOMING = "|r"
TAG_OUTGOING = "|g"
TAG_OUTGOING_NAME = "|w"
TAG_MISS = "|x"
TAG_DEATH = "|R"
TAG_RESET = "|n"


# ─── Outgoing perspective (the attacker sees these) ────────────────────────


def format_outgoing_hit(attacker, target, damage: int) -> str:
    """
    Purpose: One-line message describing a successful hit the caller dealt.

    Entry:
        attacker - the damage dealer (unused in the message but kept in the
                   signature so callers can pass through uniformly).
        target   - the entity taking the damage; target.key is rendered.
        damage   - integer damage dealt (post accuracy+damage roll).

    Exit/Returns:
        Formatted single-line string ready for caller.msg(...).

    Module Globals:
        TAG_OUTGOING read.
        TAG_OUTGOING_NAME read.
        TAG_RESET read.

    Methodology:
        Green damage number, white target name. Single f-string, ≤1 line.

    Notes/References:
        Research doc §"Combat Logging and ANSI Formatting".

    Author: Nick Hobar
    Creation date: 07/26/2026
    """
    return f"{TAG_OUTGOING}You hit {TAG_OUTGOING_NAME}{target.key}{TAG_OUTGOING} for {damage}.{TAG_RESET}"


def format_outgoing_miss(attacker, target) -> str:
    """
    Purpose: One-line message describing a missed swing the caller made.

    Entry:
        attacker - the attacker (unused, signature parity with format_*_hit).
        target   - the entity that dodged.

    Exit/Returns:
        Gray single-line string.

    Module Globals:
        TAG_MISS read.
        TAG_OUTGOING_NAME read.
        TAG_RESET read.

    Methodology:
        Muted gray tone — a whiff is non-critical feedback.

    Notes/References:
        Research doc §"Combat Logging and ANSI Formatting".

    Author: Nick Hobar
    Creation date: 07/26/2026
    """
    return f"{TAG_MISS}You swing at {TAG_OUTGOING_NAME}{target.key}{TAG_MISS} and miss.{TAG_RESET}"


# ─── Incoming perspective (the defender sees these) ─────────────────────────


def format_incoming_hit(attacker, target, damage: int) -> str:
    """
    Purpose: One-line message describing damage the caller took.

    Entry:
        attacker - the entity that landed the hit.
        target   - the defender (the message recipient; kept for symmetry).
        damage   - integer amount of HP loss.

    Exit/Returns:
        Red single-line string — immediate visual alarm.

    Module Globals:
        TAG_INCOMING read.
        TAG_OUTGOING_NAME read.
        TAG_RESET read.

    Methodology:
        Bold red is reserved for damage the player takes. Keeping it ≤1 line
        prevents spam in high-APM twitch combat.

    Notes/References:
        Research doc §"Combat Logging and ANSI Formatting".

    Author: Nick Hobar
    Creation date: 07/26/2026
    """
    return f"{TAG_INCOMING}{TAG_OUTGOING_NAME}{attacker.key}{TAG_INCOMING} hits you for {damage}.{TAG_RESET}"


def format_incoming_miss(attacker, target) -> str:
    """
    Purpose: One-line message describing an incoming swing that missed.

    Entry:
        attacker - the entity whose swing failed to land.
        target   - the would-be victim.

    Exit/Returns:
        Gray single-line string.

    Module Globals:
        TAG_MISS read.
        TAG_OUTGOING_NAME read.
        TAG_RESET read.

    Methodology:
        Same gray fallback as the outgoing miss; a dodge is a non-critical
        event for the defender too.

    Notes/References:
        Research doc §"Combat Logging and ANSI Formatting".

    Author: Nick Hobar
    Creation date: 07/26/2026
    """
    return f"{TAG_MISS}{TAG_OUTGOING_NAME}{attacker.key}{TAG_MISS} swings at you and misses.{TAG_RESET}"


# ─── Public room broadcasts ─────────────────────────────────────────────────


def format_third_party_hit(attacker, target, damage: int) -> str:
    """
    Purpose: Room broadcast line for bystanders watching a hit land.

    Entry:
        attacker - the damage dealer.
        target   - the damage taker.
        damage   - integer damage.

    Exit/Returns:
        Plain (uncolored) single-line string. Bystanders see combat at
        neutral color to avoid noise-spamming observers.

    Module Globals:
        None.

    Methodology:
        Colorless f-string; tags applied only on directed (in/out) messages.

    Notes/References:
        Research doc §"Combat Logging and ANSI Formatting".

    Author: Nick Hobar
    Creation date: 07/26/2026
    """
    return f"{attacker.key} hits {target.key} for {damage}."


def format_death(victim, killer=None) -> str:
    """
    Purpose: Room broadcast for an entity's HP hitting zero.

    Entry:
        victim - the entity that just collapsed.
        killer - optional killer; pass None for environmental deaths
                 (poison, fall damage, etc. — currently out of scope).

    Exit/Returns:
        Bright-red single-line string ready for location.msg_contents(...).

    Module Globals:
        TAG_DEATH read.
        TAG_RESET read.

    Methodology:
        Single line collapses the brand of all future death animations —
        corpses, loot drops, etc. will be follow-on messages, not part of
        this one, so the formatter's signature can stay stable as those
        land in later batches.

    Notes/References:
        Research doc §"Translating Game State to Evennia".

    Author: Nick Hobar
    Creation date: 07/26/2026
    """
    if killer is None:
        return f"{TAG_DEATH}{victim.key} collapses.{TAG_RESET}"

    return f"{TAG_DEATH}{victim.key} collapses, killed by {killer.key}.{TAG_RESET}"
