"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/20/2026
Description: The one owner of Blackout's menu key bindings and of the labels
             used to advertise them.
"""


# Public constant definitions

# EvMenu's auto_quit already accepts all three of these on every node of every
# menu, before it consults a node's own _default option -- see
# EvMenu.parse_input. Blackout therefore does NOT re-declare quitting as a menu
# option anywhere; it only advertises the binding in the footer. This tuple
# records the engine's behaviour so that the footer and the docs cannot drift
# away from what actually works.
QUIT_KEYS = ("q", "quit", "exit")

# Likewise built into EvMenu (auto_help / auto_look), and likewise advertised
# rather than declared.
HELP_KEYS = ("h", "help")
LOOK_KEYS = ("l", "look")

# The key a node's own options MUST use for "go up one level". Declared as an
# explicit option key rather than left to auto-numbering so that one letter
# means one thing on every screen, and so that a digit typed at a quantity
# prompt can never be stolen by a navigation option.
BACK_KEYS = ("b", "back")

# Yes/no confirmation. The whole word is bound as well as the letter, because a
# player who types "yes" should not be told it was not an option.
#
# Note that "n" is also list_node's built-in "next page" key. The two never
# meet: a confirmation is a plain node with two options, never a paginated
# list. Do not add a confirmation to a @list_node without re-keying it.
CONFIRM_YES_KEYS = ("y", "yes")
CONFIRM_NO_KEYS = ("n", "no")

# Quantity prompts. Every menu that asks "how many?" offers the same three
# shapes under the same three keys, whichever EvMenu node idiom it is built on.
QUANTITY_ONE_KEYS = ("1",)
QUANTITY_CUSTOM_KEYS = ("x",)
QUANTITY_ALL_KEYS = ("a", "all")

# Descriptions for the options whose meaning is identical everywhere. The
# navigational back options keep their own per-screen wording ("Back to
# recipes"), because naming the destination is worth more than uniform text --
# it is the KEY that standardises, not the sentence.
CANCEL_DESC = "Cancel"
QUANTITY_ONE_DESC = "1"
QUANTITY_CUSTOM_DESC = "X (custom)"

# Footer labels. The footer advertises only the bindings that are invisible --
# the ones EvMenu handles itself and that therefore appear in no option row.
QUIT_HINT_LABEL = "quit"
BACK_HINT_LABEL = "back"
HELP_HINT_LABEL = "help"

# Rendered between footer hints.
FOOTER_GAP = "   "

# What a node says to input that matched no option.
#
# Mirrors EvMenu's own _HELP_NO_OPTION_MATCH, and exists because arming a
# `_default` option SUPPRESSES that line: parse_input reaches the default
# branch instead of the else that prints it. A node arming one to catch a
# specific typed verb -- the sell and deposit nodes do, so a graphical client
# can act while the menu holds the cmdset -- therefore has to say this itself
# for everything else, or a typo silently redraws the screen.
#
# Restated here rather than imported out of evmenu because the name there is
# private and its value is ours to word.
NO_OPTION_MATCH = "Choose an option or try 'help'."
