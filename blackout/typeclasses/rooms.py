"""
Room

Rooms are simple containers that has no location of their own.

"""

from evennia.objects.objects import DefaultRoom
from evennia.contrib.grid.xyzgrid.xyzroom import XYZRoom
from evennia.utils import logger

from systems.quests import constants as quest_constants
from systems.quests.hooks import notify_quests
from systems.spawning import teardown
from systems.statefeed import commerce
from systems.statefeed import constants as feed_const
from systems.statefeed import events as feed
from systems.statefeed import neighbourhood
from systems.statefeed import subscriptions
from .objects import ObjectParent
from .spawners import SPAWNER_REGISTRY, load_all_spawners

# The ASCII map this room prints on every look.
#
# Tagged `map` and not `xymap`: the tag names what the line IS to a player,
# where `xymap` names the contrib that happens to render it -- which is a
# detail no client should need to know to build a tab.
_MSG_MAP = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_MAP}

# Fallback map width when the looker has no session to measure. Same constant
# the xyzgrid contrib falls back to in XYZRoom.return_appearance.
CLIENT_DEFAULT_WIDTH = 78


class Room(ObjectParent, DefaultRoom):
    """
    Rooms are like any Object, except their location is None
    (which is default). They also use basetype_setup() to
    add locks so they cannot be puppeted or picked up.
    (to change that, use at_object_creation instead)

    See mygame/typeclasses/objects.py for a list of
    properties and methods available on all Objects.
    """

    pass


