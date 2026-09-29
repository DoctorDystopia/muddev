"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/28/2026
Description: The `worldmap` command.

             A session that subscribes to the world map feed gets the feed
             (`events.emit_world_map`). The Godot client opens its world
             map when the index arrives. Every other session, telnet
             included, gets the text overview of world/tile_world_map.py. The
             pop-up commands make the same split. The minimap button of the
             Godot client sends this command, as a telnet player types it.
"""

from evennia.commands.command import Command

from systems.core.tilegrid import constants as tile_const
from systems.core.tilegrid.world import get_world
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import events as feed
from systems.interface.statefeed import subscriptions
from world import tile_travel, tile_world_map


# ─── Private constant definitions ────────────────────────────────────────────

_MSG_NO_WORLD = "There is no world map here."
_MSG_HEADER = ("World map, plane {plane}. One mark is {block} x {block} "
               "tiles. North is up. You are |w@|n.")

# The text of the overview files under the map type, as the tile map does.
_MAP_TYPE = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_MAP}


# ─── Private helper routines ─────────────────────────────────────────────────

def _wants_feed(caller, session) -> bool:
    """Say whether the session of the command draws the world map itself."""
    channel = feed_const.CHANNEL_WORLD_MAP

    if session is not None:
        return subscriptions.is_subscribed(session, channel)

    return subscriptions.has_channel_subscribers(caller, channel)


# ─── Public classes ──────────────────────────────────────────────────────────

class CmdWorldMap(Command):
    """
    Show the map of the whole world.

    Usage:
        worldmap

    The graphical client opens its world map. A text client gets a small
    map of the plane you stand on.
    """

    key = feed_const.WORLD_MAP_COMMAND
    aliases = ["wmap"]
    locks = "cmd:all()"
    help_category = "General"

    def func(self):
        """Send the world map feed, or print the overview."""
        caller = self.caller

        if _wants_feed(caller, self.session):
            feed.emit_world_map(caller)
            return

        plane = tile_travel.plane_of(caller)
        plane = tile_const.GROUND_PLANE if plane is None else plane
        tile_plane = get_world().plane(plane)
        drawn = tile_world_map.render_overview(tile_plane,
                                               tile_travel.tile_of(caller))

        if not drawn:
            caller.msg(_MSG_NO_WORLD)
            return

        header = _MSG_HEADER.format(plane=plane,
                                    block=tile_world_map.OVERVIEW_BLOCK)
        caller.msg(text=(header + "\n" + drawn, _MAP_TYPE))
