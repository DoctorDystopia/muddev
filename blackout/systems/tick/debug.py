"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/08/2026
Description: tick_debug — the player-toggleable monitor for the global 0.6s tick.

Why this is not in engine.py
------------------------------
The engine's job is to advance handlers. Deciding who is watching, and how a
tick reads, is a different fact with a different lifetime. engine.py gains
only the timing it already had no way to report plus two hook calls; the
observer set, the before/after diff and every format string live here.

Why the engine calls us TWICE per tick
--------------------------------------
The interesting fact about a tick is what RESOLVED on it, and that is only
visible as a difference. By the time the handler loop has run, a swing has
already recharged ``cooldown_ticks`` to ``attack_speed - 1``, so a reading
taken afterwards cannot tell the tick a swing landed on from any other tick of
the cycle. before_tick captures the pre-state; after_tick diffs against it.

Why nothing here may raise
--------------------------
An exception escaping ``_tick`` errbacks the twisted LoopingCall and stops it
dead. The Evennia-side watchdog would re-arm it, but only on its next pass --
up to TICK_ENGINE_WATCHDOG_SECONDS later, which is ~100 lost ticks for every
combatant on the server. A diagnostic must never be able to do that, so both
hooks swallow and log instead of propagating, and that guarantee lives here
rather than at the call site so it cannot be dropped by a future caller.

Why observers are process-local
-------------------------------
_observers is module state, so a reload clears every subscription. That is the
same lifetime rule the statefeed's session-ndb subscriptions follow, and for
the same reason: a monitor is meaningless across the reload that wiped the ndb
counters it was reporting on.
"""

from dataclasses import dataclass

from evennia.utils import logger
from systems.ui import colors

from . import constants as const
from systems.statefeed import constants as feed_const

# Every line this module sends a player is the server speaking as itself, so
# the routing tag is bound once here rather than repeated at every call site.
#
# The SERVER says what a line IS; the client decides which tab shows it. See
# MESSAGE_TYPES in systems/statefeed/constants.py.
_MSG_SYSTEM = {feed_const.MESSAGE_TYPE_KEY: feed_const.MESSAGE_TYPE_SYSTEM}


# ─── Public constant definitions ─────────────────────────────────────────────

# Streaming verbosity. QUIET is the default because a combatant spends most of
# its cycle counting down: at a speed-4 weapon three ticks in four say nothing
# new, and ALL would spend them repeating the previous line.
MODE_ALL: str = "all"
MODE_QUIET: str = "quiet"

# Not stream modes -- accepted by the command, handled before a mode is set.
MODE_OFF: str = "off"
MODE_STATUS: str = "status"

STREAM_MODES: tuple = (MODE_QUIET, MODE_ALL)
DEFAULT_MODE: str = MODE_QUIET


# ─── Private constant definitions ────────────────────────────────────────────

# Zero-padding on the tick number. Wide enough that the column does not jitter
# for the first ~11 hours of server uptime, which is what makes a stream
# scannable by eye.
_TICK_NUMBER_WIDTH: int = 5

# Decimal places on a measured interval. Three, because the deviations worth
# seeing at a 0.6s cadence are milliseconds.
_INTERVAL_PRECISION: int = 3

_SEGMENT_SEPARATOR: str = " | "
_IDLE_LABEL: str = "idle"

# What the marker on a resolving tick reads. A swing is the overwhelmingly
# common case and deserves its own word; hold/flee/wield resolve on the same
# branch of BlackoutCombatHandler.tick but are not swings, and labelling them
# one would be a lie on the line that matters most.
_SWING_LABEL: str = "SWING"
_RESOLVE_LABEL: str = "RESOLVE"

# The action kind ActionAttack carries. combat.queue_action spells this as a
# literal in its own dispatch; it is repeated here only to pick a display
# word, and nothing branches on it.
_ATTACK_ACTION_KIND: str = "attack"

_PULSE_LABEL: str = "PULSE"
_LATE_LABEL: str = "LATE"
_LOOP_RUNNING_LABEL: str = "running"
_LOOP_STOPPED_LABEL: str = "STOPPED"
_UNREGISTERED_LABEL: str = "UNREGISTERED"
_COMBAT_ENDED_LABEL: str = "combat ended"
_AURA_ENDED_LABEL: str = "aura out"
_NO_SAMPLES_LABEL: str = "no samples yet"
_NO_ENGINE_LABEL: str = "no tick engine exists"


# ─── Module globals ──────────────────────────────────────────────────────────

# character dbid -> _Observer. Process-local by design; see the module header.
_observers: dict = {}


# ─── Private data structures ─────────────────────────────────────────────────

@dataclass
class _CombatSnapshot:
    """One reading of a combatant's tick-facing combat state."""

    present: bool = False
    registered: bool = False
    cooldown: int = 0
    speed: int = 0
    action: str = ""
    target_id: int = None
    resolved: bool = False


