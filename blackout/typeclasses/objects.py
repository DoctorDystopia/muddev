"""
Object

The Object is the class for general items in the game world.

Use the ObjectParent class to implement common features for *all* entities
with a location in the game world (like Characters, Rooms, Exits).

"""

from evennia import DefaultObject
from evennia.utils import logger

from systems.interface.statefeed import constants as feed_const

# Refusing a pickup is a line about your inventory, so it carries the same
# routing tag commands/get_cmds.py puts on every other line in that flow.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/interface/statefeed/constants.py.
_MSG_INVENTORY = {
    feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_INVENTORY}


class ObjectParent:
    """
    This is a mixin that can be used to override *all* entities inheriting at
    some distance from DefaultObject (Objects, Exits, Characters and Rooms).

    Just add any method that exists on `DefaultObject` to this class. If one
    of the derived classes has itself defined that same hook already, that will
    take precedence.

    """


    def at_object_delete(self):
        """
        Purpose: Tell every watching client that this entity is gone, before
        it stops being readable.

        Entry:
            No conditions. Called by DefaultObject.delete() as its first act,
            while self.location and self.id are both still valid.

        Exit/Returns:
            Returns whatever the parent hook returns -- False vetoes the
            deletion, and this must never be the thing that changes that
            answer.

        Module variables:
            None.

        Methodology:
            THE SEAM IS DELETION, and it had none. The feed's remove-delta was
            wired to Room.at_object_leave, which Evennia fires from move_to --
            and delete() does not move anything. It assigns `self.location =
            None` directly (evennia/objects/objects.py, DefaultObject.delete),
            so every object that left the world by being destroyed rather than
            by walking out left a permanent ghost on every client that had
            been told about it.

            That covered the two most common events in the game. A killed NPC
            is deleted by HostileNPC.respawn, and a butchered corpse is
            deleted by GatheringSkill.consume_node. Both stayed on screen,
            stacked up over a session, and stayed CLICKABLE -- so a click
            aimed at the live raider standing on the tile could land on the
            body of the one before it, or on last kill's uncollected loot, and
            send that entity's verb instead. Nothing was wrong with the verb;
            the client was being asked about an entity the server had
            forgotten.

            Deliberately here on ObjectParent rather than on the two
            typeclasses that provoked it. The next deletable entity should not
            have to remember to do this, and every Blackout entity already
            inherits this mixin.

            Exits are skipped because the feed does not report them
            (serialize_area skips them by db_destination), and a location of
            None means nobody could have been told about it in the first
            place -- which is also every room, since a room has no location.

        Notes/References:
            The import is local. This module is loaded very early, by items,
            npcs and characters alike, and systems.interface.statefeed pulls
            in a large graph -- matching the local-import style
            typeclasses/npc_combat.py documents.

        Author: Nick Hobar
        Creation date: 09/10/2026
        """
        try:
            room = self.location

            if room is not None and not self.destination:
                from systems.interface.statefeed import events as feed

                feed.emit_entity_left(room, self.id, exclude=(self,))
        except Exception:
            # A cosmetic feed must never be able to veto a deletion. A
            # skipped removal is a ghost; a raised one would leave a 0-hp NPC
            # standing and hang the fight that killed it.
            logger.log_trace()

        parent_class = super()

        return parent_class.at_object_delete()


