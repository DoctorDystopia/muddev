"""
DEPRECATED: This module has been renamed to crafting_facilities.py.

This shim re-exports everything for backward compatibility.
New code should import from typeclasses.crafting_facilities.
"""

from typeclasses.crafting_facilities import *

import warnings

warnings.warn(
    "crafting_stations.py is deprecated; use crafting_facilities.py instead.",
    DeprecationWarning,
    stacklevel=2,
)
