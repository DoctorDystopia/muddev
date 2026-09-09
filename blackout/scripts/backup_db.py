"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/08/2026
Description: Operator script. Backs up the live Evennia database.

             The database path and engine are read from Django settings
             rather than hardcoded, so a future switch to Postgres fails
             loud here (see _get_sqlite_path) instead of silently backing up
             the wrong file. Only Django settings are loaded -- Evennia
             itself is never started.

             The snapshot uses sqlite3's own online backup API, not a raw
             file copy. A raw copy can grab a page mid-write while the
             server is running; `Connection.backup()` copies under a read
             lock and is safe against that.

             Output is gzip-compressed and timestamped into server/backups/
             (gitignored), which this script also prunes to the newest
             --keep backups on every run.

             NOT destructive to the live database -- it only ever reads
             from it. Pruning only ever deletes files matching this
             script's own naming pattern, in its own backup directory.

Usage:
    ../evenv/Scripts/python.exe scripts/backup_db.py [--keep N] [--dest DIR]

    --keep N     how many backups to retain (default 14). 0 disables pruning.
    --dest DIR   backup directory (default server/backups, relative to the
                 game dir).
"""

import argparse
import gzip
import os
import shutil
import sqlite3
import sys
from datetime import datetime

# The game dir (blackout/), one level up from this file in scripts/. See the
# same note in map_sync.py: running `python scripts/backup_db.py` puts THIS
# file's directory on sys.path[0], not the caller's cwd.
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_DEFAULT_KEEP = 14
_DEFAULT_DEST = os.path.join(_GAME_DIR, "server", "backups")
_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
_BACKUP_PREFIX = "evennia_"
_BACKUP_SUFFIX = ".db3.gz"
_SQLITE_ENGINE_MARKER = "sqlite3"


def _bootstrap_django():
    """Load Django settings only -- no evennia._init(), no server start."""
    if _GAME_DIR not in sys.path:
        sys.path.insert(0, _GAME_DIR)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")

    import django

    django.setup()


def _get_sqlite_path():
    """
    Purpose: Resolve the live database file path from Django settings.

    Exit/Returns: Absolute path to the sqlite3 file.

    Notes: Exits with an error if the configured engine is not sqlite3 --
           this script has no pg_dump leg, and reporting success while
           backing up nothing would be worse than refusing outright.
    """
    from django.conf import settings

    engine = settings.DATABASES["default"]["ENGINE"]
    if _SQLITE_ENGINE_MARKER not in engine:
        sys.exit(
            f"backup_db.py only knows how to back up sqlite3; "
            f"DATABASES['default']['ENGINE'] is '{engine}'. Extend this "
            f"script (a pg_dump leg) before relying on it here."
        )

    return settings.DATABASES["default"]["NAME"]


def _write_backup(source_path, dest_dir):
    """
    Purpose: Snapshot the live sqlite3 database into a gzip-compressed,
             timestamped file.

    Entry: source_path names an existing sqlite3 file. dest_dir exists or
           is creatable.

    Exit/Returns: Path to the written .db3.gz file.

    Methodology: sqlite3.Connection.backup() page-copies under a read lock,
                 then the plain copy is gzipped and discarded.
    """
    os.makedirs(dest_dir, exist_ok=True)

    timestamp = datetime.now().strftime(_TIMESTAMP_FORMAT)
    plain_path = os.path.join(dest_dir, f"{_BACKUP_PREFIX}{timestamp}.db3")
    gz_path = plain_path + ".gz"

    source_conn = sqlite3.connect(source_path)
    dest_conn = sqlite3.connect(plain_path)
    with dest_conn:
        source_conn.backup(dest_conn)
    source_conn.close()
    dest_conn.close()

    with open(plain_path, "rb") as plain_file, gzip.open(gz_path, "wb") as gz_file:
        shutil.copyfileobj(plain_file, gz_file)
    os.remove(plain_path)

    return gz_path


def _prune_old_backups(dest_dir, keep):
    """
    Purpose: Delete this script's own backups beyond the newest `keep`.

    Entry: keep >= 0. dest_dir may not exist yet.

    Exit/Returns: List of paths deleted, newest-first ordering unaffected.

    Notes: Only ever touches files named like this script's own output in
           dest_dir -- never anything else an operator put there.
    """
    if keep <= 0 or not os.path.isdir(dest_dir):
        return []

    backups = sorted(
        (
            entry.path
            for entry in os.scandir(dest_dir)
            if entry.name.startswith(_BACKUP_PREFIX) and entry.name.endswith(_BACKUP_SUFFIX)
        ),
        reverse=True,
    )

    stale = backups[keep:]
    for path in stale:
        os.remove(path)

    return stale


def _parse_args():
    """Purpose: Parse --keep and --dest from the command line."""
    parser = argparse.ArgumentParser(description="Back up the live Evennia database.")
    parser.add_argument("--keep", type=int, default=_DEFAULT_KEEP)
    parser.add_argument("--dest", default=_DEFAULT_DEST)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    _bootstrap_django()
    source_path = _get_sqlite_path()

    backup_path = _write_backup(source_path, args.dest)
    print(f"Backed up {source_path} -> {backup_path}")

    deleted_paths = _prune_old_backups(args.dest, args.keep)
    for deleted_path in deleted_paths:
        print(f"Pruned {deleted_path}")
