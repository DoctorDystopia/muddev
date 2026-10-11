"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/24/2026
Description: Tests for the chunk file: the reader, the canonical writer, the
             seam check, and the Python half of the parity test.

The parity test, in two halves
------------------------------
A Python test cannot run GDScript. So each language proves the same three
things against the same committed files:

1. It reads each fixture and writes it back byte for byte.
2. Its `semantic_dump` of each fixture has the digest in
   `fixtures/digests.json`.
3. It refuses every case in INVALID_CASES.

`godot/tests/test_chunk_file.gd` is the other half. The guard at the end of
this module reads that file as text and fails if its case names differ from
INVALID_CASES, so one side cannot gain a rule that the other lacks.
"""

import copy
import json
import os
import re
import tempfile
import unittest

from systems.core.tilegrid import chunkfile
from systems.core.tilegrid import constants as const
from systems.core.tilegrid.tests import fixture_builder


# ─── Private constant definitions ────────────────────────────────────────────

# The game dir (blackout/), five levels up from this file.
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))

_REPO_ROOT = os.path.dirname(_GAME_DIR)

_WORLD_CHUNK_DIRECTORY = os.path.join(_GAME_DIR, const.CHUNK_DIRECTORY)

_GODOT_TEST = os.path.join(_REPO_ROOT, "godot", "tests", "test_chunk_file.gd")

# The fixture that the invalid cases mutate.
_BASE_FIXTURE = "chunk_-1_2_p0.json"

# How the Godot test names a case: `_refuses("case_name", ...)`.
_GODOT_CASE_RE = re.compile(r'_refuses\(\s*"([a-z_]+)"')


# ─── Private helper routines ─────────────────────────────────────────────────

def _fixture_path(name: str) -> str:
    return os.path.join(fixture_builder.FIXTURE_DIRECTORY, name)


def _fixture_text(name: str) -> str:
    """Return the committed text, with any CRLF made LF."""
    with open(_fixture_path(name), "r", encoding="utf-8", newline="") as handle:
        text = handle.read()

    return text.replace("\r\n", "\n")


def _fixture_dict(name: str) -> dict:
    return json.loads(_fixture_text(name))


def _set(key, value):
    def mutate(data):
        data[key] = value

    return mutate


def _delete(key):
    def mutate(data):
        del data[key]

    return mutate


def _set_cell(key, row, column, value):
    def mutate(data):
        data[key][row][column] = value

    return mutate


def _set_object(key, value):
    def mutate(data):
        data["objects"][0][key] = value

    return mutate


def _delete_object_key(key):
    def mutate(data):
        del data["objects"][0][key]

    return mutate


def _pop_row(key):
    def mutate(data):
        data[key].pop()

    return mutate


def _pop_value(key):
    def mutate(data):
        data[key][0].pop()

    return mutate


def _with_walls(names, cell=0):
    """
    Make the base fixture a file of format 2 with the wall styles `names`.
    The first tile gets index `cell`. Every other tile gets index 0.
    """
    def mutate(data):
        size = const.CHUNK_SIZE
        walls = [[0] * size for _ in range(size)]
        walls[0][0] = cell
        data["format"] = const.CHUNK_FORMAT_VERSION
        data["wall_names"] = list(names)
        data["walls"] = walls

    return mutate


def _plain_walls_in_format_one(data):
    """Give a file of format 1 the two keys of format 2."""
    _with_walls(["brick"])(data)
    data["format"] = const.CHUNK_FORMAT_PLAIN_WALLS


# ─── Public constant definitions ─────────────────────────────────────────────

# Each case: a name, and a change to the parsed base fixture that makes it
# break format 1. `not_json` is a text case, so it has no change.
INVALID_CASES: dict = {
    "not_json": None,
    "missing_key": _delete("objects"),
    "unknown_key": _set("seed", 7),
    "wrong_format": _set("format", const.CHUNK_FORMAT_VERSION + 1),
    "wrong_size": _set("size", const.CHUNK_SIZE // 2),
    "chunk_not_pair": _set("chunk", [0]),
    "plane_too_high": _set("plane", const.PLANE_MAX + 1),
    "plane_negative": _set("plane", -1),
    "bool_as_int": _set("plane", True),
    "fractional_number": _set("plane", 0.5),
    "floor_names_empty": _set("floor_names", []),
    "bad_name": _set("floor_names", ["Sand", "asphalt", "rubble"]),
    "name_line_break": _set("floor_names", ["sand\n", "asphalt", "rubble"]),
    "duplicate_name": _set("floor_names", ["sand", "sand", "rubble"]),
    "short_height_rows": _pop_row("heights"),
    "short_row": _pop_value("floors"),
    "height_out_of_range": _set_cell("heights", 0, 0, const.HEIGHT_MAX + 1),
    "floor_index_past_names": _set_cell("floors", 0, 0, 3),
    "area_index_past_names": _set_cell("areas", 0, 0, 2),
    "unknown_flag_bit": _set_cell("flags", 0, 0, const.FLAGS_ALL + 1),
    "negative_flag": _set_cell("flags", 0, 0, -1),
    "object_extra_key": _set_object("facing", 1),
    "object_missing_rotation": _delete_object_key("rotation"),
    "object_outside_chunk": _set_object("x", const.CHUNK_SIZE),
    "object_bad_rotation": _set_object("rotation", const.ROTATION_COUNT),
    "object_bad_kind": _set_object("kind", "Bad Kind"),
    "object_empty_text": _set_object("text", ""),
    "object_text_not_string": _set_object("text", 7),
    "object_text_quote": _set_object("text", 'Say "hi"'),
    "object_text_markup": _set_object("text", "|rRed"),
    "object_text_edge_space": _set_object("text", "Bank "),
    "object_text_line_break": _set_object("text", "Bank\n"),
    "object_text_too_long": _set_object(
        "text", "x" * (const.CHUNK_TEXT_MAX_CHARS + 1)),
    # Format 2, the wall styles (DESIGN-0013 section 6.4).
    "format_one_with_walls": _plain_walls_in_format_one,
    "format_two_without_walls": _set("format", const.CHUNK_FORMAT_VERSION),
    "wall_names_empty": _with_walls([]),
    "wall_index_past_names": _with_walls(["brick"], 1),
    "walls_all_default": _with_walls([const.DEFAULT_WALL_STYLE, "brick"]),
}


# ─── Tests ───────────────────────────────────────────────────────────────────

class FixtureTests(unittest.TestCase):
    """The committed fixtures are the builder's output, and read back exactly."""

    def test_every_fixture_is_what_the_builder_writes(self):
        for built in fixture_builder.build_fixtures():
            with self.subTest(fixture=built.file_name()):
                expected = chunkfile.to_text(built)
                self.assertEqual(
                    _fixture_text(built.file_name()), expected,
                    "The fixture differs from fixture_builder. Run the "
                    "builder, as its docstring says.")

    def test_the_digest_file_is_what_the_builder_writes(self):
        built = fixture_builder.build_fixtures()
        expected = fixture_builder.digest_text(built)

        self.assertEqual(_fixture_text(fixture_builder.DIGEST_FILE_NAME),
                         expected)

    def test_each_fixture_reads_and_writes_back_byte_for_byte(self):
        for built in fixture_builder.build_fixtures():
            name = built.file_name()

            with self.subTest(fixture=name):
                text = _fixture_text(name)
                read_back = chunkfile.parse_text(text)
                self.assertEqual(chunkfile.to_text(read_back), text)

    def test_each_fixture_has_its_committed_digest(self):
        committed = json.loads(_fixture_text(fixture_builder.DIGEST_FILE_NAME))

        for name, digest in committed.items():
            with self.subTest(fixture=name):
                read_back = chunkfile.read_file(_fixture_path(name))
                self.assertEqual(chunkfile.semantic_digest(read_back), digest)


