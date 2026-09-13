"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: ItemDef entries for food -- what Curing preserves and Gastronomy
             cooks, and the only items in the game a player uses UP.

             Every entry declares TWO families. `crafting_material` is how a
             recipe finds it: Gastronomy's sandwich consumes a cured chuck and a
             cured fatless meat by that tag, so dropping it would strand the
             recipes. `food` is how a client draws it, and it sits ahead of
             material in ITEM_FAMILY_PRIORITY so these render as food rather
             than as anonymous lumps. An item may belong to several families,
             and this is the clearest case of it in the game.

             `heal_amount` is the field that makes an item edible -- not the
             tag. A family tag is a LOOK, not a rule, exactly as it is for
             weapons: an ItemDef tagged `food` with no heal_amount would render
             as food and refuse to be eaten, which is the same trap an ItemDef
             tagged `weapon` with no combat_styles walks into.

             The cured meats carry CURED_MEAT_ATTACK_DELAY_TICKS and the cooked
             meals do not, which is a real tactical difference rather than a
             detail: a cured chuck heals less than a prime steak but lets you
             swing a tick sooner after eating it. That is the Cooked karambwan
             property, and it is why the cheapest food in the chain is not
             simply the worst one.

             A separate module from materials.py on purpose. `cured` is not a
             processing state of the metal chain and the two dicts have nothing
             to say to each other; world/item_database.py names modules in this
             package explicitly, so a new file costs one import and one list
             entry.
"""



from systems.gameplay.consumables.constants import (
    CURED_MEAT_ATTACK_DELAY_TICKS,
)
from systems.interface.statefeed.constants import ITEM_FAMILY_FOOD
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
    # apart, and what separates these is how much they heal.
    #
    # The heal ladder across this whole module runs 2 to 12 against a 10 HP
    # start (Fortitude is seeded at 10) and a 127 cap, with passive regen at
    # 1 HP per minute -- so a cured chuck is a fifth of a new character's pool
    # and the deepest sandwich is a tenth of a maxed one. Scaled off OSRS's
    # 3-to-22 range by the same factor the combat maths uses, then halved:
    # food is a supplement here, not a reset button, which leaves room for a
    # later chain to heal more without breaking this one.
    "mutant_raider_cured_chuck": ItemDef(
        key="mutant_raider_cured_chuck",
        name="mutant raider cured chuck",
        desc="A slab of chuck, dark and firm, crusted white with salt.",
        value=14,
        weight=1.2,
        tradeable=True,
        stackable=False,
        heal_amount=2,
        attack_delay_ticks=CURED_MEAT_ATTACK_DELAY_TICKS,
        tags=[
            ("mutant_raider_cured_chuck", "crafting_material"),
            ("mutant_raider_cured_chuck", ITEM_FAMILY_FOOD),
        ],
    ),
    "mutant_raider_cured_fatless_meat": ItemDef(
        key="mutant_raider_cured_fatless_meat",
        name="mutant raider cured fatless meat",
        desc="Lean meat rendered dry and then cured drier. It could outlast you.",
        value=22,
        weight=0.9,
        tradeable=True,
        stackable=False,
        heal_amount=3,
        attack_delay_ticks=CURED_MEAT_ATTACK_DELAY_TICKS,
        tags=[
            ("mutant_raider_cured_fatless_meat", "crafting_material"),
            ("mutant_raider_cured_fatless_meat", ITEM_FAMILY_FOOD),
        ],
    ),
    "mutant_raider_cured_filet": ItemDef(
        key="mutant_raider_cured_filet",
        name="mutant raider cured filet",
        desc="A whole filet cured through without splitting.",
        value=40,
        weight=0.7,
        tradeable=True,
        stackable=False,
        heal_amount=5,
        attack_delay_ticks=CURED_MEAT_ATTACK_DELAY_TICKS,
        tags=[
            ("mutant_raider_cured_filet", "crafting_material"),
            ("mutant_raider_cured_filet", ITEM_FAMILY_FOOD),
        ],
    ),
    "mutant_raider_cured_prime_meat": ItemDef(
        key="mutant_raider_cured_prime_meat",
        name="mutant raider cured prime meat",
        desc="Butchered, rendered, then cured. Prime mutant meat.",
        value=52,
        weight=0.5,
        tradeable=True,
        stackable=False,
        heal_amount=6,
        attack_delay_ticks=CURED_MEAT_ATTACK_DELAY_TICKS,
        tags=[
            ("mutant_raider_cured_prime_meat", "crafting_material"),
            ("mutant_raider_cured_prime_meat", ITEM_FAMILY_FOOD),
        ],
    ),

    # ─── Prepared meals (Gastronomy) ──────────────────────────────────────
    # The end of the chain: nothing consumes these, and the spreadsheet marks
    # every one "eat to heal HP". They are the first items in the game that
    # exist only to be used up by the player rather than by a recipe.
    #
    # These heal MORE than the cured meats above and swing SLOWER after --
    # they take the standard attack delay where a cured meat takes the
    # karambwan two. A meal is the considered choice and a cured cut is the
    # panicked one, which is the trade the numbers are here to express.
    #
    # The sheet promises the sandwich heals more than cured meat eaten raw, and
    # it does: 7 against the 2 and 3 of the two cured cuts that went into it.
    "mutant_raider_steak": ItemDef(
        key="mutant_raider_steak",
        name="mutant raider steak",
        desc="Lean meat seared in its own rendered fat.",
        value=30,
        weight=1.0,
        tradeable=True,
        stackable=False,
        heal_amount=4,
        tags=[
            ("mutant_raider_steak", "crafting_material"),
            ("mutant_raider_steak", ITEM_FAMILY_FOOD),
        ],
    ),
    "mutant_raider_cured_meat_sandwich": ItemDef(
        key="mutant_raider_cured_meat_sandwich",
        name="mutant raider cured meat sandwich",
        desc=(
            "Two kinds of cured meat pressed together. That's basically a sandwich, right?"
        ),
        value=48,
        weight=1.1,
        tradeable=True,
        stackable=False,
        heal_amount=7,
        tags=[
            ("mutant_raider_cured_meat_sandwich", "crafting_material"),
            ("mutant_raider_cured_meat_sandwich", ITEM_FAMILY_FOOD),
        ],
    ),
    "mutant_raider_prime_steak": ItemDef(
        key="mutant_raider_prime_steak",
        name="mutant raider prime steak",
        desc="A prime cut seared in prime fat. Mmmm...",
        value=76,
        weight=0.8,
        tradeable=True,
        stackable=False,
        heal_amount=9,
        tags=[
            ("mutant_raider_prime_steak", "crafting_material"),
            ("mutant_raider_prime_steak", ITEM_FAMILY_FOOD),
        ],
    ),
    "mutant_raider_prime_cured_meat_sandwich": ItemDef(
        key="mutant_raider_prime_cured_meat_sandwich",
        name="mutant raider prime cured meat sandwich",
        desc=(
            "Cured prime meat pressed together with a cured filet. That's basically a sandwich, right?"
        ),
        value=104,
        weight=0.9,
        tradeable=True,
        stackable=False,
        heal_amount=12,
        tags=[
            ("mutant_raider_prime_cured_meat_sandwich", "crafting_material"),
            ("mutant_raider_prime_cured_meat_sandwich", ITEM_FAMILY_FOOD),
        ],
    ),
}
