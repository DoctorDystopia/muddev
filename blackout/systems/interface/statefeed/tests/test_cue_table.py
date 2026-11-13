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

import dataclasses
import os
import tempfile
import unittest
from unittest import mock

from assets.audio import check, credits, cue_table, kinds, paths, tracks
from assets.pipeline import paths as pipeline_paths
from systems.interface.statefeed import constants as const
from world import areas, music_tracks


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
    """Each sound kind in the pck writes an import file that Godot reads.
    A served kind writes none."""

    def test_each_import_text_holds_each_setting_of_its_kind(self):
        for key, kind in kinds.KINDS.items():
            if kind.served:
                continue

            with self.subTest(kind=key):
                text = kinds.render_import(kind)

                self.assertIn('importer="%s"' % kind.importer, text)

                for name, value in kind.params:
                    self.assertIn("%s=%s" % (name, value), text)

    def test_a_served_kind_has_no_import_file(self):
        served = [kind for kind in kinds.KINDS.values() if kind.served]

        self.assertTrue(served)

        for kind in served:
            with self.subTest(kind=kind.folder):
                self.assertEqual(kinds.render_import(kind), "")
                self.assertEqual(kind.importer, "")

    def test_each_kind_takes_suffixes_and_a_folder(self):
        for key, kind in kinds.KINDS.items():
            with self.subTest(kind=key):
                self.assertTrue(kind.suffixes)
                self.assertTrue(all(suffix.startswith(".")
                                    for suffix in kind.suffixes))
                self.assertTrue(kind.output_suffix.startswith("."))
                self.assertNotIn("/", kind.folder)

    def test_the_music_kind_serves_the_suffix_that_the_server_names(self):
        kind = kinds.KINDS[kinds.MUSIC_KIND]

        self.assertTrue(kind.served)
        self.assertEqual(kind.output_suffix, music_tracks.SERVED_SUFFIX)
        self.assertTrue(music_tracks.SERVED_DIRECTORY.endswith(kind.folder))


