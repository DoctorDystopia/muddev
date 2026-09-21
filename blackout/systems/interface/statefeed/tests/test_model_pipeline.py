"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: Guard the served 3D models and the pipeline that builds them.

             Until 09/18/2026 this file was test_model_budgets.py, and it
             asserted the budgets only. The model pipeline
             (assets/pipeline) now owns every fact about a model: its record,
             its source and license, its budget, the served file, the manifest
             and the credits. `check.run_check()` asserts that all of them
             agree, and the first test here runs it. The other tests pin the
             rules that the check depends on.

             WHAT THIS CATCHES. A temp art asset dropped straight into
             web/static/webclient/models/, a model record edited without a
             rebuild, an edited download, a license nobody confirmed, and a
             model over its family budget. player_character.glb once carried
             fifteen 1024-square textures for 10.4 MiB, and nothing failed.

             NO CENSUS. Per CLAUDE.md, this never asserts a list of models.
             Every case is a RELATIONSHIP: between a record and its served
             file, a key and the manifest, a source and the license gate.
             Adding a model or a family needs no edit in this file.

             NO NODE AND NO BLENDER. The check reads files only, so the suite
             runs on a machine that cannot build a model.
"""

import json
import os
import tempfile
import unittest

# assets/ is import-safe by design -- it touches no database and starts no
# Evennia. That is what separates it from blackout/scripts/, which CLAUDE.md
# marks import-unsafe and which a test must never reach into.
from assets.pipeline import (budgets, check, glb, licenses, outputs, paths,
                             records, sources)


def _write_record(folder, family, asset_key, text):
    """
    Purpose: Write one model record into a temporary models tree.

    Entry:
        folder is a temporary directory.

    Exit/Returns:
        Returns the path of the written record.
    """
    family_dir = os.path.join(folder, family)
    os.makedirs(family_dir, exist_ok=True)
    path = os.path.join(family_dir, asset_key + paths.MODEL_RECORD_SUFFIX)

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)

    return path


class PipelineCheckTests(unittest.TestCase):
    """The records, the sources and the served tree agree."""

    def test_the_pipeline_check_finds_no_problem(self):
        """
        The whole point of the module. Each problem is its own subTest, so
        one stale model names itself and does not hide the others.
        """
        report = check.run_check()

        for problem in report.problems:
            with self.subTest(problem=problem):
                self.fail(problem)

    def test_there_is_at_least_one_record(self):
        """
        A vacuity guard. Every check passes against an empty models tree,
        which is how a guard stops guarding with nobody noticing.
        """
        self.assertTrue(records.load_all(),
                        "no model records under assets/models/")


class ModelRecordTests(unittest.TestCase):
    """A model record says what it means, or it refuses to load."""

    def test_the_file_name_is_the_key_and_the_directory_is_the_family(self):
        with tempfile.TemporaryDirectory() as folder:
            path = _write_record(folder, "items", "a_key",
                                 'source = "s"\nfile = "f.glb"\n')
            record = records.load_record(path)

        self.assertEqual(record.asset_key, "a_key")
        self.assertEqual(record.family, "items")

    def test_an_unknown_field_is_refused(self):
        """
        "rotation" for "rotate" must fail. Ignored, it builds a model with no
        correction and no error.
        """
        with tempfile.TemporaryDirectory() as folder:
            path = _write_record(
                folder, "items", "k",
                'source = "s"\nfile = "f.glb"\n[fix]\nrotation = [0, 90, 0]\n')

            with self.assertRaises(records.RecordError) as caught:
                records.load_record(path)

        self.assertIn("rotation", str(caught.exception))

    def test_a_record_needs_a_source_and_a_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = _write_record(folder, "items", "k", 'source = "s"\n')

            with self.assertRaises(records.RecordError):
                records.load_record(path)

    def test_a_bad_filter_or_rotation_is_refused(self):
        bodies = ('[fix]\nfilter = "blurry"\n', '[fix]\nrotate = [90, 0]\n')

        for body in bodies:
            with self.subTest(body=body):
                with tempfile.TemporaryDirectory() as folder:
                    path = _write_record(
                        folder, "items", "k",
                        'source = "s"\nfile = "f.glb"\n' + body)

                    with self.assertRaises(records.RecordError):
                        records.load_record(path)

    def test_aliases_follow_the_key(self):
        with tempfile.TemporaryDirectory() as folder:
            path = _write_record(
                folder, "items", "k",
                'source = "s"\nfile = "f.glb"\naliases = ["a", "b"]\n')
            record = records.load_record(path)

        self.assertEqual(record.keys, ("k", "a", "b"))


class ManifestTests(unittest.TestCase):
    """The manifest a graphical client fetches to learn which keys have art."""

    def test_every_key_and_alias_of_a_served_record_is_in_the_manifest(self):
        manifest = outputs.render_manifest(records.load_all())

        for record in records.load_all():
            served = paths.served_path(record.family, record.asset_key)

            if not os.path.isfile(served):
                continue

            for key in record.keys:
                with self.subTest(key=key):
                    self.assertEqual(
                        manifest.get(key),
                        paths.served_relative(record.family, record.asset_key),
                        "an alias must name its model's one file, never a copy")

    def test_it_carries_paths_only_and_no_presentation(self):
        """
        WHICH models exist is a build fact; HOW each is shown is not.
        CLAUDE.md is explicit that the model registry -- rotations, offsets --
        is the client's own and must never be generated. A correction to an
        export is baked into the file instead, so no field is needed here.
        """
        for asset_key, entry in outputs.render_manifest(
                records.load_all()).items():
            with self.subTest(asset_key=asset_key):
                self.assertIsInstance(entry, str)
                self.assertTrue(entry.endswith(paths.SERVED_SUFFIX))

    def test_every_served_tile_is_opaque(self):
        """
        budgets.ALWAYS_OPAQUE_FAMILIES bakes the rule. This reads the served
        files, so a tile dropped in by hand with BLEND fails here too.
        """
        for record in records.load_all():
            if record.family not in budgets.ALWAYS_OPAQUE_FAMILIES:
                continue

            served = paths.served_path(record.family, record.asset_key)

            with self.subTest(asset_key=record.asset_key):
                summary = glb.summarize(served)
                self.assertEqual(set(summary.alpha_modes), {"OPAQUE"})


class CreditTests(unittest.TestCase):
    """Every served model has a credit, and the credit tells the truth."""

    def test_every_served_source_has_a_credit(self):
        credits = outputs.render_credits(records.load_all())
        credited = {key for entry in credits for key in entry["models"]}
        manifest = outputs.render_manifest(records.load_all())

        for asset_key in manifest:
            with self.subTest(asset_key=asset_key):
                self.assertIn(asset_key, credited)

    def test_a_credit_is_unconfirmed_exactly_when_its_source_has_an_exception(
            self):
        """
        The Godot credits box marks an unconfirmed license. The mark must
        come from the source record, never from a guess.
        """
        all_records = records.load_all()
        by_title = {entry["title"]: entry
                    for entry in outputs.render_credits(all_records)}

        for source_id in {record.source_id for record in all_records}:
            source = sources.load_source(source_id)

            with self.subTest(source_id=source_id):
                self.assertEqual(by_title[source.title]["confirmed"],
                                 not source.exception)

    def test_the_credits_json_is_valid_and_matches_a_fresh_render(self):
        with open(paths.CREDITS_JSON_PATH, encoding="utf-8") as handle:
            committed = json.load(handle)

        self.assertEqual(committed,
                         outputs.render_credits(records.load_all()))


class LicenseGateTests(unittest.TestCase):
    """The gate refuses what it must, and an exception is never silent."""

    def _source(self, license_id, exception=""):
        return sources.Source(
            source_id="x", directory="", title="t", author="a", url="u",
            site="s", license=license_id, retrieved="2026-09-18",
            exception=exception)

    def test_an_allowed_license_passes(self):
        for license_id in licenses.ALLOWED_LICENSES:
            with self.subTest(license_id=license_id):
                source = self._source(license_id)
                self.assertEqual(sources.gate_problem(source), "")

    def test_a_restrictive_or_missing_license_is_refused(self):
        for license_id in ("CC-BY-NC-4.0", "CC-BY-ND-4.0", "TODO", ""):
            with self.subTest(license_id=license_id):
                source = self._source(license_id)
                self.assertTrue(sources.gate_problem(source))

    def test_an_exception_waives_the_gate(self):
        source = self._source("LicenseRef-Unconfirmed", exception="reason")

        self.assertEqual(sources.gate_problem(source), "")

    def test_every_exception_is_reported_by_the_check(self):
        """
        An exception must stay visible on every run, or it becomes a silent
        pass -- the state the gate exists to end.
        """
        report = check.run_check()

        for source_id in sources.list_source_ids():
            source = sources.load_source(source_id)

            if not source.exception:
                continue

            with self.subTest(source_id=source_id):
                named = [line for line in report.warnings
                         if line.startswith(source_id)]
                self.assertTrue(named)


class BudgetTableTests(unittest.TestCase):
    """The budget table is coherent, whatever the numbers are."""

    def test_every_budget_is_positive_and_described(self):
        """
        A zero or negative ceiling would silently pass everything or fail
        everything. `reason` is required because a number nobody justified is
        one the next person edits rather than argues with.
        """
        listed = dict(budgets.FAMILY_BUDGETS)
        listed["<default>"] = budgets.DEFAULT_BUDGET

        for family, budget in listed.items():
            with self.subTest(family=family):
                self.assertGreater(budget.max_texture_edge, 0)
                self.assertGreater(budget.max_bytes, 0)
                self.assertGreater(budget.max_triangles, 0)
                self.assertTrue(budget.reason.strip(),
                                "%s has no stated reason" % family)

    def test_an_unlisted_family_falls_back_rather_than_raising(self):
        """
        A new family must be buildable the day it is created, the same way an
        unknown asset key already draws a generic mesh. The fallback is the
        tightest texture tier, so not being listed costs a smaller model.
        """
        fallback = budgets.budget_for("a-family-nobody-has-added")

        self.assertEqual(fallback, budgets.DEFAULT_BUDGET)

        for family, budget in budgets.FAMILY_BUDGETS.items():
            with self.subTest(family=family):
                self.assertGreaterEqual(
                    budget.max_texture_edge,
                    budgets.DEFAULT_BUDGET.max_texture_edge)

    def test_a_model_over_budget_names_every_broken_limit(self):
        budget = budgets.budget_for("items")
        summary = glb.GlbSummary(
            size_bytes=budget.max_bytes + 1,
            triangles=budget.max_triangles + 1,
            extensions_used=(), texture_edges=(budget.max_texture_edge * 2,),
            alpha_modes=(), generator="")

        problems = budgets.budget_problems("items", summary)

        self.assertEqual(len(problems), 3)


class GodotExtensionTests(unittest.TestCase):
    """The list of extensions Godot reads leaves out the known traps."""

    def test_geometry_compression_is_not_in_the_list(self):
        """
        Every other glTF tool supports these, and Godot's runtime loader does
        not. A served file that needs one loads as nothing, with no error.
        """
        traps = ("KHR_draco_mesh_compression", "EXT_meshopt_compression",
                 "KHR_mesh_quantization")

        for name in traps:
            with self.subTest(extension=name):
                self.assertNotIn(name, glb.GODOT_RUNTIME_EXTENSIONS)


if __name__ == "__main__":
    unittest.main()