@dataclass
class _AuraSnapshot:
    """One reading of a caster's tick-facing aura state."""

    present: bool = False
    registered: bool = False
    remaining: int = 0
    interval: int = 0
    aura_key: str = ""
    pulsed: bool = False


@dataclass
class _Observer:
    """One player watching the tick, and the state the diff needs.

    before_* is this tick's pre-state, captured by before_tick and used only to
    decide whether an action RESOLVED on this tick. last_* is the previous
    tick's post-state, used to decide whether anything CHANGED. They answer
    different questions and cannot be collapsed into one field.
    """

    character: object
    mode: str
    ticks_remaining: int
    before_combat: object = None
    before_aura: object = None
    last_combat: object = None
    last_aura: object = None
    target_id: int = None
    target_name: str = ""


# ─── Private helper routines: state capture ──────────────────────────────────

def _find_engine():
    """Return the global tick engine if it exists, without creating one.

    Deliberately not get_tick_engine: a diagnostic that reports on the engine
    must not be the thing that brings it into being, or `tickdebug status`
    could never answer "the engine is missing".
    """
    from evennia.scripts.models import ScriptDB

    from .engine import TICK_ENGINE_KEY

    engine = ScriptDB.objects.filter(db_key=TICK_ENGINE_KEY).first()

    return engine


def _capture_combat(engine, character) -> _CombatSnapshot:
    """Read `character`'s combat handler into a snapshot.

    The imports are deferred for the reason given on
    the tickable registry: the handler modules and the engine
    reference each other, and resolving that at import time closes the cycle.
    """
    from systems.combat.combat import get_handler_for

    handler = get_handler_for(character)

    if handler is None:
        return _CombatSnapshot()

    weapon_data = handler.ndb.active_weapon_data or {}
    action = handler.ndb.pending_action
    cooldown = handler.ndb.cooldown_ticks or 0
    speed = weapon_data.get("attack_speed", 0)
    registered = engine.is_registered(handler) if engine is not None else False

    return _CombatSnapshot(
        present=True,
        registered=registered,
        cooldown=cooldown,
        speed=speed,
        action=getattr(action, "kind", ""),
        target_id=handler.ndb.target_id,
    )


def _capture_aura(engine, character) -> _AuraSnapshot:
    """Read `character`'s aura handler into a snapshot."""
    from systems.combat.auras.aura_handler import get_aura_handler_for

    handler = get_aura_handler_for(character)

    if handler is None:
        return _AuraSnapshot()

    aura = handler.get_aura()

    if aura is None:
        return _AuraSnapshot(present=True)

    registered = engine.is_registered(handler) if engine is not None else False

    return _AuraSnapshot(
        present=True,
        registered=registered,
        remaining=handler.ndb.ticks_until_pulse or 0,
        interval=aura.tick_interval,
        aura_key=aura.key,
    )


def _mark_resolutions(observer, combat, aura) -> None:
    """Set the resolved/pulsed flags on this tick's post-state snapshots.

    A handler resolves its pending action on the tick it enters with a zero
    counter -- that is exactly the branch BlackoutCombatHandler.tick and
    BlackoutAuraHandler.tick take -- so the pre-state alone decides this. It is
    read off `before` rather than inferred from the post-state on purpose: a
    killing blow ends combat on the very tick it lands, and an inference from
    the post-state would lose the most interesting swing of the fight.
    """
    before_combat = observer.before_combat

    if before_combat is not None and before_combat.present:
        combat.resolved = (before_combat.cooldown <= 0 and bool(before_combat.action))

    before_aura = observer.before_aura

    if before_aura is not None and before_aura.present and before_aura.aura_key:
        aura.pulsed = (before_aura.remaining <= 0)


