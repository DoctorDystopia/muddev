"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/30/2026
Description: BlackoutRespawnManager — the single server-wide queue that brings
             timed-respawn NPCs back after they die.

Why a Script and not utils.delay
--------------------------------
``utils.delay(..., persistent=True)`` *is* reload-safe (TASK_HANDLER persists to
ServerConfig and rebuilds the deferreds at boot — evennia/scripts/taskhandler.py),
so persistence is not the reason to avoid it. The reasons are:

  * No dedupe. The one hard requirement here is "never two raiders on one tile",
    which needs a queue you can *query* — TASK_HANDLER.tasks is an opaque dict
    keyed by task id.
  * The callback is pickled by identity, so renaming this module would silently
    break every queued task with no way to enumerate the damage.
  * One deferLater per pending NPC vs. one sweep for the whole world.

Persistence shape
-----------------
``db.respawn_queue`` is a list of plain dicts::

    {"npc_key": "mutant_raider", "room": <Room>, "due_at": 1753900000.0}

Live Object references nest safely: ``to_pickle`` packs them as
``("__packed_dbobj__", natural_key, date_created, id)`` at any depth
(evennia/utils/dbserialize.py) and ``from_pickle`` checks for that form *before*
the tuple branch. The packed form also validates ``db_date_created`` on unpack,
which is why we store the object rather than a bare dbref int — a raw int would
silently resolve to the wrong room after an id reuse.

If the room was deleted, ``unpack_dbobj`` returns ``None`` rather than raising,
so ``_spawn`` must treat ``room is None`` as "drop this entry".

Entries are *dicts inside a list*, never tuples: ``from_pickle.process_tree``
passes the tuple itself as the saver ``parent``, and a tuple has no
``_save_tree`` — so any mutable nested in a tuple raises on the first in-place
edit. Dicts inside a list get a real ``_SaverList`` parent.

