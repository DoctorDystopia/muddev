"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: Turn the observer's open pop-up into the plain values
             CharPopupPayload carries.

             IT COMPOSES NOTHING. systems/interface/popups/service.py builds
             the snapshot, and each pop-up definition builds its own grids.
             This module copies that description into the dataclass, the
             arrangement combat_options.py has with style_options.py.

             Imported LAZILY by events.emit_popup. The pop-up registry imports
             every definition, and the bank's imports typeclasses/bank_nodes.py.
             events.py is imported by typeclasses/mixins.py at startup.
"""

from .payloads import CharPopupPayload


# ─── Public interface ────────────────────────────────────────────────────────

def build_payload(observer) -> CharPopupPayload:
    """
    Purpose: Build the observer's pop-up as one snapshot.

    Entry:
        observer - the puppeted Character, or any object. One with nothing
                   open yields the closed state.

    Exit/Returns:
        Returns a CharPopupPayload.

    Module Globals:
        None.

    Methodology:
        A straight copy of service.build_snapshot into the dataclass.

    Notes/References:
        Sent on CHANNEL_CHAR_POPUP. Every value must survive json.dumps --
        see systems/interface/statefeed/payloads.py.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    from systems.interface.popups import service

    snapshot = service.build_snapshot(observer)
    payload = CharPopupPayload(**snapshot)

    return payload
