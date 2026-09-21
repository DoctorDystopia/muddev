"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/18/2026
Description: Build the served models from their model records.

             For each record, the build does four steps:

               1. INGEST. A glTF or GLB file goes on as it is. A picoCAD save
                  file goes through picocad.py. Any other format goes through
                  Blender (blender.py).
               2. RECIPE AND OPTIMIZE, in Node (build_model.mjs): take the
                  node, attach the texture, bake the [fix], then prune, dedup,
                  weld and resize to the family budget.
               3. VALIDATE with the Khronos glTF Validator. An error stops the
                  model.
               4. BUDGET. Bytes, triangles and texture edges against the
                  family budget. Over budget stops the model.

             Only a model that passes all four reaches the served tree.

             THE LOCK FILE (assets/build.lock.json) records, for each model,
             a digest of everything that went in and the SHA-256 of what came
             out. The check compares both, so an edited record, a changed
             download or a hand-dropped .glb fails the test suite until
             someone runs the build. The inputs are the record, the sealed
             hashes of its source, and the pipeline code itself.
"""

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass

from assets.pipeline import (blender, budgets, glb, paths, picocad, records,
                             sources)


# ─── Public constant definitions ─────────────────────────────────────────────

LOCK_PATH: str = os.path.join(paths.ASSETS_DIR, "build.lock.json")


class BuildError(RuntimeError):
    """One model could not be built. The message names the step."""


@dataclass(frozen=True)
class BuildResult:
    """What one successful build wrote, for the log and the lock file."""

    record: records.ModelRecord
    served_path: str
    summary: glb.GlbSummary
    inputs_digest: str
    output_digest: str
    skipped: bool


# ─── Private constant definitions ────────────────────────────────────────────

_PICOCAD_SUFFIX: str = ".txt"
_PICOCAD_GLTF: str = "scene.gltf"
_NODE_EXECUTABLE: str = "node"
_NODE_TIMEOUT_SECONDS: int = 300
_JOB_FILENAME: str = "job.json"
_OUTPUT_FILENAME: str = "model.glb"
_BLENDER_FILENAME: str = "ingest.glb"
_PICOCAD_DIRNAME: str = "picocad"
_HASH_PREFIX: str = "sha256:"

# The files whose content decides how a record becomes a .glb. A change to
# any of them changes every input digest, so the check asks for a rebuild.
_PIPELINE_FILES: tuple = (
    paths.NODE_SCRIPT,
    paths.BLENDER_SCRIPT,
    os.path.join(paths.ASSETS_DIR, "pipeline", "picocad.py"),
    os.path.join(paths.ASSETS_DIR, "package-lock.json"),
)


# ─── Private helper routines ─────────────────────────────────────────────────

def _text_digest(path: str) -> str:
    """
    Purpose: Hash a text file with its line endings made uniform.

    Entry:
        path names a readable text file.

    Exit/Returns:
        Returns the hex SHA-256 of the file with CRLF read as LF.

    Module Globals:
        None.

    Methodology:
        git can check a text file out with CRLF on Windows and LF elsewhere.
        A raw hash would then call every model stale on the other machine.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    with open(path, "rb") as handle:
        raw = handle.read()

    uniform = raw.replace(b"\r\n", b"\n")

    return hashlib.sha256(uniform).hexdigest()


def _file_digest(path: str) -> str:
    """
    Purpose: Hash one binary file, in the form the lock file stores.

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


def _job(record, source, input_path, output_path) -> dict:
    """
    Purpose: Write down, for the Node step, everything one record asks for.

    Entry:
        record and source are loaded. input_path is the ingested file.

    Exit/Returns:
        Returns the job as a dict, ready for JSON.

    Module Globals:
        None.

    Methodology:
        The family budget gives the texture edge unless the record sets one.
        A family in budgets.ALWAYS_OPAQUE_FAMILIES is opaque whatever the
        record says.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    budget = budgets.budget_for(record.family)
    edge = record.max_texture_edge or budget.max_texture_edge
    opaque = record.opaque or record.family in budgets.ALWAYS_OPAQUE_FAMILIES
    texture = None

    if record.texture_image:
        image = os.path.join(source.directory, record.texture_image)
        texture = {"image": image, "roughness": record.texture_roughness}

    fix = {"rotate": record.rotate, "opaque": opaque, "filter": record.filter}

    return {"input": input_path, "output": output_path, "node": record.node,
            "texture": texture, "fix": fix, "max_texture_edge": edge,
            "texture_format": record.texture_format,
            "allowed_extensions": sorted(glb.GODOT_RUNTIME_EXTENSIONS)}


