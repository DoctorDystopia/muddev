"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 06/05/2026
Description: The gathering channel -- the roll, the cadence, what opens one
             and what ends one.

             A harvest was one command and one guaranteed item until
             09/20/2026. It is now a CHANNEL: the command commits the player
             to a node and a GatheringHandler on the global tick swings at it
             until something stops it. The tests below split along that seam.
             The roll is arithmetic and is tested as arithmetic, on a plain
             TestCase with no database at all. The channel is tested through
             the command that opens it. The swing is driven directly, with a
             scripted draw -- see tests/gathering_support.py for why.

             NO TEST HERE ASSERTS A BALANCE VALUE. Every expectation is read
             back out of GATHERABLE_REGISTRY, so retuning a chance, a level
             or a respawn is a content change and not a test edit. See
             CLAUDE.md, "Never assert a balance value".
"""



import time
import unittest

from evennia import create_object
from evennia.utils.test_resources import (
    EvenniaCommandTest,
    EvenniaTest,
    EvenniaTestCase,
)

from commands.gathering_cmds import CmdCutGatheringNode
from items.inventory.handler import SLOTS_TOTAL
from systems.gameplay.progression.skills.constants import SKILL_KEY_CUTTING
from systems.gameplay.progression.skills.gatherables import (
    GATHERABLE_REGISTRY,
    GatherChance,
    get_yield_item_name,
)
from systems.gameplay.progression.skills.handler import SkillHandler
from systems.gameplay.progression.skills.registry import SKILL_REGISTRY
from systems.gameplay.progression.skills.skill_defs.base_skill import (
    BaseSkill,
    COOLDOWN_KEY_PREFIX,
    NO_COOLDOWN,
)
from systems.gameplay.progression.skills.skill_defs.gathering import (
    constants as gather_constants,
    depletion,
    gather_handler,
    roll,
)
from systems.gameplay.progression.tests import gathering_support
from typeclasses.gathering_nodes import MetalPole, RustyPole
from typeclasses.objects import DefaultObject
from world.item_database import ITEM_DB


_RUSTY_POLE = "rusty_pole"
_METAL_POLE = "metal_pole"

# Enough hit points that a bare-handed harvest costs one rather than killing.
# Any number above the cost works; this one is far enough clear that a change
# to BARE_HAND_HP_COST does not quietly turn these tests into death tests.
_HEALTHY_HP = 20



def _pole_def():
    """The rusty pole's registry entry, read rather than restated."""
    return GATHERABLE_REGISTRY[_RUSTY_POLE]



# ─── The roll ───────────────────────────────────────────────────────────────

