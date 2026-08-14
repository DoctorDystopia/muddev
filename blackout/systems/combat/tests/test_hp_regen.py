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
from evennia.utils.test_resources import EvenniaTest

from systems.combat import constants as const
from systems.combat.hp_regen import (
    REGEN_MANAGER_KEY,
    bootstrap_regen,
    get_regen_manager,
    register_for_regen,
)
from typeclasses.npc_combat import spawn_mutant_raider


class TestRegenManagerWiring(EvenniaTest):
    """The global sweep Script itself."""

    def test_manager_is_a_singleton(self):
        first = get_regen_manager()
        second = get_regen_manager()

        self.assertEqual(first.id, second.id)
        self.assertEqual(ScriptDB.objects.filter(db_key=REGEN_MANAGER_KEY).count(), 1)

    def test_sweep_interval_is_a_whole_number(self):
        """Rides on Evennia's IntegerField, so it must be an int -- a float
        would truncate and disable the timer entirely."""
        manager = get_regen_manager()

        self.assertIsInstance(const.HP_REGEN_INTERVAL_SECONDS, int)
        self.assertGreater(const.HP_REGEN_INTERVAL_SECONDS, 0)
        self.assertEqual(manager.interval, const.HP_REGEN_INTERVAL_SECONDS)

    def test_manager_is_persistent(self):
        """A non-persistent manager would silently drop the registry on reload."""
        self.assertTrue(get_regen_manager().persistent)

    def test_ensure_running_rearms_a_timerless_manager(self):
        """Simulates the hard-crash path: the server never got to pause the
        script, so it comes back is_active with no task and would never sweep
        again."""
        manager = get_regen_manager()
        manager.ndb._task = None

        manager._ensure_running()

        self.assertIsNotNone(manager.ndb._task)
        self.assertTrue(manager.ndb._task.running)

    def test_bootstrap_starts_the_manager(self):
        manager = bootstrap_regen()

        self.assertEqual(manager.key, REGEN_MANAGER_KEY)
        self.assertTrue(manager.is_active)


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
    not gated on db.in_combat, per the 08/08 design dialogue."""

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
        self.char1.db.in_combat = True
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
        """Registration must not depend on in_combat being False -- regen
        runs ALL the time, mid-fight included."""
        manager = get_regen_manager()
        self.char1.db.in_combat = True

        self.char1.hp = self.char1.max_hp - 1

        self.assertIn(self.char1, manager.db.registry)

    def test_at_damage_registers_the_victim(self):
        """at_damage routes through the hp setter, so a combat hit alone is
        enough to enter the regen registry -- no explicit registration call
        needed at the combat-handler layer."""
        manager = get_regen_manager()

        self.char1.at_damage(3)

        self.assertIn(self.char1, manager.db.registry)
