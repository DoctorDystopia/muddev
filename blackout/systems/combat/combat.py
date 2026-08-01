"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/26/2026
Description: Per-combatant BlackoutCombatHandler (DefaultScript) and action
             classes for twitch-style melee combat — attack, hold, flee, wield.
"""

from evennia.scripts.scripts import DefaultScript
from evennia.utils import logger

from items.equipment.constants import WieldLocation
from items.equipment.handler import EquipmentError

from . import combat_calc, combat_msg
from . import constants as const

# ─── Weapon-style => XP award table ───────────────────────────────────────

_WEAPON_STYLE_XP_MAP: dict[str, float] = {
    "accurate": const.XP_PER_DAMAGE_ACCURATE,
    "aggressive": const.XP_PER_DAMAGE_AGGRESSIVE,
    "controlled": const.XP_PER_DAMAGE_CONTROLLED_EACH,
    "defensive": const.XP_PER_DAMAGE_DEFENSIVE,
}

def _normalize_xp_skills(xp_skill) -> tuple:
    """Resolve a style's `xp_skill` entry to a tuple of skill keys.

    Accepts a single key ("strike"), any iterable of keys, or the legacy
    "controlled" sentinel still stored on weapons spawned before multi-skill
    styles existed. Returns an empty tuple when the style awards nothing.
    """
    if xp_skill is None:
        return ()

    if isinstance(xp_skill, str):
        if xp_skill == const.LEGACY_CONTROLLED_XP_SENTINEL:
            return const.CONTROLLED_XP_SKILLS
        return (xp_skill,)

    return tuple(xp_skill)


def _award_style_xp(attacker, style: dict, damage: int) -> None:
    """Post-swing XP award driven by the active attack style entry.

    attacker — a CombatEntity that exposes .skills (Character / HostileNPC).
    style    — one entry from the entity's combat_styles table.
    damage   — the integer damage returned by combat_calc.resolve_melee_swing.

    Every skill the style names receives the style's full per-skill rate. The
    rates in constants.py are already per-skill shares, so this must NOT
    divide again.
    """
    style_name = style.get("weapon_style")
    xp_per_damage = _WEAPON_STYLE_XP_MAP.get(style_name)
    if xp_per_damage is None:
        logger.log_err(
            f"_award_style_xp: unknown weapon_style {style_name!r} on {attacker}; no XP awarded."
        )
        return

    skills = getattr(attacker, "skills", None)
    if skills is None:
        return

    # "weapon_style_xp_skill" is the current key. Weapons spawned before that
    # rename still carry "xp_skill" in their stored style dicts, so fall back
    # to it rather than silently awarding those swings nothing.
    raw_targets = style.get("weapon_style_xp_skill", style.get("xp_skill"))
    skill_targets = _normalize_xp_skills(raw_targets)
    if not skill_targets:
        return

    award = int(round(xp_per_damage * damage))
    if award <= 0:
        return

    for skill_key in skill_targets:
        skills.add_xp(skill_key, award)


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

    `combat_styles` is the current attribute. Objects spawned before the
    rename still carry the table under `attack_type`, which collided
    confusingly with the per-style `attack_type` key naming the damage type
    (stab/slash/crush). Both are read here so live DB rows keep resolving
    their styles instead of silently degrading to unarmed.
    """
    styles = getattr(entity.db, "combat_styles", None)
    if styles:
        return styles

    legacy_styles = getattr(entity.db, "attack_type", None)
    if legacy_styles:
        return legacy_styles

    return {}


def _stance_bonus(boost_profile: dict, skill_key: str) -> int:
    """Pull the integer stance boost for one combat axis (strike|brawn|defense)."""
    return boost_profile.get(skill_key, 0)


def _attack_equip(combat_stats: dict, damage_type: str) -> int:
    """Grab the equip attack bonus for the given type (stab/slash/crush)."""
    return combat_stats.get(f"{damage_type}_attack_bonus", 0)


