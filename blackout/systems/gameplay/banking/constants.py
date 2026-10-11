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
VERB_NAME: str = "name"
VERB_PLACEHOLDERS: str = "placeholders"
VERB_RELEASE: str = "release"

# The separator between the two sides of `move`, `swap` and `name`. An `=`,
# the Evennia habit, because an item name can hold spaces.
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

# The fields of the stored layout record. The record is a plain dict in one
# Attribute, so its keys are named once.
RECORD_TABS: str = "tabs"
RECORD_NAMES: str = "names"
RECORD_META: str = "meta"
RECORD_VIEWED: str = "viewed"
RECORD_KEEP: str = "keep_placeholders"

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
NAME_TEMPLATE: str = (
    f"{BANK_COMMAND_KEY} {VERB_NAME} {{index}} {ARG_SEPARATOR} {{text}}")
CLEAR_NAME_TEMPLATE: str = f"{BANK_COMMAND_KEY} {VERB_NAME} {{index}}"
RELEASE_TEMPLATE: str = f"{BANK_COMMAND_KEY} {VERB_RELEASE} {{name}}"
PLACEHOLDERS_TEMPLATE: str = f"{BANK_COMMAND_KEY} {VERB_PLACEHOLDERS} {{switch}}"
