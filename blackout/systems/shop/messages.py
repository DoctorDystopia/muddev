"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/02/2026
Description: Player-facing wording for shop trades — the presentation half of
             systems/shop/shop_service.py.

Why this is a separate module
-----------------------------
Mirrors systems/banking/messages.py, and for the same reason: there are now
TWO callers. The shopkeep dialogue in systems/menus/npc_dialogues/npc_shopkeep
.py has always rendered a completed trade, and `sell <slot>` renders the same
event from a command with no menu anywhere near it. Phrasing it in both would
put one sentence in two files, and the first copy edit would make a sale
report differently depending on which route the player took.

`execute_buy` and `execute_sell` already return BuyResult / SellResult with an
`error` string rather than messaging, precisely so a non-telnet caller could
reuse them. This is the other half of that split.

Colour is deliberately NOT applied here, the same rule banking/messages.py
states: the menu tints its own failures and the command prints plain text. A
colour code baked in here reaches a Godot client as a literal ``|r``.
"""

# ─── Public constant definitions ────────────────────────────────────────────

# Verbs a trade can be described with. Passed in rather than inferred, because
# a BuyResult and a SellResult carry the same shape and the service layer is
# directionless about which sentence describes them.
VERB_BOUGHT: str = "bought"
VERB_SOLD: str = "sold"

# Prefix for a trade that delivered nothing. The result's own `error` finishes
# the sentence -- "Insufficient credits.", "Your inventory is full." -- so the
# two halves are owned by the layer that knows each.
FAILURE_PREFIX: str = "Transaction failed"

# What a trade that moved nothing and named no reason should say. A result in
# that state is a bug rather than a refusal, and a silent one reads to the
# player as a click that did nothing.
UNKNOWN_FAILURE: str = "nothing happened."

# The shop refusing an item is not a transaction failure, so it gets its own
# line rather than the prefix above. Formatted with the item's key.
NOT_WANTED_TEMPLATE: str = "{keeper} has no interest in {item}."

# A sell request naming a quantity the player does not have. Clamping down is
# the rule parse_quantity already follows, so this exists only for zero.
NOTHING_TO_SELL: str = "You have none of that to sell."

# A bare `sell` with no argument. Phrased as a question rather than as usage,
# matching what `deposit` with no argument already asks.
NOTHING_NAMED: str = "What do you want to sell?"


# ─── Public routines ────────────────────────────────────────────────────────

def format_trade(result, verb: str, count: int) -> str:
    """
    Purpose: Turn a BuyResult or a SellResult into the one line a player
             should read.

    Entry:
        result - a shop_service.BuyResult or SellResult.
        verb   - VERB_BOUGHT or VERB_SOLD.
        count  - how many units actually changed hands. Passed rather than
                 read off the result because the two result types name it
                 differently (`bought_count` / `sold_count`), and a reader
                 picking the field by type would be a branch this module has
                 no reason to carry.

    Exit/Returns:
        Returns the success sentence when anything moved, and the prefixed
        refusal otherwise. Never returns "" -- a caller that got a result at
        all has something to tell the player.

    Module Globals:
        FAILURE_PREFIX, UNKNOWN_FAILURE read.

    Methodology:
        The price is in the sentence because the price is the whole decision,
        and the server is the only thing that knows the miser and upsell
        factors. This is also why the context-menu labels do NOT carry it:
        a label is drawn before the trade and would go stale as the stack
        drains, whereas this line describes a trade that has already
        happened and cannot be wrong.

    Notes/References:
        Callers apply their own colour; see this module's header.

    Author: Nick Hobar
    Creation date: 09/02/2026
    """
    if not result.success:
        reason = result.error or UNKNOWN_FAILURE

        return f"{FAILURE_PREFIX} — {reason}"

    return (
        f"You {verb} {count} {result.item_name} "
        f"for {result.total_price} credits."
    )


def format_not_wanted(keeper_name: str, item_name: str) -> str:
    """
    Purpose: Say that the shop will not buy a particular item.

    Entry:
        keeper_name - the shopkeeper's key.
        item_name   - the item's key.

    Exit/Returns:
        Returns the refusal sentence.

    Module Globals:
        NOT_WANTED_TEMPLATE read.

    Methodology:
        Named for the shopkeeper rather than phrased impersonally, because
        the refusal IS per shopkeeper -- `_is_sellable` is what the shop's
        own sell list is filtered by, and a second shop could answer
        differently for the same object.

    Notes/References:
        systems/statefeed/inventory.py suppresses the Sell action for an item
        this would refuse, so a graphical client never reaches this line. A
        telnet player typing `sell 7` at a worthless item does.

    Author: Nick Hobar
    Creation date: 09/02/2026
    """
    return NOT_WANTED_TEMPLATE.format(keeper=keeper_name, item=item_name)
