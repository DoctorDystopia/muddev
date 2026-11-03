"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The graft (DESIGN-0015, Phase 4): the one way to train
             Augmentation from an item. A graft consumes one unit of a
             sample and pays its `sample_xp`. On a tile that holds an
             Augmentation Locus, it pays AUG_LOCUS_XP_MULT times that. The
             bone and the gilded altar of OSRS Prayer.

             The command in commands/augment_cmds.py resolves the item and
             hands it here. This module decides what a sample is, what it
             pays, and what the quest system hears. The award goes through
             xp_awards: announced on the graft line, then granted, as every
             award is.
"""

from evennia.prototypes.prototypes import PROTOTYPE_TAG_CATEGORY
from evennia.utils import logger

from systems.gameplay.progression.skills import xp_awards
from systems.gameplay.progression.skills.constants import SKILL_KEY_AUGMENTATION
from systems.gameplay.quests import constants as quest_constants
from systems.gameplay.quests.hooks import notify_quests
from systems.interface.statefeed import constants as feed_const

from . import constants as aug_const


# Every line this module sends a player is progression, so the routing tag
# is bound one time here.
_MSG_PROGRESSION = {
    feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_PROGRESSION}


# ─── Private helper routines ─────────────────────────────────────────────────

def _consume_one(item) -> None:
    """Use up one unit of the sample. A stack decrements, and anything else
    is deleted. The rule of consumables/service._consume_one."""
    is_stackable = getattr(item, "is_stackable", False)

    if not is_stackable:
        item.delete()
        return

    item.quantity -= 1

    if item.quantity <= 0:
        item.delete()


def _publish_inventory(character) -> None:
    """Tell a graphical client that the sample is gone. obj.delete() fires
    no at_object_leave, so the pane keeps the sample without this send."""
    from systems.interface.statefeed import events as feed

    try:
        feed.emit_inventory(character)
    except Exception:
        logger.log_trace()


def _prototype_key(item) -> str:
    """The ItemDef key of an item, from the tag that spawn stamps. Empty
    for an object that no ItemDef made."""
    keys = item.tags.get(category=PROTOTYPE_TAG_CATEGORY, return_list=True) or []

    if not keys:
        return ""

    return str(keys[0])


# ─── Public routines ─────────────────────────────────────────────────────────

def is_sample(item) -> bool:
    """Whether an object is a sample: it carries SAMPLE_XP_ATTR."""
    attributes = getattr(item, "attributes", None)

    if attributes is None:
        return False

    return attributes.has(aug_const.SAMPLE_XP_ATTR)


def samples_carried(character) -> list:
    """Every sample in the contents of a character, in bag order."""
    found = []

    for item in getattr(character, "contents", []):
        if is_sample(item):
            found.append(item)

    return found


def xp_for(item, at_locus: bool) -> int:
    """
    Purpose: The Augmentation XP that a graft of one sample pays.

    Entry:
        item is a sample (is_sample is True).
        at_locus says whether a Locus stands on the tile of the grafter.

    Exit/Returns:
        Returns an int of at least 0. The Locus multiplies by
        AUG_LOCUS_XP_MULT, and the product rounds to the nearest int.

    Module Globals:
        aug_const.AUG_LOCUS_XP_MULT read.

    Methodology:
        Read the attribute off the item, never the def. A tuned def reaches
        the samples that already exist through the attribute that spawn
        stamped, and a test can stamp any value.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    base = int(item.attributes.get(aug_const.SAMPLE_XP_ATTR, default=0))

    if not at_locus:
        return max(0, base)

    boosted = round(base * aug_const.AUG_LOCUS_XP_MULT)

    return max(0, int(boosted))


def graft(character, item) -> bool:
    """
    Purpose: Consume one unit of a sample, pay its XP, and tell the quests.

    Entry:
        character is the grafter, with `location` and `contents`.
        item is an object in its contents.

    Exit/Returns:
        Returns True when the graft happened. Returns False, after one line
        to the character, when the item is no sample.

    Module Globals:
        aug_const.GRAFT_* read.

    Methodology:
        1. Refuse an item with no sample_xp.
        2. Ask the room for a Locus (typeclasses/loci.py, imported inside
           the routine because it imports this package).
        3. Read the name, the key, and the kind BEFORE the consume, because
           the consume can delete the row.
        4. Send the graft line with the XP suffix, then grant the XP.
        5. Consume one unit and send the inventory.
        6. Notify the quests two times: with the item key, and with the
           sample kind. A quest names either.

    Notes/References:
        The order "announce, then grant" is the rule of xp_awards.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    from typeclasses.loci import locus_here

    is_a_sample = is_sample(item)

    if not is_a_sample:
        character.msg((aug_const.GRAFT_NOT_A_SAMPLE_MESSAGE.format(
            name=item.get_display_name(character)), _MSG_PROGRESSION))
        return False

    locus = locus_here(character)
    at_locus = locus is not None
    name = item.get_display_name(character)
    item_key = _prototype_key(item)
    kind = item.attributes.get(aug_const.SAMPLE_KIND_ATTR, default="")
    awards = [(SKILL_KEY_AUGMENTATION, xp_for(item, at_locus))]
    template = aug_const.GRAFT_LOCUS_MESSAGE if at_locus else aug_const.GRAFT_MESSAGE
    suffix = xp_awards.format_xp_suffix(awards)

    character.msg((template.format(name=name, suffix=suffix), _MSG_PROGRESSION))
    xp_awards.grant_xp(character, awards, feed_const.MESSAGE_TYPE_PROGRESSION)

    _consume_one(item)
    _publish_inventory(character)

    if item_key:
        notify_quests(character, quest_constants.ACTION_GRAFT, item_key)

    if kind:
        notify_quests(character, quest_constants.ACTION_GRAFT, kind)

    return True
