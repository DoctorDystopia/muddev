# import all combat skill definitions
# container to be passed around of all combat skill definitions

"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Container module mapping all combat skill classes.
"""

from .fortitude import Fortitude
from .strike import Strike
from .brawn import Brawn
from .defense import Defense

# Container dictionary bundling all combat skill classes
COMBAT_SKILLS = {
    Fortitude.key: Fortitude,
    Strike.key: Strike,
    Brawn.key: Brawn,
    Defense.key: Defense,
}
