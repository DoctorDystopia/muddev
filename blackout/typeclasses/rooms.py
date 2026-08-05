"""
Room

Rooms are simple containers that has no location of their own.

"""

from evennia.objects.objects import DefaultRoom
from evennia.contrib.grid.xyzgrid.xyzroom import XYZRoom
from evennia.utils import logger
from .objects import ObjectParent
from .spawners import SPAWNER_REGISTRY, load_all_spawners

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
    map_visual_range = 10  # None = full map; default is 2 tiles in each direction

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
        radius = self._active_aura_radius(looker)

        if radius <= 0:
            return super().return_appearance(looker, **kwargs)

        room_desc = super().return_appearance(looker, map_display=False, **kwargs)

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

        looker.msg(text=(framed, {"type": "xymap"}), options=None)

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