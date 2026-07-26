from world.item_database import ItemDef

ITEMS = {
    "credits": ItemDef(
        key="credits",
        name="Credits",
        typeclass="typeclasses.items.CreditsItem",
        desc="Standard-issue Hegemony credits. The wasteland runs on these.",
        value=1,
        weight=0.0,
        tradeable=True,
        stackable=True,
        tags=[("credits", "currency")],
    ),
}
