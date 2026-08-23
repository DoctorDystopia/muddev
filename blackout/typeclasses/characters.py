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
from systems.statefeed import events as feed
from systems.statefeed import resync
from world.respawn import get_respawn_room



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


    # ─── Death ──────────────────────────────────────────────────────────────

    def respawn(self) -> None:
        """
        Purpose: Return a dead player to the respawn room at full HP.

        Entry:
            None. Called by CombatEntity.at_death, which has already
            broadcast the death line, rolled drops and torn this side of the
            fight down via leave_combat.

        Exit/Returns:
            No return value. Raises nothing: see Methodology.

        Module Globals:
            world.respawn.get_respawn_room read.

        Methodology:
            1. Resolve the respawn room. None means "unresolvable" -- already
               logged by get_respawn_room.
            2. Restore HP first, THEN move. A move fires at_object_receive on
               the destination and is the step that can fail; doing it second
               means a failed move still leaves a live player rather than a
               0 HP one standing where they died.
            3. Move quietly and message explicitly. The default move messaging
               would announce a routine arrival ("X arrives from the north"),
               which is wrong for a respawn -- there is no direction they came
               from, and at_death already told the old room what happened.

            The base CombatEntity.respawn refills HP in place, which was the
            only behaviour available while Blackout had no respawn-room fact.
            That is exactly what this degrades back to if the room cannot be
            resolved.

            No XP penalty. That is a deliberate scope decision recorded in
            docs/2026-08-23-DESIGN-0003 §1.4, not an omission -- a death
            penalty is a tuning question, and hostile retaliation had to land
            before there was anything to tune it against.

        Notes/References:
            Every failure path here is caught. This runs inside at_death: an
            exception escaping would abandon the death sequence with combat
            already torn down and HP still at zero, which is a worse state
            than any respawn bug it could report. Death must never crash.

        Author: Nick Hobar
        Creation date: 08/23/2026
        """
        # Through the property, not db.hp: the hp setter is what clamps to
        # max_hp AND publishes the state-feed HP event the 3D client's bar
        # reads. Writing db.hp directly refills the number but leaves every
        # connected client still showing the corpse's zero.
        self.hp = self.max_hp

        room = get_respawn_room()

        if room is None:
            self.msg(
                "|rYou black out... and come to where you fell, barely "
                "breathing but alive.|n"
            )
            return

        if self.location is room:
            self.msg("|rYou black out... and wake where you stand.|n")
            return

        try:
            self.move_to(room, quiet=True, move_type="teleport")
        except Exception as exc:
            logger.log_err(f"Character.respawn move to {room} failed: {exc!r}")
            self.msg(
                "|rYou black out... and come to where you fell, barely "
                "breathing but alive.|n"
            )
            return

        self.msg("|rYou black out.|n")
        self.msg(f"|wYou wake up at {room.key}, your wounds closed over.|n")


    def at_pre_object_receive(self, moved_obj, source_location, **kwargs):
        """
        Purpose: Refuse an incoming item once the 32-slot grid is full,
        before the move happens.

        Entry:
            moved_obj is the object about to move into this Character.
            source_location is where it is moving from.

        Exit/Returns:
            True to allow the move, False to cancel it and leave
            moved_obj where it was.

        Methodology:
            Runs at move_to() step 3 (destination.at_pre_object_receive),
            which is the one hook in the move sequence that can veto
            before anything changes -- the object hasn't left
            source_location yet, so there is no bounce-back to perform.
            InventoryHandler.can_accept mirrors add_item's own stack/
            free-slot logic, so a pickup that would merge into an
            existing stack is still allowed at 32/32.

            This is what makes the swallowed InventoryError in
            at_object_receive (below) unreachable in the full-inventory
            case: that hook now only ever sees objects this one already
            approved. Before this hook existed, add_item's
            InventoryError was raised *after* the object had already
            been moved into contents (move_to's step 8) and caught by a
            bare except-pass, so the item sat in contents with no slot
            -- invisible to `inv`, uncounted against the 32-slot cap,
            but still real and still tradeable/droppable. That is what
            let Carrying 32/32 keep accepting `get`s.

        Notes/References: CLAUDE.md gotcha table doesn't cover this one;
            see evennia.objects.objects.DefaultObject.move_to docstring
            for the full pre/post hook order.

        Author: Nick Hobar
        Creation date: 08/16/2026
        """
        if hasattr(moved_obj, "is_stackable") and not self.inventory.can_accept(moved_obj):
            self.msg("Your inventory is completely full.")
            return False
        parent_class = super()
        return parent_class.at_pre_object_receive(moved_obj, source_location, **kwargs)


    def at_object_receive(self, moved_obj, source_location, move_type="move", **kwargs):
        if hasattr(moved_obj, "is_stackable"):
            try:
                self.inventory.add_item(moved_obj)
            except Exception as exc:
                logger.log_err(
                    f"Character.at_object_receive: add_item failed for "
                    f"{moved_obj!r} on {self!r} despite at_pre_object_receive "
                    f"approving the move: {exc!r}"
                )
        super().at_object_receive(moved_obj, source_location, move_type=move_type, **kwargs)
        self._publish_inventory()


    def at_object_leave(self, moved_obj, target_location, move_type="move", **kwargs):
        if hasattr(moved_obj, "is_stackable"):
            try:
                self.inventory.remove_item(moved_obj)
            except Exception:
                pass
        super().at_object_leave(moved_obj, target_location, move_type=move_type, **kwargs)
        # moved_obj is still in self.contents here -- move_to does not reassign
        # its location until the step AFTER this hook. Publishing without
        # naming it would re-adopt it into a free slot; see
        # InventoryHandler.sync.
        self._publish_inventory(ignore=moved_obj)


    def _publish_inventory(self, ignore=None) -> None:
        """
        Purpose: Push a fresh inventory snapshot to this character's graphical
        clients after an item has finished moving.

        Entry:
            Called from at_object_receive and at_object_leave, AFTER super().
            `ignore` is an object to treat as already gone, which the leave
            path passes and the receive path does not.

        Exit/Returns:
            No return value. Never raises.

        Module Globals:
            None.

        Methodology:
            After super(), not before, and not inside the try block above it.
            add_item merges a stackable pickup by writing onto the surviving
            stack and DELETING the incoming object; a snapshot taken mid-merge
            would describe a grid holding an object that is about to stop
            existing. Waiting until the move has completed is what makes the
            snapshot true.

            The two callers are NOT symmetric, because Evennia's move_to does
            not treat them symmetrically. at_object_receive runs at step 8,
            after the location change, so `contents` is already correct and
            there is nothing to ignore. at_object_leave runs at step 4, before
            it, so the departing object is still present and must be named --
            otherwise sync() re-adopts it and the snapshot describes the
            inventory the player had a moment ago.

            InventoryHandler deliberately does not publish from its own
            mutators for that same reason -- see EquipmentHandler._publish,
            which documents the other half of the asymmetry.

        Notes/References:
            emit_inventory pre-checks the subscription, so on a telnet-only
            server this costs one getattr per item movement.

        Author: Nick Hobar
        Creation date: 08/15/2026
        """
        try:
            feed.emit_inventory(self, ignore=ignore)
        except Exception:
            logger.log_trace()


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