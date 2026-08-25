"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: Guards on the real registry -- that the shipped content actually
             loads, and that every blueprint in it is well formed.
"""

import unittest

from systems.quests.loader import GLOBAL_QUEST_REGISTRY, QuestRegistry
from systems.quests.quests import QuestBlueprint, QuestStep



class RegistryLoadTests(unittest.TestCase):
    """The registry must be populated, and must have loaded cleanly."""

    def test_no_content_module_failed_to_load(self):
        """
        The regression test for the bug that made this whole system inert.

        systems/quests/quests.py used to import the loader at module scope.
        The loader builds its singleton at import time by importing every
        module under content/, and each of those imports QuestBlueprint back
        out of quests.py -- a ring, whose third hop found a half-initialized
        module. Every content module therefore raised ImportError inside the
        loader's `except Exception`, and the registry came up EMPTY.

        Nothing was visible in play except a quest that could not be accepted,
        because the error was only trace-logged. load_errors and this
        assertion are what make it loud.
        """
        self.assertEqual(
            GLOBAL_QUEST_REGISTRY.load_errors,
            [],
            "A quest content module failed to load; see the entries above.",
        )


    def test_the_game_ships_at_least_one_quest(self):
        # Deliberately not a census -- adding a quest must never fail a test.
        self.assertGreater(len(GLOBAL_QUEST_REGISTRY), 0)


    def test_every_blueprint_is_addressable_by_its_own_key(self):
        for quest_key, blueprint in GLOBAL_QUEST_REGISTRY.all().items():
            with self.subTest(quest=quest_key):
                self.assertEqual(blueprint.key, quest_key)
                self.assertIs(GLOBAL_QUEST_REGISTRY.get(quest_key), blueprint)
                self.assertIn(quest_key, GLOBAL_QUEST_REGISTRY)


    def test_all_returns_a_copy(self):
        catalog = GLOBAL_QUEST_REGISTRY.all()
        catalog["injected"] = None

        self.assertNotIn("injected", GLOBAL_QUEST_REGISTRY)



class RegistryDuplicateTests(unittest.TestCase):
    """A duplicate key must be recorded, not merely logged past."""

    def test_duplicate_key_is_recorded_as_a_load_error(self):
        registry = QuestRegistry.__new__(QuestRegistry)
        registry._blueprints = {}
        registry.load_errors = []

        blueprint = QuestBlueprint(
            "dupe", "Dupe", "desc",
            steps=[QuestStep("only", "Do it", targets={"talk:x": True})],
        )
        registry._blueprints["dupe"] = blueprint

        module = type("FakeModule", (), {"QUESTS": [blueprint]})()

        with unittest.mock.patch(
            "systems.quests.loader.importlib.import_module",
            return_value=module,
        ):
            registry._load_module("systems.quests.content.fake")

        self.assertEqual(len(registry.load_errors), 1)
        self.assertIn("dupe", registry.load_errors[0][1])


    def test_import_failure_is_recorded_as_a_load_error(self):
        registry = QuestRegistry.__new__(QuestRegistry)
        registry._blueprints = {}
        registry.load_errors = []

        with unittest.mock.patch(
            "systems.quests.loader.importlib.import_module",
            side_effect=ImportError("cannot import name 'QuestBlueprint'"),
        ):
            registry._load_module("systems.quests.content.fake")

        self.assertEqual(len(registry.load_errors), 1)
        self.assertIn("QuestBlueprint", registry.load_errors[0][1])
        # The server must still come up; one bad file is not a startup failure.
        self.assertEqual(registry._blueprints, {})



class BlueprintShapeTests(unittest.TestCase):
    """Every shipped quest must be structurally playable."""

    def test_every_quest_has_title_description_and_steps(self):
        for quest_key, blueprint in GLOBAL_QUEST_REGISTRY.all().items():
            with self.subTest(quest=quest_key):
                self.assertTrue(blueprint.title,
                                f"{quest_key} has no title")
                self.assertTrue(blueprint.description,
                                f"{quest_key} has no description")
                self.assertTrue(blueprint.steps,
                                f"{quest_key} has no steps")


    def test_every_step_has_a_description_and_at_least_one_target(self):
        for quest_key, blueprint in GLOBAL_QUEST_REGISTRY.all().items():
            for step in blueprint.steps:
                with self.subTest(quest=quest_key, step=step.key):
                    self.assertTrue(step.description,
                                    f"{quest_key}/{step.key} has no description")
                    self.assertTrue(step.targets,
                                    f"{quest_key}/{step.key} has no targets")


    def test_step_keys_are_unique_within_a_quest(self):
        for quest_key, blueprint in GLOBAL_QUEST_REGISTRY.all().items():
            with self.subTest(quest=quest_key):
                keys = blueprint.step_keys

                self.assertEqual(len(keys), len(set(keys)))


    def test_every_prerequisite_names_a_real_quest(self):
        catalog = GLOBAL_QUEST_REGISTRY.all()

        for quest_key, blueprint in catalog.items():
            for required in blueprint.prerequisites:
                with self.subTest(quest=quest_key, requires=required):
                    self.assertIn(required, catalog)


    def test_no_quest_requires_itself(self):
        for quest_key, blueprint in GLOBAL_QUEST_REGISTRY.all().items():
            with self.subTest(quest=quest_key):
                self.assertNotIn(quest_key, blueprint.prerequisites)
