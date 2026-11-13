"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/26/2026
Description: Guard the sound wizard, `python -m assets.audio add`.

             Each test gives the wizard a scripted console: one answer for
             each question, in order. The test fails when the wizard asks one
             question more than the script answers, and when an answer is
             left over. Thus, a new question or a lost question is loud.

             THE PROMISES THAT THESE TESTS KEEP:
               - The wizard writes nothing before the confirm. A no, or a
                 Ctrl+C, leaves each file as it was.
               - What it writes reads back through the modules that own the
                 files: cue_table.read_table, credits.packs_of, and the
                 check.
               - A question refuses what the check refuses: a taken cue, a
                 sound clip that is there already, a suffix of another kind,
                 and a credits cell that breaks the table.
               - A moment that no cue plays is on offer, and a number picks
                 it.

             Each test points the paths of assets/audio at a temporary
             folder. Thus, no test touches godot/audio/. No test needs Godot
             or ffmpeg: find_godot, run_import, find_ffmpeg and run_encode
             are patched.

             THE TRACK FLOW (DESIGN-0016) has its own class. Its promises:
               - A track writes the source record of its master, the served
                 file, the credits row and the table row, and the check
                 passes on them.
               - The master never enters git: the source is local.
               - A machine with no ffmpeg gets no question and no write.
               - The title and the area come from the folder and the file
                 name of the master, and a yes takes each guess.
"""

import os
import tempfile
import unittest
from unittest import mock

# assets/ is import-safe by design: it touches no database.
from assets.audio import (check, credits, cue_table, encode, godot_import,
                          kinds, packs, paths, tracks, wizard)
from assets.pipeline import figure, licenses, questions, sources
from assets.pipeline import paths as pipeline_paths
from world import areas, music_tracks


_YES = "y"
_NO = "n"
_ENTER = ""

# The rows of the kind question, in the order of kinds.KINDS.
_SFX_ROW = str(list(kinds.KINDS).index(kinds.SFX_KIND) + 1)
_MUSIC_ROW = str(list(kinds.KINDS).index(kinds.MUSIC_KIND) + 1)
_FLAC_BODY = b"fLaC...."
_PACK_FOLDER = "Sound FX Starter Pack Vol. 1"
_PACK_HEADING = "Ovani Sound — " + _PACK_FOLDER
_OTHER_HEADING = "Enzo — Flesh and Fracture - Lite"
_CLIP_BODY = b"RIFF....WAVEfmt "

# The moments of the fixture constants file. The cue table maps the first
# one, so the other two are on offer, in this order.
_MAPPED_MOMENT = "task_complete"
_FREE_MOMENTS = ("guns_shot", "rain_start")
_CONSTANTS_TEXT = """# Game moments -- what a client can mark with a sound.
const MOMENT_TASK_COMPLETE := "task_complete"
const MOMENT_GUNS_SHOT := "guns_shot"
const MOMENT_RAIN_START := "rain_start"
"""

_CREDITS_TEXT = """# Audio credits

Every clip under `audio/`.

---

## %s

Royalty-free licence.

| Clip | Source file in the pack | Changes |
|---|---|---|
| `sfx/level_up.wav` | `Jingles & Stingers/Level Up.wav` | Renamed. |

## %s

Bought by Nick.