def _defense_equip(combat_stats: dict, damage_type: str) -> int:
    """Grab the equip defense bonus for the given type."""
    return combat_stats.get(f"{damage_type}_defense_bonus", 0)


def _strength_equip(combat_stats: dict) -> int:
    """Grab the melee strength bonus."""
    return combat_stats.get("melee_strength_bonus", 0)


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


def _held_weapon(entity):
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


def get_defense_bonuses(entity) -> dict:
    """Return the combat_stat_bonuses dict to use for `entity`'s DEFENSE.

    Mirrors _refresh_weapon's source selection:
        HostileNPC (no equipment handler) -> db.combat_stat_bonuses
        Character                          -> wielded weapon's bonuses
        neither available                  -> UNARMED defaults

    This exists because the defender's armour must never be read out of the
    *attacker's* stat block. It is also the single seam that full multi-slot
    armour aggregation will extend — today only the wielded item contributes.
    """
    if entity is None:
        return const.UNARMED_DEFAULT_COMBAT_STATS.copy()

    if not hasattr(entity, "equipment"):
        stats = getattr(entity.db, "combat_stat_bonuses", None)
        if stats:
            return dict(stats)
        return const.UNARMED_DEFAULT_COMBAT_STATS.copy()

    weapon = _held_weapon(entity)
    if weapon is None:
        return const.UNARMED_DEFAULT_COMBAT_STATS.copy()

    stats = getattr(weapon.db, "combat_stat_bonuses", None)
    if stats:
        return dict(stats)
    return const.UNARMED_DEFAULT_COMBAT_STATS.copy()


# ─── Action classes ──────────────────────────────────────────────────────


