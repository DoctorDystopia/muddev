"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: Cases for the profile menu: the dossier, skills and records of
             any character, and the three commands that open it.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.interface.menus.tests.test_profile_menu
"""

from evennia.utils.ansi import strip_ansi
from evennia.utils.test_resources import EvenniaTest

from systems.gameplay.progression.skills.registry import SKILL_REGISTRY
from systems.interface.menus import profile_menu
from systems.interface.summary.panel_defs import records
from typeclasses.characters import Character as BlackoutCharacter


class _ProfileTest(EvenniaTest):
    """char1 reads the profile of char2."""

    character_typeclass = BlackoutCharacter

    def _open(self, node: str = profile_menu.NODE_DOSSIER):
        return profile_menu.start_profile_menu(self.char1, self.char2, node)

    def _node(self, node_function) -> tuple:
        text, options = node_function(self.char1)

        return strip_ansi(text), options

    def _run(self, line: str) -> str:
        """Run a command as char1 and return everything char1 was told.

        Captures keyword arguments too: EvMenu sends a node as `text=`.
        """
        captured = []
        self.char1.msg = lambda *args, **kwargs: captured.append((args, kwargs))
        self.char1.execute_cmd(line)

        return strip_ansi(" ".join(str(entry) for entry in captured))


class TestPages(_ProfileTest):

    def setUp(self):
        super().setUp()
        self._open()

    def test_the_dossier_page_is_the_dossier_of_the_target(self):
        self.char2.key = "Targetname"

        text, _options = self._node(profile_menu.start)

        self.assertIn("DOSSIER -- Targetname", text)

    def test_the_skills_page_lists_every_registered_skill(self):
        """Derived from the registry, so a skill added later is covered."""
        text, _options = self._node(profile_menu.node_skills)

        for skill_key, skill_class in SKILL_REGISTRY.items():
            with self.subTest(skill=skill_key):
                self.assertIn(str(skill_class.name), text)

    def test_the_records_page_is_the_stats_sheet_of_the_target(self):
        text, _options = self._node(profile_menu.node_records)

        self.assertIn(self.char2.key, text)
        self.assertIn(records.EMPTY_SHEET_TEXT, text)

    def test_every_page_offers_the_other_two_and_refresh(self):
        nodes = {
            profile_menu.NODE_DOSSIER: profile_menu.start,
            profile_menu.NODE_SKILLS: profile_menu.node_skills,
            profile_menu.NODE_RECORDS: profile_menu.node_records,
        }

        for node_name, node_function in nodes.items():
            _text, options = self._node(node_function)
            gotos = [option["goto"] for option in options]

            with self.subTest(page=node_name):
                self.assertEqual(len(profile_menu.PAGES), len(options))
                self.assertEqual(node_name, gotos[-1])

                for page, _label in profile_menu.PAGES:
                    self.assertIn(page, gotos)

    def test_a_target_that_no_longer_exists_ends_the_menu(self):
        # An id with no row behind it, as after a delete. A puppeted test
        # character cannot simply be deleted.
        missing_id = self.char2.id + 10_000
        setattr(self.char1.ndb._evmenu, profile_menu.TARGET_ID_ATTR, missing_id)

        text, options = self._node(profile_menu.start)

        self.assertIsNone(options)
        self.assertIn(profile_menu.TARGET_GONE_TEXT, text)


class TestCommandsOpenTheMenu(_ProfileTest):
    """`profile`, `skills` and `stats` each open one page of the menu."""

    def test_profile_by_name_opens_the_dossier(self):
        text = self._run(f"profile {self.char2.key}")

        self.assertIn("Profile: " + self.char2.key, text)

    def test_profile_by_dbref_works_for_a_player(self):
        """A click sends the dbref. A player without Builder must reach it."""
        text = self._run(f"profile #{self.char2.id}")

        self.assertIn("Profile: " + self.char2.key, text)

    def test_skills_of_a_character_opens_the_skills_page(self):
        text = self._run(f"skills #{self.char2.id}")

        self.assertIn(f"{self.char2.key}'s Skills", text)

    def test_stats_of_a_character_opens_the_records_page(self):
        text = self._run(f"stats #{self.char2.id}")

        self.assertIn(self.char2.key, text)
        self.assertIn(records.EMPTY_SHEET_TEXT, text)

    def test_every_click_command_on_a_player_opens_a_page(self):
        """Each Profile/Skills/Records row a click sends reaches the menu.

        Read from the entity row the feed sends, so a fourth row added later
        is covered with no edit here.
        """
        from systems.interface.statefeed import serializers

        body = serializers.serialize_entity(self.char2)

        for action in body["actions"]:
            with self.subTest(command=action["command"]):
                self._run(action["command"])
                menu = self.char1.ndb._evmenu

                self.assertIsNotNone(menu)
                self.assertEqual(
                    self.char2.id,
                    getattr(menu, profile_menu.TARGET_ID_ATTR, None))
