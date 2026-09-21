"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: Check that the model records, the sources and the served tree
             agree. Writes nothing.

             `python -m assets.pipeline check` prints the result and exits
             non-zero on a problem. test_model_pipeline.py runs the same
             routine, so the test suite fails on the same problems.

             A PROBLEM fails the check:
               - a record that does not load, or names a missing source/file
               - a source that fails the license gate, or whose files do not
                 match their sealed hashes
               - a served model that is missing, stale (the lock file
                 disagrees), over budget, not from the build, or that uses a
                 glTF extension Godot cannot read
               - a .glb in the served tree that no record builds
               - a generated file (manifest, credits) that differs from a
                 fresh render

             A WARNING does not fail the check, and the check prints it on
             every run, so it cannot be forgotten:
               - a source served under a license exception
               - a source that no record uses

             Needs no Node and no Blender. It reads files only.
"""

import glob
import hashlib
import os
from dataclasses import dataclass, field

from assets.pipeline import (budgets, build, glb, outputs, paths, records,
                             sources)


# ─── Public constant definitions ─────────────────────────────────────────────

@dataclass
class CheckReport:
    """Everything the check found. ok is True when problems is empty."""

    problems: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when nothing fails the check."""
        return not self.problems


# ─── Private constant definitions ────────────────────────────────────────────

_BUILD_GENERATOR: str = "Blackout model pipeline"
_HASH_PREFIX: str = "sha256:"
_REBUILD_HINT: str = "run `python -m assets.pipeline build`"


# ─── Private helper routines ─────────────────────────────────────────────────

def _file_digest(path: str) -> str:
    """
    Purpose: Hash one file, in the form the lock file stores.

    Entry:
        path names a readable file.

    Exit/Returns:
        Returns "sha256:<hex>".

    Module Globals:
        _HASH_PREFIX read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    with open(path, "rb") as handle:
        raw = handle.read()

    hex_digest = hashlib.sha256(raw).hexdigest()

    return _HASH_PREFIX + hex_digest


def _check_sources(report: CheckReport, used: set) -> dict:
    """
    Purpose: Check every source record, and return the ones that load.

    Entry:
        used holds the source ids that some record names.

    Exit/Returns:
        Returns {source_id: Source} for each source that loads. Adds problems
        and warnings to report.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    loaded = {}

    for source_id in sources.list_source_ids():
        try:
            source = sources.load_source(source_id)
        except sources.SourceError as problem:
            report.problems.append(str(problem))
            continue

        loaded[source_id] = source
        refusal = sources.gate_problem(source)
        drift = sources.hash_problems(source)

        if refusal:
            report.problems.append("%s: %s" % (source_id, refusal))

        if source.exception:
            report.warnings.append("%s is served under a license exception: "
                                   "%s" % (source_id, source.exception))

        for line in drift:
            report.problems.append("%s: %s. If the change is deliberate, run "
                                   "`python -m assets.pipeline seal %s`"
                                   % (source_id, line, source_id))

        if source_id not in used:
            report.warnings.append("%s: no model record uses this source"
                                   % source_id)

    return loaded


