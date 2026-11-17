"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/16/2026
Description: The one reader and the one writer of the figure of a
             player character: its body type and its figure colors.

             The statefeed reads the two facts through body_type_of and
             figure_colors_of, and it puts them on the entity row of the
             character and on char_avatar. The client then builds the figure
             of that body type, with those colors (DESIGN-0014 section 20).

             Each write goes through set_body_type or set_figure_color. Both
             end in publish, so each write reaches each observer: the owner
             through char_avatar, and each other player in view through the
             entity row. test_freshness.py holds the proof.

             worn_items_of gives the third fact of the figure, the item in
             each slot. The equipment handler owns that fact and calls
             publish on each change (DESIGN-0014 section 21).

             The held tool is the fourth fact (11/14/2026). A gathering
             channel puts its tool in the hand of the figure through
             hold_tool, also when the tool is in the bag. release_tool
             removes it. figure_items_of puts the held tool over the worn
             items, and the client draws the worn record from it. The tool
             stays in the bag. Only the figure holds it.

             No character creator exists yet (DESIGN-0014 decision 9). Today
             the moderator egg is the only caller of the two writers.
"""

from evennia.utils import logger

from items.equipment.constants import slots_displaced_by
from systems.gameplay.figure import constants as const
from systems.gameplay.figure import figure_files


# ─── Public routines ─────────────────────────────────────────────────────────

def publish(character) -> None:
    """
    Purpose: Send the new figure of a character to each client that
             draws it.

    Entry:
        character - the character whose body type, colors, or gear changed.

    Exit/Returns:
        No return value.

    Module Globals:
        None.

    Methodology:
        Two readers draw the figure of a character, so two sends:

          1. char_avatar, for the owner. The client draws its own figure
             from this channel, because the entity list leaves out the
             observer.
          2. The entity row, for each observer nearby. The client upserts a
             row by id, so a second `add` for a known id replaces the row,
             and the look of the row decides a new figure. pvp._publish uses
             the same send.

        Wrapped, because a feed send must never stop a write that already
        happened.

        Four callers: the two writers of this module, hold_tool, and
        EquipmentHandler._publish, because the worn record is on the same
        row (DESIGN-0014 section 21).

    Notes/References:
        systems/interface/statefeed/events.py owns both emitters.

    Author: Nick Hobar
    Creation date: 10/16/2026
    """
    from systems.interface.statefeed import events as feed

    try:
        feed.emit_avatar(character, force=True)

        location = getattr(character, "location", None)

        if location is not None:
            feed.emit_entity_arrived(location, character)
    except Exception as exc:
        logger.log_err(f"character_figure.publish: {character} feed send failed: {exc!r}")


def worn_items_of(character) -> dict:
    """
    Purpose: Give the item in each slot of a character: slot value -> item.

    Entry:
        character - a character, or any object. An object with no equipment
                    handler wears nothing.

    Exit/Returns:
        Returns a new dict, slot value (the text of a WieldLocation) -> the
        equipped object. A slot with no item has no entry. An empty dict for
        an object that wears nothing.

    Module Globals:
        None.

    Methodology:
        The statefeed turns each item into its asset key, with the routine
        that names the art of each entity. This module names no asset key,
        so the worn record and an item on the ground cannot disagree.

        Reads through getattr, because the statefeed calls this on each row
        of a character, and a row must never raise into a gameplay path.

    Notes/References:
        items/equipment/handler.py owns the slots. DESIGN-0014 section 21.

    Author: Nick Hobar
    Creation date: 10/16/2026
    """
    equipment = getattr(character, "equipment", None)
    slots = getattr(equipment, "slots", None)

    if not slots:
        return {}

    worn = {}

    for slot, item in dict(slots).items():
        if item is not None:
            worn[str(getattr(slot, "value", slot))] = item

    return worn


def figure_items_of(character) -> dict:
    """
    Purpose: Give the item in each slot of the figure of a character: the
             worn items, with the held tool over them.

    Entry:
        character - a character, or any object.

    Exit/Returns:
        Returns a new dict, slot value -> item, in the shape of
        worn_items_of. With no held tool, the dict is the same as the
        dict of worn_items_of.

    Module Globals:
        None.

    Methodology:
        The held tool goes into its use slot. It empties each slot that an
        equip of the tool empties (slots_displaced_by). Thus, the figure
        holds an axe from the bag as it holds an equipped axe. A sword in
        the main hand gives way to it.

        A held tool with no use slot draws nowhere. The figure then draws
        the worn items only.

    Notes/References:
        hold_tool writes the held tool. The statefeed reads this routine
        for the worn record (serializers._worn_record).

    Author: Nick Hobar
    Creation date: 11/14/2026
    """
    worn = worn_items_of(character)
    tool = held_tool_of(character, worn)
    use_slot = getattr(tool, "inventory_use_slot", None)

    if use_slot is None:
        return worn

    for slot in slots_displaced_by(use_slot):
        worn.pop(slot.value, None)

    worn[use_slot.value] = tool

    return worn


def held_tool_of(character, worn: dict = None):
    """
    Purpose: Give the tool that the figure of a character holds, or None.

    Entry:
        character - a character, or any object.
        worn      - the dict of worn_items_of for the character, or None to
                    read it here.

    Exit/Returns:
        Returns the held tool. Returns None when the figure holds no tool,
        or when the character does not carry the tool now.

    Module Globals:
        const.HELD_TOOL_NDB read.

    Methodology:
        The ndb holds the id of the tool, not the object. This routine finds
        the id in what the character carries: the worn items and the bag.
        Thus, a tool that the player drops, sells, or banks leaves the hand
        at the next send. None of those paths needs a hook.

    Author: Nick Hobar
    Creation date: 11/14/2026
    """
    tool_id = _ndb_value(character, const.HELD_TOOL_NDB)

    if tool_id is None:
        return None

    if worn is None:
        worn = worn_items_of(character)

    carried = list(worn.values()) + list(getattr(character, "contents", None) or ())

    for item in carried:
        if getattr(item, "id", None) == tool_id:
            return item

    return None


def hold_tool(character, tool) -> None:
    """
    Purpose: Put a tool in the hand of the figure of a character, also when
             the tool is in the bag. A tool of None takes the held tool away.

    Entry:
        character - the character.
        tool      - an item that the character carries, or None.

    Exit/Returns:
        No return value.

    Module Globals:
        const.HELD_TOOL_NDB read and written.

    Methodology:
        Each call adds one to the serial, also a call that changes nothing.
        Thus, a hold cancels each late release that came before it
        (release_tool).

        The figure goes out again only when the held tool changes. The
        gathering channel calls this before each swing, and a send for each
        swing would rebuild the figure in each client for no change.

    Notes/References:
        GatheringHandler._hold_tool is the caller.

    Author: Nick Hobar
    Creation date: 11/14/2026
    """
    _next_serial(character)

    tool_id = getattr(tool, "id", None)

    if _ndb_value(character, const.HELD_TOOL_NDB) == tool_id:
        return

    setattr(character.ndb, const.HELD_TOOL_NDB, tool_id)
    publish(character)


def release_tool(character, delay: float = 0.0) -> None:
    """
    Purpose: Take the held tool out of the hand of the figure of a
             character, now or after a delay.

    Entry:
        character - the character.
        delay     - seconds from now. 0 means now.

    Exit/Returns:
        No return value. Never raises.

    Module Globals:
        None.

    Methodology:
        A late release lets the clip of the last swing end with the tool in
        the hand. The send of a release goes out before the face event of
        the same tick. Thus, a release at once rebuilds the figure with
        empty hands first. Then the last swing plays on that figure.

        The late release keeps the serial of now. A hold that comes before
        the release lands changes the serial, and the release then does
        nothing. Thus, a new channel at once keeps its tool in the hand.

        A reactor call, as buffer.mark_stale makes for a late mark. A reload
        loses the call, and it also wipes the held tool.

    Author: Nick Hobar
    Creation date: 11/14/2026
    """
    try:
        if delay <= 0:
            hold_tool(character, None)
            return

        from twisted.internet import reactor

        serial = _ndb_value(character, const.HELD_SERIAL_NDB)
        reactor.callLater(delay, _release_if_unchanged, character, serial)
    except Exception as exc:
        logger.log_err(f"release_tool: {character} failed: {exc!r}")


def body_type_of(character) -> str:
    """
    Purpose: Give the body type of a character.

    Entry:
        character - a character, or any object with an attribute handler.

    Exit/Returns:
        Returns the body type key. DEFAULT_BODY_TYPE for a character that has
        no body type of its own, or whose value cannot be read.

    Module Globals:
        const.BODY_TYPE_ATTR and const.DEFAULT_BODY_TYPE read.

    Methodology:
        The statefeed calls this on each entity row of a character. A row
        must never raise into a gameplay path, so a read that fails gives the
        default and a log line.

    Author: Nick Hobar
    Creation date: 10/16/2026
    """
    try:
        stored = character.attributes.get(const.BODY_TYPE_ATTR, default=None)
    except Exception as exc:
        logger.log_err(f"body_type_of: {character} read failed: {exc!r}")

        return const.DEFAULT_BODY_TYPE

    if not isinstance(stored, str) or not stored:
        return const.DEFAULT_BODY_TYPE

    return stored


def figure_colors_of(character) -> dict:
    """
    Purpose: Give the figure colors of a character: color role -> named
             color.

    Entry:
        character - a character, or any object with an attribute handler.

    Exit/Returns:
        Returns a new dict. It holds only the roles of CHARACTER_COLOR_ROLES
        with a text value. An empty dict for a character with no colors of
        its own.

    Module Globals:
        const.FIGURE_COLORS_ATTR and const.CHARACTER_COLOR_ROLES read.

    Methodology:
        Evennia gives a stored dict back as a _SaverDict. A plain dict of
        plain texts goes onto the wire.

    Author: Nick Hobar
    Creation date: 10/16/2026
    """
    try:
        stored = character.attributes.get(const.FIGURE_COLORS_ATTR, default=None)
    except Exception as exc:
        logger.log_err(f"figure_colors_of: {character} read failed: {exc!r}")

        return {}

    if not stored:
        return {}

    colors = {str(role): str(color) for role, color in dict(stored).items()
              if role in const.CHARACTER_COLOR_ROLES and isinstance(color, str) and color}

    return colors


def set_body_type(character, body_type: str) -> tuple:
    """
    Purpose: Give a character a body type.

    Entry:
        character - the character.
        body_type - the key of a rig.

    Exit/Returns:
        Returns (succeeded, message). A body type with no rig is refused, and
        nothing changes.

    Module Globals:
        const.BODY_TYPE_ATTR and the MSG_* templates read.

    Methodology:
        figure_files.body_types reads the rig directory on each call, so a
        new rig from the figure workbench is a choice at once.

    Author: Nick Hobar
    Creation date: 10/16/2026
    """
    choices = figure_files.body_types()

    if body_type not in choices:
        message = const.MSG_UNKNOWN_BODY_TYPE.format(
            body_type=body_type, choices=", ".join(choices))

        return False, message

    character.attributes.add(const.BODY_TYPE_ATTR, body_type)
    publish(character)
    message = const.MSG_BODY_TYPE_SET.format(target=character.key, body_type=body_type)

    return True, message


def set_figure_color(character, role: str, color: str) -> tuple:
    """
    Purpose: Give one color role of a character a named color, or give the
             role back to the palette.

    Entry:
        character - the character.
        role      - a member of CHARACTER_COLOR_ROLES.
        color     - a named color of the palette, or PALETTE_COLOR to take
                    the color of the palette.

    Exit/Returns:
        Returns (succeeded, message). An unknown role or color is refused,
        and nothing changes.

    Module Globals:
        const.FIGURE_COLORS_ATTR, CHARACTER_COLOR_ROLES, PALETTE_COLOR and the
        MSG_* templates read.

    Methodology:
        The whole dict is written again, never changed in place. A change in
        place of a _SaverDict writes the row too, but a copy keeps one write
        for each call and keeps the reader the only place that cleans it.

    Author: Nick Hobar
    Creation date: 10/16/2026
    """
    if role not in const.CHARACTER_COLOR_ROLES:
        message = const.MSG_UNKNOWN_ROLE.format(
            role=role, choices=", ".join(const.CHARACTER_COLOR_ROLES))

        return False, message

    clearing = color == const.PALETTE_COLOR

    if not clearing and color not in figure_files.named_colors():
        return False, const.MSG_UNKNOWN_COLOR.format(color=color)

    colors = figure_colors_of(character)

    if clearing:
        colors.pop(role, None)
        message = const.MSG_COLOR_CLEARED.format(target=character.key, role=role)
    else:
        colors[role] = color
        message = const.MSG_COLOR_SET.format(target=character.key, role=role, color=color)

    character.attributes.add(const.FIGURE_COLORS_ATTR, colors)
    publish(character)

    return True, message


# ─── Private helper routines ─────────────────────────────────────────────────

def _ndb_value(character, name: str):
    """Give one ndb value of a character, or None. An object with no ndb
    handler gives None, because the statefeed reads each row through here."""
    handler = getattr(character, "ndb", None)

    return getattr(handler, name, None)


def _next_serial(character) -> int:
    """Add one to the held serial of a character, and give the new value."""
    serial = (_ndb_value(character, const.HELD_SERIAL_NDB) or 0) + 1

    setattr(character.ndb, const.HELD_SERIAL_NDB, serial)

    return serial


def _release_if_unchanged(character, serial) -> None:
    """
    Purpose: Land one late release of release_tool.

    Entry:
        character - the character of the release.
        serial    - the held serial when the release started.

    Exit/Returns:
        No return value. Never raises: the reactor calls it.

    Module Globals:
        const.HELD_SERIAL_NDB read.

    Methodology:
        A character that is gone gets nothing. A hold after the start of the
        release changed the serial, and that hold wins.

    Author: Nick Hobar
    Creation date: 11/14/2026
    """
    try:
        if getattr(character, "pk", None) is None:
            return

        if _ndb_value(character, const.HELD_SERIAL_NDB) != serial:
            return

        hold_tool(character, None)
    except Exception as exc:
        logger.log_err(f"release_tool: {character} late release failed: {exc!r}")
