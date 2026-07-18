# import all production skill definitions
# container to be passed around of all production skill definitions

"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/02/2026
Description: Container module mapping all production skill classes.
"""

from .metalsmith import Metalsmith

# Container dictionary bundling all production skill classes
PRODUCTION_SKILLS = {
    Metalsmith.key: Metalsmith,
}