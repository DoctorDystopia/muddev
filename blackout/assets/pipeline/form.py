"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/02/2026
Description: The model form: `add` with no questions, for the Godot editor
             (godot/addons/blackout_models). Four commands of __main__ run
             it. Each one writes its answer to a JSON file:

               add-options ANSWER         the lists of the form
               add-polyhaven ID ANSWER    what Poly Haven says of a model
               add-check PLAN ANSWER      the problem of each field, the
                                          defaults, and each file to write
               add-write PLAN ANSWER      check again, then write, then
                                          build when the plan asks

             PLAN is a JSON file of the answers, one key for each FIELD_*
             constant. An empty field takes its default, as Enter does in
             the wizard. The answer gives each default, so the form shows
             what an empty field takes.

             WHY A FILE, NOT THE OUTPUT. The Godot bridge (FigurePipeline)
             reads stdout and stderr as one text, and a build prints lines.
             An answer in a file stays whole JSON.

             THE FORM DECIDES NO RULE. Each check is a routine of the model
             plan (plans.py) or of figure.py: the same routine that the
             terminal wizard asks. The form only sends all the answers at
             one time.

             A WARNING NEEDS A YES, AS IN THE WIZARD. An asset key or an
             alias that the game does not name needs `keep_unnamed`. A
             source that the license gate refuses needs `use_refused_source`.
             The form shows each one as a box to tick.

             Nick chose this shape on 11/02/2026: a form and JSON commands,
             not the wizard over a pipe.

             Reads and writes files only. It touches no database.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Callable

from assets.pipeline import (build, fetch, figure, licenses, paths, plans,
                             questions, records, sources)


# ─── Public constant definitions ─────────────────────────────────────────────

# The format of a plan file and of an answer file.
FORM_FORMAT: int = 1

# The keys of a plan file. godot/addons/blackout_models/model_pipeline.gd
# names the same keys, and test_model_form.py compares the two.
FIELD_FORMAT: str = "format"
FIELD_ORIGIN: str = "origin"
FIELD_UPLOAD: str = "upload"
FIELD_POLYHAVEN: str = "polyhaven"
FIELD_SOURCE_ID: str = "source_id"
FIELD_LICENSE: str = "license"
FIELD_EXCEPTION: str = "exception"
FIELD_TITLE: str = "title"
FIELD_AUTHOR: str = "author"
FIELD_URL: str = "url"
FIELD_SITE: str = "site"
FIELD_NOTES: str = "notes"
FIELD_MODEL_FILE: str = "model_file"
FIELD_FAMILY: str = "family"
FIELD_ASSET_KEY: str = "asset_key"
FIELD_ALIASES: str = "aliases"
FIELD_VARIANT: str = "variant_of"
FIELD_KEEP_UNNAMED: str = "keep_unnamed"
FIELD_USE_REFUSED: str = "use_refused_source"
FIELD_BUILD: str = "build"


class FormError(RuntimeError):
    """A plan file that does not read, or that has another format."""


# ─── Private constant definitions ────────────────────────────────────────────

# The flag that says yes to the warning of each field.
_WARNING_FLAGS: dict = {
    FIELD_ASSET_KEY: FIELD_KEEP_UNNAMED,
    FIELD_ALIASES: FIELD_KEEP_UNNAMED,
    FIELD_SOURCE_ID: FIELD_USE_REFUSED,
}

_REQUIRED: str = "Type an answer."
_NO_ALIAS: str = ("An export takes no alias and no base. Add them to its "
                  "model record after the import.")


@dataclass
class _Check:
    """The answers of one plan file, and what the check found so far."""

    content: dict
    all_records: list
    key_list: object
    plan: plans.Plan = None
    problems: dict = field(default_factory=dict)
    warnings: dict = field(default_factory=dict)
    defaults: dict = field(default_factory=dict)


# ─── Private helper routines: the plan file ──────────────────────────────────

def _text(content: dict, key: str) -> str:
    """Give one text field of a plan, stripped, or "" for anything else."""
    value = content.get(key, "")

    return value.strip() if isinstance(value, str) else ""


def _flag(content: dict, key: str) -> bool:
    """Tell whether one flag of a plan is true."""
    return content.get(key) is True


def _aliases(content: dict) -> tuple:
    """Give the aliases of a plan: a list, or a text with commas."""
    value = content.get(FIELD_ALIASES, "")

    if isinstance(value, list):
        value = ",".join(str(alias) for alias in value)

    return plans.split_aliases(value) if isinstance(value, str) else ()


