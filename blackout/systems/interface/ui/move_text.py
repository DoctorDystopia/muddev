"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/22/2026
Description: The parts of a room that the game log prints when a character
             moves, and which of them each player turned off.

             One owner for three readers. `movetext` (commands/display_cmds.py)
             writes the choice. Character.at_post_move reads it and gives it
             to the look. GridTile (typeclasses/rooms.py) leaves out each part
             that the look names.

             THE CHOICE APPLIES TO MOVEMENT ONLY. A typed `look` always shows
             the full room. A player who turns off the exits to walk quietly
             must still have a way to read them.

             A new part is one row in MOVE_TEXT_PARTS and one gate in
             GridTile. The command, the report and the help read the table.
"""

from dataclasses import dataclass


# ─── Public constant definitions ─────────────────────────────────────────────

# The Attribute that holds the keys of the parts a character turned off. A
# list of the HIDDEN parts, not the shown ones: an empty or absent list is the
# default, and the default shows every part, as the game did before this
# setting existed. A part added later is thus shown to every player at once.
MOVE_TEXT_HIDDEN_ATTR: str = "move_text_hidden"

# The keyword that carries the hidden parts from the look to the room. Only
# the look on movement sends it, so a typed `look` never hides a part.
HIDDEN_PARTS_KWARG: str = "move_text_hidden"

PART_NAME: str = "name"
PART_DESC: str = "desc"
PART_EXITS: str = "exits"
PART_CHARACTERS: str = "characters"
PART_THINGS: str = "things"


@dataclass(frozen=True)
class MoveTextPart:
    """One part of the room text: the key a player types, and what it is."""

    key: str
    label: str


# The order of the room text, top to bottom. The report lists the parts in
# this order, so it reads like the text it controls.
MOVE_TEXT_PARTS: tuple = (
    MoveTextPart(PART_NAME, "the room name"),
    MoveTextPart(PART_DESC, "the room description"),
    MoveTextPart(PART_EXITS, "the Exits line"),
    MoveTextPart(PART_CHARACTERS, "the Characters line"),
    MoveTextPart(PART_THINGS, "the You see line"),
)

PART_KEYS: frozenset = frozenset(part.key for part in MOVE_TEXT_PARTS)


# ─── Public routines ─────────────────────────────────────────────────────────

def hidden_parts(character) -> frozenset:
    """
    Purpose: Give the parts of the room text that this character turned off.

    Entry:
        character - any object with an AttributeHandler.

    Exit/Returns:
        Returns a frozenset of part keys. Empty when nothing is hidden.

    Module Globals:
        MOVE_TEXT_HIDDEN_ATTR, PART_KEYS read.

    Methodology:
        A stored key that names no part is dropped, not returned. A part that
        a later change removes must not stay in a row and hide nothing
        forever, and the reader is the one place that sees every row.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/22/2026
    """
    stored = character.attributes.get(MOVE_TEXT_HIDDEN_ATTR, default=None)

    if not stored:
        return frozenset()

    return frozenset(stored) & PART_KEYS


def set_part_shown(character, part: str, shown: bool) -> None:
    """
    Purpose: Turn one part of the room text on or off for this character.

    Entry:
        character - any object with an AttributeHandler.
        part      - a key from PART_KEYS. The caller checks it.
        shown     - True to print the part on movement, False to hide it.

    Exit/Returns:
        Returns nothing.

    Module Globals:
        MOVE_TEXT_HIDDEN_ATTR written.

    Methodology:
        Writes a sorted list, because an Attribute pickles a set into a
        different type on each save. When nothing stays hidden, the routine
        removes the Attribute, so the default costs no row.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/22/2026
    """
    hidden = set(hidden_parts(character))

    if shown:
        hidden.discard(part)
    else:
        hidden.add(part)

    if not hidden:
        character.attributes.remove(MOVE_TEXT_HIDDEN_ATTR)
        return

    character.attributes.add(MOVE_TEXT_HIDDEN_ATTR, sorted(hidden))


def reset(character) -> None:
    """Show every part again, which is the default."""
    character.attributes.remove(MOVE_TEXT_HIDDEN_ATTR)
