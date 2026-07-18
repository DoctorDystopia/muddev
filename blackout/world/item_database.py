from dataclasses import dataclass, field
from items.equipment.constants import WieldLocation
from evennia import create_object


@dataclass
class ItemDef:
    key: str
    name: str
    typeclass: str = "typeclasses.items.BaseItem"
    desc: str = ""
    value: int = 0
    weight: float = 0.0
    tradeable: bool = True
    stackable: bool = False
    use_slot: WieldLocation | None = None
    tool_type: str | None = None
    tier: int = 0
    req_level: int = 0
    tags: list = field(default_factory=list)

    def _get_attrs(self) -> dict:
        attrs = {}
        attrs["value"] = self.value
        attrs["weight"] = self.weight
        attrs["tradeable"] = self.tradeable
        attrs["stackable"] = self.stackable
        if self.use_slot is not None:
            attrs["use_slot"] = self.use_slot
        if self.tool_type is not None:
            attrs["tool_type"] = self.tool_type
        if self.tier:
            attrs["tier"] = self.tier
        if self.req_level:
            attrs["req_level"] = self.req_level
        return attrs

    def to_prototype(self) -> dict:
        proto = {
            "key": self.name,
            "typeclass": self.typeclass,
            "tags": list(self.tags),
        }
        if self.desc:
            proto["desc"] = self.desc
        attrs = self._get_attrs()
        if attrs:
            proto["attrs"] = attrs
        return proto

    def create(self, location=None, home=None, **kwargs):
        obj = create_object(
            self.typeclass,
            key=self.name,
            location=location,
            home=home or location,
            tags=list(self.tags),
        )
        update = obj.attributes.add
        update("value", self.value)
        update("weight", self.weight)
        update("tradeable", self.tradeable)
        update("stackable", self.stackable)
        if self.desc:
            update("desc", self.desc)
        if self.use_slot is not None:
            update("use_slot", self.use_slot)
        if self.tool_type is not None:
            update("tool_type", self.tool_type)
        update("tier", self.tier)
        update("req_level", self.req_level)
        return obj


from .item_defs.materials import ITEMS as _MATERIALS
from .item_defs.tools import ITEMS as _TOOLS

ITEM_DB: dict[str, ItemDef] = {}
for _d in [_MATERIALS, _TOOLS]:
    ITEM_DB.update(_d)
