"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/17/2026
Description: Ammunition — does this weapon have something to fire, and what
             happens to the projectile after it leaves.

Why this is not a rules definition
----------------------------------
The nine seams in rules/rule_defs/ describe how an action RESOLVES. Spending
a projectile is not part of resolving one: it happens on a hit and on a miss
alike, after the result is known, and it changes the world rather than the
number. A seam that fired on both outcomes and returned nothing would be a
seam in name only.

It is not on the equipment handler either. That handler knows how to put a
thing in a slot and how to take it out. It has no business knowing that one
slot empties by itself.

The two rules it encodes
------------------------
1. ONE UNIT LEAVES PER SHOT, whether the shot lands or not. A miss that cost
   nothing would make accuracy free and the arrow a tax on hits only.
2. THE PROJECTILE THEN DROPS OR BREAKS, at AMMO_RECOVERY_CHANCE. A drop lands
   on the TARGET's tile, not the shooter's, and merges into a stack already
   lying there -- so a fight leaves one pile to collect instead of forty
   objects.

The trap this module is written around
--------------------------------------
CLAUDE.md, gotcha 4 and 5: build a stack detached and then move_to. A room
does not merge arriving stacks the way a character's inventory does, so the
merge here is explicit -- find_mergeable first, split only when nothing on the
tile will take the unit.
"""



import random as _random_module

from evennia.utils import logger

from items import stacking
from items.equipment.constants import WieldLocation

from . import constants as const



# ─── Private constant definitions ────────────────────────────────────────────

# The live recovery RNG. A module-level Random so a test can pass its own
# instead, the arrangement rules/context.py makes for the action RNG.
_AMMO_RNG = _random_module.Random()

# Units one shot costs. A constant rather than a literal 1 at three call
# sites, and the number a multi-shot weapon would change.
_UNITS_PER_SHOT: int = 1



# ─── Private helper routines ─────────────────────────────────────────────────

def _equipment(attacker):
    """The attacker's equipment handler, or None for an NPC that has none."""
    return getattr(attacker, "equipment", None)



def _publish_ground_stack(room, stack) -> None:
    """Re-send one ground stack's row to everyone who can see `room`.

    The arrival payload is an upsert keyed on the entity id, so re-sending it
    for an object that never moved is how a changed COUNT reaches a client.
    """
    from systems.interface.statefeed import events as feed

    try:
        feed.emit_entity_arrived(room, stack)
    except Exception:
        logger.log_trace()



def _publish_quiver(attacker) -> None:
    """Tell the shooter's own client that the quiver is one unit lighter.

    A shot writes `quantity` on an object that does not move, so not one
    inventory hook fires. Without this the pane holds the count the quiver had
    when the player equipped it, and only the shot that EMPTIES the quiver
    corrects it -- because clearing the slot goes through the equipment
    handler, which publishes. See CLAUDE.md, "Every pane follows its facts".
    """
    from systems.interface.statefeed import events as feed

    try:
        feed.emit_inventory(attacker)
    except Exception:
        logger.log_trace()



def _drop_on_tile(ammo, room) -> None:
    """Put one recovered unit on `room`'s floor, merging where it can.

    A room does NOT merge an arriving stack -- only a character's
    at_object_receive does that -- so the merge is done here. Without it a
    fight at one tile leaves one object per recovered arrow, and the player
    picks them up one at a time.

    THE MERGE BRANCH HAS TO PUBLISH ITSELF. A new stack arrives through
    move_to, and the room's at_object_receive tells every observer about it.
    A merge is an attribute write on an object that is already lying there,
    and no hook fires for that -- so the pile on the client stayed at the
    count it had when the first arrow landed.
    """
    existing = stacking.find_mergeable(room.contents, ammo)

    if existing is not None:
        stacking.add_units(existing, _UNITS_PER_SHOT)
        stacking.reduce_units(ammo, _UNITS_PER_SHOT)
        _publish_ground_stack(room, existing)

        return

    # Detached build, then move. See the module header.
    stacking.split(ammo, _UNITS_PER_SHOT, location=room)



def _clear_drained_slot(attacker, ammo) -> None:
    """Empty the AMMO slot once its last unit is gone.

    stacking.reduce_units deletes the object when it drains it, and the
    equipment slot would otherwise keep pointing at a deleted row -- which
    reads back as "ammunition equipped" to every check in this module.
    """
    if getattr(ammo, "pk", None) is not None:
        return

    equipment = _equipment(attacker)

    if equipment is None:
        return

    try:
        equipment.remove(WieldLocation.AMMO)
    except Exception:
        logger.log_trace()



# ─── Public routines ─────────────────────────────────────────────────────────

