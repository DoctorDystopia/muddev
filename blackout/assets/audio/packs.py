"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/08/2026
Description: The questions that both flows of the sound wizard share: the
             file on this machine, and the sound pack that it came from.
             The sound effect flow (wizard.py) and the track flow
             (track_wizard.py) ask them the same way (DESIGN-0016).

             A sound pack is one section of godot/audio/CREDITS.md. A file
             from a pack folder that one heading names needs only a yes. A
             new sound pack asks for its title, author, license and store
             page. A track that Nick wrote goes under his own section, with
             the license of art made here, and no question.

             These routines were private to wizard.py until 11/08/2026.
             They moved here when the track flow needed them.

             Reads the terminal through the Console. Writes nothing.
"""

import os
from dataclasses import dataclass

from assets.audio import credits, kinds, paths
from assets.pipeline import figure, licenses, questions
from assets.pipeline.questions import INDENT, Console


# ─── Public constant definitions ─────────────────────────────────────────────

@dataclass(frozen=True)
class PackAnswer:
    """
    The answer to the pack question. pack is the heading. new_pack holds
    the prose lines of a new section, or () for a pack that the credits
    have. license, author and url are the facts of the pack, for a source
    record. They are "" for a pack of the credits that asked no question.
    """

    pack: str
    new_pack: tuple = ()
    license: str = ""
    author: str = ""
    url: str = ""


# The section of the tracks that Nick wrote. The author is the author of
# art made here, and the title is the game.
OWN_PACK_TITLE: str = "Blackout"


# ─── Private constant definitions ────────────────────────────────────────────

_NEW_PACK: str = "A new sound pack. The wizard adds its section at the end"

# The heading and the prose of a new sound pack, as the sections in git
# write them.
_PACK_HEADING: str = "%s — %s"
_LICENSE_LINE: str = "License: %s."
_LICENSE_URL: str = " %s"
_EXCEPTION_LINE: str = "Exception to the license gate: %s"
_PAGE_LINE: str = "Store page: %s"
_OWN_LINE: str = "Original music, written for the game."


# ─── Private helper routines ─────────────────────────────────────────────────

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


def _headings(text: str) -> list:
    """Give the heading of each sound pack of the credits."""
    return [pack.heading for pack in credits.packs_of(text)]


# ─── Public routines: the file ───────────────────────────────────────────────

def shown(path: str) -> str:
    """Give a path relative to the repo, with forward slashes, if it can."""
    try:
        relative = os.path.relpath(path, paths.REPO_DIR)
    except ValueError:
        return path

    return relative.replace(os.sep, "/")


def upload_problem(path: str, kind: kinds.SoundKind) -> str:
    """Refuse a path that is no file, or no file of the kind."""
    suffix = os.path.splitext(path)[1].lower()
    present = os.path.isfile(path)

    if not present:
        return "%s is not a file." % path

    if suffix not in kind.suffixes:
        return "%s is not a sound clip of this kind: %s." % (
            path, " ".join(kind.suffixes))

    return ""


def ask_upload(console: Console, kind: kinds.SoundKind, what: str) -> str:
    """
    Purpose: Ask for the path of the file until it is one of the kind.

    Entry:
        what names the file in the question: "sound clip" or "master".

    Exit/Returns:
        Returns the path. Enter at the question opens the file dialog.

    Module Globals:
        questions.PROMPT, INDENT read.

    Author: Nick Hobar
    Creation date: 10/26/2026
    """
    console.say("")
    console.say("Type the path of the %s. You can drag it here. Press Enter "
                "to open a file dialog." % what)

    while True:
        typed = console.ask(questions.PROMPT)
        path = questions.clean_path(typed)

        if not path:
            path = console.pick_file()

        if not path:
            console.say(INDENT + "No file was chosen. Type a path.")
            continue

        problem = upload_problem(path, kind)

        if not problem:
            return path

        console.say(INDENT + problem)


def in_pack_folder(path: str) -> tuple:
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


def cell_text(value: str) -> str:
    """Refuse an empty answer, or one that a credits cell cannot hold."""
    problem = questions.required(value) or credits.cell_problem(value)

    return problem


# ─── Public routines: the pack ───────────────────────────────────────────────

def ask_new_pack(console: Console, text: str, folder: str) -> PackAnswer:
    """
    Purpose: Ask the questions of a new sound pack.

    Entry:
        text is the credits. folder is the pack folder of the file, or "".

    Exit/Returns:
        Returns the PackAnswer. A heading that the credits have gives no
        new section, and the row goes under the heading.

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
    heading = _PACK_HEADING % (author, title)

    if heading in _headings(text):
        console.say(INDENT + "CREDITS.md has %s already. The row goes in it."
                    % heading)
        return PackAnswer(pack=heading, license=spdx, author=author, url=url)

    return PackAnswer(pack=heading, new_pack=tuple(lines), license=spdx,
                      author=author, url=url)


def ask_pack(console: Console, text: str, folder: str) -> PackAnswer:
    """
    Purpose: Ask which sound pack of the credits the sound clip came from.

    Entry:
        text is the credits. folder is the pack folder of the sound clip,
        or "".

    Exit/Returns:
        Returns the PackAnswer.

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
            return PackAnswer(pack=guess)

    chosen = questions.ask_choice(console, "Which sound pack holds the sound "
                                  "clip? CREDITS.md has one section for "
                                  "each.", headings + [_NEW_PACK])

    if chosen < len(packs):
        return PackAnswer(pack=headings[chosen])

    return ask_new_pack(console, text, folder)


def own_pack(text: str) -> PackAnswer:
    """
    Purpose: Give the pack of a track that Nick wrote, with no question.

    Entry:
        text is the credits.

    Exit/Returns:
        Returns the PackAnswer: the own section, new when the credits do
        not have it yet, with the license of art made here.

    Module Globals:
        OWN_PACK_TITLE, _OWN_LINE, _PACK_HEADING read.

    Author: Nick Hobar
    Creation date: 11/08/2026
    """
    heading = _PACK_HEADING % (figure.DEFAULT_AUTHOR, OWN_PACK_TITLE)
    lines = [_OWN_LINE, *_license_lines(licenses.OWNED_LICENSE, "")]
    new_pack = () if heading in _headings(text) else tuple(lines)

    return PackAnswer(pack=heading, new_pack=new_pack,
                      license=licenses.OWNED_LICENSE,
                      author=figure.DEFAULT_AUTHOR, url=figure.OWNED_URL)


def credits_with_row(text: str, answer: PackAnswer, row: str) -> tuple:
    """
    Purpose: Put one credits row under its pack.

    Entry:
        text is the credits on disk. answer came from a pack question.

    Exit/Returns:
        Returns (what the write adds, the credits after the write). The
        addition is the row, or the whole section of a new pack.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 11/08/2026
    """
    if answer.new_pack:
        section = credits.render_pack(answer.pack, list(answer.new_pack), row)
        return section, credits.with_pack(text, section)

    return row, credits.with_row(text, answer.pack, row)
