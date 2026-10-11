"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/09/2026
Description: The name check of the templates of the Build tab (DESIGN-0013
             section 6.6). The terrain editor writes a template to
             `world/structures/<key>.json`. The server never loads one. Thus,
             this test is the only server guard on a template: every floor
             type, area, wall style, and object kind that a template names
             must be a row of its table. A copy of a template with a stale
             name would put that name into a chunk file.

             Run from blackout/:
                 ../evenv/Scripts/evennia.exe test --settings test_settings.py world.tests.test_structure_templates

             The GDScript reader (`structure_template.gd`) owns the full
             format. This test reads each file with `json` and checks only
             what the server owns: the names, and that each grid index
             names a row of its list. `fixtures/structures/fixture_stall.json`
             is also the fixture of `godot/tests/test_structure_template.gd`,
             which writes it back byte for byte.

             NO CENSUS HERE. The directory may hold any number of templates.
"""

import copy
import json
import os
import unittest

from systems.core.tilegrid import constants as tile_const
from world import areas
from world import floor_types
from world import object_kinds
from world import wall_styles

# The game directory, two levels above this file.
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

_STRUCTURE_DIRECTORY = os.path.join(_GAME_DIR, tile_const.STRUCTURE_DIRECTORY)

_FIXTURE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "fixtures", "structures", "fixture_stall.json")

# Each name list of a template, its table, and the grid that indexes it.
_NAME_LISTS: tuple = (
    ("floor_names", floor_types.FLOOR_TYPES, "floors"),
    ("area_names", areas.AREAS, "areas"),
    ("wall_names", wall_styles.WALL_STYLES, "walls"),
)

# A floor type that no table holds. The bad case below uses it.
_UNKNOWN_NAME = "no_such_row"


def _template_paths() -> list:
    """
    Purpose: Every template file of the world, sorted.
    Exit-Returns: A list of paths. Empty when the directory does not exist.
    """
    if not os.path.isdir(_STRUCTURE_DIRECTORY):
        return []

    names = sorted(os.listdir(_STRUCTURE_DIRECTORY))
    suffix = tile_const.STRUCTURE_FILE_SUFFIX

    return [os.path.join(_STRUCTURE_DIRECTORY, name)
            for name in names if name.endswith(suffix)]


def _read(path: str) -> dict:
    """
    Purpose: One template file as a dict.
    Entry: path - the path of the file.
    Exit-Returns: The parsed JSON.
    """
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _list_problems(data: dict) -> list:
    """
    Purpose: Each name of a name list that is not a row of its table, and
             each grid index that names no row of its list.
    Entry: data - one template, parsed.
    Exit-Returns: A list of problems in words. Empty for a good template.
    """
    problems = []

    for list_key, table, grid_key in _NAME_LISTS:
        names = data[list_key]
        problems.extend(f"{list_key}: {name} is not a row"
                        for name in names if name not in table)

        for layer in data["planes"]:
            used = {index for row in layer[grid_key] for index in row}
            problems.extend(f"{grid_key}: index {index} names no row"
                            for index in used if not 0 <= index < len(names))

    return problems


def _object_problems(data: dict) -> list:
    """
    Purpose: Each object kind of a template that is not a row of the table.
    Entry: data - one template, parsed.
    Exit-Returns: A list of problems in words.
    """
    return [f"objects: {thing['kind']} is not an object kind"
            for thing in data["objects"]
            if thing["kind"] not in object_kinds.OBJECT_KINDS]


def template_problems(data: dict) -> list:
    """
    Purpose: Every name problem of one template.
    Entry: data - one template, parsed.
    Exit-Returns: A list of problems in words. Empty for a good template.
    """
    problems = []

    if data.get("format") != tile_const.STRUCTURE_FORMAT_VERSION:
        problems.append(f"format is {data.get('format')}")

    problems.extend(_list_problems(data))
    problems.extend(_object_problems(data))

    return problems


class TemplateNameTests(unittest.TestCase):
    """Every template names only rows of the tables of the server."""

    def test_every_world_template_names_only_rows(self):
        for path in _template_paths():
            with self.subTest(template=os.path.basename(path)):
                self.assertEqual(template_problems(_read(path)), [])

    def test_every_world_template_key_is_its_file_name(self):
        suffix = tile_const.STRUCTURE_FILE_SUFFIX

        for path in _template_paths():
            with self.subTest(template=os.path.basename(path)):
                stem = os.path.basename(path)[:-len(suffix)]
                self.assertEqual(_read(path)["key"], stem)

    def test_the_fixture_names_only_rows(self):
        self.assertEqual(template_problems(_read(_FIXTURE_PATH)), [])

    def test_the_check_names_a_name_that_is_no_row(self):
        data = copy.deepcopy(_read(_FIXTURE_PATH))
        data["floor_names"][0] = _UNKNOWN_NAME
        data["objects"][0]["kind"] = _UNKNOWN_NAME

        problems = " ".join(template_problems(data))

        self.assertIn("floor_names", problems)
        self.assertIn("objects", problems)

    def test_the_check_names_an_index_past_its_list(self):
        data = copy.deepcopy(_read(_FIXTURE_PATH))
        data["planes"][0]["walls"][0][0] = len(data["wall_names"])

        self.assertIn("walls", " ".join(template_problems(data)))
