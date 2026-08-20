"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Per-combatant BlackoutCombatHandler (DefaultScript) and action
             classes for twitch-style melee combat — attack, hold, flee, wield.
"""

from evennia.utils import logger

from items.equipment.constants import WieldLocation
from items.equipment.handler import EquipmentError
from systems.statefeed import events as feed

from . import combat_msg
from . import constants as const
from systems.tick import states
from systems.tick.states import ActivityEvent
from systems.tick.tickable import TickableHandler, ensure_handler, register_tickable
from systems.tick.tickable import get_handler_for as _get_tickable_handler_for


# ─── module constants ──────────────────────────────────────────────────────

# Canonical key for the per-combatant handler, used as its HANDLER_KEY, by
# @register_tickable, and by the CombatEntity.combat accessor. Declared up here
# rather than at the foot of the module because the class body now reads it.
COMBAT_HANDLER_KEY = "blackout_combat_handler"

# Every action kind queue_action will accept. A table rather than a branch
# chain, so adding an action means adding an entry and an apply_action case
# rather than editing a validation ladder.
_QUEUEABLE_ACTION_KINDS = frozenset({"attack", "hold", "flee", "wield"})
from .protocols import Combatant
from .rules.context import ActionContext, read_skill_levels
from .rules.contributors import collect_contributors
from .rules.pipeline import resolve_action



# ─── Weapon-style => XP award table ───────────────────────────────────────

_WEAPON_STYLE_XP_MAP: dict[str, float] = {
    "accurate": const.XP_PER_DAMAGE_ACCURATE,
    "aggressive": const.XP_PER_DAMAGE_AGGRESSIVE,
    "controlled": const.XP_PER_DAMAGE_CONTROLLED_EACH,
    "defensive": const.XP_PER_DAMAGE_DEFENSIVE,
}



def _normalize_xp_skills(xp_skill) -> tuple:
    """Resolve a style's XP-skill entry to a tuple of skill keys.

    Accepts a single key ("strike") or any iterable of keys. Returns an empty
    tuple when the style awards nothing.
    """
    if xp_skill is None:
        return ()

    if isinstance(xp_skill, str):
        return (xp_skill,)

    return tuple(xp_skill)


def _plan_style_xp(attacker, style: dict, damage: int) -> list:
    """Work out what XP a combat action earns, WITHOUT granting any of it.

    attacker — a CombatEntity that exposes .skills (Character / HostileNPC).
    style    — one entry from the entity's combat_styles table.
    damage   — the integer damage returned by resolve combat action
               (e.g., combat_calc.resolve_melee_swing).

    Returns a list of (skill_key, amount) pairs, already filtered to the awards
    worth granting. Planning is split from granting so the action message can
    name the XP on the same line as the damage: the player is told what the hit
    earned, instead of having to reopen the skills panel to find out.

    Every skill the style names receives the style's full per-skill rate. The
    rates in constants.py are already per-skill shares, so this must NOT
    divide again.
    """
    style_name = style.get("weapon_style")
    xp_per_damage = _WEAPON_STYLE_XP_MAP.get(style_name)

    if xp_per_damage is None:
        logger.log_err(
            f"_plan_style_xp: unknown weapon_style {style_name!r} on {attacker}; no XP awarded."
        )
        return []

    if getattr(attacker, "skills", None) is None:
        return []

    raw_targets = style.get("weapon_style_xp_skill")
    skill_targets = _normalize_xp_skills(raw_targets)

    awards = []

    for skill_key in skill_targets:
        # A skill may earn at its own rate rather than the style's -- Fortitude
        # earns 1.33/damage from every style, not the style's 4.0.
        rate = const.XP_PER_DAMAGE_BY_SKILL.get(skill_key, xp_per_damage)
        award = int(round(rate * damage))

        if award <= 0:
            continue

        awards.append((skill_key, award))

    return awards


def _apply_xp_awards(attacker, awards) -> None:
    """Grant a plan built by _plan_style_xp. Safe to call with an empty plan."""
    skills = getattr(attacker, "skills", None)
    if skills is None:
        return

    for skill_key, amount in awards:
        skills.add_xp(skill_key, amount)


def _award_style_xp(attacker, style: dict, damage: int) -> list:
    """Plan and immediately grant a combat action's XP. Returns the granted plan.

    The combat action path calls the two halves separately so it can print the
    award before it lands; this wrapper exists for every other caller, which
    only wants the XP to happen.
    """
    awards = _plan_style_xp(attacker, style, damage)
    _apply_xp_awards(attacker, awards)

    return awards


def _labelled_awards(awards) -> list:
    """Map an XP plan's skill keys to their player-facing display names.

    SKILL_REGISTRY owns skill names, so combat must not title-case keys itself
    ("brain_farming" is displayed "Brain Farming", not "Brain_Farming"). The
    import is deferred for the same reason as ObjectDB above: this module is
    pulled in from typeclass modules during startup, and the registry walks the
    whole skill_defs package on first import.
    """
    from systems.progression.skills.registry import SKILL_REGISTRY

    labelled = []

    for skill_key, amount in awards:
        skill_class = SKILL_REGISTRY.get(skill_key)
        display_name = getattr(skill_class, "name", skill_key)
        labelled.append((display_name, amount))

    return labelled


# ─── Helper-tool functions (encapsulate repetitive dict accesses) ─────────

def _object_by_id(obj_id):
    """Resolve a dbid to a live Evennia Object, or None if it is gone.

    The ObjectDB import stays deferred: this module is pulled in from
    typeclass modules during startup, before the app registry is ready.
    Centralized here because the same try/except was open-coded three times
    in this file alone.
    """
    if obj_id is None:
        return None

    from evennia.objects.models import ObjectDB

    try:
        return ObjectDB.objects.get(id=obj_id)
    except ObjectDB.DoesNotExist:
        return None


def _stored_combat_styles(entity) -> dict:
    """Read an entity's combat-style table off its db attributes.

    Named `combat_styles` rather than `attack_type` so it does not collide
    with the per-style `attack_type` key, which names the damage type
    (stab/slash/crush) instead of the table.
    """
    styles = getattr(entity.db, "combat_styles", None)

    if styles:
        return styles

    return {}


def _unarmed_weapon_data() -> dict:
    """Build the active_weapon_data snapshot when no weapon is wielded.

    Centralizes the unarmed-fallback structure used by at_script_creation
    and _refresh_weapon.
    """
    return {
        "combat_stat_bonuses": const.UNARMED_DEFAULT_COMBAT_STATS.copy(),
        "active_combat_style": const.UNARMED_COMBAT_STYLES[const.UNARMED_DEFAULT_COMBAT_STYLE].copy(),
        "attack_speed": const.UNARMED_ATTACK_SPEED_TICKS,
    }


def held_weapon(entity):
    """Return the entity's wielded weapon (two-handed first), or None.

    A two-handed weapon lives in WieldLocation.TWO_HANDS, never MAIN_HAND, so
    checking only the main hand silently reduced every two-hander to unarmed
    stats.
    """
    equipment = getattr(entity, "equipment", None)
    if equipment is None:
        return None

    slots = equipment.slots

    return slots.get(WieldLocation.TWO_HANDS) or slots.get(WieldLocation.MAIN_HAND)


def _combat_style_source(entity):
    """Return the object carrying `entity`'s combat STYLE and attack speed, or None.

    A HostileNPC has no equipment handler and carries its spawner-stamped
    style/speed on itself. A Character reads them off the weapon it is
    wielding -- style and attack speed are inherently weapon-specific and,
    unlike stat bonuses, are never summed across equipped slots. None means
    "no weapon wielded"; the caller falls back to the unarmed style
    regardless of what armour (if any) is equipped.

    This single choice is what lets the profile below read one uniform set of
    db fields for style/speed, regardless of who is fighting.
    """
    if entity is None:
        return None

    if not hasattr(entity, "equipment"):
        return entity

    return held_weapon(entity)


def available_combat_styles(weapon) -> dict:
    """Return the style-key -> style-dict table stored on `weapon`.

    Thin public wrapper around _stored_combat_styles so callers outside this
    module (the combat-options menu) read the table through one accessor.
    """
    return _stored_combat_styles(weapon)


def active_combat_style_key(weapon):
    """Return the style key currently active on `weapon`, or None if it has
    no styles registered. Mirrors the default-key resolution
    _resolve_style_and_speed uses, without needing the unarmed fallback dict.
    """
    styles = _stored_combat_styles(weapon)
    stored = getattr(weapon.db, "default_combat_style", None)

    if stored and stored in styles:
        return stored

    return next(iter(styles), None)


def set_combat_style(weapon, style_key: str, combatant=None) -> bool:
    """Set `weapon`'s active combat style. Returns False if style_key names
    no style on this weapon, leaving the current style untouched.

    If `combatant` is mid-fight, refreshes its cached active_weapon_data the
    same way ActionWield.resolve does after a weapon swap -- otherwise the
    new style would not take effect until the next wield or combat entry.
    """
    styles = _stored_combat_styles(weapon)
    if style_key not in styles:
        return False

    weapon.db.default_combat_style = style_key

    if combatant is not None and combatant.combat is not None:
        combatant.combat._refresh_weapon()

    return True


def _resolve_style_and_speed(style_source, unarmed: dict) -> tuple:
    """Return (active_combat_style, attack_speed) for one style source.

    style_source is the wielded weapon, an NPC carrying its own block, or
    None -- which falls back to the unarmed profile untouched.
    """
    if style_source is None:
        return unarmed["active_combat_style"], unarmed["attack_speed"]

    styles = _stored_combat_styles(style_source)

    default_key = getattr(style_source.db, "default_combat_style", None) or next(
        iter(styles), const.UNARMED_DEFAULT_COMBAT_STYLE
    )

    active_combat_style = styles.get(default_key) or unarmed["active_combat_style"]
    speed = getattr(style_source.db, "attack_speed", None) or const.UNARMED_ATTACK_SPEED_TICKS

    return active_combat_style, speed


def _resolve_stat_bonuses(entity, style_source, unarmed: dict) -> dict:
    """Return the combat_stat_bonuses dict `entity` fights with.

    A Character's total is the SUM across every equipped slot (weapon,
    off-hand, armour, jewellery), via
    EquipmentHandler.total_combat_stat_bonuses -- this is the seam the
    "multi-slot armour aggregation" comment used to point at. An NPC has no
    equipment handler and keeps its single spawner-stamped stat block, read
    off `style_source` (only consulted for this branch, since a Character's
    total does not depend on which weapon, if any, is held).
    """
    equipment = getattr(entity, "equipment", None)

    if equipment is not None:
        merged = dict(unarmed["combat_stat_bonuses"])
        for stat_key, stat_value in equipment.total_combat_stat_bonuses().items():
            merged[stat_key] = merged.get(stat_key, 0) + stat_value
        return merged

    stats = getattr(style_source.db, "combat_stat_bonuses", None) if style_source else None

    return dict(stats) if stats else dict(unarmed["combat_stat_bonuses"])


def combat_profile(entity) -> dict:
    """Build the full active_weapon_data snapshot for `entity`.

    Returns the same shape as _unarmed_weapon_data:
        combat_stat_bonuses / active_combat_style / attack_speed

    This is the ONE place that resolves where combat stats come from.

    combat_stat_bonuses is the SUM across every equipped slot for a Character
    (see _resolve_stat_bonuses); active_combat_style and attack_speed stay
    sourced from the single wielded weapon, since those are not summable the
    way flat stat bonuses are -- wearing two attack-speed items does not
    average their speeds.
    """
    if entity is None:
        return _unarmed_weapon_data()

    unarmed = _unarmed_weapon_data()
    style_source = _combat_style_source(entity)

    active_combat_style, speed = _resolve_style_and_speed(style_source, unarmed)
    stats = _resolve_stat_bonuses(entity, style_source, unarmed)

    return {
        "combat_stat_bonuses": stats,
        "active_combat_style": dict(active_combat_style),
        "attack_speed": speed,
    }


def get_defense_bonuses(entity) -> dict:
    """Return the combat_stat_bonuses dict to use for `entity`'s DEFENSE.

    The defender's armour must never be read out of the *attacker's* stat
    block, which is why this takes the defender explicitly.
    """
    profile = combat_profile(entity)
    
    return profile["combat_stat_bonuses"]


# ─── Action classes ──────────────────────────────────────────────────────

class _Action:
    """Abstract twitch-combat action.

    Subclasses define resolve(handler) which the CombatHandler calls each
    tick when its personal weapon cooldown counter hits zero.

    Two class attributes tell the tick loop what to do AFTER resolve():

        consumes_cooldown — True if this action costs a weapon-speed cooldown
                            before anything may resolve again.
        next_action()     — the action to leave queued. Returning None idles
                            the combatant.

    Declaring both on the subclass is what keeps tick() free of `if kind ==`
    branches; a new action type needs no edit to the tick loop.
    """

    consumes_cooldown: bool = False

    def __init__(self, kind: str) -> None:
        self.kind = kind

    def resolve(self, handler):
        """Execute the action and report what happened to the activity.

        Returns an ActivityEvent. Subclasses do NOT tear anything down: the
        transition table decides what an outcome means, which is what keeps
        an action from having to know about handler teardown at all.
        """
        raise NotImplementedError

    def next_action(self, handler):
        """Return the action to queue after this one resolves (None = idle)."""
        return None


class ActionAttack(_Action):
    """An on-pace combat action (e.g., melee swing) resolved against the combatant's current target."""

    consumes_cooldown = True

    def __init__(self, target_id: int) -> None:
        super().__init__("attack")
        self.target_id = target_id


    def next_action(self, handler):
        """Keep performing combat actions at the same target until told otherwise."""
        return self


    def _get_target(self):
        target = _object_by_id(self.target_id)
        return target


    def _land_hit(self, context, result) -> bool:
        """Announce, damage, and pay out one connecting combat action (e.g., melee swing).

        Returns True if the hit was lethal.

        Takes the ActionContext and ActionResult rather than loose arguments so
        the damage SOURCE and TYPE reach at_damage: a gadget that discharges
        for 5 and a sword that rolls 5 have to be distinguishable to the death
        broadcast even though the number is identical.

        Everything the players see is sent BEFORE at_damage runs, because
        at_damage broadcasts the death line and a killed NPC then deletes
        itself: announcing afterwards printed "X collapses" above the very hit
        that killed it, and dropped the room broadcast for the killing blow
        entirely once .location had gone None.

        That inversion is also why the HP bar works off arithmetic rather than
        re-reading target.hp — the bar has to show the post-hit total while the
        hit has not been applied yet.
        """
        attacker = context.attacker
        target = context.defender
        style = context.style
        dmg = result.damage
        room = getattr(target, "location", None)

        # Decide lethality from the pre-damage HP rather than polling
        # is_alive() afterwards. A player's at_death runs respawn(), which
        # restores full HP synchronously, so the post-hoc poll always reported
        # the victim alive and the fight never ended.
        hp_before = getattr(target, "hp", 0)
        hp_after = max(0, hp_before - dmg)
        max_hp = getattr(target, "max_hp", 0)
        killed = (dmg >= hp_before)

        awards = _plan_style_xp(attacker, style, dmg)
        xp_text = combat_msg.format_xp_gain(_labelled_awards(awards))

        attacker.msg(
            (combat_msg.format_outgoing_hit(attacker, target, dmg, xp_text),
             {"type": "testing"},
            )
        )
        attacker.msg(
            (
                combat_msg.format_hp_status(target.key, hp_after, max_hp),
                {"type": "target_health"},
            )
        )

        target.msg(
            (
                combat_msg.format_incoming_hit(attacker, target, dmg),
                {"type": "testing"},
            )
        )
        target.msg(
            (
                combat_msg.format_hp_status(combat_msg.SELF_HP_LABEL, hp_after, max_hp),
                {"type": "player_health"},
            )
        )

        if room is not None:
            third_party = combat_msg.format_third_party_hit(attacker, target, dmg)
            room.msg_contents(third_party, exclude=(attacker, target))

        # Pay the XP before the damage so a level-up line reads next to the
        # award that caused it, rather than below the target's death.
        _apply_xp_awards(attacker, awards)

        # Publish the structured mirror of everything announced above, while
        # the target still exists. This has to sit on the same side of
        # at_damage as the text for the same reason the text does: a killed NPC
        # deletes itself in there, and a client resolving target_id afterwards
        # would have nothing to attach a death animation to.
        # TODO: update emit_swing name (e.g, emit_combat_action). Also, might be
        # other useful metadata to carry through the pipeline
        feed.emit_swing(context, result, hp_after, max_hp, killed)

        target.at_damage(
            dmg,
            attacker=attacker,
            source=context.weapon,
            damage_type=result.damage_type,
        )

        return killed


    def _build_context(self, handler, attacker, target) -> ActionContext:
        """Snapshot everything one combat action needs into an ActionContext.

        This is the seam that replaced a block of loose local variables. The
        action's inputs now travel as one object, which is what lets a rules
        definition reach the wielder's own stats -- an amulet that keys off
        Brawn-over-Fortitude cannot be expressed against six bare integers.

        Contributors come from handler.ndb.active_rules, cached beside
        active_weapon_data: collecting them is an Attribute read per equipped
        item and this runs on the 0.6s tick.
        """
        weapon_data = handler.ndb.active_weapon_data or _unarmed_weapon_data()
        style = weapon_data.get("active_combat_style")

        if not style:
            # A malformed/missing style dict would otherwise KeyError below and
            # kill the combat action.
            logger.log_err(
                f"ActionAttack: {attacker} has no usable attack style; falling back to unarmed."
            )
            style = const.UNARMED_COMBAT_STYLES[const.UNARMED_DEFAULT_COMBAT_STYLE]

        attacker_stats = (
            weapon_data.get("combat_stat_bonuses") or const.UNARMED_DEFAULT_COMBAT_STATS
        )

        return ActionContext(
            attacker=attacker,
            defender=target,
            weapon=held_weapon(attacker),
            weapon_data=weapon_data,
            style=style,
            attack_type=style["attack_type"],
            attacker_stats=attacker_stats,
            defender_stats=get_defense_bonuses(target),
            attacker_levels=read_skill_levels(attacker),
            defender_levels=read_skill_levels(target),
            stance_boost=style.get("weapon_style_level_boost") or {},
            attacker_rules=handler.active_rules(),
            defender_rules=collect_contributors(target),
        )

    def _land_backfire(self, context, result) -> bool:
        """Apply a combat action's self-damage to the attacker. True if it killed them.

        Same message-before-damage ordering as _land_hit, and for the same
        reason: at_damage can end in at_death, which broadcasts and then
        respawns. Announcing afterwards would print the backfire line below
        the death it caused.

        The attacker is passed as their own `attacker` truthfully; at_death
        normalises a self-kill so the victim is not credited with their own
        kill.

        damage_type is carried through from the rule's result verbatim, NOT
        hard-coded here: self-damage is typed by whatever caused it (a
        malfunctioning energy gizmo backfires as DAMAGE_TYPE_ENERGY, not a
        dedicated "backfire" type), the same as it would be typed if it had
        landed on a target instead of the wielder. "Backfire" is a delivery
        mechanism, not a damage type; at_death's self-inflicted check is what
        picks the death line, independent of this.
        """
        attacker = context.attacker
        hurt = result.self_damage
        hp_before = getattr(attacker, "hp", 0)
        hp_after = max(0, hp_before - hurt)
        max_hp = getattr(attacker, "max_hp", 0)
        killed = (hurt >= hp_before)

        attacker.msg(combat_msg.format_backfire(attacker, context.weapon, hurt))
        attacker.msg(
            combat_msg.format_hp_status(
                combat_msg.SELF_HP_LABEL,
                hp_after,
                max_hp,
            )
        )

        # TODO: update emit_swing name (e.g, emit_combat_action). Also, might be
        # other useful metadata to carry through the pipeline
        feed.emit_swing(context, result, hp_after, max_hp, killed, backfire=True)

        attacker.at_damage(
            hurt,
            attacker=attacker,
            source=context.weapon,
            damage_type=result.damage_type,
        )

        return killed

    def _target_unusable(self, target) -> bool:
        """Whether `target` can no longer be acted on, for any reason.

        Four separate checks used to be written out along resolve's length --
        `target is None`, no `is_alive` attribute, `is_alive()` returning
        False, and `target.pk is None` after an NPC deleted itself inside
        at_damage -- with two of them repeated at different points. They are
        one question with one answer, and the state machine has one event for
        it.
        """
        if target is None:
            return True

        if getattr(target, "pk", None) is None:
            return True

        if not isinstance(target, Combatant):
            return True

        alive = target.is_alive()

        return not alive

    def resolve(self, handler):
        """
        Purpose: Resolve one combat action and report what it did to the activity.

        Entry:
            handler is this action's owning BlackoutCombatHandler.

        Exit/Returns:
            Returns an ActivityEvent describing the outcome:
                TARGET_INVALID       — nothing left to combat action at, before or
                                       after the combat action landed
                ACTOR_INCAPACITATED  — the attacker killed itself on a
                                       backfire
                ACTION_RESOLVED      — the combat action completed and the fight goes on

        Module Globals:
            None

        Methodology:
            Returns an EVENT rather than a should-end boolean, and calls no
            teardown itself. Deciding what an outcome means for the activity
            is the transition table's job; this routine's job is to say what
            happened. That is what removed the four end_combat() calls that
            used to be scattered through here.

        Notes/References:
            Self-damage lands AFTER the target's, so a combat action that both kills
            and backfires still reads in cause-then-consequence order.

        Author: Nick Hobar
        Creation date: 07/26/2026
        """
        attacker = handler.obj
        target = self._get_target()

        unusable = self._target_unusable(target)

        if unusable:
            self._announce_lost_target(attacker, target)
            return ActivityEvent.TARGET_INVALID

        context = self._build_context(handler, attacker, target)
        result = resolve_action(context)

        if result.hit and result.damage > 0:
            killed = self._land_hit(context, result)

            if killed:
                return ActivityEvent.TARGET_INVALID
        elif result.damage <= 0 and not result.self_damage:
            self._announce_miss(attacker, target, context)

        if result.self_damage > 0:
            self_killed = self._land_backfire(context, result)

            if self_killed:
                return ActivityEvent.ACTOR_INCAPACITATED

        # at_damage may have deleted the target out from under us.
        gone = self._target_unusable(target)

        if gone:
            return ActivityEvent.TARGET_INVALID

        return ActivityEvent.ACTION_RESOLVED

    def _announce_lost_target(self, attacker, target) -> None:
        """Tell the attacker why the combat action did not happen."""
        if target is None:
            attacker.msg("Your target is gone.")
            return

        name = getattr(target, "key", "something")
        attacker.msg(f"|x{name} is already dead.|n")

    def _announce_miss(self, attacker, target, context) -> None:
        """Broadcast a combat action that connected with nothing."""
        attacker.msg(
            (combat_msg.format_outgoing_miss(attacker, target), {"type": "testing"})
        )
        target.msg(
            (combat_msg.format_incoming_miss(attacker, target), {"type": "testing"})
        )
        feed.emit_miss(context)