def _upload_of(check: _Check) -> str:
    """Give the upload path of a plan, as the wizard reads a typed path."""
    return questions.clean_path(_text(check.content, FIELD_UPLOAD))


# ─── Private helper routines: the origins ────────────────────────────────────

def _upload_files(check: _Check, upload: str) -> tuple:
    """Give the model files of an upload, or note the problem of the path."""
    if not upload:
        check.problems[FIELD_UPLOAD] = "Choose a file, a folder or a .zip."
        return ()

    if not os.path.exists(upload):
        check.problems[FIELD_UPLOAD] = "%s does not exist." % upload
        return ()

    found = plans.upload_model_files(upload)

    if not found:
        check.problems[FIELD_UPLOAD] = ("%s holds no model file that the "
                                        "build reads." % upload)

    return found


def _license_of(check: _Check) -> tuple:
    """Give (SPDX id, exception) of a new source, and note each problem."""
    spdx = _text(check.content, FIELD_LICENSE)
    exception = _text(check.content, FIELD_EXCEPTION)
    passes = licenses.is_allowed(spdx)

    if not spdx:
        check.problems[FIELD_LICENSE] = "Choose the license."
    elif not passes and not exception:
        check.problems[FIELD_EXCEPTION] = (
            "The license gate refuses %s. Give the reason of an exception."
            % spdx)

    return spdx, "" if passes else exception


def _credit_of(check: _Check, key: str, default: str) -> str:
    """Give one credit field, or its default, and note an empty answer."""
    value = _text(check.content, key) or default
    check.defaults[key] = default

    if not value:
        check.problems[key] = _REQUIRED

    return value


def _source_fields(check: _Check, name_hint: str) -> fetch.SourceFields:
    """
    Purpose: Give the source record of a new source from an upload.

    Entry:
        name_hint is the name of the upload, or "".

    Exit/Returns:
        Returns the SourceFields. Each empty field takes its default, and a
        field with no default is a problem.

    Module Globals:
        FIELD_* read.

    Author: Nick Hobar
    Creation date: 11/02/2026
    """
    spdx, exception = _license_of(check)
    defaults = plans.credit_defaults(spdx, name_hint)
    title = _credit_of(check, FIELD_TITLE, defaults["title"])
    author = _credit_of(check, FIELD_AUTHOR, defaults["author"])
    url = _credit_of(check, FIELD_URL, defaults["url"])
    site = _credit_of(check, FIELD_SITE, plans.site_for(url) if url else "")
    terms = licenses.terms_for(spdx)

    return fetch.SourceFields(
        title=title, author=author, url=url, site=site, license=spdx,
        notes=_text(check.content, FIELD_NOTES), exception=exception,
        local=terms.local_only)


def _file_origin(check: _Check) -> plans.Plan:
    """
    Purpose: Check the answers of a new source from a file, a folder or a
    .zip.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the plan, with the source and its model files.

    Module Globals:
        FIELD_SOURCE_ID read.

    Author: Nick Hobar
    Creation date: 11/02/2026
    """
    upload = _upload_of(check)
    found = _upload_files(check, upload)
    name_hint = questions.name_of(upload) if upload else ""
    fields = _source_fields(check, name_hint)
    default = plans.default_source_id(fields.site, name_hint) if (
        fields.site and name_hint) else ""
    source_id = _credit_of(check, FIELD_SOURCE_ID, default)
    problem = plans.new_source_problem(source_id) if source_id else ""

    if problem:
        check.problems[FIELD_SOURCE_ID] = problem

    return plans.Plan(upload=upload, fields=fields, source_id=source_id,
                      source_note=plans.upload_note(upload, fields),
                      name_hint=name_hint, model_files=found)


def _polyhaven_id_problem(asset_id: str, source_id: str) -> str:
    """Tell why a Poly Haven id cannot be a new source, or give ""."""
    fits = bool(asset_id) and records.is_key(source_id)

    if not fits:
        return "A Poly Haven id uses only a-z, 0-9 and _."

    if plans.source_exists(source_id):
        return ("sources/%s exists already. Choose it as a source that is "
                "in sources/." % source_id)

    return ""


