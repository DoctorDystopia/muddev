"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Inline ANSI-tagged combat message builders.
"""

# ─── Color palette ─────────────────────────────────────────────────────────
# Sourced from the game-wide palette in systems/ui/colors.py
#
# Color theory:
#   incoming damage  → bold red    (|r)   — danger, drawn to the eye
#   outgoing damage  → green/white (|g|w) — positive feedback for the player
#   miss / zero dmg  → muted gray   (|x)  — fail-state, low visual weight
#   death            → bright red   (|R)  — terminal event
#   xp gained        → yellow       (|y)  — reward, distinct from the damage
from systems.ui.colors import (  # noqa: E402  (palette, not behaviour)
    TAG_DEATH,
    TAG_INCOMING,
    TAG_LOOT,
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

# Damage-type constants own the vocabulary format_death branches on. Imported
# rather than restated so a renamed type is a one-line change, not a silent
# fallthrough to the generic line.
from systems.combat import constants as const  # noqa: E402


# ─── Public constant definitions ───────────────────────────────────────────

# Label used when an HP bar is shown to the entity it belongs to.
SELF_HP_LABEL = "You"

# Separator between the per-skill entries of one hit's XP award.
XP_ENTRY_SEPARATOR = ", "

# Separator between the items named on one kill's drop line.
DROP_ENTRY_SEPARATOR = ", "

# Every combat_stat_bonuses key is spelled "<axis>_bonus"; stripping this
# suffix and title-casing the rest is what lets format_combat_stat_bonuses
# label a new stat key with no parallel lookup table to keep in sync -- the
# same approach WieldLocation.label uses for slot names.
STAT_KEY_BONUS_SUFFIX = "_bonus"


# ─── Private helper routines ────────────────────────────────────────────────

def _label_for_stat_key(stat_key: str) -> str:
    """Derive a player-facing label from a combat_stat_bonuses key.

    "stab_attack_bonus" -> "Stab Attack". Purely mechanical so a new stat key
    added to a weapon or armor def needs no second edit here to display.
    """
    stripped = stat_key.removesuffix(STAT_KEY_BONUS_SUFFIX)
    spaced = stripped.replace("_", " ")

    return spaced.title()


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


def format_death(victim, killer=None, damage_type=None, self_inflicted=False) -> str:
    """
    Purpose: Room broadcast for an entity's HP hitting zero.

    Entry:
        victim         - the entity that just collapsed.
        killer         - optional killer; pass None for a death with no other
                         party, including a self-inflicted one.
        damage_type    - optional DAMAGE_TYPE_* constant naming what landed
                         the killing blow. Not read by this function today;
                         accepted so callers can pass it through uniformly
                         for future per-type death lines.
        self_inflicted - True if the victim killed themselves (a backfiring
                         gadget, a fumbled trap). Decides the line, NOT
                         damage_type -- the damage type names what killed
                         them (energy, melee, ...), self_inflicted names WHO.

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

        The self-inflicted branch exists because "X collapses." reads as an
        unexplained death when the player just watched their own gadget go
        off. CombatEntity.at_death computes self_inflicted from `killer is
        self` BEFORE normalising the killer to None, since by the time
        `killer` reaches this function that identity is already gone.

    Author: Nick Hobar
    Creation date: 07/26/2026
    """
    if self_inflicted:
        return f"{TAG_DEATH}{victim.key} is killed by their own equipment.{TAG_RESET}"

    if killer is None:
        return f"{TAG_DEATH}{victim.key} collapses.{TAG_RESET}"

    return f"{TAG_DEATH}{victim.key} collapses, killed by {killer.key}.{TAG_RESET}"


def format_drops(victim, drops: list) -> str:
    """
    Purpose: Room broadcast naming what a dead entity left on the ground.

    Entry:
        victim - the entity that just died.
        drops  - list of (item_name, quantity) tuples, already resolved to
                 DISPLAY NAMES by the caller. Must be non-empty; a kill that
                 dropped nothing has no line to print, and deciding that is
                 the caller's job, not this formatter's.

    Exit/Returns:
        Single-line string ready for location.msg_contents(...).

    Module Globals:
        TAG_LOOT read.
        TAG_RESET read.
        DROP_ENTRY_SEPARATOR read.

    Methodology:
        A quantity above one is suffixed "(xN)" rather than prefixed as a
        count, because the item names in ITEM_DB are singular and unpluralised
        -- "2 rusty metal chunk" reads as a bug, and pluralising properly would
        need a second name field on every ItemDef to handle the irregulars.

    Notes/References:
        This is the follow-on message format_death's docstring reserved: the
        death line stays a single stable sentence and drops arrive beside it,
        so neither formatter's signature has to move when corpses land.

        Takes display names rather than item keys so the message layer never
        reaches into ITEM_DB -- systems/loot/drops.py already has the ItemDef
        in hand at the point it calls this.

    Author: Nick Hobar
    Creation date: 08/14/2026
    """
    parts = []

    for item_name, quantity in drops:
        if quantity > 1:
            parts.append(f"{item_name} (x{quantity})")
        else:
            parts.append(str(item_name))

    listed = DROP_ENTRY_SEPARATOR.join(parts)

    return f"{TAG_LOOT}{victim.key} drops: {listed}.{TAG_RESET}"


def format_backfire(wielder, source, damage: int) -> str:
    """
    Purpose: Line shown to a player whose own equipment just hurt them.

    Entry:
        wielder - the entity taking the damage.
        source  - the object that backfired. May be None if the rule that
                  produced the damage was not carried by an item.
        damage  - integer damage dealt to the wielder.

    Exit/Returns:
        Single-line string for wielder.msg(...).

    Module Globals:
        TAG_INCOMING read.
        TAG_OUTGOING_NAME read.
        TAG_RESET read.

    Methodology:
        Uses the incoming palette, because that is what it is from the
        player's side — the damage happens to them, not to their target.
        Names the culprit for the same reason an aura burn names the aura: a
        player with a backfiring weapon has two damage sources on screen and
        must be able to tell which one just went off.

    Author: Nick Hobar
    Creation date: 08/04/2026
    """
    culprit = getattr(source, "key", None) or "equipment"

    return (
        f"{TAG_INCOMING}Your {TAG_OUTGOING_NAME}{culprit}{TAG_INCOMING} "
        f"backfires, hitting you for {damage}.{TAG_RESET}"
    )


# ─── Damage auras ───────────────────────────────────────────────────────────
# An aura pulses on a cadence with no player input, so its lines are read
# passively and repeatedly rather than as a reaction to a command. They reuse
# the outgoing/incoming palette so a burn reads like any other damage, but the
# aura is always named — otherwise a player with an aura up cannot tell which
# of the two damage sources on screen is which.

def format_aura_activate(aura) -> str:
    """
    Purpose: Confirm to the caster that an aura is now burning.

    Entry:
        aura - the aura definition being switched on; aura.name is rendered.

    Exit/Returns:
        Formatted single-line string ready for caller.msg(...).

    Module Globals:
        TAG_OUTGOING, TAG_OUTGOING_NAME, TAG_RESET read.

    Methodology:
        Names the aura rather than saying "it" so the off message can mirror it
        exactly, which matters once a second aura exists.

    Author: Nick Hobar
    Creation date: 08/03/2026
    """
    return (
        f"{TAG_OUTGOING}You ignite "
        f"{TAG_OUTGOING_NAME}{aura.name}{TAG_OUTGOING}.{TAG_RESET}"
    )


def format_aura_deactivate(aura) -> str:
    """
    Purpose: Confirm to the caster that an aura has been switched off.

    Entry:
        aura - the aura definition being switched off; aura.name is rendered.

    Exit/Returns:
        Formatted single-line string ready for caller.msg(...).

    Module Globals:
        TAG_MISS, TAG_RESET read.

    Methodology:
        Muted rather than green: switching an aura off is a neutral state
        change, not an accomplishment, and it happens often enough that a bright
        line would draw the eye away from combat.

    Author: Nick Hobar
    Creation date: 08/03/2026
    """
    return f"{TAG_MISS}{aura.name} gutters out.{TAG_RESET}"


def format_aura_pulse(aura, target, damage: int) -> str:
    """
    Purpose: One line describing an aura pulse the caller dealt to one target.

    Entry:
        aura   - the aura definition; aura.name is rendered.
        target - the entity taking the damage; target.key is rendered.
        damage - integer HP removed by this pulse.

    Exit/Returns:
        Formatted single-line string ready for caller.msg(...).

    Module Globals:
        TAG_OUTGOING, TAG_OUTGOING_NAME, TAG_RESET read.

    Methodology:
        Deliberately carries no XP suffix. An aura pulse hits every enemy in
        radius at once and earns experience on the pulse TOTAL, so a per-target
        award would either repeat the same figure on every line or show shares
        that do not sum as displayed. format_aura_xp prints it once instead.

    Author: Nick Hobar
    Creation date: 08/03/2026
    """
    return (
        f"{TAG_OUTGOING}{aura.name} sears "
        f"{TAG_OUTGOING_NAME}{target.key}{TAG_OUTGOING} for "
        f"{TAG_OUTGOING_NAME}{damage}{TAG_OUTGOING} damage.{TAG_RESET}"
    )


def format_aura_incoming(aura, target, damage: int) -> str:
    """
    Purpose: One line describing an aura pulse, for everyone else in the room.

    Entry:
        aura   - the aura definition; aura.name is rendered.
        target - the entity taking the damage; target.key is rendered.
        damage - integer HP removed by this pulse.

    Exit/Returns:
        Formatted single-line string ready for room.msg_contents(...).

    Module Globals:
        TAG_INCOMING, TAG_RESET read.

    Methodology:
        An aura reaches rooms the caster is not standing in, so this line must
        make sense with nobody visible to attribute it to — it names the aura
        and the victim, never the caster.

    Author: Nick Hobar
    Creation date: 08/03/2026
    """
    return (
        f"{TAG_INCOMING}{target.key} is seared by {aura.name} "
        f"for {damage} damage.{TAG_RESET}"
    )


def format_aura_xp(aura, amount: int) -> str:
    """
    Purpose: Report the experience one aura pulse earned, on its own line.

    Entry:
        aura   - the aura definition; aura.xp_skill names the earning skill.
        amount - integer experience granted for the whole pulse.

    Exit/Returns:
        Formatted single-line string ready for caller.msg(...).

    Module Globals:
        TAG_XP, TAG_RESET read.

    Methodology:
        Separate from the burn lines because one pulse produces N burn lines but
        exactly one award. Title-cases the skill key for display rather than
        importing the skill registry, keeping this module free of that
        dependency exactly as format_xp_gain does.

    Author: Nick Hobar
    Creation date: 08/03/2026
    """
    skill_name = str(aura.xp_skill).replace("_", " ").title()

    return f"{TAG_XP}(+{amount} {skill_name} xp){TAG_RESET}"


# ─── Equipment stat readouts ─────────────────────────────────────────────────

def format_combat_stat_bonuses(bonuses: dict) -> list:
    """
    Purpose: Render a combat_stat_bonuses dict as player-facing lines, for an
    item's inspect screen or an equipment total.

    Entry:
        bonuses - dict[str, int] keyed by stat (e.g. "stab_attack_bonus").
                  May be empty.

    Exit/Returns:
        A list of colour-tagged "Label: +N" strings, one per NON-ZERO entry,
        in the dict's iteration order. Positive values render in the
        outgoing (green) tag, negative in the incoming (red) tag. An
        all-zero or empty dict returns an empty list -- callers show their
        own "no bonuses" line rather than this module guessing that copy.

    Module Globals:
        TAG_OUTGOING, TAG_INCOMING, TAG_RESET read.
        STAT_KEY_BONUS_SUFFIX read (via _label_for_stat_key).

    Methodology:
        Zero entries are skipped so an item's screen only lists what it
        actually changes -- the unarmed baseline and every unworn armour slot
        carry a full set of zero keys that would otherwise bury the nonzero
        ones.

    Author: Nick Hobar
    Creation date: 08/04/2026
    """
    lines = []

    for stat_key, stat_value in bonuses.items():
        if stat_value == 0:
            continue

        label = _label_for_stat_key(stat_key)
        tag = TAG_OUTGOING if stat_value > 0 else TAG_INCOMING
        sign = "+" if stat_value > 0 else ""
        lines.append(f"{label}: {tag}{sign}{stat_value}{TAG_RESET}")

    return lines


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
