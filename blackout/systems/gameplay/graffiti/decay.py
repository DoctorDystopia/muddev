"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: The clock behind the sweep. The only module in this package that
             knows one exists.

             A global Script rather than a tick-engine phase hook, and the
             reason is the ratio: the tick is 0.6s and a scrawl lives a week,
             so riding the tick would mean a counter compared 100,000 times
             between sweeps to answer "not yet". The engine's phase hooks are
             for work measured in ticks -- combat, regen, AI -- and this is
             measured in hours.

             Why a Script and not ``utils.delay``: the same reason respawn.py
             gives at length. A delay chain has one link, and a link lost to a
             hard crash is a sweep that never runs again with nothing raised.
             An interval Script is a row in the database that Evennia re-arms
             at boot.

             Reached through ``managers.get_singleton_script``, which is what
             repairs the row if this package is ever moved -- a Script stores
             its typeclass as an import path, and a stale one hands back a
             plain DefaultScript instead of raising. That is exactly the
             ShopkeepCleanup failure CLAUDE.md records, and the reason nothing
             here is reached by key alone.
"""

from evennia import DefaultScript
from evennia.utils import logger

from systems.core.managers import get_singleton_script, register_manager

from . import constants as const
from . import service


class GraffitiDecayScript(DefaultScript):
    """
    Purpose: Run the graffiti sweep once an hour, forever.

    Entry:
        Created and armed by bootstrap_graffiti_decay below.

    Exit/Returns:
        No conditions.

    Module variables:
        const.DECAY_SCRIPT_KEY and const.SWEEP_INTERVAL_SECONDS read.

    Methodology:
        It holds NO state. The queue a respawn manager needs does not exist
        here: what is due is a question the database answers, because every
        scrawl carries its own timestamp. That makes the Script disposable --
        losing it and recreating it loses nothing, which is what lets
        get_singleton_script replace a stale row without rescuing attributes.

        Wrapped in at_repeat, matching the respawn manager: a failed sweep must
        not kill the timer, or one unlucky hour stops every future hour.

    Notes/References:
        systems/gameplay/graffiti/service.py sweep() does the work.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """

    def at_script_creation(self):
        self.key = const.DECAY_SCRIPT_KEY
        self.desc = "Hourly sweep of expired player graffiti"
        self.interval = const.SWEEP_INTERVAL_SECONDS
        self.persistent = True


    def _ensure_running(self) -> None:
        """
        Guarantee the Evennia timer is armed, after a crash as well as a
        reload.

        A clean reload re-arms every Script for free; a hard crash never runs
        the pause, so `_unpause_task` creates nothing and the Script stays
        active with no timer behind it. `start()` is idempotent, so calling it
        is cheaper than deciding whether to. Copied in shape from
        BlackoutRespawnManager._ensure_running, which found this out first.
        """
        task = self.ndb._task

        if task is not None and task.running:
            return

        self.start()


    def at_server_start(self) -> None:
        """
        The one hook guaranteed to run after any reload or restart --
        `update_scripts_after_server_start` calls it on every Script, active or
        not.
        """
        self._ensure_running()


    def at_repeat(self, **kwargs) -> None:
        """
        One sweep. Wrapped, because a timer that dies on a bad row never comes
        back and the world quietly fills up again.
        """
        try:
            service.sweep()
        except Exception:
            logger.log_trace()


# ─── Module helpers ──────────────────────────────────────────────────────────

def get_decay_script() -> GraffitiDecayScript:
    """
    Purpose: The one decay Script, created and armed if absent.

    Entry:
        Called after Django and Evennia are initialised.

    Exit/Returns:
        Returns a live GraffitiDecayScript.

    Module Globals:
        const.DECAY_SCRIPT_KEY read.

    Methodology:
        Mirrors get_respawn_manager: the singleton lookup repairs a stale
        typeclass path, and the explicit arm is what an interval-driven Script
        needs to survive a hard crash.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    script = get_singleton_script(
        const.DECAY_SCRIPT_KEY, GraffitiDecayScript)

    script._ensure_running()

    return script


@register_manager
def bootstrap_graffiti_decay() -> GraffitiDecayScript:
    """
    Purpose: Bring the sweep up at server start.

    Entry:
        Called by managers.bootstrap_all, which isolates a failure here from
        every other manager.

    Exit/Returns:
        Returns the armed Script.

    Module Globals:
        None.

    Methodology:
        An immediate sweep on the way up, for the reason the respawn manager
        runs one: a server down for a fortnight comes back holding scrawls
        that expired while it was off, and waiting another hour to notice is a
        world that looks unswept exactly when somebody is looking at it.

        Failures are logged rather than raised. The sweep is housekeeping --
        nothing a player does depends on it having run -- so a broken one must
        not join the boot sequence's list of reasons the server did not come
        up.

    Notes/References:
        Registered by name in systems/core/managers.py _MANAGER_MODULES.

    Author: Nick Hobar
    Creation date: 09/11/2026
    """
    script = get_decay_script()

    try:
        service.sweep()
    except Exception:
        logger.log_trace()

    return script
