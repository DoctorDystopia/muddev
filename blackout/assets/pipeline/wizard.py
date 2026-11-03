"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/25/2026
Description: The model wizard. `python -m assets.pipeline add` asks one
             question at a time, and adds one model to the pipeline. It does
             steps 1 to 4 of "Add a model" in assets/README.md, with no TODO
             to fill in later.

             THREE ORIGINS:
               1. A file, a folder or a .zip on this machine. Enter at the
                  path question opens a file dialog.
               2. A Poly Haven model. The API gives each field of the source
                  record.
               3. A source that is in sources/ already. One pack can feed
                  many models.

             THE QUESTIONS, in this order:
               1. The origin.
               2. For a new source: the license, the credit, the source id.
               3. The model file in the source.
               4. The family and the asset key. The wizard first shows each
                  asset key that the game names and no model draws yet. A
                  number picks one.
               5. The aliases, and the base of a model variant.

             AN ASSET KEY THAT THE GAME DOES NOT NAME GETS A WARNING
             (10/25/2026). The client then draws the model nowhere, and
             nothing says so. The bench of 10/25/2026 went in as
             gunsmith_bench, which is its object kind. The game draws it as
             gunbench. Thus, the warning asks, and a yes keeps the key.

             THE WIZARD WRITES NOTHING BEFORE THE CONFIRM. It shows the
             text of each record, and it writes only after a yes. Ctrl+C at
             any question before that leaves the disk as it was.

             THE WIZARD DECIDES NO RULE AND WRITES NO FILE ITSELF. Each check
             and each write is a routine of the model plan (plans.py). The
             model form of the Godot editor (form.py) uses the same
             routines, so the two cannot refuse different answers. The
             routines came out of this module on 11/02/2026.

             The build question comes last. __main__ runs the build, as it
             does for figure-model.

             The questions themselves (questions.py) are shared with the
             sound wizard, assets/audio/wizard.py.

             Reads and writes files only. It touches no database.
"""

import os
from dataclasses import dataclass

from assets.pipeline import (build, fetch, licenses, paths, plans, questions,
                             records, sources)
from assets.pipeline.questions import INDENT, Console


# ─── Public constant definitions ─────────────────────────────────────────────

@dataclass(frozen=True)
class WizardResult:
    """
    What the wizard wrote. build is True when the person asked for a build
    now and this machine can build.
    """

    asset_key: str
    record_path: str
    build: bool


# ─── Private constant definitions ────────────────────────────────────────────

# One row of the offered asset keys: the key and its kind, each in a column
# as wide as its longest text, then the name, then the worn look note.
_OFFER_LABEL: str = "%-*s  %-*s  %s%s"
_OFFER_HINT: str = "Type the key of one of them."

# An item with a worn look draws on the figure with no served model. A
# served model takes the place of that look in the hand.
_WORN_LOOK_NOTE: str = "  (it has a worn look)"

_BUILD_COMMAND: str = "../evenv/Scripts/python.exe -m assets.pipeline build %s"
_DIALOG_TITLE: str = "Choose a 3D model, a folder of one, or a .zip"
_DIALOG_MODELS: str = "3D models and .zip files"

_STOPPED: str = "  Stopped. Nothing was written."

# The columns of a row of _ORIGINS.
_ROW_ORIGIN: int = 0
_ROW_ASKER: int = 1


# ─── Private helper routines: a new source from a file ───────────────────────

def _pick_model_file() -> str:
    """Open the file dialog on the model files and the .zip files."""
    suffixes = plans.MODEL_SUFFIXES + (plans.ZIP_SUFFIX,)
    chosen = questions.open_file_dialog(_DIALOG_TITLE, _DIALOG_MODELS,
                                        suffixes)

    return chosen


def _ask_upload(console: Console) -> tuple:
    """
    Purpose: Ask for the path of an upload until it holds a model file.

    Entry:
        No conditions.

    Exit/Returns:
        Returns (path, its model files). Enter at the question opens the
        file dialog.

    Module Globals:
        questions.PROMPT, INDENT, plans.MODEL_SUFFIXES read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    readable = " ".join(plans.MODEL_SUFFIXES)
    console.say("")
    console.say("Type the path of the file, the folder or the .zip. You can "
                "drag it here. Press Enter to open a file dialog.")

    while True:
        typed = console.ask(questions.PROMPT)
        path = questions.clean_path(typed)

        if not path:
            path = console.pick_file()

        if not path:
            console.say(INDENT + "No file was chosen. Type a path.")
            continue

        if not os.path.exists(path):
            console.say(INDENT + "%s does not exist." % path)
            continue

        found = plans.upload_model_files(path)

        if found:
            return path, found

        console.say(INDENT + "%s holds no model file that the build reads: "
                    "%s, or a .zip of them." % (path, readable))


