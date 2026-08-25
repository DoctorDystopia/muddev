"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/14/2026
Description: LootTableDef entries for hostile NPCs. One dict entry per table;
             an NpcDef names one by key through its loot_table field.

             Every main pool below is denominated in 128ths, matching the OSRS
             drop tables the monster stat blocks in world/npc_defs/hostile.py
             were transferred from. Weights are relative, so the denominator
             is a convention rather than a requirement -- but keeping it means
             a wiki drop rate can be copied across without arithmetic, and the
             nothing_weight reads directly as "how many kills give nothing".
"""

from world.loot_database import LootEntry, LootTableDef, TertiaryDrop


# ─── Private constant definitions ────────────────────────────────────────────

# The denominator every main pool below sums to, nothing_weight included.
# Not consumed by the roller -- it only needs relative weights -- but stated
# once here so a table that no longer adds up is obvious on sight.
_OSRS_TABLE_DENOMINATOR = 128


TABLES = {
    # ─── Mutant Raider ────────────────────────────────────────────────────
    # The starter enemy. Half of all kills give nothing
    "mutant_raider_drops": LootTableDef(
        key="mutant_raider_drops",
        main=[
            LootEntry(item_key="credits", min_quantity=5, max_quantity=15,
                      weight=40),
            LootEntry(item_key="rusty_metal_chunk", weight=16),
            LootEntry(item_key="rusty_metal_dust", min_quantity=1,
                      max_quantity=3, weight=8),
        ],
        nothing_weight=64,
    ),

    # ─── Floating Eye ─────────────────────────────────────────────────────
    # Mid-weight (OSRS Chaos Druid, 20 hp). Drops dust and a gadget.
    "floating_eye_drops": LootTableDef(
        key="floating_eye_drops",
        main=[
            LootEntry(item_key="credits", min_quantity=15, max_quantity=40,
                      weight=48),
            LootEntry(item_key="rusty_metal_dust", min_quantity=2,
                      max_quantity=5, weight=32),
            LootEntry(item_key="malfunctioning_gizmo", weight=8),
        ],
        nothing_weight=40,
    ),

    # ─── Big Mutant ───────────────────────────────────────────────────────
    # ~ boss tier right now (OSRS Greater Demon, 87 hp). Guaranteed scrap,
    # two rolls on tertiary, and source of the Glass Cannon amulet at 1/128.
    "big_mutant_drops": LootTableDef(
        key="big_mutant_drops",
        always=[
            LootEntry(item_key="rusty_metal_chunk", min_quantity=1,
                      max_quantity=2),
        ],
        main=[
            LootEntry(item_key="credits", min_quantity=40, max_quantity=120,
                      weight=48),
            LootEntry(item_key="rusty_scrap_metal", weight=32),
            LootEntry(item_key="rusty_scrap_shortsword", weight=16),
            LootEntry(item_key="rusty_scrap_spear", weight=16),
        ],
        nothing_weight=16,
        rolls=2,
        tertiary=[
            TertiaryDrop(
                entry=LootEntry(item_key="glass_cannon_amulet"),
                chance_denominator=128,
            ),
        ],
    ),
}
