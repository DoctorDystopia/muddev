"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 10/26/2026
Description: The questions of a wizard. The model wizard (wizard.py) and the
             sound wizard (assets/audio/wizard.py) ask through these
             routines. Thus, the two wizards ask, refuse, and show a list in
             the same way.

             A wizard meets a person through a Console. A test gives a
             scripted one.

             The routines came out of the model wizard on 10/26/2026, when
             the sound wizard needed the same questions.

             Reads no file. The file dialog loads tkinter only when it opens.
"""

import os
import re
from dataclasses import dataclass
from typing import Callable

from assets.pipeline import licenses, records


# ─── Public constant definitions ─────────────────────────────────────────────

@dataclass(frozen=True)
class Console:
    """
    How a wizard meets a person. ask shows a prompt and returns one typed
    line. say shows one line. pick_file opens a file dialog and returns the
    chosen path, or "". A test gives scripted ones.
    """

    ask: Callable
    say: Callable
    pick_file: Callable


PROMPT: str = "> "
INDENT: str = "  "


# ─── Private constant definitions ────────────────────────────────────────────

_TEXT_INDENT: str = "      "
_DEFAULT_HINT: str = " [%s]"
_YES_HINT: str = " [Y/n]"
_NO_HINT: str = " [y/N]"
_YES: tuple = ("y", "yes")
_NO: tuple = ("n", "no")

# A list longer than this shows its first rows, and a typed text filters it.
_LIST_ROWS: int = 20
_FILTER_HINT: str = "Type text to filter the list."

# A path that a person drags into a terminal can arrive in quotes, and
# PowerShell can put its call operator before it.
_PATH_QUOTES: str = "\"'"
_POWERSHELL_CALL: str = "& "

_KEY_JOINER: str = "_"
_NOT_KEY_CHARACTERS: str = r"[^a-z0-9]+"

_DIALOG_ALL: tuple = ("All files", "*.*")


# ─── Public routines: the questions ──────────────────────────────────────────

def no_problem(_value: str) -> str:
    """Accept any answer."""
    return ""


def required(value: str) -> str:
    """Refuse an empty answer."""
    return "" if value else "Type an answer."


def ask_text(console: Console, question: str, default: str = "",
             check: Callable = no_problem) -> str:
    """
    Purpose: Ask for one line of text until check accepts it.

    Entry:
        check takes the answer and returns "" or the problem.

    Exit/Returns:
        Returns the answer, stripped. An empty answer takes default.

    Module Globals:
        PROMPT, INDENT, _DEFAULT_HINT read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    hint = _DEFAULT_HINT % default if default else ""
    console.say("")
    console.say(question + hint)

    while True:
        typed = console.ask(PROMPT)
        value = typed.strip() or default
        problem = check(value)

        if not problem:
            return value

        console.say(INDENT + problem)


def ask_yes(console: Console, question: str, default: bool) -> bool:
    """
    Purpose: Ask a yes or no question.

    Entry:
        default is the answer that Enter gives.

    Exit/Returns:
        Returns True for yes.

    Module Globals:
        PROMPT, _YES, _NO, _YES_HINT, _NO_HINT read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    hint = _YES_HINT if default else _NO_HINT
    console.say("")
    console.say(question + hint)

    while True:
        typed = console.ask(PROMPT)
        answer = typed.strip().lower()

        if not answer:
            return default

        if answer in _YES or answer in _NO:
            return answer in _YES

        console.say(INDENT + "Type y or n.")


def show_rows(console: Console, labels: list, rows: list,
              more: str = _FILTER_HINT) -> None:
    """
    Purpose: Show the first rows of a list, with a number on each.

    Entry:
        rows holds indexes into labels. more tells how to reach a row that
        the list does not show.

    Exit/Returns:
        Returns None.

    Module Globals:
        _LIST_ROWS, INDENT read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    for number, index in enumerate(rows[:_LIST_ROWS], start=1):
        console.say("%s%2d. %s" % (INDENT, number, labels[index]))

    hidden = len(rows) - _LIST_ROWS

    if hidden > 0:
        console.say("%s... and %d more. %s" % (INDENT, hidden, more))


def picked_row(typed: str, rows: list):
    """
    Purpose: Read a typed number as a row of the shown list.

    Entry:
        rows holds the indexes that the list shows, in order.

    Exit/Returns:
        Returns the index that the number names, or None.

    Module Globals:
        _LIST_ROWS read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    if not typed.isdigit():
        return None

    number = int(typed)
    shown = min(len(rows), _LIST_ROWS)

    if 1 <= number <= shown:
        return rows[number - 1]

    return None


def ask_choice(console: Console, question: str, labels: list) -> int:
    """
    Purpose: Ask the person to choose one row of a list.

    Entry:
        labels is not empty.

    Exit/Returns:
        Returns the index of the chosen label. A typed text that is not a
        number filters the list to the labels that hold it.

    Module Globals:
        PROMPT, INDENT read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    every_row = list(range(len(labels)))
    rows = every_row
    console.say("")
    console.say(question)

    while True:
        show_rows(console, labels, rows)
        typed = console.ask(PROMPT).strip()
        picked = picked_row(typed, rows)

        if picked is not None:
            return picked

        lowered = typed.lower()
        matches = [index for index in every_row
                   if lowered in labels[index].lower()]

        if typed and matches:
            rows = matches
            continue

        console.say(INDENT + "Type a number from the list, or a text to "
                    "filter it.")
        rows = every_row


