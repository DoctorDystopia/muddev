"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/11/2026
Description: Tests for the clock behind the graffiti sweep.

             The sweep itself is tested in test_service.py. What is tested
             here is the part that has historically gone wrong in this repo
             rather than in this package: a global Script that exists in the
             database and is not actually running.

             CLAUDE.md records the two ways that happens. A Script row stores
             its typeclass as an import PATH, so moving the module leaves
             Evennia handing back a plain DefaultScript instead of raising --
             which is how every attack in the game died on
             `'DefaultScript' object has no attribute '_ensure_loop'`. And a
             hard crash never runs the shutdown pause, so the timer is never
             re-armed and the Script stays `is_active` with nothing behind it.

             `managers.get_singleton_script` answers the first and
             `_ensure_running` answers the second; these assert both are
             actually reached, and that bootstrapping twice does not make two.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \
        systems.gameplay.graffiti.tests.test_decay
"""

import time

from evennia import create_object
from evennia.scripts.models import ScriptDB
from evennia.utils.test_resources import EvenniaTestCase

from systems.core.managers import MANAGER_REGISTRY, load_all_managers
from systems.gameplay.graffiti import constants as const
from systems.gameplay.graffiti import decay
from typeclasses.signs import Graffiti


class TestDecayScript(EvenniaTestCase):
    """
    Purpose: That the sweep is scheduled, once, and reachable after a restart.

    Entry:
        No conditions.

    Exit/Returns:
        No conditions.

    Module Globals:
        None.

    Methodology:
        EvenniaTestCase: a Script needs a database and nothing else here needs
        a character.

        Each test stops and deletes whatever it created, because a global
        singleton keyed on a db_key is exactly the kind of state that leaks
        between test methods and makes the second assertion about "only one"
        pass or fail depending on order.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/11/2026
    """

    def tearDown(self):
        for row in ScriptDB.objects.filter(db_key=const.DECAY_SCRIPT_KEY):
            row.delete()

        super().tearDown()


    def _rows(self):
        return ScriptDB.objects.filter(db_key=const.DECAY_SCRIPT_KEY)


    def test_bootstrapping_creates_the_script(self):
        script = decay.bootstrap_graffiti_decay()

        self.assertIsInstance(script, decay.GraffitiDecayScript)
        self.assertEqual(self._rows().count(), 1)


    def test_bootstrapping_twice_does_not_make_two(self):
        # bootstrap_all runs after a reload as well as a cold start, so every
        # bootstrap in the registry has to be idempotent.
        first = decay.bootstrap_graffiti_decay()
        second = decay.bootstrap_graffiti_decay()

        self.assertEqual(first, second)
        self.assertEqual(self._rows().count(), 1)


    def test_it_is_scheduled_at_the_interval_the_constants_name(self):
        script = decay.bootstrap_graffiti_decay()

        self.assertEqual(script.interval, const.SWEEP_INTERVAL_SECONDS)
        self.assertTrue(script.persistent)


    def test_a_stale_typeclass_row_is_repaired_rather_than_returned(self):
        # The ShopkeepCleanup failure, in a new place. Evennia hands back a
        # plain DefaultScript for a path that no longer resolves instead of
        # raising, so a lookup by key alone returns an object missing every
        # method the caller is about to use.
        script = decay.bootstrap_graffiti_decay()
        script.db_typeclass_path = "systems.gameplay.graffiti.gone.Nothing"
        script.save()

        repaired = decay.get_decay_script()

        self.assertIsInstance(repaired, decay.GraffitiDecayScript)
        self.assertEqual(self._rows().count(), 1)


    def test_the_bootstrap_is_registered_with_the_manager_registry(self):
        # The one thing joining this package to server start. A bootstrap that
        # is not registered never runs, with nothing raised and nothing
        # logged -- which is the hole systems/core/managers.py was written to
        # close.
        load_all_managers()
        names = list(MANAGER_REGISTRY)

        self.assertTrue(
            any(name.endswith("bootstrap_graffiti_decay") for name in names),
            f"bootstrap_graffiti_decay is not registered; found {names}")


    def test_the_bootstrap_sweeps_on_the_way_up(self):
        # A server down for a fortnight comes back holding scrawls that
        # expired while it was off, and waiting another hour to notice is a
        # world that looks unswept exactly when somebody is looking at it.
        room = create_object(key="a wall", location=None)
        stale = create_object(Graffiti, key="graffiti", location=room)
        stale.world_label = "OLD"
        stale.attributes.add(
            const.WRITTEN_AT_ATTR, time.time() - const.LIFETIME_SECONDS - 1)

        decay.bootstrap_graffiti_decay()

        self.assertIsNone(stale.pk)


    def test_one_repeat_runs_a_sweep(self):
        room = create_object(key="a wall", location=None)
        fresh = create_object(Graffiti, key="graffiti", location=room)
        fresh.world_label = "NEW"
        fresh.attributes.add(const.WRITTEN_AT_ATTR, time.time())

        stale = create_object(Graffiti, key="graffiti", location=room)
        stale.world_label = "OLD"
        stale.attributes.add(
            const.WRITTEN_AT_ATTR, time.time() - const.LIFETIME_SECONDS - 1)

        script = decay.bootstrap_graffiti_decay()
        script.at_repeat()

        self.assertIsNone(stale.pk)
        self.assertIsNotNone(fresh.pk)