| Clip | Source file in the pack | Changes |
|---|---|---|
| `sfx/task_complete.wav` | `Flesh/Tear.wav` | Renamed. |
""" % (_PACK_HEADING, _OTHER_HEADING)


class _OutOfAnswers(AssertionError):
    """The wizard asked one question more than the script answers."""


def _scripted(answers, picked=""):
    """
    Purpose: Make a console that answers from a list.

    Entry:
        answers holds one text for each question. For an exception class
        in it, the console raises it at that question, as Ctrl+C does.

    Exit/Returns:
        Returns (console, the lines said, the answers left, the dialog
        calls).
    """
    queue = list(answers)
    said = []
    dialogs = []

    def ask(_prompt):
        if not queue:
            raise _OutOfAnswers("no answer left. The last lines: %s"
                                % said[-4:])

        answer = queue.pop(0)

        if isinstance(answer, type) and issubclass(answer, BaseException):
            raise answer

        return answer

    def pick_file():
        dialogs.append(picked)
        return picked

    console = questions.Console(ask=ask, say=said.append, pick_file=pick_file)

    return console, said, queue, dialogs


def _license_row(spdx):
    """Give the number of an allowed license in the license list."""
    allowed = list(licenses.ALLOWED_LICENSES)

    return str(allowed.index(spdx) + 1)


def _new_pack_row(text):
    """Give the number of the row for a new sound pack."""
    return str(len(credits.packs_of(text)) + 1)


def _no_moment_row():
    """Give the number of the row for no moment."""
    return str(len(_FREE_MOMENTS) + 1)


class _SoundWizardTestCase(unittest.TestCase):
    """A temporary godot/audio/, sound pack folder, and constants file."""

    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.addCleanup(self._folder.cleanup)
        self.root = self._folder.name
        project = os.path.join(self.root, "godot")
        self.audio_dir = os.path.join(project, "audio")
        self.table_path = os.path.join(self.audio_dir, "cues.json")
        self.credits_path = os.path.join(self.audio_dir, "CREDITS.md")
        self.constants_path = os.path.join(project, "blackout_constants.gd")
        self.packs_dir = os.path.join(self.root, "packs")
        self.downloads = os.path.join(self.root, "downloads")
        self.served_dir = os.path.join(self.root, "served", "music")
        self.tracks_path = os.path.join(self.root, "tables",
                                        "music_tracks.json")
        self.sources_dir = os.path.join(self.root, "sources")

        for name, value in (("REPO_DIR", self.root),
                            ("GODOT_PROJECT_DIR", project),
                            ("AUDIO_DIR", self.audio_dir),
                            ("CUE_TABLE_PATH", self.table_path),
                            ("CREDITS_PATH", self.credits_path),
                            ("CLIENT_CONSTANTS_PATH", self.constants_path),
                            ("PACKS_DIR", self.packs_dir),
                            ("SERVED_MUSIC_DIR", self.served_dir),
                            ("TRACK_TABLE_PATH", self.tracks_path)):
            patch = mock.patch.object(paths, name, value)
            patch.start()
            self.addCleanup(patch.stop)

        sources_patch = mock.patch.object(pipeline_paths, "SOURCES_DIR",
                                          self.sources_dir)
        sources_patch.start()
        self.addCleanup(sources_patch.stop)

        for target, name in ((godot_import, "find_godot"),
                             (encode, "find_ffmpeg")):
            patch = mock.patch.object(target, name, return_value="")
            patch.start()
            self.addCleanup(patch.stop)

        self._write_world()

    def _file(self, path, body):
        """Write one file, text or bytes, and give its path."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        mode = "wb" if isinstance(body, bytes) else "w"
        encoding = None if isinstance(body, bytes) else "utf-8"

        with open(path, mode, encoding=encoding) as handle:
            handle.write(body)

        return path

    def _write_world(self):
        """Write two cues with their sound clips, the credits, and the
        constants file."""
        cues = {}

        for key in ("level_up", _MAPPED_MOMENT):
            clip = cue_table.clip_for("sfx", key, ".wav")
            self._file(paths.clip_path(clip), _CLIP_BODY)
            self._file(cue_table.import_path(clip), 'uid="uid://x"\n')
            cues[key] = cue_table.Cue(key=key, kind=kinds.SFX_KIND, clip=clip,
                                      note="A note.")

        table = cue_table.CueTable(cues=cues,
                                   moments={_MAPPED_MOMENT: _MAPPED_MOMENT})
        cue_table.write_table(table, self.table_path)
        self._file(self.credits_path, _CREDITS_TEXT)
        self._file(self.constants_path, _CONSTANTS_TEXT)
        os.makedirs(os.path.dirname(self.tracks_path))
        os.makedirs(self.sources_dir)
        tracks.write_table((), self.tracks_path)

    def _pack_clip(self, name="Titan Handgun.wav"):
        """Write one sound clip into the sound pack folder."""
        path = os.path.join(self.packs_dir, _PACK_FOLDER, "Hollywood", name)

        return self._file(path, _CLIP_BODY)

    def _download(self, name):
        """Write one file outside the sound pack folder."""
        return self._file(os.path.join(self.downloads, name), _CLIP_BODY)

    def _snapshot(self):
        """Give each file that the wizard can write, with its bytes."""
        found = {}

        for root in (self.audio_dir, self.served_dir, self.sources_dir,
                     os.path.dirname(self.tracks_path)):
            for parent, _folders, names in os.walk(root):
                for name in names:
                    path = os.path.join(parent, name)

                    with open(path, "rb") as handle:
                        found[path] = handle.read()

        return found

    def _run(self, answers, picked=""):
        """Run the wizard on a script, and check that it used each answer."""
        console, said, left, dialogs = _scripted(answers, picked)
        result = wizard.run(console)
        self.assertEqual(left, [], "the wizard asked fewer questions")

        return result, said, dialogs

    def _free_moment_answers(self, path, confirm=_YES):
        """Pick the first free moment for a sound clip from the known pack."""
        return [_SFX_ROW, path, _YES, _ENTER, "1", _ENTER, confirm]


