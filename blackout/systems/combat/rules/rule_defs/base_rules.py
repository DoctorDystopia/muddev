"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: BaseActionRules — the nine overridable seams of a combat action,
             and the OSRS-exact default behaviour for every one of them.

A rules definition is DATA plus overrides. Subclasses set `key`, `name`, and
`priority` as class attributes and override only the seams they actually
change; the glass cannon amulet overrides one, the toy sword overrides one, the
malfunctioning gizmo overrides one. That keeps "adding a rule" to "adding one
file", per the repo convention.

This class IS the default implementation — there is no separate
DefaultActionRules. That mirrors BaseAura (a working default, excluded from
discovery) and means an override can call super() to get OSRS back for the
part it does not want to change.
"""

from __future__ import annotations

from systems.combat import combat_calc
from systems.combat import constants as const
from systems.progression.skills.constants import (
    BRAWN_SKILL_KEY,
    DEFENSE_SKILL_KEY,
    STRIKE_SKILL_KEY,
)

from .. import modifiers
from ..context import ActionResult


# Public constant definitions

# Placeholder key. The registry refuses to register any subclass still
# carrying it, which is what stops a definition that forgot to name itself
# from shadowing a real rule.
BASE_RULES_KEY = "base"

# Every seam name the pipeline resolves a winner for. Kept as data so the
# registry can compute which seams a subclass overrides by comparing bound
# functions, instead of each definition hand-maintaining an `overrides` tuple
# that goes stale the first time someone adds a method and forgets.
ACTION_SEAM_NAMES: tuple = (
    "contribute_modifiers",
    "effective_attack_level",
    "effective_strength_level",
    "effective_defense_level",
    "max_hit",
    "accuracy",
    "roll_accuracy",
    "roll_damage",
    "resolve",
)


# Private helper routines

def _seams(context):
    """Return the object that dispatches a seam to whoever won it.

    Falls back to the module's default rules when a context was built without
    going through the pipeline -- a hand-built context in a unit test. Without
    the fallback such a context would raise on the first nested seam call.
    """
    if context.rules is not None:
        return context.rules

    return DEFAULT_ACTION_RULES


class BaseActionRules:
    """
    Purpose: The default melee action, expressed as nine replaceable steps.

    Entry:
        Subclasses must set a unique `key`. `name`, `description`, and
        `priority` are optional but `priority` should name the tier that
        matches what the rule DOES (see RULES_PRIORITY_* in the combat
        constants), not the item that carries it.

    Exit/Returns:
        Not applicable — an interface plus its default implementation.

    Module Globals:
        BASE_RULES_KEY read by the registry.
        ACTION_SEAM_NAMES read by the registry.

    Methodology:
        Every default method is a short delegation to combat_calc, which stays
        pure and untouched as the OSRS oracle. An empty bag makes the modifier
        appliers the identity, so an action with no contributors reproduces
        combat_calc.resolve_melee_swing exactly -- asserted over fifty seeds by
        tests/test_action_pipeline.TestDefaultRulesMatchTheReference.

        roll_damage WRITES into the ActionResult rather than returning an int.
        That single choice is what keeps a "a 1 hurts you" weapon to one
        overridden method: a returning-int seam cannot express damage to the
        wielder as well as damage to the target.

        The three effective_*_level seams stay separate rather than collapsing
        into one key-dispatched method. Each is three lines, and a rule that
        changes only strength should not have to reimplement the other two or
        branch on a key.

    Notes/References:
        Two contributors overriding the SAME seam do not chain - the higher
        priority wins that seam outright. accuracy() would need previous-value
        plumbing to chain and resolve() cannot chain at all, and mixed
        semantics across nine seams is not reasonable-about-able. A definition
        that wants composition calls super() or calls two helpers itself.

    Author: Nick Hobar
    Creation date: 08/04/2026
    """

    key = BASE_RULES_KEY
    name = "Standard Combat"
    description = "The unmodified OSRS-derived melee action."
    priority = const.RULES_PRIORITY_DEFAULT

    # ─── Modifier contribution ───────────────────────────────────────────────

    def contribute_modifiers(self, context, bag) -> None:
        """
        Purpose: Add this rule's stat modifiers into the entity's bag.

        Entry:
            context - the ActionContext. Read-only here.
            bag     - the ModifierBag belonging to the entity this rule is
                      equipped on. Write only into this one.

        Exit/Returns:
            No conditions. Returns nothing; the contribution is the write.

        Module Globals:
            None.

        Methodology:
            No-op by default. Unlike the eight seams below, EVERY contributor's
            contribute_modifiers runs -- modifiers never lose to priority. That
            asymmetry is why modifiers and seams are two mechanisms and not one.

            A CONDITIONAL modifier must read its wearer's numbers through
            context.levels_for(bag), never through context.attacker_levels.
            The same definition can sit on the attacker or the defender in one
            action, and reading the attacker unconditionally would make a
            defender's amulet key off its opponent's stats.

        Notes/References:
            The bag validates channel keys and raises on an unknown one, so a
            typo fails at contribution time rather than accumulating into a
            number nothing reads.

        Author: Nick Hobar
        Creation date: 08/04/2026
        """
        return None

    # ─── Effective levels ────────────────────────────────────────────────────

    def effective_attack_level(self, context) -> int:
        """Return the attacker's effective Strike level for this action."""
        stance = context.stance_bonus(STRIKE_SKILL_KEY)
        base_level = context.attacker_levels[STRIKE_SKILL_KEY]

        return modifiers.apply_to_level(
            context.attacker_bag, const.CHANNEL_STRIKE_LEVEL, base_level, stance
        )

    def effective_strength_level(self, context) -> int:
        """Return the attacker's effective Brawn level for this action."""
        stance = context.stance_bonus(BRAWN_SKILL_KEY)
        base_level = context.attacker_levels[BRAWN_SKILL_KEY]

        return modifiers.apply_to_level(
            context.attacker_bag, const.CHANNEL_BRAWN_LEVEL, base_level, stance
        )

    def effective_defense_level(self, context) -> int:
        """Return the DEFENDER's effective Defense level for this action.

        Reads the defender's bag and the defender's levels. The attacker's
        stance boost never applies here: the defender is not the one choosing
        a combat style this tick.
        """
        base_level = context.defender_levels[DEFENSE_SKILL_KEY]

        return modifiers.apply_to_level(
            context.defender_bag, const.CHANNEL_DEFENSE_LEVEL, base_level, 0
        )

    # ─── Damage ceiling ──────────────────────────────────────────────────────

    def max_hit(self, context, eff_str: int) -> int:
        """
        Purpose: Compute the action's damage ceiling.

        Entry:
            context - the ActionContext.
            eff_str - the effective Brawn level from effective_strength_level.

        Exit/Returns:
            Integer max hit, floored at ACTION_DAMAGE_FLOOR.

        Module Globals:
            const.CHANNEL_STRENGTH_BONUS read.
            const.CHANNEL_MAX_HIT read.

        Methodology:
            The strength-bonus channel modifies the EQUIPMENT number before it
            enters the OSRS formula; the max-hit channel modifies the RESULT.
            Both exist because they are different design levers: "+5 strength
            bonus" scales with effective level, "+5 max hit" does not.

        Notes/References:
            H_max = floor( 0.5 + eff_str * (equip_str + 64) / 640 )

        Author: Nick Hobar
        Creation date: 08/04/2026
        """
        base_equip = context.strength_equip_bonus()
        equip_str = modifiers.apply_to_int(
            context.attacker_bag, const.CHANNEL_STRENGTH_BONUS, base_equip
        )
        raw_max = combat_calc.max_melee_hit(eff_str, equip_str)
        modified = modifiers.apply_to_int(
            context.attacker_bag, const.CHANNEL_MAX_HIT, raw_max
        )

        return modifiers.clamp_damage(modified)

    # ─── Accuracy ────────────────────────────────────────────────────────────

    def accuracy(self, context, eff_atk: int, eff_def: int) -> float:
        """
        Purpose: Compute the probability that this action connects.

        Entry:
            context - the ActionContext.
            eff_atk - the attacker's effective Strike level.
            eff_def - the DEFENDER's effective Defense level.

        Exit/Returns:
            Float probability, clamped to the declared hit-chance bounds.

        Module Globals:
            const.CHANNEL_ATTACK_BONUS read.
            const.CHANNEL_DEFENSE_BONUS read.
            const.CHANNEL_HIT_CHANCE read.

        Methodology:
            Attack and defense equipment bonuses are modified from their
            OWNERS' bags -- the defender's armour must never be scaled by an
            attacker's modifier -- then fed to the untouched OSRS rolls.

        Notes/References:
            Prefer the attack_bonus channel over the hit_chance channel when
            designing. The OSRS curve is provably bounded and self-correcting;
            a raw probability multiplier is neither, which is why the result
            here has to be clamped back into band.

        Author: Nick Hobar
        Creation date: 08/04/2026
        """
        equip_atk = modifiers.apply_to_int(
            context.attacker_bag,
            const.CHANNEL_ATTACK_BONUS,
            context.attack_equip_bonus(),
        )
        equip_def = modifiers.apply_to_int(
            context.defender_bag,
            const.CHANNEL_DEFENSE_BONUS,
            context.defense_equip_bonus(),
        )

        r_atk = combat_calc.melee_attack_roll(eff_atk, equip_atk)
        r_def = combat_calc.melee_defense_roll(eff_def, equip_def)
        chance = combat_calc.hit_chance(r_atk, r_def)
        modified = modifiers.apply_to_scalar(
            context.attacker_bag, const.CHANNEL_HIT_CHANCE, chance
        )

        return modifiers.clamp_hit_chance(modified)

    def roll_accuracy(self, context, chance: float) -> bool:
        """Roll the accuracy check. True means the action connects.

        Draws exactly one rng.random(), and must stay the FIRST draw of the
        action: seeded reproducibility depends on draw order, and
        combat_calc.resolve_melee_swing draws accuracy before damage.
        """
        roll = context.rng.random()

        return roll < chance

    # ─── Damage roll ─────────────────────────────────────────────────────────

    def roll_damage(self, context, result) -> None:
        """
        Purpose: Roll the connecting action's damage into the result.

        Entry:
            context - the ActionContext.
            result  - the ActionResult to write into. Writes `damage`, and may
                      write `self_damage` for a weapon that can hurt its user.

        Exit/Returns:
            No conditions. Returns nothing; the roll is the write.

        Module Globals:
            const.CHANNEL_DAMAGE read.

        Methodology:
            Uniform on [0, max_hit], then the damage channel, then the floor.
            Draws exactly one rng.randint, and must stay the SECOND draw of
            the action -- see roll_accuracy.

            An override that replaces the die (a d20 weapon) should NOT call
            super(): the max hit is the OSRS ceiling and a replacement die is
            deliberately not bound by it.

        Notes/References:
            A 0 here is a successful accuracy check followed by a 0 damage
            roll -- the OSRS "0 splat" -- and is distinct from a miss.

        Author: Nick Hobar
        Creation date: 08/04/2026
        """
        seams = _seams(context)
        eff_str = seams.effective_strength_level(context)
        ceiling = seams.max_hit(context, eff_str)
        rolled = combat_calc.roll_damage(ceiling, context.rng)
        modified = modifiers.apply_to_int(
            context.attacker_bag, const.CHANNEL_DAMAGE, rolled
        )

        result.damage = modifiers.clamp_damage(modified)

    # ─── Whole-action resolution ──────────────────────────────────────────────

    def resolve(self, context) -> ActionResult:
        """
        Purpose: Resolve one action end to end. The pipeline calls exactly this.

        Entry:
            context - a fully populated ActionContext whose bags have already
                      been filled by every contributor's contribute_modifiers.

        Exit/Returns:
            An ActionResult. `damage` is 0 on a miss OR on a connecting action
            that rolled 0.

        Module Globals:
            None.

        Methodology:
            Accuracy first, damage second, the same order and the same
            number of rng draws as combat_calc.resolve_melee_swing, so a
            seeded context produces the identical outcome. That equivalence is
            the net that stops the live path drifting from the OSRS reference.

            An override that replaces this seam bypasses accuracy, max hit,
            and every modifier channel. For a gadget that "just does 5" that
            is exactly right; for anything that should still respect gear,
            override a narrower seam instead.

        Notes/References:
            Nested seams are called through context.rules, NOT through self.
            Seams are resolved independently, so the contributor that won
            roll_damage is frequently not the one that won resolve; calling
            self.roll_damage here would run the default roll and silently
            ignore the weapon that was supposed to replace it.

        Author: Nick Hobar
        Creation date: 08/04/2026
        """
        seams = _seams(context)
        result = ActionResult(damage_type=const.DAMAGE_TYPE_MELEE) # Melee only existing action type right now

        eff_atk = seams.effective_attack_level(context)
        eff_def = seams.effective_defense_level(context)
        result.hit_prob = seams.accuracy(context, eff_atk, eff_def)

        if not seams.roll_accuracy(context, result.hit_prob):
            return result

        result.hit = True
        seams.roll_damage(context, result)

        return result


# Module globals

# The fallback seam owner. Every seam no contributor claims resolves to this
# instance, and a context built outside the pipeline dispatches to it.
DEFAULT_ACTION_RULES: BaseActionRules = BaseActionRules()
