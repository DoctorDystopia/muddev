from world.item_database import ItemDef
from items.equipment.constants import WieldLocation

ITEMS = {
    "rusty_scrap_axe": ItemDef(
        key="rusty_scrap_axe",
        name="Rusty Scrap Axe",
        typeclass="typeclasses.items.ToolItem",
        desc="A crude axe hammered together from scrap metal.",
        value=10,
        weight=3.0,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="axe",
        tier=1,
        req_level=0,
        tags=[("rusty_scrap_axe", "crafting_tool")],
    ),
    "hammer": ItemDef(
        key="hammer",
        name="Hammer",
        typeclass="typeclasses.crafting_tools.Hammer",
        desc="A heavy hammer used for hitting things.",
        value=15,
        weight=4.0,
        tradeable=True,
        stackable=False,
        use_slot=WieldLocation.MAIN_HAND,
        tool_type="hammer",
        tier=1,
        req_level=0,
        tags=[("hammer", "crafting_tool")],
    ),
}
