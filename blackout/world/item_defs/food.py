"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: ItemDef entries for food -- the cured meats Curing produces.

             These are the first items in the game whose POINT is to be
             eaten. Nothing eats anything yet: there is no `eat` command and no
             consumable hook, and the spreadsheet's "eat to heal HP" column is
             a promise about a stage that is not built. So every entry here is
             tagged `crafting_material` and nothing else, which is exactly what
             Gastronomy needs to find them -- the sandwich consumes a cured
             chuck and a cured fatless meat.

             When `eat` lands it brings a food FAMILY with it, and that is a
             statefeed constant plus a regenerated blackout_constants.gd rather
             than an edit here. Until then a cured chuck renders as a material,
             which is honest: it is currently an ingredient that happens to be
             meat.

             A separate module from materials.py on purpose. `cured` is not a
             processing state of the metal chain and the two dicts have nothing
             to say to each other; world/item_database.py discovers modules in
             this package, so a new file is the whole cost of the split.
"""



from world.item_database import ItemDef



ITEMS = {
    # ─── Cured mutant raider meats (Curing) ───────────────────────────────
    # Two per tier, and the pairs are deliberately not interchangeable:
    # Gastronomy's sandwich needs ONE OF EACH, so a chuck cured straight and a
    # chuck rendered-then-cured have to be two different items. The
    # spreadsheet's note on the cured chuck row says they share an output; the
    # Outputs column says they do not, and the sandwich's two inputs settle it.
    #
    # Non-stackable, all four. Food that stacks is food a player cannot tell
    # apart, and the moment `eat` exists the difference between these is how
    # much they heal.
    "mutant_raider_cured_chuck": ItemDef(
        key="mutant_raider_cured_chuck",
        name="mutant raider cured chuck",
        desc="A slab of chuck gone dark and firm, crusted white with salt.",
        value=14,
        weight=1.2,
        tradeable=True,
        stackable=False,
        tags=[("mutant_raider_cured_chuck", "crafting_material")],
    ),
    "mutant_raider_cured_fatless_meat": ItemDef(
        key="mutant_raider_cured_fatless_meat",
        name="mutant raider cured fatless meat",
        desc="Lean meat rendered dry and then cured drier. It could outlast you.",
        value=22,
        weight=0.9,
        tradeable=True,
        stackable=False,
        tags=[("mutant_raider_cured_fatless_meat", "crafting_material")],
    ),
    "mutant_raider_cured_filet": ItemDef(
        key="mutant_raider_cured_filet",
        name="mutant raider cured filet",
        desc="A whole filet cured through without splitting. Patient work.",
        value=40,
        weight=0.7,
        tradeable=True,
        stackable=False,
        tags=[("mutant_raider_cured_filet", "crafting_material")],
    ),
    "mutant_raider_cured_prime_meat": ItemDef(
        key="mutant_raider_cured_prime_meat",
        name="mutant raider cured prime meat",
        desc="Butchered, rendered, then cured -- three skills deep, and it shows.",
        value=52,
        weight=0.5,
        tradeable=True,
        stackable=False,
        tags=[("mutant_raider_cured_prime_meat", "crafting_material")],
    ),
}
