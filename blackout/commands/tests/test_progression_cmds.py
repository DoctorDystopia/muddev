"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/28/2026
Description: Cases for `skills`, whose one argument has three readings.

             The reading ORDER is what these guard. A skill name wins over a
             character name, and the claim that this takes nothing away rests
             on a fact worth asserting rather than asserting once in a comment:
             every string the skill branch now claims used to be a failed
             search. So the cases here are about which branch a given argument
             lands in, and about the fallback still working.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        commands.tests.test_progression_cmds
"""

from evennia.utils.test_resources import EvenniaCommandTest

from commands import progression_cmds
from systems.progression.skills.registry import SKILL_REGISTRY
from typeclasses.characters import Character as BlackoutCharacter


class SkillsCommandTests(EvenniaCommandTest):
    """The three readings of `skills <argument>`."""

    character_typeclass = BlackoutCharacter

    def _run(self, argument=""):
        """Run the command and return everything the caller was told."""
        return self.call(progression_cmds.CmdSkills(), argument)

    def test_a_skill_key_prints_that_skill_s_sheet(self):
        response = self._run("cutting")

        self.assertIn("Cutting", response)
        self.assertIn("Level", response)

    def test_a_display_name_reaches_the_same_sheet(self):
        by_key = self._run("brain_farming")
        by_name = self._run("Brain Farming")

        self.assertEqual(by_key, by_name)

    def test_a_unique_prefix_reaches_it_too(self):
        self.assertIn("Cutting", self._run("cut"))

    def test_the_sheet_names_what_the_skill_unlocks(self):
        """The sheet's whole reason to exist beyond a level: the ladder.

        Derived from the renderer rather than from a literal, so a recipe added
        tomorrow is covered and a skill that legitimately unlocks nothing does
        not fail this.
        """
        from systems.progression.skills import detail as skill_detail

        for skill_key in SKILL_REGISTRY:
            sections = skill_detail.unlock_sections(skill_key)
            rows = [row for _title, entries in sections for row in entries]

            if not rows:
                continue

            response = self._run(skill_key)

            with self.subTest(skill=skill_key):
                for name, _level, _note in rows:
                    self.assertIn(name, response)

    def test_a_character_name_still_reaches_the_other_player_view(self):
        response = self._run(self.char2.key)

        self.assertIn(self.char2.key, response)

    def test_an_argument_that_is_neither_reports_the_failed_search(self):
        """Unchanged behaviour: the search reports its own miss, and the skill
        branch declining to claim a string must not add a second complaint."""
        response = self._run("nothing_by_that_name")

        self.assertIn("could not find", response.lower())

    def test_every_registered_skill_is_reachable_by_its_own_key(self):
        """A skill added tomorrow is readable with no edit anywhere.

        Asserted over the registry rather than as a list, so this is a
        relationship and not a census.
        """
        for skill_key, skill_class in SKILL_REGISTRY.items():
            with self.subTest(skill=skill_key):
                self.assertIn(str(skill_class.name), self._run(skill_key))
