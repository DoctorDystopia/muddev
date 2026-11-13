"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: Names, templates and wording for the pop-up system.

             A pop-up is a box that the server opens over the world pane of a
             graphical client: the bank today, the shop and the crafting
             stations next. Each one is a set of item grids, and each slot in a
             grid carries the whole commands that act on it.

             This module imports nothing from the game. The command, the
             service, every pop-up definition and the statefeed builder read
             their names from here, so no two of them can spell a verb
             differently.
"""


# ─── Public constant definitions ─────────────────────────────────────────────

# The one command every pop-up answers to. A graphical client sends it for the
# close button and for the quantity buttons. A telnet player can type it too,
# and that is the rule: the client sends only what a telnet player could type.
POPUP_COMMAND_KEY: str = "popup"

# The two sub-commands.
POPUP_ARG_CLOSE: str = "close"
POPUP_ARG_QUANTITY: str = "quantity"

# The whole close command, which the snapshot names so that the client never
# composes it.
POPUP_CLOSE_COMMAND: str = f"{POPUP_COMMAND_KEY} {POPUP_ARG_CLOSE}"

# The quantity command. `{amount}` is the statefeed's placeholder token, which
# the client fills in for the X button. It is formatted in, not typed, so the
# token has one owner: ACTION_AMOUNT_PLACEHOLDER.
POPUP_QUANTITY_TEMPLATE: str = f"{POPUP_COMMAND_KEY} {POPUP_ARG_QUANTITY} {{amount}}"

# Where the open pop-up lives on the character: ndb, so a reload closes it.
# A resync after the reload sends the closed state, so the client agrees.
OPEN_POPUP_ATTR: str = "open_popup"

# Where the quantity mode lives on the character: db, so it outlives a logout.
# OSRS keeps the bank's quantity button across sessions, and so does this.
# A dict of pop-up key -> mode, so the bank and a future shop keep their own.
QUANTITY_MODE_ATTR: str = "popup_quantity"

# Keys of the stored {key, anchor} dict in OPEN_POPUP_ATTR.
OPEN_KEY_FIELD: str = "key"
OPEN_ANCHOR_FIELD: str = "anchor"

# A quantity mode is an int, or this word for "every unit". The word is the
# same one `deposit` and `withdraw` already parse.
QUANTITY_ALL: str = "all"

# The fixed buttons, in the order OSRS draws them. X is not in this tuple: it
# is the prompted button, and it shows whatever custom amount is active.
QUANTITY_FIXED_MODES: tuple = (1, 5, 10)

# The mode a pop-up starts in before the player picks one.
QUANTITY_DEFAULT_MODE: int = 1

# The largest amount the X button may set. A bound, so a typed number cannot
# ask the bank for more units than any stack holds in practice.
QUANTITY_MAX_CUSTOM: int = 1_000_000

# Button labels.
QUANTITY_LABEL_X: str = "X"
QUANTITY_LABEL_ALL: str = "All"

# What the X button's box asks.
QUANTITY_PROMPT: str = "Set the quantity to how many?"

# A grid can name a layout: a doll shape that the client knows by its key.
# Each row of that grid names its place in the shape. The server names the
# shape and the places. The client owns where each place sits, as the paper
# doll owns where each wield location sits. A client with no table for the
# key draws the plain grid.
GRID_LAYOUT_FIELD: str = "layout"
ROW_PLACE_FIELD: str = "place"

# The body doll of the rig sockets (11/09/2026). Its places are the socket
# keys of systems/gameplay/augmentation/constants.py. The client export
# sends this key, so the client table names it with no typed copy.
POPUP_LAYOUT_RIG: str = "rig"

# A drag and its drop. `drag_key` is the name that a drag of a row carries.
# The bank vault fills its grid templates with it (10/08/2026).
#
# `drops` is the drop table of a target row (11/09/2026): drag key -> the
# whole command that a drop of that drag on this row sends. The client
# fills in nothing. A drag key with no entry is no drop, and the client
# shows the "no" cursor. The table may name a drag from any grid of the
# pop-up. The rig puts an augment into a socket this way. The server
# names every pair, so the rig fit rule stays on the server.
ROW_DRAG_KEY_FIELD: str = "drag_key"
ROW_DROPS_FIELD: str = "drops"


# Messages. Plain text: a colour code would reach a graphical client as a
# literal `|r`, the reason banking/messages.py gives.
MSG_NOTHING_OPEN: str = "You have nothing open."
MSG_CLOSED: str = "You close the {title}."
MSG_QUANTITY_SET: str = "Quantity set to {mode}."
MSG_QUANTITY_BAD: str = "Give a quantity from 1 to {maximum}, or 'all'."
MSG_USAGE: str = (
    "Usage: popup close, or popup quantity <1-{maximum}|all>."
)
