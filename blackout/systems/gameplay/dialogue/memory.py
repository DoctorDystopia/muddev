"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/19/2026
Description: The dialogue memory (DESIGN-0017): the values that the dialogue
             scripts keep for one player character, by a memory key.

             A SCRIPT KEEPS A CHOICE OF THE PLAYER. The Lone Android gives a
             reading of 82% or 72% human, from the opener that the player
             picks. A later cue says that reading again. A conversation
             keeps nothing between two talks, so the script keeps the
             reading here with `memory.remember`, and reads it back with
             `memory.recall`.

             THIS MODULE IS THE ONE READER AND WRITER of the Attribute
             MEMORY_ATTRIBUTE. The two names in `vocab_defs/memory.py` call
             it. Nothing else reads the Attribute.

             ONE MEMORY FOR EACH CHARACTER. Each script reads and writes the
             same dict. Thus, a later NPC can recall a key that the android
             remembered. The content check finds a recall of a key that no
             script remembers (checks.memory_problems).
"""

from systems.gameplay.dialogue import constants as dialogue_const


# ─── Private helper routines ─────────────────────────────────────────────────

def _kept(character: object) -> dict:
    """A copy of the memory of a character, as a plain dict. Empty if the
    character has no memory."""
    stored = character.attributes.get(dialogue_const.MEMORY_ATTRIBUTE, default=None)

    return dict(stored or {})


# ─── Public routines ─────────────────────────────────────────────────────────

def remember(character: object, key: str, value: object) -> None:
    """
    Purpose: Keep one value for a character under a memory key.

    Entry:
        character is a player character.
        key is a snake_case memory key.
        value is one of MEMORY_VALUE_TYPES.

    Exit/Returns:
        No return value. A second call with the same key replaces the value.
        Raises TypeError for a value of a different type.

    Module Globals:
        None.

    Methodology:
        1. Refuse a value that is not a plain fact.
        2. Copy the memory, set the key, and write the whole dict back.

    Notes/References:
        The write replaces the whole Attribute. A change inside the saved
        dict of Evennia also saves, but one write is easier to read.

    Author: Nick Hobar
    Creation date: 11/19/2026
    """
    if not isinstance(value, dialogue_const.MEMORY_VALUE_TYPES):
        raise TypeError(
            f"the dialogue memory keeps a text, a number, or true or false, "
            f"and '{key}' got {type(value).__name__}")

    kept = _kept(character)
    kept[key] = value
    character.attributes.add(dialogue_const.MEMORY_ATTRIBUTE, kept)


def recall(character: object, key: str, default: object) -> object:
    """
    Purpose: Give the value that a character keeps under a memory key.

    Entry:
        character is a player character.
        key is a snake_case memory key.
        default is the value for a character with no value under the key.

    Exit/Returns:
        Returns the kept value, or the default.

    Module Globals:
        None.

    Methodology:
        Read the memory and look up the key.

    Notes/References:
        The default covers a character that had the conversation before
        the script kept the value.

    Author: Nick Hobar
    Creation date: 11/19/2026
    """
    kept = _kept(character)
    value = kept.get(key, default)

    return value
