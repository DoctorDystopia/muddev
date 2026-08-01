"""
typeclasses/characters.py

Characters are (by default) Objects setup to be puppeted by Accounts.
They are what you "see" in game. The Character class in this module
is setup to be the "default" character type created by the default
creation commands.

"""



from evennia import DefaultCharacter
from evennia.contrib.game_systems.cooldowns import CooldownHandler
from evennia.utils import logger
from evennia.utils.utils import lazy_property

from .mixins import CombatEntity
from .objects import ObjectParent
from systems.progression.skills.handler import SkillHandler
from systems.banking.handler import BankHandler
from items.equipment.handler import EquipmentHandler
from items.inventory.handler import InventoryHandler
from systems.quests.quests import QuestHandler



def _handler_property(handler_class: type, attr_name: str):
    """
    Purpose: Build a lazy, cached accessor that attaches `handler_class` to
    the character on first use.

    Entry:
        handler_class is a handler taking the character as its only argument.
        attr_name is the attribute name the accessor is bound to.

    Exit/Returns:
        Returns a lazy_property descriptor.

    Module Globals:
        None

    Methodology:
        The five handler accessors were five identical copies of "log, then
        construct". `name=attr_name` is passed explicitly because
        lazy_property caches into obj.__dict__ under its __name__ -- letting
        it default would key every accessor built here as the inner
        function's name and make them collide. Combat also pops that cache
        entry by name (see systems/combat/combat.py), so the key must stay
        exactly the attribute name.

    Notes/References:
        A plain @property would rebuild the handler on every access; in a
        combat loop reading a skill many times per second that is a lot of
        short-lived objects.

    Author: Nick Hobar
    Creation date: 06/02/2026
    """
    def accessor(self):
        logger.log_info(f"Accessing {attr_name} for character: {self.key}")
        return handler_class(self)

    return lazy_property(
        accessor,
        name=attr_name,
        doc=f"Cached {handler_class.__name__} for this character.",
    )


class Character(CombatEntity, ObjectParent, DefaultCharacter):
    """
    The Character just re-implements some of the Object's methods and hooks
    to represent a Character entity in-game.

    The baseline character representation for project Blackout.
    """
    
    # Cached handler accessors. Built by _handler_property so the five share
    # one definition; see that function for why the cache name is explicit.
    # A standard @property would rebuild the handler on every access -- in a
    # combat loop reading a skill many times per second that is a lot of
    # short-lived objects for the collector to reap.
    skills = _handler_property(SkillHandler, "skills")
    equipment = _handler_property(EquipmentHandler, "equipment")
    inventory = _handler_property(InventoryHandler, "inventory")
    bank = _handler_property(BankHandler, "bank")
    quests = _handler_property(QuestHandler, "quests")

    # Evennia's contrib cooldown handler. Stores absolute expiry timestamps in
    # a persistent Attribute, so unlike the ndb timestamp it replaces, a
    # cooldown survives @reload. Poll-based -- nothing ticks.
    cooldowns = _handler_property(CooldownHandler, "cooldowns")


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
        logger.log_info(f"Creating character: {self.key}")

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

        # Touch each lazy handler once so its backing db attributes are
        # written at creation rather than on first in-game use. The return
        # values are deliberately unused.
        self.skills
        self.quests
        self.equipment
        self.inventory
        self.cooldowns


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