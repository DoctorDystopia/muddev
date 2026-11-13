"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 11/08/2026
Description: The track flow of the sound wizard (DESIGN-0016). It adds one
             music track: the master goes into a source record, ffmpeg
             encodes it into the served tree, the credits get a row, and
             the music track table gets a row. wizard.py hands over here
             when the kind question gives the music kind.

             THE QUESTIONS, in this order:
               1. The master: a .flac on this machine. A path, a drag, or
                  Enter for a file dialog.
               2. Whether Nick wrote it. A yes puts it under his own section
                  of the credits, with the license of art made here. A no
                  asks the questions of a new sound pack.
               3. The title that the player sees. The wizard guesses it from
                  the file name, without the name of the area in front.
               4. The track key, which names the served file.
               5. The area. The wizard guesses it from the folder of the
                  master, because Nick keeps Areas/<Area>/<Area> <Title>.flac.
               6. The unlock rule, and the quest key of a quest unlock.
               7. The hint of the locked row, which can stay empty.
               8. The note: what the track is, for the next author.

             THE WIZARD WRITES NOTHING BEFORE THE CONFIRM, and it finds
             ffmpeg before the first question. A machine with no ffmpeg
             gets one line and no question.

             THE WRITE, IN THIS ORDER: the source record (a copy of the
             master, source.toml, and the seal that writes the hashes and
             the .gitignore), the encode, the credits, then the table row.
             The table names the track last, when the other files are
             there. The master never enters git: every track source is
             local.

             Reads and writes files only. It touches no database.