class ActionHold(_Action):
    """Do nothing (player waiting for a better moment)."""

    def __init__(self) -> None:
        super().__init__("hold")

    def resolve(self, _handler):
        """Holding is a completed action -- it just does nothing."""
        return ActivityEvent.ACTION_RESOLVED


class ActionFlee(_Action):
    """Player attempts to leave combat — always succeeds in batch 2."""

    def __init__(self) -> None:
        super().__init__("flee")

    def resolve(self, handler):
        obj = handler.obj
        obj.msg("|xYou scramble back and flee.|n")
        room = getattr(obj, "location", None)

        if room is not None:
            room.msg_contents(f"|x{obj.key} flees!|n", exclude=obj)

        # No teardown here: the event says the actor chose to stop, and the
        # transition table turns that into ENDING, which tick() acts on. This
        # used to call end_combat() itself and return True purely so the loop
        # would stop touching a deleted row.
        return ActivityEvent.ACTIVITY_ABANDONED


class ActionWield(_Action):
    """Weapon change queued between combat actions. Resolves once, then hands the
    combatant back to whatever they were attacking."""

    def __init__(self, weapon_id: int) -> None:
        super().__init__("wield")
        self.weapon_id = weapon_id

    def _get_weapon(self):
        weapon = _object_by_id(self.weapon_id)
        return weapon

    def resolve(self, handler):
        weapon = self._get_weapon()
        if weapon is None:
            handler.obj.msg("|rYour weapon is gone.|n")
            return ActivityEvent.ACTION_RESOLVED

        equipment = getattr(handler.obj, "equipment", None)
        if equipment is None:
            handler.obj.msg("|rYou can't wield anything.|n")
            return ActivityEvent.ACTION_RESOLVED

        # Call the handler directly rather than execute_cmd("equip ..."):
        # CmdEquipment is a menu opener that ignores its arguments, so the
        # command route popped an EvMenu mid-fight and never swapped weapons.
        # It also swallowed every EquipmentError, since the cmdhandler traps
        # command exceptions itself before they could reach us.
        try:
            equipment.equip(weapon)
        except EquipmentError as exc:
            handler.obj.msg(f"|r{exc}|n")
            return ActivityEvent.ACTION_RESOLVED

        handler._refresh_weapon()
        handler.obj.msg(f"|gYou ready your |w{weapon.key}|g.|n")

        return ActivityEvent.ACTION_RESOLVED

    def next_action(self, handler):
        """Resume attacking the current target, if there still is one.

        Without this the wield stayed queued and re-resolved every 0.6s
        forever, and the attack the player had running was silently dropped.
        """
        target_id = handler.ndb.target_id

        if target_id is None:
            return None
        
        return ActionAttack(target_id)


