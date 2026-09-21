"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/20/2026
Description: Tunables and message templates for the channeled harvest -- the
             swing cadence, the units a chance is quoted in, where a node
             records who has spent it, and every line a channel sends.

             A harvest used to be one command and one guaranteed item, so
             there was nothing to tune and these values did not exist. A
             channel has a cadence, a roll, a depletion and four ways to end,
             and each of those is a number or a sentence somebody will want to
             change. They live here rather than in the handler so that a
             retune is an edit to a table and not to a state machine.
"""



from systems.core.tick import constants as tick_constants
from systems.gameplay.progression.skills import constants as skill_constants



# ─── The swing ──────────────────────────────────────────────────────────────

# How many engine ticks pass between one swing and the next. OSRS rolls
# woodcutting every four ticks, and the Blackout tick is the same length, so
# the cadence transfers with the numbers it was measured against.
#
# THE TOOL DOES NOT CHANGE THIS. A better axe raises the success chance
# instead. That is the OSRS rule, and it is the one knob that cannot make a
# fast tool strictly better than an accurate one -- two knobs multiply, and
# the tiers separate faster than any table can predict.
SWING_TICKS: int = 4

# Seconds between swings. DERIVED, never typed. The tick length has one owner
# and a second copy of 2.4 here goes stale the day the tick is retuned.
SWING_SECONDS: float = SWING_TICKS * tick_constants.TICK_SECONDS



# ─── The roll ───────────────────────────────────────────────────────────────

# The denominator a low/high pair is quoted in. OSRS quotes its woodcutting
# and mining tables in 1/255, so a pair lifted from the wiki transfers with no
# arithmetic -- the same bargain the combat maths takes with raw monster
# stats. See CLAUDE.md "Design intent".
CHANCE_DENOMINATOR: int = 255

# The level a `high` value describes. `low` describes level 0.
#
# Read from the skill system rather than typed, so a rescale of the ladder
# moves the roll with it. OSRS interpolates over 1..99; Blackout's skills run
# 0..127, so the endpoints are the ends of the range rather than 1 and 99.
CHANCE_TOP_LEVEL: int = skill_constants.MAX_BASE_SKILL_LEVEL

# The tier a node's chance table falls back on when the character carries no
# tool at all. Not zero and not a real tier: a bare-handed roll reads its own
# pair off GatherableDef.bare_hand_chance, and this names the absence so a log
# line can say which pair it used.
BARE_HAND_TIER: int = -1



# ─── Per-player depletion ───────────────────────────────────────────────────

# The Attribute on the NODE that records who has spent it and until when:
# {character_id: unix timestamp}. It lives on the node rather than on the
# character because a deleted node must take the fact with it. A character
# side list would outlive every node it named and grow for the life of the
# account, and a map rebuild would leave it pointing at ids that no longer
# exist.
SPENT_ATTRIBUTE: str = "spent_until"

# How many expired rows the prune tolerates before it rewrites the Attribute.
# A busy node collects one row per harvester, and rewriting a dict on every
# read would cost a database write per swing per player. Zero would be
# correct and expensive; a small number is correct and cheap.
SPENT_PRUNE_THRESHOLD: int = 8



# ─── Why a channel stopped ──────────────────────────────────────────────────
# A reason is a key, not a sentence, so the handler names what happened and
# this table decides how to say it. The handler is a state machine and must
# not also be a phrasebook.

STOP_REASON_DEPLETED = "depleted"
STOP_REASON_BAG_FULL = "bag_full"
STOP_REASON_MOVED = "moved"
STOP_REASON_INTERRUPTED = "interrupted"
STOP_REASON_ABANDONED = "abandoned"
STOP_REASON_GONE = "gone"
STOP_REASON_LEVELLED_OUT = "levelled_out"
STOP_REASON_CONSUMED = "consumed"

# Every reason a channel can end, and the line the player reads for it.
#
# {node} is the node's key and {verb} is the skill's verb, so one table serves
# Cutting, Butchery and anything added later. A reason with no row here is a
# reason the player is told nothing about, which is the bug the old silent
# cooldown refusal was.
STOP_MESSAGES: dict = {
    STOP_REASON_DEPLETED: ("You have stripped the {node} bare. Need to wait for it to respawn."),
    STOP_REASON_BAG_FULL: ("You stop: you have no room to carry any more."),
    STOP_REASON_MOVED: "You stop working the {node}.",
    STOP_REASON_INTERRUPTED: "You are interrupted, and stop working the {node}.",
    STOP_REASON_ABANDONED: "You stop working the {node}.",
    STOP_REASON_GONE: "The {node} is no longer there.",
    STOP_REASON_LEVELLED_OUT: ("There is nothing left on the {node} that you can take."),
    STOP_REASON_CONSUMED: "There is nothing left of the {node}.",
}

# Reasons whose line would repeat something the player has just read. These
# send nothing.
#
# MOVED: walking away already prints a room description, and a sentence
# under it saying you stopped doing the thing you walked away from is noise.
#
# CONSUMED: the harvest line that ended the node says what happened to it.
# "You butcher the Mutant Raider corpse and receive a chuck" needs no
# "there is nothing left of it" beneath it.
QUIET_STOP_REASONS: frozenset = frozenset({
    STOP_REASON_MOVED,
    STOP_REASON_CONSUMED,
})

# Every reason the handler may be given. One name in one place, so a reason
# invented at a call site is caught here rather than reaching a player as
# silence.
STOP_REASONS: frozenset = frozenset(STOP_MESSAGES)

# A reason with no line and no exemption is a channel that ends and says
# nothing, which is the bug the old silent cooldown refusal was. Caught at
# import, like every other table in the gathering system.
_voiceless = [
    reason for reason in STOP_REASONS
    if not STOP_MESSAGES[reason] and reason not in QUIET_STOP_REASONS
]
if _voiceless:
    raise ValueError(
        f"gathering constants: stop reasons with no message and no quiet "
        f"exemption: {_voiceless}"
    )

# The reverse: an exemption naming a reason that does not exist is a typo
# that reads as working, because a reason nobody sends is never announced.
_unknown_quiet = [
    reason for reason in QUIET_STOP_REASONS if reason not in STOP_MESSAGES
]
if _unknown_quiet:
    raise ValueError(
        f"gathering constants: QUIET_STOP_REASONS names unknown reasons: "
        f"{_unknown_quiet}"
    )



# ─── What a channel says ────────────────────────────────────────────────────

# The line that opens a channel. Sent once, however long the channel runs.
#
# A FAILED SWING IS SILENT, which is the OSRS rule and the reason this line
# exists: without it a player whose first six rolls miss has no evidence the
# command did anything. With it, the channel announces itself once and then
# speaks only when it produces something.
MSG_CHANNEL_START = "You start to {verb} the {node}."

# What a player is told when they aim at a node they have already spent. The
# node is still standing and still visible -- see SPENT_ATTRIBUTE for why it
# is not hidden -- so the refusal has to say why it will not work rather than
# pretend the node is absent.
MSG_NODE_SPENT = "You have already stripped the {node}. It recovers in a moment."

# What a player is told when they aim at the node they are already working.
# Not a refusal: repeating the command is what a player does when they are not
# sure it took, and telling them "you are already busy" reads as a failure.
MSG_ALREADY_WORKING = "You are already working the {node}."