class FreeMomentTests(_SoundWizardTestCase):
    """A moment that no cue plays becomes a cue, from a known pack."""

    def test_the_wizard_writes_the_clip_the_import_the_cue_and_the_row(self):
        upload = self._pack_clip()
        result, _said, _dialogs = self._run(self._free_moment_answers(upload))
        moment = _FREE_MOMENTS[0]
        clip = cue_table.clip_for("sfx", moment, ".wav")
        table = cue_table.read_table(self.table_path)

        self.assertEqual((result.cue, result.moment, result.clip),
                         (moment, moment, clip))
        self.assertFalse(result.imported)
        self.assertEqual(table.cues[moment].clip, clip)
        self.assertEqual(table.cues[moment].kind, kinds.SFX_KIND)
        self.assertEqual(table.moments[moment], moment)
        self.assertIn("level_up", table.cues)

        with open(paths.clip_path(clip), "rb") as handle:
            self.assertEqual(handle.read(), _CLIP_BODY)

        with open(cue_table.import_path(clip), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), kinds.render_import(
                kinds.KINDS[kinds.SFX_KIND]))

    def test_the_row_goes_under_the_pack_of_the_folder(self):
        upload = self._pack_clip()
        self._run(self._free_moment_answers(upload))
        text = credits.read_credits(self.credits_path)
        packs = {pack.heading: pack.clips for pack in credits.packs_of(text)}
        clip = cue_table.clip_for("sfx", _FREE_MOMENTS[0], ".wav")

        self.assertEqual(packs[_PACK_HEADING], ("sfx/level_up.wav", clip))
        self.assertEqual(packs[_OTHER_HEADING], ("sfx/task_complete.wav",))
        self.assertIn("`Hollywood/Titan Handgun.wav`", text)
        self.assertIn("mono", text.lower())

    def test_what_the_wizard_writes_passes_the_check(self):
        upload = self._pack_clip()
        self._run(self._free_moment_answers(upload))
        report = check.run_check()

        self.assertEqual(report.problems, [])

    def test_the_note_of_a_moment_names_it_by_default(self):
        upload = self._pack_clip()
        self._run(self._free_moment_answers(upload))
        table = cue_table.read_table(self.table_path)

        self.assertIn(_FREE_MOMENTS[0], table.cues[_FREE_MOMENTS[0]].note)


