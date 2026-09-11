"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: ItemDef entries for raw and processed crafting materials.
"""



from world.item_database import ItemDef



ITEMS = {
    # Rusty metal items
    "rusty_metal_chunk": ItemDef(
        key="rusty_metal_chunk",
        name="rusty metal chunk",
        desc="A chunk of metal corroded by rust and age.",
        value=4,
        weight=2.0,
        tradeable=True,
        stackable=False,
        tags=[("rusty_metal_chunk", "crafting_material")],
    ),
    "rusty_metal_dust": ItemDef(
        key="rusty_metal_dust",
        name="rusty metal dust",
        desc="A fine, reddish-brown dust ground from rusty metal.",
        value=8,
        weight=0.2,
        tradeable=True,
        stackable=True,
        tags=[("rusty_metal_dust", "crafting_material")],
    ),
    "rusty_scrap_metal": ItemDef(
        key="rusty_scrap_metal",
        name="rusty scrap metal",
        desc="A rough piece of scrap metal, smelted down from a rusty chunk.",
        value=10,
        weight=1.0,
        tradeable=True,
        stackable=False,
        tags=[("rusty_scrap_metal", "crafting_material")],
    ),

    # ─── Mutant raider cuts (Butchery) ────────────────────────────────────
    # Butchery's two yields off a raider corpse: the chuck from level 0, the
    # filet from 10. Non-stackable, matching rusty_metal_chunk -- a gathered
    # material a recipe consumes one of. Rendering and Gastronomy read them
    # by tag, so adding a third cut needs no edit outside this dict and
    # GATHERABLE_REGISTRY.
    #
    # The `raw_` in the key is doing work. By the time the food chain is whole
    # this corpse yields a chuck that is raw, one that is rendered, and one
    # that is cured, and the player holds all three at once. A bare
    # `mutant_raider_chuck` would be the one nobody could name -- which is why
    # the crafting spreadsheet, the source of truth for this chain, spells it
    # with the prefix.
    "mutant_raider_raw_chuck": ItemDef(
        key="mutant_raider_raw_chuck",
        name="mutant raider raw chuck",
        desc="A rough rectangular slab off a mutant raider.",
        value=6,
        weight=1.5,
        tradeable=True,
        stackable=False,
        tags=[("mutant_raider_raw_chuck", "crafting_material")],
    ),
    "mutant_raider_raw_filet": ItemDef(
        key="mutant_raider_raw_filet",
        name="mutant raider raw filet",
        desc="A clean, boneless portion of a mutant raider.",
        value=18,
        weight=0.8,
        tradeable=True,
        stackable=False,
        tags=[("mutant_raider_raw_filet", "crafting_material")],
    ),

    # ─── Rendered mutant raider products (Rendering) ──────────────────────
    # What the rendering cooker makes of a cut: the fat boiled out of it, and
    # what is left once the fat is gone. One cut in, ONE product out -- the
    # two rows per tier are two separate recipes the player chooses between,
    # not a single recipe with two outputs, so the chuck a player spends on
    # tallow is a chuck they do not get fatless meat from.
    #
    # Tallow is stackable and the meat is not, following metal_dust against
    # metal_chunk: rendering reduces a cut to a quantity of a substance, and a
    # substance with no shape of its own has nothing to lose by stacking.
    # Neither is food. Nothing here is edible and the spreadsheet's "eat to
    # heal HP" column is empty for every Rendering row -- these are the
    # INGREDIENTS Curing and Gastronomy turn into food.
    "mutant_raider_tallow": ItemDef(
        key="mutant_raider_tallow",
        name="mutant raider tallow",
        desc="A pale cake of rendered fat, faintly iridescent where the light catches it.",
        value=10,
        weight=0.4,
        tradeable=True,
        stackable=True,
        tags=[("mutant_raider_tallow", "crafting_material")],
    ),
    "mutant_raider_fatless_meat": ItemDef(
        key="mutant_raider_fatless_meat",
        name="mutant raider fatless meat",
        desc="A lean, dry cut with every trace of fat boiled out of it. Edible, in theory.",
        value=12,
        weight=1.1,
        tradeable=True,
        stackable=False,
        tags=[("mutant_raider_fatless_meat", "crafting_material")],
    ),
    "mutant_raider_prime_tallow": ItemDef(
        key="mutant_raider_prime_tallow",
        name="mutant raider prime tallow",
        desc="Clean white fat rendered off a good filet, set hard and smelling of almost nothing.",
        value=26,
        weight=0.3,
        tradeable=True,
        stackable=True,
        tags=[("mutant_raider_prime_tallow", "crafting_material")],
    ),
    "mutant_raider_prime_meat": ItemDef(
        key="mutant_raider_prime_meat",
        name="mutant raider prime meat",
        desc="A dense, close-grained cut off a filet, trimmed of everything that was not worth keeping.",
        value=32,
        weight=0.6,
        tradeable=True,
        stackable=False,
        tags=[("mutant_raider_prime_meat", "crafting_material")],
    ),

    # Metal items
    "metal_chunk": ItemDef(
        key="metal_chunk",
        name="metal chunk",
        desc="A chunk of metal. Weirdly fresh.",
        value=17,
        weight=2.267,
        tradeable=True,
        stackable=False,
        tags=[("metal_chunk", "crafting_material")],
    ),
    "metal_dust": ItemDef(
        key="metal_dust",
        name="metal dust",
        desc="A fine, grey dust ground from metal.",
        value=19,
        weight=0.2,
        tradeable=True,
        stackable=True,
        tags=[("metal_dust", "crafting_material")],
    ),
    "scrap_metal": ItemDef(
        key="scrap_metal",
        name="scrap metal",
        desc="A rough piece of scrap metal, smelted down from a metal chunk.",
        value=28,
        weight=1.814,
        tradeable=True,
        stackable=False,
        tags=[("scrap_metal", "crafting_material")],
    ),
}