class GatherRollTest(unittest.TestCase):
    """The interpolation, with no database and no Evennia at all.

    Plain unittest.TestCase on purpose. The maths needs no fixtures, and
    EvenniaTest costs 138ms per method to build two accounts and two
    characters this never looks at. See CLAUDE.md, "Inherit the cheapest base
    class that works".
    """

    def test_level_zero_reads_the_low_end(self):
        chance = roll.success_chance(0, 40, 200)
        expected = 40 / gather_constants.CHANCE_DENOMINATOR

        self.assertAlmostEqual(chance, expected)


    def test_the_top_level_reads_the_high_end(self):
        top = gather_constants.CHANCE_TOP_LEVEL
        chance = roll.success_chance(top, 40, 200)
        expected = 200 / gather_constants.CHANCE_DENOMINATOR

        self.assertAlmostEqual(chance, expected)


    def test_a_level_above_the_ladder_is_clamped_not_extrapolated(self):
        """A rescale that has not reached the table is not a chance above 1.0."""
        top = gather_constants.CHANCE_TOP_LEVEL
        at_top = roll.success_chance(top, 40, 200)
        above = roll.success_chance(top * 2, 40, 200)

        self.assertEqual(above, at_top)


    def test_a_negative_level_is_clamped_too(self):
        at_zero = roll.success_chance(0, 40, 200)
        below = roll.success_chance(-50, 40, 200)

        self.assertEqual(below, at_zero)


    def test_the_chance_rises_with_the_level(self):
        top = gather_constants.CHANCE_TOP_LEVEL
        readings = [
            roll.success_chance(level, 40, 200)
            for level in range(0, top + 1, 8)
        ]

        for lower, higher in zip(readings, readings[1:]):
            with self.subTest(lower=lower, higher=higher):
                self.assertLess(lower, higher)


    def test_a_flat_pair_never_moves(self):
        """low == high is a chance the level does not touch."""
        top = gather_constants.CHANCE_TOP_LEVEL

        for level in (0, top // 2, top):
            with self.subTest(level=level):
                chance = roll.success_chance(level, 128, 128)
                expected = 128 / gather_constants.CHANCE_DENOMINATOR

                self.assertAlmostEqual(chance, expected)


    def test_a_zero_chance_can_never_succeed(self):
        """Strictly less than, so a draw of exactly 0.0 still fails."""
        draws = gathering_support.ScriptedRandom((0.0,))
        landed = roll.rolls_success(0.0, draws)

        self.assertFalse(landed)


    def test_a_certain_chance_always_succeeds(self):
        draws = gathering_support.ScriptedRandom((0.999999,))
        landed = roll.rolls_success(1.0, draws)

        self.assertTrue(landed)


    def test_a_node_that_cannot_deplete_never_does(self):
        draws = gathering_support.ScriptedRandom((0.0,))
        gave_out = roll.depletes(0.0, draws)

        self.assertFalse(gave_out)



class ChanceTableTest(unittest.TestCase):
    """The gap rule every node's chance table relies on."""

    def _table(self):
        return GATHERABLE_REGISTRY[_METAL_POLE]


    def test_a_declared_tier_reads_its_own_row(self):
        node = self._table()

        for entry in node.chances:
            with self.subTest(tier=entry.tool_tier):
                found = node.chance_for_tier(entry.tool_tier)

                self.assertEqual(found, entry)


    def test_a_tier_above_the_table_inherits_the_best_row(self):
        """A new axe tier must not need an edit to every node in the world."""
        node = self._table()
        highest = max(entry.tool_tier for entry in node.chances)
        best = node.chance_for_tier(highest)
        beyond = node.chance_for_tier(highest + 5)

        self.assertEqual(beyond, best)


    def test_a_tier_below_the_table_falls_to_the_lowest_row(self):
        """The level gate decides who may try. A forgotten tier is not a gate."""
        node = self._table()
        lowest = min(entry.tool_tier for entry in node.chances)
        floor = node.chance_for_tier(lowest)
        under = node.chance_for_tier(lowest - 5)

        self.assertEqual(under, floor)


    def test_no_tool_reads_the_bare_hand_row_and_never_a_tier(self):
        pole = _pole_def()
        bare = pole.chance_for_tier(None)

        self.assertIs(bare, pole.bare_hand_chance)
        self.assertNotIn(bare, pole.chances)


    def test_a_node_that_refuses_bare_hands_offers_no_bare_row(self):
        node = self._table()
        bare = node.chance_for_tier(None)

        self.assertFalse(node.bare_hands)
        self.assertIsNone(bare)


    def test_every_registered_node_can_answer_every_tool_it_allows(self):
        """A node nothing can roll on is a channel that swings forever."""
        for key, node in GATHERABLE_REGISTRY.items():
            with self.subTest(node=key):
                self.assertTrue(node.chances or node.bare_hand_chance)

                if node.bare_hands:
                    self.assertIsInstance(node.bare_hand_chance, GatherChance)



# ─── Opening a channel ──────────────────────────────────────────────────────

class GatheringChannelTest(EvenniaCommandTest):
    """What the command does now: it commits, and it produces nothing."""

    def setUp(self) -> None:
        super().setUp()

        self.handler = SkillHandler(self.char1)

        # The skill matches on db.tool_type, not on the object key.
        axe = create_object(DefaultObject, key="axe", location=self.char1)
        axe.db.tool_type = "axe"
        axe.db.tier = 1
        self.axe = axe

        self.pole = create_object(
            RustyPole, key="rusty pole", location=self.room1)
        self.char1.db.skills[SKILL_KEY_CUTTING] = {"level": 1, "xp": 0}


    def tearDown(self) -> None:
        gather_handler.stop_gathering(
            self.char1, gather_constants.STOP_REASON_ABANDONED)
        super().tearDown()


    def _cut(self, args=" rusty pole"):
        return self.call(
            CmdCutGatheringNode(),
            args,
            cmdstring="cut",
            caller=self.char1,
            obj=self.pole,
        )


    def test_the_verb_opens_a_channel_and_says_so(self):
        response = self._cut()

        self.assertIn("You start to cut", response)
        self.assertTrue(gathering_support.channel_is_open(self.char1))


    def test_the_verb_alone_produces_nothing(self):
        """The command commits. The SWING is what yields."""
        before = self.handler.get_total_xp(SKILL_KEY_CUTTING)

        self._cut()

        after = self.handler.get_total_xp(SKILL_KEY_CUTTING)

        self.assertEqual(before, after)


    def test_re_aiming_at_the_same_node_is_not_a_refusal(self):
        """Repeating a command is what a player does when unsure it took."""
        self._cut()
        second = self._cut()

        self.assertIn("already working", second)
        self.assertTrue(gathering_support.channel_is_open(self.char1))


    def test_naming_a_different_node_while_busy_is_refused(self):
        self._cut()

        other = create_object(
            RustyPole, key="second pole", location=self.room1)
        response = self.call(
            CmdCutGatheringNode(),
            " second pole",
            cmdstring="cut",
            caller=self.char1,
            obj=other,
        )

        self.assertIn("already busy", response)


    def test_the_channel_keeps_working_the_node_it_started_on(self):
        self._cut()

        handler = gather_handler.get_gathering_handler(self.char1)

        self.assertEqual(handler.ndb.node_id, self.pole.id)
        self.assertEqual(handler.ndb.skill_key, SKILL_KEY_CUTTING)


    def test_walking_away_stops_the_channel(self):
        """A node is a thing you stand at. See Character.at_post_move."""
        self._cut()

        self.char1.move_to(self.room2, quiet=True)

        self.assertFalse(gathering_support.channel_is_open(self.char1))


    def test_a_node_above_your_level_refuses_and_names_the_level(self):
        metal = create_object(MetalPole, key="metal pole", location=self.room1)
        required = GATHERABLE_REGISTRY[_METAL_POLE].yields[0].required_level

        self.char1.db.skills[SKILL_KEY_CUTTING] = {"level": 0, "xp": 0}

        response = self.call(
            CmdCutGatheringNode(),
            " metal pole",
            cmdstring="cut",
            caller=self.char1,
            obj=metal,
        )

        self.assertIn(f"Cutting level {required}", response)
        self.assertFalse(gathering_support.channel_is_open(self.char1))


    def test_a_refused_node_opens_no_channel(self):
        response = self.call(
            CmdCutGatheringNode(),
            " Obj",
            cmdstring="cut",
            caller=self.char1,
            obj=self.obj1,
        )

        self.assertIn("not something you can cut", response)
        self.assertFalse(gathering_support.channel_is_open(self.char1))



# ─── One swing ──────────────────────────────────────────────────────────────

class GatheringSwingTest(EvenniaTest):
    """What a swing does, with the draw written down."""

    def setUp(self) -> None:
        super().setUp()

        self.skill = SKILL_REGISTRY[SKILL_KEY_CUTTING]()
        self.handler = SkillHandler(self.char1)

        axe = create_object(DefaultObject, key="axe", location=self.char1)
        axe.db.tool_type = "axe"
        axe.db.tier = 1
        self.axe = axe

        self.pole = create_object(
            RustyPole, key="rusty pole", location=self.room1)
        self.char1.db.skills[SKILL_KEY_CUTTING] = {"level": 1, "xp": 0}


    def _swing(self, draws=gathering_support.DRAWS_YIELD_ONLY):
        return gathering_support.swing_once(
            self.char1, self.skill, self.pole, draws=draws)


    def test_a_swing_that_lands_yields_the_item_and_teaches(self):
        before = self.handler.get_total_xp(SKILL_KEY_CUTTING)
        response, stop = self._swing()
        after = self.handler.get_total_xp(SKILL_KEY_CUTTING)

        self.assertIn("You successfully cut", response)
        self.assertGreater(after, before)
        self.assertEqual(stop, "")


    def test_a_swing_that_misses_says_nothing_and_continues(self):
        """The OSRS rule. A silent miss is why the channel announces itself."""
        before = self.handler.get_total_xp(SKILL_KEY_CUTTING)
        response, stop = self._swing(draws=gathering_support.DRAWS_MISS)
        after = self.handler.get_total_xp(SKILL_KEY_CUTTING)

        self.assertEqual(response, "")
        self.assertEqual(stop, "")
        self.assertEqual(before, after)


    def test_the_yield_the_swing_gives_is_the_one_the_registry_names(self):
        expected = _pole_def().yields_for_skill(SKILL_KEY_CUTTING)[0]
        expected_name = get_yield_item_name(expected)

        self._swing()

        carried = [obj.key for obj in self.char1.contents]

        self.assertIn(expected_name, carried)


    def test_a_swing_that_depletes_ends_the_channel(self):
        _response, stop = self._swing(
            draws=gathering_support.DRAWS_YIELD_AND_DEPLETE)

        self.assertEqual(stop, gather_constants.STOP_REASON_DEPLETED)


    def test_depletion_marks_the_node_spent_for_the_harvester(self):
        self._swing(draws=gathering_support.DRAWS_YIELD_AND_DEPLETE)

        self.assertTrue(depletion.is_spent_for(self.pole, self.char1))


    def test_a_swing_that_did_not_deplete_leaves_the_node_whole(self):
        self._swing(draws=gathering_support.DRAWS_YIELD_ONLY)

        self.assertFalse(depletion.is_spent_for(self.pole, self.char1))


    def test_a_miss_can_never_deplete_a_node(self):
        """A tree falls because you took a log, never because you missed."""
        self._swing(draws=(gathering_support.DRAW_MISS,
                           gathering_support.DRAW_HIT))

        self.assertFalse(depletion.is_spent_for(self.pole, self.char1))


    def test_a_full_bag_stops_the_channel_and_keeps_the_swing_unpaid(self):
        before = self.handler.get_total_xp(SKILL_KEY_CUTTING)

        self._fill_the_bag()

        _response, stop = self._swing()
        after = self.handler.get_total_xp(SKILL_KEY_CUTTING)

        self.assertEqual(stop, gather_constants.STOP_REASON_BAG_FULL)
        self.assertEqual(before, after)


    def _fill_the_bag(self):
        """Occupy every inventory slot the character has.

        The filler is a REAL ItemDef, not a bare DefaultObject.
        Character.at_object_receive slots an incoming object only when it
        carries `is_stackable`, which the item typeclasses declare and
        DefaultObject does not -- so a bag "filled" with plain objects has
        every slot still free and the loop below never ends.

        It is also the node's own yield, and non-stackable, so each one takes
        a slot of its own and the bag this builds is exactly the bag the
        swing will be refused by.

        BOUNDED BY THE SLOT COUNT as well as by the free-slot check. A filler
        the inventory refuses for any reason leaves the count unchanged, and
        a plain `while there is room` loop then runs until the suite is
        killed rather than failing.
        """
        inventory = self.char1.inventory
        filler_key = _pole_def().yields_for_skill(SKILL_KEY_CUTTING)[0].item_key

        for _index in range(SLOTS_TOTAL):
            if not inventory.has_free_slots(1):
                break

            ITEM_DB[filler_key].create(location=self.char1, home=self.char1)

        self.assertFalse(inventory.has_free_slots(1))


    def test_a_better_tier_rolls_a_better_chance(self):
        """The one thing a tool changes. Read from the table, not asserted."""
        pole = _pole_def()
        level = 0
        readings = []

        for entry in sorted(pole.chances, key=lambda row: row.tool_tier):
            odds = roll.success_chance(level, entry.low, entry.high)

            readings.append(odds)

        for weaker, stronger in zip(readings, readings[1:]):
            with self.subTest(weaker=weaker, stronger=stronger):
                self.assertLess(weaker, stronger)



class BareHandedSwingTest(EvenniaTest):
    """The cost is paid on a harvest, never on an attempt."""

    def setUp(self) -> None:
        super().setUp()

        self.skill = SKILL_REGISTRY[SKILL_KEY_CUTTING]()
        self.pole = create_object(
            RustyPole, key="rusty pole", location=self.room1)
        self.char1.db.skills[SKILL_KEY_CUTTING] = {"level": 1, "xp": 0}

        # The fixture character starts on 1 hit point, so a bare-handed
        # harvest KILLS them and respawn restores the bar -- and the test
        # then reads a character back on full and concludes nothing was
        # charged. Given real health, the cost is a cost.
        self.char1.max_hp = _HEALTHY_HP
        self.char1.hp = _HEALTHY_HP


    def _swing(self, draws=gathering_support.DRAWS_YIELD_ONLY):
        return gathering_support.swing_once(
            self.char1, self.skill, self.pole, draws=draws)


    def test_a_bare_handed_harvest_costs_a_hitpoint(self):
        before = self.char1.hp

        self._swing()

        self.assertEqual(self.char1.hp, before - 1)


    def test_a_bare_handed_MISS_costs_nothing(self):
        """A cost per attempt at a one-in-six chance kills a new character."""
        before = self.char1.hp

        self._swing(draws=gathering_support.DRAWS_MISS)

        self.assertEqual(self.char1.hp, before)


    def test_the_pole_is_what_allows_bare_hands_at_all(self):
        """The exemption is a property of the node, not of the character."""
        self.assertTrue(_pole_def().bare_hands)
        self.assertFalse(GATHERABLE_REGISTRY[_METAL_POLE].bare_hands)



# ─── Per-player depletion ───────────────────────────────────────────────────

class DepletionTest(EvenniaTest):
    """Spent is a fact about a node AND a player, never about a node alone."""

    def setUp(self) -> None:
        super().setUp()

        self.pole = create_object(
            RustyPole, key="rusty pole", location=self.room1)


    def test_a_fresh_node_is_spent_for_nobody(self):
        self.assertFalse(depletion.is_spent_for(self.pole, self.char1))
        self.assertFalse(depletion.is_spent_for(self.pole, self.char2))


    def test_marking_it_spent_touches_one_player_only(self):
        depletion.mark_spent(self.pole, self.char1, 30)

        self.assertTrue(depletion.is_spent_for(self.pole, self.char1))
        self.assertFalse(depletion.is_spent_for(self.pole, self.char2))


    def test_an_expired_row_reads_as_whole_again(self):
        depletion.mark_spent(self.pole, self.char1, 30)

        rows = self.pole.attributes.get(gather_constants.SPENT_ATTRIBUTE)
        rows[self.char1.id] = time.time() - 1
        self.pole.attributes.add(gather_constants.SPENT_ATTRIBUTE, dict(rows))

        self.assertFalse(depletion.is_spent_for(self.pole, self.char1))


    def test_a_zero_timer_marks_nothing(self):
        """A node that cannot deplete reaching here is harmless, not an error."""
        expiry = depletion.mark_spent(self.pole, self.char1, 0)

        self.assertEqual(expiry, 0.0)
        self.assertFalse(depletion.is_spent_for(self.pole, self.char1))


    def test_spent_until_hands_back_a_time_in_the_future(self):
        before = time.time()
        expiry = depletion.mark_spent(self.pole, self.char1, 30)

        self.assertGreater(expiry, before)
        self.assertEqual(depletion.spent_until(self.pole, self.char1), expiry)


    def test_a_non_node_is_never_spent(self):
        """Every failed verb lands here first, and most targets are people."""
        self.assertFalse(depletion.is_spent_for(self.obj1, self.char1))
        self.assertFalse(depletion.is_spent_for(self.char2, self.char1))


    def test_a_spent_node_offers_that_player_no_verbs(self):
        whole = self.pole.extra_actions(observer=self.char1)

        depletion.mark_spent(self.pole, self.char1, 30)

        spent = self.pole.extra_actions(observer=self.char1)
        others = self.pole.extra_actions(observer=self.char2)

        self.assertTrue(whole)
        self.assertEqual(spent, [])
        self.assertEqual(others, whole)


    def test_no_observer_still_gets_the_whole_node(self):
        """Every broadcast path passes none, and a node arriving is whole."""
        depletion.mark_spent(self.pole, self.char1, 30)

        broadcast = self.pole.extra_actions()

        self.assertTrue(broadcast)



class SpentNodeSerializationTest(EvenniaTest):
    """The entity row is the first one that depends on who is reading it."""

    def setUp(self) -> None:
        super().setUp()

        self.pole = create_object(
            RustyPole, key="rusty pole", location=self.room1)


    def _row(self, observer):
        from systems.interface.statefeed import serializers

        return serializers.serialize_entity(self.pole, observer=observer)


    def test_a_whole_node_carries_no_spent_key(self):
        """Sent only when True, the rule every optional field follows."""
        from systems.interface.statefeed import constants as feed_const

        row = self._row(self.char1)

        self.assertNotIn(feed_const.ENTITY_SPENT_KEY, row)
        self.assertTrue(row["interact"])


    def test_a_spent_node_says_so_and_affords_nothing(self):
        from systems.interface.statefeed import constants as feed_const

        depletion.mark_spent(self.pole, self.char1, 30)

        row = self._row(self.char1)

        self.assertTrue(row[feed_const.ENTITY_SPENT_KEY])
        self.assertEqual(row["interact"], "")


    def test_the_player_beside_them_still_sees_a_whole_node(self):
        from systems.interface.statefeed import constants as feed_const

        depletion.mark_spent(self.pole, self.char1, 30)

        row = self._row(self.char2)

        self.assertNotIn(feed_const.ENTITY_SPENT_KEY, row)
        self.assertTrue(row["interact"])



# ─── The vocabulary the handler and the constants share ─────────────────────

class StopReasonTest(EvenniaTestCase):
    """A channel that ends and says nothing is the bug this table prevents."""

    def test_every_reason_has_a_line_or_an_exemption(self):
        for reason in gather_constants.STOP_REASONS:
            with self.subTest(reason=reason):
                spoken = gather_constants.STOP_MESSAGES.get(reason)
                quiet = reason in gather_constants.QUIET_STOP_REASONS

                self.assertTrue(spoken or quiet)


    def test_every_quiet_reason_is_a_real_reason(self):
        for reason in gather_constants.QUIET_STOP_REASONS:
            with self.subTest(reason=reason):
                self.assertIn(reason, gather_constants.STOP_REASONS)


    def test_the_swing_cadence_is_derived_from_the_tick(self):
        """One owner for the tick length. A second copy of 2.4 goes stale."""
        from systems.core.tick import constants as tick_constants

        expected = (gather_constants.SWING_TICKS
                    * tick_constants.TICK_SECONDS)

        self.assertAlmostEqual(gather_constants.SWING_SECONDS, expected)



# ─── The shared BaseSkill cooldown, which gathering no longer uses ──────────

class _CooldownSkill(BaseSkill):
    """A skill that declares a cooldown, for testing the shared helpers.

    Declared here rather than borrowed from the registry. Cutting used to be
    the stand-in and it declares NO_COOLDOWN now -- the channel's cadence
    replaced the per-skill timer -- so borrowing a real skill made this test
    a hostage to a gameplay decision it does not describe.
    """

    key = "test_cooldown_skill"
    name = "Test Cooldown Skill"
    cooldown_seconds = 30.0



class SkillCooldownKeyingTest(EvenniaTest):
    """The shared BaseSkill cooldown helpers, independent of any one skill."""

    def test_cooldown_keys_are_namespaced_per_skill(self):
        """The ndb timestamp this replaced was a single value shared by every
        gathering skill, so harvesting one node would have blocked every
        other gathering skill the moment a second one existed."""
        mine = _CooldownSkill()
        other_key = sorted(SKILL_REGISTRY)[0]
        other = SKILL_REGISTRY[other_key]()

        self.assertNotEqual(mine.cooldown_key(), other.cooldown_key())
        self.assertTrue(mine.cooldown_key().startswith(COOLDOWN_KEY_PREFIX))


    def test_arming_one_skill_leaves_another_ready(self):
        mine = _CooldownSkill()
        other_key = sorted(SKILL_REGISTRY)[0]
        other = SKILL_REGISTRY[other_key]()

        mine.arm_cooldown(self.char1)

        self.assertFalse(mine.is_off_cooldown(self.char1))
        self.assertTrue(other.is_off_cooldown(self.char1))


    def test_the_cooldown_is_stored_persistently_not_on_ndb(self):
        """The implementation this replaced kept the timestamp on ndb, so
        every @reload handed the player a free harvest."""
        mine = _CooldownSkill()

        mine.arm_cooldown(self.char1)

        stored = self.char1.attributes.get("cooldowns")

        self.assertIsNotNone(stored)
        self.assertIn(mine.cooldown_key(), stored)


    def test_a_cooldown_clears_once_reset(self):
        mine = _CooldownSkill()

        mine.arm_cooldown(self.char1)
        self.char1.cooldowns.reset(mine.cooldown_key())

        self.assertTrue(mine.is_off_cooldown(self.char1))


    def test_a_skill_without_a_cooldown_is_always_ready(self):
        """Most skills declare no cooldown and must never touch the handler."""
        plain = BaseSkill()

        self.assertEqual(plain.cooldown_seconds, NO_COOLDOWN)

        plain.arm_cooldown(self.char1)

        self.assertTrue(plain.is_off_cooldown(self.char1))
        self.assertEqual(self.char1.cooldowns.all, [])


    def test_a_gathering_skill_declares_no_cooldown_of_its_own(self):
        """The channel's cadence is the only clock a harvest has now."""
        cutting = SKILL_REGISTRY[SKILL_KEY_CUTTING]()

        self.assertEqual(cutting.cooldown_seconds, NO_COOLDOWN)
