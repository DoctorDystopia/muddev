"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/03/2026
Description: Tests for the profiling harness's own machinery.

             What is asserted here is the machinery, never a measured number.
             A test that pinned serialize_area to 1.8ms would fail on a slower
             machine, on a busy CI worker, and on the day somebody legitimately
             added a field -- and would be edited rather than read, which is
             the failure mode CLAUDE.md describes for registry censuses.

             So: that the registry registers, that the severity bands are
             ordered and total, that a failing scenario is reported rather than
             raised, and that the report renders what it was given.

Run from blackout/:
    ../evenv/Scripts/evennia.exe test --settings test_settings.py \\
        systems.profiling
"""

import unittest

from systems.profiling import constants as const
from systems.profiling import instruments, report
from systems.profiling.scenarios import SCENARIO_REGISTRY, scenarios_for


# ─── Private helper routines ─────────────────────────────────────────────────

def _measurement(name="probe",
                 layer=const.LAYER_STATEFEED,
                 seconds=0.0,
                 queries=0,
                 error=""):
    """Build a Measurement without measuring anything."""
    return instruments.Measurement(name=name,
                                   layer=layer,
                                   repeat=1,
                                   total_seconds=seconds,
                                   query_count=queries,
                                   duplicate_queries=0,
                                   call_count=0,
                                   error=error)


# ─── Public routines / Classes ───────────────────────────────────────────────

class TestScenarioRegistry(unittest.TestCase):
    """Discovery finds every scenario module without anything naming them."""

    def test_every_layer_has_at_least_one_scenario(self):
        """The audit's claim is end-to-end coverage; this is that claim.

        Derived from PIPELINE_LAYERS rather than from a list of expected
        names, so adding a scenario never edits this test and REMOVING a
        layer's last scenario fails it.
        """
        entries = scenarios_for()
        covered = set()

        for entry in entries:
            covered.add(entry.layer)

        for layer in const.PIPELINE_LAYERS:
            with self.subTest(layer=layer):
                self.assertIn(layer, covered,
                              f"no profiling scenario covers the {layer} "
                              "layer; the audit cannot claim to cover the "
                              "pipeline end to end")


    def test_every_registered_scenario_is_well_formed(self):
        """Every entry names a real layer, a callable, and a positive repeat."""
        scenarios_for()

        for name, entry in SCENARIO_REGISTRY.items():
            with self.subTest(scenario=name):
                self.assertIn(entry.layer, const.PIPELINE_LAYERS)
                self.assertTrue(callable(entry.factory))
                self.assertGreater(entry.repeat, 0)
                self.assertEqual(entry.name, name)


    def test_layers_are_reported_in_pipeline_order(self):
        """A report walks the pipeline front to back, not registration order."""
        entries = scenarios_for()
        seen_order = []

        for entry in entries:
            if entry.layer not in seen_order:
                seen_order.append(entry.layer)

        expected = [layer for layer in const.PIPELINE_LAYERS
                    if layer in seen_order]

        self.assertEqual(seen_order, expected)


    def test_an_unknown_layer_is_refused_at_decoration(self):
        """A typo in a layer name must fail at import, not mid-run."""
        from systems.profiling.scenarios import scenario

        with self.assertRaises(ValueError):
            scenario(name="never registered", layer="renderer")


class TestSeverityBands(unittest.TestCase):
    """The bands are total, ordered, and judged worst-dimension-first."""

    def test_a_faster_scenario_is_never_more_severe(self):
        """Monotonic in duration, which a hand-written ladder can get wrong."""
        ladder = (const.SEVERITY_OK,
                  const.SEVERITY_LOW,
                  const.SEVERITY_MEDIUM,
                  const.SEVERITY_HIGH,
                  const.SEVERITY_CRITICAL)

        durations = (0.0,
                     const.DURATION_LOW_SECONDS,
                     const.DURATION_MEDIUM_SECONDS,
                     const.DURATION_HIGH_SECONDS,
                     const.DURATION_CRITICAL_SECONDS)

        for expected, seconds in zip(ladder, durations):
            with self.subTest(seconds=seconds):
                measurement = _measurement(seconds=seconds)
                verdict = report.severity_for(measurement)

                self.assertEqual(verdict, expected)


    def test_a_query_storm_is_severe_even_when_fast(self):
        """A fast scenario issuing hundreds of queries is fast only locally."""
        measurement = _measurement(seconds=0.0,
                                   queries=const.QUERIES_CRITICAL)
        verdict = report.severity_for(measurement)

        self.assertEqual(verdict, const.SEVERITY_CRITICAL)


    def test_severity_takes_the_worse_of_the_two_dimensions(self):
        """Fixing only the cheaper dimension must not clear the verdict."""
        measurement = _measurement(seconds=0.0,
                                   queries=const.QUERIES_HIGH)
        verdict = report.severity_for(measurement)

        self.assertEqual(verdict, const.SEVERITY_HIGH)


    def test_a_failed_scenario_is_critical_not_fast(self):
        """Zero duration on a scenario that raised is an absence, not a pass."""
        measurement = _measurement(error="ValueError: boom")
        verdict = report.severity_for(measurement)

        self.assertEqual(verdict, const.SEVERITY_CRITICAL)


    def test_the_run_is_graded_by_its_worst_row(self):
        """One critical row makes the run critical."""
        rows = [_measurement(name="fine"),
                _measurement(name="bad", seconds=1.0)]
        overall = report.worst_severity(rows)

        self.assertEqual(overall, const.SEVERITY_CRITICAL)


class TestInstruments(unittest.TestCase):
    """measure() reports failures rather than raising them."""

    def test_a_raising_scenario_is_recorded_not_raised(self):
        """A harness run must report the scenarios that worked."""
        def explode():
            raise RuntimeError("scenario is broken")

        measurement = instruments.measure(name="broken",
                                          layer=const.LAYER_ENGINE,
                                          work=explode,
                                          repeat=1,
                                          warmup=0)

        self.assertTrue(measurement.failed)
        self.assertIn("RuntimeError", measurement.error)
        self.assertEqual(measurement.total_seconds, 0.0)


    def test_an_unknown_layer_raises(self):
        """A layer typo is the caller's bug and must not be measured around."""
        with self.assertRaises(ValueError):
            instruments.measure(name="probe",
                                layer="renderer",
                                work=lambda: None,
                                repeat=1,
                                warmup=0)


    def test_per_pass_divides_by_the_repeat_count(self):
        """The comparable number is per-pass, not per-run."""
        measurement = instruments.Measurement(name="probe",
                                              layer=const.LAYER_ENGINE,
                                              repeat=4,
                                              total_seconds=1.0,
                                              query_count=0,
                                              duplicate_queries=0,
                                              call_count=0)

        self.assertAlmostEqual(measurement.per_pass_seconds, 0.25)


    def test_a_zero_repeat_does_not_divide_by_zero(self):
        """A failed measurement carries repeat=0 and is still renderable."""
        measurement = instruments.Measurement(name="probe",
                                              layer=const.LAYER_ENGINE,
                                              repeat=0,
                                              total_seconds=2.0,
                                              query_count=0,
                                              duplicate_queries=0,
                                              call_count=0)

        self.assertEqual(measurement.per_pass_seconds, 2.0)


