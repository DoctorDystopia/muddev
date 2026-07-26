from dataclasses import dataclass, field


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


from .oasis_shop import ITEMS as _OASIS

SHOP_DB: dict[str, ShopDef] = {}
for _d in [_OASIS]:
    SHOP_DB.update(_d)
