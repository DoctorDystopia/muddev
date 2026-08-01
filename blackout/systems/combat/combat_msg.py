"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Inline ANSI-tagged combat message builders.
"""

# ─── Color palette ─────────────────────────────────────────────────────────
# Sourced from the game-wide palette in systems/ui/colors.py rather than
# carrying a second copy of the tag literals.
#
# Color theory per the research doc §"Combat Logging and ANSI Formatting":
#   incoming damage  → bold red    (|r)   — danger, drawn to the eye
#   outgoing damage  → green/white (|g|w) — positive feedback for the player
#   miss / zero dmg  → muted gray   (|x)  — fail-state, low visual weight
#   death            → bright red   (|R)  — terminal event
#   xp gained        → yellow       (|y)  — reward, distinct from the damage
from systems.ui.colors import (  # noqa: E402  (palette, not behaviour)
    TAG_DEATH,
    TAG_INCOMING,
    TAG_MISS,
    TAG_OUTGOING,
    TAG_OUTGOING_NAME,
    TAG_RESET,
    TAG_XP,
)

# The HP bar is drawn by the shared meter wrapper so combat and the skills
# panel cannot drift apart. This is the one Evennia-backed import in the
# module (meters wraps the health_bar contrib); everything else here is pure
# string assembly.
from systems.ui.meters import build_hp_meter  # noqa: E402


# ─── Public constant definitions ───────────────────────────────────────────

# Label used when an HP bar is shown to the entity it belongs to.
SELF_HP_LABEL = "You"

# Separator between the per-skill entries of one hit's XP award.
XP_ENTRY_SEPARATOR = ", "


# ─── Outgoing perspective (the attacker sees these) ────────────────────────


def format_outgoing_hit(attacker, target, damage: int, xp_text: str = "") -> str:
    """
    Purpose: One-line message describing a successful hit the caller dealt.

    Entry:
        attacker - the damage dealer (unused in the message but kept in the
                   signature so callers can pass through uniformly).
        target   - the entity taking the damage; target.key is rendered.
        damage   - integer damage dealt (post accuracy+damage roll).
        xp_text  - optional pre-formatted XP suffix from format_xp_gain. It
                   carries its own leading space and colour tags, so it is
                   appended verbatim.

    Exit/Returns:
        Formatted single-line string ready for caller.msg(...).

    Module Globals:
        TAG_OUTGOING read.
        TAG_OUTGOING_NAME read.
        TAG_RESET read.

    Methodology:
        Green damage number, white target name, and the XP earned by this one
        swing on the same line. Keeping the award inline rather than on its own
        line matters at a 0.6s tick: a second line per hit doubles the scroll
        rate of a fight.

    Notes/References:
        Research doc §"Combat Logging and ANSI Formatting".

    Author: Nick Hobar
    Creation date: 07/26/2026
    """
    hit_line = f"{TAG_OUTGOING}You hit {TAG_OUTGOING_NAME}{target.key}{TAG_OUTGOING} for {damage}.{TAG_RESET}"

    return f"{hit_line}{xp_text}"


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


# ─── Progress readouts (XP earned, HP remaining) ────────────────────────────


def format_xp_gain(awards) -> str:
    """
    Purpose: Render the per-skill XP one swing earned, as a suffix for the hit
    line.

    Entry:
        awards - a sequence of (display_name, amount) pairs, already filtered
                 to the awards actually granted. An empty sequence is the
                 normal case for a miss or a zero-damage hit.

    Exit/Returns:
        Empty string when nothing was awarded, so callers can append it
        unconditionally. Otherwise a yellow parenthesised list carrying a
        LEADING SPACE, e.g. " |y(+4 Strike, +1 Fortitude xp)|n".

    Module Globals:
        XP_ENTRY_SEPARATOR read.
        TAG_XP read.
        TAG_RESET read.

    Methodology:
        Takes display names rather than skill keys so this module needs no
        dependency on the skill registry — the caller, which already holds the
        registry, resolves them.

    Notes/References:
        Combat XP was previously awarded silently: the player could watch
        Strike climb only by re-opening the skills panel between fights.

    Author: Nick Hobar
    Creation date: 08/01/2026
    """
    if not awards:
        return ""

    entries = [f"+{amount} {name}" for name, amount in awards]
    joined = XP_ENTRY_SEPARATOR.join(entries)

    return f" {TAG_XP}({joined} xp){TAG_RESET}"


def format_hp_status(label: str, current_hp: int, max_hp: int) -> str:
    """
    Purpose: Render one combatant's remaining hitpoints as a labelled bar.

    Entry:
        label      - the name to print ahead of the bar. Pass SELF_HP_LABEL
                     when the bar is going to the entity it describes.
        current_hp - integer HP remaining, post-damage.
        max_hp     - integer HP ceiling. Zero or less renders a no-data marker
                     rather than a misleading full bar.

    Exit/Returns:
        Single-line string: white label, then a METER_WIDTH-wide meter.

    Module Globals:
        TAG_OUTGOING_NAME read.
        TAG_RESET read.

    Methodology:
        Delegates the bar itself to systems.ui.meters.build_hp_meter, the same
        wrapper the skills panel uses for XP, so both bars share one width and
        one rendering path. The label lives OUTSIDE the meter: the contrib
        truncates its base text to the bar width, so folding a long combatant
        name into it would eat the numbers.

    Notes/References:
        systems/ui/meters.py for the gradient and the width constant.

    Author: Nick Hobar
    Creation date: 08/01/2026
    """
    meter = build_hp_meter(current_hp, max_hp)

    return f"{TAG_OUTGOING_NAME}{label}{TAG_RESET} {meter}"