def _ask_license(console: Console) -> tuple:
    """Ask for the license of a new source: (SPDX id, exception)."""
    spdx, exception = questions.ask_license(
        console, "Which license does the download page give? On itch.io, "
        "each page has its own.", "Why can Blackout serve it? The check "
        "shows this reason on each run.", plans.license_note)

    return spdx, exception


def _ask_credits(console: Console, spdx: str, exception: str,
                 name_hint: str) -> fetch.SourceFields:
    """
    Purpose: Ask for the credit fields of a new source record.

    Entry:
        spdx and exception came from _ask_license.

    Exit/Returns:
        Returns the SourceFields. A local_only license gives a local source.

    Module Globals:
        None.

    Notes:
        plans.credit_defaults gives the defaults.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    terms = licenses.terms_for(spdx)
    defaults = plans.credit_defaults(spdx, name_hint)
    title = questions.ask_text(console, "The title of the model.",
                               defaults["title"], questions.required)
    author = questions.ask_text(console, "Who made it? The credits box shows "
                                "this name.", defaults["author"],
                                questions.required)
    url = questions.ask_text(console, "The URL of the download page.",
                             defaults["url"], questions.required)
    site = questions.ask_text(console, "The site of the download.",
                              plans.site_for(url), questions.required)
    notes = questions.ask_text(console, "Notes for the next person, for "
                               "example the name of the .zip. Press Enter "
                               "for none.")

    return fetch.SourceFields(title=title, author=author, url=url, site=site,
                              license=spdx, notes=notes, exception=exception,
                              local=terms.local_only)


def _ask_source_id(console: Console, site: str, name_hint: str) -> str:
    """
    Purpose: Ask for the source id of a new source.

    Entry:
        site is the site of the source record.

    Exit/Returns:
        Returns a free source id. The default is the first word of the
        site and the name of the download: itch_rusty_sword.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    default = plans.default_source_id(site, name_hint)

    return questions.ask_text(console, "The source id: the name of its "
                              "directory in sources/.", default,
                              plans.new_source_problem)


def _ask_file_origin(console: Console, _all_records: list) -> plans.Plan:
    """
    Purpose: Ask the questions of a new source from a file, a folder or a
    .zip.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the plan, with the source and its model files.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    upload, found = _ask_upload(console)
    name_hint = questions.name_of(upload)
    spdx, exception = _ask_license(console)
    fields = _ask_credits(console, spdx, exception, name_hint)
    source_id = _ask_source_id(console, fields.site, name_hint)

    return plans.Plan(upload=upload, fields=fields, source_id=source_id,
                      source_note=plans.upload_note(upload, fields),
                      name_hint=name_hint, model_files=found)


# ─── Private helper routines: the other origins ──────────────────────────────

def _ask_polyhaven_origin(console: Console, _all_records: list) -> plans.Plan:
    """
    Purpose: Ask for a Poly Haven model, and read what the API gives.

    Entry:
        No conditions. The API needs the network.

    Exit/Returns:
        Returns the plan. Returns None when the source exists already,
        because the person can choose that source as an origin.

    Module Globals:
        INDENT read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    while True:
        typed = questions.ask_text(console, "The Poly Haven id of the model: "
                                   "the end of its page URL, for example "
                                   "wooden_crate_01.",
                                   check=questions.required)
        asset_id = typed.rstrip("/").split("/")[-1]
        source_id = fetch.polyhaven_source_id(asset_id)
        fits = records.is_key(source_id)
        exists = plans.source_exists(source_id)

        if not fits:
            console.say(INDENT + "A Poly Haven id uses only a-z, 0-9 and _.")
            continue

        if exists:
            console.say(INDENT + "sources/%s exists already. Choose it as a "
                        "source that is in sources/." % source_id)
            return None

        try:
            model = fetch.read_polyhaven(asset_id)
        except fetch.FetchError as problem:
            console.say(INDENT + str(problem))
            continue

        console.say(INDENT + "Found %s, by %s." % (model.title, model.author))
        fields = fetch.polyhaven_fields(model)

        return plans.Plan(polyhaven=model, fields=fields, source_id=source_id,
                          source_note=plans.polyhaven_note(model),
                          name_hint=asset_id, model_files=(model.main_file,))