def _ingest(record, source, work_dir) -> str:
    """
    Purpose: Give a path to a glTF or GLB file for one record's source file.

    Entry:
        record and source are loaded. work_dir exists.

    Exit/Returns:
        Returns the path the Node step reads. Raises BuildError when the
        source file is missing or the conversion fails.

    Module Globals:
        _PICOCAD_SUFFIX, _PICOCAD_DIRNAME, _PICOCAD_GLTF, _BLENDER_FILENAME
        read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    original = os.path.join(source.directory, record.file)
    suffix = os.path.splitext(original)[1].lower()

    if not os.path.isfile(original):
        raise BuildError("ingest: %s has no file %s"
                         % (source.source_id, record.file))

    if suffix in blender.GLTF_SUFFIXES:
        return original

    if suffix == _PICOCAD_SUFFIX:
        picocad_dir = os.path.join(work_dir, _PICOCAD_DIRNAME)
        picocad.convert(original, picocad_dir)

        return os.path.join(picocad_dir, _PICOCAD_GLTF)

    converted = os.path.join(work_dir, _BLENDER_FILENAME)

    try:
        blender.to_glb(original, converted)
    except blender.BlenderError as problem:
        raise BuildError("ingest: %s" % problem)

    return converted


def _run_node(command: str, argument: str) -> dict:
    """
    Purpose: Run one command of build_model.mjs and read its JSON answer.

    Entry:
        command is "build" or "validate". node_modules is installed.

    Exit/Returns:
        Returns the parsed JSON line. Raises BuildError with Node's error
        text when the process fails.

    Module Globals:
        paths.NODE_SCRIPT, paths.ASSETS_DIR, _NODE_EXECUTABLE,
        _NODE_TIMEOUT_SECONDS read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    process = [_NODE_EXECUTABLE, paths.NODE_SCRIPT, command, argument]
    finished = subprocess.run(process, capture_output=True, text=True,
                              cwd=paths.ASSETS_DIR, check=False,
                              timeout=_NODE_TIMEOUT_SECONDS, encoding="utf-8")

    if finished.returncode != 0:
        raise BuildError("%s: %s" % (command, finished.stderr.strip()))

    answer = json.loads(finished.stdout.strip().splitlines()[-1])

    return answer


def _check_budget(record, summary) -> None:
    """
    Purpose: Refuse a built model that breaks its family budget.

    Entry:
        summary describes the built file.

    Exit/Returns:
        Returns None. Raises BuildError that names every broken limit.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    problems = budgets.budget_problems(record.family, summary)

    if problems:
        raise BuildError("budget: %s" % "; ".join(problems))


def _validate(output_path) -> None:
    """
    Purpose: Refuse a built file that the glTF Validator finds errors in.

    Entry:
        output_path names a built .glb.

    Exit/Returns:
        Returns None. Raises BuildError with the first validator errors.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    report = _run_node("validate", output_path)

    if report["errors"]:
        raise BuildError("validate: %d error(s): %s"
                         % (report["errors"], "; ".join(report["messages"])))


# ─── Public routines ─────────────────────────────────────────────────────────

