"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/26/2026
Description: The sound wizard. `python -m assets.audio add` asks one
             question at a time, and adds one sound clip to the Godot
             client. It does each step of "To add a sound" in
             godot/README.md. It asks as the model wizard does, through
             assets/pipeline/questions.py.

             THE QUESTIONS, in this order:
               1. The sound kind. Only a table of two kinds or more asks it.
               2. The sound clip: a path, a drag, or Enter for a file dialog
                  that opens in the folder of the sound packs.
               3. The sound pack. A sound clip from a pack folder that one
                  heading of the credits names needs only a yes. A new sound
                  pack asks for its title, author, license and store page.
               4. The source file in the sound pack, for the credits row.
               5. The cue. The wizard first shows each moment that the
                  server names and no cue plays yet. A number picks one, and
                  the cue takes the name of the moment.
               6. The moment, for a typed cue.
               7. The note: when the cue plays.

             THE WIZARD WRITES NOTHING BEFORE THE CONFIRM. It shows each
             file and each new line, and it writes only after a yes. Ctrl+C
             at any question before that leaves the disk as it was.

             THE WRITE, IN THIS ORDER: the copy of the sound clip, its
             .import file, the credits, then the cue table. The cue table
             names the sound clip last, when the other files are there.

             The import question comes last. It runs Godot headless when
             this machine has Godot (godot_import.py).

             THE WIZARD WRITES NO SERVER CODE. A cue for a new moment needs
             the three edits of "A moment is that event" in godot/README.md.
             next_steps names them.

             Reads and writes files only. It touches no database.
"""

import os
import shutil
from dataclasses import dataclass

from assets.audio import credits, cue_table, godot_import, kinds, paths
from assets.pipeline import licenses, questions, records
from assets.pipeline.questions import INDENT, Console


# ─── Public constant definitions ─────────────────────────────────────────────

@dataclass(frozen=True)
class WizardResult:
    """
    What the wizard wrote. moment is "" for a cue that no moment plays.
    imported is True when Godot imported the sound clip.
    """

    cue: str
    clip: str
    moment: str
    imported: bool


# ─── Private constant definitions ────────────────────────────────────────────

@dataclass
class _Plan:
    """
    The answers so far, and the text that the write gives.

    kind: the row of kinds.KINDS.
    upload: the path of the sound clip on this machine.
    clip: the new sound clip, relative to godot/audio/.
    pack: the heading of the sound pack in the credits.
    new_pack: the prose lines of a new sound pack, or ().
    credits_added: the new row, or the section of a new sound pack.
    credits_text: the credits after the write.
    table: the cue table after the write.
    """

    kind: str = ""
    upload: str = ""
    clip: str = ""
    pack: str = ""
    new_pack: tuple = ()
    source_file: str = ""
    cue: str = ""
    moment: str = ""
    note: str = ""
    credits_added: str = ""
    credits_text: str = ""
    table: cue_table.CueTable = None


_ALL_SUFFIXES: tuple = tuple(suffix for kind in kinds.KINDS.values()
                             for suffix in kind.suffixes)
_DIALOG_TITLE: str = "Choose a sound clip"
_DIALOG_SOUNDS: str = "Sound clips"

_NEW_PACK: str = "A new sound pack. The wizard adds its section at the end"
_NO_MOMENT: str = ("No moment. A client caller plays the cue, or a moment "
                   "comes later")

# The heading and the prose of a new sound pack, as the sections in git
# write them.
_PACK_HEADING: str = "%s — %s"
_LICENSE_LINE: str = "License: %s."
_LICENSE_URL: str = " %s"
_EXCEPTION_LINE: str = "Exception to the license gate: %s"
_PAGE_LINE: str = "Store page: %s"

_OFFER_HINT: str = "Type the name of one of them."
_MOMENT_NOTE: str = "The server sends the moment %s."

_CHECK_COMMAND: str = "../evenv/Scripts/python.exe -m assets.audio check"
_IMPORT_COMMAND: str = "godot --headless --path godot --import"
_STOPPED: str = "  Stopped. Nothing was written."


# ─── Private helper routines: the sound clip and the sound pack ─────────────

def _shown(path: str) -> str:
    """Give a path relative to the repo, with forward slashes, if it can."""
    try:
        relative = os.path.relpath(path, paths.REPO_DIR)
    except ValueError:
        return path

    return relative.replace(os.sep, "/")


def _pick_sound_file() -> str:
    """Open the file dialog on the sound clips, in the sound pack folder."""
    chosen = questions.open_file_dialog(_DIALOG_TITLE, _DIALOG_SOUNDS,
                                        _ALL_SUFFIXES, paths.PACKS_DIR)

    return chosen


def _ask_kind(console: Console) -> str:
    """
    Purpose: Ask for the sound kind of the new cue.

    Entry:
        kinds.KINDS is not empty.

    Exit/Returns:
        Returns a key of kinds.KINDS. With one kind, no question comes.

    Module Globals:
        kinds.KINDS read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    keys = list(kinds.KINDS)
    labels = [kinds.KINDS[key].label for key in keys]

    if len(keys) == 1:
        label = labels[0][:1].lower() + labels[0][1:]
        console.say("")
        console.say("The sound kind is %s." % label)
        return keys[0]

    chosen = questions.ask_choice(console, "Which sound kind is it?", labels)

    return keys[chosen]


