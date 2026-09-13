"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/13/2026
Description: Blackout armor ItemDef entries — head armor
"""



import systems.gameplay.combat.constants as combat_constants
from items.equipment.constants import WieldLocation
from world.item_database import ItemDef



ITEMS = {
    # ─── Rusty scrap melee armor head ───────────────────────────────────────────────
    "rusty_scrap_great_helm": ItemDef(
        key="rusty_scrap_great_helm",
        name="rusty scrap great helm",
        typeclass="typeclasses.items.ArmorItem",
        desc="Rusty scrap great helm. Infection not included.",
        value=44,
        weight=2.721,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.HEAD,
        tool_type="helmet",
        tier=1,
        req_level=0,
        tags=[("rusty_scrap_great_helm", "armor")],
        combat_stat_bonuses={
            # Attack bonuses
            "stab_attack_bonus": 0,
            "slash_attack_bonus": 0,
            "crush_attack_bonus": 0,
            # Defense bonuses
            "stab_defense_bonus": 4,
            "slash_defense_bonus": 5,
            "crush_defense_bonus": 3,
            # Other bonuses
            "melee_strength_bonus": 0,
        },
    ),



    # ─── Scrap melee armor head ───────────────────────────────────────────────
    "scrap_great_helm": ItemDef(
        key="scrap_great_helm",
        name="scrap great helm",
        typeclass="typeclasses.items.ArmorItem",
        desc="Scrap great helm. Infection not included.",
        value=154,
        weight=2.721,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.HEAD,
        tool_type="helmet",
        tier=1,
        req_level=10,
        tags=[("scrap_great_helm", "armor")],
        combat_stat_bonuses={
            # Attack bonuses
            "stab_attack_bonus": 0,
            "slash_attack_bonus": 0,
            "crush_attack_bonus": 0,
            # Defense bonuses
            "stab_defense_bonus": 6,
            "slash_defense_bonus": 7,
            "crush_defense_bonus": 5,
            # Other bonuses
            "melee_strength_bonus": 0,
        },
    ),
}
