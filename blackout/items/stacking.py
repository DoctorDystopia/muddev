"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/18/2026
Description: One owner for stackable-item semantics — what may merge with
             what, how a merge is performed, and how a stack is split safely.

Why this module exists
----------------------
Three modules independently derived "same key + both stackable => mergeable"
and "quantity += then delete()":

  * items/inventory/handler.py   -- _find_existing_stack / add_item
  * systems/banking/handler.py   -- _find_existing_stack_in_bank / _split_stack
  * systems/loot/drops.py        -- _merge_stackable_pairs

They did not agree. Inventory compared keys case-SENSITIVELY
(``existing.key == obj.key``) while banking compared them case-insensitively
(``obj.key.lower() == item_key.lower()``), so the same two objects could merge
in a vault and refuse to merge in a backpack. Item keys come from ITEM_DB and
are canonical in practice, which is the only reason that never surfaced as a
bug — it was latent, not absent.

This is the one duplication in the codebase that can LOSE PLAYER ITEMS, so it
gets a single owner. Case-insensitive comparison wins: it is the more
conservative rule, in that it can only ever merge two objects that would
otherwise have occupied two slots.

Scope
-----
This module owns LIVE-OBJECT semantics. ``loot/drops._merge_stackable_pairs``
is deliberately NOT ported onto it: that function merges ``(item_key, quantity)``
pairs BEFORE anything is spawned, and answers stackability from ITEM_DB rather
than from an object. It is the same idea one abstraction level down, and
folding it in here would mean this module importing the item database.

The split rule
--------------
``detached_copy`` builds at ``location=None`` and only moves once the object is
complete. That ordering is load-bearing and is CLAUDE.md gotcha 4: creating the
copy directly at its destination fires ``at_object_receive``, whose stack-merge
calls ``delete()`` on the incoming object, and the next attribute write then
fails with "needs to have a value for field id". Evennia's own
``DefaultObject.copy()`` / ``copy_object()`` hit the same wall for the same
reason, which is why this stays hand-rolled.
"""

from evennia import create_object

# ─── Public constant definitions ────────────────────────────────────────────

# What a non-stackable object counts as when tallying units. A sword is one
# sword; only a stackable carries a meaningful `quantity`.
SINGLE_UNIT: int = 1

# The quantity at or below which a drained stack is deleted rather than left
# behind as an empty object.
EMPTY_STACK_QUANTITY: int = 0


# ─── Private helper routines ────────────────────────────────────────────────

def _normalized_key(obj) -> str:
    """
    Purpose: Reduce an object's key to the form stack matching compares on.

    Entry:
        obj is an Evennia Object, or None.

    Exit/Returns:
        Returns the lower-cased key, or an empty string when obj is None or
        carries no key. An empty string never matches another empty string
        for merge purposes -- is_mergeable rejects None operands before it
        ever gets here -- so the empty return is a safe floor rather than a
        wildcard.

    Module Globals:
        None

    Methodology:
        Lower-casing is the whole rule. It lives in its own routine so the two
        comparison sites cannot drift apart the way the inventory and banking
        handlers did.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    if obj is None:
        return ""

    key = getattr(obj, "key", None)

    if key is None:
        return ""

    normalized = key.lower()

    return normalized


# ─── Public routines ────────────────────────────────────────────────────────

def is_stackable(obj) -> bool:
    """
    Purpose: Report whether an object carries stack semantics at all.

    Entry:
        obj is an Evennia Object, or None.

    Exit/Returns:
        Returns True only for an object whose `is_stackable` property is
        truthy. None and objects lacking the property both return False.

    Module Globals:
        None

    Methodology:
        A getattr probe rather than an isinstance check, because ground items,
        bank contents and inventory contents are all typed loosely at these
        call sites and a non-item Object may legitimately appear in any of
        them.

    Notes/References:
        typeclasses/items.py BaseItem.is_stackable is the property this reads.

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    stackable = getattr(obj, "is_stackable", False)

    return bool(stackable)


def quantity_of(obj) -> int:
    """
    Purpose: Report how many units an object represents.

    Entry:
        obj is an Evennia Object, or None.

    Exit/Returns:
        Returns the object's `quantity` for a stack, SINGLE_UNIT for a
        non-stackable or for an object with no quantity at all, and
        EMPTY_STACK_QUANTITY for None.

    Module Globals:
        SINGLE_UNIT read.
        EMPTY_STACK_QUANTITY read.

    Methodology:
        BaseItem.quantity already returns 1 for a non-stackable, but the
        getattr default is kept so this is safe on objects that are not
        BaseItem -- which the bank room and a room's ground contents can
        both hold.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    if obj is None:
        return EMPTY_STACK_QUANTITY

    quantity = getattr(obj, "quantity", SINGLE_UNIT)

    return quantity


