"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: ItemDef entries for moderator tooling -- items that exist to be
             carried by staff, not earned by players.

             There is one, and there is meant to be one. The Moderator Egg is
             a MENU, not a bag of abilities: every new moderator power should
             become a node under systems/menus/dev_egg_menu.py, so that a
             moderator has one object to find and one screen to learn. A
             second dev item is how a game ends up with four of them and no
             agreement about which one heals.
"""

from world.item_database import ItemDef


# ─── Private constant definitions ────────────────────────────────────────────

# The tag category every moderator item declares. Deliberately NOT one of
# statefeed's ITEM_FAMILIES: the 3D pane falls an unknown family through to a
# generic mesh labelled with the item's real name, which is exactly right for
# an object no art was ever commissioned for. See _item_family.
_DEV_TOOL_TAG_CATEGORY = "dev_tool"

_MODERATOR_EGG_DESC = (
    "A smooth ovoid of dull ceramic, warm to the touch and heavier than it "
    "has any right to be. Hairline seams across its surface shift when you "
    "are not looking at them directly. It does not belong to the world so "
    "much as sit on top of it."
)


ITEMS = {
    "moderator_egg": ItemDef(
        key="moderator_egg",
        name="Moderator Egg",
        typeclass="typeclasses.dev_tools.ModeratorEgg",
        desc=_MODERATOR_EGG_DESC,
        # Worthless and weightless on purpose. A staff tool must never move a
        # carry calculation, and a shop must never put a price on it.
        value=0,
        weight=0.0,
        # The single most important field here. tradeable=False keeps the egg
        # out of the shop's sell path and out of any future trade window, so
        # the only way one reaches a player is a moderator handing it over --
        # which is a decision someone made, not an accident of the economy.
        tradeable=False,
        stackable=False,
        # No use_slot: the egg is used from the bag, never worn. Nothing about
        # it is equipment, and giving it a slot would put it in the equipment
        # screen's rotation for no reason.
        tier=0,
        req_level=0,
        tags=[("moderator_egg", _DEV_TOOL_TAG_CATEGORY)],
    ),
}
