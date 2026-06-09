"""
systems/quests/content/quest_lone_android_intro.py

Quest name: Oasis
Description: Starter quest designed to introduce players to basic quest mechanics and the game's setting.

"""



from systems.quests.quests import QuestBlueprint, QuestStep



def award_rewards(character):
    character.skills.add_xp("cutting", 150)
    character.skills.add_xp("[CRAFTING_SKILL]", 100)

    # Permanent ownership validation for the player-crafted makeshift weapon
    # (Note: Assumes the weapon was spawned and assigned to `character.db.weapon` 
    # during the crafting phase trigger; we validate it permanently here).
    # if hasattr(character.db, "weapon"):
    #     character.db.weapon_ownership_validated = True

    character.msg("|g[QUEST AWARD TEXT].|n")



# defining the quest locally
OASIS = QuestBlueprint(
    key="oasis",
    title="Oasis",
    description=(
        # "You awaken in the blistering heat of the Sahara desert, stripped of your belongings "
        # "and completely disoriented. Ahead lies a small, impossibly green sanctuary tended by a "
        # "solitary synthetic caretaker. If you hope to survive the wastes and secure passage to "
        # "the neon walls of Neo Cairo, you must first earn this android's trust by keeping its "
        # "fragile haven alive."
        "An android lives in the wastes of the Sahara, just outside Neo Cairo. It tends a farm, "
        "which is some of the only green that exists there. The android lives completely alone. "
        "It was once a farm hand, and it does not know what else to do. Seems awfully futile..."
    ),
    steps=[
        QuestStep(
            key="intro",
            description="Regain your bearings and initiate contact with the lone android tending the farm.",
            targets={"talk:lone_android": True}
        ),
        # EXAMPLES
        # QuestStep(
        #     key="maintenance",
        #     description="Complete daily agricultural chores to understand basic survival mechanics: clear out the sand-clogged drainage pipe and analyze the oasis soil.",
        #     targets={"interact:pipe": True, "interact:soil": True}
        # ),
        # QuestStep(
        #     key="combat_bottleneck",
        #     description="Scavenge parts from your chores to assemble a rudimentary weapon, then stand your ground against incoming desert raiders targeting the oasis.",
        #     targets={"craft:weapon": True, "kill:raider": 1}
        # ),
        # QuestStep(
        #     key="resolution",
        #     description="Speak with the lone android amidst the dust of the repelled raiding party to secure your navigation route to the city.",
        #     targets={"talk:lone_android_end": True}
        # )
    ],
    rewards_callback=award_rewards
)



# Expose a unified list for the dynamic loader to grab
QUESTS = [
    OASIS,
]