def _polyhaven_origin(check: _Check) -> plans.Plan:
    """
    Purpose: Check the answers of a Poly Haven model.

    Entry:
        The form puts the title, the author and the model file of
        add-polyhaven into the plan.

    Exit/Returns:
        Returns the plan. Its model has no file list, so the write reads
        the API again.

    Module Globals:
        FIELD_* read.

    Author: Nick Hobar
    Creation date: 11/02/2026
    """
    typed = _text(check.content, FIELD_POLYHAVEN)
    asset_id = typed.rstrip("/").split("/")[-1]
    source_id = fetch.polyhaven_source_id(asset_id)
    main_file = _text(check.content, FIELD_MODEL_FILE)
    problem = _polyhaven_id_problem(asset_id, source_id)

    if not problem and not main_file:
        problem = "Look the model up first."

    if problem:
        check.problems[FIELD_POLYHAVEN] = problem

    model = fetch.PolyHavenModel(
        asset_id=asset_id, title=_text(check.content, FIELD_TITLE) or asset_id,
        author=_text(check.content, FIELD_AUTHOR) or fetch.TODO,
        main_file=main_file)

    return plans.Plan(polyhaven=model, fields=fetch.polyhaven_fields(model),
                      source_id=source_id,
                      source_note=plans.polyhaven_note(model),
                      name_hint=asset_id,
                      model_files=(main_file,) if main_file else ())


def _source_origin(check: _Check) -> plans.Plan:
    """
    Purpose: Check the answers of a source that is in sources/ already.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the plan. A source that the license gate refuses gives a
        warning, not a problem.

    Module Globals:
        FIELD_SOURCE_ID read.

    Author: Nick Hobar
    Creation date: 11/02/2026
    """
    source_id = _text(check.content, FIELD_SOURCE_ID)

    if not source_id:
        check.problems[FIELD_SOURCE_ID] = "Choose a source."
        return plans.Plan()

    try:
        source = sources.load_source(source_id)
    except sources.SourceError as problem:
        check.problems[FIELD_SOURCE_ID] = str(problem)
        return plans.Plan(source_id=source_id)

    problem = plans.source_problem(source)
    refusal = sources.gate_problem(source)

    if problem:
        check.problems[FIELD_SOURCE_ID] = problem
        return plans.Plan(source_id=source_id)

    if refusal:
        check.warnings[FIELD_SOURCE_ID] = (
            "The build refuses this source until you correct its "
            "source.toml: " + refusal)

    found = plans.folder_model_files(source.directory)

    return plans.Plan(source_id=source_id, model_files=found)


def _export_origin(check: _Check) -> plans.Plan:
    """
    Purpose: Check the answers of a new export of art made here.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the plan with the upload and the author. _finish_export
        names its source and its file when the key is known.

    Module Globals:
        FIELD_AUTHOR read.

    Author: Nick Hobar
    Creation date: 11/02/2026
    """
    upload = _upload_of(check)
    found = _upload_files(check, upload)
    exported = os.path.isfile(upload)

    if found and not exported:
        check.problems[FIELD_UPLOAD] = ("An export is one model file, not a "
                                        "folder or a .zip.")

    author = _credit_of(check, FIELD_AUTHOR, figure.DEFAULT_AUTHOR)
    name_hint = questions.name_of(upload) if upload else ""

    return plans.Plan(upload=upload, name_hint=name_hint,
                      fields=fetch.SourceFields(
                          title="", author=author, url=figure.OWNED_URL,
                          site=figure.OWNED_SITE,
                          license=licenses.OWNED_LICENSE),
                      model_files=found if exported else ())


def _new_key_problem(check: _Check, key: str) -> str:
    """Refuse an asset key that is no key, or that a record has already."""
    owners = plans.owners_of(check.all_records)

    return plans.key_problem(key, owners)


def _export_key_problem(check: _Check, key: str) -> str:
    """Refuse what figure.import_model refuses. Its own record passes."""
    plan = check.plan

    if not plan.upload or not plan.family:
        return ""

    return figure.import_problem(plan.family, key, plan.upload)


def _finish_nothing(check: _Check) -> plans.Plan:
    """Keep the plan as the checks left it."""
    return check.plan


def _finish_export(check: _Check) -> plans.Plan:
    """Name the source and the file of an export from its key."""
    plan = check.plan

    return plans.export_plan(plan.upload, plan.fields.author, plan.family,
                             plan.asset_key)


