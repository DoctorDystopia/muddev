"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/01/2026
Description: Paced multi-craft batches ("craft X" / "craft all"). Layers a
             real-time, interruptible loop on top of crafting_service's
             single-craft execution and the cooldown handler contrib.
"""



from evennia.utils import logger
from evennia.utils.utils import delay

from . import crafting_service
from .constants import CRAFTING_BUSY_COOLDOWN_KEY
from systems.statefeed import constants as feed_const

# Every line this module sends a player is crafting, so the routing tag is
# bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/statefeed/constants.py.
_MSG_CRAFTING = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_CRAFTING}



# Public constant definitions

# db attribute holding the active batch's state, or absent if none is
# running. A db (not ndb) Attribute so a batch resumes correctly even though
# its own pacing timer is non-persistent -- see start_batch's docstring.
BATCH_ATTRIBUTE = "craft_batch"



def _object_by_id(obj_id):
    """Resolve a dbid to a live Evennia Object, or None if it is gone.

    Deferred import: this module can be pulled in before the app registry is
    ready. Mirrors systems/combat/combat.py's _object_by_id.
    """
    if obj_id is None:
        return None

    from evennia.objects.models import ObjectDB

    try:
        return ObjectDB.objects.get(id=obj_id)
    except ObjectDB.DoesNotExist:
        return None


def is_batch_active(caller) -> bool:
    """Return True if caller currently has a craft batch in progress."""
    return bool(caller.attributes.get(BATCH_ATTRIBUTE))


def get_active_batch(caller) -> dict | None:
    """Return caller's active batch state dict, or None if there isn't one."""
    return caller.attributes.get(BATCH_ATTRIBUTE)


def cancel_batch(caller) -> bool:
    """Stop caller's active batch, if any.

    Returns:
        bool: True if a batch was actually cancelled, False if none was
        running. Does not craft a partial item or refund anything -- items
        already produced by prior steps stay produced.
    """
    if not is_batch_active(caller):
        return False

    caller.attributes.remove(BATCH_ATTRIBUTE)

    return True


def start_batch(caller, recipe_key, count):
    """
    Purpose: Begin a paced multi-craft batch of `count` copies of recipe_key.

    Entry:
        caller is a Character with a .cooldowns handler.
        recipe_key names a registered recipe.
        count is the requested batch size, an int >= 1.

    Exit/Returns:
        Returns (started: bool, message: str). message is always safe to
        show the caller directly.

    Module Globals:
        BATCH_ATTRIBUTE read/written.
        CRAFTING_BUSY_COOLDOWN_KEY read.

    Methodology:
        Refuses to start over an already-running batch or while the busy
        cooldown from a just-finished one is still ticking down -- two
        separate guards because the batch Attribute clears the instant the
        last item completes, slightly before its cooldown expires. Clamps
        the requested count down to what materials/tools/skill actually
        allow, then crafts the first item synchronously (matching "craft 1"
        completing instantly) before handing subsequent items to the paced
        loop in _craft_one/_continue_batch.

    Notes/References:
        The pacing timer (evennia.utils.delay, persistent=True) survives a
        server reload by re-resolving caller from its dbid rather than
        closing over the live object -- see _continue_batch. The batch
        Attribute itself does not need to be persistent for that reason; it
        already is one because caller.attributes.add always persists.

    Author: Nick Hobar
    Creation date: 08/01/2026
    """
    if is_batch_active(caller):
        active = get_active_batch(caller)
        message = (
            f"You are already crafting {active['recipe_name']} "
            f"({active['crafted']}/{active['total']})."
        )
        return False, message

    if not caller.cooldowns.ready(CRAFTING_BUSY_COOLDOWN_KEY):
        return False, "You are still finishing up your last craft."

    recipe_cls = crafting_service.get_recipe_class(recipe_key)
    if not recipe_cls:
        return False, "Recipe not found."

    can_craft, reasons = crafting_service.check_craftable(caller, recipe_key)
    if not can_craft:
        return False, f"Cannot craft: {'; '.join(reasons)}."

    max_craftable = crafting_service.get_max_craftable(caller, recipe_key)
    count = max(1, min(count, max_craftable))

    caller.attributes.add(
        BATCH_ATTRIBUTE,
        {
            "recipe_key": recipe_key,
            "recipe_name": recipe_cls.name,
            "total": count,
            "remaining": count,
            "crafted": 0,
        },
    )

    _craft_one(caller, recipe_key)

    message = f"You begin crafting {recipe_cls.name} x{count}."
    if count > 1:
        message += f" ({recipe_cls.craft_seconds:.1f}s per item.)"

    return True, message


def _craft_one(caller, recipe_key) -> None:
    """Craft a single item toward the active batch, then either schedule the
    next one or close the batch out.

    Silently returns without crafting if the batch was cancelled or
    superseded (its Attribute is gone, or now names a different recipe) --
    that is how cancel_batch stops an in-flight loop.
    """
    batch = caller.attributes.get(BATCH_ATTRIBUTE)
    if not batch or batch.get("recipe_key") != recipe_key:
        return

    recipe_cls = crafting_service.get_recipe_class(recipe_key)
    if not recipe_cls:
        caller.attributes.remove(BATCH_ATTRIBUTE)
        return

    can_craft, reasons = crafting_service.check_craftable(caller, recipe_key)
    if not can_craft:
        caller.msg(
            (f"Crafting halted: {batch['crafted']}/{batch['total']} "
            f"{recipe_cls.name} ({'; '.join(reasons)}).", _MSG_CRAFTING)
        )
        caller.attributes.remove(BATCH_ATTRIBUTE)
        return

    crafting_service.perform_craft(caller, recipe_key)
    caller.cooldowns.add(CRAFTING_BUSY_COOLDOWN_KEY, recipe_cls.craft_seconds)

    batch["crafted"] += 1
    batch["remaining"] -= 1

    if batch["remaining"] <= 0:
        caller.msg(
            (f"Crafting complete: {batch['crafted']}/{batch['total']} "
            f"{recipe_cls.name}.", _MSG_CRAFTING)
        )
        caller.attributes.remove(BATCH_ATTRIBUTE)
        return

    caller.attributes.add(BATCH_ATTRIBUTE, batch)
    delay(recipe_cls.craft_seconds, _continue_batch, caller.id, recipe_key, persistent=True)


def _continue_batch(caller_id, recipe_key) -> None:
    """Delayed callback re-entry point. Re-resolves caller by dbid rather
    than closing over the live object so a persistent delay across a reload
    still finds the right character."""
    caller = _object_by_id(caller_id)

    if caller is None:
        return

    try:
        _craft_one(caller, recipe_key)
    except Exception:
        logger.log_trace()
        caller.attributes.remove(BATCH_ATTRIBUTE)
