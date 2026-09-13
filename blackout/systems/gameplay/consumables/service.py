"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Eating — the one stage of the food chain that is a mechanic.

Where the two delays live, and why they live apart
--------------------------------------------------
Eating imposes two delays and they belong to different owners, because only one
of them is about combat:

  * the EAT delay gates the next bite, and must work standing in an empty room.
    It is a tick number in ndb on the character, compared against
    ``BlackoutTickEngine.current_tick()``. Nothing counts it down -- readiness
    is a comparison, the same shape ``CuringHandler`` uses for a deadline and
    the cooldown contrib uses for an expiry.

  * the ATTACK delay gates the next swing, which is meaningless outside a fight.
    It is added to ``ndb.cooldown_ticks`` on the combat handler, the counter
    ``BlackoutCombatHandler.tick`` already decrements before it will act.

A consequence worth naming: a player who eats with no combat handler loses the
attack delay entirely, so eating and THEN opening combat swings immediately.
Harmless while combat is PvE -- the alternative is stamping a delay onto a
handler that does not exist yet, which means either creating one for a player
who is not fighting or persisting a second counter for the rare case.

What this module does not decide
--------------------------------
How much a food heals, how long its delays are, and whether a thing is food at
all are ALL the ItemDef's. This module reads ``heal_amount`` and never tests a
tag, a typeclass or a key -- which is what makes a new food one dict entry. A
family tag is a LOOK, not a rule, exactly as it is for weapons: an item tagged
``food`` with no heal_amount renders as food and cannot be eaten.
"""



from evennia.utils import logger

from . import constants as consumable_const



def heal_amount_of(item) -> int | None:
    """
    Purpose: How much the given object heals, or None if it is not food.

    Entry:
        item is any object, or None.

    Exit/Returns:
        Returns a positive int, or None when the object is not edible.

    Module Globals:
        None.

    Methodology:
        Read through `attributes.get` so this is safe on anything -- most
        objects in the game carry no heal_amount and every failed `eat`
        lands here first, the same way get_gatherable_for_node tolerates
        being asked about a rock.

        A non-positive value is treated as NOT FOOD rather than as food that
        heals nothing. Zero is what an author writes by accident; a food that
        is meant to do nothing has no reason to exist.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    attributes = getattr(item, "attributes", None)

    if attributes is None:
        return None

    amount = attributes.get("heal_amount", default=None)

    if not isinstance(amount, int) or amount <= 0:
        return None

    return amount



def is_edible(item) -> bool:
    """Whether the given object can be eaten at all."""
    amount = heal_amount_of(item)

    return amount is not None



def _delay_of(item, attr_name: str, fallback: int) -> int:
    """One tick-delay field off a food, falling back to the standard.

    The fallback matters for an object spawned before the field existed: a
    cured chuck already in somebody's bag carries heal_amount and no delay,
    and the right answer for it is ordinary food rather than zero.
    """
    attributes = getattr(item, "attributes", None)

    if attributes is None:
        return fallback

    value = attributes.get(attr_name, default=None)

    if not isinstance(value, int) or value < 0:
        return fallback

    return value



