import importlib
import pkgutil
from dataclasses import dataclass, field


# Seconds between two restocks of one ware, when its WareStock names none.
# OSRS restocks one unit at a time, on a timer that differs for each item.
DEFAULT_RESTOCK_SECONDS: float = 60.0


@dataclass
class WareStock:
    """The stock rule of one ware in one shop.

    max_stock is the level that the shop restocks to. A buy lowers the level,
    and the shop adds one unit back each restock_seconds until it is full.
    A ware with no WareStock in ShopDef.stock has endless stock.
    """
    max_stock: int
    restock_seconds: float = DEFAULT_RESTOCK_SECONDS


@dataclass
class ShopDef:
    key: str
    name: str = ""
    desc: str = ""
    greeting: str = '"Welcome."'
    farewell: str = '"Farewell."'
    upsell_factor: float = 1.5
    miser_factor: float = 0.5
    max_held_items: int = 20
    buy_list: list[str] = field(default_factory=list)
    # Ware key -> WareStock. Every key must also be in buy_list. A buy_list
    # ware that is not here has endless stock, so a shop with an empty dict
    # is an endless shop.
    stock: dict[str, WareStock] = field(default_factory=dict)


# The dict that each shop module exports.
_SHOPS_ATTR: str = "ITEMS"


def _discover_shops() -> dict[str, ShopDef]:
    """
    Purpose: Build SHOP_DB from every module in this package.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a dict of shop key -> ShopDef.

    Module Globals:
        _SHOPS_ATTR read.

    Methodology:
        Each module exports a dict named ITEMS. A new shop file needs no
        registration. Until 10/27/2026 this was a list of imports, and a new
        file that nobody added to the list was not a shop. Two faults raise
        at import: a key that two modules define, and an entry whose dict
        key differs from its own `key`.

    Notes/References:
        world/npc_database.py walks world/npc_defs the same way. The modules
        import ShopDef from this package, so this runs after the classes
        exist.

    Author: Nick Hobar
    Creation date: 10/27/2026
    """
    registry = {}

    for info in pkgutil.iter_modules(__path__):
        module = importlib.import_module(f"{__name__}.{info.name}")
        entries = getattr(module, _SHOPS_ATTR, {})

        for key, shop_def in entries.items():
            if key != shop_def.key:
                raise ValueError(
                    f"SHOP_DB: {info.name} files {shop_def.key!r} under {key!r}.")

            if key in registry:
                raise ValueError(f"SHOP_DB: {key!r} is defined two times.")

            registry[key] = shop_def

    return registry


SHOP_DB: dict[str, ShopDef] = _discover_shops()


def shop_def_for(shopkeep) -> ShopDef | None:
    """
    The ShopDef of a shopkeep, or None.

    The NpcDef of the shopkeep names it (`shop_key`). A shopkeep with no def
    falls back to db.shopdef_key, which every shopkeep carried until
    10/09/2026. The def comes first, so a stale row cannot hide it.
    """
    npc_def = getattr(shopkeep, "npc_def", None)
    key = npc_def.shop_key if npc_def is not None else None

    if not key:
        key = getattr(shopkeep.db, "shopdef_key", None)

    if not key:
        return None

    return SHOP_DB.get(key)
