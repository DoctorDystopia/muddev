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

from .mixins import CombatEntity
from .objects import ObjectParent
from systems.progression.skills.handler import SkillHandler
from systems.banking.handler import BankHandler
from items.equipment.handler import EquipmentHandler
from items.inventory.handler import InventoryHandler
from systems.quests.quests import QuestHandler



# class Character(ObjectParent, DefaultCharacter):
#     """
#     The Character just re-implements some of the Object's methods and hooks
#     to represent a Character entity in-game.

#     See mygame/typeclasses/objects.py for a list of
#     properties and methods available on all Object child classes like this.

#     """

#     pass



class Character(CombatEntity, ObjectParent, DefaultCharacter):
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
    def inventory(self) -> InventoryHandler:
        log_message = f"Accessing inventory for character: {self.key}"
        logger.log_info(log_message)
        print(log_message)

        new_inventory_handler = InventoryHandler(self)

        return new_inventory_handler

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

        # Fortitude is the one skill that does NOT start at DEFAULT_START_LEVEL (0).
        # init_combat_attrs then sets max_hp=hp=10.
        self.skills.seed_fortitude_on_creation()
        self.init_combat_attrs(max_hp=self.db.max_hp or 10)

        skills_prop = self.skills
        quests_prop = self.quests
        equipment_prop = self.equipment
        inventory_prop = self.inventory


    def at_post_unpuppet(self, account, session=None, **kwargs) -> None:
        """
        Purpose: Cleanup hook fired when a player disconnects. Relays to the
        CombatEntity mixin to release the player from any active combat.

        Entry:
            account is the Evennia Account that was puppeting this character.
            session is the optional session that closed.

        Exit/Returns:
            No conditions. Calls the parent hook so default cleanup still runs.

        Module Globals:
            None

        Methodology:
            Defensive relay to at_disconnect_combat_cleanup before super().
            Per research doc §"Architecting the Combat Handler": players
            disconnecting mid-combat must not be allowed to "combat-log"
            without resolving an escape mechanic.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/26/2026
        """
        try:
            self.at_disconnect_combat_cleanup()
        except Exception as exc:
            logger.log_err(f"Character.at_post_unpuppet combat cleanup failed: {exc!r}")

        parent_class = super()
        parent_class.at_post_unpuppet(account, session=session, **kwargs)


    def at_object_receive(self, moved_obj, source_location, move_type="move", **kwargs):
        if hasattr(moved_obj, "is_stackable"):
            try:
                self.inventory.add_item(moved_obj)
            except Exception:
                pass
        super().at_object_receive(moved_obj, source_location, move_type=move_type, **kwargs)


    def at_object_leave(self, moved_obj, target_location, move_type="move", **kwargs):
        if hasattr(moved_obj, "is_stackable"):
            try:
                self.inventory.remove_item(moved_obj)
            except Exception:
                pass
        super().at_object_leave(moved_obj, target_location, move_type=move_type, **kwargs)


    def at_object_delete(self) -> None:
        """
        Purpose: Called when the character object is about to be deleted.
        
        Entry:
            No conditions
            
        Exit/Returns:
            No conditions (cleanup is best-effort)
            
        Methodology:
            Cleans up the bank room if it exists.
        """
        bank_room = self.db._bank_room
        if bank_room is not None:
            try:
                bank_room.delete()
            except Exception:
                pass
            self.db._bank_room = None

        parent_class = super()
        parent_class.at_object_delete()