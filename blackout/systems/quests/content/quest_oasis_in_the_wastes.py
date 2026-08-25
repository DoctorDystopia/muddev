"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/13/2026
Description: "Oasis in the Wastes" -- the game's opening quest. Teaches the
             Cutting -> Foundry -> Metalsmith loop, then asks the player to
             use what they made.

Design lives in the Obsidian vault, not here:
    04_Content/Quests_and_Adventures/Full Quest List/
    Oasis in the Wastes (name TBD) [AI-EDITABLE].md

The android's side of every beat is in
systems/menus/npc_dialogues/npc_oasis_guide.py. This module owns only what is
TRUE about the quest -- its phases, what satisfies them, and what it pays.
"""

from world.item_database import ITEM_DB

from systems.quests.quests import QuestBlueprint, QuestStep
from systems.ui.colors import highlight as _hl



# Public constant definitions
QUEST_KEY = "oasis_in_the_wastes"
QUEST_TITLE = "Oasis in the Wastes"

# Step keys. The dialogue gates every node on these, so they are named here
# and imported there rather than spelled twice.
STEP_INTRO = "intro"
STEP_MAINTENANCE = "maintenance"
STEP_APPRENTICESHIP = "apprenticeship"
STEP_DEFENSE = "defense"
STEP_RESOLUTION = "resolution"

# The two things the player must forge. Both are metalsmith level 0 and cost
# one scrap apiece, which is the only pair a character who started this quest
# with nothing can actually reach.
#
# The vault doc says "Rusty Scrap Axe and Sword". The sword it means is the
# rusty scrap shortsword -- metalsmith level 4, two scrap -- which a level-0
# character cannot make, so the dagger stands in as the first weapon. Flagged
# for the design doc rather than silently reinterpreted.
RECIPE_AXE = "rusty scrap axe"
RECIPE_DAGGER = "rusty scrap dagger"

# What the android is teaching, and what the quest pays out for having
# learned it.
REWARD_XP = {
    "cutting": 150,
    "foundry": 150,
    "metalsmith": 100,
}

# The hammer the android lends the player for the Foundry/Metalsmith lesson.
# Every metalsmith recipe needs one and a new character has none; the only
# other source is the oasis shop, which wants credits they do not have. Not in
# the vault doc -- added here because the step is otherwise impossible.
TEACHING_TOOL_ITEM_KEY = "hammer"



def grant_teaching_tool(character: object, step: object) -> None:
    """
    Purpose: Hand the player the hammer the crafting lesson requires.

    Entry:
        character is the Character entering the apprenticeship step.
        step is the QuestStep being entered (unused).

    Exit/Returns:
        No conditions. Does nothing if the player already holds a hammer.

    Module Globals:
        TEACHING_TOOL_ITEM_KEY read.
        ITEM_DB read.

    Methodology:
        Fired as the apprenticeship step's on_enter hook, so the tool arrives
        with the lesson rather than being scattered on the ground for anyone
        to find.

        Guarded on the player already carrying a hammer: a step hook runs on
        entry, and a player who abandoned and retook the quest would otherwise
        accumulate them.

        The guard reads db.tool_type rather than the typeclass, matching how
        Cutting._has_tool looks for an axe -- a player who already bought a
        hammer from the oasis shop should not be handed a second one just
        because it is a different object.

    Notes/References:
        ItemDef.create spawns detached and then moves, which is what makes the
        item register in an inventory slot -- create_object(location=...) does
        not fire at_object_receive. See CLAUDE.md.

    Author: Nick Hobar
    Creation date: 08/25/2026
    """
    tool_type = ITEM_DB[TEACHING_TOOL_ITEM_KEY].tool_type

    already_held = any(
        getattr(item.db, "tool_type", None) == tool_type
        for item in character.contents
    )

    if already_held:
        return

    ITEM_DB[TEACHING_TOOL_ITEM_KEY].create(location=character,
                                           home=character)



def award_rewards(character: object) -> None:
    """
    Purpose: Pay out the quest on completion.

    Entry:
        character is the Character who finished the quest.

    Exit/Returns:
        No conditions.

    Module Globals:
        REWARD_XP read.

    Methodology:
        XP into the three skills the android actually taught, driven off the
        REWARD_XP table rather than three literal calls. The player keeps the
        axe and dagger they forged -- those are the reward the quest is
        named for, and they are already in the player's hands, so nothing is
        granted here.

    Notes/References:
        This used to call add_xp("[CRAFTING_SKILL]", 100) and message
        "[QUEST AWARD TEXT]" -- authoring placeholders that shipped.
        test_quest_content.py now runs every reward callback and fails on
        either.

    Author: Nick Hobar
    Creation date: 07/13/2026
    """
    for skill_key, amount in REWARD_XP.items():
        character.skills.add_xp(skill_key, amount)

    character.msg(_hl(
        "The android transmits a route east, out of the sand and toward the "
        "lights. You leave knowing how to cut, to smelt, and to forge."
    ))



QUEST_BLUEPRINT_OASIS_IN_THE_WASTES = QuestBlueprint(
    key=QUEST_KEY,
    title=QUEST_TITLE,
    description=(
        "You woke in the Sahara with nothing -- no gear, no bearings, and no "
        "clear memory of arriving. There is green ahead of you, which there "
        "should not be: a farm, kept alive by one android that has been "
        "tending it alone since the Blackout because nobody ever told it to "
        "stop. It will trade you the road to Neo Cairo for a day's work."
    ),
    steps=[
        QuestStep(
            key=STEP_INTRO,
            description=(
                "Get the android's attention and find out where you are."
            ),
            targets={"talk:lone_android": True},
            objectives={"talk:lone_android": "Speak with the lone android"},
        ),
        QuestStep(
            key=STEP_MAINTENANCE,
            description=(
                "Work the farm: clear the sand out of the drainage pipe and "
                "get the new varietal into the soil."
            ),
            targets={
                "interact:pipe": True,
                "interact:soil": True,
            },
            objectives={
                "interact:pipe": "Clear the drainage pipe",
                "interact:soil": "Plant the new orange varietal",
            },
        ),
        QuestStep(
            key=STEP_APPRENTICESHIP,
            description=(
                "Learn the trade the hard way: tear scrap from a rusty pole, "
                "smelt it at the furnace, and beat it into an axe and a "
                "blade at the anvil."
            ),
            targets={
                f"craft:{RECIPE_AXE}": True,
                f"craft:{RECIPE_DAGGER}": True,
            },
            objectives={
                f"craft:{RECIPE_AXE}": "Forge a rusty scrap axe",
                f"craft:{RECIPE_DAGGER}": "Forge a rusty scrap dagger",
            },
            on_enter=grant_teaching_tool,
        ),
        QuestStep(
            key=STEP_DEFENSE,
            description=(
                "Raiders have come for the farm. Put down the one that gets "
                "through."
            ),
            targets={"kill:mutant_raider": 1},
            objectives={"kill:mutant_raider": "Mutant raiders repelled"},
        ),
        QuestStep(
            key=STEP_RESOLUTION,
            description=(
                "Go back to the android and collect what you were promised."
            ),
            targets={"talk:lone_android_end": True},
            objectives={"talk:lone_android_end": "Speak with the android again"},
        ),
    ],
    rewards_callback=award_rewards,
)



# Expose a unified list for the dynamic loader to grab
QUESTS = [
    QUEST_BLUEPRINT_OASIS_IN_THE_WASTES,
]
