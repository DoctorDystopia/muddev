"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/08/2026
Description: BlackoutRegenManager — the single server-wide sweep that heals
             every wounded CombatEntity 1 HP per minute, in or out of combat.

Why a Script and not the twitch tick engine
--------------------------------------------
This is NOT part of the 0.6s tick rhythm in systems/tick/engine.py -- regen is a
per-minute mechanic (Player_Overview.md: "Players regenerate 1 Hitpoint per
minute"), and HP_REGEN_INTERVAL_SECONDS is a whole number, so it can ride
Evennia's own Script.interval (a Django IntegerField) directly instead of
needing a twisted LoopingCall.

Runs unconditionally, not gated on db.in_combat. Regen is always live,
mid-fight included; the sweep does not care whether the entity is currently
mid combat action (e.g., melee swing) at something.

Registry shape
--------------
``db.registry`` is a plain list of live Objects (mirrors
``systems/spawning/respawn.py``'s ``db.respawn_queue``) rather than an ndb
set: an ndb registry is wiped by every reload with no cheap way to reseed it
(unlike the tick engine's combat handlers, which are themselves queryable
Scripts), so a wounded player sitting across a reload would otherwise stop
regenerating until they took damage again. Persisting the registry means it
survives untouched.

Membership is by object identity (Django model ``__eq__`` compares by pk),
so ``entity in registry`` is a safe, idempotent check.

Entities register themselves the moment their HP drops below max_hp --
CombatEntity.hp's setter (typeclasses/mixins.py) is the single choke point
every HP change passes through, so that is where register_for_regen is
called from, rather than from any one damage source. ``sweep`` self-cleans:
any entity at or above max_hp is dropped, so nothing needs to explicitly
unregister on healing.
"""

from evennia.scripts.scripts import DefaultScript
from evennia.utils import logger

from . import constants as const
from .protocols import Combatant
from systems.managers import get_singleton_script, register_manager

# ─── module constants ──────────────────────────────────────────────────────

REGEN_MANAGER_KEY = "blackout_regen_manager"

# Evennia interval meaning "this Script owns no timer". The regen sweep runs on
# the tick engine's scheduler; the Script survives only to hold the persistent
# registry.
NO_EVENNIA_TIMER: int = -1


# ─── the manager ────────────────────────────────────────────────────────────

class BlackoutRegenManager(DefaultScript):
    """Global Script owning the passive-HP-regen registry.

    One sweep every HP_REGEN_INTERVAL_SECONDS heals every registered entity
    that is alive and short of max_hp -- in combat or not -- isolating
    failures so one broken entity cannot stall regen world-wide.
    """

    def at_script_creation(self) -> None:
        self.key = REGEN_MANAGER_KEY
        self.desc = "Global hitpoint regeneration registry"

        # No Evennia timer. The sweep is scheduled on the tick engine, so this
        # Script exists only to own db.registry -- see the module header.
        self.interval = NO_EVENNIA_TIMER
        self.persistent = True
        self.db.registry = []

    # ── scheduling ───────────────────────────────────────────────────────

    def arm(self) -> None:
        """Schedule the next sweep on the tick engine.

        Idempotent by handle: an existing pending sweep is cancelled first, so
        calling this from bootstrap and from register cannot stack two.
        """
        from systems.tick.engine import get_tick_engine

        engine = get_tick_engine()
        pending = self.ndb._sweep_handle

        if pending is not None:
            engine.cancel_scheduled(pending)

        self.ndb._sweep_handle = engine.schedule_in(
            const.HP_REGEN_INTERVAL_TICKS, self._on_due
        )

    def _on_due(self) -> None:
        """Re-arm, then sweep.

        The order matters and is the whole reason this is not one line. The
        scheduler contains a callback's exceptions so one bad entry cannot
        stop the tick -- which means a sweep that raised before re-arming
        would leave regen unscheduled forever, with nothing to point at. Arm
        first and the next sweep is booked no matter what this one does.
        """
        self.arm()
        self.sweep()

    # ── registry access ──────────────────────────────────────────────────

    def register(self, entity) -> bool:
        """Add `entity` to the regen registry. Returns True if it was added.

        Idempotent: calling this on an already-registered entity is a no-op
        besides re-arming the timer, which is cheap and safe to repeat.
        """
        if entity is None or getattr(entity, "pk", None) is None:
            return False

        registry = list(self.db.registry or [])

        if entity in registry:
            return False

        registry.append(entity)
        self.db.registry = registry

        return True

    # ── the sweep ────────────────────────────────────────────────────────

    def sweep(self) -> int:
        """Heal every eligible registered entity by HP_REGEN_AMOUNT.

        Runs regardless of db.in_combat -- regen is not gated on being out
        of a fight.

        Exit/Returns:
            The number of entities actually healed this sweep.
        """
        registry = list(self.db.registry or [])
        if not registry:
            return 0

        remaining = []
        healed = 0

        for entity in registry:
            try:
                if entity is None or getattr(entity, "pk", None) is None:
                    # Deleted since registration -- drop silently.
                    continue

                if not isinstance(entity, Combatant) or not entity.is_alive():
                    continue

                if entity.hp >= entity.max_hp:
                    # Healed by some other means since registering -- drop.
                    continue

                entity.hp = entity.hp + const.HP_REGEN_AMOUNT
                healed += 1

                if entity.hp < entity.max_hp:
                    remaining.append(entity)
            except Exception:
                # One bad entity must never stall regen world-wide; mirrors
                # BlackoutRespawnManager.sweep / BlackoutTickEngine._tick.
                logger.log_trace()

        self.db.registry = remaining
        return healed


# ─── module helpers ────────────────────────────────────────────────────────

def get_regen_manager() -> BlackoutRegenManager:
    """Return the global regen manager, creating and arming it if absent.

    Mirrors get_respawn_manager / get_tick_engine.
    """
    manager = get_singleton_script(REGEN_MANAGER_KEY, BlackoutRegenManager)

    return manager


def register_for_regen(entity) -> bool:
    """Convenience wrapper -- the entry point CombatEntity.hp's setter calls.

    Silently declines entities that are already at full HP (or otherwise
    lack hp/max_hp), so callers can invoke this unconditionally on every HP
    change without checking HP themselves first.
    """
    if entity is None:
        return False

    max_hp = getattr(entity, "max_hp", None)
    hp = getattr(entity, "hp", None)

    if max_hp is None or hp is None or hp >= max_hp:
        return False

    return get_regen_manager().register(entity)


@register_manager
def bootstrap_regen() -> BlackoutRegenManager:
    """Bring passive regen up at server start. Called from at_server_startstop.

    Arming here is load-bearing: the tick scheduler lives on ndb and is empty
    after a reload, so a sweep booked before the restart is gone. Every user of
    the scheduler is responsible for re-arming itself at boot, and this is
    regen's.
    """
    manager = get_regen_manager()
    manager.arm()

    return manager
