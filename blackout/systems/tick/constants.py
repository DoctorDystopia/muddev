"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/18/2026
Description: Tunables for the server-wide tick — its length, its watchdog, its
             failure policy, and the knobs on its diagnostic monitor.

These lived in systems/combat/constants.py because combat is what needed a
heartbeat first. The tick is not combat's: auto-walk, auras, item definitions
and NPC definitions all express cadence in it, so it moved here with the engine
and TICK_SECONDS was renamed TICK_SECONDS to stop implying otherwise.
"""

# ─── Tick rhythm ─────────────────────────────────────────────────────────────
# Blackout surfaces a universal tick so the engine rhythm can be retuned
# globally without touching weapon definitions.
#
# This is consumed by the twisted LoopingCall in engine.py, NOT by an
# Evennia Script.interval — ScriptDB.db_interval is a Django IntegerField and
# would silently truncate 0.6 to 0, which disables the timer entirely.
TICK_SECONDS: float = 0.6

# How often the tick engine's Evennia-side watchdog fires to confirm the
# LoopingCall above is still alive. Must be a whole number of seconds.
TICK_ENGINE_WATCHDOG_SECONDS: int = 60

# How many CONSECUTIVE failures a handler may raise before the engine stops
# driving it. The old policy was to drop a handler on the FIRST exception,
# whose only symptom was combat silently stopping forever -- which is why
# debug.py had to be written to tell a stalled fight apart from a dropped
# handler. A transient failure (a row mid-delete, a target that vanished
# between the query and the swing) now costs a strike instead of the fight,
# and a genuinely broken handler still leaves the rotation, loudly.
#
# Three is chosen so a handler must fail across ~1.8s of wall time before it
# is given up on -- long enough to outlast a single bad tick, short enough
# that a wedged handler cannot spin for a noticeable stretch.
TICK_HANDLER_MAX_STRIKES: int = 3

# ─── Tick diagnostics ────────────────────────────────────────────────────────
# Knobs for the player-toggleable tick monitor in debug.py. Diagnostics
# only: nothing here changes what the engine DOES, only what it reports.

# How many ticks a streaming observer is served before the monitor switches
# itself off. At TICK_SECONDS that is five minutes. Left on, a stream
# emits ~100 lines a minute forever, and the player who forgot about it is the
# last person who will notice.
TICK_DEBUG_AUTO_EXPIRE_TICKS: int = 500

# A tick is reported LATE when the measured gap since the previous one exceeds
# this multiple of TICK_SECONDS. LoopingCall schedules on a fixed
# cadence and absorbs small overruns on its own, so a factor rather than a flat
# margin is what distinguishes a real stall from ordinary scheduler noise.
TICK_DEBUG_LATE_TICK_FACTOR: float = 1.5

# How many measured intervals the engine keeps for the `tickdebug status`
# mean/max/late report. Recorded unconditionally -- one deque append per tick
# costs nothing, and it is what makes status a health check over a window
# rather than a single instantaneous reading.
TICK_DEBUG_SAMPLE_WINDOW: int = 50
