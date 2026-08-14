"""
typeclasses/characters.py

Characters are (by default) Objects setup to be puppeted by Accounts.
They are what you "see" in game. The Character class in this module
is setup to be the "default" character type created by the default
creation commands.

"""



import time

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
from systems.statefeed import resync



# ─── Playtime accounting ────────────────────────────────────────────────────
# Evennia keeps no CUMULATIVE playtime figure, so the Character owns one. The
# summary screen reads it; nothing else writes it.
#
# ServerSession.conn_time is not the thing being reimplemented here. It is the
# current connection's start time, reset by at_login on every reconnect and
# belonging to a session rather than to a character -- it can answer "how long
# has this session been up", never "how long has this character been played".

# Persistent total, in seconds, of every COMPLETED puppet session.
PLAYTIME_TOTAL_ATTR = "total_playtime"

# Unix timestamp stamped at puppet, cleared at unpuppet. A db attribute rather
# than ndb, and the reason is specific: @reload does NOT unpuppet anyone.
# ServerSession.at_sync re-attaches the puppet from session.puid explicitly
# "without any hooks", so neither at_post_unpuppet nor at_post_puppet fires
# across a reload. A db stamp therefore survives untouched and the session
# keeps accumulating; an ndb stamp would be wiped, and every reload -- which on
# this project is many per hour -- would silently discard the time since the
# last one.
PLAYTIME_SESSION_START_ATTR = "_playtime_session_start"


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


    # ─── Playtime ───────────────────────────────────────────────────────────

    @property
    def playtime_seconds(self) -> int:
        """
        Purpose: Total seconds this character has been played, including the
        session currently in progress.

        Entry:
            None.

        Exit/Returns:
            Returns an integer number of seconds. A character that has never
            been puppeted returns 0.

        Module Globals:
            PLAYTIME_TOTAL_ATTR, PLAYTIME_SESSION_START_ATTR read.

        Methodology:
            Banked total plus the elapsed time since the current puppet stamp,
            if there is one. Computing the live portion on READ rather than
            ticking it into the database means no timer, no Script, and no
            write on any path other than unpuppet.

            A stale start stamp -- left behind by a hard crash that skipped
            at_post_unpuppet -- would inflate this reading until the next clean
            unpuppet banks it. at_post_puppet overwrites the stamp rather than
            adding to it, so the error cannot compound across sessions.

        Notes/References:
            The cost of a crash is therefore at most one session's worth of
            playtime, misreported until the next login. Accepted rather than
            defended against with a periodic flush.

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        banked = self.attributes.get(PLAYTIME_TOTAL_ATTR, default=0) or 0
        started_at = self.attributes.get(PLAYTIME_SESSION_START_ATTR, default=None)

        if started_at is None:
            return int(banked)

        elapsed = time.time() - started_at

        if elapsed < 0:
            elapsed = 0

        total = int(banked + elapsed)

        return total


    def at_post_puppet(self, **kwargs) -> None:
        """
        Purpose: Stamp the start of a play session, push the world to any
        graphical client, then run default puppet behaviour.

        Entry:
            Called by Evennia when an Account takes control of this character.

        Exit/Returns:
            No conditions.

        Module Globals:
            PLAYTIME_SESSION_START_ATTR written.

        Methodology:
            Overwrite rather than preserve any existing stamp -- see the note
            on stale stamps in playtime_seconds. Guarded so that a failure here
            can never block a player from logging in.

            The state-feed snapshot is pushed HERE because this is the only
            moment the server knows a session has taken control of a character.
            A graphical client subscribes as soon as its socket opens, which is
            before it has logged in -- at that point ServerSession.at_sync has
            already run and send_full_state had no puppet to describe. Without
            this call the client sits subscribed to a world it will not be sent
            until it happens to walk somewhere.

        Notes/References:
            send_full_state swallows and logs its own failures and is a no-op
            for a session with no subscriptions, so this costs a telnet player
            one function call.

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        try:
            self.attributes.add(PLAYTIME_SESSION_START_ATTR, time.time())
        except Exception as exc:
            logger.log_err(f"Character.at_post_puppet playtime stamp failed: {exc!r}")

        resync.send_full_state(self)

        parent_class = super()
        parent_class.at_post_puppet(**kwargs)


    def _bank_playtime(self) -> None:
        """
        Purpose: Fold the in-progress session into the persistent total.

        Entry:
            None. Safe to call when no session stamp is present.

        Exit/Returns:
            No conditions. After this call the session stamp is cleared, so a
            second call cannot double-count the same session.

        Module Globals:
            PLAYTIME_TOTAL_ATTR, PLAYTIME_SESSION_START_ATTR read and written.

        Methodology:
            Read the stamp, add the elapsed time, remove the stamp. Clearing
            the stamp is what makes this idempotent -- at_post_unpuppet fires
            once per session normally, but a disconnect racing a manual
            unpuppet would otherwise bank the same interval twice.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        started_at = self.attributes.get(PLAYTIME_SESSION_START_ATTR, default=None)

        if started_at is None:
            return

        elapsed = time.time() - started_at

        if elapsed < 0:
            elapsed = 0

        banked = self.attributes.get(PLAYTIME_TOTAL_ATTR, default=0) or 0
        self.attributes.add(PLAYTIME_TOTAL_ATTR, int(banked + elapsed))
        self.attributes.remove(PLAYTIME_SESSION_START_ATTR)


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

            The playtime bank rides here for the same reason the combat
            cleanup does: this is the one hook that fires on every way a
            session ends. Both are guarded independently so a failure in
            either cannot swallow the other or the parent hook.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 07/26/2026
        """
        try:
            self.at_disconnect_combat_cleanup()
        except Exception as exc:
            logger.log_err(f"Character.at_post_unpuppet combat cleanup failed: {exc!r}")

        try:
            self._bank_playtime()
        except Exception as exc:
            logger.log_err(f"Character.at_post_unpuppet playtime bank failed: {exc!r}")

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