class Object(ObjectParent, DefaultObject):
    """
    This is the root Object typeclass, representing all entities that
    have an actual presence in-game. DefaultObjects generally have a
    location. They can also be manipulated and looked at. Game
    entities you define should inherit from DefaultObject at some distance.

    It is recommended to create children of this class using the
    `evennia.create_object()` function rather than to initialize the class
    directly - this will both set things up and efficiently save the object
    without `obj.save()` having to be called explicitly.

    Note: Check the autodocs for complete class members, this may not always
    be up-to date.

    * Base properties defined/available on all Objects

     key (string) - name of object
     name (string)- same as key
     dbref (int, read-only) - unique #id-number. Also "id" can be used.
     date_created (string) - time stamp of object creation

     account (Account) - controlling account (if any, only set together with
                       sessid below)
     sessid (int, read-only) - session id (if any, only set together with
                       account above). Use `sessions` handler to get the
                       Sessions directly.
     location (Object) - current location. Is None if this is a room
     home (Object) - safety start-location
     has_account (bool, read-only)- will only return *connected* accounts
     contents (list, read only) - returns all objects inside this object
     exits (list of Objects, read-only) - returns all exits from this
                       object, if any
     destination (Object) - only set if this object is an exit.
     is_superuser (bool, read-only) - True/False if this user is a superuser
     is_connected (bool, read-only) - True if this object is associated with
                            an Account with any connected sessions.
     has_account (bool, read-only) - True is this object has an associated account.
     is_superuser (bool, read-only): True if this object has an account and that
                        account is a superuser.

    * Handlers available

     aliases - alias-handler: use aliases.add/remove/get() to use.
     permissions - permission-handler: use permissions.add/remove() to
                   add/remove new perms.
     locks - lock-handler: use locks.add() to add new lock strings
     scripts - script-handler. Add new scripts to object with scripts.add()
     cmdset - cmdset-handler. Use cmdset.add() to add new cmdsets to object
     nicks - nick-handler. New nicks with nicks.add().
     sessions - sessions-handler. Get Sessions connected to this
                object with sessions.get()
     attributes - attribute-handler. Use attributes.add/remove/get.
     db - attribute-handler: Shortcut for attribute-handler. Store/retrieve
            database attributes using self.db.myattr=val, val=self.db.myattr
     ndb - non-persistent attribute handler: same as db but does not create
            a database entry when storing data

    * Helper methods (see src.objects.objects.py for full headers)

     get_search_query_replacement(searchdata, **kwargs)
     get_search_direct_match(searchdata, **kwargs)
     get_search_candidates(searchdata, **kwargs)
     get_search_result(searchdata, attribute_name=None, typeclass=None,
                       candidates=None, exact=False, use_dbref=None, tags=None, **kwargs)
     get_stacked_result(results, **kwargs)
     handle_search_results(searchdata, results, **kwargs)
     search(searchdata, global_search=False, use_nicks=True, typeclass=None,
            location=None, attribute_name=None, quiet=False, exact=False,
            candidates=None, use_locks=True, nofound_string=None,
            multimatch_string=None, use_dbref=None, tags=None, stacked=0)
     search_account(searchdata, quiet=False)
     execute_cmd(raw_string, session=None, **kwargs))
     msg(text=None, from_obj=None, session=None, options=None, **kwargs)
     for_contents(func, exclude=None, **kwargs)
     msg_contents(message, exclude=None, from_obj=None, mapping=None,
                  raise_funcparse_errors=False, **kwargs)
     move_to(destination, quiet=False, emit_to_obj=None, use_destination=True)
     clear_contents()
     create(key, account, caller, method, **kwargs)
     copy(new_key=None)
     at_object_post_copy(new_obj, **kwargs)
     delete()
     is_typeclass(typeclass, exact=False)
     swap_typeclass(new_typeclass, clean_attributes=False, no_default=True)
     access(accessing_obj, access_type='read', default=False,
            no_superuser_bypass=False, **kwargs)
     filter_visible(obj_list, looker, **kwargs)
     get_default_lockstring()
     get_cmdsets(caller, current, **kwargs)
     check_permstring(permstring)
     get_cmdset_providers()
     get_display_name(looker=None, **kwargs)
     get_extra_display_name_info(looker=None, **kwargs)
     get_numbered_name(count, looker, **kwargs)
     get_display_header(looker, **kwargs)
     get_display_desc(looker, **kwargs)
     get_display_exits(looker, **kwargs)
     get_display_characters(looker, **kwargs)
     get_display_things(looker, **kwargs)
     get_display_footer(looker, **kwargs)
     format_appearance(appearance, looker, **kwargs)
     return_apperance(looker, **kwargs)

    * Hooks (these are class methods, so args should start with self):

     basetype_setup()     - only called once, used for behind-the-scenes
                            setup. Normally not modified.
     basetype_posthook_setup() - customization in basetype, after the object
                            has been created; Normally not modified.

     at_object_creation() - only called once, when object is first created.
                            Object customizations go here.
     at_object_delete() - called just before deleting an object. If returning
                            False, deletion is aborted. Note that all objects
                            inside a deleted object are automatically moved
                            to their <home>, they don't need to be removed here.

     at_init()            - called whenever typeclass is cached from memory,
                            at least once every server restart/reload
     at_first_save()
     at_cmdset_get(**kwargs) - this is called just before the command handler
                            requests a cmdset from this object. The kwargs are
                            not normally used unless the cmdset is created
                            dynamically (see e.g. Exits).
     at_pre_puppet(account)- (account-controlled objects only) called just
                            before puppeting
     at_post_puppet()     - (account-controlled objects only) called just
                            after completing connection account<->object
     at_pre_unpuppet()    - (account-controlled objects only) called just
                            before un-puppeting
     at_post_unpuppet(account) - (account-controlled objects only) called just
                            after disconnecting account<->object link
     at_server_reload()   - called before server is reloaded
     at_server_shutdown() - called just before server is fully shut down

     at_access(result, accessing_obj, access_type) - called with the result
                            of a lock access check on this object. Return value
                            does not affect check result.

     at_pre_move(destination)             - called just before moving object
                        to the destination. If returns False, move is cancelled.
     announce_move_from(destination)         - called in old location, just
                        before move, if obj.move_to() has quiet=False
     announce_move_to(source_location)       - called in new location, just
                        after move, if obj.move_to() has quiet=False
     at_post_move(source_location)          - always called after a move has
                        been successfully performed.
     at_pre_object_leave(leaving_object, destination, **kwargs)
     at_object_leave(obj, target_location, move_type="move", **kwargs)
     at_object_leave(obj, target_location)   - called when an object leaves
                        this object in any fashion
     at_pre_object_receive(obj, source_location)
     at_object_receive(obj, source_location, move_type="move", **kwargs) - called when this object receives
                        another object
     at_post_move(source_location, move_type="move", **kwargs)

     at_traverse(traversing_object, target_location, **kwargs) - (exit-objects only)
                              handles all moving across the exit, including
                              calling the other exit hooks. Use super() to retain
                              the default functionality.
     at_post_traverse(traversing_object, source_location) - (exit-objects only)
                              called just after a traversal has happened.
     at_failed_traverse(traversing_object)      - (exit-objects only) called if
                       traversal fails and property err_traverse is not defined.

     at_msg_receive(self, msg, from_obj=None, **kwargs) - called when a message
                             (via self.msg()) is sent to this obj.
                             If returns false, aborts send.
     at_msg_send(self, msg, to_obj=None, **kwargs) - called when this objects
                             sends a message to someone via self.msg().

     return_appearance(looker) - describes this object. Used by "look"
                                 command by default
     at_desc(looker=None)      - called by 'look' whenever the
                                 appearance is requested.
     at_pre_get(getter, **kwargs)
     at_get(getter)            - called after object has been picked up.
                                 Does not stop pickup.
     at_pre_give(giver, getter, **kwargs)
     at_give(giver, getter, **kwargs)
     at_pre_drop(dropper, **kwargs)
     at_drop(dropper, **kwargs)          - called when this object has been dropped.
     at_pre_say(speaker, message, **kwargs)
     at_say(message, msg_self=None, msg_location=None, receivers=None, msg_receivers=None, **kwargs)

     at_look(target, **kwargs)
     at_desc(looker=None)

    """