def ticks_until_can_eat(character) -> int:
    """
    Purpose: How many ticks before this character may eat again.

    Entry:
        character is a Character.

    Exit/Returns:
        Returns 0 when they may eat now, otherwise the remaining tick count.

    Module Globals:
        consumable_const read.

    Methodology:
        A comparison against the engine's tick counter, with no stored
        countdown to advance and nothing registered on the tick. The stored
        value is the tick the next bite is ALLOWED on, which is why a reload --
        which resets both the counter and ndb together -- leaves a consistent
        pair rather than a stale deadline.

    Notes/References:
        systems/core/tick/engine.py current_tick() documents the reset.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    allowed_at = getattr(
        character.ndb, consumable_const.NEXT_EAT_TICK_ATTR, None
    )

    if not allowed_at:
        return 0

    now = _current_tick()
    remaining = allowed_at - now

    if remaining <= 0:
        return 0

    return remaining



def _current_tick() -> int:
    """The engine's notion of now, or 0 when there is no engine.

    Imported inside the function: the engine pulls in the tickable registry and
    the scheduler, and this module is reached from a command on the character's
    cmdset. Falling back to 0 rather than raising means a test or a script with
    no tick running can still eat -- with every delay effectively expired,
    which is the right degradation for a mechanic whose delays are 1.8 seconds.
    """
    from systems.core.tick.engine import get_tick_engine

    try:
        engine = get_tick_engine()
        return engine.current_tick()
    except Exception:
        logger.log_trace()
        return 0



def _arm_eat_delay(character, delay_ticks: int) -> None:
    """Record the tick this character may next eat on.

    Takes the resolved tick count rather than the food, because by the time
    this runs the food has been eaten -- see eat() on why the delays are read
    first.
    """
    allowed_at = _current_tick() + delay_ticks

    setattr(character.ndb, consumable_const.NEXT_EAT_TICK_ATTR, allowed_at)



def _charge_attack_delay(character, delay_ticks: int) -> None:
    """Push back the eater's next swing, if they are in a fight.

    Reads the combat handler off the character rather than creating one. A
    player who is not fighting has nothing to delay, and spinning up a combat
    handler to hold a 1.2s number would put a script on every character who
    ever ate anything.

    The delay is MAXED with whatever cooldown is already standing, never added
    to it and never replacing it: a combatant who eats halfway through a
    speed-6 weapon's recovery should not have their swing brought forward, and
    one who eats twice should not compound the penalty beyond a single food's
    worth. Assignment alone would do the former, addition the latter.
    """
    handler = getattr(character, "combat", None)

    if handler is None:
        return

    # `combat` is a lazy_property returning None when no handler is attached,
    # so the None check above is the real gate. is_active is read as well
    # because a handler row can outlive the fight it was created for.
    is_fighting = getattr(handler, "is_active", False)
    if not is_fighting:
        return

    try:
        standing = handler.ndb.cooldown_ticks or 0
        handler.ndb.cooldown_ticks = max(standing, delay_ticks)
    except Exception:
        logger.log_trace()



def eat(character, item) -> bool:
    """
    Purpose: Eat one food, heal for it, and pay both delays.

    Entry:
        character is a Character. item is an object they are carrying.

    Exit/Returns:
        Returns True when the food was eaten. Returns False, having messaged
        the character, when the item is not food or the eat delay has not
        expired.

    Module Globals:
        consumable_const read.

    Methodology:
        Order is the whole routine, and it is load bearing in two places.
        Both refusals come FIRST and cost nothing, so a misclick is free. And
        the food's DELAYS are read before it is consumed, because consuming a
        non-stackable deletes the row the delays live on.

        Eating at full health is ALLOWED and wastes the food, which is OSRS's
        behaviour and keeps one rule doing the work: healing is capped at max
        HP, and a cap is not a refusal. The player is told it did nothing.

    Notes/References:
        CombatEntity's `hp` setter owns the cap and the state-feed publish, so
        _apply_heal goes through it rather than writing db.hp.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    amount = heal_amount_of(item)

    if amount is None:
        refusal = consumable_const.MSG_NOT_EDIBLE.format(item=item.key)
        character.msg(refusal)
        return False

    if ticks_until_can_eat(character) > 0:
        character.msg(consumable_const.MSG_TOO_SOON)
        return False

    # Read everything off the food BEFORE it is destroyed. _consume_one
    # deletes a non-stackable outright, and attributes.get on a deleted row
    # returns None -- so reading the delays afterwards silently gave every food
    # the STANDARD pair and quietly threw away the cured meats' faster swing.
    # Nothing raised, and the eat delay's fallback happened to equal its real
    # value, which is what made the bug invisible from the outside.
    item_name = item.key
    eat_delay = _delay_of(
        item,
        "eat_delay_ticks",
        consumable_const.STANDARD_EAT_DELAY_TICKS,
    )
    attack_delay = _delay_of(
        item,
        "attack_delay_ticks",
        consumable_const.STANDARD_ATTACK_DELAY_TICKS,
    )

    healed = _apply_heal(character, amount)

    _consume_one(item)
    _arm_eat_delay(character, eat_delay)
    _charge_attack_delay(character, attack_delay)

    _report(character, item_name, healed)
    _publish_inventory(character)

    return True



def _apply_heal(character, amount: int) -> int:
    """Restore hit points, capped, and report how many actually landed.

    The difference between requested and delivered is what tells the player
    their prime sandwich was wasted, so it is measured rather than assumed.

    Written through the `hp` SETTER rather than to db.hp, and that is where the
    overheal rule actually lives: the setter clamps to max_hp and emits the
    vitals the client's HP bar redraws from. Assigning db.hp directly would heal
    past the cap and leave the bar stale -- CombatEntity's own comment about a
    Fortitude level-up raising the cap makes the same point from the other side.
    """
    before = character.hp
    character.hp = before + amount
    after = character.hp

    healed = after - before

    if healed < 0:
        return 0

    return healed



def _consume_one(item) -> None:
    """Use up one unit of the food, deleting the object when it runs out.

    Stackables decrement; everything else is deleted. The same two-branch rule
    BlackoutRecipe._consume_inputs follows, because a stack of food is a real
    inventory and eating one must not bin the other nine.
    """
    is_stackable = getattr(item, "is_stackable", False)

    if not is_stackable:
        item.delete()
        return

    item.quantity -= 1

    if item.quantity <= 0:
        item.delete()



def _report(character, item_name: str, healed: int) -> None:
    """Tell the player what happened, in one or two lines.

    Two messages rather than one sentence with a conditional inside it: eating
    and being healed are separate facts, and at full health the second is
    replaced rather than omitted -- a player who just destroyed a prime
    sandwich should be told so plainly.
    """
    character.msg(consumable_const.MSG_EATEN.format(item=item_name))

    if healed > 0:
        character.msg(
            consumable_const.MSG_HEALED.format(item=item_name, healed=healed)
        )
        return

    character.msg(consumable_const.MSG_NO_EFFECT.format(item=item_name))



def _publish_inventory(character) -> None:
    """Tell a graphical client the food is gone.

    Imported inside the function, copying BankHandler and CuringHandler for the
    reason they both give: this module is reached from a character cmdset and a
    module-scope import of the feed would couple the two systems' import order.

    obj.delete() does not fire at_object_leave, so without this the pane keeps
    drawing a sandwich the player has already eaten.
    """
    from systems.interface.statefeed import events as feed

    try:
        feed.emit_inventory(character)
    except Exception:
        logger.log_trace()