@dataclass(frozen=True)
class _OriginRule:
    """
    How the form checks one origin. build checks the answers of the origin
    and gives the plan. key_problem checks the asset key. aliases is True
    when the origin takes aliases and a base. finish gives the plan to
    write, after every check.
    """

    build: Callable
    key_problem: Callable
    aliases: bool
    finish: Callable


# The rule of each origin. A fifth origin is one more row, beside its rows
# in plans.py.
_ORIGIN_RULES: dict = {
    plans.ORIGIN_FILE: _OriginRule(_file_origin, _new_key_problem, True,
                                   _finish_nothing),
    plans.ORIGIN_POLYHAVEN: _OriginRule(_polyhaven_origin, _new_key_problem,
                                        True, _finish_nothing),
    plans.ORIGIN_SOURCE: _OriginRule(_source_origin, _new_key_problem, True,
                                     _finish_nothing),
    plans.ORIGIN_EXPORT: _OriginRule(_export_origin, _export_key_problem,
                                     False, _finish_export),
}


# ─── Private helper routines: the fields of every origin ─────────────────────

def _check_model_file(check: _Check) -> None:
    """Choose the model file: the typed one, or the only one of the source."""
    files = check.plan.model_files
    chosen = _text(check.content, FIELD_MODEL_FILE)

    if not files:
        return

    if chosen in files:
        check.plan.model_file = chosen
    elif len(files) == 1:
        check.plan.model_file = files[0]
    elif chosen:
        check.problems[FIELD_MODEL_FILE] = ("%s is not a model file of the "
                                            "source." % chosen)
    else:
        check.problems[FIELD_MODEL_FILE] = ("Choose the model file. The "
                                            "source holds %d." % len(files))


def _check_family(check: _Check) -> None:
    """Check the family: one of the list, or a new one."""
    family = _text(check.content, FIELD_FAMILY)
    problem = plans.new_family_problem(family) if family else (
        "Choose a family.")
    check.plan.family = family

    if problem:
        check.problems[FIELD_FAMILY] = problem


def _check_key(check: _Check, rule: _OriginRule) -> None:
    """Check the asset key, or its default."""
    owners = plans.owners_of(check.all_records)
    default = plans.default_key(check.plan, owners)
    key = _text(check.content, FIELD_ASSET_KEY) or default
    problem = rule.key_problem(check, key) if key else (
        "Type an asset key.")
    check.defaults[FIELD_ASSET_KEY] = default
    check.plan.asset_key = key

    if problem:
        check.problems[FIELD_ASSET_KEY] = problem


def _check_aliases_and_base(check: _Check, rule: _OriginRule) -> None:
    """Check the aliases and the base of a model variant."""
    aliases = _aliases(check.content)
    variant_of = _text(check.content, FIELD_VARIANT)
    owners = plans.owners_of(check.all_records)
    bases = {record.asset_key: record for record in check.all_records}
    key = check.plan.asset_key
    refused = not rule.aliases and bool(aliases or variant_of)
    alias_problem = _NO_ALIAS if refused else plans.aliases_problem(
        aliases, key, owners)
    variant_problem = "" if refused else plans.variant_problem(
        variant_of, key, bases)
    check.plan.aliases = aliases
    check.plan.variant_of = variant_of

    if alias_problem:
        check.problems[FIELD_ALIASES] = alias_problem

    if variant_problem:
        check.problems[FIELD_VARIANT] = variant_problem


def _check_named(check: _Check) -> None:
    """Warn about the asset key and each alias that the game does not name."""
    key = check.plan.asset_key
    unnamed = [alias for alias in check.plan.aliases
               if not plans.is_named(alias, check.key_list)]

    if key and not plans.is_named(key, check.key_list):
        check.warnings[FIELD_ASSET_KEY] = plans.unnamed_hint(
            key, check.key_list)

    if unnamed:
        check.warnings[FIELD_ALIASES] = " ".join(
            plans.unnamed_hint(alias, check.key_list) for alias in unnamed)


def _load_key_list() -> tuple:
    """Give (the rows of the key list or None, the problem or "")."""
    try:
        rows = plans.read_key_list(paths.KEY_LIST_PATH)
    except plans.KeyListError as problem:
        return None, "%s The form cannot check the asset key." % problem

    return rows, ""