class NothingWrittenTests(_SoundWizardTestCase):
    """A no at the confirm, or a Ctrl+C, leaves each file as it was."""

    def test_a_no_at_the_confirm_writes_nothing(self):
        upload = self._pack_clip()
        before = self._snapshot()
        result, said, _dialogs = self._run(
            self._free_moment_answers(upload, confirm=_NO))

        self.assertIsNone(result)
        self.assertEqual(self._snapshot(), before)
        self.assertIn("nothing was written", said[-1].lower())

    def test_ctrl_c_at_a_question_writes_nothing(self):
        upload = self._pack_clip()
        before = self._snapshot()
        result, _said, _dialogs = self._run([_SFX_ROW, upload, _YES, _ENTER,
                                             "1", KeyboardInterrupt])

        self.assertIsNone(result)
        self.assertEqual(self._snapshot(), before)


class NewPackTests(_SoundWizardTestCase):
    """A sound clip from a new pack gets a section of its own."""

    def _new_pack_answers(self, path):
        """Answer the questions of a new CC BY pack with no moment."""
        return [_SFX_ROW, path, _new_pack_row(_CREDITS_TEXT), "Weather Kit",
                "Sonniss", _license_row("CC-BY-4.0"),
                "https://sonniss.com/weather", _ENTER, _ENTER,
                _no_moment_row(), "Rain on a tin roof.", _YES]

    def test_a_new_pack_is_a_section_at_the_end(self):
        upload = self._download("Rain Loop.wav")
        result, _said, _dialogs = self._run(self._new_pack_answers(upload))
        text = credits.read_credits(self.credits_path)
        last = credits.packs_of(text)[-1]
        terms = licenses.ALLOWED_LICENSES["CC-BY-4.0"]

        self.assertEqual(last.heading, "Sonniss — Weather Kit")
        self.assertEqual(last.clips, (result.clip,))
        self.assertIn(terms.name, text)
        self.assertIn("https://sonniss.com/weather", text)
        self.assertIn("`Rain Loop.wav`", text)

    def test_a_cue_with_no_moment_maps_no_moment(self):
        upload = self._download("Rain Loop.wav")
        result, _said, _dialogs = self._run(self._new_pack_answers(upload))
        table = cue_table.read_table(self.table_path)

        self.assertEqual(result.cue, "rain_loop")
        self.assertEqual(result.moment, "")
        self.assertNotIn("rain_loop", table.moments.values())
        self.assertEqual(sorted(table.moments), [_MAPPED_MOMENT])

    def test_the_next_steps_tell_how_to_play_a_cue_with_no_moment(self):
        upload = self._download("Rain Loop.wav")
        result, _said, _dialogs = self._run(self._new_pack_answers(upload))
        steps = "\n".join(wizard.next_steps(result))

        self.assertIn("SoundCues.play", steps)
        self.assertIn("moments", steps)
        self.assertIn("import", steps.lower())


class RefusalTests(_SoundWizardTestCase):
    """Each question refuses what the check refuses."""

    def test_a_taken_cue_and_a_clip_that_is_there_are_refused(self):
        upload = self._pack_clip()
        self._file(paths.clip_path("sfx/orphan.wav"), _CLIP_BODY)
        answers = [_SFX_ROW, upload, _YES, _ENTER, "level_up", _MAPPED_MOMENT,
                   "orphan", "thunder", _no_moment_row(), "Thunder.", _NO]
        _result, said, _dialogs = self._run(answers)
        text = "\n".join(said)

        self.assertEqual(text.count("has the cue"), 2)
        self.assertIn("there already", text)

    def test_a_path_that_is_no_sound_clip_is_refused(self):
        upload = self._pack_clip()
        other = self._download("theme.mp3")
        missing = os.path.join(self.downloads, "missing.wav")
        answers = [_SFX_ROW, missing, other, _ENTER, upload, _YES, _ENTER,
                   "1", _ENTER, _NO]
        _result, said, _dialogs = self._run(answers)
        text = "\n".join(said)

        self.assertIn("is not a file", text)
        self.assertIn("not a sound clip of this kind", text)
        self.assertIn("No file was chosen", text)

    def test_a_credits_cell_that_breaks_the_table_is_refused(self):
        upload = self._pack_clip()
        answers = [_SFX_ROW, upload, _YES, "Hollywood/a|b.wav", _ENTER, "1",
                   _ENTER, _NO]
        _result, said, _dialogs = self._run(answers)

        self.assertIn("cannot hold", "\n".join(said))

    def test_enter_at_the_path_opens_the_file_dialog(self):
        upload = self._pack_clip()
        answers = [_SFX_ROW, _ENTER, _YES, _ENTER, "1", _ENTER, _NO]
        _result, _said, dialogs = self._run(answers, picked=upload)

        self.assertEqual(dialogs, [upload])


