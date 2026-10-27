"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/25/2026
Description: Guard the model wizard, `python -m assets.pipeline add`.

             Each test gives the wizard a scripted console: one answer for
             each question, in order. The test fails when the wizard asks one
             question more than the script answers, and when an answer is
             left over. Thus, a new question or a lost question is loud.

             THE PROMISES THAT THESE TESTS KEEP:
               - The wizard writes nothing before the confirm. A no, or a
                 Ctrl+C, leaves sources/ and models/ empty.
               - What it writes loads back through the modules that own
                 the files: sources.load_source, records.load_all, and the
                 license gate.
               - A question refuses what the build refuses: a taken key, a
                 base that is an alias, a license with no exception.
               - An asset key or an alias that the key list does not name
                 needs a yes. The wizard offers each key that the list names
                 and no record has.

             Each test points paths.SOURCES_DIR and paths.MODELS_DIR at a
             temporary directory, so no test touches the sources in git.
             paths.KEY_LIST_PATH points at a file that is not there, unless
             a test writes one. The real key list thus changes no question.
             No test needs the network, Node or Blender. The Poly Haven
             test gives fetch a fake API.
"""

import ast
import hashlib
import json
import os
import tempfile
import unittest
import zipfile
from unittest import mock

# assets/ is import-safe by design: it touches no database.
from assets.pipeline import (blender, build, fetch, licenses, paths, picocad,
                             questions, records, sources, wizard)


_YES = "y"
_NO = "n"
_ENTER = ""
_FAMILY = "items"
_AUTHOR = "Kenney"
_URL = "https://kenney.itch.io/crate-pack"
_PICOCAD_TEXT = "picocad;art;1;0;0\n{}%\n"


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


def _origin_row(writer):
    """Give the number of the origin row whose source write is writer."""
    writers = [row[wizard._ROW_WRITER] for row in wizard._ORIGINS]

    return str(writers.index(writer) + 1)


def _license_row(spdx):
    """Give the number of an allowed license in the license list."""
    allowed = list(licenses.ALLOWED_LICENSES)

    return str(allowed.index(spdx) + 1)


def _another_license_row():
    """Give the number of the row for a license that is not allowed."""
    return str(len(licenses.ALLOWED_LICENSES) + 1)


def _family_row(family):
    """Give the number of one family in the family list."""
    return str(wizard._families().index(family) + 1)


def _md5(body):
    """Give the MD5 of bytes as the Poly Haven API gives it."""
    return hashlib.md5(body).hexdigest()


class _WizardTestCase(unittest.TestCase):
    """A temporary sources/ and models/, and a machine that can build."""

    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.addCleanup(self._folder.cleanup)
        self.root = self._folder.name
        self.sources_dir = os.path.join(self.root, "sources")
        self.models_dir = os.path.join(self.root, "models")
        self.downloads = os.path.join(self.root, "downloads")

        self.key_list_path = os.path.join(self.root, "key_list.json")
        self.looks_dir = os.path.join(self.root, "looks")

        for folder in (self.sources_dir, self.models_dir, self.downloads):
            os.makedirs(folder)

        for name, value in (("SOURCES_DIR", self.sources_dir),
                            ("MODELS_DIR", self.models_dir),
                            ("KEY_LIST_PATH", self.key_list_path),
                            ("FIGURE_LOOKS_DIR", self.looks_dir)):
            patch = mock.patch.object(paths, name, value)
            patch.start()
            self.addCleanup(patch.stop)

        tools = mock.patch.object(build, "tools_problem", return_value="")
        tools.start()
        self.addCleanup(tools.stop)

    def _download(self, name, body=b"glTF"):
        """Write one file into the downloads folder, and give its path."""
        path = os.path.join(self.downloads, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, "wb") as handle:
            handle.write(body)

        return path

    def _upload_answers(self, path, license_answers=None, title=_ENTER,
                        model_answers=(), key_answers=(_ENTER,),
                        alias_answers=(_ENTER,), variant_answers=(_ENTER,),
                        confirm=_YES):
        """Give the answers for an upload, with the defaults elsewhere."""
        if license_answers is None:
            license_answers = (_license_row("CC0-1.0"),)

        answers = [_origin_row(wizard._write_upload), path]
        answers += list(license_answers)
        answers += [title, _AUTHOR, _URL, _ENTER, _ENTER, _ENTER]
        answers += list(model_answers)
        answers += [_family_row(_FAMILY)]
        answers += list(key_answers) + list(alias_answers)
        answers += list(variant_answers) + [confirm]

        if confirm == _YES:
            answers.append(_NO)

        return answers

    def _run(self, answers, picked=""):
        """Run the wizard on a script, and check that it used each answer."""
        console, said, left, dialogs = _scripted(answers, picked)
        result = wizard.run(console)
        self.assertEqual(left, [], "the wizard asked fewer questions")

        return result, said, dialogs

    def _existing_source(self, source_id, names, license="CC0-1.0"):
        """Make a source in the temporary sources/ that holds names."""
        folder = os.path.join(self.downloads, source_id)

        for name in names:
            self._download(os.path.join(source_id, name))

        fields = fetch.SourceFields(title="Kit", author=_AUTHOR, url=_URL,
                                    site="itch.io", license=license)
        fetch.fetch_file(folder, source_id, fields)

    def _written(self):
        """Name each entry in the temporary sources/ and models/."""
        return os.listdir(self.sources_dir) + os.listdir(self.models_dir)


class UploadTests(_WizardTestCase):
    """A file, a folder or a .zip becomes a source and a model record."""

    def test_an_upload_becomes_a_sealed_source_and_a_record(self):
        path = self._download("crate.glb")
        result, _said, _dialogs = self._run(self._upload_answers(path))
        record = records.load_record(result.record_path)
        source = sources.load_source(record.source_id)

        self.assertEqual(result.asset_key, "crate")
        self.assertFalse(result.build)
        self.assertEqual((record.family, record.file), (_FAMILY, "crate.glb"))
        self.assertEqual(source.license, "CC0-1.0")
        self.assertEqual(source.author, _AUTHOR)
        self.assertEqual(source.site, "itch.io")
        self.assertIn("crate.glb", source.files)
        self.assertEqual(sources.hash_problems(source), [])
        self.assertEqual(sources.gate_problem(source), "")

    def test_the_source_id_names_the_site_and_the_download(self):
        path = self._download("crate.glb")
        result, _said, _dialogs = self._run(self._upload_answers(path))
        record = records.load_record(result.record_path)

        self.assertTrue(record.source_id.startswith("itch_"))
        self.assertTrue(record.source_id.endswith("crate"))

    def test_enter_at_the_path_question_opens_the_file_dialog(self):
        path = self._download("crate.glb")
        answers = self._upload_answers(_ENTER)
        result, _said, dialogs = self._run(answers, picked=path)

        self.assertEqual(dialogs, [path])
        self.assertEqual(result.asset_key, "crate")

    def test_a_dragged_path_in_quotes_is_accepted(self):
        path = self._download("crate.glb")
        result, _said, _dialogs = self._run(
            self._upload_answers("& '%s'" % path))

        self.assertEqual(result.asset_key, "crate")

    def test_a_path_with_no_model_file_is_asked_again(self):
        readme = self._download("readme.txt", b"Read me first.")
        path = self._download("crate.glb")
        answers = self._upload_answers(path)
        answers.insert(1, readme)
        result, said, _dialogs = self._run(answers)

        self.assertTrue(any("holds no model file" in line for line in said))
        self.assertEqual(result.asset_key, "crate")

    def test_a_zip_lists_its_model_files_and_skips_the_rest(self):
        path = os.path.join(self.downloads, "pack.zip")

        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("pack/Models/crate.fbx", b"fbx")
            archive.writestr("pack/Models/barrel.glb", b"glTF")
            archive.writestr("pack/art.txt", _PICOCAD_TEXT)
            archive.writestr("pack/readme.txt", "Read me first.")
            archive.writestr("__MACOSX/pack/Models/._crate.fbx", b"junk")

        answers = self._upload_answers(path, model_answers=("barrel", "1"))
        result, said, _dialogs = self._run(answers)
        record = records.load_record(result.record_path)
        shown = "\n".join(said)

        self.assertEqual(record.file, "pack/Models/barrel.glb")
        self.assertEqual(result.asset_key, "barrel")
        self.assertIn("pack/art.txt", shown)
        self.assertNotIn("readme.txt", shown)
        self.assertNotIn("__MACOSX", shown)

    def test_a_palette_format_gets_the_nearest_filter(self):
        for suffix in blender.PALETTE_SUFFIXES:
            with self.subTest(suffix=suffix):
                path = self._download("stove" + suffix, b"VOX ")
                result, _said, _dialogs = self._run(
                    self._upload_answers(path))
                record = records.load_record(result.record_path)

                self.assertEqual(record.filter, records.FILTER_NEAREST)

    def test_a_glb_gets_no_fix(self):
        path = self._download("crate.glb")
        result, _said, _dialogs = self._run(self._upload_answers(path))
        record = records.load_record(result.record_path)

        self.assertEqual(record.filter, records.FILTER_LINEAR)

    def test_a_title_with_quotes_and_backslashes_reads_back(self):
        title = 'The "big" crate \\ two'
        path = self._download("crate.glb")
        result, _said, _dialogs = self._run(
            self._upload_answers(path, title=title))
        record = records.load_record(result.record_path)
        source = sources.load_source(record.source_id)

        self.assertEqual(source.title, title)


class NothingWrittenTests(_WizardTestCase):
    """The wizard writes nothing before the confirm."""

    def test_a_no_at_the_confirm_writes_nothing(self):
        path = self._download("crate.glb")
        result, said, _dialogs = self._run(
            self._upload_answers(path, confirm=_NO))

        self.assertIsNone(result)
        self.assertEqual(self._written(), [])
        self.assertTrue(any("Nothing was written" in line for line in said))

    def test_ctrl_c_at_a_question_writes_nothing(self):
        path = self._download("crate.glb")
        answers = self._upload_answers(path)[:4] + [KeyboardInterrupt]
        result, said, _dialogs = self._run(answers)

        self.assertIsNone(result)
        self.assertEqual(self._written(), [])
        self.assertTrue(any("Nothing was written" in line for line in said))


class LicenseTests(_WizardTestCase):
    """The license question gives what the license gate asks for."""

    def test_a_bought_pack_becomes_a_local_source(self):
        path = self._download("crate.glb")
        answers = self._upload_answers(
            path, license_answers=(_license_row(licenses.PURCHASED_LICENSE),))
        result, _said, _dialogs = self._run(answers)
        record = records.load_record(result.record_path)
        source = sources.load_source(record.source_id)

        self.assertTrue(source.local)
        self.assertEqual(sources.gitignore_problem(source), "")
        self.assertEqual(sources.gate_problem(source), "")

    def test_another_license_needs_the_reason_of_an_exception(self):
        reason = "Nick read the page on 10/25/2026."
        path = self._download("crate.glb")
        license_answers = (_another_license_row(), "CC-BY-NC-4.0", _ENTER,
                           reason)
        result, said, _dialogs = self._run(
            self._upload_answers(path, license_answers=license_answers))
        record = records.load_record(result.record_path)
        source = sources.load_source(record.source_id)

        self.assertTrue(any("Type an answer" in line for line in said))
        self.assertEqual(source.license, "CC-BY-NC-4.0")
        self.assertEqual(source.exception, reason)
        self.assertEqual(sources.gate_problem(source), "")

    def test_a_typed_license_that_passes_the_gate_needs_no_exception(self):
        path = self._download("crate.glb")
        license_answers = (_another_license_row(), "CC-BY-4.0")
        result, _said, _dialogs = self._run(
            self._upload_answers(path, license_answers=license_answers))
        record = records.load_record(result.record_path)
        source = sources.load_source(record.source_id)

        self.assertEqual(source.license, "CC-BY-4.0")
        self.assertEqual(source.exception, "")


class KeyTests(_WizardTestCase):
    """The key questions refuse what records.load_all refuses."""

    def setUp(self):
        super().setUp()
        self._existing_source("itch_kit", ("rusty_pole.glb",))
        fetch.write_model_record(_FAMILY, "rusty_pole", "itch_kit",
                                 "rusty_pole.glb", aliases=("old_pole",))

    def test_a_taken_key_is_refused_and_asked_again(self):
        path = self._download("rusty_pole.glb")
        answers = self._upload_answers(
            path, key_answers=("old_pole", "rusty_pole", "new_pole"))
        result, said, _dialogs = self._run(answers)
        refusals = [line for line in said if "has the key" in line]

        self.assertEqual(len(refusals), 2)
        self.assertEqual(result.asset_key, "new_pole")

    def test_aliases_and_a_variant_load_back(self):
        path = self._download("bent_pole.glb")
        answers = self._upload_answers(
            path, alias_answers=("bent_a, bent_b",),
            variant_answers=("old_pole", "no_such_pole", "rusty_pole"))
        result, said, _dialogs = self._run(answers)
        loaded = {record.asset_key: record for record in records.load_all()}
        record = loaded[result.asset_key]

        self.assertEqual(record.aliases, ("bent_a", "bent_b"))
        self.assertEqual(record.variant_of, "rusty_pole")
        self.assertEqual(
            len([line for line in said if "An alias is no base" in line]), 2)

    def test_an_alias_that_a_record_has_is_refused(self):
        path = self._download("bent_pole.glb")
        answers = self._upload_answers(
            path, alias_answers=("old_pole", _ENTER))
        result, said, _dialogs = self._run(answers)
        record = records.load_record(result.record_path)

        self.assertTrue(any("has the key old_pole" in line for line in said))
        self.assertEqual(record.aliases, ())


def _key_row(key, owner, kind):
    """Give one row of a key list, as key_list.py writes it."""
    return {"key": key, "owner": owner, "kind": kind, "name": owner}


class KeyListTests(_WizardTestCase):
    """
    The asset key questions read the key list: the offer, the number that
    picks a row, and the warning about a key that the game does not name.

    The fixture: a record of the family has rusty_pole, a gatherable. The
    list names rusty_pole, copper_pole (gatherable), crate (crafting_tool),
    and gunbench (station), which the object kind gunsmith_bench owns. The
    upload is crate.glb, so the default key is crate.
    """

    def setUp(self):
        super().setUp()
        self._existing_source("itch_kit", ("rusty_pole.glb",))
        fetch.write_model_record(_FAMILY, "rusty_pole", "itch_kit",
                                 "rusty_pole.glb")
        self._write_key_list([
            _key_row("copper_pole", "copper_pole", "gatherable"),
            _key_row("crate", "crate", "crafting_tool"),
            _key_row("gunbench", "gunsmith_bench", "station"),
            _key_row("rusty_pole", "rusty_pole", "gatherable"),
        ])
        self.upload = self._download("crate.glb")

    def _write_key_list(self, rows, version=1):
        with open(self.key_list_path, "w", encoding="utf-8") as handle:
            json.dump({"format": version, "keys": rows}, handle)

    def _warnings(self, said):
        return [line for line in said if "names no entity" in line]

    def test_the_offer_shows_each_named_key_that_no_record_has(self):
        result, said, _dialogs = self._run(self._upload_answers(self.upload))
        shown = "\n".join(said)

        self.assertIn("copper_pole", shown)
        self.assertIn("gunbench", shown)
        self.assertNotIn("rusty_pole", shown)
        self.assertEqual(result.asset_key, "crate")
        self.assertEqual(self._warnings(said), [])

    def test_a_kind_that_the_family_draws_comes_first(self):
        result, _said, _dialogs = self._run(
            self._upload_answers(self.upload, key_answers=("1",)))

        self.assertEqual(result.asset_key, "copper_pole")

    def test_a_key_with_a_worn_look_is_marked_and_comes_after(self):
        # With no look, crate (crafting_tool) comes before gunbench
        # (station), by kind. The look of crate puts it after gunbench.
        os.makedirs(self.looks_dir)
        look = os.path.join(self.looks_dir, "crate" + paths.FIGURE_FILE_SUFFIX)

        with open(look, "w", encoding="utf-8") as handle:
            json.dump({"key": "crate"}, handle)

        result, said, _dialogs = self._run(
            self._upload_answers(self.upload, key_answers=("2",)))
        marked = [line for line in said if "worn look" in line]

        self.assertEqual(result.asset_key, "gunbench")
        self.assertEqual(len(marked), 1)
        self.assertIn("crate", marked[0])

    def test_an_owner_key_warns_names_its_asset_key_and_a_no_asks_again(self):
        answers = self._upload_answers(
            self.upload, key_answers=("gunsmith_bench", _NO, "gunbench"))
        result, said, _dialogs = self._run(answers)
        warnings = self._warnings(said)

        self.assertEqual(len(warnings), 1)
        self.assertIn("gunsmith_bench draws with the asset key gunbench",
                      warnings[0])
        self.assertEqual(result.asset_key, "gunbench")

    def test_a_yes_keeps_a_key_that_the_game_does_not_name(self):
        answers = self._upload_answers(self.upload,
                                       key_answers=("food_meat", _YES))
        result, said, _dialogs = self._run(answers)

        self.assertEqual(len(self._warnings(said)), 1)
        self.assertIn("family shape", self._warnings(said)[0])
        self.assertEqual(result.asset_key, "food_meat")

    def test_an_alias_that_the_game_does_not_name_warns_too(self):
        answers = self._upload_answers(
            self.upload, alias_answers=("old_crate", _NO, _ENTER))
        result, said, _dialogs = self._run(answers)
        record = records.load_record(result.record_path)

        self.assertEqual(len(self._warnings(said)), 1)
        self.assertEqual(record.aliases, ())

    def test_with_no_key_list_the_wizard_offers_and_warns_nothing(self):
        os.remove(self.key_list_path)
        answers = self._upload_answers(self.upload,
                                       key_answers=("gunsmith_bench",))
        result, said, _dialogs = self._run(answers)
        shown = "\n".join(said)

        self.assertIn("is not there", shown)
        self.assertNotIn("copper_pole", shown)
        self.assertEqual(self._warnings(said), [])
        self.assertEqual(result.asset_key, "gunsmith_bench")

    def test_the_reader_refuses_a_newer_format_and_a_short_row(self):
        newer = wizard._KEY_LIST_FORMAT + 1
        short = {"key": "crate", "owner": "crate"}

        for rows, version in (([], newer), ([short], 1)):
            with self.subTest(version=version, rows=rows):
                self._write_key_list(rows, version)

                with self.assertRaises(wizard.KeyListError):
                    wizard.read_key_list(self.key_list_path)

    def test_the_reader_refuses_a_file_that_is_not_json(self):
        with open(self.key_list_path, "w", encoding="utf-8") as handle:
            handle.write("{not json")

        with self.assertRaises(wizard.KeyListError):
            wizard.read_key_list(self.key_list_path)


class ExistingSourceTests(_WizardTestCase):
    """A source that is in sources/ already feeds one more model."""

    def _source_answers(self, choose_answers, model_row):
        return ([_origin_row(wizard._write_nothing)] + list(choose_answers)
                + [model_row, _family_row(_FAMILY), _ENTER, _ENTER, _ENTER,
                   _YES, _NO])

    def test_a_second_model_comes_from_the_same_source(self):
        self._existing_source("itch_kit", ("barrel.glb", "crate.glb"))
        before = sources.load_source("itch_kit")
        result, _said, _dialogs = self._run(
            self._source_answers(("1",), "2"))
        record = records.load_record(result.record_path)
        after = sources.load_source("itch_kit")

        self.assertEqual((record.source_id, record.file),
                         ("itch_kit", "crate.glb"))
        self.assertEqual(result.asset_key, "crate")
        self.assertEqual(after.files, before.files)

    def test_a_source_that_fails_the_gate_needs_a_yes(self):
        self._existing_source("itch_kit", ("barrel.glb", "crate.glb"),
                              license=fetch.TODO)
        result, said, _dialogs = self._run(
            self._source_answers(("1", _NO, "1", _YES), "1"))

        self.assertTrue(any("refuses this source" in line for line in said))
        self.assertEqual(result.asset_key, "barrel")


class PolyHavenTests(_WizardTestCase):
    """A Poly Haven model downloads only after the confirm."""

    def setUp(self):
        super().setUp()
        self.gltf = b'{"asset": {"version": "2.0"}}'
        self.image = b"jpeg"
        files = {"gltf": {"1k": {"gltf": {
            "url": "https://dl.example/wooden_crate_01_1k.gltf",
            "md5": _md5(self.gltf),
            "include": {"textures/crate_diff_1k.jpg": {
                "url": "https://dl.example/crate_diff_1k.jpg",
                "md5": _md5(self.image)}}}}}}
        info = {"type": 2, "name": "Wooden Crate 01",
                "authors": {"Jane Doe": "All"}}
        self.bodies = {"/info/": json.dumps(info).encode(),
                       "/files/": json.dumps(files).encode(),
                       ".gltf": self.gltf, ".jpg": self.image}
        self.requested = []
        patch = mock.patch.object(fetch, "_download", side_effect=self._fake)
        patch.start()
        self.addCleanup(patch.stop)

    def _fake(self, url):
        self.requested.append(url)
        matches = [body for part, body in self.bodies.items() if part in url]

        return matches[0]

    def _answers(self, confirm):
        answers = [_origin_row(wizard._write_polyhaven), "wooden_crate_01",
                   _family_row(_FAMILY), _ENTER, _ENTER, _ENTER, confirm]

        return answers + [_NO] if confirm == _YES else answers

    def test_the_api_gives_every_field_of_the_source_record(self):
        result, _said, _dialogs = self._run(self._answers(_YES))
        record = records.load_record(result.record_path)
        source = sources.load_source(record.source_id)

        self.assertEqual(result.asset_key, "wooden_crate_01")
        self.assertEqual(record.file, "wooden_crate_01_1k.gltf")
        self.assertEqual(source.license, fetch.POLYHAVEN_LICENSE)
        self.assertEqual(source.author, "Jane Doe")
        self.assertIn("textures/crate_diff_1k.jpg", source.files)
        self.assertEqual(sources.hash_problems(source), [])

    def test_a_no_at_the_confirm_downloads_no_file(self):
        result, _said, _dialogs = self._run(self._answers(_NO))
        downloads = [url for url in self.requested
                     if url.startswith("https://dl.example/")]

        self.assertIsNone(result)
        self.assertEqual(downloads, [])
        self.assertEqual(self._written(), [])


class BuildQuestionTests(_WizardTestCase):
    """The build question comes only on a machine that can build."""

    def test_a_machine_that_cannot_build_gets_no_question(self):
        path = self._download("crate.glb")
        answers = self._upload_answers(path)[:-1]

        with mock.patch.object(build, "tools_problem",
                               return_value="Node is not on the PATH"):
            result, said, _dialogs = self._run(answers)

        self.assertFalse(result.build)
        self.assertTrue(any("cannot build" in line for line in said))

    def test_the_next_steps_give_the_build_command_when_nothing_built(self):
        result = wizard.WizardResult("crate", "models/items/crate.toml",
                                     False)
        unbuilt = "\n".join(wizard.next_steps(result, False))
        built = "\n".join(wizard.next_steps(result, True))

        self.assertIn("assets.pipeline build crate", unbuilt)
        self.assertNotIn("assets.pipeline build crate", built)


class FormatTableTests(unittest.TestCase):
    """The formats that the wizard lists are those that the build reads."""

    def test_the_blender_suffixes_are_those_of_the_ingest_script(self):
        script = os.path.join(paths.ASSETS_DIR, "pipeline",
                              "blender_ingest.py")

        with open(script, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read())

        wanted = ("_IMPORTERS", "_BLEND_SUFFIX")
        values = {}

        for node in tree.body:
            target = node.targets[0] if isinstance(node, ast.Assign) else None
            named = isinstance(target, ast.Name) and target.id in wanted

            if named:
                values[target.id] = ast.literal_eval(node.value)

        importers = set(values["_IMPORTERS"]) - set(blender.GLTF_SUFFIXES)
        expected = (importers | {values["_BLEND_SUFFIX"]}
                    | set(blender.FORMAT_SCRIPTS))

        self.assertEqual(set(blender.BLENDER_SUFFIXES), expected)

    def test_the_picocad_header_is_the_one_that_picocad_reads(self):
        # build.py keeps its own copy, because the text of picocad.py feeds
        # the input digest of every model.
        header = picocad._HEADER_PREFIX + picocad._HEADER_SEPARATOR

        self.assertEqual(build.PICOCAD_HEADER, header)
        self.assertTrue(_PICOCAD_TEXT.startswith(header))

    def test_picocad_is_a_file_that_the_pipeline_digests(self):
        # If picocad.py leaves the digest, its constants can move back.
        script = os.path.join(paths.ASSETS_DIR, "pipeline", "picocad.py")
        digested = [os.path.normcase(path) for path in build._PIPELINE_FILES]

        self.assertIn(os.path.normcase(script), digested)
