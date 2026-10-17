"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/16/2026
Description: The names and the messages of the figure of a player
             character (DESIGN-0014 section 20).

             The server learns no bone name, no region name, and no file name
             (requirement D8). It learns two kinds of names only: the body
             types, which are the keys of the rigs, and the named colors of
             the palette. figure_files.py reads both lists from the figure
             files, so a new rig or a new named color needs no edit here.
"""


# ─── Public constant definitions ─────────────────────────────────────────────

# The Attribute that holds the body type of a character. A character with no
# such Attribute has DEFAULT_BODY_TYPE, so no migration is necessary.
BODY_TYPE_ATTR: str = "body_type"

# The Attribute that holds the figure colors of a character: color role ->
# named color. A role that the dict does not have takes its color from the
# palette, as the figure workbench shows it.
FIGURE_COLORS_ATTR: str = "figure_colors"

# The body type of a character that has none of its own. It must be the key
# of a rig. test_character_figure.py fails if no rig has this key.
DEFAULT_BODY_TYPE: str = "body_1"

# The color roles that a character owns (DESIGN-0014 section 8.5). Each other
# role of a figure takes its color from the look or from the palette. The
# list is a choice of 10/16/2026 that waits for Nick (section 20).
CHARACTER_COLOR_ROLES: tuple = ("skin", "hair")

# The value that gives a color role back to the palette.
PALETTE_COLOR: str = ""

# The messages of the two writers. A moderator tool and a test read them.
MSG_UNKNOWN_BODY_TYPE: str = (
    "{body_type} is not a body type. The body types are: {choices}."
)
MSG_UNKNOWN_ROLE: str = (
    "{role} is not a color role of a character. The roles are: {choices}."
)
MSG_UNKNOWN_COLOR: str = (
    "{color} is not a named color of the palette."
)
MSG_BODY_TYPE_SET: str = "{target} now has the body type {body_type}."
MSG_COLOR_SET: str = "{target} now has the color {color} for {role}."
MSG_COLOR_CLEARED: str = "{target} now takes the palette color for {role}."