class ImportTests(_SoundWizardTestCase):
    """The wizard imports the new sound clip when Godot is there."""

    def _fake_import(self, clip):
        """Act as Godot does: add the uid line to the .import file."""
        def run_import(_executable):
            with open(cue_table.import_path(clip), "a",
                      encoding="utf-8") as handle:
                handle.write('uid="uid://test"\n')

            return ""

        return run_import

    def test_a_yes_imports_the_clip(self):
        upload = self._pack_clip()
        clip = cue_table.clip_for("sfx", _FREE_MOMENTS[0], ".wav")
        answers = self._free_moment_answers(upload) + [_YES]

        with mock.patch.object(godot_import, "find_godot",
                               return_value="godot.exe"), \
                mock.patch.object(godot_import, "run_import",
                                  side_effect=self._fake_import(clip)):
            result, _said, _dialogs = self._run(answers)

        steps = "\n".join(wizard.next_steps(result))

        self.assertTrue(result.imported)
        self.assertNotIn("Import it", steps)

    def test_a_failed_import_is_reported(self):
        upload = self._pack_clip()
        answers = self._free_moment_answers(upload) + [_YES]

        with mock.patch.object(godot_import, "find_godot",
                               return_value="godot.exe"), \
                mock.patch.object(godot_import, "run_import",
                                  return_value="Godot ended with code 1"):
            result, said, _dialogs = self._run(answers)

        self.assertFalse(result.imported)
        self.assertIn("ended with code 1", "\n".join(said))

    def test_no_godot_asks_no_import_question(self):
        upload = self._pack_clip()
        result, said, _dialogs = self._run(self._free_moment_answers(upload))

        self.assertFalse(result.imported)
        self.assertIn("GODOT_BIN", "\n".join(said))


class _TrackTestCase(_SoundWizardTestCase):
    """The track flow, with a master in a folder that names an area, and
    an ffmpeg that writes bytes."""

    def setUp(self):
        super().setUp()
        self.area = list(areas.AREAS)[-1]
        self.area_name = areas.AREAS[self.area].name
        self.title = "Frigid Memory"
        self.key = questions.as_key(self.title)
        encodes = mock.patch.object(encode, "run_encode",
                                    side_effect=self._fake_encode)
        encodes.start()
        self.addCleanup(encodes.stop)
        self.encoded = []

    def _fake_encode(self, _executable, master, output):
        """Act as ffmpeg does: write the output file."""
        self.encoded.append((master, output))

        with open(output, "wb") as handle:
            handle.write(b"OggS")

        return ""

    def _with_ffmpeg(self):
        """Give the wizard an ffmpeg."""
        patch = mock.patch.object(encode, "find_ffmpeg",
                                  return_value="ffmpeg.exe")
        patch.start()
        self.addCleanup(patch.stop)

    def _master(self, name=None):
        """Write one master under Areas/<Area name>/."""
        name = name or "%s %s.flac" % (self.area_name, self.title)
        path = os.path.join(self.downloads, "Areas", self.area_name, name)

        return self._file(path, _FLAC_BODY)

    def _own_track_answers(self, path, confirm=_YES):
        """Take each guess of a track that Nick wrote, with an area unlock."""
        return [_MUSIC_ROW, path, _YES, _ENTER, _ENTER, _YES, "1", _ENTER,
                _ENTER, confirm]