def _upload_problem(path: str, kind: kinds.SoundKind) -> str:
    """Refuse a path that is no file, or no sound clip of the kind."""
    suffix = os.path.splitext(path)[1].lower()
    present = os.path.isfile(path)

    if not present:
        return "%s is not a file." % path

    if suffix not in kind.suffixes:
        return "%s is not a sound clip of this kind: %s." % (
            path, " ".join(kind.suffixes))

    return ""


def _ask_upload(console: Console, kind: kinds.SoundKind) -> str:
    """
    Purpose: Ask for the path of the sound clip until it is one.

    Entry:
        kind is the sound kind of the new cue.

    Exit/Returns:
        Returns the path. Enter at the question opens the file dialog.

    Module Globals:
        questions.PROMPT, INDENT read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    console.say("")
    console.say("Type the path of the sound clip. You can drag it here. "
                "Press Enter to open a file dialog.")

    while True:
        typed = console.ask(questions.PROMPT)
        path = questions.clean_path(typed)

        if not path:
            path = console.pick_file()

        if not path:
            console.say(INDENT + "No file was chosen. Type a path.")
            continue

        problem = _upload_problem(path, kind)

        if not problem:
            return path

        console.say(INDENT + problem)


def _in_pack_folder(path: str) -> tuple:
    """
    Purpose: Split a path in the folder of the sound packs.

    Entry:
        path names a file.

    Exit/Returns:
        Returns (the folder of its sound pack, its path in the pack). For
        a path outside paths.PACKS_DIR, returns ("", its file name).

    Module Globals:
        paths.PACKS_DIR read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    name = os.path.basename(path)

    try:
        relative = os.path.relpath(path, paths.PACKS_DIR)
    except ValueError:
        return "", name

    parts = relative.replace(os.sep, "/").split("/")
    outside = parts[0] == os.pardir or len(parts) < 2

    if outside:
        return "", name

    return parts[0], "/".join(parts[1:])


def _guess_pack(packs: list, folder: str) -> str:
    """Give the one heading that names the pack folder, or ""."""
    lowered = folder.lower()
    matches = [pack.heading for pack in packs
               if folder and lowered in pack.heading.lower()]

    return matches[0] if len(matches) == 1 else ""


def _license_lines(spdx: str, exception: str) -> list:
    """Give the license prose of a new sound pack section."""
    terms = licenses.terms_for(spdx)
    allowed = licenses.is_allowed(spdx)
    name = terms.name if allowed else spdx
    line = _LICENSE_LINE % name

    if terms.url:
        line += _LICENSE_URL % terms.url

    lines = [line]

    if exception:
        lines.append(_EXCEPTION_LINE % exception)

    return lines


def _no_license_note(_terms: licenses.LicenseTerms) -> str:
    """Add nothing after a license name: each heading names the author."""
    return ""


def _cell_text(value: str) -> str:
    """Refuse an empty answer, or one that a credits cell cannot hold."""
    problem = questions.required(value) or credits.cell_problem(value)

    return problem