def required_family(weapon_data) -> str:
    """The ammunition family this weapon needs, or "" when it needs none.

    Every melee weapon and bare hands return "", which is what lets the
    checks below be asked of every combatant rather than of bows only.
    """
    if not weapon_data:
        return ""

    family = weapon_data.get("accepted_ammo")

    return family or ""



def equipped_ammo(attacker):
    """The object in the attacker's AMMO slot, or None."""
    equipment = _equipment(attacker)

    if equipment is None:
        return None

    ammo = equipment.slots.get(WieldLocation.AMMO)

    if ammo is None or getattr(ammo, "pk", None) is None:
        return None

    return ammo



def family_of(ammo) -> str:
    """The family an ammunition object belongs to, or "" when it names none.

    Read off the tag rather than a db attribute, because the family is what
    the item IS to the rest of the game and Evennia tags are how an item
    declares that. See world/item_defs/ammunition.py.
    """
    if ammo is None:
        return ""

    family = ammo.tags.get(category=const.AMMO_FAMILY_TAG_CATEGORY)

    if not family:
        return ""

    if isinstance(family, str):
        return family

    # Evennia returns a LIST when an object carries several tags in one
    # category. An ammunition item declares exactly one family, so a list here
    # is a content bug -- take the first and let the mismatch be visible
    # rather than raising on the tick.
    return next(iter(family), "")



def check(attacker, weapon_data) -> tuple:
    """
    Purpose: Decide whether this attacker may fire, and say why not.

    Entry:
        attacker    - the acting combatant.
        weapon_data - its combat_profile snapshot.

    Exit/Returns:
        Returns (True, "") when the shot may go ahead. Returns (False,
        reason) otherwise, where reason is a player-facing line.

        A melee weapon always returns (True, ""): it needs no ammunition, so
        it can never fail this check.

    Module Globals:
        None.

    Methodology:
        Asked at QUEUE TIME, beside the reach check, so an empty quiver is
        refused the moment the player types `attack` rather than 600ms later
        through a fight that never starts.

        Two distinct refusals, not one. "You have no arrows" and "these
        arrows do not fit that bow" send a player to two different places,
        and a single "you cannot fire" line would send them to neither.

    Notes/References:
        The families are matched by exact string. See AMMO_FAMILY_ARROW.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """
    family = required_family(weapon_data)

    if not family:
        return True, ""

    ammo = equipped_ammo(attacker)

    if ammo is None:
        return False, "You have nothing to fire."

    carried = family_of(ammo)

    if carried != family:
        return False, f"{ammo.key} does not fit that weapon."

    return True, ""



def spend(attacker, weapon_data, target, rng=None):
    """
    Purpose: Take one unit out of the attacker's quiver and settle where it
             went.

    Entry:
        attacker    - the acting combatant.
        weapon_data - its combat_profile snapshot.
        target      - the entity shot at. Its LOCATION is where a recovered
                      projectile lands.
        rng         - optional random.Random, for tests.

    Exit/Returns:
        Returns True when a unit was spent, False when there was nothing to
        spend -- which is every melee swing and is not an error.

    Module Globals:
        const.AMMO_RECOVERY_CHANCE read.
        _AMMO_RNG read.

    Methodology:
        Called on a HIT AND ON A MISS. A projectile that cost nothing when it
        missed would make accuracy free, and an arrow a tax paid only by a
        player who was already winning.

        The recovery roll is separate from the accuracy roll and separate
        from the damage roll. It uses this module's RNG rather than the
        action's, because the action's draw ORDER is what keeps the pipeline
        byte-equivalent to combat_calc -- a third draw wedged into that
        sequence would break every seeded test in rules/tests/.

        It lands on the TARGET's tile, which is the whole reason recovery is
        a mechanic and not a refund: the player has to walk over and pick it
        up, in the place the fight just happened.

    Notes/References:
        Never raises. This runs inside ActionAttack.resolve, on the tick, and
        a quiver bug must not be able to cancel a fight.

        It publishes its own two changes, because neither one moves an object
        and no hook fires for either: the quiver to the shooter, and the pile
        on the ground to everyone who can see the tile.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """
    family = required_family(weapon_data)

    if not family:
        return False

    ammo = equipped_ammo(attacker)

    if ammo is None:
        return False

    source = rng if rng is not None else _AMMO_RNG
    room = getattr(target, "location", None)
    recovered = source.random() < const.AMMO_RECOVERY_CHANCE

    try:
        if recovered and room is not None:
            _drop_on_tile(ammo, room)
        else:
            stacking.reduce_units(ammo, _UNITS_PER_SHOT)

        _clear_drained_slot(attacker, ammo)
        _publish_quiver(attacker)
    except Exception:
        logger.log_trace()

        return False

    return True
