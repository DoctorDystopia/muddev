"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/08/2026
Description: Layout tunables and forward-hook defaults for the player summary
             screen.
"""


# ─── Screen geometry ─────────────────────────────────────────────────────────
# The dossier is a fixed-width grid so that every panel's fields line up in one
# column no matter which panel drew them. Panels never choose their own widths.

# Total rendered width of the screen, in columns. Matches the option separator
# BlackoutEvMenu draws underneath it, so the screen and its option list read as
# one block rather than two mismatched ones.
SUMMARY_WIDTH: int = 60

# Leading indent applied to every field row. Section headings sit flush left so
# they stand out against the indented rows beneath them.
FIELD_INDENT: str = "   "

# Column widths for a label/value pair. Two pairs fit on one row:
#   FIELD_INDENT + label + value + FIELD_GUTTER + label + value
# which is 3 + 14 + 12 + 2 + 14 + 12 = 57 columns, inside SUMMARY_WIDTH.
FIELD_LABEL_WIDTH: int = 14
FIELD_VALUE_WIDTH: int = 12
FIELD_GUTTER: str = "  "

# How many label/value pairs share one row. A panel that needs a wide value
# (an HP meter, a location name) calls the single-field renderer instead.
FIELDS_PER_ROW: int = 2

# Rule characters. The heavy rule brackets the screen; the light one separates
# one panel from the next.
HEAVY_RULE_CHAR: str = "="
LIGHT_RULE_CHAR: str = "-"

# Shown in a value column when the underlying system has no answer. One spelling
# so an empty screen never looks like five different kinds of broken.
EMPTY_VALUE_TEXT: str = "--"

# Shown in place of a panel whose render raised. The screen degrades to one bad
# row rather than to nothing at all -- see service.render_summary.
PANEL_ERROR_TEXT: str = "(unavailable)"


# ─── Panel ordering ──────────────────────────────────────────────────────────
# Panels declare an integer `order` and the registry sorts on it. Gaps of 10
# leave room to slot a panel in between two existing ones without renumbering
# the ones after it -- the same convention the combat rules priorities use.
PANEL_ORDER_IDENTITY: int = 10
PANEL_ORDER_VITALS: int = 20
PANEL_ORDER_READINESS: int = 30
PANEL_ORDER_SKILLS: int = 40
PANEL_ORDER_HOLDINGS: int = 50
PANEL_ORDER_WORLD: int = 60


# ─── Character mode (forward hook) ───────────────────────────────────────────
# 02_Player/Character_Modes.md defines Standard / Outsider / Mutant plus an
# independent Hardcore flag. None of it is implemented yet, so the identity
# panel reads these db attributes and falls back to the documented default.
#
# THIS IS NOT THE OWNER OF THAT FACT. When the Character Modes system ships it
# brings its own constants module and its own handler, and identity.py must be
# repointed at those -- these three exist only so the dossier has the right
# shape on the day that happens, not so mode lives here permanently.
CHARACTER_MODE_ATTR: str = "character_mode"
CHARACTER_MODE_DEFAULT: str = "Standard"
HARDCORE_ATTR: str = "hardcore"
HARDCORE_LABEL: str = "HARDCORE"


# ─── Duration display ────────────────────────────────────────────────────────
# Units for rendering a playtime figure as "6d 04h". The playtime VALUE is owned
# by typeclasses/characters.py (which accumulates it); only its formatting
# belongs here.
SECONDS_PER_MINUTE: int = 60
MINUTES_PER_HOUR: int = 60
HOURS_PER_DAY: int = 24

# Date format for the character's creation stamp.
CREATED_DATE_FORMAT: str = "%Y-%m-%d"
