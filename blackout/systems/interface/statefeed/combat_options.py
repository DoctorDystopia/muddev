"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/12/2026
Description: Turn a character's combat options into the plain values
             CharCombatPayload carries.

             IT COMPOSES NOTHING. Every value comes from
             systems/gameplay/combat/style_options.py, which is also what the
             combat options EvMenu renders -- so the tab a graphical client
             draws and the menu a telnet player reads describe the same
             styles by construction. It is skills.py's arrangement with
             detail.py, one system over.

             Imported LAZILY by events.emit_combat_options. style_options
             reaches combat.py and the combat level package, and events.py is
             imported by typeclasses/mixins.py, which every Character and NPC
             pulls in at startup.
"""

from .payloads import CharCombatPayload


# ─── Public interface ────────────────────────────────────────────────────────

def build_payload(observer) -> CharCombatPayload:
    """
    Purpose: Build the observer's combat options as one snapshot.

    Entry:
        observer - the puppeted Character. One with no equipment handler is a
                   supported no-op and yields an empty payload.

    Exit/Returns:
        Returns a CharCombatPayload.

    Module Globals:
        None.

    Methodology:
        A straight copy of style_options.combat_options into the dataclass.
        An empty description becomes a payload with no styles rather than a
        None, so a client has one shape to read.

    Notes/References:
        Sent on CHANNEL_CHAR_COMBAT. Every value must survive json.dumps --
        see systems/interface/statefeed/payloads.py.

    Author: Nick Hobar
    Creation date: 09/12/2026
    """
    from systems.gameplay.combat import style_options

    options = style_options.combat_options(observer)

    if not options:
        return CharCombatPayload()

    payload = CharCombatPayload(
        weapon_name=options["weapon_name"],
        armed=options["armed"],
        combat_level=options["combat_level"],
        attack_speed_ticks=options["attack_speed_ticks"],
        attack_speed_seconds=options["attack_speed_seconds"],
        styles=options["styles"],
    )

    return payload