class CheckTests(unittest.TestCase):
    """The check reports each kind of fault in a temporary godot/audio/."""

    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.addCleanup(self._folder.cleanup)
        root = self._folder.name
        self.audio_dir = os.path.join(root, "audio")
        self.served_dir = os.path.join(root, "music")
        self.sources_dir = os.path.join(root, "sources")
        os.makedirs(os.path.join(self.audio_dir, "sfx"))
        os.makedirs(self.served_dir)
        os.makedirs(self.sources_dir)

        for name, value in (
                ("AUDIO_DIR", self.audio_dir),
                ("SERVED_MUSIC_DIR", self.served_dir),
                ("TRACK_TABLE_PATH", os.path.join(root, "music_tracks.json")),
                ("CUE_TABLE_PATH", os.path.join(self.audio_dir, "cues.json")),
                ("CREDITS_PATH", os.path.join(self.audio_dir, "CREDITS.md")),
                ("CLIENT_CONSTANTS_PATH", os.path.join(root, "constants.gd"))):
            patch = mock.patch.object(paths, name, value)
            patch.start()
            self.addCleanup(patch.stop)

        sources = mock.patch.object(pipeline_paths, "SOURCES_DIR",
                                    self.sources_dir)
        sources.start()
        self.addCleanup(sources.stop)

        with open(paths.CLIENT_CONSTANTS_PATH, "w", encoding="utf-8") as out:
            out.write('const MOMENT_A := "a"\n')

        tracks.write_table((), paths.TRACK_TABLE_PATH)

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

    def _track(self, key, served=True, credited=True, sourced=True,
               **changes):
        """Write one track row, with its served file, row and source."""
        track = music_tracks.Track(key=key, name="A Track",
                                   area=areas.DEFAULT_AREA,
                                   unlock=music_tracks.UNLOCK_AREA,
                                   unlock_key="", hint="", note="A note.")
        track = dataclasses.replace(track, **changes)
        rows = tracks.with_track(tracks.read_table(paths.TRACK_TABLE_PATH),
                                 track)
        tracks.write_table(rows, paths.TRACK_TABLE_PATH)

        if served:
            with open(paths.track_path(key), "wb") as handle:
                handle.write(b"OggS")

        if credited:
            text = credits.read_credits(paths.CREDITS_PATH)
            row = credits.render_row(tracks.served_relative(key), "X.flac", "")
            credits.write_credits(credits.with_row(text, "A — Pack", row),
                                  paths.CREDITS_PATH)

        if sourced:
            directory = paths.source_dir(key)
            os.makedirs(directory)

            with open(os.path.join(directory, "source.toml"), "w",
                      encoding="utf-8") as handle:
                handle.write('title = "A"\nauthor = "B"\nurl = "C"\n'
                             'site = "D"\nlicense = "CC0-1.0"\n'
                             'retrieved = 2026-11-08\n')

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

    def test_a_whole_track_passes(self):
        self._world({"a": "sfx/a.wav"}, {}, ["sfx/a.wav"], ["sfx/a.wav"])
        self._track("whole")

        self.assertEqual(check.run_check().problems, [])

    def test_a_track_with_no_served_file_no_row_and_no_source_fails(self):
        self._world({"a": "sfx/a.wav"}, {}, ["sfx/a.wav"], ["sfx/a.wav"])
        self._track("bare", served=False, credited=False, sourced=False)
        problems = "\n".join(check.run_check().problems)

        self.assertIn("is not there", problems)
        self.assertIn("no row in CREDITS.md", problems)
        self.assertIn("no source record", problems)

    def test_a_served_file_that_no_track_names_fails(self):
        self._world({"a": "sfx/a.wav"}, {}, ["sfx/a.wav"], ["sfx/a.wav"])

        with open(paths.track_path("stray"), "wb") as handle:
            handle.write(b"OggS")

        problems = "\n".join(check.run_check().problems)

        self.assertIn("stray", problems)
        self.assertIn("names no track", problems)

    def test_a_track_of_an_unknown_area_fails(self):
        self._world({"a": "sfx/a.wav"}, {}, ["sfx/a.wav"], ["sfx/a.wav"])
        self._track("lost", area="no_such_area")
        problems = "\n".join(check.run_check().problems)

        self.assertIn("no_such_area", problems)

    def test_a_track_table_that_does_not_read_fails(self):
        self._world({"a": "sfx/a.wav"}, {}, ["sfx/a.wav"], ["sfx/a.wav"])

        with open(paths.TRACK_TABLE_PATH, "w", encoding="utf-8") as handle:
            handle.write("{not json")

        self.assertFalse(check.run_check().ok)


class TrackTableTests(unittest.TestCase):
    """The track table writer gives the bytes of the Tables tab, and an
    empty table reads."""

    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.addCleanup(self._folder.cleanup)
        self.path = os.path.join(self._folder.name, "music_tracks.json")

    def test_an_empty_table_reads_back_empty(self):
        tracks.write_table((), self.path)

        self.assertEqual(tracks.read_table(self.path), ())

    def test_a_table_reads_back_as_it_was_written(self):
        track = music_tracks.Track(key="a", name="A", area=areas.DEFAULT_AREA,
                                   unlock=music_tracks.UNLOCK_AREA,
                                   unlock_key="", hint="", note="A note.")
        rows = tracks.with_track((), track)
        tracks.write_table(rows, self.path)

        self.assertEqual(tracks.read_table(self.path), rows)

    def test_the_text_has_a_tab_indent_and_sorted_keys(self):
        track = music_tracks.Track(key="a", name="A", area=areas.DEFAULT_AREA,
                                   unlock=music_tracks.UNLOCK_AREA,
                                   unlock_key="", hint="", note="A note.")
        text = tracks.render_table((track,))
        lines = text.splitlines()

        self.assertEqual(lines[0], "{")
        self.assertTrue(lines[1].startswith('\t"format"'))
        self.assertLess(text.index('"area"'), text.index('"key"'))
        self.assertTrue(text.endswith("}\n"))

    def test_the_served_name_and_the_source_id_come_from_the_key(self):
        self.assertEqual(tracks.served_relative("a_track"),
                         "music/a_track" + music_tracks.SERVED_SUFFIX)
        self.assertEqual(tracks.source_ids((music_tracks.Track(
            key="a_track", name="A", area=areas.DEFAULT_AREA,
            unlock=music_tracks.UNLOCK_AREA, unlock_key="", hint="",
            note="A note."),)), {music_tracks.source_id_for("a_track")})


if __name__ == "__main__":
    unittest.main()
