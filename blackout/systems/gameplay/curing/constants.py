"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Single source of truth for the Curing stage's tunables, storage
             names and player-facing strings.

             Curing is the one stage of the food chain that takes TIME, so it
             is the one stage with state of its own. Everything that state is
             named by lives here, for the reason the quest package splits the
             same way: a constants module nothing imports back is the only
             thing every other module in the package can safely depend on.
"""



from systems.interface.ui import colors



# Public constant definitions

# The Curing levels at which the player gains a curing slot.
#
# A TABLE, not a branch, and not a count. Slots are "how many of these
# thresholds has the player cleared", so a third slot is one entry here and
# nothing else in the package changes -- the same shape GATHERABLE_REGISTRY
# uses to gate a yield by level.
#
# The first entry MUST be the starting level. A player at level 0 with no
# cleared threshold would have zero slots and could never cure anything, which
# is a deadlock rather than a curve.
CURING_SLOT_LEVELS: tuple = (0, 10)

# Attribute on the CHARACTER holding the in-progress cures.
#
# On the character and not on the chamber, and that is load bearing rather
# than convenient. A chamber is a map facility: systems/gameplay/spawning/
# teardown.py destroys every facility with its room on a map rebuild, and it
# does so DEPTH-FIRST, so a chamber's contents are destroyed before the
# chamber is. Meat left curing in a chamber would therefore be destroyed by
# `clean_and_reload_all_maps.ps1` -- an operator action, not an accident.
#
# The bank reached the same conclusion for the same reason: the terminal on
# the map is UI, and the vault hangs off the character
# (BankHandler._get_bank_room).
#
# Leading underscore because nothing outside CuringHandler may read it. Three
# modules owning db.active_quests is how the android came to print
# "talk:tester: 0/True" at players.
CURING_SLOTS_ATTR = "_curing_slots"

# Keys inside one stored slot dict.
#
# Slots are a LIST OF PLAIN DICTS and the dict-inside-a-list shape is not a
# style choice -- systems/gameplay/spawning/respawn.py documents why: Evennia's
# from_pickle passes a tuple itself as the saver parent, and a tuple has no
# _save_tree, so any mutable nested in a tuple raises on the first in-place
# edit. Dicts inside a list get a real _SaverList parent.
SLOT_RECIPE_KEY = "recipe"
SLOT_DUE_AT_KEY = "due_at"

# What a slot is, when asked. Machine tokens rather than display strings, in
# the ROOM_KIND_DEFAULT style, because a client branches on these and a copy
# edit to a sentence must not change a state name.
SLOT_STATE_CURING = "curing"
SLOT_STATE_READY = "ready"



# Message templates

# Every line the player reads about curing. Here rather than inline so the
# handler and the chamber's commands cannot describe the same event two ways.
MSG_CURE_STARTED = "You seal the {item} into the curing chamber."
MSG_CURE_READY = "You draw the {item} out of the chamber, cured."
MSG_NO_FREE_SLOT = (
    "Every curing slot you have is full. Collect something first."
)
MSG_NOTHING_READY = "Nothing in the chamber is ready yet."
MSG_NOTHING_CURING = "You have nothing curing."

# There is deliberately no "you gained a slot" line.
#
# logic._LEVEL_UP_SIDE_EFFECTS is the data hook it would hang on, and it is one
# dict entry -- but apply_level_up_side_effects fires ONCE after add_xp's while
# loop has applied every level it could, so a character jumping 8 -> 12 arrives
# at the hook with no record of having crossed 10. Announcing correctly needs
# the old level, which the hook does not pass, or a stored "slots last
# announced" counter, which is a second copy of a fact slots_for_level already
# owns.
#
# Nothing is lost: the level-up line names the new level, and the slot shows on
# the skills sheet as a Capacity Unlocks row (detail._capacity_rows). A constant
# here with no caller would be dead weight that looks like configuration.

# The progress line, both halves of it. Split so a slot that is still working
# and one that is done are not assembled by the same format call with a
# conditional inside it.
MSG_SLOT_WORKING = "{item} -- {remaining} remaining"
MSG_SLOT_DONE = f"{{item}} -- {colors.SUCCESS_COLOR}ready{colors.RESET_COLOR}"

# The line above those, naming how much of the chamber is spoken for.
#
# Two templates rather than one with a conditional inside the format call, the
# same split MSG_SLOT_WORKING and MSG_SLOT_DONE already make: "you have room"
# and "come back and collect" are different things to tell a player, and the
# second is the only one worth colouring.
#
# The word "Curing" is typed here and nowhere else. Every screen that shows
# this block -- the chamber's craft menu, the dossier's Processing band --
# prints lines this module built, so none of them names the stage and none of
# them can name it differently.
MSG_SLOT_HEADER = "Curing slots: {used}/{total}"
MSG_SLOT_HEADER_READY = (
    f"Curing slots: {{used}}/{{total}} -- {colors.SUCCESS_COLOR}"
    f"{{ready}} ready to collect{colors.RESET_COLOR}"
)

# How far a per-slot line sits under its header. A constant because the block
# is assembled here and handed out whole: a caller that indented for itself
# would be a second owner of how this reads, and the two screens showing it
# would drift the first time either was edited.
SLOT_LINE_INDENT = "  "

# What `collect` says when a stored slot names a recipe the game no longer
# has. The slot is freed rather than retried, and the line is deliberately not
# an apology: the player did nothing wrong and there is nothing for them to do
# about it.
#
# This is the failure mode a recipe RENAME causes. A slot stores a recipe key,
# which is the same indirection notify_quests and a QuestBlueprint's
# `craft:rusty scrap axe` already rely on, so it is consistent practice -- but
# it is still a string in a database row, and CLAUDE.md's rule about those is
# that the reader refuses an unresolvable one rather than passing it on. EvMenu
# is the cautionary tale: mod_import returns None for a path that does not
# resolve and _parse_menudata reads __dict__ off it unchecked.
MSG_RECIPE_GONE = (
    "Whatever was in this slot is no longer anything the world knows how to "
    "make. The slot is yours again."
)



# Private constant definitions

# Seconds per minute, for the remaining-time line. Named because `// 60`
# appearing twice in a formatter is the kind of literal style.md asks to be
# given a name.
_SECONDS_PER_MINUTE = 60



def slots_for_level(level: int) -> int:
    """
    Purpose: How many cures a character of this Curing level may run at once.

    Entry:
        level is a Curing skill level, 0 or greater.

    Exit/Returns:
        Returns the slot count, always 1 or more for any valid level.

    Module Globals:
        CURING_SLOT_LEVELS read.

    Methodology:
        Counts the cleared thresholds. Reading the table rather than comparing
        against two named levels is what makes a third slot one entry, and it
        is why the table is the constant rather than a MAX_SLOTS integer that
        would have to agree with a branch somewhere else.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    cleared = [
        threshold for threshold in CURING_SLOT_LEVELS if level >= threshold
    ]

    return len(cleared)



def format_remaining(seconds: float) -> str:
    """
    Purpose: Render a seconds-remaining count as a short human phrase.

    Entry:
        seconds is a float or int. A negative value is treated as zero.

    Exit/Returns:
        Returns a string like "4m 12s", or "12s" under a minute.

    Module Globals:
        _SECONDS_PER_MINUTE read.

    Methodology:
        Whole seconds, rounded UP. A cure with 0.4s left reading "0s" invites
        the player to collect something that is not ready, and being told
        "1s" once is better than being refused once.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    if seconds < 0:
        seconds = 0

    whole = int(seconds)
    if whole < seconds:
        whole = whole + 1

    minutes = whole // _SECONDS_PER_MINUTE
    rest = whole % _SECONDS_PER_MINUTE

    if minutes <= 0:
        return f"{rest}s"

    return f"{minutes}m {rest}s"
