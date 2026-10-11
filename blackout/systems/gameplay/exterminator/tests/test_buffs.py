"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: Tests for the buff framework: the target check, the collector
             in combat, the seam contest with a weapon, the conflict check,
             and the held buffs on the task.

             The buffs here live in this module, not under buff_defs/. Each
             test puts them into BUFF_REGISTRY with mock.patch.dict.
             DESIGN-0012, Phase 3.
"""

from unittest import mock

from evennia.utils import create
from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.combat import constants as combat_const
from systems.gameplay.combat.combat import ActionAttack, ensure_combat_handler
from systems.gameplay.combat.rules.pipeline import _resolve_winners, resolve_action
from systems.gameplay.combat.rules.registry import RULES_REGISTRY
from systems.gameplay.exterminator import constants as ext_const
from systems.gameplay.exterminator.buff_defs.base_buff import BaseExterminatorBuff
from systems.gameplay.exterminator.buffs import BUFF_REGISTRY, active_buffs, instantiate
from systems.gameplay.exterminator.conflicts import RIVAL_BUFF, RIVAL_ITEM, seam_conflicts
from systems.gameplay.exterminator.preceptors import PRECEPTOR_ATTICUS_QUIN
from typeclasses.characters import Character as BlackoutCharacter
from world import creature_types
from world.npc_database import NPC_DB



# ─── Private constant definitions ────────────────────────────────────────────

_MUTANT_CRAB_KEY: str = "mutant_crab"     # a mutant AND a crab
_FLOATING_EYE_KEY: str = "floating_eye"   # an eye, no other type

_TOY_SWORD_RULES: str = "toy_sword"       # owns roll_damage
_GLASS_CANNON_RULES: str = "glass_cannon_amulet"  # modifiers only

_TEST_BONUS: int = 10
_TEST_ROLL: int = 77

_PLAIN_TYPECLASS: str = "evennia.objects.objects.DefaultObject"



# ─── Test buffs ─────────────────────────────────────────────────────────────

class _AccuracyTestBuff(BaseExterminatorBuff):
    """A modifier buff: more accuracy level against the task type."""

    key = "test_accuracy_buff"
    name = "Test Accuracy"

    def contribute_modifiers(self, context, bag) -> None:
        bag.add_flat_pre(context.accuracy_channel(), _TEST_BONUS)


class _DefenseTestBuff(BaseExterminatorBuff):
    """A modifier buff: more defense level against the task type."""

    key = "test_defense_buff"
    name = "Test Defense"

    def contribute_modifiers(self, context, bag) -> None:
        bag.add_flat_pre(combat_const.CHANNEL_DEFENSE_LEVEL, _TEST_BONUS)


class _RollTestBuff(BaseExterminatorBuff):
    """A seam buff: the damage roll is always _TEST_ROLL."""

    key = "test_roll_buff"
    name = "Test Roll"

    def roll_damage(self, context, result) -> None:
        result.damage = _TEST_ROLL


class _SecondRollTestBuff(_RollTestBuff):
    """A second buff on the same seam, for the buff-against-buff check."""

    key = "test_second_roll_buff"
    name = "Test Second Roll"


_TEST_BUFFS: dict = {
    buff_class.key: instantiate(buff_class)
    for buff_class in (_AccuracyTestBuff, _DefenseTestBuff, _RollTestBuff, _SecondRollTestBuff)
}



def _task(creature_type: str, buffs=()) -> dict:
    """A task dict for a fixture, written straight to the Attribute."""
    return {
        ext_const.FIELD_PRECEPTOR: PRECEPTOR_ATTICUS_QUIN,
        ext_const.FIELD_CREATURE_TYPE: creature_type,
        ext_const.FIELD_TOTAL: 100,
        ext_const.FIELD_KILLS: 0,
        ext_const.FIELD_STARTED_AT: 0.0,
        ext_const.FIELD_BUFFS: [
            {ext_const.CARD_KEY: key, ext_const.CARD_RARITY: ext_const.RARITY_COMMON}
            for key in buffs
        ],
    }



class _BuffTest(EvenniaTest):
    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(BUFF_REGISTRY, _TEST_BUFFS)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.crab = NPC_DB[_MUTANT_CRAB_KEY].create(location=self.room1)
        self.eye = NPC_DB[_FLOATING_EYE_KEY].create(location=self.room1)

    def _give_task(self, creature_type: str, *buff_keys) -> None:
        self.char1.attributes.add(ext_const.TASK_ATTR, _task(creature_type, buff_keys))

    def _context(self, attacker, target):
        """A real context, from the collector that combat uses."""
        handler = ensure_combat_handler(attacker)

        return ActionAttack(target.id)._build_context(handler, attacker, target)



class TargetCheckTests(_BuffTest):

    def _applies(self, opponent) -> bool:
        return _TEST_BUFFS[_AccuracyTestBuff.key].applies_to(self.char1, opponent)

    def test_the_mutant_crab_matches_a_mutant_task_and_a_crab_task(self):
        for type_key in (creature_types.CREATURE_TYPE_MUTANT, creature_types.CREATURE_TYPE_CRAB):
            self._give_task(type_key)

            with self.subTest(task=type_key):
                self.assertTrue(self._applies(self.crab))

    def test_another_type_does_not_match(self):
        self._give_task(creature_types.CREATURE_TYPE_CRAB)

        self.assertFalse(self._applies(self.eye))

    def test_no_task_matches_nothing(self):
        self.assertFalse(self._applies(self.crab))

    def test_an_npc_holder_matches_nothing(self):
        self.assertFalse(_TEST_BUFFS[_AccuracyTestBuff.key].applies_to(self.crab, self.char1))
        self.assertEqual(active_buffs(self.crab, self.char1), ())



class CollectorTests(_BuffTest):

    def test_a_modifier_buff_works_against_the_task_type(self):
        self._give_task(creature_types.CREATURE_TYPE_CRAB, _AccuracyTestBuff.key)
        context = self._context(self.char1, self.crab)

        resolve_action(context)

        self.assertIn(_TEST_BUFFS[_AccuracyTestBuff.key], context.attacker_rules)
        self.assertIn(context.accuracy_channel(), context.attacker_bag.touched_channels())

    def test_a_modifier_buff_does_nothing_against_another_type(self):
        self._give_task(creature_types.CREATURE_TYPE_CRAB, _AccuracyTestBuff.key)
        context = self._context(self.char1, self.eye)

        resolve_action(context)

        self.assertNotIn(_TEST_BUFFS[_AccuracyTestBuff.key], context.attacker_rules)
        self.assertNotIn(context.accuracy_channel(), context.attacker_bag.touched_channels())

    def test_a_defense_buff_on_the_defender_tests_the_attacker(self):
        self._give_task(creature_types.CREATURE_TYPE_CRAB, _DefenseTestBuff.key)
        buff = _TEST_BUFFS[_DefenseTestBuff.key]

        crab_attacks = self._context(self.crab, self.char1)
        eye_attacks = self._context(self.eye, self.char1)

        self.assertIn(buff, crab_attacks.defender_rules)
        self.assertNotIn(buff, eye_attacks.defender_rules)

    def test_a_buff_never_enters_the_equipment_cache(self):
        self._give_task(creature_types.CREATURE_TYPE_CRAB, _AccuracyTestBuff.key)
        handler = ensure_combat_handler(self.char1)

        self._context(self.char1, self.crab)

        self.assertNotIn(_TEST_BUFFS[_AccuracyTestBuff.key], handler.active_rules())



class SeamContestTests(_BuffTest):
    """The toy sword owns roll_damage. A roll buff takes it only against the task type."""

    def _context_with_sword(self, target):
        handler = ensure_combat_handler(self.char1)
        sword = (RULES_REGISTRY[_TOY_SWORD_RULES],)

        with mock.patch.object(handler, "active_rules", return_value=sword):
            return self._context(self.char1, target)

    def test_the_buff_wins_against_a_task_creature(self):
        self._give_task(creature_types.CREATURE_TYPE_CRAB, _RollTestBuff.key)
        context = self._context_with_sword(self.crab)

        owner = _resolve_winners(context.attacker_rules).owner("roll_damage")

        self.assertIs(owner, _TEST_BUFFS[_RollTestBuff.key])

    def test_the_sword_wins_against_any_other_target(self):
        self._give_task(creature_types.CREATURE_TYPE_CRAB, _RollTestBuff.key)
        context = self._context_with_sword(self.eye)

        owner = _resolve_winners(context.attacker_rules).owner("roll_damage")

        self.assertIs(owner, RULES_REGISTRY[_TOY_SWORD_RULES])



class ConflictTests(_BuffTest):

    def _carry_rules(self, rules_key: str):
        item = create.create_object(_PLAIN_TYPECLASS, key=rules_key, location=self.char1)
        item.attributes.add(combat_const.COMBAT_RULES_ATTR, [rules_key])

        return item

    def test_a_roll_buff_names_the_toy_sword(self):
        self._carry_rules(_TOY_SWORD_RULES)
        buff = _TEST_BUFFS[_RollTestBuff.key]

        conflicts = seam_conflicts(buff, self.char1)

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].rival_kind, RIVAL_ITEM)
        self.assertEqual(conflicts[0].rival_rules_key, _TOY_SWORD_RULES)
        self.assertEqual(conflicts[0].buff_wins, buff.priority >= RULES_REGISTRY[_TOY_SWORD_RULES].priority)

    def test_a_modifier_buff_names_nothing(self):
        self._carry_rules(_TOY_SWORD_RULES)
        self._carry_rules(_GLASS_CANNON_RULES)

        conflicts = seam_conflicts(_TEST_BUFFS[_AccuracyTestBuff.key], self.char1)

        self.assertEqual(conflicts, [])

    def test_a_roll_buff_names_a_held_roll_buff(self):
        self._give_task(creature_types.CREATURE_TYPE_CRAB, _SecondRollTestBuff.key)

        conflicts = seam_conflicts(_TEST_BUFFS[_RollTestBuff.key], self.char1)

        self.assertEqual([c.rival_kind for c in conflicts], [RIVAL_BUFF])



class HeldBuffTests(_BuffTest):

    def setUp(self):
        super().setUp()
        self._give_task(creature_types.CREATURE_TYPE_CRAB)
        self.handler = self.char1.exterminator

    def test_a_granted_buff_is_held(self):
        granted, _message = self.handler.grant_buff(_AccuracyTestBuff.key)

        self.assertTrue(granted)
        self.assertEqual(self.handler.held_buffs(), (_AccuracyTestBuff.key,))

    def test_a_buff_is_held_once(self):
        self.handler.grant_buff(_AccuracyTestBuff.key)
        granted, _message = self.handler.grant_buff(_AccuracyTestBuff.key)

        self.assertFalse(granted)
        self.assertEqual(len(self.handler.held_buffs()), 1)

    def test_an_unknown_buff_is_refused(self):
        granted, _message = self.handler.grant_buff("no_such_buff")

        self.assertFalse(granted)

    def test_no_task_holds_no_buff(self):
        self.char1.attributes.add(ext_const.TASK_ATTR, None)

        granted, _message = self.handler.grant_buff(_AccuracyTestBuff.key)

        self.assertFalse(granted)
        self.assertEqual(self.handler.held_buffs(), ())

    def test_the_buffs_end_with_the_task(self):
        self.handler.grant_buff(_AccuracyTestBuff.key)
        self.char1.attributes.add(ext_const.POINTS_ATTR, ext_const.SKIP_COST_POINTS)

        self.handler.skip()

        self.assertEqual(self.handler.held_buffs(), ())