def _source_usable(console: Console, source_id: str) -> bool:
    """
    Purpose: Tell whether the person can take a model from one source.

    Entry:
        source_id is a directory in sources/.

    Exit/Returns:
        Returns False for a source that does not load or has no model
        file. A source that fails the license gate needs a yes.

    Module Globals:
        INDENT read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    try:
        source = sources.load_source(source_id)
    except sources.SourceError as problem:
        console.say(INDENT + str(problem))
        return False

    problem = plans.source_problem(source)
    refusal = sources.gate_problem(source)

    if problem:
        console.say(INDENT + problem)
        return False

    if not refusal:
        return True

    console.say(INDENT + "The build refuses this source until you correct "
                "its source.toml: " + refusal)
    use_it = questions.ask_yes(console, "Use it anyway?", False)

    return use_it


def _ask_source_origin(console: Console, all_records: list) -> plans.Plan:
    """
    Purpose: Ask the person to choose a source that is in sources/ already.

    Entry:
        all_records holds every loaded model record.

    Exit/Returns:
        Returns the plan. Returns None when sources/ is empty.

    Module Globals:
        INDENT read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    source_ids = sources.list_source_ids()
    counts = plans.record_counts(all_records)

    if not source_ids:
        console.say(INDENT + "sources/ holds no source. Choose another "
                    "origin.")
        return None

    labels = [plans.source_label(source_id, counts)
              for source_id in source_ids]
    usable = False

    while not usable:
        chosen = questions.ask_choice(console, "Which source holds the "
                                      "model?", labels)
        source_id = source_ids[chosen]
        usable = _source_usable(console, source_id)

    directory = os.path.join(paths.SOURCES_DIR, source_id)
    found = plans.folder_model_files(directory)

    return plans.Plan(source_id=source_id, model_files=found)


# ─── Private helper routines: the key list ───────────────────────────────────

def _load_key_list(console: Console):
    """
    Purpose: Read the key list for the asset key questions.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the rows. Returns None when the file does not read. Then
        the wizard offers no key, and it warns about no key.

    Module Globals:
        paths.KEY_LIST_PATH read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    try:
        rows = plans.read_key_list(paths.KEY_LIST_PATH)
    except plans.KeyListError as problem:
        console.say("")
        console.say("%s The wizard cannot check the asset key." % problem)
        return None

    return rows


def _show_offer(console: Console, offered: list, looks: set) -> None:
    """Show the offered asset keys, with a number on each."""
    key_width = max(len(row["key"]) for row in offered)
    kind_width = max(len(row["kind"]) for row in offered)
    labels = [_OFFER_LABEL % (key_width, row["key"], kind_width, row["kind"],
                              row["name"],
                              _WORN_LOOK_NOTE if row["key"] in looks else "")
              for row in offered]
    console.say("")
    console.say("The game names these asset keys, and no model record draws "
                "them yet:")
    questions.show_rows(console, labels, list(range(len(labels))), _OFFER_HINT)


def _keep_key(console: Console, key: str, key_list) -> bool:
    """
    Purpose: Ask about an asset key that the game does not name.

    Entry:
        key_list is the rows, or None when the key list does not read.

    Exit/Returns:
        Returns True for a key that the key list names, and for any key
        when there is no key list. For another key, it gives a warning and
        returns the answer to "Keep it?". Enter gives no.

    Module Globals:
        INDENT read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    named = plans.is_named(key, key_list)

    if named:
        return True

    console.say(INDENT + plans.unnamed_hint(key, key_list))
    keep = questions.ask_yes(console, "Keep %s?" % key, False)

    return keep


# ─── Private helper routines: the model record ───────────────────────────────

def _ask_model_file(console: Console, plan: plans.Plan) -> str:
    """
    Purpose: Ask which file of the source is the model.

    Entry:
        plan.model_files is not empty.

    Exit/Returns:
        Returns the file. With one model file, no question comes.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    files = list(plan.model_files)

    if len(files) == 1:
        console.say("")
        console.say("The model file is %s." % files[0])
        return files[0]

    chosen = questions.ask_choice(console, "Which file is the model? The "
                                  "source holds %d model files." % len(files),
                                  files)

    return files[chosen]


def _ask_family(console: Console) -> str:
    """
    Purpose: Ask for the family of the model record.

    Entry:
        No conditions.

    Exit/Returns:
        Returns a family. A new family gets the budget of an unlisted
        family.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    families = plans.families()
    labels = [plans.family_label(family) for family in families]
    labels.append("A new family. It gets the budget of an unlisted family")
    chosen = questions.ask_choice(console, "Which family is it? The family "
                                  "sets the budget of the served file.",
                                  labels)

    if chosen < len(families):
        return families[chosen]

    return questions.ask_text(console, "The name of the new family.",
                              check=plans.new_family_problem)