def _check_plan(content: dict, all_records: list, key_list) -> _Check:
    """
    Purpose: Check every answer of one plan file.

    Entry:
        all_records holds every loaded model record. key_list is the rows
        of the key list, or None.

    Exit/Returns:
        Returns the _Check: the plan, the problems, the warnings and the
        defaults. An unknown origin is the only problem then.

    Module Globals:
        _ORIGIN_RULES read.

    Author: Nick Hobar
    Creation date: 11/02/2026
    """
    check = _Check(content=content, all_records=all_records,
                   key_list=key_list)
    origin = _text(content, FIELD_ORIGIN)
    rule = _ORIGIN_RULES.get(origin)

    if rule is None:
        check.problems[FIELD_ORIGIN] = "Choose where the model comes from."
        return check

    check.plan = rule.build(check)
    check.plan.origin = origin
    _check_model_file(check)
    _check_family(check)
    _check_key(check, rule)
    _check_aliases_and_base(check, rule)
    _check_named(check)
    check.plan = rule.finish(check)

    return check


# ─── Private helper routines: the answer ─────────────────────────────────────

def _is_ready(check: _Check) -> bool:
    """Tell whether a plan can be written: no problem, a yes to each warning."""
    accepted = all(_flag(check.content, _WARNING_FLAGS[key])
                   for key in check.warnings)

    return not check.problems and accepted


def _offered_rows(check: _Check) -> list:
    """Give the asset keys to offer for the family of the plan."""
    if check.key_list is None or check.plan is None:
        return []

    looks = plans.worn_look_keys()
    rows = plans.offered_keys(check.key_list, check.all_records,
                              check.plan.family, looks)

    return [{"key": row["key"], "kind": row["kind"], "name": row["name"],
             "worn_look": row["key"] in looks} for row in rows]


def _files_of(check: _Check) -> list:
    """Give each file of a plan with no problem, as JSON rows."""
    if check.problems or check.plan is None:
        return []

    return [{"path": planned.path, "note": planned.note,
             "text": planned.text} for planned in plans.preview(check.plan)]


def _answer(check: _Check, key_list_problem: str) -> dict:
    """
    Purpose: Give the answer of add-check for one checked plan.

    Entry:
        _check_plan made check.

    Exit/Returns:
        Returns the answer dict. Each key is a JSON value.

    Module Globals:
        FORM_FORMAT read.

    Author: Nick Hobar
    Creation date: 11/02/2026
    """
    plan = check.plan or plans.Plan()
    build_problem = build.tools_problem(plan.model_file) if (
        plan.model_file) else ""

    return {"format": FORM_FORMAT, "ready": _is_ready(check), "problem": "",
            "problems": check.problems, "warnings": check.warnings,
            "defaults": check.defaults, "model_files": list(plan.model_files),
            "model_file": plan.model_file, "asset_key": plan.asset_key,
            "offered": _offered_rows(check), "files": _files_of(check),
            "build_problem": build_problem,
            "key_list_problem": key_list_problem}


def _source_row(source_id: str, counts: dict) -> dict:
    """Give the row of one source for the source list of the form."""
    problem = ""
    refusal = ""

    try:
        source = sources.load_source(source_id)
        problem = plans.source_problem(source)
        refusal = sources.gate_problem(source)
    except sources.SourceError as failure:
        problem = str(failure)

    return {"id": source_id, "label": plans.source_label(source_id, counts),
            "problem": problem, "refusal": refusal}


# ─── Public routines ─────────────────────────────────────────────────────────

