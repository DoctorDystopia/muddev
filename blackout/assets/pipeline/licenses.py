"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: The license gate. Which licenses a served model may carry, and
             what each one asks of Blackout.

             THE PROBLEM THIS FIXES. Before this module, a license was a line
             of prose in CREDITS.md. The OSRS player character shipped with a
             row that said "no grant to redistribute it is recorded", and
             nothing stopped the build. A license that only a person reads is
             a license that nothing enforces.

             Each source record names its license as an SPDX id. The build
             refuses a source whose id is not in ALLOWED_LICENSES, unless the
             source record carries an `exception` with a reason. The check
             reports every exception on every run, so an exception stays
             visible and never becomes a silent pass.

             WHAT IS NOT ALLOWED, AND WHY:
               NC  (non-commercial)  - Blackout may one day earn money.
               ND  (no derivatives)  - every build resizes and changes the art.
               SA  (share-alike)     - not refused for a reason in law. It is
                                       refused until Nick decides it, because
                                       its terms reach past the model.
               "Sketchfab Standard", "Editorial" - no right to redistribute.
               An empty field        - a license nobody checked.

             This module gives no legal advice. It records a policy.

             PURE. Importing it reads no file.
"""

from dataclasses import dataclass


# ─── Public constant definitions ─────────────────────────────────────────────

@dataclass(frozen=True)
class LicenseTerms:
    """
    What one license asks of Blackout.

    name is the display name for the credits. url is the license text.
    attribution is True when the license requires a visible credit. It is
    False for CC0 and for art made here, and the credits list those anyway,
    because a model with no credit row looks the same as a model whose
    license nobody checked.
    """

    name: str
    url: str
    attribution: bool


# The SPDX id for art made for Blackout, which no third party owns. SPDX
# reserves the "LicenseRef-" prefix for exactly this.
OWNED_LICENSE: str = "LicenseRef-Blackout-Owned"

ALLOWED_LICENSES: dict = {
    "CC0-1.0": LicenseTerms(
        name="CC0 1.0",
        url="https://creativecommons.org/publicdomain/zero/1.0/",
        attribution=False,
    ),
    "CC-BY-3.0": LicenseTerms(
        name="CC BY 3.0",
        url="https://creativecommons.org/licenses/by/3.0/",
        attribution=True,
    ),
    "CC-BY-4.0": LicenseTerms(
        name="CC BY 4.0",
        url="https://creativecommons.org/licenses/by/4.0/",
        attribution=True,
    ),
    OWNED_LICENSE: LicenseTerms(
        name="Made for Blackout",
        url="",
        attribution=False,
    ),
}

# What the credits show for a source that passes only by exception.
UNLICENSED_TERMS: LicenseTerms = LicenseTerms(
    name="License not confirmed",
    url="",
    attribution=True,
)


# ─── Public routines ─────────────────────────────────────────────────────────

def is_allowed(spdx_id: str) -> bool:
    """
    Purpose: Tell whether one license id passes the gate on its own.

    Entry:
        spdx_id is any string, empty included.

    Exit/Returns:
        Returns True when spdx_id is in ALLOWED_LICENSES.

    Module Globals:
        ALLOWED_LICENSES read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    return spdx_id in ALLOWED_LICENSES


def terms_for(spdx_id: str) -> LicenseTerms:
    """
    Purpose: Give the terms that the credits show for one license id.

    Entry:
        spdx_id is any string, empty included.

    Exit/Returns:
        Returns the LicenseTerms for an allowed id. Returns UNLICENSED_TERMS
        for any other id, because only an exception lets such a source build.

    Module Globals:
        ALLOWED_LICENSES, UNLICENSED_TERMS read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    terms = ALLOWED_LICENSES.get(spdx_id, UNLICENSED_TERMS)

    return terms
