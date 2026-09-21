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



    # ─── Cured mutant giant meats (Curing) ────────────────────────────────
    # THE GIANT LADDER IS EXACTLY TWICE THE RAIDER LADDER, on every number:
    # heal, value and weight. The raider heals run 2/3/5/6 for the cured cuts
    # and 4/7/9/12 for the meals, so the giant runs 4/6/10/12 and 8/14/18/24
    # against the same 127 HP cap.
    #
    # A single rule rather than 8 separate judgements, for the same reason the
    # raider ladder is one scaling of the OSRS 3-to-22 range: a retune is one
    # multiplication, and a reader can check any row without a table.
    #
    # The doubled WEIGHT is what stops the giant meal being free. A prime
    # cured sandwich heals a fifth of a maxed pool and costs 1.8 units of bag
    # to carry, so a player still chooses how many to bring.
    #
    # The karambwan property carries over unchanged: a cured cut takes
    # CURED_MEAT_ATTACK_DELAY_TICKS and a cooked meal does not. The cheapest
    # food in the giant chain is still not the worst one.

    "mutant_giant_cured_chuck": ItemDef(
        key="mutant_giant_cured_chuck",
        name="mutant giant cured chuck",
        desc="A slab of giant chuck, hung until it went dark and hard.",
        value=28,
        weight=2.4,
        tradeable=True,
        stackable=False,
        heal_amount=4,
        attack_delay_ticks=CURED_MEAT_ATTACK_DELAY_TICKS,
        tags=[
            ("mutant_giant_cured_chuck", "crafting_material"),
            ("mutant_giant_cured_chuck", ITEM_FAMILY_FOOD),
        ],
    ),

    "mutant_giant_cured_fatless_meat": ItemDef(
        key="mutant_giant_cured_fatless_meat",
        name="mutant giant cured fatless meat",
        desc="Giant meat rendered dry and cured drier. It keeps for a season.",
        value=44,
        weight=1.8,
        tradeable=True,
        stackable=False,
        heal_amount=6,
        attack_delay_ticks=CURED_MEAT_ATTACK_DELAY_TICKS,
        tags=[
            ("mutant_giant_cured_fatless_meat", "crafting_material"),
            ("mutant_giant_cured_fatless_meat", ITEM_FAMILY_FOOD),
        ],
    ),

    "mutant_giant_cured_filet": ItemDef(
        key="mutant_giant_cured_filet",
        name="mutant giant cured filet",
        desc="A giant filet cured whole. The chamber held it for a long time.",
        value=80,
        weight=1.4,
        tradeable=True,
        stackable=False,
        heal_amount=10,
        attack_delay_ticks=CURED_MEAT_ATTACK_DELAY_TICKS,
        tags=[
            ("mutant_giant_cured_filet", "crafting_material"),
            ("mutant_giant_cured_filet", ITEM_FAMILY_FOOD),
        ],
    ),

    "mutant_giant_cured_prime_meat": ItemDef(
        key="mutant_giant_cured_prime_meat",
        name="mutant giant cured prime meat",
        desc="Butchered, rendered, then cured. Prime giant meat.",
        value=104,
        weight=1.0,
        tradeable=True,
        stackable=False,
        heal_amount=12,
        attack_delay_ticks=CURED_MEAT_ATTACK_DELAY_TICKS,
        tags=[
            ("mutant_giant_cured_prime_meat", "crafting_material"),
            ("mutant_giant_cured_prime_meat", ITEM_FAMILY_FOOD),
        ],
    ),



    # ─── Prepared mutant giant meals (Gastronomy) ─────────────────────────
    # The deepest food in the game. The giant prime cured sandwich heals 24,
    # which is a fifth of the 127 cap and twice what the raider's deepest item
    # gives -- and it costs two giant corpses, two renders and two cures.

    "mutant_giant_steak": ItemDef(
        key="mutant_giant_steak",
        name="mutant giant steak",
        desc="Lean giant meat seared in its own rendered fat. It covers the pan.",
        value=60,
        weight=2.0,
        tradeable=True,
        stackable=False,
        heal_amount=8,
        tags=[
            ("mutant_giant_steak", "crafting_material"),
            ("mutant_giant_steak", ITEM_FAMILY_FOOD),
        ],
    ),

    "mutant_giant_cured_meat_sandwich": ItemDef(
        key="mutant_giant_cured_meat_sandwich",
        name="mutant giant cured meat sandwich",
        desc=(
            "Two cured giant cuts pressed together. Still no bread out here."
        ),
        value=96,
        weight=2.2,
        tradeable=True,
        stackable=False,
        heal_amount=14,
        tags=[
            ("mutant_giant_cured_meat_sandwich", "crafting_material"),
            ("mutant_giant_cured_meat_sandwich", ITEM_FAMILY_FOOD),
        ],
    ),

    "mutant_giant_prime_steak": ItemDef(
        key="mutant_giant_prime_steak",
        name="mutant giant prime steak",
        desc="A prime giant cut seared in prime giant fat. It feeds a squad.",
        value=152,
        weight=1.6,
        tradeable=True,
        stackable=False,
        heal_amount=18,
        tags=[
            ("mutant_giant_prime_steak", "crafting_material"),
            ("mutant_giant_prime_steak", ITEM_FAMILY_FOOD),
        ],
    ),

    "mutant_giant_prime_cured_meat_sandwich": ItemDef(
        key="mutant_giant_prime_cured_meat_sandwich",
        name="mutant giant prime cured meat sandwich",
        desc=(
            "Cured prime giant meat against a cured giant filet. Two giants "
            "went into this."
        ),
        value=208,
        weight=1.8,
        tradeable=True,
        stackable=False,
        heal_amount=24,
        tags=[
            ("mutant_giant_prime_cured_meat_sandwich", "crafting_material"),
            ("mutant_giant_prime_cured_meat_sandwich", ITEM_FAMILY_FOOD),
        ],
    ),
}