def _ask_new_pack(console: Console, folder: str) -> tuple:
    """
    Purpose: Ask the questions of a new sound pack.

    Entry:
        folder is the pack folder of the sound clip, or "".

    Exit/Returns:
        Returns (heading, the prose lines under it).

    Module Globals:
        _PACK_HEADING, _PAGE_LINE read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    title = questions.ask_text(console, "The title of the sound pack, as "
                               "its store page gives it.", folder,
                               questions.required)
    author = questions.ask_text(console, "Who made it?",
                                check=questions.required)
    spdx, exception = questions.ask_license(
        console, "Which license does the store page give?", "Why can "
        "Blackout ship it? CREDITS.md shows this reason.", _no_license_note)
    url = questions.ask_text(console, "The URL of the store page.",
                             check=questions.required)
    lines = _license_lines(spdx, exception)
    lines.append(_PAGE_LINE % url)

    return _PACK_HEADING % (author, title), lines


def _ask_pack(console: Console, plan: _Plan, text: str, folder: str) -> None:
    """
    Purpose: Ask which sound pack of the credits the sound clip came from.

    Entry:
        text is the credits. folder is the pack folder of the sound clip,
        or "".

    Exit/Returns:
        Returns None. Sets plan.pack, and plan.new_pack for a new pack.

    Module Globals:
        _NEW_PACK read.

    Methodology:
        1. When one heading names the pack folder, ask for a yes.
        2. Otherwise, show each sound pack and one row for a new one.
        3. A new pack with the heading of a pack in the credits is that
           pack.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    packs = credits.packs_of(text)
    headings = [pack.heading for pack in packs]
    guess = _guess_pack(packs, folder)

    if guess:
        same = questions.ask_yes(console, "The sound pack is %s. Is that "
                                 "right?" % guess, True)

        if same:
            plan.pack = guess
            return

    chosen = questions.ask_choice(console, "Which sound pack holds the sound "
                                  "clip? CREDITS.md has one section for "
                                  "each.", headings + [_NEW_PACK])

    if chosen < len(packs):
        plan.pack = headings[chosen]
        return

    heading, lines = _ask_new_pack(console, folder)
    plan.pack = heading

    if heading in headings:
        console.say(INDENT + "CREDITS.md has %s already. The row goes in it."
                    % heading)
        return

    plan.new_pack = tuple(lines)


# ─── Private helper routines: the cue ────────────────────────────────────────

def _cue_problem(value: str, table: cue_table.CueTable,
                 kind: kinds.SoundKind, suffix: str) -> str:
    """
    Purpose: Refuse a cue that is no key, that the cue table has, or whose
    sound clip is there already.

    Entry:
        suffix is the suffix of the uploaded sound clip.

    Exit/Returns:
        Returns the problem, or "".

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    fits = records.is_key(value)
    clip = cue_table.clip_for(kind.folder, value, suffix)
    taken = os.path.exists(paths.clip_path(clip))
    imported = os.path.exists(cue_table.import_path(clip))

    if not fits:
        return "A cue uses only a-z, 0-9 and _, with a letter first."

    if value in table.cues:
        return "The cue table has the cue %s already." % value

    if taken or imported:
        return "godot/audio/%s is there already. Type another cue." % clip

    return ""


def _typed_cue_problem(value: str, free: list, table: cue_table.CueTable,
                       kind: kinds.SoundKind, suffix: str) -> str:
    """Accept a number of the shown moments, or a free cue."""
    picked = questions.picked_row(value, free)

    if picked:
        return ""

    return _cue_problem(value, table, kind, suffix)


def _show_free_moments(console: Console, free: list) -> None:
    """Show each moment that no cue plays, with a number on each."""
    console.say("")
    console.say("The server names these moments, and no cue plays them yet:")
    questions.show_rows(console, free, list(range(len(free))), _OFFER_HINT)


def _ask_cue(console: Console, plan: _Plan, table: cue_table.CueTable,
             free: list) -> str:
    """
    Purpose: Ask for the cue of the new sound clip.

    Entry:
        free holds each moment that the server names and no cue plays.

    Exit/Returns:
        Returns a free cue. A number of the shown list gives that moment.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    kind = kinds.KINDS[plan.kind]
    suffix = os.path.splitext(plan.upload)[1].lower()
    wanted = questions.as_key(questions.name_of(plan.upload))
    taken = _cue_problem(wanted, table, kind, suffix)
    default = "" if taken else wanted
    question = ("The cue: the name of the sound in the client, for example "
                "guns_shot.")

    if free:
        _show_free_moments(console, free)
        question += " Type a number from the list, or a cue."

    typed = questions.ask_text(console, question, default,
                               lambda value: _typed_cue_problem(
                                   value, free, table, kind, suffix))
    picked = questions.picked_row(typed, free)

    return picked or typed


