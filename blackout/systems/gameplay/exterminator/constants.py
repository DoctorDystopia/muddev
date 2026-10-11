"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: The one owner of every Exterminator literal: the attribute
             names, the task fields, the points rules, and the message
             templates.

             The vault note 03_Systems/Skills/Utility_Skills/
             Exterminator_Skill.md owns the rules. Every number here is a TBD
             placeholder (Nick, 10/06/2026). DESIGN-0012, Phase 2.
"""

from systems.interface.ui.colors import (
    ERROR_COLOR,
    HIGHLIGHT_COLOR,
    RESET_COLOR,
    SUCCESS_COLOR,
)



# ─── Attributes on the character ────────────────────────────────────────────
# Nothing outside handler.py reads or writes these. The task is one dict, or
# None when the character has no task. The streak and the points outlive a
# task, so each one has its own Attribute.
TASK_ATTR: str = "exterminator_task"
STREAK_ATTR: str = "exterminator_streak"
POINTS_ATTR: str = "exterminator_points"


# ─── Fields of the task dict ────────────────────────────────────────────────
FIELD_PRECEPTOR: str = "preceptor"          # a key of PRECEPTOR_DB
FIELD_CREATURE_TYPE: str = "creature_type"  # a key of CREATURE_TYPES
FIELD_TOTAL: str = "total"                  # kills that the task needs
FIELD_KILLS: str = "kills"                  # kills that counted so far
FIELD_STARTED_AT: str = "started_at"        # time.time() at the assignment
FIELD_BUFFS: str = "buffs"                  # held buffs, as card dicts, in pick order
FIELD_PICKS_EARNED: str = "picks_earned"    # pick milestones passed so far
FIELD_BANKED_PICKS: str = "banked_picks"    # picks that came due, not used yet
FIELD_OFFER: str = "offer"                  # the open offer: card dicts, or None
FIELD_PLAYTIME_AT_START: str = "playtime_at_start"  # playtime_seconds at the assignment

# The fields of one card dict. A held buff uses the same shape.
CARD_KEY: str = "key"          # a key of BUFF_REGISTRY
CARD_RARITY: str = "rarity"    # one of RARITIES


# ─── Buff keys ──────────────────────────────────────────────────────────────
# The key of each buff in BUFF_REGISTRY. One buff class serves one archetype
# from the vault note, so the key IS the archetype key. A pool names a buff
# by this key, and the buff class sets `key` from it. preceptors.py cannot
# import buff_defs/, because each buff imports the combat rules package.
BUFF_ACCURACY_VS_TYPE: str = "accuracy_vs_type"
BUFF_DEFENSE_SEAL: str = "defense_seal"
BUFF_MILESTONE_GROWTH: str = "milestone_growth"
BUFF_LOW_HP_MAX_HIT: str = "low_hp_max_hit"
BUFF_BEST_OF_TWO_ROLLS: str = "best_of_two_rolls"
BUFF_DAMAGE_FOR_DEFENSE: str = "damage_for_defense"
BUFF_PAR_TIME_POINTS: str = "par_time_points"


# ─── Pick milestones ────────────────────────────────────────────────────────
# The count of pick milestones in one task. The picks come at 0%, 33%, and
# 66% of the task. A permanent upgrade can add to the count later.
PICK_MILESTONE_COUNT: int = 3

# The cards in one offer. A permanent upgrade can add to it later.
CARDS_PER_OFFER: int = 3


# ─── Rarity ─────────────────────────────────────────────────────────────────
# Each card rolls a rarity, and the rarity sets the strength of the buff, as
# in Hades (Nick, 10/06/2026). A buff declares one number for each rarity.
# The weights are TBD. Points shift them later (Phase 6).
RARITY_COMMON: str = "common"
RARITY_RARE: str = "rare"
RARITY_EPIC: str = "epic"
RARITY_LEGENDARY: str = "legendary"

# Lowest first.
RARITIES: tuple = (RARITY_COMMON, RARITY_RARE, RARITY_EPIC, RARITY_LEGENDARY)

RARITY_WEIGHTS: dict = {
    RARITY_COMMON: 60,
    RARITY_RARE: 25,
    RARITY_EPIC: 12,
    RARITY_LEGENDARY: 3,
}

RARITY_NAMES: dict = {
    RARITY_COMMON: "Common",
    RARITY_RARE: "Rare",
    RARITY_EPIC: "Epic",
    RARITY_LEGENDARY: "Legendary",
}


# ─── Seam labels, for the conflict warning on a card ────────────────────────
# The player-facing name of each seam that a buff can own. A seam with no row
# shows its key.
SEAM_LABELS: dict = {
    "effective_attack_level": "accuracy level",
    "effective_strength_level": "damage level",
    "effective_defense_level": "defense level",
    "max_hit": "max hit",
    "accuracy": "hit chance",
    "roll_accuracy": "hit roll",
    "roll_damage": "damage roll",
    "resolve": "whole attack",
}


# ─── Points ─────────────────────────────────────────────────────────────────
# The streak milestones, highest first. A completed task that brings the
# streak to a multiple of the first value gives the base points times the
# second value. Only the highest multiplier applies: streak 100 gives 10x,
# not 5x + 10x. TBD numbers (Nick, 10/06/2026).
STREAK_MULTIPLIERS: tuple = (
    (1000, 30),
    (100, 10),
    (10, 5),
)

# The multiplier of a streak that is on no milestone.
STREAK_BASE_MULTIPLIER: int = 1

# What a skip costs. A player with fewer points cannot skip. A skip breaks
# the streak. TBD number.
SKIP_COST_POINTS: int = 30


# ─── Par time ───────────────────────────────────────────────────────────────
# The par time of a task is its total kills times the seconds per kill of
# its creature type. Each Assignment can set its own number. This is the
# default. The clock counts online time only (Nick, 10/07/2026). TBD number.
DEFAULT_PAR_SECONDS_PER_KILL: int = 30

SECONDS_PER_MINUTE: int = 60


# ─── The task item ──────────────────────────────────────────────────────────
# The ItemDef key of the item that opens the task pop-up. A Preceptor gives
# one free. Its display name is TBD.
TASK_WRIT_ITEM_KEY: str = "task_writ"


# ─── The `task` command ─────────────────────────────────────────────────────
TASK_COMMAND_KEY: str = "task"
TASK_ARG_NEW: str = "new"
TASK_ARG_SKIP: str = "skip"
TASK_ARG_WRIT: str = "writ"

# Whole commands, for an action row and for a dialogue option.
TASK_NEW_COMMAND: str = f"{TASK_COMMAND_KEY} {TASK_ARG_NEW}"
TASK_SKIP_COMMAND: str = f"{TASK_COMMAND_KEY} {TASK_ARG_SKIP}"
TASK_WRIT_COMMAND: str = f"{TASK_COMMAND_KEY} {TASK_ARG_WRIT}"


# ─── Message templates ──────────────────────────────────────────────────────
MSG_NO_TASK = "You have no Exterminator task. A Preceptor gives you one."

MSG_TASK_LINE = "Task: kill {total} {plural}. {kills}/{total} done."
MSG_STREAK_LINE = "Streak: {streak}. Points: {points}."

MSG_TASK_ASSIGNED = (
    f"{HIGHLIGHT_COLOR}[NEW TASK] {{preceptor}} tells you to kill {{total}} "
    f"{{plural}}.{RESET_COLOR}"
)

MSG_TASK_KILL = "Task: {kills}/{total} {plural}."

MSG_TASK_COMPLETE = (
    f"{SUCCESS_COLOR}[TASK COMPLETE] You killed {{total}} {{plural}}. "
    f"+{{points}} points. Streak: {{streak}}.{RESET_COLOR}"
)

MSG_TASK_SKIPPED = (
    f"{ERROR_COLOR}[TASK SKIPPED] You pay {{cost}} points. Your streak "
    f"ends.{RESET_COLOR}"
)

MSG_SKIP_TOO_FEW_POINTS = (
    f"{ERROR_COLOR}A skip costs {{cost}} points. You have "
    f"{{points}}.{RESET_COLOR}"
)

MSG_ALREADY_HAS_TASK = (
    f"{ERROR_COLOR}You already have a task. Finish it or skip it "
    f"first.{RESET_COLOR}"
)

MSG_NO_TASK_FOR_LEVEL = (
    f"{ERROR_COLOR}{{preceptor}} has no task for your Exterminator "
    f"level.{RESET_COLOR}"
)

MSG_PRECEPTOR_LEVEL_TOO_LOW = (
    f"{ERROR_COLOR}{{preceptor}} teaches only an Exterminator of level "
    f"{{level}} or more.{RESET_COLOR}"
)

MSG_NO_PRECEPTOR_HERE = f"{ERROR_COLOR}No Preceptor is here.{RESET_COLOR}"

MSG_WRIT_GIVEN = f"{SUCCESS_COLOR}{{preceptor}} gives you a {{item}}.{RESET_COLOR}"
MSG_WRIT_ALREADY = "You already carry a {item}."

MSG_BUFF_GAINED = f"{SUCCESS_COLOR}You learn {{buff}}.{RESET_COLOR}"
MSG_BUFF_NEEDS_TASK = f"{ERROR_COLOR}A buff needs a task.{RESET_COLOR}"
MSG_BUFF_ALREADY_HELD = "You already hold {buff}."
MSG_BUFF_UNKNOWN = f"{ERROR_COLOR}No buff is called {{buff}}.{RESET_COLOR}"

TASK_ARG_PICK: str = "pick"
TASK_PICK_COMMAND: str = f"{TASK_COMMAND_KEY} {TASK_ARG_PICK}"

MSG_PICKS_LINE = "Picks waiting: {banked}."
MSG_HELD_BUFFS_LINE = "Buffs: {buffs}."
MSG_HELD_BUFF = "{name} ({rarity})"
HELD_BUFF_SEPARATOR = ", "

MSG_POINTS_BONUS = f"{SUCCESS_COLOR}Your buffs add {{bonus}} points.{RESET_COLOR}"
MSG_CARD_LINE = "{index}. {name} ({rarity}): {description}"
MSG_CONFLICT_WINS = "Against your task, it replaces the {seam} of {rival}."
MSG_CONFLICT_LOSES = "{rival} keeps its {seam}. This buff does nothing there."

MSG_PICK_EARNED = f"{HIGHLIGHT_COLOR}[PICK] A buff waits for you. Type `task pick`.{RESET_COLOR}"
MSG_NO_PICK = f"{ERROR_COLOR}You have no buff to pick.{RESET_COLOR}"
MSG_NO_CARDS = "Your Preceptor has no buff to offer you now."
MSG_BAD_CARD = f"{ERROR_COLOR}Pick a card from 1 to {{count}}.{RESET_COLOR}"

MSG_TASK_USAGE = (
    "Usage: task | task new | task skip | task writ | task pick [n]. "
    "`task new` and `task writ` need a Preceptor here."
)