def _target_name(observer, target_id) -> str:
    """Resolve a target dbid to a display name, caching on the observer.

    One database query per target CHANGE rather than per tick. Naming the
    target is the whole point of the combat segment, but re-fetching an object
    whose id has not moved, ten times a minute per observer, is not.
    """
    if target_id is None:
        return ""

    if observer.target_id == target_id:
        return observer.target_name

    from evennia.objects.models import ObjectDB

    target = ObjectDB.objects.filter(id=target_id).first()
    name = target.key if target is not None else str(target_id)

    observer.target_id = target_id
    observer.target_name = name

    return name


# ─── Private helper routines: measurement ────────────────────────────────────

def _late_threshold() -> float:
    """Return the interval above which a tick counts as late."""
    threshold = const.TICK_SECONDS * const.TICK_DEBUG_LATE_TICK_FACTOR

    return threshold


def _interval_stats(engine) -> dict:
    """
    Purpose: Summarise the engine's recent measured tick intervals.

    Entry:
        engine - a BlackoutTickEngine, or None.

    Exit/Returns:
        Returns a dict with keys count / mean / peak / late. count is 0 when
        no samples have been recorded yet, and the other fields are then 0.0.

    Module Globals:
        const.TICK_SECONDS and const.TICK_DEBUG_LATE_TICK_FACTOR read.

    Methodology:
        Reads the engine's rolling window and reduces it in one pass.

    Notes/References:
        The window is recorded by the engine unconditionally, so this reports
        real health whether or not anyone is streaming.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    empty = {"count": 0, "mean": 0.0, "peak": 0.0, "late": 0}

    if engine is None:
        return empty

    recorded = engine.ndb.tick_intervals

    if not recorded:
        return empty

    samples = list(recorded)
    threshold = _late_threshold()
    total = sum(samples)
    peak = max(samples)
    late = 0

    for sample in samples:
        if sample > threshold:
            late += 1

    mean = total / len(samples)

    return {"count": len(samples), "mean": mean, "peak": peak, "late": late}


# ─── Private helper routines: rendering ──────────────────────────────────────

def _format_interval(interval: float, is_late: bool) -> str:
    """Render one measured interval, tinted when it ran long."""
    text = f"{interval:.{_INTERVAL_PRECISION}f}s"

    if not is_late:
        return text

    return f"{colors.ERROR_COLOR}{text} {_LATE_LABEL}{colors.RESET_COLOR}"


def _format_engine(engine) -> str:
    """Render the engine's own health: loop state and rotation size."""
    if engine is None:
        return f"{colors.ERROR_COLOR}{_NO_ENGINE_LABEL}{colors.RESET_COLOR}"

    loop = engine.ndb._tick_loop
    count = engine.registered_count()

    if loop is None or not loop.running:
        return f"{colors.ERROR_COLOR}loop {_LOOP_STOPPED_LABEL}{colors.RESET_COLOR}"

    return f"eng {count}h"


def _resolution_marker(action: str) -> str:
    """Pick the word for a tick on which an action fired."""
    if action == _ATTACK_ACTION_KIND:
        return _SWING_LABEL

    return _RESOLVE_LABEL


def _format_combat(observer, combat: _CombatSnapshot) -> str:
    """Render the combat segment of one stream line, or "" when there is none."""
    last = observer.last_combat

    if not combat.present:
        if last is not None and last.present:
            return f"{colors.DIM_COLOR}{_COMBAT_ENDED_LABEL}{colors.RESET_COLOR}"
        return ""

    target = _target_name(observer, combat.target_id)
    action = combat.action or _IDLE_LABEL
    parts = [f"cd {combat.cooldown}/{combat.speed} {action}"]

    if target:
        parts.append(f"-> {target}")

    if combat.resolved:
        # The marker names what resolved, which is the action the tick STARTED
        # with. Reading it off the post-state would mislabel every one-shot
        # action: a hold clears itself, so `combat.action` is already "" by now.
        marker = _resolution_marker(observer.before_combat.action)
        parts.insert(0, f"{colors.SUCCESS_COLOR}{marker}{colors.RESET_COLOR}")

    if not combat.registered:
        parts.append(f"{colors.ERROR_COLOR}{_UNREGISTERED_LABEL}{colors.RESET_COLOR}")

    return " ".join(parts)