def _ask_moment(console: Console, cue: str, free: list) -> str:
    """
    Purpose: Ask which moment plays the new cue.

    Entry:
        free holds each moment that the server names and no cue plays.

    Exit/Returns:
        Returns the moment, or "" for none. A cue with the name of a free
        moment is that moment, with no question.

    Module Globals:
        _NO_MOMENT read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    if cue in free:
        console.say("")
        console.say("The moment %s plays the cue." % cue)
        return cue

    if not free:
        return ""

    chosen = questions.ask_choice(console, "Which moment plays the cue?",
                                  free + [_NO_MOMENT])

    return free[chosen] if chosen < len(free) else ""


def _ask_note(console: Console, moment: str) -> str:
    """Ask when the cue plays. The cue table keeps the answer as a note."""
    default = _MOMENT_NOTE % moment if moment else ""
    note = questions.ask_text(console, "When does the cue play? The cue "
                              "table keeps this note for the next person.",
                              default, questions.required)

    return note


# ─── Private helper routines: the plan and the write ─────────────────────────

def _finish_plan(plan: _Plan, table: cue_table.CueTable, text: str) -> None:
    """
    Purpose: Make the cue table and the credits that the write gives.

    Entry:
        Every question of the plan has its answer. table and text are the
        cue table and the credits on disk.

    Exit/Returns:
        Returns None. Sets plan.clip, plan.table and plan.credits_text.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    kind = kinds.KINDS[plan.kind]
    suffix = os.path.splitext(plan.upload)[1].lower()
    plan.clip = cue_table.clip_for(kind.folder, plan.cue, suffix)
    renamed = os.path.basename(plan.upload) != os.path.basename(plan.clip)
    changes = credits.changes_text(renamed, kind.import_note)
    row = credits.render_row(plan.clip, plan.source_file, changes)
    plan.credits_added = row

    if plan.new_pack:
        section = credits.render_pack(plan.pack, list(plan.new_pack), row)
        plan.credits_added = section
        plan.credits_text = credits.with_pack(text, section)
    else:
        plan.credits_text = credits.with_row(text, plan.pack, row)

    cue = cue_table.Cue(key=plan.cue, kind=plan.kind, clip=plan.clip,
                        note=plan.note)
    plan.table = cue_table.with_cue(table, cue, plan.moment)


def _show_plan(console: Console, plan: _Plan) -> None:
    """
    Purpose: Show each file that the wizard is about to write.

    Entry:
        _finish_plan ran on the plan.

    Exit/Returns:
        Returns None.

    Module Globals:
        INDENT read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    kind = kinds.KINDS[plan.kind]
    destination = paths.clip_path(plan.clip)
    cue = plan.table.cues[plan.cue]
    where = "one more row under %s" % plan.pack

    if plan.new_pack:
        where = "a new section at the end"

    console.say("")
    console.say("The plan:")
    console.say(INDENT + "%s  a copy of %s" % (_shown(destination),
                                              plan.upload))
    console.say(INDENT + "%s  the import settings of %s" % (
        _shown(destination + paths.IMPORT_SUFFIX), plan.kind))
    questions.show_text(console, kind.import_note)
    console.say(INDENT + "%s  one more cue" % _shown(paths.CUE_TABLE_PATH))
    questions.show_text(console, "%s: %s, %s. %s" % (cue.key, cue.kind,
                                                     cue.clip, cue.note))

    if plan.moment:
        questions.show_text(console, "The moment %s plays it." % plan.moment)

    console.say(INDENT + "%s  %s" % (_shown(paths.CREDITS_PATH), where))
    questions.show_text(console, plan.credits_added)


def _ask_plan(console: Console):
    """
    Purpose: Ask every question, show the plan, and ask for the confirm.

    Entry:
        No conditions.

    Exit/Returns:
        Returns the plan, or None for a no at the confirm. Raises
        cue_table.CueTableError or credits.CreditsError when a file that
        the wizard reads does not read.

    Module Globals:
        paths.CUE_TABLE_PATH, paths.CLIENT_CONSTANTS_PATH,
        paths.CREDITS_PATH read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    table = cue_table.read_table(paths.CUE_TABLE_PATH)
    moments = cue_table.read_moments(paths.CLIENT_CONSTANTS_PATH)
    text = credits.read_credits(paths.CREDITS_PATH)
    free = [moment for moment in moments if moment not in table.moments]
    console.say("Add a sound. Press Ctrl+C at a question to stop. The wizard "
                "writes nothing before you confirm.")
    kind = _ask_kind(console)
    plan = _Plan(kind=kind)
    plan.upload = _ask_upload(console, kinds.KINDS[kind])
    folder, in_pack = _in_pack_folder(plan.upload)
    _ask_pack(console, plan, text, folder)
    plan.source_file = questions.ask_text(console, "The path of the sound "
                                          "clip in the sound pack, for the "
                                          "credits.", in_pack, _cell_text)
    plan.cue = _ask_cue(console, plan, table, free)
    plan.moment = _ask_moment(console, plan.cue, free)
    plan.note = _ask_note(console, plan.moment)
    _finish_plan(plan, table, text)
    _show_plan(console, plan)
    confirmed = questions.ask_yes(console, "Write these files?", True)

    return plan if confirmed else None


