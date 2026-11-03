"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/30/2026
Description: The Augmentation intro quest end to end (DESIGN-0015, Phase
             4): the blueprint, the two placeholder dialogues, and one
             playthrough from the recruit to the reward, with the graft
             driven through the real command.
Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py systems.gameplay.quests
"""

from evennia.utils.test_resources import EvenniaCommandTest, EvenniaTest

from commands.augment_cmds import CmdGraft
from systems.gameplay.augmentation import constants as aug_const
from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.quests.content import quest_augmentation_intro as quest
from systems.gameplay.quests.loader import GLOBAL_QUEST_REGISTRY
from typeclasses.characters import Character as BlackoutCharacter
from world.item_database import ITEM_DB
from world.npc_database import NPC_DB
from world.npc_dialogues import aug_clinic_1 as clinic
from world.npc_dialogues import aug_hospital_1 as hospital


_QUEST_KEY = quest.QUEST_KEY


class IntroBlueprintTests(EvenniaTest):
    """The shipped blueprint, as the rest of the game sees it."""

    def setUp(self):
        super().setUp()
        self.blueprint = GLOBAL_QUEST_REGISTRY.get(_QUEST_KEY)

    def test_the_quest_is_registered(self):
        self.assertIsNotNone(self.blueprint)
        self.assertEqual(self.blueprint.title, quest.QUEST_TITLE)

    def test_it_has_the_four_steps_in_order(self):
        self.assertEqual(self.blueprint.step_keys, [
            quest.STEP_RECRUIT, quest.STEP_TRAIL, quest.STEP_GRAFT, quest.STEP_REPORT])

    def test_the_two_npcs_are_real_defs(self):
        for key in (quest.NPC_CLINIC_KEY, quest.NPC_HOSPITAL_KEY):
            with self.subTest(npc=key):
                self.assertIn(key, NPC_DB)

    def test_the_graft_step_names_a_sample_kind_that_an_item_carries(self):
        index = self.blueprint.step_index_of(quest.STEP_GRAFT)
        step = self.blueprint.steps[index]
        kinds = {item_def.sample_kind for item_def in ITEM_DB.values()
                 if item_def.sample_xp is not None}

        self.assertIn(quest.TARGET_GRAFT, step.targets)
        self.assertIn(ITEM_DB[quest.TEACHING_SAMPLE_KEY].sample_kind, kinds)
        self.assertEqual(quest.TARGET_GRAFT.split(":")[1],
                         ITEM_DB[quest.TEACHING_SAMPLE_KEY].sample_kind)

    def test_rewards_land_in_augmentation_and_give_the_samples(self):
        self.char1.quests.accept_quest(_QUEST_KEY)
        before = self.char1.skills.get_total_xp(skill_constants.SKILL_KEY_AUGMENTATION)

        quest.award_rewards(self.char1)

        gained = self.char1.skills.get_total_xp(skill_constants.SKILL_KEY_AUGMENTATION) - before
        self.assertEqual(gained, quest.REWARD_XP[skill_constants.SKILL_KEY_AUGMENTATION])

        samples = [item for item in self.char1.contents
                   if item.attributes.get(aug_const.SAMPLE_KIND_ATTR, default=None)]
        self.assertEqual(sum(getattr(item, "quantity", 1) for item in samples),
                         quest.REWARD_SAMPLE_COUNT)


class IntroPlaythroughTests(EvenniaCommandTest):
    """One run from the recruit to the reward, through the real nodes and
    the real graft command."""

    character_typeclass = BlackoutCharacter

    def _step(self):
        return self.char1.quests.current_step_key(_QUEST_KEY)

    def _accept(self):
        clinic._accept_quest(self.char1, "")

    def _samples(self):
        return [item for item in self.char1.contents
                if item.attributes.get(aug_const.SAMPLE_KIND_ATTR, default=None)]

    def test_the_offer_names_the_quest(self):
        text, _options = clinic.node_quest_offer(self.char1)

        self.assertIn(quest.QUEST_TITLE, text)

    def test_accepting_starts_the_quest_on_the_recruit_step(self):
        self._accept()

        self.assertTrue(self.char1.quests.is_active(_QUEST_KEY))
        self.assertEqual(self._step(), quest.STEP_RECRUIT)

    def test_the_brief_closes_the_recruit_step(self):
        self._accept()

        clinic.node_step_recruit(self.char1)

        self.assertEqual(self._step(), quest.STEP_TRAIL)

    def test_the_hospital_gives_nothing_away_before_the_trail(self):
        text, _options = hospital.start(self.char1)

        self.assertIn("nothing away", text)

    def test_taking_the_sample_opens_the_graft_step_with_a_sample_in_hand(self):
        self._accept()
        clinic.node_step_recruit(self.char1)
        self.assertEqual(self._samples(), [])

        hospital._take_sample(self.char1, "")

        self.assertEqual(self._step(), quest.STEP_GRAFT)
        self.assertEqual(len(self._samples()), 1)

    def test_the_sample_is_not_handed_over_twice(self):
        self._accept()
        clinic.node_step_recruit(self.char1)
        hospital._take_sample(self.char1, "")

        quest.grant_teaching_sample(self.char1, None)

        self.assertEqual(len(self._samples()), 1)

    def test_a_real_graft_closes_the_graft_step(self):
        self._accept()
        clinic.node_step_recruit(self.char1)
        hospital._take_sample(self.char1, "")
        sample = self._samples()[0]

        self.call(CmdGraft(), f" {sample.key}", caller=self.char1)

        self.assertEqual(self._step(), quest.STEP_REPORT)

    def test_either_report_completes_the_quest_and_pays(self):
        for story in ("truth", "cover"):
            with self.subTest(story=story):
                self.char1.db.active_quests = {}
                self.char1.db.completed_quests = []
                self.char1.__dict__.pop("quests", None)
                self._accept()
                clinic.node_step_recruit(self.char1)
                hospital._take_sample(self.char1, "")
                sample = self._samples()[0]
                self.call(CmdGraft(), f" {sample.key}", caller=self.char1)
                before = self.char1.skills.get_total_xp(
                    skill_constants.SKILL_KEY_AUGMENTATION)

                clinic._finish_quest(self.char1, "", story=story)

                self.assertTrue(self.char1.quests.is_complete(_QUEST_KEY))
                self.assertGreater(self.char1.skills.get_total_xp(
                    skill_constants.SKILL_KEY_AUGMENTATION), before)

    def test_the_conversations_resume_on_the_right_step(self):
        self._accept()
        clinic.node_step_recruit(self.char1)

        text, _options = clinic.start(self.char1)
        self.assertIn("trail", text.lower())

        text, _options = hospital.start(self.char1)
        self.assertIn("admits", text)

    def test_a_finished_player_gets_the_post_quest_scene(self):
        self._accept()
        clinic.node_step_recruit(self.char1)
        hospital._take_sample(self.char1, "")
        sample = self._samples()[0]
        self.call(CmdGraft(), f" {sample.key}", caller=self.char1)
        clinic._finish_quest(self.char1, "", story="truth")

        text, _options = clinic.start(self.char1)

        self.assertIn("Locus", text)