def _format_aura(observer, aura: _AuraSnapshot) -> str:
    """Render the aura segment of one stream line, or "" when there is none."""
    last = observer.last_aura

    if not aura.present or not aura.aura_key:
        if last is not None and last.present:
            return f"{colors.DIM_COLOR}{_AURA_ENDED_LABEL}{colors.RESET_COLOR}"
        return ""

    parts = [f"{aura.aura_key} {aura.remaining}/{aura.interval}"]

    if aura.pulsed:
        parts.insert(0, f"{colors.HIGHLIGHT_COLOR}{_PULSE_LABEL}{colors.RESET_COLOR}")

    if not aura.registered:
        parts.append(f"{colors.ERROR_COLOR}{_UNREGISTERED_LABEL}{colors.RESET_COLOR}")

    return " ".join(parts)


def _render_line(engine, observer, combat, aura, is_late: bool) -> str:
    """Assemble one stream line from the engine and per-handler segments."""
    number = engine.ndb.tick_number or 0
    interval = engine.ndb.tick_interval or 0.0

    head = f"{colors.DIM_COLOR}[t {number:0{_TICK_NUMBER_WIDTH}d}]{colors.RESET_COLOR}"
    timing = _format_interval(interval, is_late)
    segments = [_format_engine(engine)]

    combat_text = _format_combat(observer, combat)
    aura_text = _format_aura(observer, aura)

    if combat_text:
        segments.append(combat_text)

    if aura_text:
        segments.append(aura_text)

    if len(segments) == 1:
        segments.append(f"{colors.DIM_COLOR}{_IDLE_LABEL}{colors.RESET_COLOR}")

    body = _SEGMENT_SEPARATOR.join(segments)

    return f"{head} {timing} {body}"


# ─── Private helper routines: emission policy ────────────────────────────────

def _combat_changed(combat, last) -> bool:
    """True if the combat segment says something new since the previous tick."""
    if last is None:
        return True

    if combat.present != last.present:
        return True

    if not combat.present:
        return False

    if combat.registered != last.registered:
        return True

    if combat.action != last.action:
        return True

    return combat.target_id != last.target_id


def _aura_changed(aura, last) -> bool:
    """True if the aura segment says something new since the previous tick."""
    if last is None:
        return True

    if aura.present != last.present:
        return True

    if not aura.present:
        return False

    if aura.registered != last.registered:
        return True

    return aura.aura_key != last.aura_key


def _should_emit(observer, combat, aura, is_late: bool) -> bool:
    """
    Purpose: Decide whether this observer is told about this tick.

    Entry:
        observer - the _Observer being served.
        combat, aura - this tick's post-state snapshots, resolution flags set.
        is_late - True if the measured interval exceeded the late threshold.

    Exit/Returns:
        Returns True if a line should be sent.

    Module Globals:
        MODE_ALL read.

    Methodology:
        ALL emits unconditionally. QUIET emits only on something the player
        could not have predicted from the previous line: a resolution, a late
        tick, or a change in what a segment reports. A counter ticking down is
        deliberately NOT an event -- suppressing exactly that is what makes
        QUIET readable during a long fight.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    if observer.mode == MODE_ALL:
        return True

    if is_late or combat.resolved or aura.pulsed:
        return True

    combat_changed = _combat_changed(combat, observer.last_combat)

    if combat_changed:
        return True

    aura_changed = _aura_changed(aura, observer.last_aura)

    return aura_changed


def _is_reachable(character) -> bool:
    """True if `character` still exists to print to.

    Deliberately NOT a session check. Disconnecting drops the observer through
    at_disconnect_combat_cleanup, which is an event we already receive; polling
    every observer's session handler ten times a second to learn the same fact
    would be the wrong shape. This covers the case that has no event: an object
    deleted out from under us, whose row is simply gone.
    """
    if character is None:
        return False

    return character.pk is not None


def _serve(engine, observer, is_late: bool) -> bool:
    """Render and send one tick to one observer. False if it should be dropped.

    Returns False once the observer has run out of budget or has gone away, so
    the caller can retire it without a second pass over the dictionary.
    """
    character = observer.character

    reachable = _is_reachable(character)

    if not reachable:
        return False

    combat = _capture_combat(engine, character)
    aura = _capture_aura(engine, character)

    _mark_resolutions(observer, combat, aura)

    emit = _should_emit(observer, combat, aura, is_late)

    if emit:
        line = _render_line(engine, observer, combat, aura, is_late)
        character.msg((line, _MSG_SYSTEM))

    observer.last_combat = combat
    observer.last_aura = aura
    observer.ticks_remaining -= 1

    if observer.ticks_remaining > 0:
        return True

    character.msg(
        (f"{colors.DIM_COLOR}Tick monitor expired after "
        f"{const.TICK_DEBUG_AUTO_EXPIRE_TICKS} ticks.{colors.RESET_COLOR}", _MSG_SYSTEM)
    )

    return False


# ─── Public routines ─────────────────────────────────────────────────────────

def attach(character, mode: str = DEFAULT_MODE) -> None:
    """
    Purpose: Start streaming the tick to a character.

    Entry:
        character - a live, connected object with a msg() method.
        mode      - one of STREAM_MODES.

    Exit/Returns:
        No return. Re-attaching an already-watching character replaces its
        mode and refills its tick budget rather than stacking a second stream.

    Module Globals:
        _observers written.

    Methodology:
        Keyed on the character's dbid so a reconnecting player cannot end up
        watched twice through two different object references.

    Notes/References:
        The observer holds the character object directly rather than its id:
        serving it is a per-tick path, and a database round trip per observer
        per tick is exactly what the caching elsewhere in this module avoids.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    _observers[character.id] = _Observer(
        character=character,
        mode=mode,
        ticks_remaining=const.TICK_DEBUG_AUTO_EXPIRE_TICKS,
    )


