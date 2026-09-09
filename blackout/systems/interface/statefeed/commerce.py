"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/02/2026
Description: Who is standing here that you can trade with.

             One question, asked once per inventory payload rather than once
             per item: is there a shopkeeper in this room, and is there a bank
             terminal. serialize_inventory threads the answer down to
             _build_actions, which is what turns a Sell entry on or off.

             THIS MODULE COMPOSES, IT DOES NOT DECIDE. It does not know what a
             shop buys -- shop_service._is_sellable answers that, per item. It
             does not know whether a vault is full -- BankHandler answers that,
             at the moment of the transfer, with its own message. All it
             answers is "is there a counterparty here", which is a fact about
             the ROOM and is the same for every row in the payload.

             It names no typeclass. A counterparty declares itself with a
             `commerce_role` class attribute, read through getattr exactly the
             way serializers.py already reads `asset_kind` and
             `interact_verb`. That is what keeps the state feed out of the
             typeclass layer, what lets every shopkeeper already in the
             database gain the role with no migration, and what makes a future
             fence or pawnbroker one class attribute rather than an edit here.
"""

from dataclasses import dataclass

from . import constants as const


# ─── Public classes ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CommerceContext:
    """The counterparties standing in one room, or None for each absent one.

    Frozen because it is read by every row of one payload and must describe
    the same room for all of them. A builder that could mutate it mid-walk
    would be a snapshot that disagreed with itself.
    """

    shopkeep: object = None
    bank: object = None

    def offers_anything(self) -> bool:
        """Whether this room affords any commerce at all.

        Lets a caller skip the per-row work in the common case -- most rooms
        have neither -- without naming either field.
        """
        return bool(self.shopkeep or self.bank)


# ─── Private helper routines ─────────────────────────────────────────────────

def _role_of(obj) -> str:
    """Name the commerce role an object declares, or "".

    getattr rather than an import, for the reason serializers.interact_command
    gives: a class attribute is a fact about the typeclass, and reading it
    this way keeps this module out of the typeclass layer entirely.
    """
    role = getattr(obj, "commerce_role", "")

    if not role:
        return ""

    role = str(role)

    if role not in const.COMMERCE_ROLES:
        return ""

    return role


# ─── Public routines ─────────────────────────────────────────────────────────

def is_counterparty(obj) -> bool:
    """
    Purpose: Report whether an object's arrival or departure changes what a
             character in the room can do with their inventory.

    Entry:
        obj - any object. None and a half-built test object are supported.

    Exit/Returns:
        True when the object declares a commerce role.

    Module Globals:
        None.

    Methodology:
        Read by typeclasses/rooms.py, which re-publishes the inventory of
        every character in a room when a counterparty walks in or out. That
        is unnecessary for today's static spawns and is the one line that
        stops a wandering shopkeeper from becoming a bug report.

    Notes/References:
        Same predicate build_context filters on, so the thing that turns an
        action ON and the thing that re-publishes when it should are the same
        fact read twice rather than two rules that can disagree.

    Author: Nick Hobar
    Creation date: 09/02/2026
    """
    return bool(_role_of(obj))


def build_context(observer) -> CommerceContext:
    """
    Purpose: Find the counterparties in the observer's room.

    Entry:
        observer - a puppeted Character. One with no location is a supported
                   case and yields an empty context rather than raising.

    Exit/Returns:
        Returns a CommerceContext. Both fields are None when the room holds
        no counterparty, which is the common case.

    Module Globals:
        None.

    Methodology:
        ONE walk of the room's contents, for the whole payload. Asked per item
        instead, this would be a room scan for each of up to thirty-two rows,
        on the most expensive payload the feed builds.

        First of each role wins. Two shopkeepers in one room is not a case any
        current map has, and if it ever is, the labelled price must be the
        price paid -- which means this has to pick whichever one Evennia's
        cmdset merge would answer `sell` with. Room contents come back in a
        stable order, so this is at least deterministic; making it AGREE with
        the merge is work to do when a map first needs it, and a test naming
        that day is cheaper than a guess today.

        The observer is excluded from the scan, so a character who somehow
        declared a role could not trade with themself.

    Notes/References:
        The counterparty being PRESENT is all this establishes. Whether the
        shop will buy a particular item is shop_service._is_sellable, asked
        per row; whether the vault has space is BankHandler's, asked at the
        moment of transfer.

    Author: Nick Hobar
    Creation date: 09/02/2026
    """
    room = getattr(observer, "location", None)

    if room is None:
        return CommerceContext()

    shopkeep = None
    bank = None

    for obj in room.contents:
        if obj is observer:
            continue

        role = _role_of(obj)

        if role == const.COMMERCE_ROLE_SHOP and shopkeep is None:
            shopkeep = obj
        elif role == const.COMMERCE_ROLE_BANK and bank is None:
            bank = obj

        if shopkeep is not None and bank is not None:
            break

    return CommerceContext(shopkeep=shopkeep, bank=bank)
