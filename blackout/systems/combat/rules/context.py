"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: ActionContext and ActionResult — the input snapshot and output slot
             a rules definition reads and writes during one action.
"""

from __future__ import annotations

import random as _random_module
from dataclasses import dataclass, field

from systems.combat import constants as const
from systems.progression.skills.constants import COMBAT_SKILL_KEYS

from .modifiers import ModifierBag


# ─── Private constant definitions ────────────────────────────────────────────

# The live action RNG. A module-level Random instance rather than the `random`
# module itself so an ActionContext's `rng` field is ALWAYS a concrete Random --
# rules definitions call context.rng.randint directly and must never have to
# check for None the way combat_calc's optional rng parameter does.
_ACTION_RNG = _random_module.Random()

# Level fallback for an entity with no skills handler. A HostileNPC spawned
# without a stat block would otherwise KeyError out of the action entirely.
_MISSING_SKILL_LEVEL = 1


# ─── Private helper routines ─────────────────────────────────────────────────

def _default_rng() -> _random_module.Random:
    """Return the shared live action RNG. Used as a dataclass default_factory."""
    return _ACTION_RNG


# ─── Public routines ─────────────────────────────────────────────────────────

def read_skill_levels(entity) -> dict:
    """
    Purpose: Snapshot an entity's four combat skill levels into a plain dict.

    Entry:
        entity - any object. May or may not expose a `skills` handler; a
                 HostileNPC spawned without one is a supported case.

    Exit/Returns:
        dict keyed by every entry in COMBAT_SKILL_KEYS, values integer levels.
        Every key is always present. Missing skills read as
        _MISSING_SKILL_LEVEL rather than being absent.

    Module Globals:
        _MISSING_SKILL_LEVEL read.

    Methodology:
        One get_level call per key. Reading all four ONCE, here, is what lets
        the rest of the action treat levels as a consistent snapshot: without
        it, N contributors each do their own Attribute reads at the 0.6s tick
        cadence, and two contributors could disagree if a level-up landed
        between them.

    Notes/References:
        Fortitude is snapshotted even though no action resolves against it --
        rules definitions read it (glass cannon keys off Brawn-over-Fortitude).

    Author: Nick Hobar
    Creation date: 08/04/2026
    """
    skills = getattr(entity, "skills", None)
    levels = {}

    for skill_key in COMBAT_SKILL_KEYS:
        if skills is None:
            levels[skill_key] = _MISSING_SKILL_LEVEL
            continue

        levels[skill_key] = skills.get_level(skill_key)

    return levels


@dataclass
class ActionResult:
    """
    Purpose: The mutable output of one action. A rules seam writes here; nothing
    reads a seam's return value except `resolve`.

    Entry:
        hit         - True iff the accuracy roll succeeded.
        damage      - damage dealt to the DEFENDER. Never negative.
        self_damage - damage dealt to the ATTACKER by their own item. A
                      backfiring gadget or a fumbled die roll, not recoil from
                      a normal swing.
        hit_prob    - the probability the accuracy roll used, for the caller's
                      diagnostics.
        damage_type - one of the DAMAGE_TYPE_* constants. Threaded into
                      at_damage so death attribution and messaging can tell a
                      sword from a backfiring gadget.

    Exit/Returns:
        Not applicable — a data carrier.

    Module Globals:
        const.DAMAGE_TYPE_MELEE read (default).

    Methodology:
        `roll_damage` writes into this rather than returning an int, which is
        the single decision that keeps a "a 1 hurts you" weapon to one
        overridden method: a returning-int seam cannot express a second damage
        channel.

    Notes/References:
        Deliberately carries no `effects` list. Trigger hooks (on_hit /
        on_kill) are a later cut, and an unused list invites appends that go
        nowhere silently. This is a non-persisted dataclass, so adding the
        field later is a one-line change with no migration.

    Author: Nick Hobar
    Creation date: 08/04/2026
    """

    hit: bool = False
    damage: int = 0
    self_damage: int = 0
    hit_prob: float = 0.0
    damage_type: str = const.DAMAGE_TYPE_MELEE


@dataclass
class ActionContext:
    """
    Purpose: Everything one action needs to resolve, snapshotted once so every
    contributor sees the same numbers.

    Entry:
        attacker / defender - live CombatEntity objects.
        weapon              - the wielded item, or None (unarmed, or an NPC
                              carrying its stat block on itself).
        weapon_data         - the handler.ndb.active_weapon_data snapshot.
        style               - the active entry from the combat_styles table.
        attack_type         - one of MELEE_ATTACK_TYPES; selects which
                              equipment bonus keys the action reads.
        attacker_stats      - the attacker's combat_stat_bonuses.
        defender_stats      - the DEFENDER's combat_stat_bonuses.
        attacker_levels     - read_skill_levels(attacker).
        defender_levels     - read_skill_levels(defender).
        stance_boost        - style["weapon_style_level_boost"].
        attacker_rules      - priority-sorted contributor tuple.
        defender_rules      - the same for the defender.
        attacker_bag        - modifier accumulator the attacker's contributors
                              write into.
        defender_bag        - the same for the defender.
        rules               - the ResolvedActionRules for this action: the object
                              that knows which contributor won each seam. A
                              seam that needs to call ANOTHER seam must go
                              through this, never through `self`, see the
                              Methodology note below.
        rng                 - always a concrete random.Random, never None.

    Exit/Returns:
        Not applicable — a data carrier.

    Module Globals:
        _ACTION_RNG read via _default_rng.

    Methodology:
        Mutable, not frozen. `frozen=True` is shallow -- attacker_stats and
        the bags stay mutable regardless -- so it would buy a false guarantee
        while blocking the pipeline from filling in the rules tuples after
        construction.

        The contract is by convention instead: INPUTS ARE READ-ONLY to a rules
        definition. The only sanctioned writes are into a ModifierBag during
        contribute_modifiers, and into the ActionResult.

        `rules` carries the per-seam winners because seams are resolved
        INDEPENDENTLY. A player wielding a d20 sword while wearing an amulet
        that changes the max hit has one contributor owning roll_damage and a
        different one owning max_hit, with the default still owning resolve.
        If resolve called self.roll_damage it would run the DEFAULT roll and
        the sword would silently do nothing; going through context.rules
        dispatches to whoever actually won that seam.

        A definition that wants the OSRS default for a seam it is overriding
        still calls super() -- that is a statement about its own class, not
        about who won.

    Notes/References:
        Seeded reproducibility depends on the NUMBER AND ORDER of rng draws,
        not just the seed. BaseActionRules.resolve draws accuracy before damage
        to match combat_calc.resolve_melee_swing.

    Author: Nick Hobar
    Creation date: 08/04/2026
    """

    attacker: object
    defender: object
    weapon: object
    weapon_data: dict
    style: dict
    attack_type: str
    attacker_stats: dict
    defender_stats: dict
    attacker_levels: dict
    defender_levels: dict
    stance_boost: dict
    attacker_rules: tuple = ()
    defender_rules: tuple = ()
    attacker_bag: ModifierBag = field(default_factory=ModifierBag)
    defender_bag: ModifierBag = field(default_factory=ModifierBag)
    rules: object = None
    rng: _random_module.Random = field(default_factory=_default_rng)

    def attack_equip_bonus(self) -> int:
        """Return the attacker's equipment attack bonus for the active type."""
        bonus_key = f"{self.attack_type}_attack_bonus"

        return self.attacker_stats.get(bonus_key, 0)

    def defense_equip_bonus(self) -> int:
        """Return the DEFENDER's equipment defense bonus for the active type."""
        bonus_key = f"{self.attack_type}_defense_bonus"

        return self.defender_stats.get(bonus_key, 0)

    def strength_equip_bonus(self) -> int:
        """Return the attacker's melee strength bonus."""
        return self.attacker_stats.get("melee_strength_bonus", 0)

    def stance_bonus(self, skill_key: str) -> int:
        """Return the style's invisible level boost for one combat axis."""
        return self.stance_boost.get(skill_key, 0)

    def levels_for(self, bag: ModifierBag) -> dict:
        """Return the skill levels of whoever owns the given modifier bag.

        A conditional modifier must read the levels of the entity WEARING it,
        and contribute_modifiers is handed a bag rather than an entity. The
        same rules definition can sit on the attacker or the defender in the
        same action, so reading context.attacker_levels unconditionally would
        make a defender's amulet key off its opponent's stats.
        """
        if bag is self.defender_bag:
            return self.defender_levels

        return self.attacker_levels

    def stats_for(self, bag: ModifierBag) -> dict:
        """Return the equipment stat block of whoever owns the given bag."""
        if bag is self.defender_bag:
            return self.defender_stats

        return self.attacker_stats
