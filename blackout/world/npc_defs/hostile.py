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

import systems.gameplay.combat.constants as combat_constants
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
        # BlackoutRespawnManager (systems/gameplay/spawning/respawn.py).
        respawn_seconds=15,
        # Drop table in world/loot_defs/hostile.py, resolved at death through
        # db.npc_key -> NPC_DB -> LOOT_DB by systems/gameplay/loot/drops.py.
        loot_table="mutant_raider_drops",
        # Butchery's starter node. The body carries its own yields via
        # the ItemDef's gatherable_key, so nothing about chuck or filet
        # is restated here.
        corpse_key="mutant_raider_corpse",
    ),
    # ─── Mutant Giant ─────────────────────────────────────────────────────
    # OSRS source: Hill Giant — Combat level 28.
    #   https://oldschool.runescape.wiki/w/Hill_Giant
    #
    # Combat stats (raw, transferred verbatim):
    #   Hitpoints 35, Attack 18, Strength 22, Defence 26, Magic 1, Ranged 1
    #   Max hit 4, Attack style Crush, Attack speed 6 ticks (3.6s)
    #   Aggressive: Yes
    # Monster attack bonus (crush): +18
    # Monster strength bonus:      +16
    # Defence stab/slash/crush:      0 /  0 /  0
    #
    # THE FIRST NPC IN THE GAME THAT SWINGS SLOWER THAN 4 TICKS. Every other
    # entry in this dict uses 4, which made attack_speed look like a constant
    # rather than a stat. The Hill Giant's 6 is what the wiki says, and the
    # combat maths reads the field per NPC, so the number transfers with the
    # rest of the block and needs nothing else.
    #
    # THE WIKI'S "Aggressive: Yes" HAS NO HOME YET. Both behaviour keys in
    # systems/gameplay/ai/constants.py retaliate: aggressive_melee swings back
    # at what hit it, and chasing_melee follows what hit it. Neither one starts
    # a fight. The giant therefore chases what attacks it and ignores a player
    # who walks past. An unprovoked-aggression behaviour is one more key in
    # that registry when a design wants one.
    #
    # The tier between the Mutant Raider (5 hp) and the Big Mutant (87 hp),
    # and the source of the second food chain. The body carries its own yields
    # through the ItemDef's gatherable_key, so nothing about the cuts is
    # restated here.
    "mutant_giant": NpcDef(
        key="mutant_giant",
        name="Mutant Giant",
        desc="Huge, slow, and in no hurry about it.",
        strike_level=18,
        brawn_level=22,
        defense_level=26,
        max_hp=35,
        attack_speed=6,
        combat_stat_bonuses={
            # Attack bonuses. The Hill Giant is crush-only, and the math reads
            # whichever *_attack_bonus the active style names, so the wiki's
            # single "Monster attack bonus" of +18 is stamped across all three.
            "stab_attack_bonus": 18,
            "slash_attack_bonus": 18,
            "crush_attack_bonus": 18,
            # Defense bonuses
            "stab_defense_bonus": 0,
            "slash_defense_bonus": 0,
            "crush_defense_bonus": 0,
            # Other bonuses
            "melee_strength_bonus": 16,
        },
        combat_styles=_headbutt_crush_aggressive_combat_style(),
        default_combat_style="headbutt",
        # 30s timed respawn, matching the Big Mutant rather than the raider's
        # 15s. A tier the player clears deliberately should not refill behind
        # them while they butcher the last one.
        respawn_seconds=30,
        # Drop table in world/loot_defs/hostile.py.
        loot_table="mutant_giant_drops",
        # Butchery's second node, and the whole giant food chain's source.
        corpse_key="mutant_giant_corpse",
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
        # BlackoutRespawnManager (systems/gameplay/spawning/respawn.py).
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
        # BlackoutRespawnManager (systems/gameplay/spawning/respawn.py).
        respawn_seconds=30,
        # Drop table in world/loot_defs/hostile.py.
        loot_table="floating_eye_drops",
    ),
    "mutant_crab": NpcDef(
        key="mutant_crab",
        name="Mutant Crab",
        desc="A large, aggressive crab.",
        strike_level=1,
        brawn_level=1,
        defense_level=1,
        max_hp=60,
        attack_speed=4,
        combat_stat_bonuses={
            # stats based on OSRS chaos druid, defenses lowered for flavor
            # https://oldschool.runescape.wiki/w/Chaos_druid
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
        # 30s timed respawn on the Mutant Crab's spawn tile, driven by
        # BlackoutRespawnManager (systems/gameplay/spawning/respawn.py).
        respawn_seconds=30,
        # Drop table in world/loot_defs/hostile.py.
        loot_table="mutant_crab_drops",
    ),
}