class Unpocketable:
    """
    Purpose: Refuse `get` on an object that is scenery or a person, for every
    instance already in the database as well as every future one.

    Entry:
        Mixed in FIRST, before the typeclass's other bases, so at_pre_get
        below wins over DefaultObject's permissive one.

    Exit/Returns:
        No conditions. at_pre_get returns False and messages the getter.

    Module variables:
        _MSG_INVENTORY read.

    Methodology:
        A HOOK, deliberately, and not the `get:false()` lock every other
        un-pickable thing in the game carries. A lock is a row on the object:
        it is written once in at_object_creation, which runs once, so adding
        one now would leave every NPC already standing on the grid pocketable
        until the next map rebuild -- and the shopkeeps, whose rooms are never
        rebuilt, forever. A hook is a class attribute, read live on every
        attempt, so declaring it here corrects objects that were created
        months ago with no migration. Same reasoning CLAUDE.md gives for
        TalkativeNPC.dialogue_module.

        The message is a class attribute rather than a literal so a subclass
        can say something truer about itself without reimplementing the hook.

    Notes/References:
        Both Evennia's CmdGet (commands/default/general.py:466) and Blackout's
        override (commands/get_cmds.py:160) call at_pre_get and abort on a
        False return, so this is the one seam both honour.

        Why it was needed: a player could `get mutant raider`, and the raider
        went into their bag alive. It never died in its room, so
        HostileNPC.respawn never ran, so nothing was ever queued on
        BlackoutRespawnManager -- the tile stayed empty for the rest of the
        server's life. The respawn queue itself was never at fault.

    Author: Nick Hobar
    Creation date: 09/10/2026
    """
    cannot_get_message = "{name} is not going anywhere in your pocket."

    def at_pre_get(self, getter, **kwargs) -> bool:
        message = self.cannot_get_message.format(name=self.key)
        getter.msg((message, _MSG_INVENTORY))

        return False
