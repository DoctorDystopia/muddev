"""
systems/quests/quests.py

The quest module defines the Quest class, which represents a quest that a character can undertake in the game.
Quests can have multiple steps, each with specific objectives and rewards.

Use the Quest class to create new quests and assign them to characters as needed.

"""



from systems.quests.loader import GLOBAL_QUEST_REGISTRY



# class QuestStep:
#     """
#     Base structural unit of a quest phase.
#     """

#     def __init__(self, key, description, targets=None):
#         self.key = key
#         self.description = description
#         self.targets = targets or {} # e.g., {"silt_pipe_cleared": True} or {"raiders_killed": 3}

# systems/quests/quests.py

class QuestStep:
    """
    Base structural unit of a quest phase supporting parameterized targets.
    """

    def __init__(self, key, description, targets=None):
        self.key = key
        self.description = description
        
        # Normalize keys: Converts ("met_npc", "android") -> "met_npc:android"
        self.targets = {}
        if targets:
            for k, v in targets.items():
                normalized_key = f"{k[0]}:{k[1]}" if isinstance(k, tuple) else k
                self.targets[normalized_key] = v



class QuestBlueprint:
    """
    Static template containing steps, descriptions, and rewards.
    """

    def __init__(self, key, title, description, steps, rewards_callback=None):
        self.key = key
        self.title = title
        self.description = description
        self.steps = steps  # List of QuestStep objects
        self.rewards_callback = rewards_callback



class QuestHandler:
    """
    Manages active state progress and completed keys for a character.
    Persists data cleanly inside `obj.db.active_quests` and `obj.db.completed_quests`.
    """


    def __init__(self, obj):
        self.obj = obj

        if not self.obj.db.active_quests:
            self.obj.db.active_quests = {}

        if not self.obj.db.completed_quests:
            self.obj.db.completed_quests = []


    def accept_quest(self, quest_key):
        """
        Accepts a quest using its unique string identifier.
        """

        blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)

        if not blueprint:
            self.obj.msg(f"|rError: Quest '{quest_key}' could not be found in the game world.|n")
            return False
            
        if quest_key in self.obj.db.completed_quests or quest_key in self.obj.db.active_quests:
            return False
        
        self.obj.db.active_quests[quest_key] = {
            "step_index": 0,
            "progress_data": {k: 0 for k in blueprint.steps[0].targets.keys()}
        }

        self.obj.msg(f"|y[NEW QUEST] {blueprint.title}|n\n{blueprint.description}")

        return True


    # def update_progress(self, quest_key, target_key, amount=1):
    #     """
    #     Updates objective counters for an active quest instance by key.
    #     """

    #     blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)
    #     if not blueprint or quest_key not in self.obj.db.active_quests:
    #         return

    #     active_data = self.obj.db.active_quests[quest_key]
    #     current_step = blueprint.steps[active_data["step_index"]]

    #     if target_key in active_data["progress_data"]:
    #         target_requirement = current_step.targets[target_key]
            
    #         if isinstance(target_requirement, bool):
    #             active_data["progress_data"][target_key] = True
    #         else:
    #             active_data["progress_data"][target_key] += amount
            
    #         self.obj.db.active_quests[quest_key] = active_data
    #         self._check_step_completion(blueprint)

    def update_progress(self, quest_key, action, argument=None, amount=1):
        """
        Updates objective counters using generic actions and specific arguments.
        Example: handler.update_progress("oasis", "met_npc", "android")
        """

        blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)
        if not blueprint or quest_key not in self.obj.db.active_quests:
            return

        active_data = self.obj.db.active_quests[quest_key]
        current_step = blueprint.steps[active_data["step_index"]]

        # Construct the internal compound key dynamically
        target_key = f"{action}:{argument}" if argument else action

        if target_key in active_data["progress_data"]:
            target_requirement = current_step.targets[target_key]
            
            if isinstance(target_requirement, bool):
                active_data["progress_data"][target_key] = True
            else:
                active_data["progress_data"][target_key] += amount
            
            # Commit changes to Evennia's persistent layer
            self.obj.db.active_quests[quest_key] = active_data
            self._check_step_completion(blueprint)


    def _check_step_completion(self, quest_blueprint):
        """
        Evaluates whether the active step's condition arrays evaluate fully.
        """

        q_key = quest_blueprint.key
        active_data = self.obj.db.active_quests[q_key]
        current_step = quest_blueprint.steps[active_data["step_index"]]

        # Verify all targeted values match or exceed criteria
        step_complete = True

        for target, req_val in current_step.targets.items():
            current_val = active_data["progress_data"].get(target, 0)

            if isinstance(req_val, bool):
                if current_val != req_val:
                    step_complete = False
            elif current_val < req_val:
                step_complete = False

        if step_complete:
            if active_data["step_index"] + 1 < len(quest_blueprint.steps):
                # Move to next phase sequential step
                active_data["step_index"] += 1
                next_step = quest_blueprint.steps[active_data["step_index"]]
                active_data["progress_data"] = {k: 0 for k in next_step.targets.keys()}
                self.obj.db.active_quests[q_key] = active_data
                self.obj.msg(f"|y[QUEST UPDATE] Phase completed! Next: {next_step.description}|n")
            else:
                # Total pipeline resolved
                self.complete_quest(quest_blueprint)


    def complete_quest(self, quest_blueprint):
        """
        Fires off conditional hooks/rewards and locks the tracking instance.
        """

        q_key = quest_blueprint.key
        if q_key in self.obj.db.active_quests:
            del self.obj.db.active_quests[q_key]
        
        if q_key not in self.obj.db.completed_quests:
            self.obj.db.completed_quests.append(q_key)
            
        self.obj.msg(f"|g[QUEST COMPLETE] You have completed: {quest_blueprint.title}!|n")
        if quest_blueprint.rewards_callback:
            quest_blueprint.rewards_callback(self.obj)