"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/03/2026
Description: Tests for the aura handler's cadence, damage, XP and lifecycle.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.combat
"""

from evennia import create_object
from evennia.scripts.models import ScriptDB
from evennia.utils.test_resources import EvenniaTest

from systems.combat import constants as const
from systems.combat.auras.aura_handler import (
    AURA_HANDLER_KEY,
    ensure_aura_handler,
    get_aura_handler_for,
)
from systems.combat.auras.aura_defs.righteous_fire import RighteousFire
from systems.combat.auras.registry import AURA_REGISTRY, find_aura
from systems.tick.engine import get_tick_engine, purge_stale_handlers
from systems.progression.skills.constants import FORTITUDE_SKILL_KEY
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.npc_combat import HostileNPC


class TestAuraRegistry(EvenniaTest):
    """Auto-discovery and name resolution."""

    def test_righteous_fire_is_discovered(self):
        self.assertIn(RighteousFire.key, AURA_REGISTRY)

    def test_registry_holds_instances_not_classes(self):
        self.assertIsInstance(AURA_REGISTRY[RighteousFire.key], RighteousFire)

    def test_base_aura_is_not_registered(self):
        self.assertNotIn("base", AURA_REGISTRY)

    def test_find_aura_accepts_the_spaced_display_name(self):
        self.assertIs(find_aura("righteous fire"), AURA_REGISTRY["righteous_fire"])

    def test_find_aura_accepts_the_underscored_key(self):
        self.assertIs(find_aura("righteous_fire"), AURA_REGISTRY["righteous_fire"])

    def test_find_aura_rejects_an_unknown_name(self):
        self.assertIsNone(find_aura("nonexistent aura"))


class TestAuraDamageScaling(EvenniaTest):
    """Damage is a share of the CASTER's Fortitude, floored at AURA_MIN_DAMAGE."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.aura = AURA_REGISTRY["righteous_fire"]

    def _set_fortitude(self, level: int) -> None:
        self.char1.db.skills[FORTITUDE_SKILL_KEY] = {"level": level, "xp": 0}

    def test_damage_scales_with_fortitude(self):
        self._set_fortitude(100)

        expected = int(100 * self.aura.damage_pct)

        self.assertEqual(self.aura.damage_for(self.char1), expected)

    def test_low_fortitude_still_deals_the_floor(self):
        """Regression: a level-10 spawn times a 10% share truncates to 1.

        Any share below that would truncate to 0 and the aura would appear
        broken at exactly the levels a new character has.
        """
        self._set_fortitude(1)

        self.assertEqual(self.aura.damage_for(self.char1), const.AURA_MIN_DAMAGE)

    def test_damage_is_independent_of_target_health(self):
        self._set_fortitude(50)

        first = self.aura.damage_for(self.char1)
        self.char2.db.max_hp = 5
        second = self.aura.damage_for(self.char1)

        self.assertEqual(first, second)


class TestAuraExperience(EvenniaTest):
    """XP uses the same per-damage rate table as the melee swing path."""

    def setUp(self):
        super().setUp()
        self.aura = AURA_REGISTRY["righteous_fire"]

    def test_awards_fortitude_rate_per_damage(self):
        expected = int(round(const.XP_PER_DAMAGE_FORTITUDE * 9))

        self.assertEqual(self.aura.xp_for(9), expected)

    def test_zero_damage_awards_nothing(self):
        self.assertEqual(self.aura.xp_for(0), 0)


