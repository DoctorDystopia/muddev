"""
typeclasses/characters.py

Characters are (by default) Objects setup to be puppeted by Accounts.
They are what you "see" in game. The Character class in this module
is setup to be the "default" character type created by the default
creation commands.

"""



from evennia import DefaultCharacter
from evennia.utils import logger
from evennia.utils.utils import lazy_property

from .objects import ObjectParent
from systems.progression.skills.handler import SkillHandler
from systems.banking.handler import BankHandler
from items.equipment.handler import EquipmentHandler
from systems.quests.quests import QuestHandler



# class Character(ObjectParent, DefaultCharacter):
#     """
#     The Character just re-implements some of the Object's methods and hooks
#     to represent a Character entity in-game.

#     See mygame/typeclasses/objects.py for a list of
#     properties and methods available on all Object child classes like this.

#     """

#     pass



class Character(ObjectParent, DefaultCharacter):
    """
    The Character just re-implements some of the Object's methods and hooks
    to represent a Character entity in-game.

    The baseline character representation for project Blackout.
    """
    
    # If we used a standard @property, Python would execute that instantiation every single time a script, combat loop, or command checked a skill.
    # If a player is in a fight and the system checks their melee skill 10 times a second, a standard property would create 10 brand-new SkillHandler
    # objects in memory every second, forcing Python's garbage collector to work overtime to clean them up.
    @lazy_property
    def skills(self) -> SkillHandler:
        """
        Purpose: Cached property accessor for decoupled skill handling operations.
        
        Entry:
            No conditions
            
        Exit/Returns:
            Returns an instantiated SkillHandler mapped to this character.
            
        Module Globals:
            None
            
        Methodology:
            Logs the access event to the server logs. Instantiates the external 
            SkillHandler, wrapping the current instance to allow lazy-loaded 
            database lookups.
            
        Notes/References:
            None
            
        Author: Nick Hobar
        Creation date: 06/02/2026
        """
        log_message = f"Accessing skills for character: {self.key}"
        logger.log_info(log_message)
        print(log_message)
        
        new_skill_handler = SkillHandler(self)
        
        return new_skill_handler
    

    @lazy_property
    def equipment(self):
        log_message = f"Accessing equipment for character: {self.key}"
        logger.log_info(log_message)
        print(log_message)
        
        new_equipment_handler = EquipmentHandler(self)
        
        return new_equipment_handler


    @lazy_property
    def bank(self) -> BankHandler:
        log_message = f"Accessing bank for character: {self.key}"
        logger.log_info(log_message)
        print(log_message)

        new_bank_handler = BankHandler(self)

        return new_bank_handler


    @lazy_property
    def quests(self) -> QuestHandler:
        """
        Purpose: Cached property accessor for decoupled quest handling operations.
        
        Entry:
            No conditions
            
        Exit/Returns:
            Returns an instantiated QuestHandler mapped to this character.
            
        Module Globals:
            None
            
        Methodology:
            Logs the access event to the server logs. Instantiates the external 
            QuestHandler, wrapping the current instance to allow lazy-loaded 
            database lookups.
            
        Notes/References:
            None
            
        Author: Nick Hobar
        Creation date: 06/02/2026
        """
        log_message = f"Accessing quests for character: {self.key}"
        logger.log_info(log_message)
        print(log_message)
        
        new_quest_handler = QuestHandler(self)
        
        return new_quest_handler


    def at_object_creation(self) -> None:
        """
        Purpose: Called once when the object is initially piped to the database layer.
        
        Entry:
            No conditions
            
        Exit/Returns:
            No conditions
            
        Module Globals:
            None
            
        Methodology:
            Logs the creation event to the server logs. Invokes the parent class 
            setup routine. Explicitly initializes the database attributes for skills 
            and quests using local variables to prevent embedded literals. Forces 
            the initial evaluation of the lazy properties to ensure the handler states
            are mapped into the Evennia database.
            
        Notes/References:
            None
            
        Author: Nick Hobar
        Creation date: 06/02/2026
        """
        log_message = f"Creating character: {self.key}"
        logger.log_info(log_message)
        print(log_message)
        
        parent_class = super()
        parent_class.at_object_creation()
        
        empty_skills_dict = {}
        empty_active_quests_dict = {}
        empty_completed_quests_list = []
        
        self.db.skills = empty_skills_dict
        self.db.active_quests = empty_active_quests_dict
        self.db.completed_quests = empty_completed_quests_list

        self.skills.init_all_skills()
        
        skills_prop = self.skills
        quests_prop = self.quests
        equipment_prop = self.equipment
        
        # _ = skills_prop
        # _ = quests_prop