class TestReportRendering(unittest.TestCase):
    """The report renders what it was given and nothing it was not."""

    def test_an_empty_layer_is_omitted_rather_than_printed_empty(self):
        """A heading with no rows under it reads as a measurement of zero."""
        rows = [_measurement(layer=const.LAYER_STATEFEED)]
        table = report.render_table(rows)

        self.assertIn(const.LAYER_LABELS[const.LAYER_STATEFEED], table)
        self.assertNotIn(const.LAYER_LABELS[const.LAYER_WEB], table)


    def test_a_failed_row_shows_its_error(self):
        """A reader must be able to tell a broken row from a fast one."""
        rows = [_measurement(name="broken", error="ValueError: boom")]
        table = report.render_table(rows)

        self.assertIn("ERROR", table)
        self.assertIn("boom", table)


    def test_json_carries_the_derived_severity(self):
        """Storing the verdict is what lets a later run say 'this got worse'."""
        import json

        rows = [_measurement(name="probe", seconds=1.0)]
        document = report.to_json(rows)
        parsed = json.loads(document)

        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["severity"], const.SEVERITY_CRITICAL)
        self.assertEqual(parsed[0]["name"], "probe")


    def test_a_measurement_with_no_profile_renders_a_note(self):
        """render_profile must not raise on a scenario that never ran."""
        measurement = _measurement(name="broken", error="ValueError: boom")
        rendered = report.render_profile(measurement)

        self.assertIn("broken", rendered)
        self.assertIn("boom", rendered)