def read_plan(path: str) -> dict:
    """
    Purpose: Read one plan file.

    Entry:
        path names a JSON file that the form wrote.

    Exit/Returns:
        Returns the content. Raises FormError for a file that does not read,
        is no JSON object, or has another format.

    Module Globals:
        FORM_FORMAT, FIELD_FORMAT read.

    Author: Nick Hobar
    Creation date: 11/02/2026
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            content = json.load(handle)
    except (OSError, ValueError) as problem:
        raise FormError("the plan file %s does not read: %s" % (path, problem))

    whole = isinstance(content, dict)

    if not whole or content.get(FIELD_FORMAT) != FORM_FORMAT:
        raise FormError("the plan file %s is not a plan of format %d"
                        % (path, FORM_FORMAT))

    return content


def write_answer(path: str, answer: dict) -> None:
    """Write one answer file as JSON."""
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(answer, handle, indent=1)
        handle.write("\n")


def wants_build(content: dict) -> bool:
    """Tell whether a plan asks for a build after the write."""
    return _flag(content, FIELD_BUILD)


def options() -> dict:
    """
    Purpose: Give the lists of the form: the origins, the licenses, the
    families and the sources.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the answer dict. A model record that does not load gives a
        `problem`, and the lists stay empty.

    Module Globals:
        FORM_FORMAT read.

    Author: Nick Hobar
    Creation date: 11/02/2026
    """
    try:
        all_records = records.load_all()
    except records.RecordError as problem:
        return {"format": FORM_FORMAT, "problem": str(problem)}

    counts = plans.record_counts(all_records)
    allowed = licenses.ALLOWED_LICENSES

    return {"format": FORM_FORMAT, "problem": "",
            "origins": [{"key": key, "label": label}
                        for key, label in plans.ORIGIN_LABELS.items()],
            "licenses": [{"spdx": spdx, "name": terms.name,
                          "note": plans.license_note(terms)}
                         for spdx, terms in allowed.items()],
            "families": [{"key": family, "label": plans.family_label(family)}
                         for family in plans.families()],
            "sources": [_source_row(source_id, counts)
                        for source_id in sources.list_source_ids()],
            "model_suffixes": list(plans.MODEL_SUFFIXES),
            "zip_suffix": plans.ZIP_SUFFIX,
            "owned_license": licenses.OWNED_LICENSE,
            "default_author": figure.DEFAULT_AUTHOR}


def polyhaven(typed: str) -> dict:
    """
    Purpose: Read what Poly Haven says about one model, with no download.

    Entry:
        typed is a Poly Haven id, or the URL of its page.

    Exit/Returns:
        Returns the answer dict: ok, problem, and the title, the author,
        the model file and the number of files of the model.

    Module Globals:
        FORM_FORMAT read.

    Author: Nick Hobar
    Creation date: 11/02/2026
    """
    asset_id = typed.strip().rstrip("/").split("/")[-1]
    source_id = fetch.polyhaven_source_id(asset_id)
    answer = {"format": FORM_FORMAT, "ok": False, "asset_id": asset_id,
              "source_id": source_id, "title": "", "author": "",
              "model_file": "", "file_count": 0}
    answer["problem"] = _polyhaven_id_problem(asset_id, source_id)

    if answer["problem"]:
        return answer

    try:
        model = fetch.read_polyhaven(asset_id)
    except (fetch.FetchError, ValueError) as problem:
        answer["problem"] = str(problem)
        return answer

    answer.update({"ok": True, "title": model.title, "author": model.author,
                   "model_file": model.main_file,
                   "file_count": len(model.files)})

    return answer


def check(content: dict) -> dict:
    """
    Purpose: Check one plan, with no write.

    Entry:
        content came from read_plan.

    Exit/Returns:
        Returns the answer of add-check. A model record on disk that does
        not load gives a `problem`, and nothing is ready.

    Module Globals:
        FORM_FORMAT read.

    Author: Nick Hobar
    Creation date: 11/02/2026
    """
    try:
        all_records = records.load_all()
    except records.RecordError as problem:
        return {"format": FORM_FORMAT, "ready": False,
                "problem": str(problem)}

    key_list, key_list_problem = _load_key_list()
    checked = _check_plan(content, all_records, key_list)

    return _answer(checked, key_list_problem)


def write(content: dict) -> dict:
    """
    Purpose: Check one plan again, and write it when it is ready.

    Entry:
        content came from read_plan.

    Exit/Returns:
        Returns the answer of add-check, with `ok` and, after a write,
        `wrote` (the paths) and `record_path`. A plan that is not ready
        writes nothing.

    Module Globals:
        None.

    Notes:
        The check runs again because the disk can change between the
        check that the form showed and the click on Write.

    Author: Nick Hobar
    Creation date: 11/02/2026
    """
    try:
        all_records = records.load_all()
    except records.RecordError as problem:
        return {"format": FORM_FORMAT, "ok": False, "problem": str(problem)}

    key_list, key_list_problem = _load_key_list()
    checked = _check_plan(content, all_records, key_list)
    answer = _answer(checked, key_list_problem)
    answer["ok"] = False

    if not answer["ready"]:
        answer["problem"] = "The plan is not ready. Nothing was written."
        return answer

    try:
        written = plans.write(checked.plan)
    except (fetch.FetchError, sources.SourceError, figure.FigureError,
            OSError) as problem:
        answer["problem"] = str(problem)
        return answer

    answer.update({"ok": True, "wrote": [plans.shown(path)
                                         for path in written],
                   "record_path": plans.shown(written[-1])})

    return answer
