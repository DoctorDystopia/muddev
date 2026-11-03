"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The Augmentation intro quest (DESIGN-0015, Phase 4). It takes
             the player from the Augmentation Clinic to the Public Hospital,
             teaches the graft, and pays the first samples and the first
             levels.

EVERY NAME AND EVERY LINE HERE IS A PLACEHOLDER. Nick owns the story, the
lore, and the names (10/30/2026). The two NPCs are NPC_AUG_CLINIC_1 and
NPC_AUG_HOSPITAL_1 until he names them. The outline is his, from the vault
note of the skill: the Clinic and the Hospital are small rivals, the Clinic
gets the Hegemony funding, the Clinic recruits the player to find the
missing augments, and the trail ends at the Hospital, which steals out of
need and is sympathetic.

Design lives in the Obsidian vault, not here:
    03_Systems/Skills/Combat Skills/Augmentation_Skill.md

The two dialogues are world/npc_dialogues/aug_clinic_1.py and
aug_hospital_1.py. This module owns only what is TRUE about the quest: its
steps, what satisfies them, and what it pays.
"""

from world.item_database import ITEM_DB

from systems.gameplay.augmentation import constants as aug_const
from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.progression.skills import xp_awards
from systems.gameplay.quests import constants as quest_constants
from systems.gameplay.quests.quests import QuestBlueprint, QuestStep, normalize_target
from systems.interface.ui.colors import highlight as _hl
from systems.interface.statefeed import constants as feed_const


# Every line this module sends a player is about a quest, so the routing tag
# is bound one time here.
_MSG_QUEST = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_QUEST}


# Public constant definitions
QUEST_KEY = "augmentation_intro"
QUEST_TITLE = "Augmentation Intro"

# The two NPCs, as placeholders. The npc keys are the keys of the NpcDefs in
# world/npc_defs/augmentation.py, and the dialogue modules import them from
# here, so the three cannot spell a key differently.
NPC_CLINIC_KEY = "npc_aug_clinic_1"
NPC_CLINIC_NAME = "NPC_AUG_CLINIC_1"
NPC_HOSPITAL_KEY = "npc_aug_hospital_1"
NPC_HOSPITAL_NAME = "NPC_AUG_HOSPITAL_1"

# Step keys. The dialogues gate every node on these.
STEP_RECRUIT = "recruit"
STEP_TRAIL = "trail"
STEP_GRAFT = "graft"
STEP_REPORT = "report"

# The talk targets. The Clinic NPC is two targets, as the android is: one
# at the start and one at the end.
TARGET_TALK_CLINIC = normalize_target(quest_constants.ACTION_TALK, NPC_CLINIC_KEY)
TARGET_TALK_HOSPITAL = normalize_target(quest_constants.ACTION_TALK, NPC_HOSPITAL_KEY)
TARGET_TALK_CLINIC_END = normalize_target(
    quest_constants.ACTION_TALK, f"{NPC_CLINIC_KEY}_end")

# The graft target names the sample KIND, not one item. The Hospital hands
# the player one biological sample, and any biological sample satisfies the
# step: a player who grafts a gland of their own before they graft the gift
# has still learned the verb.
TARGET_GRAFT = normalize_target(quest_constants.ACTION_GRAFT, aug_const.SAMPLE_KIND_BIO)

# The sample that the Hospital gives at the graft step, and the samples
# that the Clinic pays at the end. The first biological sample today.
TEACHING_SAMPLE_KEY = "mutant_gland"
REWARD_SAMPLE_KEY = "mutant_gland"
REWARD_SAMPLE_COUNT = 3

# What the quest pays in XP. A placeholder until Nick tunes it.
REWARD_XP = {
    skill_constants.SKILL_KEY_AUGMENTATION: 300,
}


def grant_teaching_sample(character: object, step: object) -> None:
    """
    Purpose: Hand the player the sample that the graft lesson needs.

    Entry:
        character is the Character entering the graft step.
        step is the QuestStep being entered (unused).

    Exit/Returns:
        No conditions. Does nothing if the player already carries a sample
        of the kind, so a retaken quest does not stack gifts.

    Module Globals:
        TEACHING_SAMPLE_KEY read. ITEM_DB read.

    Methodology:
        The on_enter hook of the graft step, as the android's hammer is the
        on_enter hook of its craft step. The guard reads the sample kind
        attribute, not the typeclass, so a gland from a kill counts.

    Notes/References:
        ItemDef.create spawns detached and then moves, which registers the
        item in a bag slot (CLAUDE.md).

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    wanted_kind = ITEM_DB[TEACHING_SAMPLE_KEY].sample_kind

    already_held = any(
        item.attributes.get(aug_const.SAMPLE_KIND_ATTR, default=None) == wanted_kind
        for item in character.contents
    )

    if already_held:
        return

    ITEM_DB[TEACHING_SAMPLE_KEY].create(location=character, home=character)