class RefusalTests(unittest.TestCase):
    """Every case in INVALID_CASES is refused."""

    def test_every_invalid_case_is_refused(self):
        base = _fixture_dict(_BASE_FIXTURE)

        for name, mutate in INVALID_CASES.items():
            with self.subTest(case=name):
                if mutate is None:
                    with self.assertRaises(chunkfile.ChunkFileError):
                        chunkfile.parse_text("{ not json")
                    continue

                data = copy.deepcopy(base)
                mutate(data)

                with self.assertRaises(chunkfile.ChunkFileError):
                    chunkfile.from_dict(data)

    def test_an_integral_float_counts_as_an_int(self):
        # GDScript reads every JSON number as a float. So both readers accept
        # 0.0 where they accept 0.
        data = _fixture_dict(_BASE_FIXTURE)
        data["plane"] = 0.0

        self.assertEqual(chunkfile.from_dict(data).plane, 0)

    def test_the_wall_cases_differ_from_a_good_file_only_in_their_fault(self):
        # A wall case that a reader refuses for another reason proves
        # nothing. The same change with a legal index reads.
        data = _fixture_dict(_BASE_FIXTURE)
        _with_walls(["brick"])(data)

        self.assertEqual(chunkfile.from_dict(data).wall_names, ["brick"])

        data = _fixture_dict(_BASE_FIXTURE)
        _with_walls([const.DEFAULT_WALL_STYLE, "brick"], 1)(data)

        self.assertEqual(chunkfile.from_dict(data).wall_style_name(0, 0),
                         "brick")


