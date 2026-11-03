"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The augment handler (DESIGN-0015, Phase 2). One for each
             holder, attached while any augment burns. It holds the lit set
             and the drain counter in ndb, and it spends Grit on the tick.

             The OSRS counter: each tick adds the drain of each lit augment.
             When the counter passes the resistance, one Grit point goes.
             At 0 Grit, every augment goes out, and the handler deletes
             itself. The aura twin is auras/aura_handler.py. It differs in
             one way: the aura handler holds ONE aura, and this one holds a
             set. It stays while any augment burns, and deletes itself at
             the last put-out.

             The sustain event, the free window, the anneal, and the flick
             are on hold (Nick, 10/30/2026). The tick here is the drain
             alone. A swing reads the lit set at its own tick through
             rules.active_rules, so a flick already works as OSRS does.

             Phase 5 added the conflict group (a light puts out the other
             lit augment of the group), the roll of an augment that rolls
             (Overclock), and the ring refresh of the aura handler when the
             lit set moves (Reach).
"""

import random

from evennia.utils import logger

from systems.core.tick.tickable import TickableHandler, ensure_handler, register_tickable
from systems.core.tick.tickable import get_handler_for as _get_tickable_handler_for
from systems.gameplay.combat.protocols import Combatant
from systems.interface.statefeed import constants as feed_const

from . import constants as aug_const
from . import pool
from .registry import AUGMENT_REGISTRY, augments_in_order


# Every line this module sends a player is combat, so the routing tag is
# bound one time here.
_MSG_COMBAT = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_COMBAT}


# ─── Public constant definitions ─────────────────────────────────────────────

# The one key of the handler script. at_script_creation, the accessors, and
# the boot sweep of the tick engine read it.
AUGMENT_HANDLER_KEY: str = "blackout_augment_handler"


# ─── Public routines ─────────────────────────────────────────────────────────

def resistance_for(holder) -> int:
    """
    Purpose: The counter value at which one Grit point goes.

    Entry:
        holder is any object. It may wear nothing.

    Exit/Returns:
        Returns AUG_DRAIN_BASE plus AUG_DRAIN_PER_BONUS times the
        augmentation bonus of the gear, as an int of at least 1.

    Module Globals:
        aug_const.AUG_DRAIN_BASE, AUG_DRAIN_PER_BONUS, AUGMENTATION_BONUS_KEY read.

    Methodology:
        Read the bonus from the summed gear profile, the one that the
        defense reads. OSRS reads the prayer bonus from every worn item the
        same way. The combat module is imported inside the routine. It
        imports the rules module of this package at the action.

    Notes/References:
        No item def gives the bonus yet (Phase 6). The accessor exists so
        that the day one does, nothing here changes.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """
    from systems.gameplay.combat.combat import get_defense_bonuses

    bonuses = get_defense_bonuses(holder) or {}
    bonus = bonuses.get(aug_const.AUGMENTATION_BONUS_KEY, 0)
    resistance = aug_const.AUG_DRAIN_BASE + aug_const.AUG_DRAIN_PER_BONUS * bonus

    return max(1, int(resistance))


# ─── The handler ─────────────────────────────────────────────────────────────

@register_tickable
class BlackoutAugmentHandler(TickableHandler):
    """
    Purpose: Hold the lit augments of one holder, and drain Grit on the tick.

    Entry:
        self.obj is the holder. ensure_augment_handler makes one.

    Exit/Returns:
        Not applicable. A script.

    Module Globals:
        AUGMENT_REGISTRY read.

    Methodology:
        Every per-tick field lives on ndb, never db. A reload wipes ndb,
        and the engine sweeps every handler at boot. Thus, a reload puts
        every augment out, and init_runtime_state reseeds an empty set.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 10/30/2026
    """

    HANDLER_KEY = AUGMENT_HANDLER_KEY
    ACCESSOR_NAME = "augments"
    HANDLER_DESC = "Per-holder lit augments and the Grit drain"

    # The source of the roll of an augment that rolls. A class attribute,
    # so a test seeds it with mock.patch.object and reads a known roll.
    roll_rng = random.Random()

    def init_runtime_state(self) -> None:
        """(Re)initialise the ndb fields that tick() reads."""
        if self.ndb.lit is None:
            self.ndb.lit = {}

        if self.ndb.rolls is None:
            self.ndb.rolls = {}

        if self.ndb.drain_counter is None:
            self.ndb.drain_counter = aug_const.AUG_DRAIN_COUNTER_START

    # ── the lit set ──────────────────────────────────────────────────────

    def light(self, augment, step: int) -> bool:
        """
        Purpose: Light an augment at a step, or move a lit one to the step.

        Entry:
            augment is an instance of AUGMENT_REGISTRY.
            step is an int in [AUG_STEP_MIN, AUG_STEPS].

        Exit/Returns:
            Returns True when the augment was lit before this call (a
            re-step). False for a new light.

        Module Globals:
            None.

        Methodology:
            1. Put out every lit augment of the same conflict group.
            2. Roll, when the augment rolls. A re-step rerolls too: a
               relight is the reroll, and it costs the Grit it costs.
            3. One dict write. The drain counter keeps its value: a light
               mid-run owes what the run already built up.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 10/30/2026
        """
        self.init_runtime_state()

        self._put_out_conflicts(augment)

        if augment.rolls:
            level = pool.level(self.obj)
            self.ndb.rolls[augment.key] = float(augment.roll_for(level, self.roll_rng))

        was_lit = augment.key in self.ndb.lit
        self.ndb.lit[augment.key] = int(step)
        self._publish()

        return was_lit

    def _put_out_conflicts(self, augment) -> None:
        """Put out every other lit augment of the conflict group of one."""
        group = augment.conflict_group

        if not group:
            return

        for other, _step in self.lit_augments():
            if other.key != augment.key and other.conflict_group == group:
                self.ndb.lit.pop(other.key, None)
                self.ndb.rolls.pop(other.key, None)

    def roll_of(self, augment_key: str) -> float:
        """The roll of one lit augment that rolls, or 0.0."""
        self.init_runtime_state()

        return float(self.ndb.rolls.get(augment_key, 0.0))

    def put_out(self, augment_key: str) -> bool:
        """Put one augment out. Returns True when it was lit."""
        self.init_runtime_state()

        was_lit = self.ndb.lit.pop(augment_key, None) is not None
        self.ndb.rolls.pop(augment_key, None)

        if was_lit:
            self._publish()

        return was_lit

    def put_out_all(self) -> list:
        """Put every augment out. Returns the augments that were lit, in order."""
        self.init_runtime_state()

        lit = self.lit_augments()
        self.ndb.lit = {}
        self.ndb.rolls = {}

        if lit:
            self._publish()

        return [augment for augment, _step in lit]

    def _publish(self) -> None:
        """
        Purpose: Tell each client that draws the lit set that it changed.

        Entry:
            The lit set changed in this call.

        Exit/Returns:
            No conditions. Never raises: a feed send must never stop the
            write that already happened.

        Module Globals:
            None.

        Methodology:
            Three readers draw the lit set, so three sends. The rail is
            MARKED, and the build at the drain reads the finished state,
            as emit_aura does it. The own figure reads char_avatar, and
            the figure of each observer reads the entity row. Both carry
            the lit set, as they carry the worn record, so this is the
            send of character_figure.publish. A fourth reader is the ring
            of a lit aura, because Reach widens it: the aura handler
            rebuilds and sends its ring.

        Notes/References:
            The statefeed events are imported inside the routine. They
            import the pool of this package, which this module imports.

        Author: Nick Hobar
        Creation date: 10/30/2026
        """
        from systems.interface.statefeed import events as feed

        holder = self.obj

        if holder is None:
            return

        try:
            feed.refresh_abilities(holder)
            feed.emit_avatar(holder, force=True)

            location = getattr(holder, "location", None)

            if location is not None:
                feed.emit_entity_arrived(location, holder)

            self._refresh_aura_ring(holder)
        except Exception as exc:
            logger.log_err(f"AugmentHandler._publish: {holder} feed send failed: {exc!r}")

    def _refresh_aura_ring(self, holder) -> None:
        """Ask the aura handler of the holder, if any, to rebuild its ring.
        The aura package is imported inside the routine. It reaches this
        package through the rules module."""
        from systems.gameplay.combat.auras.aura_handler import get_aura_handler_for

        aura_handler = get_aura_handler_for(holder)

        if aura_handler is not None:
            aura_handler.refresh_ring()

    def is_lit(self, augment_key: str) -> bool:
        """Whether one augment burns."""
        self.init_runtime_state()

        return augment_key in self.ndb.lit

    def step_of(self, augment_key: str) -> int:
        """The step of one lit augment, or 0 when it is out."""
        self.init_runtime_state()

        return int(self.ndb.lit.get(augment_key, 0))

    def lit_augments(self) -> list:
        """
        Purpose: Every lit augment with its step, in the order of the rail.

        Entry:
            No conditions.

        Exit/Returns:
            Returns a list of (augment, step) pairs. A key with no registry
            entry (a renamed file after a light) is left out.

        Module Globals:
            None.

        Methodology:
            Walk the registry order, and keep the lit keys. The order is the
            server's, so the listing and the rail agree.

        Notes/References:
            None.

        Author: Nick Hobar
        Creation date: 10/30/2026
        """
        self.init_runtime_state()

        lit = self.ndb.lit
        pairs = []

        for augment in augments_in_order():
            if augment.key in lit:
                pairs.append((augment, int(lit[augment.key])))

        return pairs

    # ── the tick ─────────────────────────────────────────────────────────

    def tick(self) -> None:
        """
        Purpose: Advance the drain one tick.

        Entry:
            The tick engine calls this one time for each tick.

        Exit/Returns:
            No conditions. Every failure path ends the handler rather than
            raising, because the engine drops a handler on an exception.

        Module Globals:
            None.

        Methodology:
            1. No holder, or nothing lit: stop.
            2. A dead holder: put everything out and stop.
            3. Add the drain of each lit augment to the counter.
            4. While the counter passes the resistance, spend one point.
            5. At 0 Grit, put everything out, say so, and stop.

        Notes/References:
            The counter is a float, because a step share of a drain is one.

        Author: Nick Hobar
        Creation date: 10/30/2026
        """
        holder = self.obj

        if holder is None:
            self.stop_handler()
            return

        self.init_runtime_state()

        lit = self.lit_augments()

        if not lit:
            self.stop_handler()
            return

        alive = isinstance(holder, Combatant) and holder.is_alive()

        if not alive:
            self.put_out_all()
            self.stop_handler()
            return

        try:
            self._drain(holder, lit)
        except Exception:
            logger.log_trace()

    def _drain(self, holder, lit: list) -> None:
        """Run the counter for one tick, and spend what passes the resistance."""
        total = sum(augment.drain_for(step) for augment, step in lit)
        self.ndb.drain_counter += total
        resistance = resistance_for(holder)

        while self.ndb.drain_counter >= resistance:
            self.ndb.drain_counter -= resistance
            pool.spend(holder, aug_const.AUG_DRAIN_POINT)

        held = pool.current(holder)

        if held > aug_const.GRIT_EMPTY:
            return

        self.put_out_all()
        holder.msg((aug_const.AUG_SPENT_MESSAGE, _MSG_COMBAT))
        self.stop_handler()

    # ── cleanup ──────────────────────────────────────────────────────────

    def stop_handler(self) -> None:
        """
        Purpose: Leave the tick rotation and delete the script.

        Entry:
            No conditions.

        Exit/Returns:
            No conditions. After return, the holder has no augment handler.

        Module Globals:
            None.

        Methodology:
            The steps of BlackoutAuraHandler.stop_aura: pop the accessor
            cache, unregister, stop, delete. Each step is guarded alone.

        Notes/References:
            The lit set goes with the script. A caller that needs the names
            reads them before this call.

        Author: Nick Hobar
        Creation date: 10/30/2026
        """
        holder = self.obj

        if holder is not None:
            holder.__dict__.pop(self.ACCESSOR_NAME, None)

        try:
            from systems.core.tick.engine import get_tick_engine

            get_tick_engine().unregister(self)
        except Exception as exc:
            logger.log_err(f"AugmentHandler.stop_handler failed to unregister: {exc!r}")

        try:
            self.stop()
        except Exception as exc:
            logger.log_err(f"AugmentHandler.stop_handler failed stop: {exc!r}")

        try:
            self.delete()
        except Exception as exc:
            logger.log_err(f"AugmentHandler.stop_handler failed delete: {exc!r}")


# ─── Module helpers ──────────────────────────────────────────────────────────

def get_augment_handler_for(entity):
    """Return the ACTIVE augment handler of an entity, or None."""
    handler = _get_tickable_handler_for(entity, BlackoutAugmentHandler)

    return handler


def ensure_augment_handler(holder) -> BlackoutAugmentHandler:
    """Return the augment handler of a holder, and make and arm one if absent."""
    handler = ensure_handler(holder, BlackoutAugmentHandler)

    return handler


def lit_augments_of(entity) -> list:
    """The (augment, step) pairs lit on an entity. Empty with no handler."""
    handler = get_augment_handler_for(entity)

    if handler is None:
        return []

    return handler.lit_augments()