def _typed_key_problem(value: str, offered: list, owners: dict) -> str:
    """Accept a number of the offered list, or a free asset key."""
    picked = questions.picked_row(value, offered)

    if picked:
        return ""

    return plans.key_problem(value, owners)


def _ask_asset_key(console: Console, plan: plans.Plan, all_records: list,
                   key_list) -> str:
    """
    Purpose: Ask for the asset key of the new model record.

    Entry:
        all_records holds every loaded model record. key_list is the rows
        of the key list, or None.

    Exit/Returns:
        Returns a free asset key. A key that the game does not name needs a
        yes.

    Module Globals:
        None.

    Methodology:
        1. Show each asset key that the game names and no record has.
        2. Ask for a number of that list, or a key.
        3. Warn about a key that the game does not name, and ask again
           after a no.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    owners = plans.owners_of(all_records)
    looks = plans.worn_look_keys()
    rows = [] if key_list is None else plans.offered_keys(
        key_list, all_records, plan.family, looks)
    offered = [row["key"] for row in rows]
    default = plans.default_key(plan, owners)
    question = "The asset key: the name of the model in the game and in the "
    question += "client."

    if offered:
        _show_offer(console, rows, looks)
        question += " Type a number from the list, or a key."

    while True:
        typed = questions.ask_text(console, question, default,
                                   lambda value: _typed_key_problem(
                                       value, offered, owners))
        key = questions.picked_row(typed, offered) or typed
        kept = _keep_key(console, key, key_list)

        if kept:
            return key


def _ask_aliases(console: Console, asset_key: str, owners: dict,
                 key_list) -> tuple:
    """
    Purpose: Ask for more asset keys that draw the same model.

    Entry:
        owners maps each asset key and alias on disk to its record.
        key_list is the rows of the key list, or None.

    Exit/Returns:
        Returns the aliases. Enter gives none. An alias that the game does
        not name needs a yes, as the asset key does.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    while True:
        text = questions.ask_text(console, "More asset keys that draw the "
                                  "same model, with a comma between two. "
                                  "Press Enter for none.",
                                  check=lambda value: plans.aliases_problem(
                                      plans.split_aliases(value), asset_key,
                                      owners))
        aliases = plans.split_aliases(text)
        kept = all(_keep_key(console, alias, key_list) for alias in aliases)

        if kept:
            return aliases


def _ask_variant(console: Console, asset_key: str, all_records: list) -> str:
    """Ask for the base of a model variant. Enter gives no base."""
    bases = {record.asset_key: record for record in all_records}
    variant_of = questions.ask_text(console, "Is it a second look of another "
                                    "model (a model variant)? Type the asset "
                                    "key of that model. Press Enter for no.",
                                    check=lambda value: plans.variant_problem(
                                        value, asset_key, bases))

    return variant_of


# ─── Private helper routines: the confirm and the write ──────────────────────

def _show_plan(console: Console, plan: plans.Plan) -> None:
    """
    Purpose: Show each file that the wizard is about to write, with its
    text.

    Entry:
        Every question of the plan has its answer.

    Exit/Returns:
        Returns None.

    Module Globals:
        INDENT read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    console.say("")
    console.say("The plan:")

    for planned in plans.preview(plan):
        note = "  " + planned.note if planned.note else ""
        console.say(INDENT + planned.path + note)
        questions.show_text(console, planned.text)


def _ask_build(console: Console, plan: plans.Plan) -> bool:
    """
    Purpose: Ask whether to build the new model now.

    Entry:
        The model record is on disk.

    Exit/Returns:
        Returns True for a build. Returns False with no question when this
        machine cannot build the model.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    problem = build.tools_problem(plan.model_file)

    if problem:
        console.say("")
        console.say("This machine cannot build the model now: %s." % problem)
        return False

    wanted = questions.ask_yes(console, "Build %s now?" % plan.asset_key, True)

    return wanted


# The origins that the wizard asks, and the questions of each. The label
# and the write of an origin belong to plans.py. The export origin is not
# here, because `figure-model` does it in one line.
_ORIGINS: tuple = (
    (plans.ORIGIN_FILE, _ask_file_origin),
    (plans.ORIGIN_POLYHAVEN, _ask_polyhaven_origin),
    (plans.ORIGIN_SOURCE, _ask_source_origin),
)