def _check_record_inputs(report, record, loaded) -> bool:
    """
    Purpose: Check that one record's source, file and texture exist.

    Entry:
        loaded is the dict _check_sources returned.

    Exit/Returns:
        Returns True when the inputs exist. Adds problems to report.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    where = "models/%s/%s.toml" % (record.family, record.asset_key)
    source = loaded.get(record.source_id)

    if source is None:
        report.problems.append("%s: no loadable source '%s'"
                               % (where, record.source_id))
        return False

    wanted = [record.file]

    if record.texture_image:
        wanted.append(record.texture_image)

    for relative in wanted:
        full = os.path.join(source.directory, relative)

        if not os.path.isfile(full):
            report.problems.append("%s: %s has no file %s"
                                   % (where, record.source_id, relative))
            return False

    return True


def _check_served(report, record, source, lock) -> None:
    """
    Purpose: Check one record's served model against the lock and budget.

    Entry:
        source is the loaded source of record. lock is the lock file.

    Exit/Returns:
        Returns None. Adds problems to report.

    Module Globals:
        _BUILD_GENERATOR, _REBUILD_HINT read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    key = record.asset_key
    served = paths.served_path(record.family, key)

    if not os.path.isfile(served):
        report.problems.append("%s: never built. %s" % (key, _REBUILD_HINT))
        return

    locked = lock.get(key, {})
    inputs = build.inputs_digest(record, source)
    output = _file_digest(served)
    summary = glb.summarize(served)
    unreadable = set(summary.extensions_used) - glb.GODOT_RUNTIME_EXTENSIONS

    if locked.get("inputs") != inputs:
        report.problems.append("%s: its inputs changed since the last build. "
                               "%s" % (key, _REBUILD_HINT))

    if locked.get("output") != output:
        report.problems.append("%s: the served file is not the one the build "
                               "wrote. %s" % (key, _REBUILD_HINT))

    if not summary.generator.startswith(_BUILD_GENERATOR):
        report.problems.append("%s: the served file did not come from the "
                               "build. %s" % (key, _REBUILD_HINT))

    if unreadable:
        report.problems.append("%s: uses %s, which Godot cannot read"
                               % (key, ", ".join(sorted(unreadable))))

    for line in budgets.budget_problems(record.family, summary):
        report.problems.append("%s [%s]: %s" % (key, record.family, line))


def _check_orphans(report, all_records) -> None:
    """
    Purpose: Report a served .glb that no record builds.

    Entry:
        all_records holds every loaded record.

    Exit/Returns:
        Returns None. Adds problems to report.

    Module Globals:
        paths.SERVED_DIR, paths.SERVED_SUFFIX read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    expected = {os.path.normcase(paths.served_path(record.family,
                                                   record.asset_key))
                for record in all_records}
    pattern = os.path.join(paths.SERVED_DIR, "*", "*" + paths.SERVED_SUFFIX)

    for path in sorted(glob.glob(pattern)):
        if os.path.normcase(path) in expected:
            continue

        relative = os.path.relpath(path, paths.SERVED_DIR)
        report.problems.append("%s is in the served tree, but no model record "
                               "builds it. Delete it, or add a record"
                               % relative.replace(os.sep, "/"))


def _check_generated(report) -> None:
    """
    Purpose: Compare every generated file with a fresh render.

    Entry:
        Every record and every source it names loads.

    Exit/Returns:
        Returns None. Adds problems to report.

    Module Globals:
        _REBUILD_HINT read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    for path, text in outputs.render_all().items():
        name = os.path.basename(path)

        if not os.path.isfile(path):
            report.problems.append("%s is missing. %s" % (name, _REBUILD_HINT))
            continue

        with open(path, "r", encoding="utf-8", newline="") as handle:
            committed = handle.read().replace("\r\n", "\n")

        if committed != text:
            report.problems.append("%s is stale. %s" % (name, _REBUILD_HINT))


# ─── Public routines ─────────────────────────────────────────────────────────

def run_check() -> CheckReport:
    """
    Purpose: Run every check of the model pipeline.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a CheckReport. Writes nothing.

    Module Globals:
        None.

    Methodology:
        1. Load the records. If one fails, report it and stop, because every
           later check reads the records.
        2. Check the sources, the inputs and the served file of each record.
        3. Look for orphaned .glb files and stale generated files.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    report = CheckReport()

    try:
        all_records = records.load_all()
    except records.RecordError as problem:
        report.problems.append(str(problem))
        return report

    if not all_records:
        report.problems.append("no model records under assets/models/")

    used = {record.source_id for record in all_records}
    loaded = _check_sources(report, used)
    lock = build.read_lock()

    for record in all_records:
        present = _check_record_inputs(report, record, loaded)

        if present:
            _check_served(report, record, loaded[record.source_id], lock)

    _check_orphans(report, all_records)

    if report.ok:
        _check_generated(report)

    return report
