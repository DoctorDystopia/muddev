"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/02/2026
Description: Guard the model form: the JSON commands of the model pipeline
             that the Godot editor runs (`add-options`, `add-polyhaven`,
             `add-check`, `add-write`, in assets/pipeline/form.py).

             THE PROMISES THAT THESE TESTS KEEP:
               - A check writes nothing. A write that is not ready writes
                 nothing.
               - The form and the terminal wizard write the same files for
                 the same answers.
               - A field refuses what the build refuses: a taken key, an
                 alias that a record has, a base that is an alias, a license
                 with no exception.
               - A warning needs its yes: an asset key that the game does
                 not name, and a source that the license gate refuses.
               - An export of art made here replaces the file of its own
                 import, keeps a [fix], and never empties a source that
                 another record reads.
               - Each plan key of form.py and each origin of plans.py has
                 the same name and text in the Godot bridge
                 (model_pipeline.gd).

             Each test points paths.SOURCES_DIR and paths.MODELS_DIR at a
             temporary directory, so no test touches the sources in git.
             No test needs the network, Node or Blender.
"""

import hashlib
import json
import os
import re
import shutil
import tempfile
import unittest
from unittest import mock

# assets/ is import-safe by design: it touches no database.
from assets.pipeline import (build, fetch, figure, form, licenses, paths,
                             plans, questions, records, sources, wizard)
from assets.pipeline import __main__ as pipeline_cli


_FAMILY = "items"
_AUTHOR = "Kenney"
_URL = "https://kenney.itch.io/crate-pack"
_YES = "y"
_NO = "n"
_ENTER = ""

# The Godot bridge that names the plan keys, from the game directory.
_GODOT_BRIDGE = os.path.join(paths.GAME_DIR, os.pardir, "godot", "addons",
                             "blackout_models", "model_pipeline.gd")
_GODOT_CONSTANT = r'^const ((?:FIELD|ORIGIN)_[A-Z_]+) := "([^"]*)"'


def _key_row(key, owner, kind):
    """Give one row of a key list, as key_list.py writes it."""
    return {"key": key, "owner": owner, "kind": kind, "name": owner}


class _FormTestCase(unittest.TestCase):
    """A temporary sources/ and models/, and a machine that can build."""

    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.addCleanup(self._folder.cleanup)
        self.root = self._folder.name
        self.sources_dir = os.path.join(self.root, "sources")
        self.models_dir = os.path.join(self.root, "models")
        self.downloads = os.path.join(self.root, "downloads")
        self.key_list_path = os.path.join(self.root, "key_list.json")

        for folder in (self.sources_dir, self.models_dir, self.downloads):
            os.makedirs(folder)

        for name, value in (("SOURCES_DIR", self.sources_dir),
                            ("MODELS_DIR", self.models_dir),
                            ("KEY_LIST_PATH", self.key_list_path),
                            ("FIGURE_LOOKS_DIR",
                             os.path.join(self.root, "looks"))):
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

    def _existing_source(self, source_id, names, license="CC0-1.0"):
        """Make a source in the temporary sources/ that holds names."""
        folder = os.path.join(self.downloads, source_id)

        for name in names:
            self._download(os.path.join(source_id, name))

        fields = fetch.SourceFields(title="Kit", author=_AUTHOR, url=_URL,
                                    site="itch.io", license=license)
        fetch.fetch_file(folder, source_id, fields)

    def _write_key_list(self, rows):
        with open(self.key_list_path, "w", encoding="utf-8") as handle:
            json.dump({"format": plans.KEY_LIST_FORMAT, "keys": rows}, handle)

    def _upload_plan(self, path, **changes):
        """Give the plan of an upload with CC0 and the defaults elsewhere."""
        content = {form.FIELD_FORMAT: form.FORM_FORMAT,
                   form.FIELD_ORIGIN: plans.ORIGIN_FILE,
                   form.FIELD_UPLOAD: path, form.FIELD_LICENSE: "CC0-1.0",
                   form.FIELD_AUTHOR: _AUTHOR, form.FIELD_URL: _URL,
                   form.FIELD_FAMILY: _FAMILY}
        content.update(changes)

        return content

    def _export_plan(self, path, key, **changes):
        """Give the plan of an export of art made here."""
        content = {form.FIELD_FORMAT: form.FORM_FORMAT,
                   form.FIELD_ORIGIN: plans.ORIGIN_EXPORT,
                   form.FIELD_UPLOAD: path, form.FIELD_FAMILY: _FAMILY,
                   form.FIELD_ASSET_KEY: key}
        content.update(changes)

        return content

    def _written(self):
        """Name each entry in the temporary sources/ and models/."""
        return os.listdir(self.sources_dir) + os.listdir(self.models_dir)


class OptionsTests(_FormTestCase):
    """add-options lists what the wizard lists."""

    def test_the_lists_come_from_their_owners(self):
        self._existing_source("itch_kit", ("crate.glb",))
        self._existing_source("itch_todo", ("barrel.glb",), license=fetch.TODO)
        answer = form.options()
        refusals = {row["id"]: row["refusal"] for row in answer["sources"]}

        self.assertEqual(answer["problem"], "")
        self.assertEqual([row["key"] for row in answer["origins"]],
                         list(plans.ORIGIN_LABELS))
        self.assertEqual([row["spdx"] for row in answer["licenses"]],
                         list(licenses.ALLOWED_LICENSES))
        self.assertEqual([row["key"] for row in answer["families"]],
                         plans.families())
        self.assertEqual(sorted(refusals), ["itch_kit", "itch_todo"])
        self.assertEqual(refusals["itch_kit"], "")
        self.assertNotEqual(refusals["itch_todo"], "")


class UploadTests(_FormTestCase):
    """An upload: the defaults, the check with no write, and the write."""

    def test_a_check_gives_the_defaults_and_writes_nothing(self):
        path = self._download("crate.glb")
        answer = form.check(self._upload_plan(path))
        texts = [row["text"] for row in answer["files"]]

        self.assertTrue(answer["ready"], answer["problems"])
        self.assertEqual(answer["defaults"][form.FIELD_SITE], "itch.io")
        self.assertEqual(answer["defaults"][form.FIELD_SOURCE_ID],
                         "itch_crate")
        self.assertEqual(answer["asset_key"], "crate")
        self.assertEqual(answer["model_files"], ["crate.glb"])
        self.assertTrue(any('license   = "CC0-1.0"' in text for text in texts))
        self.assertEqual(self._written(), [])

    def test_a_write_gives_a_sealed_source_and_a_record(self):
        path = self._download("crate.glb")
        answer = form.write(self._upload_plan(path))
        record = records.load_record(os.path.join(self.models_dir, _FAMILY,
                                                  "crate.toml"))
        source = sources.load_source(record.source_id)

        self.assertTrue(answer["ok"], answer["problem"])
        self.assertEqual(answer["record_path"], plans.shown(
            record.record_path))
        self.assertEqual(source.author, _AUTHOR)
        self.assertEqual(sources.hash_problems(source), [])
        self.assertEqual(sources.gate_problem(source), "")

    def test_the_form_and_the_wizard_write_the_same_records(self):
        path = self._download("crate.glb")
        form.write(self._upload_plan(path))
        by_form = self._record_texts()

        for folder in (self.sources_dir, self.models_dir):
            shutil.rmtree(folder)
            os.makedirs(folder)

        answers = [_origin_number(plans.ORIGIN_FILE), path,
                   _license_number("CC0-1.0"), _ENTER, _AUTHOR, _URL, _ENTER,
                   _ENTER, _ENTER, _family_number(_FAMILY), _ENTER, _ENTER,
                   _ENTER, _YES, _NO]
        wizard.run(_scripted(answers))

        self.assertEqual(self._record_texts(), by_form)

    def _record_texts(self):
        """Give the text of the source record and of the model record."""
        texts = []

        for path in (os.path.join(self.sources_dir, "itch_crate",
                                  paths.SOURCE_RECORD_NAME),
                     os.path.join(self.models_dir, _FAMILY, "crate.toml")):
            with open(path, "r", encoding="utf-8") as handle:
                texts.append(handle.read())

        return texts

    def test_a_license_that_the_gate_refuses_needs_an_exception(self):
        path = self._download("crate.glb")
        refused = self._upload_plan(path, license="CC-BY-NC-4.0")
        excepted = self._upload_plan(path, license="CC-BY-NC-4.0",
                                     exception="Nick asked the author.")

        self.assertIn(form.FIELD_EXCEPTION, form.check(refused)["problems"])
        self.assertTrue(form.check(excepted)["ready"])

    def test_a_write_that_is_not_ready_writes_nothing(self):
        path = self._download("crate.glb")
        answer = form.write(self._upload_plan(path, license=""))

        self.assertFalse(answer["ok"])
        self.assertIn(form.FIELD_LICENSE, answer["problems"])
        self.assertEqual(self._written(), [])


class KeyTests(_FormTestCase):
    """The key fields refuse what records.load_all refuses."""

    def setUp(self):
        super().setUp()
        self._existing_source("itch_kit", ("rusty_pole.glb",))
        fetch.write_model_record(_FAMILY, "rusty_pole", "itch_kit",
                                 "rusty_pole.glb", aliases=("old_pole",))
        self.upload = self._download("bent_pole.glb")

    def _problems(self, **changes):
        return form.check(self._upload_plan(self.upload, **changes))[
            "problems"]

    def test_a_taken_key_and_a_taken_alias_are_refused(self):
        self.assertIn(form.FIELD_ASSET_KEY, self._problems(
            asset_key="old_pole"))
        self.assertIn(form.FIELD_ALIASES, self._problems(
            aliases="bent_a, rusty_pole"))

    def test_an_alias_is_no_base_and_a_record_is(self):
        self.assertIn(form.FIELD_VARIANT, self._problems(
            variant_of="old_pole"))
        self.assertEqual(self._problems(variant_of="rusty_pole"), {})

    def test_the_aliases_can_be_a_list_or_a_text(self):
        as_text = form.check(self._upload_plan(self.upload,
                                               aliases="bent_a, bent_b"))
        as_list = form.check(self._upload_plan(self.upload,
                                               aliases=["bent_a", "bent_b"]))

        self.assertEqual(as_text["files"], as_list["files"])
        self.assertIn('aliases = ["bent_a", "bent_b"]',
                      as_text["files"][-1]["text"])


class WarningTests(_FormTestCase):
    """A warning needs its yes before a plan is ready."""

    def test_an_asset_key_that_the_game_does_not_name_needs_a_yes(self):
        self._write_key_list([_key_row("crate", "crate", "crafting_tool")])
        path = self._download("barrel.glb")
        plain = form.check(self._upload_plan(path))
        kept = form.check(self._upload_plan(path, keep_unnamed=True))

        self.assertIn(form.FIELD_ASSET_KEY, plain["warnings"])
        self.assertFalse(plain["ready"])
        self.assertTrue(kept["ready"])
        self.assertEqual([row["key"] for row in plain["offered"]], ["crate"])

    def test_with_no_key_list_the_form_warns_about_no_key(self):
        answer = form.check(self._upload_plan(self._download("barrel.glb")))

        self.assertEqual(answer["warnings"], {})
        self.assertNotEqual(answer["key_list_problem"], "")

    def test_a_source_that_the_gate_refuses_needs_a_yes(self):
        self._existing_source("itch_kit", ("barrel.glb",), license=fetch.TODO)
        content = {form.FIELD_FORMAT: form.FORM_FORMAT,
                   form.FIELD_ORIGIN: plans.ORIGIN_SOURCE,
                   form.FIELD_SOURCE_ID: "itch_kit",
                   form.FIELD_FAMILY: _FAMILY}
        plain = form.check(content)
        used = form.check(dict(content, use_refused_source=True))

        self.assertIn(form.FIELD_SOURCE_ID, plain["warnings"])
        self.assertFalse(plain["ready"])
        self.assertTrue(used["ready"])


class ExistingSourceTests(_FormTestCase):
    """A source with several model files needs a choice."""

    def test_a_source_with_two_files_needs_the_model_file(self):
        self._existing_source("itch_kit", ("barrel.glb", "crate.glb"))
        content = {form.FIELD_FORMAT: form.FORM_FORMAT,
                   form.FIELD_ORIGIN: plans.ORIGIN_SOURCE,
                   form.FIELD_SOURCE_ID: "itch_kit",
                   form.FIELD_FAMILY: _FAMILY}
        unchosen = form.check(content)
        chosen = form.write(dict(content, model_file="crate.glb"))
        record = records.load_record(os.path.join(self.models_dir, _FAMILY,
                                                  "crate.toml"))

        self.assertIn(form.FIELD_MODEL_FILE, unchosen["problems"])
        self.assertTrue(chosen["ok"], chosen["problems"])
        self.assertEqual((record.source_id, record.file),
                         ("itch_kit", "crate.glb"))


class PolyHavenTests(_FormTestCase):
    """The lookup reads the API. The write downloads, and nothing before."""

    def setUp(self):
        super().setUp()
        self.gltf = b'{"asset": {"version": "2.0"}}'
        files = {"gltf": {"1k": {"gltf": {
            "url": "https://dl.example/wooden_crate_01_1k.gltf",
            "md5": hashlib.md5(self.gltf).hexdigest()}}}}
        info = {"type": 2, "name": "Wooden Crate 01",
                "authors": {"Jane Doe": "All"}}
        self.bodies = {"/info/": json.dumps(info).encode(),
                       "/files/": json.dumps(files).encode(),
                       ".gltf": self.gltf}
        self.requested = []
        patch = mock.patch.object(fetch, "_download", side_effect=self._fake)
        patch.start()
        self.addCleanup(patch.stop)

    def _fake(self, url):
        self.requested.append(url)

        return [body for part, body in self.bodies.items() if part in url][0]

    def _downloads(self):
        return [url for url in self.requested
                if url.startswith("https://dl.example/")]

    def test_the_lookup_and_the_check_download_no_file(self):
        found = form.polyhaven("https://polyhaven.com/a/wooden_crate_01/")
        content = {form.FIELD_FORMAT: form.FORM_FORMAT,
                   form.FIELD_ORIGIN: plans.ORIGIN_POLYHAVEN,
                   form.FIELD_POLYHAVEN: found["asset_id"],
                   form.FIELD_TITLE: found["title"],
                   form.FIELD_AUTHOR: found["author"],
                   form.FIELD_MODEL_FILE: found["model_file"],
                   form.FIELD_FAMILY: _FAMILY}
        answer = form.check(content)

        self.assertTrue(found["ok"], found["problem"])
        self.assertEqual(found["author"], "Jane Doe")
        self.assertTrue(answer["ready"], answer["problems"])
        self.assertEqual(self._downloads(), [])

        written = form.write(content)
        source = sources.load_source("polyhaven_wooden_crate_01")

        self.assertTrue(written["ok"], written["problem"])
        self.assertEqual(source.license, fetch.POLYHAVEN_LICENSE)
        self.assertEqual(sources.hash_problems(source), [])

    def test_a_plan_with_no_lookup_is_not_ready(self):
        content = {form.FIELD_FORMAT: form.FORM_FORMAT,
                   form.FIELD_ORIGIN: plans.ORIGIN_POLYHAVEN,
                   form.FIELD_POLYHAVEN: "wooden_crate_01",
                   form.FIELD_FAMILY: _FAMILY}

        self.assertIn(form.FIELD_POLYHAVEN, form.check(content)["problems"])


class ExportTests(_FormTestCase):
    """An export of art made here, as the gear editor sends it."""

    def test_an_export_writes_an_owned_source_with_color_roles(self):
        path = self._download("helm.glb")
        answer = form.write(self._export_plan(path, "iron_helm"))
        record = records.load_record(os.path.join(self.models_dir, _FAMILY,
                                                  "iron_helm.toml"))
        source = sources.load_source(record.source_id)

        self.assertTrue(answer["ok"], answer["problem"])
        self.assertEqual(record.source_id, figure.source_id_for("iron_helm"))
        self.assertTrue(record.color_roles)
        self.assertEqual(source.license, licenses.OWNED_LICENSE)
        self.assertEqual(source.author, figure.DEFAULT_AUTHOR)

    def test_an_export_again_replaces_the_file_and_keeps_a_fix(self):
        first = self._download("helm.glb", b"glTF one")
        second = self._download("helm_v2.gltf", b'{"asset": {}}')
        form.write(self._export_plan(first, "iron_helm"))
        target = os.path.join(self.models_dir, _FAMILY, "iron_helm.toml")

        with open(target, "a", encoding="utf-8") as handle:
            handle.write("\n[fix]\nrotate = [0, 90, 0]\n")

        answer = form.write(self._export_plan(second, "iron_helm"))
        record = records.load_record(target)
        source = sources.load_source(record.source_id)

        self.assertTrue(answer["ok"], answer["problem"])
        self.assertEqual(record.file, "iron_helm.gltf")
        self.assertEqual(sorted(source.files), ["iron_helm.gltf"])
        self.assertEqual(record.rotate, (0, 90, 0))

    def test_an_export_never_empties_a_source_that_another_record_reads(self):
        source_id = figure.source_id_for("bloody_sword2")
        self._existing_source(source_id, ("sword.glb",),
                              license=licenses.OWNED_LICENSE)
        fetch.write_model_record(_FAMILY, "blood_sword", source_id,
                                 "sword.glb")
        answer = form.write(self._export_plan(self._download("new.glb"),
                                              "bloody_sword2"))

        self.assertFalse(answer["ok"])
        self.assertIn(form.FIELD_ASSET_KEY, answer["problems"])
        self.assertEqual(sources.hash_problems(
            sources.load_source(source_id)), [])

    def test_an_export_is_one_file_with_no_alias(self):
        folder = os.path.dirname(self._download(os.path.join("kit",
                                                             "helm.glb")))
        problems = form.check(self._export_plan(
            folder, "iron_helm", aliases="helm_b"))["problems"]

        self.assertIn(form.FIELD_UPLOAD, problems)
        self.assertIn(form.FIELD_ALIASES, problems)


class CommandTests(_FormTestCase):
    """The commands read a plan file and write an answer file."""

    def _paths(self, content):
        plan_path = os.path.join(self.root, "plan.json")
        answer_path = os.path.join(self.root, "answer.json")

        with open(plan_path, "w", encoding="utf-8") as handle:
            json.dump(content, handle)

        return plan_path, answer_path

    def _answer(self, answer_path):
        with open(answer_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def test_add_write_builds_when_the_plan_asks(self):
        content = self._upload_plan(self._download("crate.glb"), build=True)
        plan_path, answer_path = self._paths(content)

        with mock.patch.object(pipeline_cli, "_command_build",
                               return_value=0) as built:
            status = pipeline_cli.main(["pipeline", "add-write", plan_path,
                                        answer_path])

        self.assertEqual(status, 0)
        built.assert_called_once_with(["crate"])
        self.assertTrue(self._answer(answer_path)["built"])

    def test_a_plan_of_another_format_is_refused(self):
        plan_path, answer_path = self._paths({"format": 0})
        status = pipeline_cli.main(["pipeline", "add-check", plan_path,
                                    answer_path])

        self.assertNotEqual(status, 0)
        self.assertFalse(os.path.exists(answer_path))


class GodotBridgeTests(unittest.TestCase):
    """The Godot bridge names each plan key and each origin as Python."""

    def test_each_plan_key_and_origin_has_the_same_text_in_godot(self):
        with open(_GODOT_BRIDGE, "r", encoding="utf-8") as handle:
            godot = dict(re.findall(_GODOT_CONSTANT, handle.read(),
                                    re.MULTILINE))

        for prefix, owner in (("FIELD_", form), ("ORIGIN_", plans)):
            python = {name: value for name, value in vars(owner).items()
                      if name.startswith(prefix) and isinstance(value, str)}
            mirrored = {name: value for name, value in godot.items()
                        if name.startswith(prefix)}

            with self.subTest(prefix=prefix):
                self.assertTrue(python)
                self.assertEqual(mirrored, python)


# ─── The wizard side of the parity test ──────────────────────────────────────

def _scripted(answers):
    """Make a console that answers from a list, and says nothing."""
    queue = list(answers)

    return questions.Console(ask=lambda _prompt: queue.pop(0),
                             say=lambda _line: None,
                             pick_file=lambda: "")


def _origin_number(origin):
    """Give the number of one origin in the list of the wizard."""
    origins = [row[wizard._ROW_ORIGIN] for row in wizard._ORIGINS]

    return str(origins.index(origin) + 1)


def _license_number(spdx):
    """Give the number of an allowed license in the license list."""
    return str(list(licenses.ALLOWED_LICENSES).index(spdx) + 1)


def _family_number(family):
    """Give the number of one family in the family list."""
    return str(plans.families().index(family) + 1)
