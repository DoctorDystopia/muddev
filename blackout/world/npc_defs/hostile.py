"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/30/2026
Description: Blackout hostile NPC NpcDef entries. Stats are faithful OSRS
              translations to the 0..127 scale (the formulas are
              scale-agnostic, so raw integer skill levels and bonuses
              transfer directly). combat_stat_bonuses keys match those
              used by weapon ItemDefs (stab/slash/crush_attack_bonus,
              *_defense_bonus, melee_strength_bonus) so the same combat
              math path resolves both PC swings and NPC defenders.
"""

import systems.combat.constants as combat_constants
from world.npc_database import NpcDef


# ─── Reusable combat-style builders ────────────────────────────────────────
# NPCs conventionally expose a subset of the four OSRS styles. These helpers
# keep sub-dicts faithful to the constants weapons reference, so the math
# resolves identically whether the attacker holds a WeaponItem or just has the
# stat block stamped by apply_combat_stats.


def _headbutt_crush_aggressive_combat_style():
    """Single crush / aggressive / brawn-XP style.

    The OSRS Goblin's attack style on the wiki is Crush, and goblins are
    aggressive-stanced (the wiki flags their attack style accordingly).
    """
    return {
        "headbutt": {
            "attack_type": "crush",
            "weapon_style": "aggressive",
            "weapon_style_xp_skill":
                combat_constants.AGGRESSIVE_XP_SKILLS,
            "weapon_style_level_boost":
                combat_constants.MELEE_WEAPON_STYLE_LEVEL_BOOST_AGGRESSIVE,
        },
    }

# TODO: add optional equipped items to the NpcDef dataclass

NPCS = {
    # ─── Mutant Raider ────────────────────────────────────────────────────
    # OSRS source: Goblin — Level 2 (Monster ID 3028).
    #   https://oldschool.runescape.wiki/w/Goblin#Level_2
    #
    # Combat stats (raw, transferred verbatim):
    #   Hitpoints 5, Attack 1, Strength 1, Defence 1, Magic 1, Ranged 1
    #   Max hit 1, Attack style Crush, Attack speed 4 ticks (2.4s)
    #   Aggressive: No
    # Monster attack bonus (crush): -21
    # Monster strength bonus:      -15
    # Defence stab/slash/crush:     -15 / -15 / -15
    #
    # Negative bonuses feed into the combat math exactly as positive ones
    # do (they only participate in the +64 zero-floor offset inside
    # attack_roll / defense_roll / max_hit), so the Goblin is a true
    # calibration point against the OSRS DPS calculator rather than a
    # face-tuned placeholder.
    "mutant_raider": NpcDef(
        key="mutant_raider",
        name="Mutant Raider",
        desc="A mutant who raids.",
        strike_level=1,
        brawn_level=1,
        defense_level=1,
        max_hp=5,
        attack_speed=4,
        combat_stat_bonuses={
            # Attack bonuses (per-damage-type; goblin is crush-only but the
            # math reads whichever *_attack_bonus the active style names, so
            # we stamp the same bonus on stab/slash to match the wiki's
            # "Monster attack bonus" of -21 across the board).
            "stab_attack_bonus": -21,
            "slash_attack_bonus": -21,
            "crush_attack_bonus": -21,
            # Defense bonuses
            "stab_defense_bonus": -15,
            "slash_defense_bonus": -15,
            "crush_defense_bonus": -15,
            # Other bonuses
            "melee_strength_bonus": -15,
        },
        combat_styles=_headbutt_crush_aggressive_combat_style(),
        default_combat_style="headbutt",
        # 30s timed respawn on the raider's spawn tile, driven by
        # BlackoutRespawnManager (systems/spawning/respawn.py).
        respawn_seconds=20,
        # Drop table in world/loot_defs/hostile.py, resolved at death through
        # db.npc_key -> NPC_DB -> LOOT_DB by systems/loot/drops.py.
        loot_table="mutant_raider_drops",
    ),
    "big_mutant": NpcDef(
        key="big_mutant",
        name="Big Mutant",
        desc="Bigger than you'd expect.",
        strike_level=76,
        brawn_level=78,
        defense_level=81,
        max_hp=87,
        attack_speed=4,
        combat_stat_bonuses={
            # stats based on OSRS Greater Demon
            "stab_attack_bonus": 0,
            "slash_attack_bonus": 0,
            "crush_attack_bonus": 0,
            # Defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 0,
            "crush_defense_bonus": 0,
            # Other bonuses
            "melee_strength_bonus": 0,
        },
        combat_styles=_headbutt_crush_aggressive_combat_style(),
        default_combat_style="headbutt",
        # 30s timed respawn on the big mutant's spawn tile, driven by
        # BlackoutRespawnManager (systems/spawning/respawn.py).
        respawn_seconds=30,
        # Two main-table rolls plus the 1/128 Glass Cannon amulet; see
        # world/loot_defs/hostile.py.
        loot_table="big_mutant_drops",
    ),
    "floating_eye": NpcDef(
        key="floating_eye",
        name="Floating Eye",
        desc="Terrified of needles.",
        strike_level=8,
        brawn_level=8,
        defense_level=12,
        max_hp=20,
        attack_speed=4,
        combat_stat_bonuses={
            # stats based on OSRS chaos druid, defenses lowered for flavor
            # https://oldschool.runescape.wiki/w/Chaos_druid
            "stab_attack_bonus": 0,
            "slash_attack_bonus": 0,
            "crush_attack_bonus": 0,
            # Defense bonuses
            "stab_defense_bonus": -42, # based on OSRS gnome child
            "slash_defense_bonus": -15,
            "crush_defense_bonus": 0,
            # Other bonuses
            "melee_strength_bonus": 8,
        },
        combat_styles=_headbutt_crush_aggressive_combat_style(),
        default_combat_style="headbutt",
        # 30s timed respawn on the Floating eye's spawn tile, driven by
        # BlackoutRespawnManager (systems/spawning/respawn.py).
        respawn_seconds=30,
        # Drop table in world/loot_defs/hostile.py.
        loot_table="floating_eye_drops",
    ),
}