"""

import os
import shutil
from dataclasses import dataclass
from urllib.parse import urlparse

from assets.audio import credits, encode, kinds, packs, paths, tracks
from assets.pipeline import fetch, figure, questions, sources
from assets.pipeline import paths as pipeline_paths
from assets.pipeline.questions import INDENT, Console
from world import areas, music_tracks


# ─── Public constant definitions ─────────────────────────────────────────────

@dataclass
class TrackPlan:
    """
    The answers so far, and the text that the write gives.

    upload: the path of the master on this machine.
    pack: the section of the credits, from packs.
    source_file: the name of the master, for the credits row.
    title, key, area, unlock, unlock_key, hint, note: the row.
    credits_added: the new row, or the section of a new sound pack.
    credits_text: the credits after the write.
    rows: the track table after the write.
    ffmpeg: the ffmpeg executable.
    """

    upload: str = ""
    pack: packs.PackAnswer = None
    source_file: str = ""
    title: str = ""
    key: str = ""
    area: str = ""
    unlock: str = ""
    unlock_key: str = ""
    hint: str = ""
    note: str = ""
    credits_added: str = ""
    credits_text: str = ""
    rows: tuple = ()
    ffmpeg: str = ""


class TrackError(OSError):
    """A write of the track flow failed after an earlier write."""


# ─── Private constant definitions ────────────────────────────────────────────

_NO_FFMPEG: str = ("The wizard finds no ffmpeg on this machine. Install it, "
                   "or set FFMPEG_BIN to its path. A track needs the encode.")
_UNLOCK_LABELS: dict = {
    music_tracks.UNLOCK_AREA: "When the player first enters the area",
    music_tracks.UNLOCK_QUEST: "When the player completes a quest",
}
_AREA_LABEL: str = "%s — %s"
_NOTE_DEFAULT: str = "The track of %s."
_SOURCE_NOTES: str = "The master of the track %s, as it was exported."


# ─── Private helper routines: the questions ─────────────────────────────────

def _folder_name(path: str) -> str:
    """Give the name of the folder of a file."""
    return os.path.basename(os.path.dirname(os.path.abspath(path)))


def _guess_area(folder: str) -> str:
    """Give the one area whose name is the folder name, or ""."""
    lowered = folder.strip().lower()
    matches = [key for key, area in areas.AREAS.items()
               if lowered and lowered == area.name.lower()]

    return matches[0] if len(matches) == 1 else ""


def _title_guess(upload: str, folder: str) -> str:
    """Guess the title from the file name, without the folder name in front."""
    name = questions.name_of(upload).strip()
    prefix = folder.strip()
    starts = prefix and name.lower().startswith(prefix.lower())
    bare = name[len(prefix):].strip() if starts else name

    return bare or name


def _ask_area(console: Console, folder: str) -> str:
    """
    Purpose: Ask which area the track belongs to.

    Entry:
        folder is the folder name of the master, for the guess.

    Exit/Returns:
        Returns an area key. A guess that the person confirms asks no list.

    Module Globals:
        areas.AREAS, _AREA_LABEL read.

    Author: Nick Hobar
    Creation date: 11/08/2026
    """
    guess = _guess_area(folder)

    if guess:
        same = questions.ask_yes(console, "The area is %s (%s). Is that "
                                 "right?" % (areas.AREAS[guess].name, guess),
                                 True)

        if same:
            return guess

    keys = list(areas.AREAS)
    labels = [_AREA_LABEL % (key, areas.AREAS[key].name) for key in keys]
    chosen = questions.ask_choice(console, "Which area does the track "
                                  "belong to?", labels)

    return keys[chosen]


def _ask_unlock(console: Console) -> tuple:
    """Ask the unlock rule, and the quest key of a quest unlock."""
    labels = [_UNLOCK_LABELS[unlock] for unlock in music_tracks.UNLOCKS]
    chosen = questions.ask_choice(console, "When does the track unlock?",
                                  labels)
    unlock = music_tracks.UNLOCKS[chosen]
    unlock_key = ""

    if unlock == music_tracks.UNLOCK_QUEST:
        unlock_key = questions.ask_text(console, "The key of the quest, for "
                                        "example the key of its blueprint.",
                                        check=questions.required)

    return unlock, unlock_key


def _ask_pack(console: Console, text: str, folder: str) -> packs.PackAnswer:
    """Ask whether Nick wrote the track. A no asks for its sound pack."""
    own = questions.ask_yes(console, "Did you write this track? A yes puts "
                            "it under your own section of the credits.", True)

    if own:
        return packs.own_pack(text)

    return packs.ask_new_pack(console, text, folder)


# ─── Private helper routines: the plan and the write ─────────────────────────

def _finish_plan(plan: TrackPlan, rows: tuple, text: str) -> None:
    """
    Purpose: Make the credits and the track table that the write gives.

    Entry:
        Every question of the plan has its answer. rows and text are the
        track table and the credits on disk.

    Exit/Returns:
        Returns None. Sets plan.credits_added, plan.credits_text and
        plan.rows.

    Module Globals:
        None.

    Author: Nick Hobar
    Creation date: 11/08/2026
    """
    kind = kinds.KINDS[kinds.MUSIC_KIND]
    served = tracks.served_relative(plan.key)
    changes = credits.changes_text(True, kind.import_note)
    row = credits.render_row(served, plan.source_file, changes)
    plan.credits_added, plan.credits_text = packs.credits_with_row(
        text, plan.pack, row)
    track = music_tracks.Track(
        key=plan.key, name=plan.title, area=plan.area, unlock=plan.unlock,
        unlock_key=plan.unlock_key, hint=plan.hint, note=plan.note)
    plan.rows = tracks.with_track(rows, track)


def _show_plan(console: Console, plan: TrackPlan) -> None:
    """
    Purpose: Show each file that the wizard is about to write.

    Entry:
        _finish_plan ran on the plan.

    Exit/Returns:
        Returns None.

    Module Globals:
        INDENT read.

    Author: Nick Hobar
    Creation date: 11/08/2026
    """
    source = paths.source_dir(plan.key)
    where = "one more row under %s" % plan.pack.pack
    track = plan.rows[-1]

    if plan.pack.new_pack:
        where = "a new section at the end"

    console.say("")
    console.say("The plan:")
    console.say(INDENT + "%s/  a copy of %s, its source record, and its "
                ".gitignore. git keeps the record only" % (
                    packs.shown(source), plan.upload))
    console.say(INDENT + "%s  the encode, with %s" % (
        packs.shown(paths.track_path(plan.key)), plan.ffmpeg))
    questions.show_text(console, kinds.KINDS[kinds.MUSIC_KIND].import_note)
    console.say(INDENT + "%s  %s" % (packs.shown(paths.CREDITS_PATH), where))
    questions.show_text(console, plan.credits_added)
    console.say(INDENT + "%s  one more track" % packs.shown(
        paths.TRACK_TABLE_PATH))
    questions.show_text(console, "%s: %s, in %s, unlock %s %s. %s" % (
        track.key, track.name, track.area, track.unlock, track.unlock_key,
        track.note))


def _source_fields(plan: TrackPlan) -> fetch.SourceFields:
    """Give the fields of the source record of the master."""
    site = urlparse(plan.pack.url).netloc or figure.OWNED_SITE
    notes = _SOURCE_NOTES % plan.key

    return fetch.SourceFields(title=plan.title, author=plan.pack.author,
                              url=plan.pack.url, site=site,
                              license=plan.pack.license, notes=notes,
                              local=True)


def _write_source(plan: TrackPlan) -> str:
    """
    Purpose: Copy the master into its source directory, write its record,
    and seal it.

    Entry:
        The source directory is not there.

    Exit/Returns:
        Returns the path of the copy. Raises OSError when a write fails,
        and sources.SourceError when the record does not load.

    Module Globals:
        pipeline_paths.SOURCE_RECORD_NAME read.

    Author: Nick Hobar
    Creation date: 11/08/2026
    """
    directory = paths.source_dir(plan.key)
    copy = os.path.join(directory, os.path.basename(plan.upload))
    record = os.path.join(directory, pipeline_paths.SOURCE_RECORD_NAME)
    text = fetch.render_source_record(_source_fields(plan))
    os.makedirs(directory)
    shutil.copyfile(plan.upload, copy)

    with open(record, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)

    source = sources.load_source(music_tracks.source_id_for(plan.key))
    sources.seal(source)

    return copy


def _write(console: Console, plan: TrackPlan) -> None:
    """
    Purpose: Write the source, the served file, the credits and the table.

    Entry:
        The person confirmed the plan.

    Exit/Returns:
        Returns None. Raises TrackError when the encode fails, with the
        source already on disk. Raises OSError when a write fails.

    Module Globals:
        paths.CREDITS_PATH, paths.TRACK_TABLE_PATH read.

    Author: Nick Hobar
    Creation date: 11/08/2026
    """
    copy = _write_source(plan)
    served = paths.track_path(plan.key)
    os.makedirs(os.path.dirname(served), exist_ok=True)
    problem = encode.run_encode(plan.ffmpeg, copy, served)

    if problem:
        raise TrackError("The encode failed, and the wizard stopped after "
                         "the source record %s: %s" % (
                             packs.shown(paths.source_dir(plan.key)), problem))

    credits.write_credits(plan.credits_text, paths.CREDITS_PATH)
    tracks.write_table(plan.rows, paths.TRACK_TABLE_PATH)
    console.say("")

    for written in (paths.source_dir(plan.key), served, paths.CREDITS_PATH,
                    paths.TRACK_TABLE_PATH):
        console.say(INDENT + "wrote %s" % packs.shown(written))


# ─── Public routines ─────────────────────────────────────────────────────────

def ask_plan(console: Console):
    """
    Purpose: Ask every question of a track, show the plan, and ask for the
    confirm.

    Entry:
        The kind question gave the music kind.

    Exit/Returns:
        Returns the TrackPlan, or None for a no at the confirm or for a
        machine with no ffmpeg. Raises table_file.TableFileError or
        credits.CreditsError when a file that the wizard reads does not
        read.

    Module Globals:
        paths.TRACK_TABLE_PATH, paths.CREDITS_PATH, _NO_FFMPEG read.

    Author: Nick Hobar
    Creation date: 11/08/2026
    """
    plan = TrackPlan(ffmpeg=encode.find_ffmpeg())

    if not plan.ffmpeg:
        console.say("")
        console.say(_NO_FFMPEG)
        return None

    rows = tracks.read_table(paths.TRACK_TABLE_PATH)
    text = credits.read_credits(paths.CREDITS_PATH)
    kind = kinds.KINDS[kinds.MUSIC_KIND]
    plan.upload = packs.ask_upload(console, kind, "master")
    folder = _folder_name(plan.upload)
    plan.pack = _ask_pack(console, text, folder)
    plan.source_file = os.path.basename(plan.upload)
    plan.title = questions.ask_text(console, "The title of the track, as the "
                                    "player sees it.",
                                    _title_guess(plan.upload, folder),
                                    packs.cell_text)
    plan.key = questions.ask_text(console, "The track key. It names the "
                                  "served file.", questions.as_key(plan.title),
                                  lambda value: tracks.key_problem(value, rows))
    plan.area = _ask_area(console, folder)
    plan.unlock, plan.unlock_key = _ask_unlock(console)
    plan.hint = questions.ask_text(console, "The hint of the locked row, "
                                   "or Enter for none.", "",
                                   questions.no_problem)
    plan.note = questions.ask_text(console, "What is the track? The table "
                                   "keeps this note for the next author.",
                                   _NOTE_DEFAULT % areas.AREAS[plan.area].name,
                                   questions.required)
    _finish_plan(plan, rows, text)
    _show_plan(console, plan)
    confirmed = questions.ask_yes(console, "Write these files?", True)

    return plan if confirmed else None


def write(console: Console, plan: TrackPlan) -> None:
    """Write what the plan gives. See _write."""
    _write(console, plan)


def next_steps(key: str) -> list:
    """Give the steps that come after a track, as lines."""
    return [
        "Restart the server. It reads the track table at start.",
        "Start the client. Walk into the area, and the track plays once "
        "the client half of DESIGN-0016 is in.",
        "Commit the source record of %s, the served .ogg, CREDITS.md and "
        "music_tracks.json in one commit. git ignores the master." % key,
    ]