class MeaningTests(unittest.TestCase):
    """What a read chunk file says about the world."""

    def setUp(self):
        self.chunk_file = chunkfile.read_file(_fixture_path(_BASE_FIXTURE))

    def test_objects_are_local_and_the_reader_adds_the_chunk_offset(self):
        size = const.CHUNK_SIZE
        first = self.chunk_file.objects[0]
        placed = self.chunk_file.global_objects()[0]

        self.assertEqual(placed, (first.kind,
                                  self.chunk_file.cx * size + first.x,
                                  self.chunk_file.cy * size + first.y,
                                  first.rotation))

    def test_an_object_text_reads_and_an_object_without_text_has_none(self):
        # The writer writes the text key only for an object with text, so a
        # file with no text is the same bytes as before the key.
        written = json.loads(chunkfile.to_text(self.chunk_file))["objects"]
        texts = [thing.text for thing in self.chunk_file.objects]

        self.assertIn("", texts)
        self.assertTrue(any(texts))

        for thing, item in zip(self.chunk_file.objects, written):
            with self.subTest(kind=thing.kind):
                self.assertEqual(item.get(chunkfile.OBJECT_TEXT_KEY, ""),
                                 thing.text)
                self.assertEqual(chunkfile.OBJECT_TEXT_KEY in item,
                                 bool(thing.text))

    def test_the_grid_reads_the_file_at_world_coordinates(self):
        grid = chunkfile.build_grid([self.chunk_file])
        size = const.CHUNK_SIZE
        origin_x = self.chunk_file.cx * size
        origin_y = self.chunk_file.cy * size

        for lx, ly in ((0, 0), (size - 1, 0), (0, size - 1), (17, 42)):
            with self.subTest(tile=(lx, ly)):
                gx, gy = origin_x + lx, origin_y + ly
                self.assertEqual(grid.flags_at(gx, gy),
                                 self.chunk_file.flags[ly * size + lx])
                self.assertEqual(grid.tile_height(gx, gy),
                                 self.chunk_file.tile_height(lx, ly))

    def test_a_format_one_file_reads_the_default_wall_style_on_every_tile(self):
        size = const.CHUNK_SIZE

        self.assertFalse(self.chunk_file.has_wall_styles())

        for lx, ly in ((0, 0), (size - 1, size - 1), (17, 42)):
            with self.subTest(tile=(lx, ly)):
                self.assertEqual(self.chunk_file.wall_style_name(lx, ly),
                                 const.DEFAULT_WALL_STYLE)

    def test_the_writer_picks_the_format_from_the_wall_styles(self):
        plain = chunkfile.to_text(self.chunk_file)
        self.chunk_file.wall_names = [const.DEFAULT_WALL_STYLE, "brick"]
        self.chunk_file.walls[5] = 1
        styled = chunkfile.to_text(self.chunk_file)

        self.assertEqual(json.loads(plain)["format"],
                         const.CHUNK_FORMAT_PLAIN_WALLS)
        self.assertNotIn("walls", json.loads(plain))
        self.assertEqual(json.loads(styled)["format"],
                         const.CHUNK_FORMAT_VERSION)
        self.assertEqual(chunkfile.parse_text(styled).wall_style_name(5, 0),
                         "brick")

    def test_a_name_list_with_only_unused_styles_still_writes_format_one(self):
        # The editor may hold a painted-over name until it compacts the
        # names. What counts is the style of each tile.
        self.chunk_file.wall_names = [const.DEFAULT_WALL_STYLE, "brick"]

        text = chunkfile.to_text(self.chunk_file)

        self.assertEqual(json.loads(text)["format"],
                         const.CHUNK_FORMAT_PLAIN_WALLS)

    def test_row_zero_is_the_south_edge(self):
        data = _fixture_dict(_BASE_FIXTURE)
        south_west_flags = data["flags"][0][0]
        north_west_flags = data["flags"][const.CHUNK_SIZE - 1][0]

        self.assertEqual(self.chunk_file.flags[0], south_west_flags)
        self.assertEqual(
            self.chunk_file.flags[(const.CHUNK_SIZE - 1) * const.CHUNK_SIZE],
            north_west_flags)


