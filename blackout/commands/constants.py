"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Help-category names for Blackout-authored commands.
"""

# ─── Help categories ─────────────────────────────────────────────────────────
# `help` groups commands by `help_category` and prints one block per category,
# sorted alphabetically. Every category below is prefixed "Blackout:" so the
# custom commands cluster together and read as distinct from Evennia's own
# stock categories (Admin, Building, Comms, General, System), which are left
# untouched on the default commands that still use them.
#
# One owner per fact: a command's category should come from here, never a
# literal string, so a rename only ever touches this file.
HELP_CATEGORY_ADMIN: str = "Blackout: Admin"
HELP_CATEGORY_BANKING: str = "Blackout: Banking"
HELP_CATEGORY_COMBAT: str = "Blackout: Combat"
HELP_CATEGORY_CRAFTING: str = "Blackout: Crafting"
HELP_CATEGORY_GATHERING: str = "Blackout: Gathering"
HELP_CATEGORY_GENERAL: str = "Blackout: General"
HELP_CATEGORY_PROGRESSION: str = "Blackout: Progression"