def _ask_origin(console: Console, all_records: list) -> plans.Plan:
    """
    Purpose: Ask where the model comes from, and ask the questions of that
    origin.

    Entry:
        all_records holds every loaded model record.

    Exit/Returns:
        Returns the plan. An origin that cannot go on asks this question
        again.

    Module Globals:
        _ORIGINS, _ROW_ORIGIN, _ROW_ASKER, plans.ORIGIN_LABELS read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    labels = [plans.ORIGIN_LABELS[row[_ROW_ORIGIN]] for row in _ORIGINS]
    plan = None

    while plan is None:
        chosen = questions.ask_choice(console, "Where does the model come "
                                      "from?", labels)
        asker = _ORIGINS[chosen][_ROW_ASKER]
        plan = asker(console, all_records)

    plan.origin = _ORIGINS[chosen][_ROW_ORIGIN]

    return plan


def _ask_plan(console: Console):
    """
    Purpose: Ask every question, show the plan, and ask for the confirm.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the plan, or None for a no at the confirm. Raises
        records.RecordError when a model record on disk does not load.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    all_records = records.load_all()
    owners = plans.owners_of(all_records)
    console.say("Add a model. Press Ctrl+C at a question to stop. The wizard "
                "writes nothing before you confirm.")
    plan = _ask_origin(console, all_records)
    plan.model_file = _ask_model_file(console, plan)
    plan.family = _ask_family(console)
    key_list = _load_key_list(console)
    plan.asset_key = _ask_asset_key(console, plan, all_records, key_list)
    plan.aliases = _ask_aliases(console, plan.asset_key, owners, key_list)
    plan.variant_of = _ask_variant(console, plan.asset_key, all_records)
    _show_plan(console, plan)
    confirmed = questions.ask_yes(console, "Write these files?", True)

    return plan if confirmed else None


def _write(console: Console, plan: plans.Plan) -> str:
    """
    Purpose: Write the source of the plan and its model record.

    Entry:
        The person confirmed the plan.

    Exit/Returns:
        Returns the path of the model record. Raises fetch.FetchError or
        sources.SourceError when a write fails.

    Module Globals:
        INDENT read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    written = plans.write(plan)
    console.say("")

    for path in written:
        console.say(INDENT + "wrote %s" % plans.shown(path))

    return written[-1]


# ─── Public routines ─────────────────────────────────────────────────────────

def run(console: Console = None):
    """
    Purpose: Ask the questions of the model wizard, and write what the
    answers give.

    Entry:
        console is None for the terminal, or a scripted Console.

    Exit/Returns:
        Returns the WizardResult. Returns None when the person stops or
        says no at the confirm, and then nothing was written. Raises
        records.RecordError, fetch.FetchError or sources.SourceError.

    Module Globals:
        _STOPPED read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    if console is None:
        console = Console(ask=input, say=print, pick_file=_pick_model_file)

    try:
        plan = _ask_plan(console)
    except (KeyboardInterrupt, EOFError):
        plan = None

    if plan is None:
        console.say("")
        console.say(_STOPPED)
        return None

    record_path = _write(console, plan)

    try:
        wanted = _ask_build(console, plan)
    except (KeyboardInterrupt, EOFError):
        wanted = False

    return WizardResult(asset_key=plan.asset_key, record_path=record_path,
                        build=wanted)


def next_steps(result: WizardResult, built: bool) -> list:
    """
    Purpose: Give the steps that come after the wizard, as lines to show.

    Entry:
        built is True when the build of the model passed.

    Exit/Returns:
        Returns the lines, numbered. A model that is not built gets the
        build command first.

    Module Globals:
        _BUILD_COMMAND, INDENT read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    record = plans.shown(result.record_path)
    steps = []

    if not built:
        steps.append("Build it from blackout/: "
                     + _BUILD_COMMAND % result.asset_key)

    steps.append("Run `evennia reload`, and look at the model in the "
                 "client.")
    steps.append("If it faces the wrong way or looks wrong, add a [fix] to "
                 "%s, and build again." % record)
    steps.append("Commit the source, the record, build.lock.json and the "
                 "served tree in one commit.")
    lines = ["", "Next:"]
    lines.extend("%s%d. %s" % (INDENT, number, step)
                 for number, step in enumerate(steps, start=1))

    return lines