class SeamTests(unittest.TestCase):

    def test_the_fixture_neighbours_share_their_seam(self):
        built = fixture_builder.build_fixtures()

        self.assertEqual(chunkfile.seam_mismatches(built), [])

    def test_a_changed_edge_corner_is_a_mismatch(self):
        west, east, *others = fixture_builder.build_fixtures()
        east.heights[0] += 1

        mismatches = chunkfile.seam_mismatches([west, east] + others)

        self.assertEqual(mismatches, [(west.file_name(), east.file_name(), 0)])


class DirectoryTests(unittest.TestCase):

    def test_the_fixture_directory_loads(self):
        found = chunkfile.load_directory(fixture_builder.FIXTURE_DIRECTORY)
        names = [f.file_name() for f in found]
        built = sorted(f.file_name() for f in fixture_builder.build_fixtures())

        self.assertEqual(names, built)

    def test_a_file_named_for_another_chunk_is_refused(self):
        text = _fixture_text(_BASE_FIXTURE)

        with tempfile.TemporaryDirectory() as directory:
            wrong = os.path.join(directory, "chunk_5_5_p0.json")

            with open(wrong, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)

            with self.assertRaises(chunkfile.ChunkFileError):
                chunkfile.load_directory(directory)

    def test_every_world_chunk_file_loads_and_its_seams_match(self):
        # This covers every chunk file that an author commits.
        found = chunkfile.load_directory(_WORLD_CHUNK_DIRECTORY)

        self.assertEqual(chunkfile.seam_mismatches(found), [])


class GodotParityGuardTests(unittest.TestCase):
    """The Godot half of the parity test refuses the same cases as this one."""

    def test_the_godot_test_names_every_invalid_case(self):
        self.assertTrue(os.path.isfile(_GODOT_TEST),
                        "%s is missing, so the GDScript reader has no parity "
                        "test." % _GODOT_TEST)

        with open(_GODOT_TEST, "r", encoding="utf-8") as handle:
            source = handle.read()

        godot_cases = set(_GODOT_CASE_RE.findall(source))

        self.assertEqual(godot_cases, set(INVALID_CASES),
                         "The two readers must refuse the same cases. Add "
                         "or remove the case on both sides.")
