"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: Cases for the PvP flag and the rule that reads it.

             The rule has three readers: CmdAttack, the combat handler's
             queue-time check, and Character.extra_actions. Each reader is
             tested here against the one rule in pvp.py, so the three cannot
             disagree about who may attack whom.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.gameplay.combat.tests.test_pvp
"""

from unittest import mock

from evennia.utils.test_resources import EvenniaCommandTest, EvenniaTest

from commands.combat_cmds import CmdAttack, CmdPvp
from systems.gameplay.combat import constants as const
from systems.gameplay.combat import pvp
from systems.gameplay.combat.combat import ensure_combat_handler
from systems.interface.statefeed import constants as feed_const
from systems.interface.statefeed import events as feed
from systems.interface.statefeed import serializers
from typeclasses.characters import Character as BlackoutCharacter
from typeclasses.npc_combat import spawn_mutant_raider


# ─── Test cases ──────────────────────────────────────────────────────────────

class TestRule(EvenniaTest):
    """attack_refusal: the rule alone, with no command and no handler."""

    character_typeclass = BlackoutCharacter

    def test_the_flag_is_off_by_default(self):
        self.assertFalse(pvp.pvp_enabled(self.char1))

    def test_only_a_character_is_a_player(self):
        raider = spawn_mutant_raider(self.room1)

        self.assertTrue(pvp.is_player(self.char1))
        self.assertFalse(pvp.is_player(raider))
        self.assertFalse(pvp.is_player(self.obj1))
        self.assertFalse(pvp.is_player(None))

    def test_a_player_may_always_attack_an_npc(self):
        raider = spawn_mutant_raider(self.room1)

        self.assertEqual("", pvp.attack_refusal(self.char1, raider))

    def test_an_npc_may_always_attack_a_player(self):
        raider = spawn_mutant_raider(self.room1)

        self.assertEqual("", pvp.attack_refusal(raider, self.char1))

    def test_an_attacker_with_pvp_off_is_refused_first(self):
        pvp.set_pvp(self.char2, True)

        refusal = pvp.attack_refusal(self.char1, self.char2)

        self.assertEqual(const.PVP_ATTACKER_OFF_MSG, refusal)

    def test_a_target_with_pvp_off_is_refused(self):
        pvp.set_pvp(self.char1, True)

        refusal = pvp.attack_refusal(self.char1, self.char2)

        self.assertIn(self.char2.key, refusal)

    def test_two_players_with_pvp_on_may_fight(self):
        pvp.set_pvp(self.char1, True)
        pvp.set_pvp(self.char2, True)

        self.assertEqual("", pvp.attack_refusal(self.char1, self.char2))


class TestSetPvp(EvenniaTest):
    """set_pvp: the lock, and the sends that follow the flag."""

    character_typeclass = BlackoutCharacter

    def test_turning_it_on_moves_the_flag(self):
        changed, _message = pvp.set_pvp(self.char1, True)

        self.assertTrue(changed)
        self.assertTrue(pvp.pvp_enabled(self.char1))

    def test_asking_for_the_current_state_changes_nothing(self):
        changed, message = pvp.set_pvp(self.char1, False)

        self.assertFalse(changed)
        self.assertIn(const.PVP_STATE_OFF, message)

    def test_it_cannot_go_off_during_a_fight(self):
        pvp.set_pvp(self.char1, True)
        ensure_combat_handler(self.char1)

        changed, message = pvp.set_pvp(self.char1, False)

        self.assertFalse(changed)
        self.assertEqual(const.PVP_LOCKED_IN_COMBAT_MSG, message)
        self.assertTrue(pvp.pvp_enabled(self.char1))

    def test_it_can_go_on_during_a_fight(self):
        ensure_combat_handler(self.char1)

        changed, _message = pvp.set_pvp(self.char1, True)

        self.assertTrue(changed)

    def test_a_change_sends_the_tab_the_dossier_and_the_entity_row(self):
        """The row carries the Attack action, so observers need it again."""
        with mock.patch.object(feed, "emit_combat_options") as tab, \
                mock.patch.object(feed, "refresh_summary") as dossier, \
                mock.patch.object(feed, "emit_entity_arrived") as row:
            pvp.set_pvp(self.char1, True)

        tab.assert_called_with(self.char1)
        dossier.assert_called_with(self.char1)
        row.assert_called_with(self.char1.location, self.char1)

    def test_the_status_command_flips_the_flag(self):
        """The Combat tab sends status()["command"]. It must be the line
        that moves the flag to the other state."""
        command = pvp.status(self.char1)["command"]
        self.char1.execute_cmd(command)

        self.assertTrue(pvp.pvp_enabled(self.char1))
        self.assertTrue(pvp.status(self.char1)["enabled"])


class TestHandlerGate(EvenniaTest):
    """The queue-time check, which no caller of queue_action can skip."""

    character_typeclass = BlackoutCharacter

    def test_the_handler_refuses_an_attack_the_rule_refuses(self):
        handler = ensure_combat_handler(self.char1)

        handler.queue_action({"kind": "attack", "target": self.char2})

        # A refused attack never reaches start_combat_state, so the target
        # is never put into the fight.
        self.assertFalse(self.char2.in_combat)

    def test_the_handler_accepts_an_attack_the_rule_allows(self):
        pvp.set_pvp(self.char1, True)
        pvp.set_pvp(self.char2, True)
        handler = ensure_combat_handler(self.char1)

        handler.queue_action({"kind": "attack", "target": self.char2})

        self.assertTrue(self.char2.in_combat)


class TestEntityActions(EvenniaTest):
    """What a click on another player offers, as serialize_entity sends it."""

    character_typeclass = BlackoutCharacter

    def _commands(self) -> list:
        body = serializers.serialize_entity(self.char2)

        return [action["command"] for action in body.get("actions", [])]

    def _verbs(self) -> list:
        return [command.split(" ")[0] for command in self._commands()]

    def test_a_player_with_pvp_off_offers_no_attack(self):
        self.assertNotIn(CmdAttack.key, self._verbs())
        self.assertTrue(self._commands())

    def test_a_player_with_pvp_on_offers_attack_last(self):
        pvp.set_pvp(self.char2, True)

        self.assertEqual(CmdAttack.key, self._verbs()[-1])

    def test_attack_is_never_the_left_click(self):
        pvp.set_pvp(self.char2, True)
        body = serializers.serialize_entity(self.char2)

        self.assertNotEqual(CmdAttack.key, body["interact"].split(" ")[0])

    def test_every_command_names_the_player_by_dbref(self):
        dbref = feed_const.ENTITY_DBREF_TEMPLATE.format(dbref=self.char2.id)
        pvp.set_pvp(self.char2, True)

        for command in self._commands():
            with self.subTest(command=command):
                self.assertTrue(command.endswith(dbref))

    def test_no_command_walks_first(self):
        """Profile, Skills and Records reach anywhere, and attack walks for
        itself. A client wrap in `goto` would move the player for nothing."""
        pvp.set_pvp(self.char2, True)
        body = serializers.serialize_entity(self.char2)

        for action in body["actions"]:
            with self.subTest(command=action["command"]):
                self.assertFalse(action[feed_const.ENTITY_APPROACH_KEY])


class TestPvpCommand(EvenniaCommandTest):
    """`pvp` and the refusal `attack` gives a player."""

    character_typeclass = BlackoutCharacter

    def test_bare_pvp_reports_the_state(self):
        response = self.call(CmdPvp(), "")

        self.assertIn(const.PVP_STATE_OFF, response.lower())

    def test_pvp_on_and_off(self):
        self.call(CmdPvp(), const.PVP_ARG_ON)
        self.assertTrue(pvp.pvp_enabled(self.char1))

        self.call(CmdPvp(), const.PVP_ARG_OFF)
        self.assertFalse(pvp.pvp_enabled(self.char1))

    def test_attack_on_a_player_says_how_to_turn_pvp_on(self):
        response = self.call(CmdAttack(), self.char2.key)

        self.assertIn("pvp on", response.lower())
        self.assertFalse(self.char2.in_combat)