class TrackTests(_TrackTestCase):
    """A track that Nick wrote lands in each of its four places."""

    def test_the_wizard_writes_the_source_the_file_the_row_and_the_track(self):
        self._with_ffmpeg()
        master = self._master()
        result, _said, _dialogs = self._run(self._own_track_answers(master))
        rows = tracks.read_table(self.tracks_path)
        source = sources.load_source(music_tracks.source_id_for(self.key))

        self.assertEqual(result.track, self.key)
        self.assertEqual([row.key for row in rows], [self.key])
        self.assertEqual(rows[0].name, self.title)
        self.assertEqual(rows[0].area, self.area)
        self.assertEqual(rows[0].unlock, music_tracks.UNLOCK_AREA)
        self.assertTrue(os.path.isfile(paths.track_path(self.key)))
        self.assertTrue(source.local)
        self.assertEqual(source.license, licenses.OWNED_LICENSE)
        self.assertEqual(source.author, figure.DEFAULT_AUTHOR)
        self.assertEqual(list(source.files), [os.path.basename(master)])
        self.assertEqual(sources.gitignore_problem(source), "")

    def test_the_encode_reads_the_copy_and_writes_the_served_file(self):
        self._with_ffmpeg()
        master = self._master()
        self._run(self._own_track_answers(master))
        copy = os.path.join(paths.source_dir(self.key),
                            os.path.basename(master))

        self.assertEqual(self.encoded, [(copy, paths.track_path(self.key))])

    def test_the_row_goes_under_the_own_section(self):
        self._with_ffmpeg()
        master = self._master()
        self._run(self._own_track_answers(master))
        text = credits.read_credits(self.credits_path)
        last = credits.packs_of(text)[-1]

        self.assertEqual(last.heading, "%s — %s" % (figure.DEFAULT_AUTHOR,
                                                   packs.OWN_PACK_TITLE))
        self.assertEqual(last.clips, (tracks.served_relative(self.key),))
        self.assertIn(licenses.ALLOWED_LICENSES[licenses.OWNED_LICENSE].name,
                      text)

    def test_what_the_wizard_writes_passes_the_check(self):
        self._with_ffmpeg()
        master = self._master()
        self._run(self._own_track_answers(master))
        report = check.run_check()

        self.assertEqual(report.problems, [])

    def test_a_second_track_goes_under_the_same_section(self):
        self._with_ffmpeg()
        self._run(self._own_track_answers(self._master()))
        second = self._master("%s Second.flac" % self.area_name)
        self._run(self._own_track_answers(second))
        text = credits.read_credits(self.credits_path)
        own = [pack for pack in credits.packs_of(text)
               if packs.OWN_PACK_TITLE in pack.heading]
        rows = tracks.read_table(self.tracks_path)

        self.assertEqual(len(own), 1)
        self.assertEqual(len(own[0].clips), 2)
        self.assertEqual([row.key for row in rows], [self.key, "second"])

    def test_the_next_steps_name_the_restart_and_the_check(self):
        self._with_ffmpeg()
        result, _said, _dialogs = self._run(
            self._own_track_answers(self._master()))
        steps = "\n".join(wizard.next_steps(result))

        self.assertIn("Restart the server", steps)
        self.assertIn("check", steps)