class TestAuraUnlock(EvenniaTest):
    """Righteous Fire is gated on the skill it scales with."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.aura = AURA_REGISTRY["righteous_fire"]

    def test_refused_below_the_unlock_level(self):
        self.char1.db.skills[FORTITUDE_SKILL_KEY] = {"level": 1, "xp": 0}

        allowed, reason = self.aura.can_activate(self.char1)

        self.assertFalse(allowed)
        self.assertIn(str(self.aura.unlock_level), reason)

    def test_allowed_at_the_unlock_level(self):
        self.char1.db.skills[FORTITUDE_SKILL_KEY] = {
            "level": self.aura.unlock_level,
            "xp": 0,
        }

        allowed, reason = self.aura.can_activate(self.char1)

        self.assertTrue(allowed)
        self.assertEqual(reason, "")


class TestAuraHandlerTick(EvenniaTest):
    """Cadence, burning, and the death path."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.aura = AURA_REGISTRY["righteous_fire"]

        self.char1.db.skills[FORTITUDE_SKILL_KEY] = {"level": 100, "xp": 0}

        self.handler = ensure_aura_handler(self.char1)
        self.handler.activate(self.aura)

        # A hostile standing in the caster's own room.
        self.char2.db.npc_key = "mutant_raider"
        self.char2.db.max_hp = 100
        self.char2.hp = 100

    def _tick_to_next_pulse(self) -> None:
        """Run ticks until exactly one damage pulse has landed.

        activate() seeds the counter at 0, so the very first tick pulses.
        """
        self.handler.tick()

    def test_burns_immediately_when_lit(self):
        """activate() seeds the counter at 0, so lighting the aura pulses at once."""
        self._tick_to_next_pulse()

        expected = self.aura.damage_for(self.char1)

        self.assertEqual(self.char2.hp, 100 - expected)

    def test_does_not_burn_again_before_the_cadence_elapses(self):
        self._tick_to_next_pulse()
        after_first = self.char2.hp

        for _ in range(self.aura.tick_interval - 1):
            self.handler.tick()

        self.assertEqual(self.char2.hp, after_first)

    def test_burns_again_exactly_one_interval_later(self):
        """Regression: assigning the full interval yields an interval+1 cadence.

        The same off-by-one the weapon-speed counter in the combat handler had
        to correct with `speed - 1`.
        """
        self._tick_to_next_pulse()
        expected = self.aura.damage_for(self.char1)

        for _ in range(self.aura.tick_interval):
            self.handler.tick()

        self.assertEqual(self.char2.hp, 100 - (2 * expected))

    def test_awards_experience_for_the_pulse(self):
        before = self.char1.skills.get_total_xp(FORTITUDE_SKILL_KEY)

        self._tick_to_next_pulse()

        after = self.char1.skills.get_total_xp(FORTITUDE_SKILL_KEY)

        self.assertGreater(after, before)

    def test_does_not_burn_a_player(self):
        del self.char2.db.npc_key

        self._tick_to_next_pulse()

        self.assertEqual(self.char2.hp, 100)

    def test_kill_deletes_the_npc_without_erroring(self):
        """at_damage -> at_death -> respawn() DELETES a HostileNPC's row.

        Must use a real HostileNPC, not a Character: Character.respawn restores
        HP to full, so it can never exercise the delete path this guards.

        Every message naming the target is built before the damage lands
        precisely so formatting cannot touch a deleted row. If that ordering is
        ever inverted, this is what catches it.
        """
        npc = create_object(
            HostileNPC,
            key="doomed_raider",
            location=self.char1.location,
        )
        npc.db.npc_key = "mutant_raider"
        npc.db.max_hp = 1
        npc.hp = 1

        self._tick_to_next_pulse()

        self.assertIsNone(npc.pk)

    def test_stops_when_the_caster_dies(self):
        self.char1.hp = 0

        self.handler.tick()

        self.assertIsNone(get_aura_handler_for(self.char1))


class TestAuraRingCache(EvenniaTest):
    """The radius is recomputed on movement, not on every tick."""

    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        self.aura = AURA_REGISTRY["righteous_fire"]
        self.handler = ensure_aura_handler(self.char1)
        self.handler.activate(self.aura)

    def test_ring_is_reused_while_standing_still(self):
        first = self.handler._current_ring(self.char1, self.aura)
        second = self.handler._current_ring(self.char1, self.aura)

        self.assertIs(first, second)

    def test_ring_is_rebuilt_after_moving(self):
        self.handler._current_ring(self.char1, self.aura)

        self.char1.location = self.room2
        rebuilt = self.handler._current_ring(self.char1, self.aura)

        self.assertEqual(self.handler.ndb.ring_origin_id, self.room2.id)
        self.assertIn(self.room2, rebuilt)


class TestAuraHandlerLifecycle(EvenniaTest):
    """Registration with the global tick engine, and the boot sweep."""

    character_typeclass = BlackoutCharacter

    def test_handler_joins_the_tick_rotation(self):
        handler = ensure_aura_handler(self.char1)

        self.assertIn(handler.id, get_tick_engine()._registry())

    def test_registry_reseed_after_reload_finds_aura_handlers(self):
        """Regression: the reseed is key-driven and once knew only combat's key.

        An aura handler missing from it would tick fine until the first reload
        and then silently stop forever.
        """
        handler = ensure_aura_handler(self.char1)

        engine = get_tick_engine()
        engine.ndb._handler_ids = None  # simulate the post-reload wipe

        self.assertIn(handler.id, engine._registry())

    def test_accessor_cache_is_cleared_when_reviving_a_stopped_handler(self):
        """Regression: the cache pop used to run only on the creation path.

        get_aura_handler_for is gated on is_active, so a stopped leftover
        cached None — and the map overlay, which reads `looker.aura`, would
        never see the aura the player had just lit.
        """
        handler = ensure_aura_handler(self.char1)
        handler.stop()

        self.char1.__dict__.pop("aura", None)
        self.assertIsNone(self.char1.aura)  # seeds the cache with None

        revived = ensure_aura_handler(self.char1)

        self.assertIs(self.char1.aura, revived)

    def test_stop_aura_removes_the_script(self):
        handler = ensure_aura_handler(self.char1)
        handler.stop_aura()

        self.assertIsNone(get_aura_handler_for(self.char1))

    def test_boot_sweep_purges_aura_handlers(self):
        ensure_aura_handler(self.char1)

        purge_stale_handlers()

        self.assertFalse(
            ScriptDB.objects.filter(db_key=AURA_HANDLER_KEY).exists()
        )
