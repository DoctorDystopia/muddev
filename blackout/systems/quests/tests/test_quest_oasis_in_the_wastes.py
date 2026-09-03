"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: "Oasis in the Wastes" end to end -- the blueprint, the android's
             dialogue, the bare-handed bootstrap, and one full playthrough
             driven through the real progression hooks.
"""

from unittest import mock

from evennia import create_object
from evennia.utils.test_resources import EvenniaTest

from systems.menus.npc_dialogues import npc_oasis_lone_android as guide
from systems.quests.content import quest_oasis_in_the_wastes
from systems.quests.loader import GLOBAL_QUEST_REGISTRY
from typeclasses.spawners import SPAWNER_REGISTRY
from world.npc_database import NPC_DB



# Private constant definitions
_QUEST_KEY = quest_oasis_in_the_wastes.QUEST_KEY
_RUSTY_POLE = "typeclasses.gathering_nodes.RustyPole"
_METAL_POLE = "typeclasses.gathering_nodes.MetalPole"



class OasisBlueprintTests(EvenniaTest):
    """The shipped blueprint, as the rest of the game sees it."""

    def setUp(self):
        super().setUp()
        self.blueprint = GLOBAL_QUEST_REGISTRY.get(_QUEST_KEY)


    def test_the_quest_is_registered_and_named(self):
        self.assertIsNotNone(self.blueprint)
        self.assertEqual(self.blueprint.title, "Oasis in the Wastes")


    def test_it_has_the_five_designed_steps_in_order(self):
        self.assertEqual(
            self.blueprint.step_keys,
            [
                quest_oasis_in_the_wastes.STEP_INTRO,
                quest_oasis_in_the_wastes.STEP_MAINTENANCE,
                quest_oasis_in_the_wastes.STEP_APPRENTICESHIP,
                quest_oasis_in_the_wastes.STEP_DEFENSE,
                quest_oasis_in_the_wastes.STEP_RESOLUTION,
            ],
        )


    def test_the_craft_step_gates_on_two_level_zero_recipes(self):
        """
        Both must be reachable by a character who arrived with nothing.

        The vault doc says "Rusty Scrap Axe and Sword", but the shortsword is
        metalsmith level 4 and costs two scrap. A level-0 starter cannot make
        it, so the dagger stands in.
        """
        from systems.crafting.registry import RECIPE_REGISTRY

        index = self.blueprint.step_index_of(quest_oasis_in_the_wastes.STEP_APPRENTICESHIP)
        step = self.blueprint.steps[index]

        for recipe_name in (quest_oasis_in_the_wastes.RECIPE_AXE, quest_oasis_in_the_wastes.RECIPE_DAGGER):
            with self.subTest(recipe=recipe_name):
                self.assertIn(f"craft:{recipe_name}", step.targets)

                recipe = RECIPE_REGISTRY[recipe_name]
                self.assertEqual(recipe.required_level, 0)


    def test_the_defense_step_names_a_real_hostile(self):
        index = self.blueprint.step_index_of(quest_oasis_in_the_wastes.STEP_DEFENSE)
        step = self.blueprint.steps[index]

        self.assertIn("kill:mutant_raider", step.targets)
        self.assertIn("mutant_raider", NPC_DB)


    def test_rewards_land_in_the_three_taught_skills(self):
        self.char1.quests.accept_quest(_QUEST_KEY)
        before = {
            key: self.char1.skills.get_total_xp(key)
            for key in quest_oasis_in_the_wastes.REWARD_XP
        }

        quest_oasis_in_the_wastes.award_rewards(self.char1)

        for skill_key, amount in quest_oasis_in_the_wastes.REWARD_XP.items():
            with self.subTest(skill=skill_key):
                gained = self.char1.skills.get_total_xp(skill_key) - before[skill_key]
                self.assertEqual(gained, amount)



class LoneAndroidSpawnerTests(EvenniaTest):
    """The quest giver must actually exist in the world."""

    def test_a_spawner_is_registered_for_the_map_tile(self):
        """
        The regression test for a quest giver that was never placed.

        world/maps/oasis.py has carried a "Lone Android" tile at (2, 0) since
        the map was written, but no spawner was registered for that room key.
        The tile built an empty room NAMED "Lone Android"; the NPC did not
        exist, npc_oasis_guide.py was unreachable, and the opening quest could
        not be started by any means.
        """
        from typeclasses.npcs import LONE_ANDROID_KEY

        self.assertIn(LONE_ANDROID_KEY, SPAWNER_REGISTRY)


    def test_the_spawner_places_a_talkable_android(self):
        from typeclasses.npcs import (
            LONE_ANDROID_DIALOGUE_MODULE,
            LONE_ANDROID_KEY,
        )

        android = SPAWNER_REGISTRY[LONE_ANDROID_KEY](self.room1)

        self.assertIsNotNone(android)
        self.assertEqual(android.db.menu_module, LONE_ANDROID_DIALOGUE_MODULE)
        self.assertIn(android, self.room1.contents)


    def test_respawning_the_tile_does_not_stack_androids(self):
        from typeclasses.npcs import LONE_ANDROID_KEY

        spawner = SPAWNER_REGISTRY[LONE_ANDROID_KEY]
        first = spawner(self.room1)
        second = spawner(self.room1)

        self.assertEqual(first, second)


    def test_the_map_tile_and_the_spawner_agree_on_the_key(self):
        # SPAWNER_REGISTRY dispatches on the room key, so a rename on either
        # side silently stops placing the NPC.
        from typeclasses.npcs import LONE_ANDROID_KEY
        from world.maps.oasis import PROTOTYPES

        tile = PROTOTYPES[(2, 0)]

        self.assertEqual(tile["key"], LONE_ANDROID_KEY)



class BareHandedCuttingTests(EvenniaTest):
    """The bootstrap that makes the crafting step reachable at all."""

    def setUp(self):
        super().setUp()
        self.rusty = create_object(_RUSTY_POLE, key="rusty pole",
                                   location=self.room1)

        # Headroom above the bare-hand cost -- FORTITUDE_START_LEVEL seeds a
        # fresh character at 1 HP, and _pay_bare_hand_cost's "survives" check
        # is strictly-greater-than the 1 HP cost, so a fresh character could
        # never survive their own first bare-handed cut. The one test that
        # wants the fatal case (test_a_fatal_cut_kills_instead_of_harvesting)
        # sets hp back down to 1 itself.
        self.char1.db.max_hp = 10
        self.char1.db.hp = 10


    def _cut(self, target):
        from systems.progression.skills.skill_defs.gathering.cutting import Cutting

        Cutting().execute(self.char1, target)


    def _held_keys(self):
        return [item.key for item in self.char1.contents]


    def test_an_axeless_character_can_work_a_rusty_pole(self):
        """
        Without this the game deadlocks.

        Cutting needs an axe; the only axe is crafted from scrap metal; the
        only scrap metal is cut. A character who arrives with nothing has no
        way into the loop from inside it.
        """
        self._cut(self.rusty)

        self.assertIn("rusty metal chunk", self._held_keys())


    def test_it_costs_one_hit_point(self):
        before = self.char1.hp

        self._cut(self.rusty)

        self.assertEqual(self.char1.hp, before - 1)


    def test_it_still_teaches_normal_xp(self):
        # The bare-hand exemption opens the bootstrap deadlock; it doesn't
        # also make the harvest worthless.
        before = self.char1.skills.get_total_xp("cutting")

        self._cut(self.rusty)

        self.assertGreater(self.char1.skills.get_total_xp("cutting"), before)


    def test_a_metal_pole_still_demands_an_axe(self):
        # The exemption is per node. Only the lowest tier carries it.
        metal = create_object(_METAL_POLE, key="metal pole",
                              location=self.room1)
        before = self.char1.hp

        self._cut(metal)

        self.assertNotIn("metal chunk", self._held_keys())
        self.assertEqual(self.char1.hp, before)


    def test_it_still_reports_the_gather_to_quests(self):
        with mock.patch.object(self.char1.quests, "notify") as notify:
            self._cut(self.rusty)

        actions = [call.args[0] for call in notify.call_args_list]

        self.assertIn("cut", actions)
        self.assertIn("gather", actions)


    def test_a_fatal_cut_kills_instead_of_harvesting(self):
        """
        Survival is decided before the blow, not after.

        at_damage routes a fatal hit through at_death, and Character.respawn
        restores HP to full -- so a character killed by the cost is back at
        max HP and is_alive() by the time at_damage returns. A guard that
        asked afterwards would always be told everything was fine, and would
        hand a freshly-respawned player a chunk of metal with a success
        message.
        """
        self.char1.hp = 1

        self._cut(self.rusty)

        self.assertNotIn("rusty metal chunk", self._held_keys())
        # Respawned, so full HP is the evidence that death happened.
        self.assertEqual(self.char1.hp, self.char1.max_hp)



class OasisPlaythroughTests(EvenniaTest):
    """
    Purpose: Walk the whole quest the way a player does.

    Entry:
        self.char1 is a real Character.

    Exit/Returns:
        No conditions.

    Module Globals:
        None

    Methodology:
        Drives the android's actual dialogue nodes and the actual progression
        hooks rather than calling update_progress directly. A quest can be
        perfectly correct in the blueprint and still be unfinishable because
        no node fires one of its targets -- which is the failure mode this
        whole audit was about.

    Notes/References:
        Nodes take (caller, **kwargs); goto callables take
        (caller, raw_string, **kwargs).

    Author: Nick Hobar
    Creation date: 08/25/2026
    """

    def _step(self):
        return self.char1.quests.current_step_key(_QUEST_KEY)


    def _accept(self):
        guide._accept_oasis_quest(self.char1, "")


    def test_the_opening_conversation_reaches_the_offer(self):
        # DCT.1 -> DCT.2 -> DCT.3, the android ignoring the player throughout.
        text, options = guide.start(self.char1)
        self.assertIn("does not look up", text)

        text, options = guide.node_hello_once(self.char1)
        self.assertIn("keeps writing", text)

        text, options = guide.node_hello_twice(self.char1)
        self.assertIn("stylus", text)

        text, options = guide.node_shoulder_tap(self.char1)
        self.assertIn("looks at you", text)

        text, options = guide.node_analysis(self.char1)
        self.assertIn("82% human", text)

        text, options = guide.node_customization(self.char1)
        text, options = guide.node_who_are_you(self.char1)
        text, options = guide.node_quest_offer(self.char1)

        self.assertIn("Oasis in the Wastes", text)


    def test_a_threatening_opener_lowers_the_confidence_reading(self):
        text, _options = guide.node_analysis(self.char1, note="raider")

        self.assertIn("72% human", text)
        self.assertIn("mutant raider", text)


    def test_a_blank_stare_earns_a_brain_damage_caveat(self):
        text, _options = guide.node_analysis(self.char1, note="damage")

        self.assertIn("brain damage", text)


    def test_accepting_starts_the_quest_on_the_intro_step(self):
        self._accept()

        self.assertTrue(self.char1.quests.is_active(_QUEST_KEY))
        self.assertEqual(self._step(), quest_oasis_in_the_wastes.STEP_INTRO)


    def test_the_briefing_closes_step_one(self):
        # talk:lone_android fires here -- not on the `talk` command, and not
        # on accepting.
        self._accept()

        guide.node_step1_drainage_intro(self.char1)

        self.assertEqual(self._step(), quest_oasis_in_the_wastes.STEP_MAINTENANCE)


    def test_reporting_both_chores_closes_step_two(self):
        self._accept()
        guide.node_step1_drainage_intro(self.char1)

        guide._report_pipe(self.char1, "")
        self.assertEqual(self._step(), quest_oasis_in_the_wastes.STEP_MAINTENANCE)

        guide._report_soil(self.char1, "")
        self.assertEqual(self._step(), quest_oasis_in_the_wastes.STEP_APPRENTICESHIP)


    def test_a_reported_chore_stops_being_offered(self):
        self._accept()
        guide.node_step1_drainage_intro(self.char1)
        guide._report_pipe(self.char1, "")

        _text, options = guide.node_step2_chores(self.char1)
        descriptions = " ".join(option["desc"] for option in options)

        self.assertNotIn("drainage", descriptions)
        self.assertIn("soil", descriptions)


    def test_entering_the_craft_step_hands_over_a_hammer(self):
        self._accept()
        guide.node_step1_drainage_intro(self.char1)
        guide._report_pipe(self.char1, "")
        guide._report_soil(self.char1, "")

        tools = [getattr(item.db, "tool_type", None)
                 for item in self.char1.contents]

        self.assertIn("hammer", tools)


    def test_the_hammer_is_not_handed_over_twice(self):
        self._accept()
        guide.node_step1_drainage_intro(self.char1)
        guide._report_pipe(self.char1, "")
        guide._report_soil(self.char1, "")

        # Re-running the hook is what an abandon-and-retake would do.
        step = self.char1.quests.current_step(_QUEST_KEY)
        quest_oasis_in_the_wastes.grant_teaching_tool(self.char1, step)

        hammers = [item for item in self.char1.contents
                   if getattr(item.db, "tool_type", None) == "hammer"]

        self.assertEqual(len(hammers), 1)


    def _advance_to(self, step_key):
        """Play the quest forward until it sits on step_key."""
        self._accept()
        guide.node_step1_drainage_intro(self.char1)

        if step_key == quest_oasis_in_the_wastes.STEP_MAINTENANCE:
            return

        guide._report_pipe(self.char1, "")
        guide._report_soil(self.char1, "")

        if step_key == quest_oasis_in_the_wastes.STEP_APPRENTICESHIP:
            return

        for recipe in (quest_oasis_in_the_wastes.RECIPE_AXE, quest_oasis_in_the_wastes.RECIPE_DAGGER):
            self.char1.quests.notify("craft", recipe)

        if step_key == quest_oasis_in_the_wastes.STEP_DEFENSE:
            return

        self.char1.quests.notify("kill", "mutant_raider")


    def test_forging_both_items_closes_step_three(self):
        self._advance_to(quest_oasis_in_the_wastes.STEP_APPRENTICESHIP)

        self.char1.quests.notify("craft", quest_oasis_in_the_wastes.RECIPE_AXE)
        self.assertEqual(self._step(), quest_oasis_in_the_wastes.STEP_APPRENTICESHIP)

        self.char1.quests.notify("craft", quest_oasis_in_the_wastes.RECIPE_DAGGER)
        self.assertEqual(self._step(), quest_oasis_in_the_wastes.STEP_DEFENSE)


    def test_killing_a_raider_closes_step_four(self):
        self._advance_to(quest_oasis_in_the_wastes.STEP_DEFENSE)

        self.char1.quests.notify("kill", "mutant_raider")

        self.assertEqual(self._step(), quest_oasis_in_the_wastes.STEP_RESOLUTION)


    def test_the_closing_conversation_completes_the_quest(self):
        self._advance_to(quest_oasis_in_the_wastes.STEP_RESOLUTION)
        before = self.char1.skills.get_total_xp("metalsmith")

        text, _options = guide.node_step5_resolution(self.char1)
        self.assertIn("Neo Cairo", text)

        guide._finish_oasis_quest(self.char1, "")

        self.assertTrue(self.char1.quests.is_complete(_QUEST_KEY))
        self.assertGreater(self.char1.skills.get_total_xp("metalsmith"), before)


    def test_the_conversation_resumes_on_the_right_step(self):
        # start() routes a returning player to the beat they are owed, rather
        # than replaying the introduction.
        for step_key in (quest_oasis_in_the_wastes.STEP_MAINTENANCE,
                         quest_oasis_in_the_wastes.STEP_APPRENTICESHIP,
                         quest_oasis_in_the_wastes.STEP_DEFENSE):
            with self.subTest(step=step_key):
                self.char1.db.active_quests = {}
                self.char1.db.completed_quests = []
                self.char1.__dict__.pop("quests", None)

                self._advance_to(step_key)
                text, _options = guide.start(self.char1)

                self.assertNotIn("does not look up", text)


    def test_a_finished_player_gets_the_post_quest_scene(self):
        self._advance_to(quest_oasis_in_the_wastes.STEP_RESOLUTION)
        guide._finish_oasis_quest(self.char1, "")

        text, _options = guide.start(self.char1)

        self.assertIn("still here", text)


    def test_the_quest_cannot_be_offered_twice(self):
        self._accept()

        text, _options = guide.node_quest_offer(self.char1)

        self.assertIn("already in progress", text)



class OasisKillHookTests(EvenniaTest):
    """The defense step must be satisfiable by an actual kill."""

    def test_a_real_raider_death_advances_the_quest(self):
        """
        Drives at_death rather than notify, because the bug this replaces was
        entirely in that call site: it passed the quest key "*" and the
        display name "Mutant Raider".
        """
        raider = NPC_DB["mutant_raider"].create(location=self.room1)

        self.char1.quests.accept_quest(_QUEST_KEY)
        guide.node_step1_drainage_intro(self.char1)
        guide._report_pipe(self.char1, "")
        guide._report_soil(self.char1, "")

        for recipe in (quest_oasis_in_the_wastes.RECIPE_AXE, quest_oasis_in_the_wastes.RECIPE_DAGGER):
            self.char1.quests.notify("craft", recipe)

        self.assertEqual(
            self.char1.quests.current_step_key(_QUEST_KEY),
            quest_oasis_in_the_wastes.STEP_DEFENSE,
        )

        raider.at_death(killer=self.char1)

        self.assertEqual(
            self.char1.quests.current_step_key(_QUEST_KEY),
            quest_oasis_in_the_wastes.STEP_RESOLUTION,
        )