class TrackQuestionTests(_TrackTestCase):
    """The guesses, the refusals, and the pack of a track that is not
    Nick's."""

    def test_the_area_list_comes_when_the_guess_is_refused(self):
        self._with_ffmpeg()
        master = self._master()
        row = str(list(areas.AREAS).index(areas.DEFAULT_AREA) + 1)
        answers = [_MUSIC_ROW, master, _YES, _ENTER, _ENTER, _NO, row, "1",
                   _ENTER, _ENTER, _YES]
        self._run(answers)
        rows = tracks.read_table(self.tracks_path)

        self.assertEqual(rows[0].area, areas.DEFAULT_AREA)

    def test_a_folder_that_names_no_area_asks_the_list(self):
        self._with_ffmpeg()
        master = self._file(os.path.join(self.downloads, "Loose.flac"),
                            _FLAC_BODY)
        row = str(list(areas.AREAS).index(self.area) + 1)
        answers = [_MUSIC_ROW, master, _YES, _ENTER, _ENTER, row, "1",
                   _ENTER, _ENTER, _YES]
        self._run(answers)
        rows = tracks.read_table(self.tracks_path)

        self.assertEqual(rows[0].key, "loose")
        self.assertEqual(rows[0].area, self.area)

    def test_a_quest_unlock_asks_the_quest_key(self):
        self._with_ffmpeg()
        quest_row = str(music_tracks.UNLOCKS.index(music_tracks.UNLOCK_QUEST)
                        + 1)
        answers = [_MUSIC_ROW, self._master(), _YES, _ENTER, _ENTER, _YES,
                   quest_row, "a_quest", "Finish the quest.", _ENTER, _YES]
        self._run(answers)
        rows = tracks.read_table(self.tracks_path)

        self.assertEqual(rows[0].unlock, music_tracks.UNLOCK_QUEST)
        self.assertEqual(rows[0].unlock_key, "a_quest")
        self.assertEqual(rows[0].hint, "Finish the quest.")

    def test_a_taken_key_and_a_bad_key_are_refused(self):
        self._with_ffmpeg()
        self._run(self._own_track_answers(self._master()))
        second = self._master("%s Second.flac" % self.area_name)
        answers = [_MUSIC_ROW, second, _YES, _ENTER, self.key, "Bad Key",
                   "other", _YES, "1", _ENTER, _ENTER, _NO]
        _result, said, _dialogs = self._run(answers)
        text = "\n".join(said)

        self.assertIn("already", text)
        self.assertIn("a-z", text)

    def test_a_master_that_is_no_flac_is_refused(self):
        self._with_ffmpeg()
        wav = self._pack_clip()
        answers = [_MUSIC_ROW, wav, self._master(), _YES, _ENTER, _ENTER,
                   _YES, "1", _ENTER, _ENTER, _NO]
        _result, said, _dialogs = self._run(answers)

        self.assertIn("not a sound clip of this kind", "\n".join(said))

    def test_a_track_of_a_pack_records_its_license(self):
        self._with_ffmpeg()
        master = self._master()
        answers = [_MUSIC_ROW, master, _NO, "Ambient Kit", "Sonniss",
                   _license_row("CC0-1.0"), "https://sonniss.com/ambient",
                   _ENTER, _ENTER, _YES, "1", _ENTER, _ENTER, _YES]
        self._run(answers)
        source = sources.load_source(music_tracks.source_id_for(self.key))
        text = credits.read_credits(self.credits_path)

        self.assertEqual(source.license, "CC0-1.0")
        self.assertEqual(source.site, "sonniss.com")
        self.assertTrue(source.local)
        self.assertEqual(credits.packs_of(text)[-1].heading,
                         "Sonniss — Ambient Kit")


class TrackNothingWrittenTests(_TrackTestCase):
    """No ffmpeg, a no, or a Ctrl+C leaves each file as it was."""

    def test_no_ffmpeg_asks_no_question(self):
        before = self._snapshot()
        result, said, _dialogs = self._run([_MUSIC_ROW])

        self.assertIsNone(result)
        self.assertIn("FFMPEG_BIN", "\n".join(said))
        self.assertEqual(self._snapshot(), before)

    def test_a_no_at_the_confirm_writes_nothing(self):
        self._with_ffmpeg()
        master = self._master()
        before = self._snapshot()
        result, _said, _dialogs = self._run(
            self._own_track_answers(master, confirm=_NO))

        self.assertIsNone(result)
        self.assertEqual(self._snapshot(), before)
        self.assertEqual(self.encoded, [])

    def test_ctrl_c_at_a_question_writes_nothing(self):
        self._with_ffmpeg()
        master = self._master()
        before = self._snapshot()
        result, _said, _dialogs = self._run([_MUSIC_ROW, master, _YES,
                                             KeyboardInterrupt])

        self.assertIsNone(result)
        self.assertEqual(self._snapshot(), before)


if __name__ == "__main__":
    unittest.main()
