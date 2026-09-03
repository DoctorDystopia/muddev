"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/18/2026
Description: Tests for the TickableHandler base and the @register_tickable
             registry that replaced the hand-maintained key list.

The registration test is the point of the module. The engine's registry reseed
and its boot sweep are both key-driven, so a handler missing from the registry
works until the first reload and then silently stops forever. That failure used
to be guarded only by a comment.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.combat
"""

import io
import os
import re

from evennia.utils.test_resources import EvenniaTest, EvenniaTestCase

from systems.tick import tickable
from systems.combat.auras.aura_handler import BlackoutAuraHandler
from systems.combat.combat import BlackoutCombatHandler


# Public constant definitions

# Where to look for TickableHandler subclasses. Scanned as TEXT, never
# imported: CLAUDE.md records that bulk-importing modules under blackout/ once
# executed an operator script and deleted 347 rooms. A regex over the source
# cannot run anything.
_SOURCE_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")

# Directories that must never be walked, for the reason above.
_EXCLUDED_DIRS = frozenset({"scripts", "__pycache__"})

_SUBCLASS_PATTERN = re.compile(r"^class\s+(\w+)\s*\(\s*TickableHandler\s*\)", re.M)


def _declared_tickable_class_names() -> set:
    """Every class in the tree that declares TickableHandler as its base."""
    found = set()

    for dirpath, dirnames, filenames in os.walk(_SOURCE_ROOT):
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDED_DIRS]

        for filename in filenames:
            if not filename.endswith(".py"):
                continue

            path = os.path.join(dirpath, filename)
            source = io.open(path, encoding="utf-8", errors="replace").read()

            for match in _SUBCLASS_PATTERN.finditer(source):
                found.add(match.group(1))

    return found


class TestRegistryIsComplete(EvenniaTestCase):
    """The guard that replaces the old "must be added HERE" comment."""

    def test_every_declared_handler_is_registered(self):
        tickable.load_all_tickables()
        declared = _declared_tickable_class_names()
        registered = {cls.__name__ for cls in tickable.TICKABLE_REGISTRY.values()}

        missing = declared - registered

        self.assertEqual(
            missing,
            set(),
            msg=(
                f"{sorted(missing)} subclass TickableHandler but are not in "
                f"TICKABLE_REGISTRY. Decorate them with @register_tickable and "
                f"add their module to tickable._TICKABLE_MODULES, or the tick "
                f"engine will drive them until the first reload and then stop "
                f"forever."
            ),
        )

    def test_the_scan_finds_the_handlers_we_know_about(self):
        """Guards the test above: a scan that silently matched nothing would
        make the registry check vacuously pass."""
        declared = _declared_tickable_class_names()

        self.assertIn("BlackoutCombatHandler", declared)
        self.assertIn("BlackoutAuraHandler", declared)

    def test_the_engine_drives_every_registered_key(self):
        keys = tickable.tickable_keys()

        self.assertIn(BlackoutCombatHandler.HANDLER_KEY, keys)
        self.assertIn(BlackoutAuraHandler.HANDLER_KEY, keys)


class TestHandlerContract(EvenniaTestCase):
    """What a subclass must declare, and what the base guarantees."""

    def test_every_handler_declares_a_key_and_an_accessor(self):
        for key, handler_cls in tickable.TICKABLE_REGISTRY.items():
            self.assertTrue(handler_cls.HANDLER_KEY, msg=handler_cls.__name__)
            self.assertTrue(handler_cls.ACCESSOR_NAME, msg=handler_cls.__name__)
            self.assertEqual(handler_cls.HANDLER_KEY, key)

    def test_handler_keys_are_unique(self):
        keys = [cls.HANDLER_KEY for cls in tickable.TICKABLE_REGISTRY.values()]

        self.assertEqual(len(keys), len(set(keys)))

    def test_accessor_names_are_unique(self):
        """Two handlers sharing an accessor name would evict each other from
        the owner's lazy_property cache."""
        names = [cls.ACCESSOR_NAME for cls in tickable.TICKABLE_REGISTRY.values()]

        self.assertEqual(len(names), len(set(names)))

    def test_registering_without_a_key_is_refused(self):
        class _Keyless(tickable.TickableHandler):
            pass

        with self.assertRaises(ValueError):
            tickable.register_tickable(_Keyless)

    def test_the_base_refuses_to_be_ticked(self):
        """tick() is the one thing every subclass must implement; the base
        must not silently no-op, or a handler with a typo'd method name would
        sit in the rotation doing nothing."""
        handler = BlackoutCombatHandler()

        with self.assertRaises(NotImplementedError):
            tickable.TickableHandler.tick(handler)


