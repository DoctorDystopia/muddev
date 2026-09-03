"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/08/2026
Description: Evennia-backed tests for BlackoutRegenManager and its wiring
             into CombatEntity.hp's setter.

Run with the Evennia/Django test runner from the game dir:

    evennia test --settings settings.py systems.combat
"""

from evennia.scripts.models import ScriptDB
from evennia.utils.test_resources import EvenniaTest, EvenniaTestCase

from systems.combat import constants as const
from systems.combat.combat import ensure_combat_handler
from systems.combat.hp_regen import (
    NO_EVENNIA_TIMER,
    REGEN_MANAGER_KEY,
    bootstrap_regen,
    get_regen_manager,
    register_for_regen,
)
from typeclasses.npc_combat import spawn_mutant_raider


class TestRegenManagerWiring(EvenniaTestCase):
    """The global sweep Script itself."""

    def test_manager_is_a_singleton(self):
        first = get_regen_manager()
        second = get_regen_manager()

        self.assertEqual(first.id, second.id)
        self.assertEqual(ScriptDB.objects.filter(db_key=REGEN_MANAGER_KEY).count(), 1)

    def test_the_manager_owns_no_evennia_timer(self):
        """The sweep runs on the tick scheduler; this Script exists only to
        hold the persistent registry."""
        manager = get_regen_manager()

        self.assertEqual(manager.interval, NO_EVENNIA_TIMER)

    def test_the_interval_is_a_whole_number_of_ticks(self):
        """60s at 0.6s is exactly 100 ticks, so nothing is quantised away."""
        self.assertIsInstance(const.HP_REGEN_INTERVAL_TICKS, int)
        self.assertGreater(const.HP_REGEN_INTERVAL_TICKS, 0)
        self.assertEqual(const.HP_REGEN_INTERVAL_TICKS, 100)

    def test_manager_is_persistent(self):
        """A non-persistent manager would silently drop the registry on reload."""
        self.assertTrue(get_regen_manager().persistent)

    def test_bootstrap_starts_the_manager(self):
        manager = bootstrap_regen()

        self.assertEqual(manager.key, REGEN_MANAGER_KEY)


class TestRegenIsScheduled(EvenniaTest):
    """Regen rides the tick now, not an Evennia timer."""

    def setUp(self):
        super().setUp()
        from systems.tick.engine import get_tick_engine

        self.engine = get_tick_engine()
        self.engine.ndb._handler_ids = {}
        self.engine.ndb._scheduler = None
        self.manager = get_regen_manager()
        self.manager.ndb._sweep_handle = None

        # Headroom above the wounds this class inflicts below --
        # FORTITUDE_START_LEVEL seeds a fresh character at 1 HP, which
        # leaves no room for "max_hp - 5" to stay positive.
        self.char1.db.max_hp = 10

    def test_bootstrap_books_a_sweep(self):
        """Load-bearing: the scheduler is ndb, so a sweep booked before a
        reload is gone and every user must re-arm itself at boot."""
        bootstrap_regen()

        self.assertIsNotNone(self.manager.ndb._sweep_handle)
        self.assertEqual(self.engine.scheduler().pending_count(), 1)

    def test_arming_twice_does_not_stack_two_sweeps(self):
        self.manager.arm()
        self.manager.arm()

        self.assertEqual(self.engine.scheduler().pending_count(), 1)

    def test_the_sweep_fires_on_its_tick(self):
        self.char1.hp = self.char1.max_hp - 5
        self.manager.arm()

        for _ in range(const.HP_REGEN_INTERVAL_TICKS):
            self.engine._tick()

        self.assertEqual(self.char1.hp, self.char1.max_hp - 4)

    def test_the_sweep_does_not_fire_early(self):
        self.char1.hp = self.char1.max_hp - 5
        self.manager.arm()

        for _ in range(const.HP_REGEN_INTERVAL_TICKS - 1):
            self.engine._tick()

        self.assertEqual(self.char1.hp, self.char1.max_hp - 5)

    def test_it_re_arms_itself_for_the_next_interval(self):
        self.manager.arm()

        for _ in range(const.HP_REGEN_INTERVAL_TICKS):
            self.engine._tick()

        self.assertEqual(self.engine.scheduler().pending_count(), 1)

    def test_a_raising_sweep_still_books_the_next_one(self):
        """The reason _on_due arms BEFORE sweeping. The scheduler contains a
        callback's exceptions, so a sweep that raised before re-arming would
        leave regen unscheduled forever with nothing to point at."""
        from unittest import mock

        self.manager.arm()

        with mock.patch.object(
            self.manager, "sweep", side_effect=RuntimeError("boom")
        ):
            for _ in range(const.HP_REGEN_INTERVAL_TICKS):
                self.engine._tick()

        self.assertEqual(self.engine.scheduler().pending_count(), 1)


class TestRegenRegistration(EvenniaTest):
    """register() / register_for_regen()."""

    def test_register_declines_full_hp_entity(self):
        manager = get_regen_manager()
        self.char1.db.hp = self.char1.db.max_hp

        added = register_for_regen(self.char1)

        self.assertFalse(added)
        self.assertNotIn(self.char1, manager.db.registry)

    def test_register_wounded_entity(self):
        manager = get_regen_manager()
        self.char1.db.hp = self.char1.db.max_hp - 1

        added = register_for_regen(self.char1)

        self.assertTrue(added)
        self.assertIn(self.char1, manager.db.registry)

    def test_register_is_idempotent(self):
        manager = get_regen_manager()
        self.char1.db.hp = self.char1.db.max_hp - 1

        register_for_regen(self.char1)
        register_for_regen(self.char1)

        self.assertEqual(manager.db.registry.count(self.char1), 1)


class TestRegenSweep(EvenniaTest):
    """sweep() -- the healing logic itself. Runs unconditionally: regen is
    not gated on being in combat, per the 08/08 design dialogue."""

    def setUp(self):
        super().setUp()

        # Headroom above the wounds this class inflicts below --
        # FORTITUDE_START_LEVEL seeds a fresh character at 1 HP, which
        # leaves no room for "max_hp - 3" to stay positive (a negative db.hp
        # reads as truthy-and-dead through the hp property, so sweep would
        # skip it as no longer alive instead of healing it).
        self.char1.db.max_hp = 10

    def test_sweep_heals_a_wounded_entity(self):
        manager = get_regen_manager()
        self.char1.db.hp = self.char1.db.max_hp - 3
        manager.register(self.char1)

        healed = manager.sweep()

        self.assertEqual(healed, 1)
        self.assertEqual(self.char1.db.hp, self.char1.db.max_hp - 3 + const.HP_REGEN_AMOUNT)

    def test_sweep_heals_an_in_combat_entity_too(self):
        """Regen must keep working mid-fight, not just once combat ends."""
        manager = get_regen_manager()
        self.char1.db.hp = self.char1.db.max_hp - 3
        ensure_combat_handler(self.char1)  # in_combat is derived from this
        manager.register(self.char1)

        healed = manager.sweep()

        self.assertEqual(healed, 1)
        self.assertEqual(self.char1.db.hp, self.char1.db.max_hp - 3 + const.HP_REGEN_AMOUNT)

    def test_sweep_drops_entity_once_fully_healed(self):
        manager = get_regen_manager()
        self.char1.db.hp = self.char1.db.max_hp - const.HP_REGEN_AMOUNT
        manager.register(self.char1)

        manager.sweep()

        self.assertEqual(self.char1.db.hp, self.char1.db.max_hp)
        self.assertNotIn(self.char1, manager.db.registry)

    def test_sweep_does_not_overheal_past_max(self):
        manager = get_regen_manager()
        self.char1.db.hp = self.char1.db.max_hp
        manager.db.registry = [self.char1]

        manager.sweep()

        self.assertEqual(self.char1.db.hp, self.char1.db.max_hp)

    def test_sweep_drops_a_deleted_entity_without_raising(self):
        """Mirrors test_respawn.py's proof that a deleted Object unpickles to
        None -- a puppeted test Character doesn't null its pk the same way on
        delete(), so this uses a plain NPC instead, exactly like respawn's own
        deleted-room test does."""
        manager = get_regen_manager()
        npc = spawn_mutant_raider(self.room1)
        npc.db.hp = npc.db.max_hp - 1
        manager.register(npc)

        npc.delete()
        healed = manager.sweep()  # must not raise

        self.assertEqual(healed, 0)
        self.assertEqual(list(manager.db.registry), [])


class TestRegenHpSetterIntegration(EvenniaTest):
    """CombatEntity.hp's setter is the single choke point every HP change
    passes through, so it is where regen registration actually happens."""

    def test_hp_setter_registers_a_wounded_entity(self):
        manager = get_regen_manager()

        self.char1.hp = self.char1.max_hp - 4

        self.assertIn(self.char1, manager.db.registry)

    def test_hp_setter_does_not_register_a_full_hp_entity(self):
        manager = get_regen_manager()

        self.char1.hp = self.char1.max_hp

        self.assertNotIn(self.char1, manager.db.registry)

    def test_hp_setter_registers_while_still_in_combat(self):
        """Registration must not depend on being out of combat -- regen
        runs ALL the time, mid-fight included."""
        manager = get_regen_manager()
        ensure_combat_handler(self.char1)  # in_combat is derived from this

        self.char1.hp = self.char1.max_hp - 1

        self.assertIn(self.char1, manager.db.registry)

    def test_at_damage_registers_the_victim(self):
        """at_damage routes through the hp setter, so a combat hit alone is
        enough to enter the regen registry -- no explicit registration call
        needed at the combat-handler layer."""
        manager = get_regen_manager()

        self.char1.at_damage(3)

        self.assertIn(self.char1, manager.db.registry)
