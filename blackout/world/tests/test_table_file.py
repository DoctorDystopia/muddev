"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/14/2026
Description: Tests for the reader of the table files (`world/table_file.py`).

             Run from blackout/:
                 ../evenv/Scripts/evennia.exe test --settings test_settings.py world.tests.test_table_file

             The cases give the reader content in memory, or a file in a
             temporary directory. No file of the repository changes. The
             tables of the repository read through the same reader at
             import, and `test_tile_content.py` checks their rows.
"""

import copy
import json
import os
import tempfile
import unittest
from dataclasses import dataclass

from systems.core.tilegrid import constants as tile_const
from world import table_file


@dataclass(frozen=True)
class _Row:
    """A row class with a text field and a flag that has a default."""

    key: str
    note: str
    flag: bool = False


_SOURCE = "fixture.json"

_GOOD = {
    table_file.FORMAT_KEY: tile_const.TABLE_FORMAT_VERSION,
    table_file.ROWS_KEY: [
        {"key": "first", "note": "The default row.", "flag": True},
        {"key": "second", "note": "A row with no flag."},
    ],
}


def _with(change) -> dict:
    """Return a deep copy of _GOOD after `change(copy)`."""
    data = copy.deepcopy(_GOOD)
    change(data)

    return data


def _rows_of(data) -> list:
    """Return the rows list of a content."""
    return data[table_file.ROWS_KEY]


class ReadTests(unittest.TestCase):
    """A good file reads, in its order, with each default filled."""

    def test_the_rows_keep_the_order_of_the_file(self):
        rows = table_file.rows_from_data(_GOOD, _Row, _SOURCE)

        self.assertEqual([row.key for row in rows], ["first", "second"])

    def test_a_missing_field_with_a_default_takes_the_default(self):
        rows = table_file.rows_from_data(_GOOD, _Row, _SOURCE)

        self.assertTrue(rows[0].flag)
        self.assertFalse(rows[1].flag)

    def test_a_file_reads_from_its_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = table_file.table_path("fixture", directory)

            with open(path, "w", encoding="utf-8") as handle:
                json.dump(_GOOD, handle)

            rows = table_file.read_rows("fixture", _Row, directory)

        self.assertEqual(len(rows), len(_rows_of(_GOOD)))

    def test_the_field_names_follow_the_row_class(self):
        self.assertEqual(table_file.field_names(_Row), ("key", "note", "flag"))


class RefusalTests(unittest.TestCase):
    """Each broken rule raises TableFileError, with the file name."""

    def _assert_refused(self, data, words: str):
        with self.assertRaises(table_file.TableFileError) as caught:
            table_file.rows_from_data(data, _Row, _SOURCE)

        self.assertIn(_SOURCE, str(caught.exception))
        self.assertIn(words, str(caught.exception))

    def test_a_file_that_is_not_there(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(table_file.TableFileError):
                table_file.read_rows("no_such_table", _Row, directory)

    def test_a_file_that_does_not_parse(self):
        with tempfile.TemporaryDirectory() as directory:
            path = table_file.table_path("broken", directory)

            with open(path, "w", encoding="utf-8") as handle:
                handle.write("{not json")

            with self.assertRaises(table_file.TableFileError):
                table_file.read_rows("broken", _Row, directory)

    def test_another_format(self):
        data = _with(lambda d: d.update({table_file.FORMAT_KEY: 99}))
        self._assert_refused(data, "format")

    def test_a_key_beside_format_and_rows(self):
        data = _with(lambda d: d.update({"extra": 1}))
        self._assert_refused(data, "exactly")

    def test_no_rows(self):
        data = _with(lambda d: d.update({table_file.ROWS_KEY: []}))
        self._assert_refused(data, "a row")

    def test_a_missing_field_with_no_default(self):
        data = _with(lambda d: _rows_of(d)[1].pop("note"))
        self._assert_refused(data, "'note'")

    def test_a_field_that_the_row_class_does_not_have(self):
        data = _with(lambda d: _rows_of(d)[0].update({"colour": "red"}))
        self._assert_refused(data, "'colour'")

    def test_a_value_of_another_type(self):
        data = _with(lambda d: _rows_of(d)[0].update({"flag": 1}))
        self._assert_refused(data, "bool")

    def test_a_key_that_is_no_chunk_file_name(self):
        data = _with(lambda d: _rows_of(d)[0].update({"key": "Bad Key"}))
        self._assert_refused(data, "legal key")

    def test_two_rows_with_one_key(self):
        data = _with(lambda d: _rows_of(d)[1].update({"key": "first"}))
        self._assert_refused(data, "'first'")

    def test_the_error_names_the_row(self):
        data = _with(lambda d: _rows_of(d)[1].update({"note": 7}))
        self._assert_refused(data, "row 1")


class RepositoryTableTests(unittest.TestCase):
    """The table directory of the repository holds a file for each table."""

    def test_the_directory_is_the_one_the_constants_name(self):
        expected = os.path.join(*tile_const.TABLE_DIRECTORY.split("/"))

        self.assertTrue(table_file.TABLE_DIRECTORY_PATH.endswith(expected))
        self.assertTrue(os.path.isdir(table_file.TABLE_DIRECTORY_PATH))
