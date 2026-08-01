"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/30/2026
Description: The single ANSI colour palette for all Blackout player-facing
             text. Menus, commands and combat messaging import from here.
"""



# Public constant definitions

# Evennia ANSI markup. See evennia/utils/ansi.py for the full tag table.
# These were previously redeclared, character for character, in nine separate
# modules (every menu, inventory_cmds, and the NPC dialogues), plus a parallel
# TAG_* naming scheme in combat_msg. Retheming the game meant finding all ten.
RESET_COLOR = "|n"

TITLE_COLOR = "|w"          # headings, and the emphasised half of a label
HIGHLIGHT_COLOR = "|y"      # menu keys, item names, anything the eye seeks
SUCCESS_COLOR = "|g"        # completed action
ERROR_COLOR = "|r"          # refused action / missing requirement
DIM_COLOR = "|x"            # de-emphasised text, misses, flavour
SKILL_COLOR = "|c"          # skill names
SPEECH_COLOR = "|c"         # NPC dialogue lines
DANGER_COLOR = "|R"         # death and other terminal outcomes

# Combat messaging aliases. Combat reads better in terms of who is acting than
# in terms of success/failure, so it keeps its own vocabulary -- but pointed at
# the same palette rather than a second set of literals.
TAG_INCOMING = ERROR_COLOR
TAG_OUTGOING = SUCCESS_COLOR
TAG_OUTGOING_NAME = TITLE_COLOR
TAG_MISS = DIM_COLOR
TAG_DEATH = DANGER_COLOR
TAG_XP = HIGHLIGHT_COLOR    # per-hit experience gained, on the same line
TAG_RESET = RESET_COLOR



def dialog(text: str) -> str:
    """Wrap an NPC's spoken line in the speech colour."""
    return f"{SPEECH_COLOR}{text}{RESET_COLOR}"


def highlight(text: str) -> str:
    """Wrap text in the highlight colour for emphasis."""
    return f"{HIGHLIGHT_COLOR}{text}{RESET_COLOR}"


def title(text: str) -> str:
    """Wrap a heading or NPC name in the title colour."""
    return f"{TITLE_COLOR}{text}{RESET_COLOR}"