class _Action:
    """Abstract twitch-combat action — one swing, hold, flee, or wield.

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

    def resolve(self, handler) -> bool:
        """Execute the action. Return True if combat ends after this action."""
        raise NotImplementedError

    def next_action(self, handler):
        """Return the action to queue after this one resolves (None = idle)."""
        return None


class ActionAttack(_Action):
    """An on-pace melee swing resolved against the combatant's current target."""

    consumes_cooldown = True

    def __init__(self, target_id: int) -> None:
        super().__init__("attack")
        self.target_id = target_id


    def next_action(self, handler):
        """Keep swinging at the same target until told otherwise."""
        return self


    def _get_target(self):
        target = _object_by_id(self.target_id)
        return target


    def resolve(self, handler) -> bool:
        attacker = handler.obj
        target = self._get_target()

        if target is None:
            attacker.msg("Your target is gone.")
            handler.end_combat()
            return True

        if not hasattr(target, "is_alive") or not target.is_alive():
            attacker.msg(f"|x{getattr(target, 'key', 'something')} is already dead.|n")
            handler.end_combat()
            return True

        # ── gather weapon data ───────────────────────────────────────────
        weapon = handler.db.active_weapon_data or _unarmed_weapon_data()
        style = weapon.get("active_combat_style")
        if not style:
            # A malformed/missing style dict would otherwise KeyError below and
            # kill the swing.
            logger.log_err(
                f"ActionAttack: {attacker} has no usable attack style; falling back to unarmed."
            )
            style = const.UNARMED_COMBAT_STYLES[const.UNARMED_DEFAULT_COMBAT_STYLE]

        combat_stats = weapon.get("combat_stat_bonuses") or const.UNARMED_DEFAULT_COMBAT_STATS
        damage_type = style["attack_type"]
        boost = style.get("weapon_style_level_boost") or {}

        equip_atk = _attack_equip(combat_stats, damage_type)
        equip_str = _strength_equip(combat_stats)

        a_strike_eff = _stance_bonus(boost, "strike")
        a_brawn_eff = _stance_bonus(boost, "brawn")

        # ── effective levels ─────────────────────────────────────────────
        a_strike_lvl = handler.obj.skills.get_level("strike")
        a_brawn_lvl = handler.obj.skills.get_level("brawn")
        d_defense_lvl = target.skills.get_level("defense") if hasattr(target, "skills") else 1

        a_eff_atk = combat_calc.effective_level(
            a_strike_lvl,
            stance_bonus=a_strike_eff,
        )
        a_eff_str = combat_calc.effective_level(
            a_brawn_lvl,
            stance_bonus=a_brawn_eff,
        )
        d_eff_def = combat_calc.effective_level(d_defense_lvl)

        # The defender's armour must come from the DEFENDER's stat block.
        defend_equip = _defense_equip(get_defense_bonuses(target), damage_type)

        # ── swing resolution ─────────────────────────────────────────────
        result = combat_calc.resolve_melee_swing(
            attacker_eff_atk=a_eff_atk,
            attacker_equip_atk=equip_atk,
            attacker_eff_str=a_eff_str,
            attacker_equip_str=equip_str,
            defender_eff_def=d_eff_def,
            defender_equip_def=defend_equip,
        )
        dmg = result["damage"]
        hit = result["hit"]

        # ── broadcast & damage application ───────────────────────────────
        if hit and dmg > 0:
            # Build every message and capture the room BEFORE applying damage.
            # at_damage can kill the target, and a killed NPC deletes itself,
            # after which .location reads None and the room broadcast for the
            # killing blow was silently skipped -- the one hit that most
            # needs announcing.
            room = getattr(target, "location", None)
            outgoing = combat_msg.format_outgoing_hit(attacker, target, dmg)
            incoming = combat_msg.format_incoming_hit(attacker, target, dmg)
            third_party = combat_msg.format_third_party_hit(attacker, target, dmg)

            # Decide lethality from the pre-damage HP rather than polling
            # is_alive() afterwards. A player's at_death runs respawn(),
            # which restores full HP synchronously, so the post-hoc poll
            # always reported the victim alive and the fight never ended.
            hp_before = getattr(target, "hp", 0)
            killed = (dmg >= hp_before)

            target.at_damage(dmg, attacker=attacker)

            attacker.msg(outgoing)
            target.msg(incoming)
            if room is not None:
                room.msg_contents(third_party, exclude=(attacker, target))

            _award_style_xp(attacker, style, dmg)

            if killed:
                handler.end_combat()
                return True
        else:
            attacker.msg(combat_msg.format_outgoing_miss(attacker, target))
            target.msg(combat_msg.format_incoming_miss(attacker, target))

        # A slain NPC deletes itself inside at_damage, so confirm the row
        # still exists before touching db-backed state on it.
        if target.pk is None:
            handler.end_combat()
            return True

        if hasattr(target, "is_alive") and not target.is_alive():
            handler.end_combat()
            return True

        return False


class ActionHold(_Action):
    """Do nothing (player waiting for a better moment)."""

    def __init__(self) -> None:
        super().__init__("hold")

    def resolve(self, _handler) -> bool:
        return False


class ActionFlee(_Action):
    """Player attempts to leave combat — always succeeds in batch 2."""

    def __init__(self) -> None:
        super().__init__("flee")

    def resolve(self, handler) -> bool:
        obj = handler.obj
        obj.msg("|xYou scramble back and flee.|n")
        room = getattr(obj, "location", None)

        if room is not None:
            room.msg_contents(f"|x{obj.key} flees!|n", exclude=obj)

        handler.end_combat()

        # MUST be True, end_combat deletes this script, so the tick loop has to
        # stop touching self.db immediately.
        return True


