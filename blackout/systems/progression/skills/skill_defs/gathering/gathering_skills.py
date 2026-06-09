# import all gathering skill definitions
# container to be passed around of all gathering skill definitions

"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/02/2026
Description: Container module mapping all gathering skill classes.
"""



from .cutting import Cutting
# from .mining import Mining
from .brain_farming import BrainFarming



# Container dictionary bundling all gathering skill classes
GATHERING_SKILLS = {
    Cutting.key: Cutting,
    # Mining.key: Mining,
    BrainFarming.key: BrainFarming,
}