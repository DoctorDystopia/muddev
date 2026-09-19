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


from .oasis_shop import ITEMS as _OASIS

SHOP_DB: dict[str, ShopDef] = {}
for _d in [_OASIS]:
    SHOP_DB.update(_d)


def shop_def_for(shopkeep) -> ShopDef | None:
    """The ShopDef that a shopkeeper's db.shopdef_key names, or None."""
    key = getattr(shopkeep.db, "shopdef_key", None)

    if not key:
        return None

    return SHOP_DB.get(key)
