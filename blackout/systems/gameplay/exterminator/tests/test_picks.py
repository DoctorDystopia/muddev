"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/06/2026
Description: Tests for the pick milestones, the bank, the offer, rarity, the
             pick, and the cards on screen.

             The buffs and the Preceptor here live in this module. Each test
             puts them into the registries with mock.patch.dict. No test
             asserts a balance value. DESIGN-0012, Phase 4.
"""

import random
import unittest
from unittest import mock

from evennia.utils import create
from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.combat import constants as combat_const
from systems.gameplay.exterminator import constants as ext_const
from systems.gameplay.exterminator import offers
from systems.gameplay.exterminator.buff_defs.base_buff import BaseExterminatorBuff
from systems.gameplay.exterminator.buffs import BUFF_REGISTRY, instantiate
from systems.gameplay.exterminator.cards import card_lines, card_views
from systems.gameplay.exterminator.preceptors import (
    PRECEPTOR_DB,
    Assignment,
    PoolEntry,
    PreceptorDef,
)
from systems.interface.menus import exterminator_pick_menu
from systems.interface.popups import service as popup_service
from systems.interface.popups.popup_defs.exterminator import (
    CARDS_GRID_KEY,
    EXTERMINATOR_POPUP_KEY,
)
from systems.gameplay.exterminator import service as ext_service
from typeclasses.characters import Character as BlackoutCharacter
from world.npc_database import NPC_DB
from world import creature_types



# ─── Private constant definitions ────────────────────────────────────────────

_SEED: int = 5
_PRECEPTOR_KEY: str = "test_pick_preceptor"
_TASK_SIZE: int = 6          # big enough for three milestones on three kills
_TOY_SWORD_RULES: str = "toy_sword"
_PLAIN_TYPECLASS: str = "evennia.objects.objects.DefaultObject"
_QUIN_KEY: str = "atticus_quin"



# ─── Test buffs ─────────────────────────────────────────────────────────────

class _StrengthBuff(BaseExterminatorBuff):
    key = "test_strength_buff"
    name = "Test Strength"
    description = "More accuracy."
    strengths = {ext_const.RARITY_COMMON: 1, ext_const.RARITY_EPIC: 9}

    def contribute_modifiers(self, context, bag) -> None:
        holder = self.holder_of(context, bag)
        bag.add_flat_pre(context.accuracy_channel(), self.strength(holder))


class _OtherModifierBuff(BaseExterminatorBuff):
    key = "test_other_modifier_buff"
    name = "Test Other"
    description = "More defense."

    def contribute_modifiers(self, context, bag) -> None:
        bag.add_flat_pre(combat_const.CHANNEL_DEFENSE_LEVEL, 1)


class _RollBuff(BaseExterminatorBuff):
    key = "test_pick_roll_buff"
    name = "Test Roll"
    description = "A fixed damage roll."

    def roll_damage(self, context, result) -> None:
        result.damage = 1


class _SecondRollBuff(_RollBuff):
    key = "test_pick_second_roll_buff"
    name = "Test Second Roll"


_BUFF_CLASSES = (_StrengthBuff, _OtherModifierBuff, _RollBuff, _SecondRollBuff)
_TEST_BUFFS: dict = {cls.key: instantiate(cls) for cls in _BUFF_CLASSES}
_POOL: tuple = tuple(PoolEntry(cls.key, 1) for cls in _BUFF_CLASSES)

_TEST_PRECEPTOR = PreceptorDef(
    key=_PRECEPTOR_KEY,
    name="Test Preceptor",
    assignments=(Assignment(creature_types.CREATURE_TYPE_CRAB, 1, _TASK_SIZE, _TASK_SIZE),),
    base_points=0,
    buff_pool=_POOL,
)



# ─── Pure functions ─────────────────────────────────────────────────────────

class PicksDueTests(unittest.TestCase):

    def test_each_milestone_comes_due_by_the_integer_rule(self):
        count = ext_const.PICK_MILESTONE_COUNT

        for total in (1, 2, 3, 7, 30):
            for kills in range(total + 1):
                expected = sum(1 for i in range(count) if kills * count >= i * total)

                with self.subTest(total=total, kills=kills):
                    self.assertEqual(offers.picks_due(kills, total, count), expected)

    def test_a_new_task_has_one_pick(self):
        self.assertEqual(offers.picks_due(0, 30, ext_const.PICK_MILESTONE_COUNT), 1)

    def test_a_task_smaller_than_the_count_gives_every_pick_on_one_kill(self):
        count = ext_const.PICK_MILESTONE_COUNT

        self.assertEqual(offers.picks_due(1, 1, count), count)

    def test_the_count_never_drops_as_kills_rise(self):
        count = ext_const.PICK_MILESTONE_COUNT
        dues = [offers.picks_due(kills, 30, count) for kills in range(31)]

        self.assertEqual(dues, sorted(dues))



class DrawOfferTests(unittest.TestCase):

    def _draw(self, held=(), card_count=ext_const.CARDS_PER_OFFER, seed=_SEED):
        return offers.draw_offer(_POOL, held, card_count, _TEST_BUFFS, random.Random(seed))

    def _keys(self, cards) -> list:
        return [card[ext_const.CARD_KEY] for card in cards]

    def test_no_duplicate_and_no_more_than_the_card_count(self):
        for seed in range(20):
            keys = self._keys(self._draw(seed=seed))

            with self.subTest(seed=seed):
                self.assertEqual(len(keys), len(set(keys)))
                self.assertLessEqual(len(keys), ext_const.CARDS_PER_OFFER)

    def test_a_held_buff_never_shows(self):
        for seed in range(20):
            with self.subTest(seed=seed):
                self.assertNotIn(_StrengthBuff.key, self._keys(self._draw((_StrengthBuff.key,), seed=seed)))

    def test_a_buff_on_a_seam_of_a_held_buff_never_shows(self):
        for seed in range(20):
            keys = self._keys(self._draw((_RollBuff.key,), seed=seed))

            with self.subTest(seed=seed):
                self.assertNotIn(_SecondRollBuff.key, keys)

    def test_every_card_has_a_known_rarity(self):
        for card in self._draw():
            with self.subTest(card=card):
                self.assertIn(card[ext_const.CARD_RARITY], ext_const.RARITIES)

    def test_an_empty_pool_draws_nothing(self):
        cards = offers.draw_offer((), (), ext_const.CARDS_PER_OFFER, _TEST_BUFFS, random.Random(1))

        self.assertEqual(cards, [])

    def test_one_seed_draws_one_offer(self):
        self.assertEqual(self._draw(seed=3), self._draw(seed=3))



# ─── The handler, the cards, and the screens ────────────────────────────────

class _PickTest(EvenniaTest):
    character_typeclass = BlackoutCharacter

    def setUp(self):
        super().setUp()

        for patcher in (mock.patch.dict(BUFF_REGISTRY, _TEST_BUFFS),
                        mock.patch.dict(PRECEPTOR_DB, {_PRECEPTOR_KEY: _TEST_PRECEPTOR})):
            patcher.start()
            self.addCleanup(patcher.stop)

        self.handler = self.char1.exterminator
        self.rng = random.Random(_SEED)
        assigned, _message = self.handler.assign(_PRECEPTOR_KEY, rng=self.rng)
        self.assertTrue(assigned)

    def _kill(self, count: int = 1) -> None:
        for _kill in range(count):
            self.handler.record_kill((creature_types.CREATURE_TYPE_CRAB,), 0, rng=self.rng)



class BankTests(_PickTest):

    def test_a_new_task_banks_one_pick_and_opens_an_offer(self):
        self.assertEqual(self.handler.banked_picks(), 1)
        self.assertTrue(self.handler.offer())

    def test_kills_count_while_a_pick_waits(self):
        self._kill()

        self.assertEqual(self.handler.kills(), 1)

    def test_each_milestone_banks_one_more_pick(self):
        count = self.handler.pick_milestone_count()

        self._kill(_TASK_SIZE - 1)

        expected = offers.picks_due(_TASK_SIZE - 1, _TASK_SIZE, count)
        self.assertEqual(self.handler.banked_picks(), expected)

    def test_the_end_of_the_task_loses_the_banked_picks(self):
        self._kill(_TASK_SIZE)

        self.assertFalse(self.handler.has_task())
        self.assertEqual(self.handler.banked_picks(), 0)



class PickTests(_PickTest):

    def test_a_pick_grants_the_card_with_its_rarity(self):
        card = self.handler.offer()[0]

        picked, _message = self.handler.pick(1, rng=self.rng)

        self.assertTrue(picked)
        self.assertIn(card[ext_const.CARD_KEY], self.handler.held_buffs())
        self.assertEqual(self.handler.buff_rarity(card[ext_const.CARD_KEY]), card[ext_const.CARD_RARITY])

    def test_a_pick_uses_one_bank_entry_and_closes_the_offer(self):
        self.handler.pick(1, rng=self.rng)

        self.assertEqual(self.handler.banked_picks(), 0)
        self.assertEqual(self.handler.offer(), [])

    def test_a_second_waiting_pick_opens_the_next_offer(self):
        self._kill(_TASK_SIZE - 1)
        waiting = self.handler.banked_picks()
        self.assertGreater(waiting, 1)

        self.handler.pick(1, rng=self.rng)

        self.assertEqual(self.handler.banked_picks(), waiting - 1)
        self.assertTrue(self.handler.offer())

    def test_a_bad_card_number_is_refused(self):
        count = len(self.handler.offer())

        picked, _message = self.handler.pick(count + 1)

        self.assertFalse(picked)
        self.assertEqual(self.handler.banked_picks(), 1)

    def test_no_waiting_pick_is_refused(self):
        self.handler.pick(1, rng=self.rng)

        picked, _message = self.handler.pick(1)

        self.assertFalse(picked)



class RarityTests(_PickTest):

    def test_the_rarity_of_the_card_sets_the_strength(self):
        buff = _TEST_BUFFS[_StrengthBuff.key]

        for rarity, value in _StrengthBuff.strengths.items():
            self.char1.attributes.add(ext_const.TASK_ATTR, None)
            self.handler.assign(_PRECEPTOR_KEY, rng=self.rng)
            self.handler.grant_buff(_StrengthBuff.key, rarity)

            with self.subTest(rarity=rarity):
                self.assertEqual(buff.strength(self.char1), value)

    def test_a_rarity_with_no_row_uses_the_common_row(self):
        missing = next(r for r in ext_const.RARITIES if r not in _StrengthBuff.strengths)
        self.handler.grant_buff(_StrengthBuff.key, missing)

        strength = _TEST_BUFFS[_StrengthBuff.key].strength(self.char1)

        self.assertEqual(strength, _StrengthBuff.strengths[ext_const.RARITY_COMMON])



class CardScreenTests(_PickTest):

    def test_each_card_carries_its_pick_command(self):
        for view in card_views(self.char1):
            with self.subTest(card=view.buff_key):
                self.assertEqual(view.command, f"{ext_const.TASK_PICK_COMMAND} {view.number}")

    def test_the_text_names_each_card(self):
        text = "\n".join(card_lines(self.char1))

        for view in card_views(self.char1):
            with self.subTest(card=view.buff_key):
                self.assertIn(view.name, text)

    def test_a_roll_card_warns_about_the_toy_sword(self):
        item = create.create_object(_PLAIN_TYPECLASS, key=_TOY_SWORD_RULES, location=self.char1)
        item.attributes.add(combat_const.COMBAT_RULES_ATTR, [_TOY_SWORD_RULES])
        task = self.handler.task()
        task[ext_const.FIELD_OFFER] = [
            {ext_const.CARD_KEY: _RollBuff.key, ext_const.CARD_RARITY: ext_const.RARITY_COMMON}]
        self.char1.attributes.add(ext_const.TASK_ATTR, task)

        views = card_views(self.char1)

        self.assertTrue(views[0].warnings)
        self.assertIn(_TOY_SWORD_RULES, views[0].warnings[0])

    def test_the_popup_shows_the_cards_as_a_grid(self):
        quin = NPC_DB[_QUIN_KEY].create(location=self.room1)
        ext_service.give_writ(self.char1, quin)
        writ = ext_service.carried_writ(self.char1)
        popup_service.open_popup(self.char1, EXTERMINATOR_POPUP_KEY, writ)

        snapshot = popup_service.build_snapshot(self.char1)
        grids = {grid["key"]: grid for grid in snapshot["grids"]}
        commands = [row["actions"][0]["command"] for row in grids[CARDS_GRID_KEY]["items"]]

        self.assertEqual(commands, [view.command for view in card_views(self.char1)])

    def test_each_popup_card_names_its_rarity_key(self):
        """The client colours a card from this key, so it must be a real one."""
        quin = NPC_DB[_QUIN_KEY].create(location=self.room1)
        ext_service.give_writ(self.char1, quin)
        writ = ext_service.carried_writ(self.char1)
        popup_service.open_popup(self.char1, EXTERMINATOR_POPUP_KEY, writ)

        snapshot = popup_service.build_snapshot(self.char1)
        grids = {grid["key"]: grid for grid in snapshot["grids"]}
        offer = self.handler.offer()
        self.assertTrue(offer)

        for row, card in zip(grids[CARDS_GRID_KEY]["items"], offer):
            with self.subTest(slot=row["slot"]):
                self.assertIn(row["rarity"], ext_const.RARITIES)
                self.assertEqual(row["rarity"], card[ext_const.CARD_RARITY])

    def test_the_menu_offers_each_card(self):
        _text, options = exterminator_pick_menu.start(self.char1)
        card_count = len(card_views(self.char1))

        self.assertEqual(len(options), card_count + 1)