def is_mergeable(first, second) -> bool:
    """
    Purpose: Answer the one question every stacking site used to answer for
             itself -- may these two objects become one object?

    Entry:
        first and second are Evennia Objects, or None.

    Exit/Returns:
        Returns True only when both are present, are DIFFERENT database rows,
        are both stackable, and share a key ignoring case.

    Module Globals:
        None

    Methodology:
        The distinct-row test is not cosmetic. InventoryHandler.add_item
        guarded `existing.id != obj.id` precisely because merging an object
        into itself doubles its quantity and then deletes it -- the item is
        destroyed and the player is told nothing.

    Notes/References:
        See the module header for why key comparison is case-insensitive.

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    if first is None or second is None:
        return False

    first_id = getattr(first, "id", None)
    second_id = getattr(second, "id", None)

    if first_id is not None and first_id == second_id:
        return False

    first_stacks = is_stackable(first)
    second_stacks = is_stackable(second)

    if not first_stacks or not second_stacks:
        return False

    first_key = _normalized_key(first)
    second_key = _normalized_key(second)

    return first_key == second_key


def find_mergeable(candidates, obj):
    """
    Purpose: Find the first object in `candidates` that `obj` may merge into.

    Entry:
        candidates is any iterable of Evennia Objects; None entries are
        tolerated and skipped.
        obj is the incoming Evennia Object, or None.

    Exit/Returns:
        Returns the matching candidate, or None when nothing matches. Does
        not mutate either operand.

    Module Globals:
        None

    Methodology:
        First-match rather than best-match. Two stacks of the same key should
        not coexist -- add_item merges on the way in -- so "first" and "best"
        are the same object whenever the invariant holds, and picking the
        first keeps the result stable when it does not.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    if obj is None:
        return None

    for candidate in candidates:
        mergeable = is_mergeable(candidate, obj)

        if mergeable:
            return candidate

    return None


def available_units(items) -> int:
    """
    Purpose: Total the units held across a run of interchangeable objects.

    Entry:
        items is any iterable of Evennia Objects; None entries are skipped.

    Exit/Returns:
        Returns the summed quantity, counting a non-stackable as SINGLE_UNIT.

    Module Globals:
        None

    Methodology:
        Exists because deposit_many / withdraw_many both need "how much is
        there in total" before they start moving anything, and a stack
        contributes its whole quantity while eleven separate scrap plates
        contribute one each.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    total = 0

    for item in items:
        units = quantity_of(item)
        total += units

    return total


def add_units(stack, count: int) -> int:
    """
    Purpose: Grow a stack by `count` units without involving a second object.

    Entry:
        stack is a stackable Evennia Object.
        count is a non-negative integer.

    Exit/Returns:
        Returns the stack's new quantity. Returns the unchanged quantity when
        stack is None or count is not positive.

    Module Globals:
        EMPTY_STACK_QUANTITY read.

    Methodology:
        The half of a merge that does not consume a source object. The bank's
        partial-deposit path needs exactly this: units leave the carried stack
        and land in an already-present vault stack, with no third object ever
        created.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    if stack is None:
        return EMPTY_STACK_QUANTITY

    current = quantity_of(stack)

    if count <= 0:
        return current

    updated = current + count
    stack.quantity = updated

    return updated