Deadlines are absolute ``time.time()`` values, so an entry that came due while
the server was down fires on the first sweep after boot. ``time.monotonic()``
cannot be used: its epoch is process-relative and meaningless after a restart.
The residual risk is an NTP step larger than a respawn window, which is
acceptable at these timescales.
"""

import time

from evennia.scripts.models import ScriptDB
from evennia.scripts.scripts import DefaultScript
from evennia.utils import logger

# ─── module constants ──────────────────────────────────────────────────────

RESPAWN_MANAGER_KEY = "blackout_respawn_manager"

# Whole seconds — ScriptDB.db_interval is a Django IntegerField, so a float
# would truncate (see systems/combat/tick_engine.py's module docstring). 2s
# bounds worst-case lateness on a 30s respawn at ~7%.
RESPAWN_SWEEP_SECONDS: int = 2


# ─── identity helper ───────────────────────────────────────────────────────


def npc_present(npc_key, room) -> bool:
    """True if a live NPC carrying this registry key already stands in `room`.

    Identity is ``db.npc_key``, deliberately NOT ``is_typeclass``. Every hostile
    shares ``typeclasses.npc_combat.HostileNPC``, so the typeclass check that
    spawn_bank / spawn_shopkeep use would false-positive the moment a second
    hostile type shares a tile — a mutant raider standing next to a feral dog
    would suppress the dog's respawn forever.

    A falsy `npc_key` never matches, so an unstamped legacy NPC (whose
    ``npc_key`` reads None) cannot be mistaken for anything.
    """
    if not npc_key or room is None or getattr(room, "pk", None) is None:
        return False
    for obj in room.contents:
        if obj.attributes.get("npc_key") == npc_key:
            return True
    return False


# ─── the manager ───────────────────────────────────────────────────────────


class BlackoutRespawnManager(DefaultScript):
    """Global Script owning the pending-respawn queue.

    One sweep every RESPAWN_SWEEP_SECONDS pops every entry whose absolute
    deadline has passed and re-creates the NPC from NPC_DB, isolating failures
    so one broken entry cannot stall respawns world-wide.
    """

    def at_script_creation(self) -> None:
        self.key = RESPAWN_MANAGER_KEY
        self.desc = "Global timed-NPC respawn queue"
        self.interval = RESPAWN_SWEEP_SECONDS
        self.persistent = True
        self.db.respawn_queue = []

    # ── lifecycle ────────────────────────────────────────────────────────

    def _ensure_running(self) -> None:
        """Guarantee the Evennia timer is actually armed.

        The *clean* reload path re-arms us for free: the server pauses every
        active Script on shutdown and ``update_scripts_after_server_start``
        unpauses them.

        A *hard* crash never runs the pause, so ``db._paused_time`` is unset
        and ``_unpause_task`` returns without creating a task — the Script
        would stay ``is_active`` forever with no timer and respawns would
        silently stop. That is the one way this diverges from the tick engine,
        which never depends on its Evennia interval for real work.

        ``start()`` is idempotent (it returns early when a task is already
        running and nothing changed), so this is safe to call repeatedly.
        """
        task = self.ndb._task
        if task is not None and task.running:
            return
        self.start()

    def at_server_start(self) -> None:
        """Reliable post-reload hook.

        ``ScriptDB.objects.update_scripts_after_server_start`` calls this on
        every script, active or not, so it is the one place guaranteed to run
        after a reload/restart.
        """
        self._ensure_running()

    # ── queue access ─────────────────────────────────────────────────────

    def _read_queue(self) -> list:
        """Plain-python snapshot of the queue.

        ``self.db.respawn_queue`` hands back a ``_SaverList`` of
        ``_SaverDict``s. Copying to plain dicts up front means every mutation
        below lands as a single explicit reassignment, so a sweep that raises
        mid-loop can never leave a half-applied queue — and we never risk
        ``_SaverMutable._save_tree``'s "root Attribute deleted" ValueError.
        """
        return [dict(entry) for entry in (self.db.respawn_queue or [])]

    def _write_queue(self, entries: list) -> None:
        self.db.respawn_queue = entries

    # ── scheduling ───────────────────────────────────────────────────────

    def schedule(self, npc_key, room, delay_seconds, now=None) -> bool:
        """Queue `npc_key` to reappear in `room` after `delay_seconds`.

        Entry:
            npc_key       - NPC_DB registry key (e.g. "mutant_raider").
            room          - the room to respawn into. Must still exist.
            delay_seconds - whole seconds from now.
            now           - injectable clock, so tests can pin the deadline
                            without mocking time.time.

        Exit/Returns:
            True if an entry was added; False if the request was rejected or
            already queued.
        """
        if not npc_key or room is None or getattr(room, "pk", None) is None:
            return False
        try:
            delay = max(0, int(delay_seconds))
        except (TypeError, ValueError):
            logger.log_err(
                f"BlackoutRespawnManager: bad delay {delay_seconds!r} for {npc_key!r}."
            )
            return False

        queue = self._read_queue()
        # Idempotent per (npc_key, room): two copies of the same NPC dying on
        # one tile in the same tick must not queue two respawns.
        for entry in queue:
            if entry.get("npc_key") == npc_key and entry.get("room") == room:
                return False

        queue.append(
            {
                "npc_key": npc_key,
                "room": room,
                "due_at": (time.time() if now is None else now) + delay,
            }
        )
        self._write_queue(queue)
        return True

    def cancel(self, npc_key, room) -> int:
        """Drop pending entries for (npc_key, room). Returns the count dropped.

        Not needed by the current flow — the two presence guards fully close
        the grid-rebuild race — but the queue is only useful if it is also
        revocable.
        """
        queue = self._read_queue()
        keep = [
            entry
            for entry in queue
            if not (entry.get("npc_key") == npc_key and entry.get("room") == room)
        ]
        dropped = len(queue) - len(keep)
        if dropped:
            self._write_queue(keep)
        return dropped

    # ── the sweep ────────────────────────────────────────────────────────

    def at_repeat(self, **kwargs) -> None:
        try:
            self.sweep()
        except Exception:
            # Belt and braces. ScriptBase._step_task's errback would absorb a
            # raise and keep the ExtendedLoopingCall alive, but the world-wide
            # sweep must not depend on that.
            logger.log_trace()

    def sweep(self, now=None) -> int:
        """Spawn every entry whose deadline has passed.

        Entry:
            now - injectable clock, so tests can advance time without sleeping.

        Exit/Returns:
            The number of NPCs actually spawned.
        """
        queue = self._read_queue()
        if not queue:
            return 0

        now = time.time() if now is None else now
        remaining = []
        spawned = 0

        for entry in queue:
            try:
                if float(entry.get("due_at", 0)) > now:
                    remaining.append(entry)
                    continue
                if self._spawn(entry):
                    spawned += 1
            except Exception:
                # One bad entry must never stall respawns world-wide; mirrors
                # BlackoutTickEngine._tick. The entry is dropped rather than
                # retried, so a permanently broken entry cannot wedge the queue
                # behind it.
                logger.log_trace()

        self._write_queue(remaining)
        return spawned

    def _spawn(self, entry) -> bool:
        """Re-create one queued NPC. Returns True if an object was created."""
        # Local import: world.npc_database pulls world.npc_defs.* at import
        # time; keeping it lazy matches the style in npc_combat.py and keeps
        # this module importable in isolation.
        from world.npc_database import NPC_DB

        room = entry.get("room")
        npc_key = entry.get("npc_key")

        # A deleted room unpickles to None, so a razed / rebuilt grid quietly
        # drops its pending respawns instead of raising mid-sweep.
        if room is None or getattr(room, "pk", None) is None:
            return False

        npc_def = NPC_DB.get(npc_key)
        if npc_def is None:
            logger.log_err(
                f"BlackoutRespawnManager: unknown npc_key {npc_key!r}; dropping entry."
            )
            return False

        if npc_present(npc_key, room):
            # e.g. `xyzgrid spawn` re-ran the room spawner during the dead
            # window. Drop rather than double up.
            return False

        npc_def.create(location=room)
        return True


# ─── module helpers ────────────────────────────────────────────────────────


def get_respawn_manager() -> BlackoutRespawnManager:
    """Return the global respawn manager, creating and arming it if absent.

    Mirrors get_tick_engine, plus the explicit _ensure_running that an
    interval-driven Script needs to survive a hard crash.
    """
    manager = ScriptDB.objects.filter(db_key=RESPAWN_MANAGER_KEY).first()

    if manager is None:
        manager, errors = BlackoutRespawnManager.create(key=RESPAWN_MANAGER_KEY)
        if errors:
            raise RuntimeError(
                f"Could not create the Blackout respawn manager: {errors}"
            )

    manager._ensure_running()
    return manager


def schedule_respawn(npc_key, room, delay_seconds, now=None) -> bool:
    """Convenience wrapper — the single entry point callers should use."""
    return get_respawn_manager().schedule(npc_key, room, delay_seconds, now=now)


def bootstrap_respawns() -> BlackoutRespawnManager:
    """Bring respawns up at server start. Called from at_server_startstop.

    The immediate sweep matters: entries that came due while the server was
    down should land at boot rather than up to RESPAWN_SWEEP_SECONDS later,
    and it gives bootstrap an assertable behaviour — mirroring how
    bootstrap_combat purges before creating the tick engine.
    """
    manager = get_respawn_manager()
    try:
        manager.sweep()
    except Exception:
        logger.log_trace()
    return manager
