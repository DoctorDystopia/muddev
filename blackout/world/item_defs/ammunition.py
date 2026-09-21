"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/17/2026
Description: Blackout ammunition ItemDef entries — what a projectile weapon
             fires, and where a shot's damage bonus comes from.

WHY AMMUNITION IS ITS OWN MODULE. It is not a weapon: a player cannot wield
one, and nothing in it declares a combat style. It is not a material either:
a recipe never consumes one. It is the only item family that occupies an
equipment slot AND leaves the inventory one unit at a time, which is a shape
no other def module has.

TWO TAGS, TWO JOBS. Every entry here carries both:

  (family, AMMO_FAMILY_TAG_CATEGORY) — the FAMILY, NOT the item key. A bow's
                                     accepted_ammo names a family, and the
                                     projectile action matches the two by
                                     exact string. Filing the item key here
                                     instead would make every new arrow a bow
                                     edit, which is the whole thing the
                                     family exists to prevent.
  (key, "crafting_material")       — the crafting name. Without it no recipe
                                     could ever consume an arrow, and a
                                     fletching chain is the obvious next one.

THE STRENGTH BONUS LIVES HERE, NOT ON THE BOW. That is the OSRS rule and it
is deliberate: it makes the arrow an upgrade path of its own, so a player at
the same Guns level has something to buy. The number reaches the max-hit
formula because the AMMO slot is an equipment slot like every other, and
EquipmentHandler.total_combat_stat_bonuses sums every slot.
"""



import systems.gameplay.combat.constants as combat_constants
from items.equipment.constants import WieldLocation
from world.item_database import ItemDef



ITEMS = {

    # ------------------------
    # --- RUSTY SCRAP AMMO ---
    # ------------------------

    "rusty_scrap_arrow": ItemDef(
        key="rusty_scrap_arrow",
        name="rusty scrap arrow",
        typeclass="typeclasses.items.AmmunitionItem",
        desc="A short shaft with a bent scrap head. It flies straight enough.",
        value=2,
        weight=0.02,
        tradeable=True,
        stackable=True,
        use_slot=WieldLocation.AMMO,
        tool_type="ammo",
        tier=0,
        req_level=0,
        tags=[
            (combat_constants.AMMO_FAMILY_ARROW,
             combat_constants.AMMO_FAMILY_TAG_CATEGORY),
            ("rusty_scrap_arrow", "crafting_material"),
        ],
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": 0,
            "slash_attack_bonus": 0,
            "crush_attack_bonus": 0,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 0,
            "crush_defense_bonus": 0,

            # Projectile defense bonuses
            "light_defense_bonus": 0,
            "standard_defense_bonus": 0,
            "heavy_defense_bonus": 0,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 7,
        },
    ),



    # ------------------
    # --- SCRAP AMMO ---
    # ------------------

    "scrap_arrow": ItemDef(
        key="scrap_arrow",
        name="scrap arrow",
        typeclass="typeclasses.items.AmmunitionItem",
        desc="A short shaft with a bent scrap head. It flies straight enough.",
        value=2,
        weight=0.02,
        tradeable=True,
        stackable=True,
        use_slot=WieldLocation.AMMO,
        tool_type="ammo",
        tier=0,
        req_level=0,
        tags=[
            (combat_constants.AMMO_FAMILY_ARROW,
             combat_constants.AMMO_FAMILY_TAG_CATEGORY),
            ("scrap_arrow", "crafting_material"),
        ],
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": 0,
            "slash_attack_bonus": 0,
            "crush_attack_bonus": 0,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 0,
            "crush_defense_bonus": 0,

            # Projectile defense bonuses
            "light_defense_bonus": 0,
            "standard_defense_bonus": 0,
            "heavy_defense_bonus": 0,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 10,
        },
    ),



    # -------------------
    # --- COPPER AMMO ---
    # -------------------

    "copper_arrow": ItemDef(
        key="copper_arrow",
        name="copper arrow",
        typeclass="typeclasses.items.AmmunitionItem",
        desc="A short shaft with a bent copper head. It flies straight enough.",
        value=4,
        weight=0.02,
        tradeable=True,
        stackable=True,
        use_slot=WieldLocation.AMMO,
        tool_type="ammo",
        tier=1,
        req_level=10,
        tags=[
            (combat_constants.AMMO_FAMILY_ARROW,
             combat_constants.AMMO_FAMILY_TAG_CATEGORY),
            ("copper_arrow", "crafting_material"),
        ],
        combat_stat_bonuses={
            # Melee attack bonuses
            "stab_attack_bonus": 0,
            "slash_attack_bonus": 0,
            "crush_attack_bonus": 0,

            # Projectile attack bonuses
            "light_attack_bonus": 0,
            "standard_attack_bonus": 0,
            "heavy_attack_bonus": 0,

            # Melee defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 0,
            "crush_defense_bonus": 0,

            # Projectile defense bonuses
            "light_defense_bonus": 0,
            "standard_defense_bonus": 0,
            "heavy_defense_bonus": 0,

            # Other bonuses
            "melee_strength_bonus": 0,
            "projectile_strength_bonus": 16,
        },
    ),
}