def detach(character) -> bool:
    """Stop streaming to a character. Returns True if it had been watching."""
    removed = _observers.pop(character.id, None)

    return removed is not None


def is_watching(character) -> bool:
    """Return True if `character` currently has a stream running."""
    return character.id in _observers


def watched_mode(character) -> str:
    """Return the character's stream mode, or "" if it is not watching."""
    observer = _observers.get(character.id)

    if observer is None:
        return ""

    return observer.mode


def before_tick(engine) -> None:
    """
    Purpose: Capture each observer's pre-tick handler state.

    Entry:
        engine - the BlackoutTickEngine about to run its handler loop.

    Exit/Returns:
        No return, and NEVER raises. See the module header: an exception here
        would stop the LoopingCall for the whole server.

    Module Globals:
        _observers read and its entries written.

    Methodology:
        Returns immediately when nobody is watching, which is the normal case
        and must cost no more than a dictionary truth test.

    Notes/References:
        Pairs with after_tick, which consumes what this stores.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    if not _observers:
        return

    for observer in _observers.values():
        try:
            character = observer.character
            observer.before_combat = _capture_combat(engine, character)
            observer.before_aura = _capture_aura(engine, character)
        except Exception:
            # Isolated per observer, mirroring the engine's own rule that one
            # bad combatant cannot cost everyone else their tick. A shared
            # try/except around the loop let one deleted character abort the
            # pass for every other watcher.
            logger.log_trace()
            observer.before_combat = None
            observer.before_aura = None


def after_tick(engine) -> None:
    """
    Purpose: Diff each observer's state against its pre-tick reading and report.

    Entry:
        engine - the BlackoutTickEngine that has just run its handler loop,
                 with this tick's number, interval and duration recorded.

    Exit/Returns:
        No return, and NEVER raises. Observers that have disconnected or run
        out of tick budget are dropped here.

    Module Globals:
        _observers read and written.

    Methodology:
        Retirements are collected during the pass and applied after it, since
        a dictionary cannot be mutated while it is being iterated. Serving is
        isolated per observer for the same reason the engine isolates each
        handler: one watcher whose character was deleted mid-tick must not
        cost every other watcher their line, nor strand itself in the
        dictionary by aborting the pass that would have retired it.

    Notes/References:
        Pairs with before_tick.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    if not _observers:
        return

    interval = engine.ndb.tick_interval or 0.0
    threshold = _late_threshold()
    is_late = interval > threshold
    retired = []

    for character_id, observer in _observers.items():
        try:
            keep = _serve(engine, observer, is_late)
        except Exception:
            logger.log_trace()
            keep = False

        if not keep:
            retired.append(character_id)

    for character_id in retired:
        _observers.pop(character_id, None)


def snapshot(character) -> str:
    """
    Purpose: Build the one-shot `tickdebug status` report for a character.

    Entry:
        character - the object asking; needs no handlers and need not be in
                    combat.

    Exit/Returns:
        Returns the full multi-line report as one string.

    Module Globals:
        const.TICK_DEBUG_SAMPLE_WINDOW read.

    Methodology:
        Reads the engine's rolling interval window rather than a single
        reading, so a stall that has already passed is still visible.

    Notes/References:
        Never creates the engine; a missing engine is itself the finding.

    Author: Nick Hobar
    Creation date: 08/08/2026
    """
    engine = _find_engine()
    lines = [f"{colors.TITLE_COLOR}Tick engine{colors.RESET_COLOR}"]

    engine_lines = _snapshot_engine(engine)
    lines.extend(engine_lines)

    lines.append("")
    lines.append(f"{colors.TITLE_COLOR}You{colors.RESET_COLOR}")

    own_lines = _snapshot_character(engine, character)
    lines.extend(own_lines)

    return "\n".join(lines)