class ActionWield(_Action):
    """Weapon change queued between swings. Resolves once, then hands the
    combatant back to whatever they were attacking."""

    def __init__(self, weapon_id: int) -> None:
        super().__init__("wield")
        self.weapon_id = weapon_id

    def _get_weapon(self):
        weapon = _object_by_id(self.weapon_id)
        return weapon

    def resolve(self, handler) -> bool:
        weapon = self._get_weapon()
        if weapon is None:
            handler.obj.msg("|rYour weapon is gone.|n")
            return False

        equipment = getattr(handler.obj, "equipment", None)
        if equipment is None:
            handler.obj.msg("|rYou can't wield anything.|n")
            return False

        # Call the handler directly rather than execute_cmd("equip ..."):
        # CmdEquipment is a menu opener that ignores its arguments, so the
        # command route popped an EvMenu mid-fight and never swapped weapons.
        # It also swallowed every EquipmentError, since the cmdhandler traps
        # command exceptions itself before they could reach us.
        try:
            equipment.equip(weapon)
        except EquipmentError as exc:
            handler.obj.msg(f"|r{exc}|n")
            return False

        handler._refresh_weapon()
        handler.obj.msg(f"|gYou ready your |w{weapon.key}|g.|n")

        return False

    def next_action(self, handler):
        """Resume attacking the current target, if there still is one.

        Without this the wield stayed queued and re-resolved every 0.6s
        forever, and the attack the player had running was silently dropped.
        """
        target_id = handler.db.target_id

        if target_id is None:
            return None
        
        return ActionAttack(target_id)


# ─── Combat handler ──────────────────────────────────────────────────────