def inputs_digest(record: records.ModelRecord,
                  source: sources.Source) -> str:
    """
    Purpose: Give one digest of everything that decides one model's bytes.

    Entry:
        record and source are loaded.

    Exit/Returns:
        Returns "sha256:<hex>" over the record file, the sealed file hashes
        of its source, the family budget, and the pipeline code.

    Module Globals:
        _PIPELINE_FILES, _HASH_PREFIX read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    digest = hashlib.sha256()
    record_digest = _text_digest(record.record_path)
    sealed = json.dumps(source.files, sort_keys=True)
    budget = repr(budgets.budget_for(record.family))
    digest.update(record_digest.encode("utf-8"))
    digest.update(sealed.encode("utf-8"))
    digest.update(budget.encode("utf-8"))

    for path in _PIPELINE_FILES:
        code_digest = _text_digest(path)
        digest.update(code_digest.encode("utf-8"))

    hex_digest = digest.hexdigest()

    return _HASH_PREFIX + hex_digest


def read_lock() -> dict:
    """
    Purpose: Read the lock file.

    Entry:
        No conditions.

    Exit/Returns:
        Returns {asset_key: {"inputs": ..., "output": ...}}. Returns an
        empty dict when there is no lock file yet.

    Module Globals:
        LOCK_PATH read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    if not os.path.isfile(LOCK_PATH):
        return {}

    with open(LOCK_PATH, "r", encoding="utf-8") as handle:
        lock = json.load(handle)

    return lock


def write_lock(lock: dict) -> None:
    """
    Purpose: Write the lock file, sorted, with a final newline.

    Entry:
        lock has the shape that read_lock returns.

    Exit/Returns:
        Returns None.

    Module Globals:
        LOCK_PATH written.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    with open(LOCK_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(lock, handle, indent=2, sort_keys=True)
        handle.write("\n")


def build_one(record: records.ModelRecord, force: bool = False) -> BuildResult:
    """
    Purpose: Build one model and put it in the served tree.

    Entry:
        record is loaded. force is True to build even when the lock file
        says that nothing changed.

    Exit/Returns:
        Returns the BuildResult. Raises BuildError, sources.SourceError or
        picocad.PicoCADError when a step fails. The served file changes
        only when every step passes.

    Module Globals:
        paths.BUILD_DIR read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    source = sources.load_source(record.source_id)
    refusal = sources.gate_problem(source)

    if refusal:
        raise BuildError("license: %s: %s" % (source.source_id, refusal))

    digest = inputs_digest(record, source)
    served = paths.served_path(record.family, record.asset_key)
    locked = read_lock().get(record.asset_key, {})
    current = os.path.isfile(served) and _file_digest(served)
    fresh = locked.get("inputs") == digest and locked.get("output") == current

    if fresh and not force:
        summary = glb.summarize(served)

        return BuildResult(record, served, summary, digest, current, True)

    return _build_fresh(record, source, served, digest)


def _build_fresh(record, source, served, digest) -> BuildResult:
    """
    Purpose: Run the four steps for one model that is not fresh.

    Entry:
        record and source are loaded. The license gate passed.

    Exit/Returns:
        Returns the BuildResult. Raises BuildError when a step fails.

    Module Globals:
        paths.BUILD_DIR, _JOB_FILENAME, _OUTPUT_FILENAME read.

    Author: Nick Hobar
    Creation date: 09/18/2026
    """
    work_dir = os.path.join(paths.BUILD_DIR, record.asset_key)
    shutil.rmtree(work_dir, ignore_errors=True)
    os.makedirs(work_dir)
    input_path = _ingest(record, source, work_dir)
    output_path = os.path.join(work_dir, _OUTPUT_FILENAME)
    job = _job(record, source, input_path, output_path)
    job_path = os.path.join(work_dir, _JOB_FILENAME)

    with open(job_path, "w", encoding="utf-8") as handle:
        json.dump(job, handle, indent=2)

    _run_node("build", job_path)
    _validate(output_path)
    summary = glb.summarize(output_path)
    _check_budget(record, summary)
    os.makedirs(os.path.dirname(served), exist_ok=True)
    shutil.copyfile(output_path, served)
    output_digest = _file_digest(served)

    return BuildResult(record, served, summary, digest, output_digest, False)