class GridTile(ObjectParent, XYZRoom):
    """
    The baseline 1x1 coordinate tile for the physical world of Blackout.
    """
    map_visual_range = 6  # None = full map; default is 2 tiles in each direction

    def at_object_creation(self):
        """
        Purpose: Drop the statefeed's cached neighbourhoods, because a new tile
                 changes which rooms are within N tiles of its neighbours.

        Entry:
            No conditions. Called once by Evennia when the room is first built.

        Exit/Returns:
            Returns nothing.

        Module Globals:
            None.

        Methodology:
            The creation half of the pair whose other half is in
            at_object_delete. A cache invalidated only on deletion would go
            stale in the direction that matters more during a map rebuild:
            rooms are demolished and then rebuilt, and an observer whose
            neighbourhood was cached mid-rebuild would be fed a map with holes
            in it until something else happened to clear the entry.

            super() first, unconditionally. This hook has a real implementation
            up the chain and a cache detail must not displace it.

        Notes/References:
            systems/statefeed/neighbourhood.py owns what is cached and why.

        Author: Nick Hobar
        Creation date: 09/03/2026
        """
        super().at_object_creation()

        neighbourhood.invalidate()

    def return_appearance(self, looker, **kwargs):
        """
        Purpose: Show the room, with the grid map tinted to mark the tiles the
        looker's active damage aura is burning.

        Entry:
            looker - the entity looking. Need not have an aura.

        Exit/Returns:
            Returns the room description string. The map is sent separately by
            msg(), matching the contrib's own behaviour.

        Module Globals:
            None.

        Methodology:
            Falls through to the contrib untouched whenever there is no aura to
            draw -- which is the overwhelmingly common case, so `look` pays only
            one attribute check for a feature most players are not using.

            THE CONTRIB PRINTS THE MAP ITSELF, and that is why `automap` is
            applied through _appearance_kwargs rather than inside
            _send_tinted_map. It was inside it for a few hours on 08/28/2026,
            which suppressed the map on the AURA path only -- so `automap off`
            reported success and the map kept appearing on every step for every
            player without an aura, which is nearly all of them. One decision,
            taken once, applied to both branches.

            When there IS an aura, the contrib's own map block is suppressed by
            passing map_display=False, and a tinted map is built and sent in its
            place. Suppressing rather than post-processing matters because
            return_appearance msg()s the map itself; without the flag the looker
            would receive two maps.

            Any failure in the overlay falls back to the plain contrib map. A
            cosmetic highlight must never be able to break `look`.

        Notes/References:
            systems/combat/auras/map_overlay.py owns the tinting itself, and
            documents the xygrid coordinate maths it depends on.

        Author: Nick Hobar
        Creation date: 08/03/2026
        """
        kwargs = self._appearance_kwargs(looker, kwargs)
        radius = self._active_aura_radius(looker)

        if radius <= 0:
            return super().return_appearance(looker, **kwargs)

        # The tinted map replaces the contrib's, so the contrib's is always off
        # on this branch whatever automap says.
        kwargs["map_display"] = False
        room_desc = super().return_appearance(looker, **kwargs)

        try:
            self._send_tinted_map(looker, radius, **kwargs)
        except Exception:
            logger.log_trace()
            # Re-send the plain map so a failed overlay does not leave the
            # looker with no map at all.
            super().return_appearance(looker, **kwargs)

        return room_desc

    def _active_aura_radius(self, looker) -> int:
        """Return the radius of the looker's burning aura, or 0 if none."""
        handler = getattr(looker, "aura", None)

        if handler is None:
            return 0

        aura = handler.get_aura()

        if aura is None:
            return 0

        return aura.radius

    def _appearance_kwargs(self, looker, kwargs: dict) -> dict:
        """
        Purpose: Turn the contrib's own map off when this looker does not want
        it.

        Entry:
            looker - the character looking.
            kwargs - whatever return_appearance was given.

        Exit/Returns:
            Returns a dict to pass to the contrib. A copy, always, so a
            caller's own dict is never mutated under it.

        Module Globals:
            None.

        Methodology:
            `map_display` is the contrib's own switch, read in
            XYZRoom.return_appearance as
            `kwargs.get("map_display", ...)`. Setting it False is the only way
            to stop the contrib msg'ing the map, because it does that itself
            rather than returning it.

            An explicit `map_display` from the CALLER is overridden rather than
            respected, and that is deliberate: `automap` is the player's
            setting and a caller asking for a map the player has turned off is
            asking on their behalf, wrongly. Nothing in the game passes it
            except this class.

            A no-op returns a copy too. Returning `kwargs` itself would make
            the aura branch's `kwargs["map_display"] = False` write into the
            caller's dictionary.

        Notes/References:
            Whether the looker wants it is _wants_ascii_map; the player sets it
            with `automap`, in commands/display_cmds.py.

        Author: Nick Hobar
        Creation date: 08/28/2026
        """
        prepared = dict(kwargs)

        if not self._wants_ascii_map(looker):
            prepared["map_display"] = False

        return prepared

    def _wants_ascii_map(self, looker) -> bool:
        """
        Purpose: Decide whether this looker should be sent the text map.

        Entry:
            looker - the character looking.

        Exit/Returns:
            True when the map should be msg'd.

        Module Globals:
            feed_const.ASCII_MAP_ATTR, feed_const.GODOT_PROTOCOL_KEY read.

        Methodology:
            An explicit attribute wins in either direction. With none set, a
            session on the Godot protocol is answered False -- it draws its own
            minimap from `blackout_map` and does not need thirty lines of box
            characters on every step -- and everything else is answered True.

            ALL sessions must be graphical, not any. Under a multisession mode
            that allowed two clients on one character, suppressing because one
            of them is graphical would blank the map in the telnet window
            beside it. A character with NO session is answered True, because
            there is nobody to have a preference.

        Notes/References:
            The attribute is an override rather than a capability, so it is
            per-character and not something the client announces. See
            ASCII_MAP_ATTR in systems/statefeed/constants.py.

        Author: Nick Hobar
        Creation date: 08/28/2026
        """
        override = looker.attributes.get(feed_const.ASCII_MAP_ATTR, default=None)

        if override is not None:
            return bool(override)

        sessions = looker.sessions.get()

        if not sessions:
            return True

        for session in sessions:
            key = getattr(session, "protocol_key", "")

            if key != feed_const.GODOT_PROTOCOL_KEY:
                return True

        return False

    def _send_tinted_map(self, looker, radius: int, **kwargs) -> None:
        """Build the highlighted map and msg it, or fall back to the plain one.

        Mirrors the contrib's own option resolution: an explicit kwarg wins,
        then the map's own options, then the class default.
        """
        from systems.combat.auras.map_overlay import build_tinted_map

        xyz = self.xyz
        xymap = self.xyzgrid.get_map(xyz[2])

        if not xymap:
            return

        def _option(name, default):
            return kwargs.get(name, xymap.options.get(name, default))

        if not _option("map_display", self.map_display):
            return

        sessions = looker.sessions.get()
        client_width = (
            sessions[0].get_client_size()[0] if sessions else CLIENT_DEFAULT_WIDTH
        )

        display_width = client_width
        map_indent = 0

        if _option("map_align", self.map_align) == "c":
            map_indent = max(0, (display_width - xymap.max_x) // 2)
        elif _option("map_align", self.map_align) == "r":
            map_indent = max(0, display_width - xymap.max_x)

        path_data = looker.ndb.xy_path_data
        target_xy = path_data.target.xyz[:2] if path_data else None

        map_display = build_tinted_map(
            xymap,
            (xyz[0], xyz[1]),
            radius,
            character_symbol=_option("map_character_symbol", self.map_character_symbol),
            visual_range=_option("map_visual_range", self.map_visual_range),
            mode=_option("map_mode", self.map_mode),
            max_size=(display_width, None),
            indent=map_indent,
            target_xy=target_xy,
            target_path_style=_option(
                "map_target_path_style", self.map_target_path_style
            ),
        )

        if map_display is None:
            return

        separator = _option("map_separator_char", self.map_separator_char) * display_width
        framed = f"{separator}|n\n{map_display}\n{separator}"

        looker.msg(text=(framed, _MSG_MAP), options=None)

    def at_object_receive(self, moved_obj, source_location, move_type="move", **kwargs):
        """
        Purpose: Mirror an arrival into the structured state feed.

        Entry:
            moved_obj       - the object that just arrived. Already in
                              self.contents by the time this runs.
            source_location - where it came from, or None.

        Exit/Returns:
            Returns nothing.

        Module Globals:
            None.

        Methodology:
            Two different messages, because two different audiences need
            different things. The arriving entity needs to know where it now is
            -- a whole room, with coordinates and exits. Everyone already
            standing here needs only a one-entity delta.

            Wrapped, and super() is called FIRST. This hook is on the movement
            path; a cosmetic feed must never be able to strand a player between
            rooms, and the base implementation must run even if the feed fails.

            The observer-side sends are gated on the arriving object actually
            having a subscriber. This hook fires for every item dropped and
            every NPC that wanders in, and building a room snapshot means
            walking the room's contents with a tag read apiece -- work that
            would otherwise be done and thrown away on every dropped rock.

        Notes/References:
            create_object(location=...) does NOT fire this hook -- only move_to
            does (see CLAUDE.md). Rooms populated by the xyzgrid spawner
            therefore produce no arrival events, which is why a subscribing
            client is sent a full room snapshot rather than being expected to
            accumulate one from deltas.

        Author: Nick Hobar
        Creation date: 08/07/2026
        """
        super().at_object_receive(moved_obj, source_location, move_type=move_type, **kwargs)

        # `visit` objectives are opt-in per room rather than derived from the
        # room's coordinates. Two reasons. A coordinate triple is not a name a
        # blueprint can read -- global_quest_actions.md spells the argument
        # `visit:oasis_perimeter`, a landmark an author chose -- and this hook
        # fires for every rock dropped and every NPC that wanders a tile, so
        # the common case must cost one attribute read and stop.
        visit_key = self.db.quest_visit_key
        if visit_key:
            notify_quests(moved_obj, quest_constants.ACTION_VISIT, visit_key)

        try:
            if subscriptions.has_subscribers(moved_obj):
                feed.emit_room_info(moved_obj)
                feed.emit_room_contents(moved_obj)
                feed.emit_inventory(moved_obj)

            feed.emit_entity_arrived(self, moved_obj)
            # The mover is excluded here as it is on the leave path, though for
            # the opposite reason: it IS legitimately in contents now, and the
            # line above has already published its snapshot.
            self._republish_for_counterparty(moved_obj, exclude=(moved_obj,))
        except Exception:
            logger.log_trace()

    def at_object_leave(self, moved_obj, target_location, move_type="move", **kwargs):
        """
        Purpose: Mirror a departure into the structured state feed.

        Entry:
            moved_obj       - the object about to leave. Still in self.contents.
            target_location - where it is going, or None.

        Exit/Returns:
            Returns nothing.

        Module Globals:
            None.

        Methodology:
            The id is read BEFORE super() runs and passed as a bare int. The
            departing object is excluded from the broadcast because it has not
            actually moved yet -- Evennia fires this hook at step 4 of move_to,
            before the location changes -- and it will receive its own new
            room's snapshot a moment later anyway.

        Notes/References:
            evennia/objects/objects.py:1224 documents the move_to hook order
            this depends on.

        Author: Nick Hobar
        Creation date: 08/07/2026
        """
        super().at_object_leave(moved_obj, target_location, move_type=move_type, **kwargs)

        try:
            departing_id = moved_obj.id
            feed.emit_entity_left(self, departing_id, exclude=(moved_obj,))
            self._republish_for_counterparty(moved_obj, exclude=(moved_obj,))
        except Exception:
            logger.log_trace()

    def _republish_for_counterparty(self, moved_obj, exclude=()):
        """
        Purpose: Refresh everyone's inventory when a shopkeeper or a bank
                 terminal walks in or out.

        Entry:
            moved_obj - the object that arrived or is leaving.
            exclude   - objects to skip. Both callers pass the mover, for
                        opposite reasons: on the leave path it is still in
                        contents and has not actually moved yet, and on the
                        arrival path its own snapshot has just been sent.

        Exit/Returns:
            Returns nothing. Callers wrap; this does not.

        Module Globals:
            None.

        Methodology:
            What a carried item AFFORDS is a fact about the room, so the
            snapshot has to be rebuilt when the room changes -- otherwise the
            context menu is right only until somebody moves.

            The mover being a CHARACTER is handled by the caller, which
            already emits that character's own snapshot. This handles the
            other direction: the counterparty is what moved, and every
            character standing here is now looking at a stale menu.

            Cheap in the common case. is_counterparty is one getattr, and it
            is false for every rock dropped and every raider that wanders a
            tile, which is what stops this walking the room's contents on the
            movement path for nothing.

        Notes/References:
            Unnecessary for today's static spawns, where no counterparty ever
            moves. It is the one line that stops a wandering shopkeeper from
            becoming a bug report, and it uses the same predicate
            commerce.build_context filters on, so the thing that turns an
            action on and the thing that republishes when it should cannot
            disagree.

        Author: Nick Hobar
        Creation date: 09/02/2026
        """
        if not commerce.is_counterparty(moved_obj):
            return

        for obj in self.contents:
            if obj in exclude:
                continue

            if not subscriptions.has_subscribers(obj):
                continue

            feed.emit_inventory(obj)

    def at_object_delete(self):
        """
        Purpose: Destroy what this tile owns before Evennia empties it.

        Entry:
            No conditions. Called by DefaultObject.delete() on this room.

        Exit/Returns:
            Returns True to let the deletion proceed, or False if a parent
            class vetoed it -- in which case nothing is destroyed.

        Module Globals:
            None.

        Methodology:
            Ask the parent first, then hand the room to
            systems.spawning.teardown, which destroys the NPCs, nodes,
            facilities and floor litter depth-first and leaves player
            characters and exits alone. Evennia's own clear_exits and
            clear_contents then run on what is left.

        Notes/References:
            This hook, not map_sync.py, is where the teardown belongs, because
            it is the only point common to every way a tile dies: the manifest
            purge, XYZGrid.remove_map, and the contrib deleting a tile that
            fell off the map in XYMap.spawn_nodes -- the last of which no
            operator script can reach.

            Wrapped, because a failed teardown must not be able to strand a
            half-deleted room in the middle of a rebuild. Leaking an object is
            recoverable by running the reaper; aborting a deletion here is not.

        Author: Nick Hobar
        Creation date: 08/28/2026
        """
        proceed = super().at_object_delete()

        if not proceed:
            return False

        try:
            teardown.demolish_contents(self)
        except Exception:
            logger.log_trace()

        # The statefeed memoises "which rooms are within N tiles of this one",
        # which is a fact about the MAP. Destroying a tile is one of the two
        # events that can change that answer, and this hook is the only point
        # common to every way a tile dies -- the manifest purge,
        # XYZGrid.remove_map, and the contrib deleting a tile that fell off the
        # map -- which is exactly the property the invalidator needs. See
        # systems/statefeed/neighbourhood.py.
        neighbourhood.invalidate()

        return True

    def at_object_post_spawn(self, prototype=None):
        """
        Called after this room is created/updated via a prototype
        during xyzgrid building. Looks up the prototype's room key
        in SPAWNER_REGISTRY and dispatches to the matching spawner, if any.
        """
        if prototype is None:
            return
        load_all_spawners()
        key = prototype.get("key")
        spawner = SPAWNER_REGISTRY.get(key)
        if spawner:
            spawner(self)