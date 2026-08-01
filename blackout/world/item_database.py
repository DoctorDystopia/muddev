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
    # ─── Combat fields (weapons only; None on non-combat items) ──
    # attack_speed — integer ticks; one tick = COMBAT_TICK_SECONDS (0.6s).
    # combat_stat_bonuses — dict[str, int] keyed by per-damage-type stat (e.g.
    #     'stab_attack_bonus', 'slash_attack_bonus', 'crush_attack_bonus',
    #     'melee_strength_bonus', 'stab_defense_bonus', 'slash_defense_bonus',
    #     'crush_defense_bonus').
    #     The active style's attack_type (stab/slash/crush) selects
    #     which *_attack_bonus feeds the accuracy roll.
    # combat_styles — dict mapping a per-weapon style name (e.g. "stab") to
    #     a sub-dict containing:
    #       { 'weapon_style': 'accurate'|'aggressive'|'defensive'|'controlled',
    #         'attack_type': 'stab'|'slash'|'crush',
    #         'weapon_style_xp_skill': <skill key, or tuple of skill keys>,
    #         'weapon_style_level_boost': <MELEE_WEAPON_STYLE_LEVEL_BOOST_* dict ref> }
    #     Named combat_styles rather than attack_type so it does not collide
    #     with the per-style 'attack_type' key above, which names the damage
    #     type. Matches NpcDef.combat_styles.
    # default_combat_style — the key into combat_styles used when no
    #     /attackstyle command has selected another.
    attack_speed: int | None = None
    combat_stat_bonuses: dict = field(default_factory=dict)
    combat_styles: dict = field(default_factory=dict)
    default_combat_style: str | None = None

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
        # Combat fields — only emitted when populated; non-combat ItemDefs
        # stay clean.
        if self.attack_speed is not None:
            attrs["attack_speed"] = self.attack_speed
        if self.combat_stat_bonuses:
            attrs["combat_stat_bonuses"] = dict(self.combat_stat_bonuses)
        if self.combat_styles:
            attrs["combat_styles"] = dict(self.combat_styles)
        if self.default_combat_style is not None:
            attrs["default_combat_style"] = self.default_combat_style

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
            # NOTE: Evennia's prototype system expects attrs as a list of (key, value, ...) tuples,
            # not a dict. Dict iteration yields only keys, silently dropping all attribute values.
            # Keep the old dict form commented in case a custom spawner later handles it.
            # proto["attrs"] = attrs
            proto["attrs"] = list(attrs.items())

        return proto

    def create(self, location=None, home=None, quantity=1, **kwargs):
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
        if self.stackable:
            update("quantity", quantity)

        if self.desc:
            update("desc", self.desc)
        if self.use_slot is not None:
            update("use_slot", self.use_slot)
        if self.tool_type is not None:
            update("tool_type", self.tool_type)

        update("tier", self.tier)
        update("req_level", self.req_level)

        # Combat attributes
        if self.attack_speed is not None:
            update("attack_speed", self.attack_speed)
        if self.combat_stat_bonuses:
            update("combat_stat_bonuses", dict(self.combat_stat_bonuses))
        if self.combat_styles:
            update("combat_styles", dict(self.combat_styles))
        if self.default_combat_style is not None:
            update("default_combat_style", self.default_combat_style)

        return obj


from .item_defs.materials import ITEMS as _MATERIALS
from .item_defs.tools import ITEMS as _TOOLS
from .item_defs.currencies import ITEMS as _CURRENCIES
from .item_defs.weapons import ITEMS as _WEAPONS

ITEM_DB: dict[str, ItemDef] = {}
for _d in [_MATERIALS, _TOOLS, _CURRENCIES, _WEAPONS]:
    ITEM_DB.update(_d)