def reduce_units(item, count: int) -> bool:
    """
    Purpose: Draw `count` units out of an object, deleting it once drained.

    Entry:
        item is an Evennia Object.
        count is a non-negative integer.

    Exit/Returns:
        Returns True when the object was deleted because nothing was left of
        it, False when it survived with a reduced quantity. Returns False for
        a None item or a non-positive count.

    Module Globals:
        EMPTY_STACK_QUANTITY read.

    Methodology:
        Deleting at zero is the rule that must not be forgotten, which is why
        it lives with the subtraction rather than beside it. The banking
        handler open-coded `item.quantity -= n` followed by an `if <= 0`
        delete in two places and omitted the delete in a third.

    Notes/References:
        A non-stackable ignores quantity assignment (BaseItem.quantity's
        setter returns early), so it is deleted outright rather than
        silently surviving a subtraction that did nothing.

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    if item is None or count <= 0:
        return False

    stackable = is_stackable(item)

    if not stackable:
        item.delete()
        return True

    current = quantity_of(item)
    remaining = current - count

    if remaining <= EMPTY_STACK_QUANTITY:
        item.delete()
        return True

    item.quantity = remaining

    return False


def merge(into, source) -> int:
    """
    Purpose: Fold `source` entirely into `into` and destroy the emptied source.

    Entry:
        into and source must satisfy is_mergeable(into, source). Callers that
        have not already checked should call it first; this routine re-checks
        and refuses rather than corrupting either object.

    Exit/Returns:
        Returns the combined quantity now held by `into`, or that object's
        unchanged quantity when the merge was refused.

    Module Globals:
        None

    Methodology:
        Read the source's units, add them, then delete the source. The order
        matters -- reading after deletion returns a value off a dead row.

    Notes/References:
        The self-merge case (into is source) is refused by is_mergeable; see
        its docstring for why that would destroy the item.

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    mergeable = is_mergeable(into, source)

    if not mergeable:
        current = quantity_of(into)
        return current

    incoming = quantity_of(source)
    combined = add_units(into, incoming)

    source.delete()

    return combined


def detached_copy(item, count: int):
    """
    Purpose: Build a fully-populated duplicate of `item` holding `count` units,
             parked at location=None.

    Entry:
        item is a live Evennia Object with a typeclass_path.
        count is a positive integer.

    Exit/Returns:
        Returns the new Object. It has NO location -- the caller is
        responsible for moving it, and `split` is the routine that does so.
        The source object is NOT modified.

    Module Globals:
        None

    Methodology:
        Create detached, copy every attribute across, stamp the quantity last
        so it wins over the copied one, and hand the object back unplaced.

    Notes/References:
        CLAUDE.md gotcha 4. Building at the destination instead fires
        at_object_receive, whose stack merge deletes the incoming object
        mid-construction; the following attribute write then raises "needs to
        have a value for field id". This is also why Evennia's own
        copy_object() cannot be used here -- it batch-adds attributes after
        placing the object.

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    new_obj = create_object(
        item.typeclass_path,
        key=item.key,
        location=None,
    )

    for attr in item.attributes.all():
        new_obj.attributes.add(attr.key, attr.value, category=attr.category)

    new_obj.attributes.add("quantity", count)

    return new_obj


def split(item, count: int, location=None):
    """
    Purpose: Take `count` units off `item` as a separate object placed at
             `location`, reducing the source by the same amount.

    Entry:
        item is a live Evennia Object.
        count is a positive integer no greater than the item's quantity.
        location is the destination Object/Room, or None to leave the new
        stack detached.

    Exit/Returns:
        Returns the new Object holding `count` units. The source has been
        reduced by `count`, and deleted if that emptied it. Returns None when
        count is not positive.

    Module Globals:
        None

    Methodology:
        Copy detached, move, then reduce the source. Reducing LAST matters:
        detached_copy reads the source's attributes, so draining it first
        would copy a quantity that has already been decremented, and
        deleting it first would leave nothing to copy from at all.

    Notes/References:
        The move happens before the reduction, so a destination whose
        at_object_receive merges the arriving stack sees a complete object.
        That merge may delete the returned object -- callers that need the
        surviving stack should re-resolve it rather than trusting the handle
        past this point.

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    if count <= 0:
        return None

    new_obj = detached_copy(item, count)

    if location is not None:
        new_obj.move_to(location, quiet=True)

    reduce_units(item, count)

    return new_obj
