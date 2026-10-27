"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/22/2026
Description: Fights with more than two combatants: two players on one NPC,
             and one player against two NPCs.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py systems.gameplay.combat.tests.test_multi_combat

The attack action of a combatant names ONE target. A fight can hold more.
Thus, the end of one target must not end the fight of a combatant that
another combatant still attacks. These tests pin that rule from both sides:
the NPC that kills one of two attackers, and the player that kills one of
two NPCs.

Every swing hits for 1, through a patched resolve_action, so a test picks
who dies with the HP of each side.
"""

from unittest import mock

from evennia.utils.test_resources import EvenniaTest

from systems.core.tick.engine import bootstrap_tick
from systems.gameplay.combat import constants as const
from systems.gameplay.combat.combat import ensure_combat_handler, get_handler_for
from systems.gameplay.combat.rules.context import ActionResult
from typeclasses.mixins import CombatEntity
from typeclasses.npc_spawners import spawn_npc
from world.item_database import ITEM_DB


# Enough HP that nobody dies by accident in a run of a few dozen ticks.
_TOUGH_HP = 500

# The ticks that one weapon cycle of each side needs, with room to spare.
_A_FEW_TICKS = 3

# Ticks past the grace, so that a fight that the grace kept alive has ended
# and a fight that an enemy keeps alive still runs.
_PAST_THE_GRACE = const.OUT_OF_REACH_GRACE_TICKS * 4


class _MultiCombatFixture(EvenniaTest):
    """One raider or two in room1, the two test characters, and a hit log.

    The log records each at_damage call as (attacker, target, amount),
    through one patch on the mixin, so that the hits of a player and the
    hits of an NPC land in one list.
    """

    def setUp(self):
        super().setUp()

        self.engine = bootstrap_tick()
        self.hits = []

        for char in (self.char1, self.char2):
            char.location = self.room1
            char.db.max_hp = _TOUGH_HP
            char.hp = _TOUGH_HP

        real_at_damage = CombatEntity.at_damage
        hits = self.hits

        def _logging_at_damage(entity, amount, attacker=None, **kwargs):
            hits.append((attacker, entity, amount))

            return real_at_damage(entity, amount, attacker=attacker, **kwargs)

        always_hits = ActionResult(hit=True, damage=1, hit_prob=1.0)
        respawn_room = self.room2

        def _respawn_in_room2(character):
            character.hp = character.max_hp
            character.move_to(respawn_room, quiet=True, move_type="teleport")

        patches = [
            mock.patch.object(CombatEntity, "at_damage", _logging_at_damage),
            mock.patch(
                "systems.gameplay.combat.combat.resolve_action",
                return_value=always_hits,
            ),
            # The respawn room of the real world. The test world has none,
            # and a player that wakes where it fell stays a target.
            mock.patch(
                "typeclasses.characters.Character.respawn", _respawn_in_room2
            ),
        ]

        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)

    def _spawn_raider(self):
        raider = spawn_npc("mutant_raider", self.room1)
        raider.db.max_hp = _TOUGH_HP
        raider.hp = _TOUGH_HP

        return raider

    def _attack(self, attacker, target):
        """What CmdAttack does: a handler for each side, an action for one."""
        ensure_combat_handler(target)
        handler = ensure_combat_handler(attacker)
        handler.queue_action({"kind": "attack", "target": target})

    def _run_ticks(self, count):
        for _ in range(count):
            self.engine._tick()

    def _hits_on(self, target, by=None):
        """The amounts that landed on `target`, by one attacker or by all."""
        return [
            amount
            for attacker, hit_target, amount in self.hits
            if hit_target is target and (by is None or attacker is by)
        ]


class TestTwoPlayersOnOneNpc(_MultiCombatFixture):
    """The NPC side: one raider, two attackers."""

    def setUp(self):
        super().setUp()

        self.raider = self._spawn_raider()

        # A slower weapon for char1, so the two cadences drift apart. The
        # raider answers char1 one tick after each hit, at the same speed.
        # With one speed on both, each hit of char1 fell one tick before
        # each swing of the raider, and the raider never left char1. That
        # is the rule at work, not a fault. The test needs a drift.
        axe = ITEM_DB["rusty_scrap_battleaxe"].create(location=self.char1)
        self.char1.equipment.equip(axe)

    def _char1_then_char2_attack(self):
        """char1 draws the raider first. char2 joins a few ticks later.

        The order matters. The raider answers the LAST attacker when it has
        no pending action, and the two first swings land on one tick. A
        later join makes char1 the target that the raider holds.
        """
        self._attack(self.char1, self.raider)
        self._run_ticks(_A_FEW_TICKS)

        self.assertTrue(
            self._hits_on(self.char1, by=self.raider),
            "the raider never turned on char1",
        )

        self._attack(self.char2, self.raider)
        self._run_ticks(_A_FEW_TICKS)

    def test_the_raider_fights_on_after_it_kills_one_attacker(self):
        """The defect: the raider that killed char1 stood still while char2
        went on hitting it, because the end of its target ended its fight."""
        self._char1_then_char2_attack()

        self.char1.hp = 1
        self._run_ticks(_PAST_THE_GRACE)

        self.assertIs(
            self.char1.location, self.room2, "char1 did not die and respawn"
        )
        self.assertIsNotNone(
            get_handler_for(self.raider), "the raider left the fight"
        )
        self.assertTrue(
            self._hits_on(self.char2, by=self.raider),
            "the raider never turned on char2 after the kill",
        )

    def test_the_raider_follows_its_last_attacker(self):
        """Nick's rule (10/22/2026): an NPC turns on whoever hit it last, as
        many times as the fight turns. The raider held char1 until that
        target died or left, whatever char2 did to it."""
        self._char1_then_char2_attack()
        self._run_ticks(_PAST_THE_GRACE)

        self.assertTrue(
            self._hits_on(self.char2, by=self.raider),
            "the raider never turned on char2",
        )

    def test_the_raider_turns_back_when_the_first_attacker_hits_again(self):
        """The second turn of the fight. char2 drew the raider. Then char2
        holds, char1 keeps hitting, and the raider comes back to char1."""
        self._char1_then_char2_attack()
        self._run_ticks(_PAST_THE_GRACE)

        self.assertTrue(self._hits_on(self.char2, by=self.raider))

        get_handler_for(self.char2).queue_action({"kind": "hold"})
        self._run_ticks(_A_FEW_TICKS)
        before = len(self._hits_on(self.char1, by=self.raider))
        self._run_ticks(_PAST_THE_GRACE)
        after = len(self._hits_on(self.char1, by=self.raider))

        self.assertGreater(after, before, "the raider never came back to char1")

    def test_the_raider_turns_on_the_attacker_that_stays(self):
        """char1 walks out of the fight. The raider turns on char2 instead of
        a hold at an empty tile."""
        self._char1_then_char2_attack()

        self.char1.move_to(self.room2, quiet=True, move_type="teleport")
        before = len(self._hits_on(self.char2, by=self.raider))
        self._run_ticks(_PAST_THE_GRACE)

        after = len(self._hits_on(self.char2, by=self.raider))

        self.assertGreater(after, before, "the raider never turned on char2")

    def test_the_second_attacker_still_fights_when_the_first_kills_it(self):
        """char1 lands the kill. char2's fight ends too, with no stale
        handler left in the rotation."""
        self._char1_then_char2_attack()

        self.raider.hp = 1
        self._run_ticks(_PAST_THE_GRACE)

        self.assertIsNone(get_handler_for(self.char1))
        self.assertIsNone(get_handler_for(self.char2))


class TestOnePlayerAgainstTwoNpcs(_MultiCombatFixture):
    """The player side: two raiders, one player that fights both."""

    def setUp(self):
        super().setUp()

        self.first = self._spawn_raider()
        self.second = self._spawn_raider_apart()

    def _spawn_raider_apart(self):
        """A second raider on the tile. spawn_npc keeps one NPC of a key for
        each tile, so this one comes from the def directly."""
        from world.npc_database import NPC_DB

        raider = NPC_DB["mutant_raider"].create(self.room1)
        raider.db.max_hp = _TOUGH_HP
        raider.hp = _TOUGH_HP

        return raider

    def _draw_both_raiders(self):
        """The player hits the first raider, then turns on the second. Both
        raiders answer, and both keep at the player."""
        self._attack(self.char1, self.first)
        self._run_ticks(_A_FEW_TICKS)
        self._attack(self.char1, self.second)
        self._run_ticks(_A_FEW_TICKS * 2)

        self.assertTrue(self._hits_on(self.char1, by=self.first))
        self.assertTrue(self._hits_on(self.char1, by=self.second))

    def test_the_player_stays_in_combat_while_the_other_raider_attacks(self):
        """The defect: the kill of the second raider ended the player's
        fight, while the first raider still hit the player. The player
        showed out of combat, and the first raider stopped after the grace."""
        self._draw_both_raiders()

        self.second.hp = 1
        self._run_ticks(_A_FEW_TICKS * 2)

        self.assertIsNone(self.second.pk, "the second raider did not die")

        before = len(self._hits_on(self.char1, by=self.first))
        self._run_ticks(_PAST_THE_GRACE)
        after = len(self._hits_on(self.char1, by=self.first))

        self.assertTrue(self.char1.in_combat, "the player read as out of combat")
        self.assertIsNotNone(get_handler_for(self.first), "the first raider stopped")
        self.assertGreaterEqual(
            after - before,
            3,
            "the first raider did not keep at the player past the grace",
        )

    def test_the_player_can_turn_on_the_other_raider_after_the_kill(self):
        self._draw_both_raiders()

        self.second.hp = 1
        self._run_ticks(_A_FEW_TICKS * 2)

        self._attack(self.char1, self.first)
        before = len(self._hits_on(self.first, by=self.char1))
        self._run_ticks(_A_FEW_TICKS * 2)
        after = len(self._hits_on(self.first, by=self.char1))

        self.assertGreater(after, before, "the player never hit the first raider")

    def test_the_player_draws_both_raiders_with_an_aura(self):
        """Nick's rule (10/22/2026): a pulse that burns a hostile starts
        its fight, as an arrow does. Both raiders answer the caster, and
        the caster never typed `attack`."""
        from systems.gameplay.combat.auras.aura_handler import ensure_aura_handler
        from systems.gameplay.combat.auras.registry import AURA_REGISTRY
        from systems.gameplay.progression.skills.constants import SKILL_KEY_FORTITUDE

        self.char1.db.skills[SKILL_KEY_FORTITUDE] = {"level": 100, "xp": 0}
        handler = ensure_aura_handler(self.char1)
        handler.activate(AURA_REGISTRY["righteous_fire"])

        self._run_ticks(_PAST_THE_GRACE)

        self.assertTrue(self._hits_on(self.char1, by=self.first), "the first raider never answered")
        self.assertTrue(self._hits_on(self.char1, by=self.second), "the second raider never answered")
        self.assertTrue(self.char1.in_combat)

    def test_a_solo_kill_still_ends_the_fight_at_once(self):
        """The rule must not keep a fight open with nobody in it. One raider,
        one kill, and the handler is gone on the tick of the kill."""
        self._attack(self.char1, self.first)
        self._run_ticks(_A_FEW_TICKS)

        self.first.hp = 1
        self.second.delete()

        for _ in range(_A_FEW_TICKS * 2):
            self.engine._tick()

            if self.first.pk is None:
                break

        self.assertIsNone(self.first.pk, "the raider did not die")
        self.assertIsNone(get_handler_for(self.char1), "the fight did not end")
