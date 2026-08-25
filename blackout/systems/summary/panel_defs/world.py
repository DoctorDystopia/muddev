"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/08/2026
Description: Summary panel: where the character is, what they are working on,
             and how long they have been at it.
"""

from evennia.utils import logger

from systems.statefeed.serializers import room_coords

from .. import constants as const
from .. import layout
from .base_panel import BasePanel


# Public constant definitions

PANEL_TITLE = "World"

LABEL_LOCATION = "Location"
LABEL_QUESTS_ACTIVE = "Quests"
LABEL_QUESTS_DONE = "Completed"
LABEL_PLAYED = "Played"
LABEL_CREATED = "Created"
LABEL_ACTIVE_LIST = "Working on"

# Duration unit suffixes, smallest rendered unit last.
DAY_SUFFIX = "d"
HOUR_SUFFIX = "h"
MINUTE_SUFFIX = "m"

# Width the hour and minute components are zero-padded to when a larger unit
# precedes them, so "6d 04h" columns line up against "6d 11h".
DURATION_PAD = 2

# How many active quest titles are named before the row is truncated. The count
# above it is always exact; this only caps the list.
MAX_LISTED_QUESTS = 3
TRUNCATION_SUFFIX = "..."


class WorldPanel(BasePanel):
    """
    Purpose: The character's position in the world and in their own progress.

    Entry:
        character is a Character with a quests handler.

    Exit/Returns:
        Not applicable -- see render / data.

    Module Globals:
        const.CREATED_DATE_FORMAT read.

    Methodology:
        Quest state has had no player-facing view at all: QuestHandler stores
        active and completed quests and nothing renders either. This band is
        where that surfaces.

        Grid coordinates are read through the state feed's room_coords, which
        already absorbs the two distinct "no coordinates" cases -- a plain Room
        with no `xyz` attribute, and an XYZRoom whose coordinates are None.
        Re-deriving that here would mean re-deriving both.

    Notes/References:
        Playtime is accumulated by typeclasses/characters.py; this panel only
        formats it.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """

    key = "world"
    title = PANEL_TITLE
    order = const.PANEL_ORDER_WORLD
    public = True


    @classmethod
    def _format_duration(cls, seconds: int) -> str:
        """
        Purpose: Render a second count as a compact "6d 04h" style duration.

        Entry:
            seconds is a non-negative integer.

        Exit/Returns:
            Returns a display string. Under one hour renders minutes only,
            under one day renders hours and minutes, otherwise days and hours.

        Module Globals:
            const.SECONDS_PER_MINUTE, const.MINUTES_PER_HOUR,
            const.HOURS_PER_DAY read.
            DAY_SUFFIX, HOUR_SUFFIX, MINUTE_SUFFIX, DURATION_PAD read.

        Methodology:
            Two units at most. A third would push the row past its column for a
            gain of nothing -- nobody reads their playtime to the minute once
            it is measured in days.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        total_minutes = seconds // const.SECONDS_PER_MINUTE
        minutes = total_minutes % const.MINUTES_PER_HOUR
        total_hours = total_minutes // const.MINUTES_PER_HOUR
        hours = total_hours % const.HOURS_PER_DAY
        days = total_hours // const.HOURS_PER_DAY

        if days > 0:
            text = f"{days}{DAY_SUFFIX} {hours:0{DURATION_PAD}d}{HOUR_SUFFIX}"

            return text

        if total_hours > 0:
            text = f"{total_hours}{HOUR_SUFFIX} {minutes:0{DURATION_PAD}d}{MINUTE_SUFFIX}"

            return text

        text = f"{total_minutes}{MINUTE_SUFFIX}"

        return text


    @classmethod
    def _location_text(cls, character: object) -> str:
        """
        Purpose: Name the character's room, with grid coordinates when it has
        any.

        Entry:
            character is a Character.

        Exit/Returns:
            Returns e.g. "Rusted Overpass (5, 3, oasis)", or the room name
            alone for an off-grid room.

        Module Globals:
            const.EMPTY_VALUE_TEXT read.

        Methodology:
            A character with no location at all is a real transient state
            (mid-move, or freshly created), so it reports as empty rather than
            raising.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        location = character.location

        if location is None:
            return const.EMPTY_VALUE_TEXT

        coords = room_coords(location)

        if not coords:
            return str(location.key)

        text = f"{location.key} ({coords[0]}, {coords[1]}, {coords[2]})"

        return text


    @classmethod
    def _quest_titles(cls, character: object) -> list:
        """
        Purpose: List the titles of the character's active quests.

        Entry:
            character is a Character with a quests handler.

        Exit/Returns:
            Returns a list of title strings, capped at MAX_LISTED_QUESTS with a
            trailing ellipsis item when it overflows.

        Module Globals:
            MAX_LISTED_QUESTS, TRUNCATION_SUFFIX read.

        Methodology:
            A quest key with no blueprint in the registry -- content removed
            since the player accepted it -- falls back to its raw key rather
            than being dropped, so the count above the list and the list itself
            cannot disagree about how many quests exist.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        from systems.quests.loader import GLOBAL_QUEST_REGISTRY

        active = character.quests.active_keys()
        titles = []

        for quest_key in active:
            blueprint = GLOBAL_QUEST_REGISTRY.get(quest_key)
            title = getattr(blueprint, "title", None) or quest_key
            titles.append(str(title))

        if len(titles) <= MAX_LISTED_QUESTS:
            return titles

        trimmed = titles[:MAX_LISTED_QUESTS]
        trimmed.append(TRUNCATION_SUFFIX)

        return trimmed


    @classmethod
    def _created_text(cls, character: object) -> str:
        """
        Purpose: Format the character's creation date.

        Entry:
            character is a Character.

        Exit/Returns:
            Returns a formatted date, or the empty-value marker if Evennia has
            no creation stamp for this object.

        Module Globals:
            const.CREATED_DATE_FORMAT, const.EMPTY_VALUE_TEXT read.

        Methodology:
            db_date_created is a Django field on ObjectDB, present for anything
            that reached the database. Guarded anyway: an unsaved in-memory
            object built by a test would have None there.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        created = getattr(character, "db_date_created", None)

        if created is None:
            return const.EMPTY_VALUE_TEXT

        try:
            text = created.strftime(const.CREATED_DATE_FORMAT)
        except Exception as exc:
            logger.log_err(f"WorldPanel._created_text failed: {exc!r}")

            return const.EMPTY_VALUE_TEXT

        return text


    @classmethod
    def render(cls, character: object) -> list:
        """
        Purpose: Render the world band.

        Entry:
            character is a Character.

        Exit/Returns:
            Returns a list of display lines.

        Module Globals:
            LABEL_* read.

        Methodology:
            Location gets a wide row because a room name plus coordinates does
            not fit a value column; the four counters pair up beneath it, and
            the active quest titles wrap on their own row when there are any.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        active = character.quests.active_keys()
        completed = character.quests.completed_keys()
        playtime = getattr(character, "playtime_seconds", 0)

        pairs = [
            (LABEL_QUESTS_ACTIVE, f"{len(active)}"),
            (LABEL_QUESTS_DONE, f"{len(completed)}"),
            (LABEL_PLAYED, cls._format_duration(playtime)),
            (LABEL_CREATED, cls._created_text(character)),
        ]

        lines = [layout.wide_field(LABEL_LOCATION, cls._location_text(character))]
        lines.extend(layout.fields(pairs))
        lines.extend(
            layout.wrapped_field(LABEL_ACTIVE_LIST, cls._quest_titles(character))
        )

        return lines


    @classmethod
    def render_public(cls, character: object) -> list:
        """
        Purpose: Render the world band as a stranger sees it.

        Entry:
            character is the Character being looked at.

        Exit/Returns:
            Returns a list of display lines: completed quests, playtime and
            creation date.

        Module Globals:
            LABEL_QUESTS_DONE, LABEL_PLAYED, LABEL_CREATED read.

        Methodology:
            Drops the location and both the active-quest count and titles.

            Location is the important one: a profile command that reported grid
            coordinates would be a player-tracking tool usable from anywhere in
            the world, which is a far stronger capability than anything else on
            this screen. Finding someone should require looking for them.

            Active quests go too, for a smaller reason -- what a player is
            working on right now is theirs to mention. What they have FINISHED
            is an achievement, and achievements are the point of a public
            profile.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        completed = character.quests.completed_keys()
        playtime = getattr(character, "playtime_seconds", 0)

        pairs = [
            (LABEL_QUESTS_DONE, f"{len(completed)}"),
            (LABEL_PLAYED, cls._format_duration(playtime)),
            (LABEL_CREATED, cls._created_text(character)),
        ]
        lines = layout.fields(pairs)

        return lines


    @classmethod
    def data(cls, character: object) -> dict:
        """
        Purpose: Structured form of the world band.

        Entry:
            character is a Character.

        Exit/Returns:
            Returns a dict of plain JSON-safe values.

        Module Globals:
            None.

        Methodology:
            Playtime goes out as raw seconds, not as the formatted string -- a
            client formats for its own locale, and a duration string is not a
            value anything can compute with.

        Notes/References:
            None

        Author: Nick Hobar
        Creation date: 08/08/2026
        """
        location = character.location
        active = character.quests.active_keys()
        completed = character.quests.completed_keys()

        if location is None:
            room_name = ""
            coords = []
        else:
            room_name = str(location.key)
            coords = room_coords(location)

        payload = {
            "room": room_name,
            "coords": coords,
            "quests_active": int(len(active)),
            "quests_completed": int(len(completed)),
            "active_quest_titles": cls._quest_titles(character),
            "playtime_seconds": int(getattr(character, "playtime_seconds", 0)),
        }

        return payload
