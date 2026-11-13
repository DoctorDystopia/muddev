"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The tunables and the vocabulary of the Augmentation skill
             (DESIGN-0015). Every number here is a placeholder until Nick
             tunes it. The vault note owns the rules:
             03_Systems/Skills/Combat Skills/Augmentation_Skill.md.
"""



# ─── The Grit pool ───────────────────────────────────────────────────────────
# The maximum Grit is the Augmentation level plus this floor. Skills start
# at 0, so the floor is what lets a new player light the starter augment for
# a short time, as Fortitude seeds at 1 (Nick, 10/30/2026: 1).
AUG_POOL_FLOOR: int = 1

# The Attribute that holds the current Grit of a character. pool.py is the
# one writer. A character made before 10/30/2026 has no such Attribute, and
# the pool reads that as full: the character never spent any.
GRIT_ATTR: str = "grit"

# The least Grit. At this value, every lit augment goes out (Phase 2).
GRIT_EMPTY: int = 0



# ─── The drain ───────────────────────────────────────────────────────────────
# The OSRS counter (DESIGN-0015, section 4.2). Each tick adds the drain of
# each lit augment to a counter. When the counter passes the resistance, one
# Grit point goes. The resistance is AUG_DRAIN_BASE plus AUG_DRAIN_PER_BONUS
# times the augmentation bonus of the gear. The OSRS values, 60 and 2, are
# the placeholders.
AUG_DRAIN_BASE: int = 60
AUG_DRAIN_PER_BONUS: int = 2

# The combat_stat_bonuses key that gear gives for the resistance. Nothing
# in the item defs gives it yet (Phase 6). The accessor reads it today.
AUGMENTATION_BONUS_KEY: str = "augmentation_bonus"

# One Grit point goes each time the counter passes the resistance.
AUG_DRAIN_POINT: int = 1

# The counter starts here when the first augment lights.
AUG_DRAIN_COUNTER_START: float = 0.0


# ─── The power level dial ────────────────────────────────────────────────────
# An augment burns at a power level from 1 to AUG_POWER_LEVELS (Nick,
# 10/30/2026: 3). Power level 1 gives a third of the strength for a third of
# the drain. Power level AUG_POWER_LEVELS gives the whole of both. The OSRS
# tiers, on one row. The power level was the "step" until 11/09/2026.
AUG_POWER_LEVELS: int = 3
AUG_POWER_LEVEL_MIN: int = 1

# A light with no power level named burns at the top power level.
AUG_POWER_LEVEL_DEFAULT: int = AUG_POWER_LEVELS


# ─── The families ────────────────────────────────────────────────────────────
# One augment for each axis (section 4.4). The family says which channel of
# the action the augment boosts. The level sets the strength.
FAMILY_ACCURACY: str = "accuracy"
FAMILY_DAMAGE: str = "damage"
FAMILY_DEFENSE: str = "defense"

# No level gates an augment with this unlock level. The aura twin is
# NO_UNLOCK_REQUIREMENT in base_aura.py.
NO_UNLOCK_LEVEL: int = 0


# ─── The `aug` command ───────────────────────────────────────────────────────
# `aug` lists. `aug <name> [<power level>]` lights an augment, or moves a lit
# augment to the new power level.
# `aug <name> off` puts one out. `aug off` puts every augment out. The
# templates are what the ability rail sends (Phase 3), as the aura
# templates in combat/constants.py are.
AUG_COMMAND_KEY: str = "aug"
AUG_OFF_ARG: str = "off"
AUG_IGNITE_TEMPLATE: str = f"{AUG_COMMAND_KEY} {{name}}"
AUG_IGNITE_POWER_LEVEL_TEMPLATE: str = f"{AUG_COMMAND_KEY} {{name}} {{power_level}}"
AUG_EXTINGUISH_TEMPLATE: str = f"{AUG_COMMAND_KEY} {{name}} {AUG_OFF_ARG}"
AUG_EXTINGUISH_ALL_COMMAND: str = f"{AUG_COMMAND_KEY} {AUG_OFF_ARG}"

# The set (the quick prayer orb of OSRS). `aug set` lights every augment
# that can come online, at the default power level. Phase 5 narrows it to
# the sockets. The set row of the rail carries it when nothing burns, and
# `aug off` when anything does.
AUG_SET_ARG: str = "set"
AUG_SET_COMMAND: str = f"{AUG_COMMAND_KEY} {AUG_SET_ARG}"
AUG_SET_ROW_KEY: str = "augment_set"
AUG_SET_ROW_NAME: str = "Set"
AUG_SET_TIP_LINES: tuple = (
    "Brings every augment you can use online at once.",
    "Press again to put them all out.",
)

# Player-facing text. The voice stays.
AUG_LIGHT_MESSAGE: str = "{name} comes online at power level {power_level}."
AUG_POWER_SHIFT_MESSAGE: str = "{name} shifts to power level {power_level}."
AUG_OUT_MESSAGE: str = "{name} goes offline."
AUG_ALL_OUT_MESSAGE: str = "Every augment goes offline."
AUG_NONE_LIT_MESSAGE: str = "You have no augment online."
AUG_NOT_LIT_MESSAGE: str = "{name} is not online."
AUG_UNKNOWN_MESSAGE: str = "You know no augment called '{name}'."
AUG_BAD_POWER_LEVEL_MESSAGE: str = "The power level is a number from {low} to {high}."
AUG_NO_GRIT_MESSAGE: str = "You have no Grit left. Find an AugBot."
AUG_SPENT_MESSAGE: str = "Your Grit is spent. Every augment goes offline."
AUG_LOCKED_MESSAGE: str = "{name} needs Augmentation level {level}."
AUG_LIST_TITLE: str = "|wAugments|n"
AUG_LIST_LIT: str = "online, power level {power_level}"
AUG_LIST_READY: str = "ready"
AUG_LIST_EMPTY: str = "You know of no augments."
AUG_LIST_NO_SOCKETS: str = "  Nothing sits in your rig. Try |yrig|n."
AUG_SET_NONE_MESSAGE: str = "No augment can come online."
AUG_SET_MESSAGE: str = "{count} augment(s) come online."

# The tip lines of an augment row. The server says what an augment IS.
AUG_TIP_BOOST: str = "+{percent:.1f}% to {axis} at your level, at the top power level."
AUG_TIP_DRAIN: str = "Drains {drain:g} Grit units each tick at the top power level."
AUG_TIP_POWER_LEVELS: str = "Power level 1 to {power_levels}: higher power level means a faster drain rate."
AUG_TIP_UNLOCK: str = "Needs Augmentation {level}."
AUG_TIP_AXIS: dict = {
    FAMILY_ACCURACY: "accuracy",
    FAMILY_DAMAGE: "damage",
    FAMILY_DEFENSE: "defense",
}


# ─── The AugBot ──────────────────────────────────────────────────────────────
# The verb at the AugBot. It restores Grit in full, at once and for nothing
# (Nick, 10/30/2026). The Augmentation Locus is a different place: it trains.
AMPLIFY_COMMAND_KEY: str = "amplify"

# The spawner key and the room name of the tile that holds an AugBot. The
# object kind `restore_point` names it (world/object_kinds.py).
AUGBOT_SPAWNER_KEY: str = "AugBot"

# Player-facing text. The voice stays.
AMPLIFY_MESSAGE: str = "You feel like you can take a lot more punishment now."
AMPLIFY_FULL_MESSAGE: str = "Your Grit is already full."
AUGBOT_DESC: str = (
    "An Augmentation Bot. Its articulating arms hold a concerning array of medical tools. "
    "Try |yamplify|n to restore your Grit."
)


# ─── The samples and the graft (Phase 4) ─────────────────────────────────────
# A sample is an item that a graft consumes for Augmentation XP: the bone of
# OSRS Prayer. Each sample names its kind (Nick, 10/30/2026): a biological
# sample or a technological sample. The kind is a tag category on the item,
# so a search by tag finds every sample of one kind, and an object name can
# carry the kind. An ItemDef with `sample_xp` is a sample, and nothing else
# decides it. The two fields reach the object as attributes of these names.
SAMPLE_XP_ATTR: str = "sample_xp"
SAMPLE_KIND_ATTR: str = "sample_kind"
SAMPLE_TAG_CATEGORY: str = "sample"
SAMPLE_KIND_BIO: str = "bio_sample"
SAMPLE_KIND_TECHNO: str = "techno_sample"
SAMPLE_KINDS: tuple = (SAMPLE_KIND_BIO, SAMPLE_KIND_TECHNO)

# The verb that consumes a sample. Anywhere, it pays `sample_xp`. On a tile
# that holds an Augmentation Locus, it pays `sample_xp x AUG_LOCUS_XP_MULT`.
# The gilded altar of OSRS pays 350% of a buried bone, and that ratio is the
# placeholder.
GRAFT_COMMAND_KEY: str = "graft"
AUG_LOCUS_XP_MULT: float = 3.5

# The spawner key and the room name of the tile that holds a Locus. The
# object kind `locus` names it (world/object_kinds.py), and
# test_tile_content.py holds the two equal.
AUG_LOCUS_SPAWNER_KEY: str = "Augmentation Locus"

# Player-facing text. The voice stays.
GRAFT_NOTHING_NAMED_MESSAGE: str = "Graft what? You carry: {names}."
GRAFT_NO_SAMPLES_MESSAGE: str = "You are not carrying any samples to graft."
GRAFT_NOT_A_SAMPLE_MESSAGE: str = "You cannot graft {name}."
GRAFT_MESSAGE: str = "You graft the {name} onto yourself.{suffix}"
GRAFT_LOCUS_MESSAGE: str = (
    "The Locus takes the {name} and grafts it onto you, more skilled than you every could. {suffix}")
AUG_LOCUS_DESC: str = (
    "An Augmentation Locus: a reclined chair under a ring of articulated "
    "arms. A graft here is always better than doing it yourself. Try |ygraft <sample>|n."
)
GRAFT_LIST_SEPARATOR: str = ", "


# ─── The graft channel and the Locus pop-up (11/09/2026) ─────────────────────
# A graft of several samples is a channel on the global tick: one graft each
# GRAFT_TICKS ticks, the pace of the OSRS altar (Nick, 11/09/2026). A walk or
# a fight ends it. The pace holds for EVERY graft, typed or clicked, so a
# click on "Graft 1" again and again is not faster than "Graft All". A count
# works anywhere. Only the XP rate changes at a Locus (Nick, 11/09/2026).
GRAFT_TICKS: int = 3

# `graft stop` ends the running channel. No sample is named "stop".
GRAFT_STOP_ARG: str = "stop"
GRAFT_STOP_COMMAND: str = f"{GRAFT_COMMAND_KEY} {GRAFT_STOP_ARG}"

# The least count of one command. An omitted count is one graft.
GRAFT_COUNT_MIN: int = 1

# Player-facing text of the channel. The voice stays.
GRAFT_BEGIN_MESSAGE: str = "You begin to graft {name} x{count}."
GRAFT_DONE_MESSAGE: str = "Grafting complete: {grafted}/{total} {name}."
GRAFT_HALT_MESSAGE: str = "Grafting halted: {grafted}/{total} {name}. You carry no more."
GRAFT_FIGHT_MESSAGE: str = "The fight breaks off your grafting: {grafted}/{total} {name}."
GRAFT_STOP_MESSAGE: str = "You stop grafting: {grafted}/{total} {name}."
GRAFT_NOTHING_TO_STOP_MESSAGE: str = "You are not grafting anything."
GRAFT_NONE_CARRIED_MESSAGE: str = "You are not carrying any {name}."

# The Locus pop-up (popups/popup_defs/locus.py). Every sample in the game
# shows, dim when the player carries none (Nick, 11/09/2026), as a recipe
# that the player cannot make shows at the anvil.
LOCUS_POPUP_TITLE: str = "Augmentation Locus"
LOCUS_SAMPLES_TITLE: str = "Samples"
LOCUS_IDLE_STATUS: str = "Choose a sample and a count."
LOCUS_BUSY_STATUS: str = "Grafting {name} ({grafted}/{total})"
LOCUS_XP_DETAIL: str = "{xp} XP each"
LOCUS_CARRIED_INFO: str = "You carry {count}."
LOCUS_RATE_INFO: str = "{xp} XP each here, {base} XP elsewhere."
LOCUS_GRAFT_LABEL: str = "Graft"
LOCUS_GRAFT_PROMPT: str = "Graft how many?"
LOCUS_STOP_LABEL: str = "Stop grafting"


# ─── The sockets and the rig (Phase 5) ───────────────────────────────────────
# A socket is one place in the rig that holds one augment. The sockets are
# the eight parts of the body (Nick, 10/30/2026). Each augment names the
# sockets it fits. The rail shows the socketed augments only, and `aug set`
# lights them. A socket swap happens anywhere, out of combat. The Locus
# trains and the AugBot restores. Neither one configures.
SOCKET_HEAD: str = "head"
SOCKET_BODY: str = "body"
SOCKET_ARM_L: str = "left_arm"
SOCKET_ARM_R: str = "right_arm"
SOCKET_LEG_L: str = "left_leg"
SOCKET_LEG_R: str = "right_leg"
SOCKET_SKELETON: str = "skeleton"
SOCKET_NEURAL: str = "neural_code"

# The sockets in the order of the rig. The slot of a socket in the pop-up is
# its index here.
SOCKETS: tuple = (
    SOCKET_HEAD,
    SOCKET_BODY,
    SOCKET_ARM_L,
    SOCKET_ARM_R,
    SOCKET_LEG_L,
    SOCKET_LEG_R,
    SOCKET_SKELETON,
    SOCKET_NEURAL,
)

# The label of each socket, as the rig and the commands show it.
SOCKET_NAMES: dict = {
    SOCKET_HEAD: "Head",
    SOCKET_BODY: "Body",
    SOCKET_ARM_L: "Left arm",
    SOCKET_ARM_R: "Right arm",
    SOCKET_LEG_L: "Left leg",
    SOCKET_LEG_R: "Right leg",
    SOCKET_SKELETON: "Skeleton",
    SOCKET_NEURAL: "Neural code",
}

# The Augmentation level that opens each socket. Two sockets are open at
# level 0, and one more opens at each 20 levels (my placeholders, open to
# Nick). The level sets the socket count, as section 4.8 of the plan says.
SOCKET_UNLOCK_LEVELS: dict = {
    SOCKET_HEAD: 0,
    SOCKET_ARM_R: 0,
    SOCKET_ARM_L: 30,
    SOCKET_BODY: 10,
    SOCKET_SKELETON: 20,
    SOCKET_NEURAL: 40,
    SOCKET_LEG_R: 50,
    SOCKET_LEG_L: 60,
}

# The Attribute that holds the rig of a character: a dict of socket key to
# augment key. sockets.py is the one writer.
SOCKETS_ATTR: str = "sockets"

# The commands. The rig pop-up sends these lines, and a telnet player types
# them.
SOCKET_COMMAND_KEY: str = "socket"
UNSOCKET_COMMAND_KEY: str = "unsocket"
RIG_COMMAND_KEY: str = "rig"
SOCKET_TEMPLATE: str = f"{SOCKET_COMMAND_KEY} {{name}} {{socket}}"
UNSOCKET_TEMPLATE: str = f"{UNSOCKET_COMMAND_KEY} {{socket}}"

# The swap switch (11/09/2026). A plain `socket` refuses a socket that holds
# a different augment. `socket/swap` takes that socket: the held augment
# moves to the socket that the new augment left, if it fits there. Else it
# leaves the rig and goes dark (Nick, 11/09/2026). A drop on a socket in the
# rig pop-up sends this form. A telnet player can type it.
SOCKET_SWAP_SWITCH: str = "swap"
SOCKET_SWITCH_MARK: str = "/"
SOCKET_SWAP_TEMPLATE: str = (
    f"{SOCKET_COMMAND_KEY}{SOCKET_SWITCH_MARK}{SOCKET_SWAP_SWITCH} {{name}} {{socket}}")

# Player-facing text. The voice stays.
SOCKET_USAGE_MESSAGE: str = (
    "Usage: socket <augment> <socket>, or socket/swap <augment> <socket>. "
    "Sockets: {sockets}.")
SOCKET_SWAP_MOVED_MESSAGE: str = "{other} moves to your {socket}."
SOCKET_SWAP_OUT_MESSAGE: str = "{other} leaves your rig."
SOCKET_MESSAGE_JOIN: str = " "
UNSOCKET_USAGE_MESSAGE: str = "Usage: unsocket <socket>. Sockets: {sockets}."
SOCKET_UNKNOWN_MESSAGE: str = "You have no socket called '{socket}'. Sockets: {sockets}."
SOCKET_IN_COMBAT_MESSAGE: str = "You cannot change your rig in a fight."
SOCKET_LOCKED_MESSAGE: str = "Your {socket} opens at Augmentation {level}."
SOCKET_NO_FIT_MESSAGE: str = "{name} does not fit your {socket}. It fits: {fits}."
SOCKET_TAKEN_MESSAGE: str = "Your {socket} holds {other}. Unsocket it first."
SOCKET_SAME_MESSAGE: str = "{name} already sits in your {socket}."
SOCKET_DONE_MESSAGE: str = "{name} sits in your {socket} now."
UNSOCKET_EMPTY_MESSAGE: str = "Your {socket} holds nothing."
UNSOCKET_DONE_MESSAGE: str = "You take {name} out of your {socket}."
AUG_NOT_SOCKETED_MESSAGE: str = "{name} is not in your rig. Socket it first."
RIG_TITLE: str = "Rig"
RIG_STATUS: str = "{open} of {total} sockets open. Augmentation level is {level}."
RIG_LIST_TITLE: str = "|wYour rig|n"
RIG_SOCKET_LINE: str = "  |y{socket}|n: {holds}"
RIG_SOCKET_EMPTY: str = "empty"
RIG_SOCKET_LOCKED: str = "|xopens at Augmentation {level}|n"
RIG_AUGMENTS_TITLE: str = "Augments"
RIG_AUGMENT_LINE: str = "  |y{name}|n fits {fits}"
RIG_IN_SOCKET_DETAIL: str = "In: {socket}"
RIG_FITS_DETAIL: str = "Fits: {fits}"
RIG_EMPTY_DETAIL: str = "Empty"
RIG_LOCKED_DETAIL: str = "Augmentation {level}"
RIG_EMPTY_NAME: str = "{socket} (empty)"
RIG_SOCKET_ACTION_LABEL: str = "Socket: {socket}"
RIG_UNSOCKET_ACTION_LABEL: str = "Unsocket"
SOCKET_LIST_SEPARATOR: str = ", "

# The drag keys of the rig pop-up (11/09/2026). A key is the name that a drag
# of one cell carries. The client never reads it. It only looks it up in the
# drop table of the target cell. A prefix keeps a socket key and an augment
# key apart, so an augment named like a socket cannot take the wrong drop.
RIG_DRAG_SOCKET_KEY: str = "socket:{key}"
RIG_DRAG_AUGMENT_KEY: str = "augment:{key}"


# ─── The conflict groups and the modifiers (Phase 5) ─────────────────────────
# Two augments of one conflict group cannot burn at once. A light of one
# puts the other out, as an OSRS overhead prayer does. The guard augments
# share one group.
CONFLICT_GROUP_GUARD: str = "guard"

# The families of Phase 5. A guard cuts incoming damage of one type on the
# defender side. A regen augment shortens the HP regen interval. An aura
# augment widens the ring of the lit aura. A modifier changes the other
# lit augments, and nothing else.
FAMILY_GUARD: str = "guard"
FAMILY_REGEN: str = "regen"
FAMILY_AURA: str = "aura"
FAMILY_MODIFIER: str = "modifier"

# Every family. A registry test holds each augment to one of these.
AUG_FAMILIES: tuple = (
    FAMILY_ACCURACY,
    FAMILY_DAMAGE,
    FAMILY_DEFENSE,
    FAMILY_GUARD,
    FAMILY_REGEN,
    FAMILY_AURA,
    FAMILY_MODIFIER,
)

# What a modifier changes (section 4.4, "More modifiers, later"). The
# handler and the rules read the field. Overclock changes the strength.
# Mend changes the regen interval, and Reach changes the aura radius.
MODIFIES_STRENGTH: str = "strength"
MODIFIES_REGEN: str = "regen"
MODIFIES_REACH: str = "reach"

# The roll of Overclock (section 4.5). On each light, the roll is uniform
# in [low, AUG_ROLL_HIGH], and the level moves the low end up by
# AUG_ROLL_LOW_PER_LEVEL for each level. The roll is a bonus in the form of
# augment_bonus: 0.10 means +10%. A relight rerolls.
AUG_ROLL_LOW: float = 0.02
AUG_ROLL_HIGH: float = 0.15
AUG_ROLL_LOW_PER_LEVEL: float = 0.0005

# The tiles that Reach adds to the ring of the lit aura at the top power
# level. A power level gives its share, rounded, so power level k of 3 gives
# k tiles.
AUG_REACH_TILES: int = 3

# The least share of the regen interval that Mend can leave. A share of
# 0.25 is four regen ticks for each one of today.
AUG_REGEN_SHARE_FLOOR: float = 0.25

# The tip lines of the Phase 5 rows.
AUG_TIP_ROLL: str = "Rolls +{low:.0f}% to +{high:.0f}% when it comes online, and adds the roll to every lit augment."
AUG_TIP_ROLL_NOW: str = "The roll now: +{percent:.0f}%."
AUG_TIP_GUARD: str = "Cuts {percent:.1f}% from the {kind} damage you take at your level, at the top power level."
AUG_TIP_REGEN: str = "Shortens the wait between HP regen ticks by {percent:.1f}% at your level, at the top power level."
AUG_TIP_REACH: str = "Adds {tiles} tile(s) to the ring of your lit aura at the top power level."
AUG_TIP_SOCKETS: str = "Fits: {fits}."
AUG_TIP_CONFLICT: str = "Only one {group} augment burns at a time."
AUG_ROLL_NOTE: str = "+{percent:.0f}%"
