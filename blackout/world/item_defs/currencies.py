"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: ItemDef entries for currency items.
"""

from world.item_database import ItemDef

ITEMS = {
    "credits": ItemDef(
        key="credits",
        name="credits",
        typeclass="typeclasses.items.CreditsItem",
        desc="Standard-issue Hegemony credits. The wasteland runs on these.",
        value=1,
        weight=0.0,
        tradeable=True,
        stackable=True,
        tags=[("credits", "currency")],
    ),
}
