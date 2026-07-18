# import all processing skill definitions
# container to be passed around of all processing skill definitions

"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/02/2026
Description: Container module mapping all processing skill classes.
"""

from .foundry import Foundry

# Container dictionary bundling all processing skill classes
PROCESSING_SKILLS = {
    Foundry.key: Foundry,
}