class BlackoutCombatHandler(DefaultScript):
    """Per-combatant twitch-combat ticker. Attached to a CombatEntity during combat.

    Each combatant runs ONE BlackoutCombatHandler at COMBAT_TICK_SECONDS
    interval. Every tick it decrements the combatant's personal weapon
    cooldown counter and, once that counter reaches zero, fires the
    pending action: an attack swing resolves against the active target,
    or a hold/flee/wield overrides the current intention.

    Cleanup detail — per the research doc and the CombatEntity plan,
    disconnect (at_post_unpuppet) triggers at_disconnect_combat_cleanup,
    which in turn calls drop_combatant on this handler so no "combat‑log"
    exploit is possible.
    """

    def at_script_creation(self) -> None:
        """Set up the persistent attributes the handler reads every tick."""
        self.key = COMBAT_HANDLER_KEY
        self.desc = "Per‑combatant combat state"

        # No Evennia timer of our own: ScriptDB.db_interval is an IntegerField
        # and cannot express the 0.6s OSRS tick. The global BlackoutTickEngine
        # owns the LoopingCall and calls our tick() instead.
        self.interval = HANDLER_NO_TIMER_INTERVAL

        # Twitch combat does not survive a restart; the engine sweeps leftovers
        # at server start, and a fresh handler is created on the next attack.
        self.persistent = False

        self.db.target_id = None  # dbref (int) of the current target
        self.db.pending_action = None  # instance of _Action subclass, or None
        self.db.cooldown_ticks = 0  # ticks until the next swing fires
        self.db.active_weapon_data = _unarmed_weapon_data()

    # ── weapon refresh ───────────────────────────────────────────────────

    def _refresh_weapon(self) -> None:
        """Rebuild the combat stat dict from the combatant's current mainhand weapon.

        Falls back to UNARMED defaults when no weapon is equipped or the
        combatant has no `equipment` handler (e.g. HostileNPC, which carries
        its combat stats in `db.combat_stats` rather than a wielded slot).
        For NPCs, we additionally prefer their spawner-stamped `combat_stats`
        over the unarmed baseline so their OSRS swing math uses intended values.
        """
        obj = self.obj

        # NPCs (HostileNPC) have no EquipmentHandler; they carry their
        # combat stat block in db.combat_stats (set by the spawner).
        if not hasattr(obj, "equipment"):
            stats = getattr(obj.db, "combat_stat_bonuses", None) or (
                const.UNARMED_DEFAULT_COMBAT_STATS.copy()
            )

            styles = _stored_combat_styles(obj)

            default_key = getattr(obj.db, "default_combat_style", None) or next(
                iter(styles), const.UNARMED_DEFAULT_COMBAT_STYLE
            )

            active_combat_style = styles.get(default_key) or _unarmed_weapon_data()["active_combat_style"]

            speed = getattr(obj.db, "attack_speed", None) or const.UNARMED_ATTACK_SPEED_TICKS
            self.db.active_weapon_data = {
                "combat_stat_bonuses": dict(stats),
                "active_combat_style": dict(active_combat_style),
                "attack_speed": speed,
            }

            return

        # Two-handed weapons live in TWO_HANDS, never MAIN_HAND — checking only
        # the main hand reduced every two-hander to unarmed stats.
        held = _held_weapon(obj)

        if held is None:
            self.db.active_weapon_data = _unarmed_weapon_data()
            return

        speed = (
            getattr(held.db, "attack_speed", const.UNARMED_ATTACK_SPEED_TICKS)
            or const.UNARMED_ATTACK_SPEED_TICKS
        )

        stats = (
            getattr(held.db, "combat_stat_bonuses", None) or const.UNARMED_DEFAULT_COMBAT_STATS
        )

        styles = _stored_combat_styles(held)

        default_key = getattr(held.db, "default_combat_style", None) or next(
            iter(styles), const.UNARMED_DEFAULT_COMBAT_STYLE
        )

        active_combat_style = styles.get(default_key) or _unarmed_weapon_data()["active_combat_style"]

        self.db.active_weapon_data = {
            "combat_stat_bonuses": dict(stats),
            "active_combat_style": dict(active_combat_style),
            "attack_speed": speed,
        }

    # ── combat lifecycle ─────────────────────────────────────────────

    def start_combat_state(self, target=None) -> None:
        """Mark this combatant (and optional target) as in combat.

        Sets the previously-missing `db.in_combat = True` producer that
        CombatEntity, CmdFlee, examine-display, and disconnect cleanup all
        read but no code path was writing.
        """
        try:
            self.obj.db.in_combat = True
        except Exception as exc:
            logger.log_err(f"CombatHandler.start_combat_state failed: {exc!r}")

        if target is not None:
            try:
                target.db.in_combat = True
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

        my_target_id = self.db.target_id
        enemies = []

        for comb in location.contents:
            if comb is obj or not hasattr(comb, "scripts"):
                continue
            their_handler = get_handler_for(comb)
            if their_handler is None:
                continue
            if comb.id == my_target_id or their_handler.db.target_id == obj.id:
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

    def mark_running(self) -> None:
        """Flag this handler as live.

        With `interval = -1` Evennia will never set `db_is_active` for us
        (`ScriptBase._start_task` bails out when the interval is <= 0), yet
        `get_handler_for`, the `CombatEntity.combat` accessor and the tick
        engine's registry rebuild all key off that flag. Since the engine —
        not Evennia — owns our timer, we set it ourselves. `stop()` clears it
        again on the way out.
        """
        if self.is_active:
            return
        
        self.db_is_active = True
        self.save(update_fields=["db_is_active"])

    # ── tick loop ────────────────────────────────────────────────────────

    def tick(self) -> None:
        """Advance one COMBAT_TICK_SECONDS tick.

        Called by the global BlackoutTickEngine's LoopingCall, not by Evennia's
        Script timer — see tick_engine.py for why.
        """
        obj = self.obj

        if obj is None:
            self.end_combat()
            return

        if not hasattr(obj, "is_alive") or not obj.is_alive():
            self.end_combat()
            return

        # Per-tick keep-alive: end combat if our target fled the room or died
        # out-of-band. Mirrors tutorial check_stop_combat (combat_twitch.py:221).
        if self.check_stop_combat():
            return

        if self.db.cooldown_ticks > 0:
            self.db.cooldown_ticks -= 1
            return

        action = self.db.pending_action
        if action is None:
            return

        should_end = action.resolve(self)
        if should_end:
            return

        # Hand the action a chance to name its successor, then charge a
        # cooldown only if that successor costs one. An action that returns
        # None idles the combatant instead of re-resolving every tick --
        # ActionWield used to re-fire forever because nothing cleared it.
        follow_up = action.next_action(self)
        self.db.pending_action = follow_up

        if follow_up is not None and follow_up.consumes_cooldown:
            # attack_speed is the number of ticks BETWEEN swings, so a speed-4
            # weapon swings on tick 0, 4, 8... The swing itself consumes one
            # tick, hence the -1; assigning the full value produced a
            # speed+1 cadence (3.0s instead of 2.4s for a speed-4 weapon).
            speed = (self.db.active_weapon_data or _unarmed_weapon_data())["attack_speed"]
            self.db.cooldown_ticks = max(0, speed - 1)

        target = _object_by_id(self.db.target_id)

        if target is not None and hasattr(target, "is_alive") and not target.is_alive():
            self.end_combat()

    # ── command interface ───────────────────────────────────────────────

    def queue_action(self, action_dict: dict) -> None:
        """Called by combat Cmd* twitch commands. Replace the current pending action.

        Expected keys:
            'kind'   — 'attack' | 'hold' | 'flee' | 'wield'
            'target' — (for 'attack') an Evennia Object.
            'weapon' — (for 'wield') an Evennia Object.

        Raises NO user-facing exception; logs errors.
        """
        kind = action_dict.get("kind")

        if kind == "attack":
            target = action_dict.get("target")

            if target is None:
                logger.log_err("CombatHandler.queue_action: 'attack' missing target")
                return
            
            if not hasattr(target, "is_alive"):
                logger.log_err(
                    f"CombatHandler.queue_action: target {target} is not a CombatEntity "
                    f"(no is_alive method)"
                )
                return
            
            if not target.is_alive():
                self.obj.msg(f"|x{target.key} is already dead.|n")
                return
            
            # Flip the in-combat flag on both sides — the canonical state signal
            # that CombatEntity, examine, CmdFlee, and disconnect cleanup all read.
            # Previously only `False` was ever written anywhere, which is why
            # `examine me` and `examine mutant raider` both reported in_combat=False
            # even mid-swing.
            self.start_combat_state(target=target)
            self.db.pending_action = ActionAttack(target.id)
            self.db.target_id = target.id

        elif kind == "hold":
            self.db.pending_action = ActionHold()

        elif kind == "flee":
            self.db.pending_action = ActionFlee()
            self.db.cooldown_ticks = 0

        elif kind == "wield":
            weapon_obj = action_dict.get("weapon")

            if weapon_obj is not None:
                self.db.pending_action = ActionWield(weapon_obj.id)
                self.db.cooldown_ticks = 0

        else:
            logger.log_err(f"CombatHandler.queue_action got unrecognized kind: {kind!r}")

    # ── cleanup ─────────────────────────────────────────────────────────

    def end_combat(self) -> None:
        """Stop combat cleanly: clear flags, drop pending action, delete script.

        Mirrors the tutorial's stop_combat (combat_twitch.py:250): clears
        ndb caches on the combatant and deletes the per-combatant handler
        script so a new combat can later start fresh without colliding on
        the canonical COMBAT_HANDLER_KEY.
        """
        obj = self.obj

        # Clear the canonical in-combat flag the rest of the codebase reads.
        try:
            if obj is not None:
                obj.db.in_combat = False
        except Exception as exc:
            logger.log_err(f"CombatHandler.end_combat failed db cleanup: {exc!r}")

        # Clear the CombatEntity.combat accessor cache. `lazy_property` caches
        # in obj.__dict__ (evennia/utils/utils.py), NOT on ndb, and its
        # __delete__ raises — so the old `del obj.ndb.combat` was a silently
        # swallowed no-op and `caller.combat` kept returning this deleted
        # script for the rest of the session.
        if obj is not None:
            obj.__dict__.pop("combat", None)

        # Drop out of the global tick rotation before the script goes away.
        try:
            from .tick_engine import get_tick_engine

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
        return self.obj is not None and hasattr(self.obj, "is_alive") and self.obj.is_alive()


