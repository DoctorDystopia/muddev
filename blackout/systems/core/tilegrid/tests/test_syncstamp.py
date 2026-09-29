"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/26/2026
Description: Tests for the tile sync stamp, `syncstamp.py`. Each test works in
             a scratch directory. Needs no database.
"""

import os
import shutil
import tempfile
import unittest

from systems.core.tilegrid import constants as const
from systems.core.tilegrid import syncstamp


def _write(directory: str, name: str, text: str) -> None:
    with open(os.path.join(directory, name), "w", encoding="utf-8",
              newline="") as handle:
        handle.write(text)


class SyncStampTests(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)
        self.stamp = os.path.join(self.directory, "stamp.json")
        _write(self.directory, "chunk_0_0_p0.json", "{\n}\n")
        _write(self.directory, "chunk_1_0_p0.json", "{\n \n}\n")

    def test_a_fresh_stamp_matches(self):
        syncstamp.write_stamp(self.directory, self.stamp)

        self.assertEqual(syncstamp.changed_files(
            self.directory, syncstamp.read_stamp(self.stamp)), [])

    def test_only_chunk_files_are_stamped(self):
        _write(self.directory, "notes.json", "{}")
        syncstamp.write_stamp(self.directory, self.stamp)

        self.assertEqual(sorted(syncstamp.read_stamp(self.stamp)),
                         ["chunk_0_0_p0.json", "chunk_1_0_p0.json"])

    def test_new_changed_and_removed_files_are_named(self):
        syncstamp.write_stamp(self.directory, self.stamp)
        _write(self.directory, "chunk_0_0_p0.json", "{\n \"x\": 1\n}\n")
        _write(self.directory, "chunk_0_0_p1.json", "{}\n")
        os.remove(os.path.join(self.directory, "chunk_1_0_p0.json"))

        found = syncstamp.changed_files(self.directory,
                                        syncstamp.read_stamp(self.stamp))

        self.assertEqual(found, [
            ("chunk_0_0_p0.json", syncstamp.STATE_CHANGED),
            ("chunk_0_0_p1.json", syncstamp.STATE_NEW),
            ("chunk_1_0_p0.json", syncstamp.STATE_REMOVED),
        ])

    def test_a_line_end_change_is_no_change(self):
        # Git may check a file out with CRLF. The meaning is the same.
        syncstamp.write_stamp(self.directory, self.stamp)
        _write(self.directory, "chunk_0_0_p0.json", "{\r\n}\r\n")

        self.assertEqual(syncstamp.changed_files(
            self.directory, syncstamp.read_stamp(self.stamp)), [])

    def test_no_stamp_reads_as_none(self):
        self.assertIsNone(syncstamp.read_stamp(self.stamp))

    def test_the_stamp_path_is_under_the_game_directory(self):
        path = syncstamp.stamp_path(self.directory)

        self.assertEqual(os.path.relpath(path, self.directory).replace(os.sep, "/"),
                         const.SYNC_STAMP_FILE)
