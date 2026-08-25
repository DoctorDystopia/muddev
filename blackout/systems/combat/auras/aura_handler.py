"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/03/2026
Description: BlackoutAuraHandler — the per-caster script that pulses a toggled
             damage aura on the global 0.6s combat tick.

Relationship to the combat handler
----------------------------------
This is a sibling of BlackoutCombatHandler, not a subclass. Both are timerless
DefaultScripts (interval = HANDLER_NO_TIMER_INTERVAL) driven by the one
BlackoutTickEngine LoopingCall, and both are non-persistent and swept at server
start. They are separate because an aura is not a combat action: it has no
target, no weapon, no cooldown on a swing, and it must keep pulsing whether or
not the caster is swinging at anything.
"""

from evennia.utils import logger

from systems.statefeed import events as feed
from systems.statefeed import serializers as feed_serializers

from .. import combat_msg
from ..protocols import Combatant
from systems.tick.tickable import TickableHandler, ensure_handler, register_tickable
from systems.tick.tickable import get_handler_for as _get_tickable_handler_for
from .registry import AURA_REGISTRY
from .targeting import hostiles_in_rooms, rooms_within_radius


# ─── module constants ──────────────────────────────────────────────────────

# Canonical key used by at_script_creation, get_aura_handler_for,
# ensure_aura_handler, and the tick engine's registry seeding — defined once.
AURA_HANDLER_KEY = "blackout_aura_handler"


# ─── the handler ───────────────────────────────────────────────────────────

@register_tickable
class BlackoutAuraHandler(TickableHandler):
    """Per-caster aura ticker. Attached to a CombatEntity while an aura is on.

    Every TICK_SECONDS the tick engine calls tick(). Most ticks only
    decrement a counter; on the aura's own cadence the handler resolves the
    radius, finds the hostiles in it, and applies one pulse to each.
    """

    HANDLER_KEY = AURA_HANDLER_KEY
    ACCESSOR_NAME = "aura"
    HANDLER_DESC = "Per-caster damage aura state"

    # at_script_creation, mark_running and the ensure/get machinery live on
    # TickableHandler; this class and BlackoutCombatHandler used to carry a
    # copy each.

    # ── per-tick runtime state ───────────────────────────────────────────
    # Everything below lives on ndb, NOT db. The cadence counter and the cached
    # radius are rebuilt from scratch whenever the aura is switched on, so
    # persisting them would buy nothing and cost an Attribute read AND write
    # every 0.6s per caster. The cached ring in particular holds live room
    # objects, which must never be pickled into the database.

    def init_runtime_state(self) -> None:
        """(Re)initialise the ndb fields tick() depends on.

        ndb does not survive a reload, and a non-persistent script can still be
        reached once before the engine sweeps it, so every entry point that
        reads this state calls this first rather than trusting
        at_script_creation to have run in this process.
        """
        if self.ndb.ticks_until_pulse is None:
            self.ndb.ticks_until_pulse = 0

        # aura_key is legitimately None until activate() runs, and the cached
        # ring is legitimately absent until the first pulse, so neither needs
        # seeding here.

    # ── aura lifecycle ───────────────────────────────────────────────────

    def activate(self, aura) -> None:
        """Switch this handler to the given aura and start its cadence."""
        self.init_runtime_state()

        self.ndb.aura_key = aura.key

        # Zero, not tick_interval: the aura pulses on the very next tick, so
        # lighting it gives immediate feedback instead of a silent first cycle.
        self.ndb.ticks_until_pulse = 0

        # Force a radius rebuild on the first pulse.
        self.ndb.ring_rooms = None
        self.ndb.ring_origin_id = None

        # The ring is persistent state between activate and deactivate, so a
        # graphical client draws it from these two events rather than from the
        # pulses -- which would leave the ring flickering on the pulse cadence.
        feed.emit_aura(self.obj, feed.AURA_EVENT_ACTIVATE, aura.key, aura.radius)

    def get_aura(self):
        """Resolve this handler's active aura, or None if it has none."""
        self.init_runtime_state()

        return AURA_REGISTRY.get(self.ndb.aura_key)

    # ── radius cache ─────────────────────────────────────────────────────

    def _current_ring(self, caster, aura) -> list:
        """Return the rooms in range, recomputing only when the caster moved.

        The radius query is one indexed database query, but the tick engine
        calls us every 0.6s and MUD movement is discrete -- a caster standing
        still would pay for an identical result forever. Comparing the room id
        we last built the ring for against the caster's current one turns that
        into one query per room change.
        """
        location = caster.location

        if location is None:
            return []

        cached_rooms = self.ndb.ring_rooms

        if cached_rooms is not None and self.ndb.ring_origin_id == location.id:
            return cached_rooms

        rooms = rooms_within_radius(location, aura.radius)

        self.ndb.ring_rooms = rooms
        self.ndb.ring_origin_id = location.id

        return rooms

    # ── the pulse ────────────────────────────────────────────────────────

    def _apply_pulse(self, caster, aura, target, damage: int) -> int:
        """Apply one pulse to one target. Returns HP actually removed.

        Message ordering here is NOT stylistic. at_damage can end in at_death,
        which for a HostileNPC calls respawn() and DELETES the row -- so every
        message that names the target must be built and sent BEFORE the damage
        lands, and the post-hit HP must be computed arithmetically rather than
        read back. This is the same trap documented on _land_hit in combat.py.
        """
        hp_before = target.hp
        dealt = min(damage, hp_before)
        hp_after = hp_before - dealt
        max_hp = getattr(target, "max_hp", 0)

        room = target.location

        # Mirrors _land_hit's attacker-side pair in combat.py: the hit line
        # plus the target's post-hit bar, computed arithmetically for the
        # same reason -- at_damage below can delete target's row before
        # anything could read target.hp back.
        caster.msg(combat_msg.format_aura_pulse(aura, target, dealt))
        caster.msg(combat_msg.format_hp_status(target.key, hp_after, max_hp))

        if room is not None:
            room.msg_contents(
                combat_msg.format_aura_incoming(aura, target, dealt),
                exclude=(caster,),
            )

        target.at_damage(
            dealt,
            attacker=caster,
            source=aura,
            damage_type=aura.damage_type,
        )

        return dealt

    def _pulse(self, caster, aura) -> None:
        """Resolve one full damage pulse across everything in radius."""
        rooms = self._current_ring(caster, aura)
        targets = hostiles_in_rooms(rooms, caster)

        if not targets:
            return

        damage = aura.damage_for(caster)
        total_dealt = 0

        # Captured before the pulse: at_damage can delete a target's row, and
        # with it the location the footprint is read from.
        tiles = self._pulse_tiles(targets)

        for target in targets:
            try:
                total_dealt += self._apply_pulse(caster, aura, target, damage)
            except Exception:
                # One bad target must not cost the caster the rest of the pulse.
                logger.log_trace()

        feed.emit_aura(
            caster,
            feed.AURA_EVENT_PULSE,
            aura.key,
            aura.radius,
            tiles=tiles,
            damage=total_dealt,
        )

        self._award_xp(caster, aura, total_dealt)

    def _pulse_tiles(self, targets) -> list:
        """Return the distinct world (x, y) tiles this pulse will land on.

        Only tiles that actually contain a target, not the whole radius. The
        ring itself is already known to the client from the activate event, so
        repeating it every pulse would be pure noise; what a renderer wants per
        pulse is where to put the burn effect.
        """
        tiles = []

        for target in targets:
            coords = feed_serializers.room_coords(target.location)

            if not coords:
                continue

            tile = (coords[0], coords[1])

            if tile not in tiles:
                tiles.append(tile)

        return tiles

    def _award_xp(self, caster, aura, total_dealt: int) -> None:
        """Grant the pulse's experience to the aura's XP skill.

        Awarded once on the pulse TOTAL rather than per target: the rate is
        fractional (Fortitude earns 1.33/damage), so rounding per target would
        pay a different amount for the same damage depending on how it happened
        to be spread across enemies.
        """
        if total_dealt <= 0:
            return

        skills = getattr(caster, "skills", None)
        if skills is None or aura.xp_skill is None:
            return

        award = aura.xp_for(total_dealt)
        if award <= 0:
            return

        try:
            skills.add_xp(aura.xp_skill, award)
        except Exception:
            logger.log_trace()
            return

        caster.msg(combat_msg.format_aura_xp(aura, award))

    # ── tick loop ────────────────────────────────────────────────────────

    def tick(self) -> None:
        """Advance one TICK_SECONDS tick.

        Called by the global BlackoutTickEngine's LoopingCall, not by Evennia's
        Script timer — see systems/tick/engine.py for why.

        Every failure path here ends the aura rather than raising, because the
        engine drops a handler from its rotation on ANY exception: an error that
        escaped would switch the aura off with nothing shown to the player.
        """
        caster = self.obj

        if caster is None:
            self.stop_aura()
            return

        # ndb is wiped by a reload; reseed before any read below.
        self.init_runtime_state()

        aura = self.get_aura()
        if aura is None:
            self.stop_aura()
            return

        if not isinstance(caster, Combatant) or not caster.is_alive():
            self.stop_aura()
            return

        if self.ndb.ticks_until_pulse > 0:
            self.ndb.ticks_until_pulse -= 1
            return

        # tick_interval is the number of ticks BETWEEN pulses, so an interval-4
        # aura pulses on tick 0, 4, 8... The pulse itself consumes one tick,
        # hence the -1; assigning the full value produces an interval+1 cadence
        # (3.0s instead of 2.4s), the same off-by-one the weapon-speed counter
        # in BlackoutCombatHandler.tick had to correct.
        self.ndb.ticks_until_pulse = max(0, aura.tick_interval - 1)

        try:
            self._pulse(caster, aura)
        except Exception:
            logger.log_trace()

    # ── cleanup ─────────────────────────────────────────────────────────

    def stop_aura(self) -> None:
        """Switch the aura off cleanly: drop out of the tick rotation, delete.

        Mirrors BlackoutCombatHandler.end_combat, including the accessor-cache
        pop: lazy_property caches into obj.__dict__ and its deleter raises, so
        a stale entry would keep handing out this deleted script.
        """
        caster = self.obj

        if caster is not None:
            # Announced before the accessor cache is popped and the script is
            # deleted, while get_aura() can still name what is being switched
            # off. Afterwards there is nothing left to report.
            self._announce_deactivate(caster)
            caster.__dict__.pop("aura", None)

        try:
            from systems.tick.engine import get_tick_engine

            get_tick_engine().unregister(self)
        except Exception as exc:
            logger.log_err(f"AuraHandler.stop_aura failed to unregister: {exc!r}")

        try:
            self.stop()
        except Exception as exc:
            logger.log_err(f"AuraHandler.stop_aura failed stop: {exc!r}")

        try:
            self.delete()
        except Exception as exc:
            logger.log_err(f"AuraHandler.stop_aura failed delete: {exc!r}")

    def _announce_deactivate(self, caster) -> None:
        """Tell graphical clients the ring is gone.

        Guarded on its own rather than folded into stop_aura's existing try
        blocks: those each log a specific failure, and a cosmetic feed has no
        business producing an "aura failed to stop" line.
        """
        try:
            aura = self.get_aura()

            if aura is None:
                return

            feed.emit_aura(
                caster, feed.AURA_EVENT_DEACTIVATE, aura.key, aura.radius
            )
        except Exception:
            logger.log_trace()


# ─── module helpers ────────────────────────────────────────────────────────

def get_aura_handler_for(entity):
    """Return the entity's ACTIVE aura handler, or None.

    Named wrapper over tickable.get_handler_for so call sites need not name
    the class; the is_active gate and its rationale live there.
    """
    handler = _get_tickable_handler_for(entity, BlackoutAuraHandler)

    return handler


def ensure_aura_handler(caster) -> BlackoutAuraHandler:
    """Return the caster's aura handler, creating and arming one if absent.

    The find-or-create dance, the stale-interval discard and the accessor-cache
    clear are all tickable.ensure_handler now -- this module and combat.py used
    to carry ~50 near-identical lines each.
    """
    handler = ensure_handler(caster, BlackoutAuraHandler)

    return handler