def _snapshot_engine(engine) -> list:
    """Render the engine half of the status report."""
    if engine is None:
        return [f"  {colors.ERROR_COLOR}{_NO_ENGINE_LABEL}{colors.RESET_COLOR}"]

    loop = engine.ndb._tick_loop
    running = loop is not None and loop.running
    state = _LOOP_RUNNING_LABEL if running else _LOOP_STOPPED_LABEL
    tint = colors.SUCCESS_COLOR if running else colors.ERROR_COLOR
    stats = _interval_stats(engine)
    number = engine.ndb.tick_number or 0
    duration = engine.ndb.tick_duration or 0.0
    count = engine.registered_count()
    failing = engine.failing_count()

    lines = [
        f"  loop          {tint}{state}{colors.RESET_COLOR}"
        f" at {const.TICK_SECONDS}s nominal",
        f"  tick number   {number}",
        f"  handlers      {count} registered",
        f"  last body     {duration * 1000:.1f}ms",
    ]

    # Only shown when non-zero. A handler that is failing but not yet evicted
    # is the state the old drop-on-first-exception policy never had a name
    # for, and silence is the correct report when nothing is wrong.
    if failing:
        lines.append(
            f"  failing       {colors.ERROR_COLOR}{failing} handler(s) carrying "
            f"strikes, evicted at {const.TICK_HANDLER_MAX_STRIKES}"
            f"{colors.RESET_COLOR}"
        )

    if not stats["count"]:
        lines.append(f"  intervals     {colors.DIM_COLOR}{_NO_SAMPLES_LABEL}{colors.RESET_COLOR}")
        return lines

    late_tint = colors.ERROR_COLOR if stats["late"] else colors.DIM_COLOR
    lines.append(
        f"  intervals     {stats['mean']:.{_INTERVAL_PRECISION}f}s mean, "
        f"{stats['peak']:.{_INTERVAL_PRECISION}f}s max over {stats['count']} ticks "
        f"({late_tint}{stats['late']} late{colors.RESET_COLOR})"
    )

    return lines


def _snapshot_character(engine, character) -> list:
    """Render the per-character half of the status report."""
    combat = _capture_combat(engine, character)
    aura = _capture_aura(engine, character)
    lines = []

    if not combat.present:
        lines.append(f"  combat        {colors.DIM_COLOR}not in combat{colors.RESET_COLOR}")
    else:
        target = _observer_free_target_name(combat.target_id)
        action = combat.action or _IDLE_LABEL
        registered = _registration_text(combat.registered)
        lines.append(
            f"  combat        cooldown {combat.cooldown}/{combat.speed}, "
            f"{action}{target} ({registered})"
        )

    if not aura.present or not aura.aura_key:
        lines.append(f"  aura          {colors.DIM_COLOR}none burning{colors.RESET_COLOR}")
    else:
        registered = _registration_text(aura.registered)
        lines.append(
            f"  aura          {aura.aura_key}, pulse in "
            f"{aura.remaining}/{aura.interval} ({registered})"
        )

    mode = watched_mode(character)

    if mode:
        lines.append(f"  monitor       streaming in {mode} mode")

    return lines


def _registration_text(registered: bool) -> str:
    """Render whether a handler is actually in the engine's rotation.

    Worth its own line in the report: _tick drops a handler from the rotation
    on any exception it raises, and the only symptom a player sees is combat
    quietly stopping.
    """
    if registered:
        return "in rotation"

    return f"{colors.ERROR_COLOR}{_UNREGISTERED_LABEL}{colors.RESET_COLOR}"


def _observer_free_target_name(target_id) -> str:
    """Resolve a target name for the status report, which has no observer cache."""
    if target_id is None:
        return ""

    from evennia.objects.models import ObjectDB

    target = ObjectDB.objects.filter(id=target_id).first()

    if target is None:
        return f" -> {target_id}"

    return f" -> {target.key}"
