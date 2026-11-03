"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/20/2026
Description: Turn the abilities of a character into the plain values that
             CharAbilitiesPayload carries.

             IT COMPOSES NOTHING. Every row comes from
             systems/gameplay/abilities.py, the composer. That module puts
             the rows of auras/detail.py and of augmentation/detail.py
             after each other (10/30/2026), and each telnet listing reads
             its own detail module. Thus, the rail that a graphical
             client draws and the listing that a telnet player reads
             describe the same abilities by construction. It is
             combat_options.py's arrangement with style_options, one
             system over.

             Imported LAZILY by events.emit_abilities. The detail module
             reads the aura handler, which imports events.py, and
             typeclasses/mixins.py imports events.py at startup.
"""

from .payloads import CharAbilitiesPayload


# ─── Public interface ────────────────────────────────────────────────────────

def build_payload(observer) -> CharAbilitiesPayload:
    """
    Purpose: Build the abilities of the observer as one snapshot.

    Entry:
        observer - the puppeted Character.

    Exit/Returns:
        Returns a CharAbilitiesPayload.

    Module Globals:
        None.

    Methodology:
        A straight copy of detail.ability_rows into the dataclass.

    Notes/References:
        Sent on CHANNEL_CHAR_ABILITIES. Every value must survive json.dumps,
        see systems/interface/statefeed/payloads.py.

    Author: Nick Hobar
    Creation date: 10/20/2026
    """
    from systems.gameplay import abilities as composer

    payload = CharAbilitiesPayload(abilities=composer.ability_rows(observer))

    return payload
