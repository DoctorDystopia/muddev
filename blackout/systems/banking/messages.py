"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/18/2026
Description: Player-facing wording for bank transfers — the presentation half
             of systems/banking/handler.py.

Why this is a separate module
-----------------------------
BankHandler used to carry 13 ``self.obj.msg()`` calls, which made the storage
routines unusable by anything that is not a telnet session and put the display
branch and the storage branch in the same routine (``deposit`` was 69 lines).
The handler now returns a ``TransferResult`` and says nothing.

The wording lives here rather than in either caller because there are TWO:
the ``deposit`` / ``withdraw`` commands in typeclasses/bank_nodes.py and the
banking menu in systems/menus/banking_menu.py. Rendering it in both would put
the same sentence in two files, which is the duplication this refactor exists
to remove.

Colour is deliberately NOT applied here. The menu tints failures with its own
ERROR_COLOR and the commands print plain text, exactly as they did before; a
colour code baked in here would reach a Godot client as literal ``|r``.
"""

# ─── Public constant definitions ────────────────────────────────────────────

# Verbs a transfer can be described with. Passed in rather than inferred,
# because the handler is directionless by design -- deposit_many and
# withdraw_many share one routine.
VERB_DEPOSIT: str = "deposit"
VERB_WITHDRAW: str = "withdraw"

# Which way the item travelled, phrased for the tail of the sentence.
_DESTINATION_BY_VERB: dict = {
    VERB_DEPOSIT: "into the bank",
    VERB_WITHDRAW: "from the bank",
}

# A count of exactly one reads better without a multiplier: "You deposit a
# hammer into the bank", not "a hammer (x1)".
_UNIT_COUNT: int = 1


# ─── Public routines ────────────────────────────────────────────────────────

def format_quantity(item_name: str, count: int) -> str:
    """
    Purpose: Render an item name with its stack size, or without one when a
             multiplier would only add noise.

    Entry:
        item_name is the item's key.
        count is how many units are being described.

    Exit/Returns:
        Returns "name" for a single unit, "name (xN)" otherwise.

    Module Globals:
        _UNIT_COUNT read.

    Methodology:
        Matches the "(xN)" convention already used by the inventory grid and
        BaseItem.get_display_name.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    if count == _UNIT_COUNT:
        return item_name

    return f"{item_name} (x{count})"


def format_transfer(result, verb: str) -> str:
    """
    Purpose: Turn a TransferResult into the one line a player should read.

    Entry:
        result is a systems.banking.handler.TransferResult.
        verb is VERB_DEPOSIT or VERB_WITHDRAW.

    Exit/Returns:
        Returns the success sentence when anything moved, the result's error
        when nothing did, and "" when there is nothing worth saying at all
        (a result that neither moved anything nor carries a reason).

    Module Globals:
        _DESTINATION_BY_VERB read.

    Methodology:
        A partial transfer reports what DID move, not why it stopped: the
        player asked for twenty and got twelve, and "You deposit scrap (x12)"
        followed by the vault-full line is two sentences for one event. The
        caller that wants both can read result.error itself.

    Notes/References:
        Callers apply their own colour; see this module's header.

    Author: Nick Hobar
    Creation date: 08/18/2026
    """
    if not result.success:
        return result.error

    destination = _DESTINATION_BY_VERB.get(verb, "")
    described = format_quantity(result.item_name, result.moved_count)

    return f"You {verb} {described} {destination}."
