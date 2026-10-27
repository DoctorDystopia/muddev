"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/26/2026
Description: Guard the cue table (godot/audio/cues.json), the credits of the
             sound clips, and the check of assets/audio.

             The client keyed its moment table on generated constants until
             10/26/2026. Thus, a moment that the server renamed broke the
             GDScript file. A JSON key cannot do that, so these tests do the
             work instead:
               - The files in git pass the check: each cue names a sound clip
                 that is there and has a credits row, and each moment row
                 names a moment that the server sends.
               - The moment reader of the sound wizard (no Django) gives the
                 same moments as statefeed/constants.py.

             The other cases run the modules on temporary files.
"""

import os
import tempfile
import unittest
from unittest import mock

from assets.audio import check, credits, cue_table, kinds, paths
from systems.interface.statefeed import constants as const


_TWO_PACKS = """# Audio credits

---

## First — Pack

Prose.

| Clip | Source file in the pack | Changes |
|---|---|---|
| `sfx/a.wav` | `A.wav` | Renamed. |

## Second — Pack

Prose with no table.
"""


class CueTableFileTests(unittest.TestCase):
    """The cue table, the credits and the sound clips in git agree."""

    def test_the_files_in_git_pass_the_check(self):
        report = check.run_check()

        self.assertEqual(report.problems, [])

    def test_each_moment_row_names_a_moment_that_the_server_sends(self):
        table = cue_table.read_table(paths.CUE_TABLE_PATH)

        for moment in table.moments:
            with self.subTest(moment=moment):
                self.assertIn(moment, const.MOMENTS)

    def test_the_moment_reader_agrees_with_the_server(self):
        read = cue_table.read_moments(paths.CLIENT_CONSTANTS_PATH)

        self.assertEqual(set(read), set(const.MOMENTS))

    def test_each_cue_has_a_known_sound_kind(self):
        table = cue_table.read_table(paths.CUE_TABLE_PATH)

        for key, cue in table.cues.items():
            with self.subTest(cue=key):
                self.assertIn(cue.kind, kinds.KINDS)

    def test_each_heading_of_the_credits_is_unique(self):
        text = credits.read_credits(paths.CREDITS_PATH)
        headings = [pack.heading for pack in credits.packs_of(text)]

        self.assertEqual(len(headings), len(set(headings)))


class CueTableFormatTests(unittest.TestCase):
    """The reader refuses what the client cannot use."""

    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.addCleanup(self._folder.cleanup)
        self.path = os.path.join(self._folder.name, "cues.json")

    def _write(self, text):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def test_a_table_reads_back_as_it_was_written(self):
        cue = cue_table.Cue(key="a", kind=kinds.SFX_KIND, clip="sfx/a.wav",
                            note="A note.")
        table = cue_table.with_cue(cue_table.CueTable(cues={}, moments={}),
                                   cue, "a_moment")
        cue_table.write_table(table, self.path)

        self.assertEqual(cue_table.read_table(self.path), table)

    def test_a_newer_format_is_refused(self):
        self._write('{"format": %d, "cues": {}, "moments": {}}'
                    % (cue_table.FORMAT + 1))

        with self.assertRaises(cue_table.CueTableError):
            cue_table.read_table(self.path)

    def test_a_cue_with_a_missing_field_is_refused(self):
        self._write('{"format": 1, "cues": {"a": {"kind": "sfx"}}}')

        with self.assertRaises(cue_table.CueTableError):
            cue_table.read_table(self.path)

    def test_a_moment_that_names_no_cue_text_is_refused(self):
        self._write('{"format": 1, "cues": {}, "moments": {"a": 3}}')

        with self.assertRaises(cue_table.CueTableError):
            cue_table.read_table(self.path)

    def test_a_constants_file_with_no_moment_is_refused(self):
        self._write('const CH_MOMENT := "blackout_moment"\n')

        with self.assertRaises(cue_table.CueTableError):
            cue_table.read_moments(self.path)


class CreditsTests(unittest.TestCase):
    """A row lands in its own section, and a new pack at the end."""

    def test_a_row_goes_after_the_last_row_of_its_pack(self):
        row = credits.render_row("sfx/b.wav", "B.wav", "Renamed.")
        text = credits.with_row(_TWO_PACKS, "First — Pack", row)
        packs = credits.packs_of(text)

        self.assertEqual(packs[0].clips, ("sfx/a.wav", "sfx/b.wav"))
        self.assertEqual(packs[1].clips, ())

    def test_a_pack_with_no_table_gets_the_head_of_one(self):
        row = credits.render_row("sfx/b.wav", "B.wav", "Renamed.")
        text = credits.with_row(_TWO_PACKS, "Second — Pack", row)
        packs = credits.packs_of(text)

        self.assertEqual(packs[1].clips, ("sfx/b.wav",))
        self.assertIn("Prose with no table.", text)

    def test_an_unknown_pack_is_refused(self):
        row = credits.render_row("sfx/b.wav", "B.wav", "Renamed.")

        with self.assertRaises(credits.CreditsError):
            credits.with_row(_TWO_PACKS, "No — Pack", row)

    def test_a_new_pack_is_the_last_section(self):
        row = credits.render_row("sfx/c.wav", "C.wav", "")
        section = credits.render_pack("Third — Pack", ["License: CC0 1.0."],
                                      row)
        text = credits.with_pack(_TWO_PACKS, section)
        packs = credits.packs_of(text)

        self.assertEqual(packs[-1].heading, "Third — Pack")
        self.assertEqual(packs[-1].clips, ("sfx/c.wav",))
        self.assertTrue(text.endswith(row + "\n"))

    def test_a_cell_that_breaks_the_table_is_refused(self):
        for value in ("a|b.wav", "a`b.wav"):
            with self.subTest(value=value):
                self.assertTrue(credits.cell_problem(value))

        self.assertEqual(credits.cell_problem("Hollywood/A b.wav"), "")

    def test_the_changes_cell_says_what_the_copy_did(self):
        note = kinds.KINDS[kinds.SFX_KIND].import_note
        renamed = credits.changes_text(True, note)
        kept = credits.changes_text(False, note)

        self.assertIn("Renamed", renamed)
        self.assertNotIn("Renamed", kept)
        self.assertIn(note, kept)
        self.assertIn("unmodified", kept)


class KindTests(unittest.TestCase):
    """Each sound kind writes an import file that Godot reads."""

    def test_each_import_text_holds_each_setting_of_its_kind(self):
        for key, kind in kinds.KINDS.items():
            with self.subTest(kind=key):
                text = kinds.render_import(kind)

                self.assertIn('importer="%s"' % kind.importer, text)

                for name, value in kind.params:
                    self.assertIn("%s=%s" % (name, value), text)

    def test_each_kind_takes_suffixes_and_a_folder(self):
        for key, kind in kinds.KINDS.items():
            with self.subTest(kind=key):
                self.assertTrue(kind.suffixes)
                self.assertTrue(all(suffix.startswith(".")
                                    for suffix in kind.suffixes))
                self.assertNotIn("/", kind.folder)


class CheckTests(unittest.TestCase):
    """The check reports each kind of fault in a temporary godot/audio/."""

    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.addCleanup(self._folder.cleanup)
        root = self._folder.name
        self.audio_dir = os.path.join(root, "audio")
        os.makedirs(os.path.join(self.audio_dir, "sfx"))

        for name, value in (
                ("AUDIO_DIR", self.audio_dir),
                ("CUE_TABLE_PATH", os.path.join(self.audio_dir, "cues.json")),
                ("CREDITS_PATH", os.path.join(self.audio_dir, "CREDITS.md")),
                ("CLIENT_CONSTANTS_PATH", os.path.join(root, "constants.gd"))):
            patch = mock.patch.object(paths, name, value)
            patch.start()
            self.addCleanup(patch.stop)

        with open(paths.CLIENT_CONSTANTS_PATH, "w", encoding="utf-8") as out:
            out.write('const MOMENT_A := "a"\n')

    def _world(self, cues, moments, credited, files):
        """Write a cue table, the credits, and the named sound clips."""
        table = cue_table.CueTable(
            cues={key: cue_table.Cue(key=key, kind=kinds.SFX_KIND, clip=clip,
                                     note="A note.")
                  for key, clip in cues.items()},
            moments=moments)
        cue_table.write_table(table, paths.CUE_TABLE_PATH)
        rows = [credits.render_row(clip, "X.wav", "") for clip in credited]
        section = credits.render_pack("A — Pack", [], "\n".join(rows))
        credits.write_credits(section, paths.CREDITS_PATH)

        for clip in files:
            with open(paths.clip_path(clip), "wb") as handle:
                handle.write(b"RIFF")

    def test_a_consistent_world_passes(self):
        self._world({"a": "sfx/a.wav"}, {"a": "a"}, ["sfx/a.wav"],
                    ["sfx/a.wav"])

        self.assertEqual(check.run_check().problems, [])

    def test_a_missing_clip_and_a_missing_row_are_problems(self):
        self._world({"a": "sfx/a.wav"}, {}, [], [])
        problems = "\n".join(check.run_check().problems)

        self.assertIn("is not there", problems)
        self.assertIn("no row in CREDITS.md", problems)

    def test_a_moment_that_the_server_does_not_send_is_a_problem(self):
        self._world({"a": "sfx/a.wav"}, {"zzz": "a", "a": "b"},
                    ["sfx/a.wav"], ["sfx/a.wav"])
        problems = "\n".join(check.run_check().problems)

        self.assertIn("no moment 'zzz'", problems)
        self.assertIn("names the cue 'b'", problems)

    def test_a_clip_outside_its_kind_folder_is_a_problem(self):
        self._world({"a": "music/a.wav"}, {}, ["music/a.wav"], [])
        problems = "\n".join(check.run_check().problems)

        self.assertIn("is not in sfx/", problems)

    def test_a_file_that_no_cue_plays_is_a_warning_only(self):
        self._world({"a": "sfx/a.wav"}, {}, ["sfx/a.wav"],
                    ["sfx/a.wav", "sfx/old.wav"])
        report = check.run_check()

        self.assertTrue(report.ok)
        self.assertIn("sfx/old.wav", "\n".join(report.warnings))


if __name__ == "__main__":
    unittest.main()
