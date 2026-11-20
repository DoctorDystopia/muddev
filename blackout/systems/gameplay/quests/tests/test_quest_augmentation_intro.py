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
from systems.gameplay.augmentation import graft_channel
from systems.gameplay.progression.skills import constants as skill_constants
from systems.gameplay.quests.content import quest_augmentation_intro as quest
from systems.gameplay.quests.loader import GLOBAL_QUEST_REGISTRY
from typeclasses.characters import Character as BlackoutCharacter
from world.item_database import ITEM_DB
from systems.gameplay.dialogue.tests import helpers as dialogue
from world.npc_database import NPC_DB


_QUEST_KEY = quest.QUEST_KEY

# The dialogue script of each of the two NPCs, from its def (DESIGN-0017).
_CLINIC_SCRIPT = NPC_DB[quest.NPC_CLINIC_KEY].dialogue_script
_HOSPITAL_SCRIPT = NPC_DB[quest.NPC_HOSPITAL_KEY].dialogue_script


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
    """One run from the recruit to the reward, through the two real
    dialogue scripts and the real graft command.

    Each step gives a response by a keyword of its label, as a player picks
    it. The conversation has no menu here: the dialogue runner is the same
    one that the menu uses."""

    character_typeclass = BlackoutCharacter

    def tearDown(self):
        graft_channel.end_grafting(self.char1)
        super().tearDown()

    def _step(self):
        return self.char1.quests.current_step_key(_QUEST_KEY)

    def _clinic(self):
        return dialogue.talk(self.char1, _CLINIC_SCRIPT)

    def _hospital(self):
        return dialogue.talk(self.char1, _HOSPITAL_SCRIPT)

    def _take_the_job(self):
        """Ask about the job and accept it. The recruiter gives the brief
        in the same beat, which closes the recruit step."""
        conversation = self._clinic()
        dialogue.give(conversation, "ask about the job")

        return dialogue.give(conversation, "Accept")

    def _take_the_sample(self):
        return dialogue.give(self._hospital(), "take the sample")

    def _graft_the_sample(self):
        sample = self._samples()[0]
        self.call(CmdGraft(), f" {sample.key}", caller=self.char1)

    def _samples(self):
        return [item for item in self.char1.contents
                if item.attributes.get(aug_const.SAMPLE_KIND_ATTR, default=None)]

    def test_the_offer_names_the_quest(self):
        conversation = self._clinic()

        beat = dialogue.give(conversation, "ask about the job")

        self.assertIn(quest.QUEST_TITLE, beat.text)

    def test_accepting_starts_the_quest(self):
        self._take_the_job()

        self.assertTrue(self.char1.quests.is_active(_QUEST_KEY))

    def test_the_brief_closes_the_recruit_step(self):
        self.char1.quests.accept_quest(_QUEST_KEY)
        self.assertEqual(self._step(), quest.STEP_RECRUIT)

        self._clinic()

        self.assertEqual(self._step(), quest.STEP_TRAIL)

    def test_the_brief_follows_the_accept_in_one_beat(self):
        beat = self._take_the_job()

        self.assertEqual(self._step(), quest.STEP_TRAIL)
        self.assertIn("brief", beat.text)

    def test_the_hospital_gives_nothing_away_before_the_trail(self):
        beat = self._hospital().beat

        self.assertIn("busy", beat.text)

    def test_taking_the_sample_opens_the_graft_step_with_a_sample_in_hand(self):
        self._take_the_job()
        self.assertEqual(self._samples(), [])

        self._take_the_sample()

        self.assertEqual(self._step(), quest.STEP_GRAFT)
        self.assertEqual(len(self._samples()), 1)

    def test_the_sample_is_not_handed_over_twice(self):
        self._take_the_job()
        self._take_the_sample()

        quest.grant_teaching_sample(self.char1, None)

        self.assertEqual(len(self._samples()), 1)

    def test_a_real_graft_closes_the_graft_step(self):
        self._take_the_job()
        self._take_the_sample()

        self._graft_the_sample()

        self.assertEqual(self._step(), quest.STEP_REPORT)

    def test_either_report_completes_the_quest_and_pays(self):
        for story in ("truth", "cover story"):
            with self.subTest(story=story):
                # A graft keeps a channel for GRAFT_TICKS ticks, and no tick
                # runs here. End it, or the next graft joins its wait.
                graft_channel.end_grafting(self.char1)
                self.char1.db.active_quests = {}
                self.char1.db.completed_quests = []
                self.char1.__dict__.pop("quests", None)
                self._take_the_job()
                self._take_the_sample()
                self._graft_the_sample()
                before = self.char1.skills.get_total_xp(
                    skill_constants.SKILL_KEY_AUGMENTATION)

                dialogue.give(self._clinic(), story)

                self.assertTrue(self.char1.quests.is_complete(_QUEST_KEY))
                self.assertGreater(self.char1.skills.get_total_xp(
                    skill_constants.SKILL_KEY_AUGMENTATION), before)

    def test_the_conversations_resume_on_the_right_step(self):
        self._take_the_job()

        self.assertIn("tracked down", self._clinic().beat.text.lower())
        self.assertIn("admits", self._hospital().beat.text)

    def test_a_finished_player_gets_the_post_quest_scene(self):
        self._take_the_job()
        self._take_the_sample()
        self._graft_the_sample()
        dialogue.give(self._clinic(), "truth")

        beat = self._clinic().beat

        self.assertIn("Locus", beat.text)
