"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/25/2026
Description: Guard the served 3D models against their family's budget.

             WHAT THIS CATCHES. A temp art asset dropped straight into
             web/static/webclient/models/ during development, or a repack run
             with an --edge override that was meant to be temporary. Both look
             fine in the pane and cost every player the difference on every
             load. player_character.glb carried fifteen 1024-square textures
             for 10.4 MiB that way -- more than the rest of the art combined,
             for the model seen from furthest away -- and nothing failed.

             It lives beside test_client_assets.py because it is the same kind
             of check: a fact about files the client fetches, asserted from the
             Python side because that is the side that can be tested.

             NO CENSUS. Per CLAUDE.md, this never asserts a list of models.
             The manifest is the source of truth for which models exist and
             asset_budgets.py for how large each may be; every case here is a
             RELATIONSHIP between the two. Adding a model or a family needs no
             edit in this file.
"""

import os
import unittest

# assets/ is import-safe by design -- it touches no database and boots no
# Evennia. That is what separates it from blackout/scripts/, which CLAUDE.md
# marks import-unsafe and which a test must never reach into.
from assets import asset_budgets
from assets import pack_model


class ModelBudgetTests(unittest.TestCase):
    """The served models obey the budgets, and the budgets are coherent."""

    def test_every_manifest_model_is_within_its_family_budget(self):
        """
        The whole point of the module: no served model is over budget.

        Reported per model via subTest so one oversized asset names itself
        rather than hiding every other one behind the first failure.
        """
        problems = pack_model.audit_served_models()

        for asset_key, family, problem in problems:
            with self.subTest(asset_key=asset_key, family=family):
                self.fail(
                    "%s [%s] %s. Repack it with "
                    "`python assets/pack_model.py --all`, or argue the budget "
                    "up in assets/asset_budgets.py -- but do not drop a raw "
                    "asset into the served tree." % (asset_key, family, problem))

    def test_the_manifest_is_readable_and_not_empty(self):
        """
        A vacuity guard.

        Every other case here passes trivially against an empty or unreadable
        manifest, which is exactly how a guard stops guarding without anyone
        noticing. test_client_constants.py carries the same guard for the same
        reason.
        """
        rows = pack_model.load_manifest()

        self.assertTrue(
            rows,
            "%s names no models, so every budget check below is vacuous"
            % os.path.basename(pack_model.manifest_path()))

    def test_every_manifest_source_directory_exists(self):
        """
        A row naming a directory that is not there can never be repacked, and
        the failure would otherwise only surface the next time somebody ran
        --all and skimmed the output.
        """
        for source_dir, asset_key in pack_model.load_manifest():
            with self.subTest(asset_key=asset_key):
                self.assertTrue(
                    os.path.isdir(source_dir),
                    "%s names %s, which does not exist"
                    % (asset_key, source_dir))

    def test_every_manifest_source_names_a_family(self):
        """
        The family is the first path component under assets/, and it is what
        chooses the budget. A source outside assets/ has no family, so
        `_served_family` raises -- better here than mid-batch.
        """
        for source_dir, asset_key in pack_model.load_manifest():
            with self.subTest(asset_key=asset_key):
                family = pack_model._served_family(source_dir)

                self.assertTrue(family, "%s resolved to an empty family"
                                % asset_key)

    def test_every_budget_is_positive_and_described(self):
        """
        A zero or negative ceiling would silently pass everything or fail
        everything. `reason` is required because a number nobody justified is
        one the next person edits rather than argues with.
        """
        listed = dict(asset_budgets.FAMILY_BUDGETS)
        listed["<default>"] = asset_budgets.DEFAULT_BUDGET

        for family, budget in listed.items():
            with self.subTest(family=family):
                self.assertGreater(budget.max_texture_edge, 0)
                self.assertGreater(budget.max_bytes, 0)
                self.assertTrue(budget.reason.strip(),
                                "%s has no stated reason" % family)

    def test_an_unlisted_family_falls_back_rather_than_raising(self):
        """
        Adding assets/vehicles/ must be packable the day it is created, the
        same way an unknown asset key already draws a generic mesh. The
        fallback is the tightest tier, so not being listed costs a smaller
        model rather than an unbounded one.
        """
        fallback = asset_budgets.budget_for("a-family-nobody-has-added")

        self.assertEqual(fallback, asset_budgets.DEFAULT_BUDGET)

        for family, budget in asset_budgets.FAMILY_BUDGETS.items():
            with self.subTest(family=family):
                self.assertGreaterEqual(
                    budget.max_texture_edge,
                    asset_budgets.DEFAULT_BUDGET.max_texture_edge,
                    "%s is tighter than the default, so the default is no "
                    "longer the tightest tier the docstring claims" % family)
