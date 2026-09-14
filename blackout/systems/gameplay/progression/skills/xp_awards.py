"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/13/2026
Description: How an XP award is told to the player, and granted. One owner.

             Every system that pays experience used to say so in its own
             words, or not at all. Combat appended "(+16 Strike, +5 Fortitude
             xp)" to the hit line; gathering said "for 25 XP" and never
             mentioned the Cutting it also taught; a recipe sent a second line
             naming the raw skill KEY; a finished cure and a quest reward paid
             silently. The award is the same fact in all five places, so it is
             now rendered in one.

             An award is a sequence of (skill_key, amount) pairs -- the shape
             combat's planner already produced. A system PLANS its award,
             appends format_xp_suffix to the line announcing what the player
             did, sends that line, and only then calls grant_xp. That order is
             what puts a level-up line under the award that caused it.

             grant_xp is also where a graphical client hears about it: every
             player-facing award passes through it, grouped the way the player
             earned it, and it publishes that group on the state feed's
             blackout_xp channel for the client's XP drops.
"""



from systems.gameplay.combat.protocols import XpEarner
from systems.interface.ui.colors import TAG_RESET, TAG_XP



# Public constant definitions

# Separator between the per-skill entries of one award.
XP_ENTRY_SEPARATOR = ", "

# The unit closing an award readout: "(+25 Butchery, +5 Cutting xp)".
XP_UNIT_LABEL = "xp"



# Private helper routines

def _positive_awards(awards) -> list:
    """
    Purpose: Drop the entries of an award that grant nothing.

    Entry:
        awards is an iterable of (skill_key, amount) pairs. May be empty.

    Exit/Returns:
        Returns a list of the pairs whose amount is above zero, in order.

    Module Globals:
        None.

    Methodology:
        Shared by the readout and the grant so the two cannot disagree about
        which entries exist: a line reading "+0 Cutting" would describe an
        award add_xp never makes.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/13/2026
    """
    kept = []

    for skill_key, amount in awards:
        if amount > 0:
            kept.append((skill_key, int(amount)))

    return kept



# Public routines

def label_awards(awards) -> list:
    """
    Purpose: Map an award's skill keys to their player-facing names.

    Entry:
        awards is an iterable of (skill_key, amount) pairs.

    Exit/Returns:
        Returns a list of (display_name, amount) pairs, zero and negative
        entries removed. A key the registry does not know is shown as itself.

    Module Globals:
        SKILL_REGISTRY read.

    Methodology:
        SKILL_REGISTRY owns skill names, so nothing here title-cases a key
        ("brain_farming" displays as the skill says, not "Brain_Farming").

        The import is deferred, and must stay so. The registry builds itself
        by importing every module under skill_defs/, and gathering_skill.py
        imports THIS module -- a module-scope import of the registry here
        would find it half-initialised on that path.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/13/2026
    """
    from systems.gameplay.progression.skills.registry import SKILL_REGISTRY

    labelled = []

    for skill_key, amount in _positive_awards(awards):
        skill_class = SKILL_REGISTRY.get(skill_key)
        display_name = getattr(skill_class, "name", skill_key)
        labelled.append((display_name, amount))

    return labelled



def format_xp_readout(awards) -> str:
    """
    Purpose: Render an award as a standalone readout.

    Entry:
        awards is an iterable of (skill_key, amount) pairs. May be empty.

    Exit/Returns:
        Returns "" when nothing is granted. Otherwise a colour-tagged
        parenthesised list with NO leading space, e.g.
        "|y(+25 Butchery, +5 Cutting xp)|n".

    Module Globals:
        XP_ENTRY_SEPARATOR, XP_UNIT_LABEL, TAG_XP and TAG_RESET read.

    Methodology:
        For an award with no single action line to ride on -- a quest reward
        paying three skills, an aura pulse that burned five targets. Anything
        that does have such a line wants format_xp_suffix instead.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/13/2026
    """
    labelled = label_awards(awards)

    if not labelled:
        return ""

    entries = [f"+{amount} {name}" for name, amount in labelled]
    joined = XP_ENTRY_SEPARATOR.join(entries)

    return f"{TAG_XP}({joined} {XP_UNIT_LABEL}){TAG_RESET}"



def format_xp_suffix(awards) -> str:
    """
    Purpose: Render an award for appending to the line that earned it.

    Entry:
        awards is an iterable of (skill_key, amount) pairs. May be empty.

    Exit/Returns:
        Returns "" when nothing is granted, so a caller appends it
        unconditionally. Otherwise format_xp_readout's text with ONE LEADING
        SPACE.

    Module Globals:
        None.

    Methodology:
        The award rides on the action's own line rather than a line of its
        own. At a 0.6s combat tick a second line per hit doubles the scroll
        rate of a fight, and a gathering log reads the same way for the same
        reason.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/13/2026
    """
    readout = format_xp_readout(awards)

    if not readout:
        return ""

    return f" {readout}"



def grant_xp(character: object, awards, kind: str) -> list:
    """
    Purpose: Pay an award into a character's skills, and tell a graphical
    client it happened.

    Entry:
        character is any object. One whose .skills is not an XpEarner -- an
        NPC, a missing handler -- is a supported no-op.
        awards is an iterable of (skill_key, amount) pairs.
        kind is the MESSAGE_TYPE of the line that announced the award, from
        systems/interface/statefeed/constants.py.

    Exit/Returns:
        Returns the (skill_key, amount) pairs actually granted.

    Module Globals:
        None.

    Methodology:
        Filters through the same _positive_awards the readout uses, so the
        line a player was shown and the XP they received are one list.
        Levelling, level-up messaging and the feed's stale marks all stay in
        SkillHandler.add_xp; this only decides what reaches it.

        The whole award is published ONCE, after every skill in it has been
        paid, so each row carries where that skill's curve now stands -- and a
        client draws "+25 Butchery +5 Cutting" as one drop, as the text line
        prints it.

        `kind` is required rather than defaulted: a default would let a new
        system publish every award it pays under a type that is not its own.

        The feed is imported inside the routine. This module is imported by
        gathering_skill.py while the skill registry is still being built, and
        the feed reaches the registry.

    Notes/References:
        Call AFTER sending the line carrying format_xp_suffix, so a level-up
        reads below the award that caused it.

    Author: Nick Hobar
    Creation date: 09/13/2026
    """
    skills = getattr(character, "skills", None)

    if not isinstance(skills, XpEarner):
        return []

    granted = _positive_awards(awards)

    for skill_key, amount in granted:
        skills.add_xp(skill_key, amount)

    if granted:
        from systems.interface.statefeed import events as feed

        feed.emit_xp_drop(character, granted, kind)

    return granted
