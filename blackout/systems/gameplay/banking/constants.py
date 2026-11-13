"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/08/2026
Description: Names, verbs and command templates for the vault layout: bank
             tabs, the order of the slots, and placeholders.

             The `bank` command, the layout model, the handler, and the bank
             pop-up read their words from here. Thus, the verb that the pop-up
             names and the verb that the command parses cannot differ.

             This module imports nothing from the game.
"""


# ─── Public constant definitions ─────────────────────────────────────────────

# The command that opens the vault. With a verb after it, it changes the
# layout: `bank view 2`, `bank move ore = new`. A telnet player types the same
# lines that the Godot pop-up sends.
BANK_COMMAND_KEY: str = "bank"

# The verbs of `bank <verb> ...`.
VERB_TABS: str = "tabs"
VERB_VIEW: str = "view"
VERB_MOVE: str = "move"
VERB_SWAP: str = "swap"
VERB_INSERT: str = "insert"
VERB_NAME: str = "name"
VERB_PLACEHOLDERS: str = "placeholders"
VERB_RELEASE: str = "release"
VERB_DRAG: str = "drag"

# The separator between the two sides of `move`, `swap`, `insert` and `name`.
# An `=`, the Evennia habit, because an item name can hold spaces.
ARG_SEPARATOR: str = "="

# The target of `move` that makes a tab. A number names a tab that exists.
NEW_TAB_WORD: str = "new"

# The argument of `release` that releases every placeholder.
RELEASE_ALL_WORD: str = "all"

# The two arguments of `placeholders`.
SWITCH_ON_WORD: str = "on"
SWITCH_OFF_WORD: str = "off"

# The main tab. It holds every item that is in no other tab. It is never
# removed, and it shows every item of the vault, grouped by tab.
MAIN_TAB: int = 0

# The first tab number that a player makes.
FIRST_TAB: int = 1

# The longest tab name, in characters. Long enough for "Herblore supplies",
# short enough for a tab button.
TAB_NAME_MAX_LENGTH: int = 18

# The characters a tab name may hold besides letters and digits. A `|` would
# start an Evennia colour code in a telnet line, so it is not one of them.
TAB_NAME_EXTRA_CHARACTERS: str = " '-_.&!?#+()"

# A new vault keeps a placeholder when the last unit leaves. OSRS calls this
# "Always set placeholders". The player turns it off with
# `bank placeholders off`.
PLACEHOLDERS_DEFAULT: bool = True

# The drag modes: what a drop of one vault slot on another does. Each mode is
# the verb that the drop sends, so `bank drag insert` makes a drop send
# `bank insert`. The OSRS bank calls this "Rearrange mode". The order is the
# order of the footer button: a click picks the next mode. A new vault swaps,
# as in OSRS and as the vault did before the modes.
DRAG_MODES: tuple = (VERB_SWAP, VERB_INSERT)
DRAG_MODE_DEFAULT: str = VERB_SWAP

# The fields of the stored layout record. The record is a plain dict in one
# Attribute, so its keys are named once.
RECORD_TABS: str = "tabs"
RECORD_NAMES: str = "names"
RECORD_META: str = "meta"
RECORD_VIEWED: str = "viewed"
RECORD_KEEP: str = "keep_placeholders"
RECORD_DRAG: str = "drag_mode"

# The fields of one meta entry: the display key, the prototype key the
# placeholder draws its mesh from, and whether the slot is a placeholder now.
META_KEY: str = "key"
META_PROTOTYPE: str = "prototype"
META_PLACEHOLDER: str = "placeholder"

# The command templates. `{index}`, `{name}`, `{target}` and `{text}` are
# filled by the server or by the client. The drag and text tokens are the
# statefeed's own, so the client fills them with its generated constants.
VIEW_TEMPLATE: str = f"{BANK_COMMAND_KEY} {VERB_VIEW} {{index}}"
MOVE_TEMPLATE: str = (
    f"{BANK_COMMAND_KEY} {VERB_MOVE} {{source}} {ARG_SEPARATOR} {{target}}")
SWAP_TEMPLATE: str = (
    f"{BANK_COMMAND_KEY} {VERB_SWAP} {{source}} {ARG_SEPARATOR} {{target}}")
INSERT_TEMPLATE: str = (
    f"{BANK_COMMAND_KEY} {VERB_INSERT} {{source}} {ARG_SEPARATOR} {{target}}")
DRAG_TEMPLATE: str = f"{BANK_COMMAND_KEY} {VERB_DRAG} {{mode}}"

# The template of a drop on a slot, for each drag mode. Every mode in
# DRAG_MODES has a row.
DROP_ON_SLOT_TEMPLATES: dict = {
    VERB_SWAP: SWAP_TEMPLATE,
    VERB_INSERT: INSERT_TEMPLATE,
}

NAME_TEMPLATE: str = (
    f"{BANK_COMMAND_KEY} {VERB_NAME} {{index}} {ARG_SEPARATOR} {{text}}")
CLEAR_NAME_TEMPLATE: str = f"{BANK_COMMAND_KEY} {VERB_NAME} {{index}}"
RELEASE_TEMPLATE: str = f"{BANK_COMMAND_KEY} {VERB_RELEASE} {{name}}"
PLACEHOLDERS_TEMPLATE: str = f"{BANK_COMMAND_KEY} {VERB_PLACEHOLDERS} {{switch}}"