def award_rewards(character: object) -> None:
    """
    Purpose: Pay out the quest on completion.

    Entry:
        character is the Character who finished the quest.

    Exit/Returns:
        No conditions.

    Module Globals:
        REWARD_XP, REWARD_SAMPLE_KEY, REWARD_SAMPLE_COUNT read.

    Methodology:
        The samples first, then the XP. The award is its own readout line,
        below the closing narration and above any level-up it causes:
        announced, then granted, as every award is.

        The samples need a database row to land in. test_quest_content runs
        every reward callback against a stub with no row, so a recipient
        with no `pk` gets the XP and the line, and no item. The playthrough
        test of this quest covers the samples with a real character.

    Notes/References:
        The closing line is a placeholder. Nick writes it.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    awards = list(REWARD_XP.items())
    is_a_row = getattr(character, "pk", None) is not None

    if is_a_row:
        ITEM_DB[REWARD_SAMPLE_KEY].create(
            location=character, home=character, quantity=REWARD_SAMPLE_COUNT)

    character.msg((_hl(
        f"{NPC_CLINIC_NAME} pays you {REWARD_SAMPLE_COUNT} samples for the "
        "report. Placeholder closing line."
    ), _MSG_QUEST))
    character.msg((xp_awards.format_xp_readout(awards), _MSG_QUEST))

    xp_awards.grant_xp(character, awards, feed_const.MESSAGE_TYPE_QUEST)


QUEST_BLUEPRINT_AUGMENTATION_INTRO = QuestBlueprint(
    key=QUEST_KEY,
    title=QUEST_TITLE,
    description=(
        f"Placeholder. {NPC_CLINIC_NAME} of the Augmentation Clinic asks "
        "you to find out who takes the augments from the Clinic. The trail "
        f"leads to {NPC_HOSPITAL_NAME} at the Public Hospital."
    ),
    steps=[
        QuestStep(
            key=STEP_RECRUIT,
            description=(
                f"Placeholder. Hear {NPC_CLINIC_NAME} out at the Augmentation "
                "Clinic."
            ),
            targets={TARGET_TALK_CLINIC: True},
            objectives={TARGET_TALK_CLINIC: f"Speak with {NPC_CLINIC_NAME}"},
        ),
        QuestStep(
            key=STEP_TRAIL,
            description=(
                f"Placeholder. Follow the trail to {NPC_HOSPITAL_NAME} at the "
                "Public Hospital."
            ),
            targets={TARGET_TALK_HOSPITAL: True},
            objectives={TARGET_TALK_HOSPITAL: f"Speak with {NPC_HOSPITAL_NAME}"},
        ),
        QuestStep(
            key=STEP_GRAFT,
            description=(
                f"Placeholder. Graft the sample that {NPC_HOSPITAL_NAME} gave "
                "you."
            ),
            targets={TARGET_GRAFT: True},
            objectives={TARGET_GRAFT: "Graft a biological sample"},
            on_enter=grant_teaching_sample,
        ),
        QuestStep(
            key=STEP_REPORT,
            description=(
                f"Placeholder. Report to {NPC_CLINIC_NAME} at the Clinic."
            ),
            targets={TARGET_TALK_CLINIC_END: True},
            objectives={TARGET_TALK_CLINIC_END: f"Report to {NPC_CLINIC_NAME}"},
        ),
    ],
    rewards_callback=award_rewards,
)


# Expose a unified list for the dynamic loader to grab
QUESTS = [
    QUEST_BLUEPRINT_AUGMENTATION_INTRO,
]