def ask_license(console: Console, question: str, why: str,
                note_for: Callable) -> tuple:
    """
    Purpose: Ask for the license of a new download.

    Entry:
        question asks for the license. why asks for the reason of an
        exception. note_for takes the LicenseTerms of one allowed license
        and gives the text after its name in the list, or "".

    Exit/Returns:
        Returns (SPDX id, exception). The exception is "" for a license
        that passes the license gate.

    Module Globals:
        licenses.ALLOWED_LICENSES read.

    Methodology:
        1. Show each allowed license, and one row for another license.
        2. For another license, ask for its name.
        3. If that name fails the license gate, ask for the reason of an
           exception.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    allowed = list(licenses.ALLOWED_LICENSES)
    labels = ["%-26s %s%s" % (spdx, licenses.ALLOWED_LICENSES[spdx].name,
                              note_for(licenses.ALLOWED_LICENSES[spdx]))
              for spdx in allowed]
    labels.append("Another license. The license gate refuses it, unless you "
                  "give the reason for an exception")
    chosen = ask_choice(console, question, labels)

    if chosen < len(allowed):
        return allowed[chosen], ""

    spdx = ask_text(console, "Type the license as the page gives it, for "
                    "example CC-BY-NC-4.0.", check=required)
    passes = licenses.is_allowed(spdx)

    if passes:
        return spdx, ""

    exception = ask_text(console, why, check=required)

    return spdx, exception


def show_text(console: Console, text: str) -> None:
    """Show each line of a text, indented under its file."""
    for line in text.splitlines():
        console.say(_TEXT_INDENT + line)


# ─── Public routines: names and paths ────────────────────────────────────────

def as_key(text: str) -> str:
    """
    Purpose: Make a name into a key, if it can be one.

    Entry:
        text is any text.

    Exit/Returns:
        Returns the key: lower case, with "_" for each run of other
        characters. Returns "" when the result fails records.is_key.

    Module Globals:
        _NOT_KEY_CHARACTERS, _KEY_JOINER read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    joined = re.sub(_NOT_KEY_CHARACTERS, _KEY_JOINER, text.lower())
    key = joined.strip(_KEY_JOINER)
    fits = records.is_key(key)

    return key if fits else ""


def as_title(name: str) -> str:
    """Make a file name into a title: "rusty_sword" gives "Rusty sword"."""
    spaced = re.sub(r"[_\-]+", " ", name).strip()

    return spaced[:1].upper() + spaced[1:]


def name_of(path: str) -> str:
    """Give the name of a file, a folder or a .zip, with no suffix."""
    base = os.path.basename(os.path.normpath(path))

    return os.path.splitext(base)[0]


def clean_path(typed: str) -> str:
    """
    Purpose: Read a typed or a dragged path.

    Entry:
        typed is one line, as the person typed it.

    Exit/Returns:
        Returns the path with no quotes, no PowerShell call operator, and
        "~" expanded. Returns "" for an empty line.

    Module Globals:
        _POWERSHELL_CALL, _PATH_QUOTES read.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    text = typed.strip()

    if text.startswith(_POWERSHELL_CALL):
        text = text[len(_POWERSHELL_CALL):].strip()

    text = text.strip(_PATH_QUOTES)

    if not text:
        return ""

    return os.path.expanduser(text)


def open_file_dialog(title: str, label: str, suffixes: tuple,
                     initial_dir: str = "") -> str:
    """
    Purpose: Let the person choose a file in a file dialog.

    Entry:
        label names the files of suffixes in the type list of the dialog.
        initial_dir is the folder that the dialog opens in, or "".

    Exit/Returns:
        Returns the chosen path, or "" when the person closes the dialog or
        this machine cannot show one.

    Module Globals:
        _DIALOG_ALL read.

    Notes:
        tkinter loads here, not at the top of the module. A machine with no
        Tk must still run a wizard with a typed path, and the tests.

    Author: Nick Hobar
    Creation date: 10/25/2026
    """
    try:
        import tkinter
        from tkinter import filedialog
    except ImportError:
        return ""

    try:
        root = tkinter.Tk()
    except tkinter.TclError:
        return ""

    root.withdraw()
    root.attributes("-topmost", True)
    patterns = " ".join("*" + suffix for suffix in suffixes)
    chosen = filedialog.askopenfilename(
        parent=root, title=title, initialdir=initial_dir or None,
        filetypes=((label, patterns), _DIALOG_ALL))
    root.destroy()

    return chosen or ""