def _write(console: Console, plan: _Plan) -> None:
    """
    Purpose: Write the sound clip, its .import file, the credits and the
    cue table.

    Entry:
        The person confirmed the plan.

    Exit/Returns:
        Returns None. Raises OSError when a write fails.

    Module Globals:
        paths.CREDITS_PATH, paths.CUE_TABLE_PATH read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    kind = kinds.KINDS[plan.kind]
    destination = paths.clip_path(plan.clip)
    import_file = cue_table.import_path(plan.clip)
    import_text = kinds.render_import(kind)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    shutil.copyfile(plan.upload, destination)

    with open(import_file, "w", encoding="utf-8", newline="") as handle:
        handle.write(import_text)

    credits.write_credits(plan.credits_text, paths.CREDITS_PATH)
    cue_table.write_table(plan.table, paths.CUE_TABLE_PATH)
    console.say("")

    for written in (destination, import_file, paths.CREDITS_PATH,
                    paths.CUE_TABLE_PATH):
        console.say(INDENT + "wrote %s" % _shown(written))


def _ask_import(console: Console, plan: _Plan) -> bool:
    """
    Purpose: Ask whether to import the new sound clip in Godot now, and
    import it.

    Entry:
        The sound clip and its .import file are on disk.

    Exit/Returns:
        Returns True when Godot imported the sound clip. Returns False with
        no question when this machine has no Godot that the wizard finds.

    Module Globals:
        INDENT read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    executable = godot_import.find_godot()
    import_file = cue_table.import_path(plan.clip)

    if not executable:
        console.say("")
        console.say("The wizard finds no Godot on this machine. Set "
                    "GODOT_BIN to import here.")
        return False

    wanted = questions.ask_yes(console, "Import %s in Godot now? A headless "
                               "Godot imports each new file of the "
                               "project." % plan.clip, True)

    if not wanted:
        return False

    console.say(INDENT + "importing with %s" % executable)
    problem = godot_import.run_import(executable)
    imported = not problem and godot_import.is_imported(import_file)

    if problem:
        console.say(INDENT + problem)
    elif not imported:
        console.say(INDENT + "Godot ended, but %s has no uid yet."
                    % _shown(import_file))

    return imported


# ─── Public routines ─────────────────────────────────────────────────────────

def run(console: Console = None):
    """
    Purpose: Ask the questions of the sound wizard, and write what the
    answers give.

    Entry:
        console is None for the terminal, or a scripted Console.

    Exit/Returns:
        Returns the WizardResult. Returns None when the person stops or
        says no at the confirm, and then nothing was written. Raises
        cue_table.CueTableError, credits.CreditsError or OSError.

    Module Globals:
        _STOPPED read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    if console is None:
        console = Console(ask=input, say=print, pick_file=_pick_sound_file)

    try:
        plan = _ask_plan(console)
    except (KeyboardInterrupt, EOFError):
        plan = None

    if plan is None:
        console.say("")
        console.say(_STOPPED)
        return None

    _write(console, plan)

    try:
        imported = _ask_import(console, plan)
    except (KeyboardInterrupt, EOFError):
        imported = False

    return WizardResult(cue=plan.cue, clip=plan.clip, moment=plan.moment,
                        imported=imported)


def next_steps(result: WizardResult) -> list:
    """
    Purpose: Give the steps that come after the wizard, as lines to show.

    Entry:
        result came from run.

    Exit/Returns:
        Returns the lines, numbered. A sound clip that Godot did not import
        gets the import first. A cue that no moment plays gets the way to
        play it.

    Module Globals:
        _IMPORT_COMMAND, _CHECK_COMMAND, INDENT read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    steps = []

    if not result.imported:
        steps.append("Import it: open the Godot editor, or run this from the "
                     "repo root: " + _IMPORT_COMMAND)

    if result.moment:
        steps.append("Start the client. The moment %s now plays %s."
                     % (result.moment, result.clip))
    else:
        steps.append("No moment plays %s yet. A client caller plays it "
                     "with SoundCues.play(\"%s\")." % (result.cue, result.cue))
        steps.append("For a new moment, make the three edits of \"A moment "
                     "is that event\" in godot/README.md. Then map the "
                     "moment to %s under \"moments\" in cues.json."
                     % result.cue)

    steps.append("Check the sound clips from blackout/: " + _CHECK_COMMAND)
    steps.append("Commit the sound clip, its .import file, cues.json and "
                 "CREDITS.md in one commit.")
    lines = ["", "Next:"]
    lines.extend("%s%d. %s" % (INDENT, number, step)
                 for number, step in enumerate(steps, start=1))

    return lines
