"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/04/2026
Description: Tests for damage source/type attribution and self-inflicted death.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings settings.py systems.combat

Regression-shaped throughout: every case here corresponds to something that
went wrong, or would have, once a weapon could hurt its own wielder.
"""

from unittest import mock

from evennia.utils.ansi import strip_ansi
from evennia.utils.test_resources import EvenniaTest

from systems.combat import combat_msg
from systems.combat import constants as const
from systems.combat.auras.registry import AURA_REGISTRY
from systems.combat.combat import ensure_combat_handler
from systems.combat.rules.context import ActionResult
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.npc_combat import spawn_mutant_raider


# Private constant definitions

# Damage large enough to kill anything in these fixtures outright.
_LETHAL_DAMAGE = 9999

# A survivable amount for the tests that need the victim still standing.
_SMALL_DAMAGE = 1


class TestDamageChannelCompatibility(EvenniaTest):
    """The new keywords must not break the old two-argument call."""

    character_typeclass = BlackoutCharacter

    def test_at_damage_still_accepts_the_old_two_argument_call(self):
        target = spawn_mutant_raider(self.room1)
        before = target.hp

        dealt = target.at_damage(_SMALL_DAMAGE, attacker=self.char1)

        self.assertEqual(dealt, _SMALL_DAMAGE)
        self.assertEqual(target.hp, before - _SMALL_DAMAGE)

    def test_at_damage_accepts_a_source_and_a_damage_type(self):
        target = spawn_mutant_raider(self.room1)

        dealt = target.at_damage(
            _SMALL_DAMAGE,
            attacker=self.char1,
            source=None,
            damage_type=const.DAMAGE_TYPE_ENERGY,
        )

        self.assertEqual(dealt, _SMALL_DAMAGE)

    def test_a_negative_amount_is_still_clamped_to_zero(self):
        target = spawn_mutant_raider(self.room1)
        before = target.hp

        dealt = target.at_damage(-5, attacker=self.char1,
                                 damage_type=const.DAMAGE_TYPE_MELEE)

        self.assertEqual(dealt, 0)
        self.assertEqual(target.hp, before)


class TestMeleeAttribution(EvenniaTest):
    """A connecting swing must arrive at at_damage typed and sourced."""

    character_typeclass = BlackoutCharacter

    def _swing(self, result):
        handler = ensure_combat_handler(self.char1)
        target = spawn_mutant_raider(self.room1)
        ensure_combat_handler(target)
        handler.apply_action({"kind": "attack", "target": target})

        with mock.patch("systems.combat.combat.resolve_action",
                        return_value=result):
            with mock.patch.object(type(target), "at_damage") as mocked:
                handler.tick()

        return mocked

    def test_a_melee_hit_is_typed_as_melee(self):
        result = ActionResult(hit=True, damage=_SMALL_DAMAGE, hit_prob=1.0)

        mocked = self._swing(result)

        _args, kwargs = mocked.call_args
        self.assertEqual(kwargs["damage_type"], const.DAMAGE_TYPE_MELEE)

    def test_the_swings_damage_type_is_carried_through_verbatim(self):
        # A rules override that types its damage as energy must not be
        # relabelled melee on the way to at_damage.
        result = ActionResult(hit=True, damage=_SMALL_DAMAGE, hit_prob=1.0,
                             damage_type=const.DAMAGE_TYPE_ENERGY)

        mocked = self._swing(result)

        _args, kwargs = mocked.call_args
        self.assertEqual(kwargs["damage_type"], const.DAMAGE_TYPE_ENERGY)

    def test_an_unarmed_hit_reports_no_source(self):
        result = ActionResult(hit=True, damage=_SMALL_DAMAGE, hit_prob=1.0)

        mocked = self._swing(result)

        _args, kwargs = mocked.call_args
        self.assertIsNone(kwargs["source"])

    def test_the_attacker_is_still_named(self):
        result = ActionResult(hit=True, damage=_SMALL_DAMAGE, hit_prob=1.0)

        mocked = self._swing(result)

        _args, kwargs = mocked.call_args
        self.assertIs(kwargs["attacker"], self.char1)


class TestAuraAttribution(EvenniaTest):
    """An aura pulse must name itself, not masquerade as a weapon."""

    character_typeclass = BlackoutCharacter

    def test_the_burn_damage_type_lives_on_the_aura_class(self):
        # Per-aura data on the aura, not a literal in the handler, so a future
        # toxin aura stays a one-file change.
        aura = AURA_REGISTRY["righteous_fire"]

        self.assertEqual(aura.damage_type, const.DAMAGE_TYPE_BURN)

    def test_a_pulse_passes_the_aura_as_the_source(self):
        from systems.combat.auras.aura_handler import ensure_aura_handler

        aura = AURA_REGISTRY["righteous_fire"]
        target = spawn_mutant_raider(self.room1)
        handler = ensure_aura_handler(self.char1)
        handler.activate(aura)

        with mock.patch.object(type(target), "at_damage") as mocked:
            handler._apply_pulse(self.char1, aura, target, _SMALL_DAMAGE)

        _args, kwargs = mocked.call_args
        self.assertIs(kwargs["source"], aura)
        self.assertEqual(kwargs["damage_type"], const.DAMAGE_TYPE_BURN)


class TestSelfInflictedDeath(EvenniaTest):
    """A player killed by their own equipment is not their own killer."""

    character_typeclass = BlackoutCharacter

    def test_self_damage_does_not_credit_the_victim_with_the_kill(self):
        # Without the killer-is-self normalisation in at_death, the victim's
        # _award_killer_xp fires: they are paid for dying.
        with mock.patch.object(type(self.char1), "_award_killer_xp") as mocked:
            self.char1.at_damage(
                _LETHAL_DAMAGE,
                attacker=self.char1,
                damage_type=const.DAMAGE_TYPE_ENERGY,
            )

        mocked.assert_not_called()

    def test_self_damage_does_not_record_a_quest_kill(self):
        quests = mock.Mock()

        with mock.patch.object(type(self.char1), "quests", quests):
            self.char1.at_damage(
                _LETHAL_DAMAGE,
                attacker=self.char1,
                damage_type=const.DAMAGE_TYPE_ENERGY,
            )

        quests.update_progress.assert_not_called()

    def test_a_normal_kill_still_credits_the_attacker(self):
        # The guard against over-correcting: normalising a self-kill must not
        # switch off attribution for every other death.
        target = spawn_mutant_raider(self.room1)

        with mock.patch.object(type(target), "_award_killer_xp") as mocked:
            target.at_damage(
                _LETHAL_DAMAGE,
                attacker=self.char1,
                damage_type=const.DAMAGE_TYPE_MELEE,
            )

        mocked.assert_called_once()

    def test_a_backfire_death_line_blames_the_equipment(self):
        line = combat_msg.format_death(self.char1, None, self_inflicted=True)

        self.assertIn("own equipment", strip_ansi(line))

    def test_a_backfire_death_line_names_no_killer(self):
        line = strip_ansi(
            combat_msg.format_death(self.char1, self.char1, self_inflicted=True)
        )

        self.assertNotIn("killed by " + self.char1.key, line)

    def test_a_melee_death_line_is_unchanged(self):
        line = strip_ansi(
            combat_msg.format_death(self.char1, self.char2,
                                    damage_type=const.DAMAGE_TYPE_MELEE)
        )

        self.assertIn(f"killed by {self.char2.key}", line)

    def test_an_untyped_death_line_is_unchanged(self):
        line = strip_ansi(combat_msg.format_death(self.char1, self.char2))

        self.assertIn(f"killed by {self.char2.key}", line)


class TestBackfireSwing(EvenniaTest):
    """self_damage must reach the attacker, after the target's damage."""

    character_typeclass = BlackoutCharacter

    def _backfiring_swing(self, self_damage: int, damage: int = 0):
        handler = ensure_combat_handler(self.char1)
        target = spawn_mutant_raider(self.room1)
        ensure_combat_handler(target)
        handler.apply_action({"kind": "attack", "target": target})

        result = ActionResult(hit=True, damage=damage, self_damage=self_damage,
                             hit_prob=1.0,
                             damage_type=const.DAMAGE_TYPE_ENERGY)

        with mock.patch("systems.combat.combat.resolve_action",
                        return_value=result):
            with mock.patch.object(type(self.char1), "msg") as mocked_msg:
                handler.tick()

        return handler, mocked_msg

    def _sent_lines(self, mocked_msg) -> list:
        return [strip_ansi(str(call.args[0])) for call in mocked_msg.call_args_list
                if call.args]

    def test_self_damage_is_typed_by_the_rule_not_hard_coded(self):
        # Regression: the combat handler used to stomp every backfire to a
        # dedicated DAMAGE_TYPE_BACKFIRE regardless of what the rule set.
        # Self-damage must carry the SAME damage_type the rule gave the
        # result, exactly as a hit on a target would.
        handler = ensure_combat_handler(self.char1)
        target = spawn_mutant_raider(self.room1)
        ensure_combat_handler(target)
        handler.apply_action({"kind": "attack", "target": target})

        result = ActionResult(hit=True, damage=0, self_damage=2, hit_prob=1.0,
                             damage_type=const.DAMAGE_TYPE_ENERGY)

        with mock.patch("systems.combat.combat.resolve_action",
                        return_value=result):
            with mock.patch.object(type(self.char1), "at_damage") as mocked:
                handler.tick()

        _args, kwargs = mocked.call_args
        self.assertEqual(kwargs["damage_type"], const.DAMAGE_TYPE_ENERGY)

    def test_the_attacker_loses_hp_to_their_own_swing(self):
        before = self.char1.hp

        self._backfiring_swing(self_damage=2)

        self.assertEqual(self.char1.hp, before - 2)

    def test_the_attacker_is_told_their_equipment_backfired(self):
        _handler, mocked_msg = self._backfiring_swing(self_damage=2)

        lines = self._sent_lines(mocked_msg)

        self.assertTrue(any("backfires" in line for line in lines),
                        msg=f"no backfire line in {lines}")

    def test_a_backfire_is_not_reported_as_a_miss(self):
        # A swing that hurts its wielder and does nothing to the target is
        # not a miss, and printing "you miss" beside it reads as a bug.
        _handler, mocked_msg = self._backfiring_swing(self_damage=2)

        lines = self._sent_lines(mocked_msg)

        self.assertFalse(any("miss" in line.lower() for line in lines),
                         msg=f"unexpected miss line in {lines}")

    def test_a_zero_damage_swing_with_no_backfire_still_reports_a_miss(self):
        # The guard against over-correcting the test above.
        handler = ensure_combat_handler(self.char1)
        target = spawn_mutant_raider(self.room1)
        ensure_combat_handler(target)
        handler.apply_action({"kind": "attack", "target": target})
        result = ActionResult(hit=False, damage=0, hit_prob=0.0)

        with mock.patch("systems.combat.combat.resolve_action",
                        return_value=result):
            with mock.patch.object(type(self.char1), "msg") as mocked_msg:
                handler.tick()

        lines = self._sent_lines(mocked_msg)
        self.assertTrue(any("miss" in line.lower() for line in lines))

    def test_a_lethal_backfire_ends_combat_without_a_stale_handler(self):
        # at_death runs leave_combat, which deletes this very handler. Ending
        # combat again afterwards would log four swallowed errors per death.
        self.char1.hp = 1

        handler, _mocked_msg = self._backfiring_swing(self_damage=_LETHAL_DAMAGE)

        self.assertIsNone(handler.pk)

    def test_a_lethal_backfire_respawns_the_attacker(self):
        self.char1.hp = 1

        self._backfiring_swing(self_damage=_LETHAL_DAMAGE)

        self.assertTrue(self.char1.is_alive())