# ─── module constants ──────────────────────────────────────────────────────

# Canonical key used by at_script_creation, get_handler_for, ensure_combat_handler,
# and the CombatEntity.combat accessor — defined once (DRY).
COMBAT_HANDLER_KEY = "blackout_combat_handler"

# Sentinel interval marking a handler as having no Evennia-owned timer. The
# global BlackoutTickEngine drives tick() instead; see tick_engine.py.
HANDLER_NO_TIMER_INTERVAL = -1


# ─── module helpers ────────────────────────────────────────────────────────

def get_handler_for(entity) -> BlackoutCombatHandler | None:
    """Scan entity's scripts and return the first *active* BlackoutCombatHandler, or None.

    A scripted combatant is considered "in combat" iff its handler is running.
    Specifying is_active ensures that leftover stopped handlers (e.g. after
    end_combat stops the script, or after a server reload races state) are not
    mistaken for live combat — which previously caused the `caller.combat`
    accessor to return a parked script and the `flee`/`hold` "you aren't in
    combat" guard to behave inconsistently.
    """
    for script in entity.scripts.all():
        if getattr(script, "key", "") == COMBAT_HANDLER_KEY and script.is_active:
            return script
        
    return None


def ensure_combat_handler(combatant) -> BlackoutCombatHandler:
    """Return the combatant's existing handler, or create+start one if absent.

    Used by the twitch combat commands (attack/wield/etc.) so each command
    site doesn't reimplement the lazy create-or-fetch dance.

    Handles DefaultScript.create()'s (script, errors) return contract:
    surfaces any creation errors to the combatant and aborts on failure.

    Two cases:
        1. A well-formed handler already exists -> reuse it.
        2. Anything else (no handler, or one persisted under an older/broken
           configuration) -> delete the leftover and create a fresh one.

    Case 2's delete-and-recreate replaces the old "revive a stopped leftover"
    behaviour, which is what made the original bug permanent: handlers written
    with `db_interval = 0` were resurrected on every attack forever, and no
    amount of restarting them could ever produce a timer.
    """
    from .tick_engine import get_tick_engine

    existing = None
    for script in combatant.scripts.all():
        if getattr(script, "key", "") == COMBAT_HANDLER_KEY:
            existing = script
            break

    if existing is not None and existing.interval != HANDLER_NO_TIMER_INTERVAL:
        # Stale configuration (e.g. a pre-tick-engine handler). Don't revive it.
        logger.log_info(
            f"ensure_combat_handler: discarding stale handler on {combatant} "
            f"(interval={existing.interval})."
        )

        combatant.__dict__.pop("combat", None)

        try:
            existing.delete()
        except Exception as exc:
            logger.log_err(f"ensure_combat_handler failed to delete stale handler: {exc!r}")

        existing = None

    if existing is None:
        existing, errors = BlackoutCombatHandler.create(
            key=COMBAT_HANDLER_KEY,
            obj=combatant,
        )

        if errors:
            for err in errors:
                combatant.msg(f"|r{err}|n")
            raise RuntimeError(f"Could not create combat handler for {combatant}: {errors}")
        
        combatant.__dict__.pop("combat", None)

    # Evennia will not flag a zero-interval script active, so we own liveness.
    existing.mark_running()

    # Seed active_weapon_data from the combatant's current equipment (player)
    # or spawner-stamped combat_stats (NPC), so the very first swing uses the
    # combatant's real weapon/style rather than the unarmed baseline. Also
    # re-runs on reuse, in case they changed weapons between combats.
    try:
        existing._refresh_weapon()
    except Exception as exc:
        logger.log_err(f"ensure_combat_handler _refresh_weapon failed: {exc!r}")

    get_tick_engine().register(existing)

    return existing
