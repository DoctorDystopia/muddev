"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 07/30/2026
Description: Evennia-backed tests for BlackoutRespawnManager and the
             HostileNPC death -> queue -> respawn cycle.

Run with the Evennia/Django test runner from the game dir:

    evennia test --settings settings.py systems.spawning

No test sleeps. `schedule()` and `sweep()` both take an injectable `now`, so
every timing case is a pure function of the timestamps it passes — strictly
better than patching time.time, which would leak into Django and twisted for
the duration of the patch.
"""

from unittest import mock

from evennia import create_object
from evennia.scripts.models import ScriptDB
from evennia.utils.dbserialize import dbserialize, dbunserialize
from evennia.utils.test_resources import EvenniaTest, EvenniaTestCase

from systems.spawning.respawn import (
    RESPAWN_MANAGER_KEY,
    RESPAWN_SWEEP_SECONDS,
    bootstrap_respawns,
    get_respawn_manager,
    npc_present,
    schedule_respawn,
)
from typeclasses.npc_combat import spawn_mutant_raider

RAIDER_KEY = "mutant_raider"


def _raiders_in(room):
    """Every object in `room` stamped as a mutant raider."""
    return [obj for obj in room.contents if obj.attributes.get("npc_key") == RAIDER_KEY]


class TestRespawnManagerWiring(EvenniaTestCase):
    """The global queue Script itself."""

    def test_manager_is_a_singleton(self):
        first = get_respawn_manager()
        second = get_respawn_manager()

        self.assertEqual(first.id, second.id)
        self.assertEqual(
            ScriptDB.objects.filter(db_key=RESPAWN_MANAGER_KEY).count(), 1
        )

    def test_sweep_interval_is_a_whole_number(self):
        """The sweep rides on Evennia's IntegerField, so it must be an int —
        a float would truncate and disable the timer entirely."""
        manager = get_respawn_manager()

        self.assertIsInstance(RESPAWN_SWEEP_SECONDS, int)
        self.assertGreater(RESPAWN_SWEEP_SECONDS, 0)
        self.assertEqual(manager.interval, RESPAWN_SWEEP_SECONDS)

    def test_manager_is_persistent(self):
        """A non-persistent manager would silently drop the queue on reload."""
        self.assertTrue(get_respawn_manager().persistent)

    def test_ensure_running_rearms_a_timerless_manager(self):
        """Simulates the hard-crash path: the server never got to pause the
        script, so it comes back is_active with no task and would never sweep
        again. Clearing ndb._task directly (rather than _stop_task, which also
        clears db_is_active) is what that state actually looks like."""
        manager = get_respawn_manager()
        manager.ndb._task = None

        manager._ensure_running()

        self.assertIsNotNone(manager.ndb._task)
        self.assertTrue(manager.ndb._task.running)


class TestQueuePersistence(EvenniaTest):
    """The queue has to survive a pickle round-trip with its room ref intact."""

    def test_entry_round_trips_through_dbserialize(self):
        schedule_respawn(RAIDER_KEY, self.room1, 30, now=1000.0)

        restored = dbunserialize(dbserialize(get_respawn_manager().db.respawn_queue))

        self.assertEqual(len(restored), 1)
        self.assertEqual(restored[0]["npc_key"], RAIDER_KEY)
        self.assertEqual(restored[0]["room"], self.room1)
        self.assertEqual(restored[0]["due_at"], 1030.0)

    def test_a_deleted_room_unpickles_to_none(self):
        """Pins the documented degradation — unpack_dbobj returns None rather
        than raising — so an Evennia upgrade that changes it is caught here
        instead of inside a live sweep."""
        doomed = create_object("typeclasses.rooms.Room", key="doomed room")
        schedule_respawn(RAIDER_KEY, doomed, 30, now=1000.0)
        blob = dbserialize(get_respawn_manager().db.respawn_queue)

        doomed.delete()

        self.assertIsNone(dbunserialize(blob)[0]["room"])


class TestScheduling(EvenniaTest):
    def test_schedule_stores_an_absolute_deadline(self):
        self.assertTrue(schedule_respawn(RAIDER_KEY, self.room1, 30, now=1000.0))

        queue = get_respawn_manager().db.respawn_queue
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["npc_key"], RAIDER_KEY)
        self.assertEqual(queue[0]["room"], self.room1)
        self.assertEqual(queue[0]["due_at"], 1030.0)

    def test_schedule_is_idempotent_per_key_and_room(self):
        schedule_respawn(RAIDER_KEY, self.room1, 30, now=1000.0)

        self.assertFalse(schedule_respawn(RAIDER_KEY, self.room1, 30, now=1000.0))
        self.assertEqual(len(get_respawn_manager().db.respawn_queue), 1)

    def test_schedule_rejects_a_missing_room(self):
        self.assertFalse(schedule_respawn(RAIDER_KEY, None, 30))
        self.assertEqual(get_respawn_manager().db.respawn_queue, [])

    def test_schedule_rejects_a_bad_delay(self):
        self.assertFalse(schedule_respawn(RAIDER_KEY, self.room1, "soon"))
        self.assertEqual(get_respawn_manager().db.respawn_queue, [])


class TestSweep(EvenniaTest):
    def test_entry_not_yet_due_is_left_alone(self):
        manager = get_respawn_manager()
        schedule_respawn(RAIDER_KEY, self.room1, 30, now=1000.0)

        self.assertEqual(manager.sweep(now=1029.0), 0)
        self.assertEqual(len(manager.db.respawn_queue), 1)
        self.assertEqual(_raiders_in(self.room1), [])

    def test_due_entry_spawns_and_leaves_the_queue(self):
        manager = get_respawn_manager()
        schedule_respawn(RAIDER_KEY, self.room1, 30, now=1000.0)

        self.assertEqual(manager.sweep(now=1030.0), 1)

        self.assertEqual(list(manager.db.respawn_queue), [])
        raiders = _raiders_in(self.room1)
        self.assertEqual(len(raiders), 1)
        self.assertEqual(raiders[0].db.hp, 5)

    def test_entry_due_during_downtime_spawns_on_the_first_sweep(self):
        """Absolute deadlines mean the world catches up after a restart."""
        manager = get_respawn_manager()
        schedule_respawn(RAIDER_KEY, self.room1, 30, now=0.0)

        self.assertEqual(manager.sweep(now=1e9), 1)
        self.assertEqual(len(_raiders_in(self.room1)), 1)

    def test_at_repeat_sweeps_using_the_wall_clock(self):
        """The timer path must reach the same code without waiting on a real
        interval — schedule far enough in the past that time.time() is due."""
        manager = get_respawn_manager()
        schedule_respawn(RAIDER_KEY, self.room1, 0, now=0.0)

        manager.at_repeat()

        self.assertEqual(len(_raiders_in(self.room1)), 1)
        self.assertEqual(list(manager.db.respawn_queue), [])

    def test_manager_will_not_double_spawn_into_an_occupied_room(self):
        """A grid rebuild during the dead window must not race the queue."""
        manager = get_respawn_manager()
        schedule_respawn(RAIDER_KEY, self.room1, 30, now=1000.0)
        spawn_mutant_raider(self.room1)

        self.assertEqual(manager.sweep(now=1030.0), 0)
        self.assertEqual(len(_raiders_in(self.room1)), 1)

    def test_unknown_npc_key_is_dropped_not_retried(self):
        manager = get_respawn_manager()
        manager.db.respawn_queue = [
            {"npc_key": "ghost", "room": self.room1, "due_at": 0.0}
        ]

        self.assertEqual(manager.sweep(now=1000.0), 0)
        self.assertEqual(list(manager.db.respawn_queue), [])

    def test_deleted_room_entry_is_dropped(self):
        manager = get_respawn_manager()
        doomed = create_object("typeclasses.rooms.Room", key="doomed room")
        schedule_respawn(RAIDER_KEY, doomed, 30, now=1000.0)
        doomed.delete()

        self.assertEqual(manager.sweep(now=1030.0), 0)
        self.assertEqual(list(manager.db.respawn_queue), [])

    def test_one_bad_entry_does_not_stop_the_sweep(self):
        """The malformed entry is queued FIRST, so a sweep that aborted on it
        would never reach the good one behind it."""
        manager = get_respawn_manager()
        manager.db.respawn_queue = [
            {"due_at": "oops"},
            {"npc_key": RAIDER_KEY, "room": self.room1, "due_at": 0.0},
        ]

        self.assertEqual(manager.sweep(now=1000.0), 1)
        self.assertEqual(len(_raiders_in(self.room1)), 1)
        self.assertEqual(list(manager.db.respawn_queue), [])


class TestHostileNpcDeathPath(EvenniaTest):
    def test_create_stamps_identity_and_spawn_room(self):
        from world.npc_database import NPC_DB

        npc = spawn_mutant_raider(self.room1)

        self.assertEqual(npc.db.npc_key, RAIDER_KEY)
        self.assertEqual(npc.db.spawn_room, self.room1)

        # That the def's value is STAMPED THROUGH, which is what this test is
        # named for -- not that the value is any particular number. It was `30`
        # and broke when the raider's respawn was retuned to 20 on 08/23/2026,
        # which told nobody anything except that a designer had changed their
        # mind.
        self.assertEqual(
            npc.db.respawn_seconds, NPC_DB[RAIDER_KEY].respawn_seconds)

    def test_raider_with_a_respawn_delay_enqueues_then_deletes(self):
        npc = spawn_mutant_raider(self.room1)

        npc.at_damage(99, attacker=self.char1)

        self.assertIsNone(npc.pk)
        queue = get_respawn_manager().db.respawn_queue
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["npc_key"], RAIDER_KEY)
        self.assertEqual(queue[0]["room"], self.room1)

    def test_raider_with_no_respawn_delay_still_just_despawns(self):
        """Locks the opt-in default: an NpcDef that says nothing keeps the
        historical permanent-despawn behavior."""
        npc = spawn_mutant_raider(self.room1)
        npc.db.respawn_seconds = None

        npc.at_damage(99, attacker=self.char1)

        self.assertIsNone(npc.pk)
        self.assertEqual(get_respawn_manager().db.respawn_queue, [])

    def test_death_deletes_even_if_the_queue_blows_up(self):
        """Skipping delete() would leave a 0-hp corpse in the room, so
        ActionAttack.resolve's `target.pk is None` guard never fires and the
        fight hangs — worse than losing one respawn."""
        npc = spawn_mutant_raider(self.room1)

        with mock.patch(
            "systems.spawning.respawn.schedule_respawn",
            side_effect=RuntimeError("boom"),
        ):
            npc.at_damage(99, attacker=self.char1)

        self.assertIsNone(npc.pk)

    def test_full_cycle_death_to_respawn(self):
        manager = get_respawn_manager()
        npc = spawn_mutant_raider(self.room1)
        old_id = npc.id

        npc.at_damage(99, attacker=self.char1)
        due_at = manager.db.respawn_queue[0]["due_at"]
        manager.sweep(now=due_at)

        raiders = _raiders_in(self.room1)
        self.assertEqual(len(raiders), 1)
        self.assertNotEqual(raiders[0].id, old_id)
        self.assertEqual(raiders[0].db.hp, 5)
        self.assertTrue(raiders[0].is_alive())


class TestSpawnerGuard(EvenniaTest):
    def test_spawner_does_not_stack_duplicates(self):
        """Regression: spawn_mutant_raider was the only spawner without a
        presence guard, so every `xyzgrid spawn` added another raider."""
        spawn_mutant_raider(self.room1)

        self.assertIsNone(spawn_mutant_raider(self.room1))
        self.assertEqual(len(_raiders_in(self.room1)), 1)

    def test_spawner_ignores_a_different_npc_key_in_the_room(self):
        """The guard keys on npc_key, not typeclass — a second hostile type
        sharing the tile must not suppress the raider."""
        other = create_object(
            "typeclasses.npc_combat.HostileNPC", key="Feral Dog", location=self.room1
        )
        other.db.npc_key = "feral_dog"

        self.assertIsNotNone(spawn_mutant_raider(self.room1))
        self.assertEqual(len(_raiders_in(self.room1)), 1)

    def test_unstamped_npc_never_matches_the_guard(self):
        self.assertFalse(npc_present(None, self.room1))


class TestBootstrap(EvenniaTest):
    def test_bootstrap_creates_and_starts_the_manager(self):
        manager = bootstrap_respawns()

        self.assertEqual(manager.key, RESPAWN_MANAGER_KEY)
        self.assertTrue(manager.is_active)
        self.assertEqual(
            ScriptDB.objects.filter(db_key=RESPAWN_MANAGER_KEY).count(), 1
        )

    def test_bootstrap_sweeps_overdue_entries(self):
        """Entries that came due while the server was down land at boot rather
        than up to RESPAWN_SWEEP_SECONDS later."""
        get_respawn_manager().db.respawn_queue = [
            {"npc_key": RAIDER_KEY, "room": self.room1, "due_at": 0.0}
        ]

        manager = bootstrap_respawns()

        self.assertEqual(len(_raiders_in(self.room1)), 1)
        self.assertEqual(list(manager.db.respawn_queue), [])
