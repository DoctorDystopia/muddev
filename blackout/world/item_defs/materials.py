"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/17/2026
Description: ItemDef entries for raw and processed crafting materials.
"""



from world.item_database import ItemDef



ITEMS = {
    # -------------------------
    # --- RUSTY METAL ITEMS ---
    # -------------------------
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

    # -------------------
    # --- METAL ITEMS ---
    # -------------------
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

    # --------------------
    # --- COPPER ITEMS ---
    # --------------------
    "copper_chunk": ItemDef(
        key="copper_chunk",
        name="copper chunk",
        desc="A chunk of copper. Weirdle fresh.",
        value=25,
        weight=2.0,
        tradeable=True,
        stackable=False,
        tags=[("copper_chunk", "crafting_material")],
    ),

    "copper_dust": ItemDef(
        key="copper_dust",
        name="copper dust",
        desc="A fine, dust ground from copper.",
        value=30,
        weight=0.2,
        tradeable=True,
        stackable=True,
        tags=[("copper_dust", "crafting_material")],
    ),

    "scrap_copper": ItemDef(
        key="scrap_copper",
        name="scrap copper",
        desc="A rough piece of scrap copper, smelted down from a copper chunk.",
        value=35,
        weight=1.0,
        tradeable=True,
        stackable=False,
        tags=[("scrap_copper", "crafting_material")],
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

    "mutant_raider_raw_hide": ItemDef(
        key="mutant_raider_raw_hide",
        name="mutant raider raw hide",
        desc="A thick, leathery piece of skin from a mutant raider.",
        value=12,
        weight=1.0,
        tradeable=True,
        stackable=False,
        tags=[("mutant_raider_raw_hide", "crafting_material")],
    ),

    "mutant_raider_prime_raw_hide": ItemDef(
        key="mutant_raider_prime_raw_hide",
        name="mutant raider prime raw hide",
        desc="A whole back hide, taken off clean. The grain runs one way the length of it.",
        value=30,
        weight=1.4,
        tradeable=True,
        stackable=False,
        tags=[("mutant_raider_prime_raw_hide", "crafting_material")],
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



    # ─── Cured mutant raider products (Curing) ──────────────────────
    # This is used for a Gunsmith recipe, so it's not in food.py.
    # mutant_raider_raw_hide is used to make mutant_raider_sinew

    "mutant_raider_sinew": ItemDef(
        key="mutant_raider_sinew",
        name="mutant raider sinew",
        desc="A tough, fibrous strand of muscle, still attached to the bone.",
        value=15,
        weight=0.2,
        tradeable=True,
        stackable=True,
        tags=[("mutant_raider_sinew", "crafting_material")],
    ),

    "mutant_raider_cured_hide": ItemDef(
        key="mutant_raider_cured_hide",
        name="mutant raider cured hide",
        desc="A thick, leathery piece of skin from a mutant raider.",
        value=12,
        weight=1.0,
        tradeable=True,
        stackable=False,
        tags=[("mutant_raider_cured_hide", "crafting_material")],
    ),

    # The tier 2 string. Cured off the prime hide, which the level 10 cut
    # yields beside the filet -- so the Gunsmith's second bow and the
    # Gastronomy chain open at the same Butchery level, off one corpse.
    "mutant_raider_prime_sinew": ItemDef(
        key="mutant_raider_prime_sinew",
        name="mutant raider prime sinew",
        desc="A long, even cord drawn off a whole hide and twisted tight. It does not fray.",
        value=45,
        weight=0.2,
        tradeable=True,
        stackable=True,
        tags=[("mutant_raider_prime_sinew", "crafting_material")],
    ),

    "mutant_raider_prime_cured_hide": ItemDef(
        key="mutant_raider_prime_cured_hide",
        name="mutant raider prime cured hide",
        desc="A thick, leathery piece of skin from a mutant raider.",
        value=12,
        weight=1.0,
        tradeable=True,
        stackable=False,
        tags=[("mutant_raider_prime_cured_hide", "crafting_material")],
    ),



    # ─── Mutant giant cuts (Butchery) ─────────────────────────────────────
    # The second corpse in the game, and the same four cuts one tier up. The
    # giant opens at Butchery 20 and its filet at 30, which is the 10-per-tier
    # spacing the Cutting poles already use: rusty at 0, metal at 10, copper
    # at 20.
    #
    # EVERY VALUE AND WEIGHT HERE IS TWICE THE RAIDER COUNTERPART. One rule,
    # applied across all 17 giant entries in this module and food.py, so a
    # retune is one multiplication rather than 17 judgements. The heal ladder
    # in food.py doubles by the same rule.
    #
    # The doubled WEIGHT is the cost of the tier. A giant cut heals twice as
    # much and fills twice as much of the bag, so the trip back is the same
    # trip it always was.

    "mutant_giant_raw_chuck": ItemDef(
        key="mutant_giant_raw_chuck",
        name="mutant giant raw chuck",
        desc="A slab off a mutant giant. It takes two hands.",
        value=12,
        weight=3.0,
        tradeable=True,
        stackable=False,
        tags=[("mutant_giant_raw_chuck", "crafting_material")],
    ),

    "mutant_giant_raw_filet": ItemDef(
        key="mutant_giant_raw_filet",
        name="mutant giant raw filet",
        desc="A clean, boneless portion of a mutant giant. The grain is coarse.",
        value=36,
        weight=1.6,
        tradeable=True,
        stackable=False,
        tags=[("mutant_giant_raw_filet", "crafting_material")],
    ),

    "mutant_giant_raw_hide": ItemDef(
        key="mutant_giant_raw_hide",
        name="mutant giant raw hide",
        desc="A heavy, scarred piece of skin from a mutant giant.",
        value=24,
        weight=2.0,
        tradeable=True,
        stackable=False,
        tags=[("mutant_giant_raw_hide", "crafting_material")],
    ),

    # The level 30 hide. NOTHING CURES IT YET, and that is deliberate: the
    # cut exists so the corpse reads the same as the raider's at every level,
    # and the tier that needs a giant prime sinew or a giant prime cured hide
    # adds the Curing recipe then. A gathered material with no recipe is a
    # material a player can sell. A CRAFTED item with no recipe is the bug
    # that left both hide capes uncraftable -- see curing_recipes.py.
    "mutant_giant_prime_raw_hide": ItemDef(
        key="mutant_giant_prime_raw_hide",
        name="mutant giant prime raw hide",
        desc="A whole back hide off a giant. One piece, and almost too wide to fold.",
        value=60,
        weight=2.8,
        tradeable=True,
        stackable=False,
        tags=[("mutant_giant_prime_raw_hide", "crafting_material")],
    ),



    # ─── Rendered mutant giant products (Rendering) ───────────────────────
    # The same two-per-tier choice the raider offers: the fat boiled out of a
    # cut, or what is left once the fat is gone. Stackable follows the raider
    # rule, which follows metal_dust against metal_chunk -- a substance with
    # no shape of its own has nothing to lose by stacking.

    "mutant_giant_tallow": ItemDef(
        key="mutant_giant_tallow",
        name="mutant giant tallow",
        desc="A yellow cake of rendered fat, heavy for its size.",
        value=20,
        weight=0.8,
        tradeable=True,
        stackable=True,
        tags=[("mutant_giant_tallow", "crafting_material")],
    ),

    "mutant_giant_fatless_meat": ItemDef(
        key="mutant_giant_fatless_meat",
        name="mutant giant fatless meat",
        desc="A lean, dry cut boiled clean of fat. It still weighs on the arm.",
        value=24,
        weight=2.2,
        tradeable=True,
        stackable=False,
        tags=[("mutant_giant_fatless_meat", "crafting_material")],
    ),

    "mutant_giant_prime_tallow": ItemDef(
        key="mutant_giant_prime_tallow",
        name="mutant giant prime tallow",
        desc="Pale fat rendered off a giant filet. It sets hard and smells of nothing.",
        value=52,
        weight=0.6,
        tradeable=True,
        stackable=True,
        tags=[("mutant_giant_prime_tallow", "crafting_material")],
    ),

    "mutant_giant_prime_meat": ItemDef(
        key="mutant_giant_prime_meat",
        name="mutant giant prime meat",
        desc="A dense cut off a giant filet, trimmed down to the part worth keeping.",
        value=64,
        weight=1.2,
        tradeable=True,
        stackable=False,
        tags=[("mutant_giant_prime_meat", "crafting_material")],
    ),



    # ─── Cured mutant giant products (Curing) ─────────────────────────────
    # The two cures that are not food. The sinew strings the copper shortbow
    # and the cured hide backs the copper hide cape, so both have a consumer
    # the day they ship.

    "mutant_giant_sinew": ItemDef(
        key="mutant_giant_sinew",
        name="mutant giant sinew",
        desc="A thick fibrous cord off a giant. It creaks when you pull it.",
        value=30,
        weight=0.4,
        tradeable=True,
        stackable=True,
        tags=[("mutant_giant_sinew", "crafting_material")],
    ),

    "mutant_giant_cured_hide": ItemDef(
        key="mutant_giant_cured_hide",
        name="mutant giant cured hide",
        desc="Giant skin cured stiff. It turns a blade better than it should.",
        value=24,
        weight=2.0,
        tradeable=True,
        stackable=False,
        tags=[("mutant_giant_cured_hide", "crafting_material")],
    ),
}
