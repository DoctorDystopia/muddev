"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/02/2026
Description: The single source of truth for every item in Blackout. An ItemDef
             is rendered into exactly one Evennia prototype, which both the
             direct-creation and crafting paths spawn from.
"""



from dataclasses import dataclass, field

from evennia.prototypes.spawner import spawn

from items.equipment.constants import WieldLocation


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
    # combat_rules — list of keys into systems/combat/rules/RULES_REGISTRY.
    #     Each names a rules definition that changes how an action is resolved
    #     while this item is EQUIPPED, in any slot: a die replacement, a
    #     conditional stat modifier, or a whole-action override.
    #     A LIST, not one key, so behaviours combine without a bespoke class
    #     per combination. Unknown keys are logged and skipped, not raised.
    attack_speed: int | None = None
    combat_stat_bonuses: dict = field(default_factory=dict)
    combat_styles: dict = field(default_factory=dict)
    default_combat_style: str | None = None
    combat_rules: list = field(default_factory=list)

    def _get_attrs(self, quantity: int = 1) -> dict:
        """
        Purpose: Build the complete attribute set for one spawned item.

        Entry:
            quantity is the stack size to stamp on a stackable item. Ignored
            for non-stackable items.

        Exit/Returns:
            Returns a dict of attribute name -> value.

        Module Globals:
            None

        Methodology:
            This is the ONE place an ItemDef field becomes an object
            attribute. create() and to_prototype() both route through here.

        Notes/References:
            create() used to restate this list inline, and the two had already
            drifted: create() wrote tier/req_level unconditionally and a
            quantity that to_prototype() never emitted, while to_prototype()
            dropped tier/req_level when they were zero. The same item was a
            different database row depending on whether it was gathered or
            crafted.

        Author: Nick Hobar
        Creation date: 06/02/2026
        """
        attrs = {}
        attrs["value"] = self.value
        attrs["weight"] = self.weight
        attrs["tradeable"] = self.tradeable
        attrs["stackable"] = self.stackable
        attrs["tier"] = self.tier
        attrs["req_level"] = self.req_level

        if self.stackable:
            attrs["quantity"] = quantity
        if self.desc:
            attrs["desc"] = self.desc
        if self.use_slot is not None:
            attrs["use_slot"] = self.use_slot
        if self.tool_type is not None:
            attrs["tool_type"] = self.tool_type
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
        if self.combat_rules:
            attrs["combat_rules"] = list(self.combat_rules)

        return attrs

    def to_prototype(self, quantity: int = 1) -> dict:
        """
        Purpose: Render this definition as an Evennia prototype dict.

        Entry:
            quantity is the stack size for a stackable item.

        Exit/Returns:
            Returns a prototype dict suitable for evennia.prototypes.spawner.

        Module Globals:
            None

        Methodology:
            prototype_key is set from this def's key so every spawned object
            carries the prototype tag and can be found by origin later.

        Notes/References:
            Evennia's prototype system expects `attrs` as a list of
            (key, value, ...) tuples, not a dict -- passing a dict iterates
            keys only and silently drops every value.

        Author: Nick Hobar
        Creation date: 06/02/2026
        """
        attrs = self._get_attrs(quantity=quantity)
        proto = {
            "prototype_key": self.key,
            "key": self.name,
            "typeclass": self.typeclass,
            "tags": list(self.tags),
            "attrs": list(attrs.items()),
        }

        return proto

    def create(self, location=None, home=None, quantity=1, **kwargs):
        """
        Purpose: Spawn one instance of this item and place it.

        Entry:
            location is the Object to place the item in, or None to leave it
            detached.
            home is the item's home location; defaults to location.
            quantity is the stack size for a stackable item.

        Exit/Returns:
            Returns the spawned Object. The return may be a deleted row: if
            the destination merged the item into an existing stack, that
            merge deletes the incoming object. Callers that only want the
            item delivered can ignore the return, as all current ones do.

        Module Globals:
            None

        Methodology:
            Spawn detached, then move. The prototype deliberately carries no
            `location`, because spawning straight into a container runs the
            destination's at_object_receive before the attributes exist --
            and the inventory stack-merge reads `stackable` and `quantity` to
            decide what to do.

        Notes/References:
            This replaces a hand-rolled create_object plus a dozen
            attributes.add calls that restated _get_attrs from memory.

            Behaviour change worth knowing: create_object assigns
            db_location directly and never fires at_object_receive, so items
            made this way used to land in a character's contents without ever
            being registered in an inventory slot or merged into an existing
            stack -- a later inventory.sync() had to repair it. move_to runs
            the hook, so registration and stacking now happen up front.

        Author: Nick Hobar
        Creation date: 06/02/2026
        """
        prototype = self.to_prototype(quantity=quantity)
        spawned = spawn(prototype)
        obj = spawned[0]

        obj.home = home or location

        if location is not None:
            obj.move_to(location, quiet=True)

        return obj


from .item_defs.materials import ITEMS as _MATERIALS
from .item_defs.tools import ITEMS as _TOOLS
from .item_defs.currencies import ITEMS as _CURRENCIES
from .item_defs.weapons import ITEMS as _WEAPONS
from .item_defs.gadgets import ITEMS as _GADGETS
from .item_defs.jewellery import ITEMS as _JEWELLERY
from .item_defs.armor_body import ITEMS as _ARMOR_BODY

# Every def module must appear in BOTH lists below. A module imported but left
# out of the loop contributes nothing and raises nothing -- its items simply
# do not exist as far as the rest of the game is concerned.
ITEM_DB: dict[str, ItemDef] = {}
for _d in [_MATERIALS, _TOOLS, _CURRENCIES, _WEAPONS, _GADGETS, _JEWELLERY, _ARMOR_BODY]:
    ITEM_DB.update(_d)