class TestEnsureHandler(EvenniaTest):
    """The find-or-create dance both handlers used to implement separately."""

    def test_it_creates_a_handler_when_none_exists(self):
        handler = tickable.ensure_handler(self.char1, BlackoutCombatHandler)

        self.assertIsNotNone(handler)
        self.assertEqual(handler.key, BlackoutCombatHandler.HANDLER_KEY)

    def test_it_reuses_an_existing_handler(self):
        first = tickable.ensure_handler(self.char1, BlackoutCombatHandler)

        second = tickable.ensure_handler(self.char1, BlackoutCombatHandler)

        self.assertEqual(first.id, second.id)

    def test_the_new_handler_is_timerless(self):
        handler = tickable.ensure_handler(self.char1, BlackoutCombatHandler)

        self.assertEqual(handler.interval, tickable.HANDLER_NO_TIMER_INTERVAL)

    def test_the_new_handler_is_marked_running(self):
        """Evennia will not flag a timerless script active, so the handler
        owns its own liveness."""
        handler = tickable.ensure_handler(self.char1, BlackoutCombatHandler)

        self.assertTrue(handler.is_active)

    def test_it_clears_the_accessor_cache_on_reuse(self):
        """The drift between the two old copies: combat cleared the cache only
        when it created or discarded a handler, so a handler reused after a
        reload could leave a stale value behind."""
        tickable.ensure_handler(self.char1, BlackoutCombatHandler)
        self.char1.__dict__[BlackoutCombatHandler.ACCESSOR_NAME] = "stale"

        tickable.ensure_handler(self.char1, BlackoutCombatHandler)

        self.assertNotIn(
            BlackoutCombatHandler.ACCESSOR_NAME, self.char1.__dict__
        )

    def test_two_handler_classes_coexist_on_one_owner(self):
        combat = tickable.ensure_handler(self.char1, BlackoutCombatHandler)
        aura = tickable.ensure_handler(self.char1, BlackoutAuraHandler)

        self.assertNotEqual(combat.id, aura.id)
        self.assertIsNotNone(
            tickable.get_handler_for(self.char1, BlackoutCombatHandler)
        )
        self.assertIsNotNone(
            tickable.get_handler_for(self.char1, BlackoutAuraHandler)
        )

    def test_a_stopped_handler_does_not_read_as_live(self):
        handler = tickable.ensure_handler(self.char1, BlackoutCombatHandler)

        handler.stop()

        self.assertIsNone(
            tickable.get_handler_for(self.char1, BlackoutCombatHandler)
        )


class TestManagerRegistry(EvenniaTestCase):
    """The other hand-maintained dispatch list step 4 removed: three
    bootstrap_*() calls in server/conf/at_server_startstop.py, which had to be
    edited to add any global system and said nothing when it wasn't."""

    def test_every_known_manager_is_registered(self):
        from systems import managers

        managers.load_all_managers()
        names = set(managers.MANAGER_REGISTRY)

        self.assertIn("systems.tick.engine.bootstrap_tick", names)
        self.assertIn("systems.spawning.respawn.bootstrap_respawns", names)
        self.assertIn("systems.combat.hp_regen.bootstrap_regen", names)

    def test_bootstrap_all_starts_every_manager(self):
        from systems import managers

        started = managers.bootstrap_all()

        self.assertTrue(started)
        for name, manager in started.items():
            self.assertIsNotNone(manager, msg=f"{name} did not start")

    def test_bootstrap_all_is_idempotent(self):
        from systems import managers

        first = managers.bootstrap_all()
        second = managers.bootstrap_all()

        self.assertEqual(set(first), set(second))
        for name in first:
            self.assertEqual(first[name].id, second[name].id, msg=name)

    def test_one_failing_manager_does_not_stop_the_others(self):
        """A broken system must not stop the server coming up -- the same
        isolation the tick engine applies to handlers."""
        from unittest import mock

        from systems import managers

        managers.load_all_managers()
        broken = {"boom": mock.MagicMock(side_effect=RuntimeError("boom"))}
        patched = {**broken, **managers.MANAGER_REGISTRY}

        with mock.patch.dict(managers.MANAGER_REGISTRY, patched, clear=True):
            started = managers.bootstrap_all()

        self.assertIsNone(started["boom"])
        self.assertIsNotNone(started["systems.tick.engine.bootstrap_tick"])


class TestPurgeClearsAccessorCaches(EvenniaTest):
    """The boot sweep must not leave an owner holding a deleted handler.

    lazy_property caches into obj.__dict__ and its deleter raises, so the
    cache has to be popped explicitly -- and the accessor names come from the
    registry rather than being hard-coded, so a third tickable needs no edit
    to the engine.
    """

    def test_purging_clears_the_cached_handler(self):
        from systems.tick.engine import purge_stale_handlers

        tickable.ensure_handler(self.char1, BlackoutCombatHandler)
        self.char1.__dict__[BlackoutCombatHandler.ACCESSOR_NAME] = "stale"

        purged = purge_stale_handlers()

        self.assertGreaterEqual(purged, 1)
        self.assertNotIn(
            BlackoutCombatHandler.ACCESSOR_NAME, self.char1.__dict__
        )

    def test_purging_clears_every_registered_accessor(self):
        from systems.tick.engine import purge_stale_handlers

        tickable.ensure_handler(self.char1, BlackoutCombatHandler)
        tickable.ensure_handler(self.char1, BlackoutAuraHandler)
        for handler_cls in tickable.TICKABLE_REGISTRY.values():
            self.char1.__dict__[handler_cls.ACCESSOR_NAME] = "stale"

        purge_stale_handlers()

        for handler_cls in tickable.TICKABLE_REGISTRY.values():
            self.assertNotIn(
                handler_cls.ACCESSOR_NAME, self.char1.__dict__,
                msg=handler_cls.__name__,
            )