# ─── Combat handler ──────────────────────────────────────────────────────

@register_tickable
class BlackoutCombatHandler(TickableHandler):
    """Per-combatant twitch-combat ticker. Attached to a CombatEntity during combat.

    Each combatant runs ONE BlackoutCombatHandler at TICK_SECONDS
    interval. Every tick it decrements the combatant's personal weapon
    cooldown counter and, once that counter reaches zero, fires the
    pending action: an attack combat action resolves against the active target,
    or a hold/flee/wield overrides the current intention.

    Disconnect (at_post_unpuppet) triggers at_disconnect_combat_cleanup,
    which in turn calls drop_combatant on this handler so no "combat‑log"
    exploit is possible.
    """

    HANDLER_KEY = COMBAT_HANDLER_KEY
    ACCESSOR_NAME = "combat"
    HANDLER_DESC = "Per‑combatant combat state"

    # at_script_creation, mark_running and the ensure/get machinery all live on
    # TickableHandler now -- they were written twice, once here and once on the
    # aura handler, and had already drifted over when the accessor cache gets
    # cleared.

    def on_ensured(self) -> None:
        """Seed active_weapon_data from the combatant's current equipment.

        Runs on reuse as well as creation, so a weapon swapped between fights
        is picked up. Without this the very first combat action of a fight used the
        unarmed baseline rather than the combatant's real weapon or an NPC's
        spawner-stamped combat_stats.
        """
        try:
            self._refresh_weapon()
        except Exception as exc:
            logger.log_err(f"ensure_combat_handler _refresh_weapon failed: {exc!r}")

    # ── per-tick runtime state ───────────────────────────────────────────
    # All four fields below live on ndb, NOT db. They are rebuilt from scratch
    # every time combat starts and are meaningless afterwards, so persisting
    # them bought nothing and cost an Attribute-table read AND write every
    # 0.6s per combatant. `pending_action` was the worse half: storing it on
    # db pickled a live _Action instance into the database, so renaming any
    # action class would have left unloadable rows behind.

    def init_runtime_state(self) -> None:
        """(Re)initialise the ndb fields tick() depends on.

        ndb does not survive a reload, and a non-persistent script can still
        be reached once before the engine sweeps it, so every entry point
        that reads this state calls this first rather than trusting
        at_script_creation to have run in this process.
        """
        if self.ndb.cooldown_ticks is None:
            self.ndb.cooldown_ticks = 0  # ticks until the next combat action fires

        if self.ndb.active_weapon_data is None:
            self.ndb.active_weapon_data = _unarmed_weapon_data()

        # target_id (dbref int) and pending_action (an _Action subclass
        # instance) are legitimately None when idle, so they need no seeding.

    # ── weapon refresh ───────────────────────────────────────────────────

    def _refresh_weapon(self) -> None:
        """Rebuild this combatant's active_weapon_data from its current source.

        Delegates the source selection (NPC stat block vs wielded weapon vs
        unarmed) to combat_profile, which the defender-side
        get_defense_bonuses also uses -- so attacker and defender can no
        longer disagree about where stats come from.

        Also drops the cached rules contributors. Equipment is the only thing
        that decides them, and this method already runs on every path that can
        change equipment, so invalidating here rather than adding a second
        refresh hook keeps the two caches impossible to desynchronise.
        """
        self.ndb.active_weapon_data = combat_profile(self.obj)
        self.ndb.active_rules = None

    def active_rules(self) -> tuple:
        """Return this combatant's rules contributors, collecting on first use.

        Cached on ndb because collecting is an Attribute read per equipped
        item and this is consulted every 0.6s tick per combatant. Invalidated
        by _refresh_weapon, which runs on wield and on entering combat --
        equipment cannot change mid-fight by any other path.
        """
        cached = self.ndb.active_rules

        if cached is not None:
            return cached

        collected = collect_contributors(self.obj)
        self.ndb.active_rules = collected

        return collected

    # ── combat lifecycle ─────────────────────────────────────────────

    def start_combat_state(self, target=None) -> None:
        """Move this combatant, and its target, into the fight.

        Used to write `db.in_combat = True` on both sides. That Attribute is
        gone: CombatEntity.in_combat now derives from whether a live handler
        exists, so ensuring the target HAS one is what puts it in combat --
        which the attack command already does before calling this.

        The defender is deliberately not given ACTION_QUEUED. It has not
        queued anything; it is in combat because it is being attacked, and
        its handler sitting in IDLE says exactly that.
        """
        self.dispatch(ActivityEvent.ACTION_QUEUED)

        if target is None:
            return

        try:
            ensure_combat_handler(target)
        except Exception as exc:
            logger.log_err(
                f"CombatHandler.start_combat_state (target) failed: {exc!r}"
            )

    def get_sides(self):
        """Return (allies, enemies) of this handler's combatant.

        Modelled on the twitch-tutorial's get_sides (combat_twitch.py:86), but
        scoped to the actual combat *relationship* rather than "everyone in the
        room who happens to hold a handler". Treating every handler-bearing
        entity as an enemy made two players attacking the same NPC enemies of
        each other, and made check_stop_combat announce "You won!" merely
        because no other handler was present.

        An entity is an enemy of ours if we are targeting it, or if it is
        targeting us.
        """
        obj = self.obj
        location = getattr(obj, "location", None)

        if location is None:
            return [obj], []

        from systems.tick.engine import get_tick_engine

        engine = get_tick_engine()
        my_target_id = self.ndb.target_id
        enemies = []

        for comb in location.contents:
            if comb is obj:
                continue

            # A dict lookup against the tick rotation, NOT obj.scripts.all().
            # This runs for every occupant, of every combatant, on every tick;
            # as a query it was O(N*M) round trips per 0.6s and the only
            # symptom would have been tick drift.
            their_handler = engine.handler_for(comb.id, COMBAT_HANDLER_KEY)

            if their_handler is None:
                continue

            if comb.id == my_target_id or their_handler.ndb.target_id == obj.id:
                enemies.append(comb)

        return [obj], enemies

    def check_stop_combat(self) -> bool:
        """Per-tick keep-alive guard. Mirrors tutorial combat_twitch.py:221.

        Returns True if combat was ended by this call so the caller can
        short-circuit further tick work.

        A side has lost if no combatant on that side is both alive *and*
        still in the same room (the tutorial's flee-by-walking-away rule).
        """
        location = getattr(self.obj, "location", None)

        if location is None:
            self.end_combat()
            return True

        allies, enemies = self.get_sides()
        allies = [c for c in allies if c.is_alive() and c.location is location]
        enemies = [c for c in enemies if c.is_alive() and c.location is location]

        if not allies and not enemies:
            self.obj.msg("|xThe combat is over. No one stands.|n")
            self.end_combat()
            return True
        
        if not allies:
            self.obj.msg("|xThe combat is over. You lost.|n")
            self.end_combat()
            return True
        
        if not enemies:
            self.obj.msg("|xThe combat is over. You won!|n")
            self.end_combat()
            return True
        
        return False

    # ── liveness ─────────────────────────────────────────────────────────

    # ── tick loop ────────────────────────────────────────────────────────

    def tick(self) -> None:
        """Advance one TICK_SECONDS tick.

        Called by the global BlackoutTickEngine's LoopingCall, not by Evennia's
        Script timer — see systems/tick/engine.py for why.
        """
        obj = self.obj

        if obj is None:
            self.end_combat()
            return

        # ndb is wiped by a reload; reseed before any read below.
        self.init_runtime_state()

        if not isinstance(obj, Combatant) or not obj.is_alive():
            # The combatant itself can no longer act. Routed through the state
            # machine rather than torn down directly, so the handler passes
            # through TERMINATED and a reader arriving mid-teardown sees why.
            self._settle(ActivityEvent.ACTOR_INCAPACITATED)
            return

        # Per-tick keep-alive: end combat if our target fled the room or died
        # out-of-band. Mirrors tutorial check_stop_combat (combat_twitch.py:221).
        if self.check_stop_combat():
            return

        if self.ndb.cooldown_ticks > 0:
            self.ndb.cooldown_ticks -= 1
            return

        action = self.ndb.pending_action
        if action is None:
            return

        event = action.resolve(self)

        finished = self._settle(event)

        if finished:
            return

        self._charge_cooldown(action)

    def _settle(self, event) -> bool:
        """Apply an action's outcome and tear down if the activity is over.

        Returns True when the handler is finished for this tick -- either
        because combat ended or because the row is already gone.

        This is the one place teardown happens now. The actions used to call
        end_combat() from four separate points and return a boolean saying
        whether they had; the table decides instead, and a state reaching
        ENDING or TERMINATED is what dismantles the handler.
        """
        if event is None:
            return False

        self.dispatch(event)

        over = states.is_final(self.state)

        if not over:
            return False

        # A backfire death runs the attacker's at_death, which calls
        # leave_combat -> drop_combatant and deletes this row. Ending combat
        # again would log four swallowed errors on every such death.
        if self.pk is not None:
            self.end_combat()

        return True

    def _charge_cooldown(self, action) -> None:
        """Queue the action's successor and pay for it, if it costs anything.

        An action that names no successor idles the combatant rather than
        re-resolving every tick -- ActionWield used to re-fire forever because
        nothing cleared it.
        """
        follow_up = action.next_action(self)
        self.ndb.pending_action = follow_up

        if follow_up is None or not follow_up.consumes_cooldown:
            return

        # attack_speed is the number of ticks BETWEEN combat actions, so a speed-4
        # weapon performs actions on tick 0, 4, 8... The action itself consumes one
        # tick, hence the -1. Assigning the full value produced a
        # speed+1 cadence (3.0s instead of 2.4s for a speed-4 weapon).
        weapon_data = self.ndb.active_weapon_data or _unarmed_weapon_data()
        speed = weapon_data["attack_speed"]

        self.ndb.cooldown_ticks = max(0, speed - 1)

    # ── command interface ───────────────────────────────────────────────

    def queue_action(self, action_dict: dict) -> None:
        """
        Purpose: Accept an intention from a combat command, to take effect at
                 the top of the next tick.

        Entry:
            Expected keys:
                'kind'   — 'attack' | 'hold' | 'flee' | 'wield'
                'target' — (for 'attack') an Evennia Object.
                'weapon' — (for 'wield') an Evennia Object.

        Exit/Returns:
            No return value. Raises no user-facing exception; logs errors and
            messages the caller on a rejected attack.

        Module Globals:
            None

        Methodology:
            Validation happens NOW, because a player who typed `attack corpse`
            should be told immediately rather than 600ms later. The state
            change happens on the tick, because a command arrives whenever its
            packet does and mutating handler state mid-tick made "does this
            tick see it?" depend on rotation order.

            start_combat_state is also immediate: it is the acknowledgement
            that combat has begun, read by the summary panel and `examine`,
            and it takes no part in per-tick resolution ordering.

        Notes/References:
            The mutations themselves are apply_action, which only the engine's
            INPUT phase calls.

        Author: Nick Hobar
        Creation date: 07/26/2026
        """
        kind = action_dict.get("kind")

        if kind == "attack":
            accepted = self._validate_attack(action_dict)

            if not accepted:
                return

            self.start_combat_state(target=action_dict.get("target"))

        elif kind not in _QUEUEABLE_ACTION_KINDS:
            logger.log_err(f"CombatHandler.queue_action got unrecognized kind: {kind!r}")
            return

        from systems.tick.engine import get_tick_engine

        get_tick_engine().enqueue_action(self, action_dict)

    def _validate_attack(self, action_dict: dict) -> bool:
        """Check an attack intention, messaging the attacker if it is refused."""
        target = action_dict.get("target")

        if target is None:
            logger.log_err("CombatHandler.queue_action: 'attack' missing target")
            return False

        if not isinstance(target, Combatant):
            logger.log_err(
                f"CombatHandler.queue_action: target {target} does not satisfy "
                f"the Combatant protocol"
            )
            return False

        if not target.is_alive():
            self.obj.msg(f"|x{target.key} is already dead.|n")
            return False

        return True

    def apply_action(self, action_dict: dict) -> None:
        """
        Purpose: Make a queued intention this handler's pending action. Called
                 only from the tick engine's INPUT phase.

        Entry:
            action_dict has already passed queue_action's validation. The
            objects it names may have been deleted since, so ids are read
            defensively.

        Exit/Returns:
            No return value.

        Module Globals:
            None

        Methodology:
            Every write that per-tick resolution reads -- pending_action,
            target_id, cooldown_ticks -- happens here and nowhere else, so
            they all land at the same point in the tick for every combatant.

        Notes/References:
            flee and wield clear the cooldown so they take effect on the tick
            they land rather than waiting out a weapon action.

        Author: Nick Hobar
        Creation date: 08/18/2026
        """
        self.init_runtime_state()

        kind = action_dict.get("kind")

        if kind == "attack":
            target = action_dict.get("target")

            if target is None or target.pk is None:
                return

            self.ndb.pending_action = ActionAttack(target.id)
            self.ndb.target_id = target.id

        elif kind == "hold":
            self.ndb.pending_action = ActionHold()

        elif kind == "flee":
            self.ndb.pending_action = ActionFlee()
            self.ndb.cooldown_ticks = 0

        elif kind == "wield":
            weapon_obj = action_dict.get("weapon")

            if weapon_obj is not None and weapon_obj.pk is not None:
                self.ndb.pending_action = ActionWield(weapon_obj.id)
                self.ndb.cooldown_ticks = 0

    # ── cleanup ─────────────────────────────────────────────────────────

    def end_combat(self) -> None:
        """Stop combat cleanly: clear flags, drop pending action, delete script.

        Mirrors the tutorial's stop_combat (combat_twitch.py:250): clears
        ndb caches on the combatant and deletes the per-combatant handler
        script so a new combat can later start fresh without colliding on
        the canonical COMBAT_HANDLER_KEY.
        """
        obj = self.obj

        # No flag to clear: in_combat derives from this handler, which is
        # about to be deleted. Announce the teardown to the state machine so a
        # reader arriving mid-teardown sees ENDING rather than a live fight.
        self.dispatch(ActivityEvent.ACTIVITY_ABANDONED)

        # Clear the CombatEntity.combat accessor cache. `lazy_property` caches
        # in obj.__dict__ (evennia/utils/utils.py), NOT on ndb, and its
        # __delete__ raises — so the old `del obj.ndb.combat` was a silently
        # swallowed no-op and `caller.combat` kept returning this deleted
        # script for the rest of the session.
        if obj is not None:
            obj.__dict__.pop("combat", None)

        # Drop out of the global tick rotation before the script goes away.
        try:
            from systems.tick.engine import get_tick_engine

            get_tick_engine().unregister(self)
        except Exception as exc:
            logger.log_err(f"CombatHandler.end_combat failed to unregister: {exc!r}")

        # Stop the ticker first (idempotent if already stopped), then delete
        # the script object so future ensure_combat_handler starts fresh.
        try:
            self.stop()
        except Exception as exc:
            logger.log_err(f"CombatHandler.end_combat failed stop: {exc!r}")

        try:
            self.delete()
        except Exception as exc:
            logger.log_err(f"CombatHandler.end_combat failed delete: {exc!r}")

    def drop_combatant(self, entity) -> None:
        """Remove one combatant's handler — called from the disconnect clean path.

        At the disconnect path, the CombatEntity mixin calls
        self.combat.drop_combatant(self), and this method matches against
        self.obj to ensure we only stop THIS combatant's script (rather
        than another participant's script).
        """
        if entity is not self.obj:
            return

        self.end_combat()

    def is_valid(self) -> bool:
        return isinstance(self.obj, Combatant) and self.obj.is_alive()


# ─── module helpers ────────────────────────────────────────────────────────

def get_handler_for(entity) -> BlackoutCombatHandler | None:
    """Return entity's ACTIVE combat handler, or None.

    A named wrapper rather than a direct tickable.get_handler_for call because
    a dozen call sites read `get_handler_for(caller)` and should not each have
    to name the class.
    """
    handler = _get_tickable_handler_for(entity, BlackoutCombatHandler)

    return handler


def ensure_combat_handler(combatant) -> BlackoutCombatHandler:
    """Return the combatant's handler, creating and arming one if absent.

    Used by the twitch combat commands (attack/wield/etc.) so each command
    site doesn't reimplement the lazy create-or-fetch dance. The dance itself
    is tickable.ensure_handler; the weapon refresh this used to do inline is
    BlackoutCombatHandler.on_ensured.
    """
    handler = ensure_handler(combatant, BlackoutCombatHandler)

    return handler
