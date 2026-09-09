"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/08/2026
Description: Operator script. Restores characters' `db.skills` Attribute from
             a database backup, for the 09/08/2026 data-loss incident.

             What was lost: a guard in SkillHandler.__init__ tested
             `isinstance(self.obj.db.skills, dict)` and reset the Attribute to
             {} when that came back False. Evennia never hands back a plain
             dict -- a saved Attribute deserialises to
             `dbserialize._SaverDict`, a MutableMapping that is NOT a dict
             subclass -- so the test was False for every healthy character and
             the reset fired on login. Two characters logged in while it was
             live and had their progress zeroed.

             This script reads skills out of a backup, decodes them (including
             the pre-reorganisation blobs that no longer unpickle -- see
             systems/gameplay/progression/skills/recovery.py) and writes them
             back into the live database.

             REPORTS BY DEFAULT. Nothing is written without --apply, which is
             the same arrangement reap_orphans.py uses and for the same
             reason: this touches the live development database.

             THE SERVER MUST BE STOPPED. Evennia caches Attribute values in
             its idmapper, so a running server will overwrite anything written
             here the next time it saves the character. The script refuses to
             --apply while a server pid file is present unless --force says
             otherwise.

Usage:
    ../evenv/Scripts/python.exe scripts/restore_skills_from_backup.py BACKUP
    ../evenv/Scripts/python.exe scripts/restore_skills_from_backup.py BACKUP --apply

    BACKUP        path to a .db3 or .db3.gz produced by backup_db.py
    --apply       actually write. Without it, the script only reports.
    --only NAME   restrict to one character key. Repeatable.
    --force       allow --apply even with a server pid file present.
"""

import argparse
import gzip
import os
import shutil
import socket
import sqlite3
import sys
import tempfile
from datetime import datetime

# The game dir (blackout/), one level up from scripts/. Same note as
# map_sync.py and backup_db.py: running this file puts THIS directory on
# sys.path[0], not the caller's cwd.
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if _GAME_DIR not in sys.path:
    sys.path.insert(0, _GAME_DIR)


def _bootstrap_django():
    """Load Django settings only -- no evennia._init(), no server start."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")

    import django

    django.setup()


# Must run before the recovery import below: that module reaches
# evennia.utils.logger, which reads settings at import time. Same reason
# backup_db.py bootstraps before it touches anything Evennia.
_bootstrap_django()

from systems.gameplay.progression.skills import recovery  # noqa: E402

_LIVE_DB = os.path.join(_GAME_DIR, "server", "evennia.db3")
_PID_FILES = ("server.pid", "portal.pid")
_PID_DIR = os.path.join(_GAME_DIR, "server")
_PROBE_HOST = "127.0.0.1"
_PROBE_TIMEOUT_SECONDS = 0.35

# Settings whose values name a TCP port the running Server or Portal holds
# open. Probed in order; the first one that accepts a connection proves a
# server is up. See _server_is_running for why a pid file is not enough.
_LIVENESS_PORT_SETTINGS = (
    "AMP_PORT",
    "GODOT_CLIENT_WEBSOCKET_PORT",
    "WEBSERVER_PORTS",
    "TELNET_PORTS",
)
_SKILLS_ATTR = "skills"
_GZIP_SUFFIX = ".gz"
_LEVEL_KEY = "level"
_SAFETY_PREFIX = "pre_restore_"

_ATTR_QUERY = """
    select o.id, o.db_key, a.id, a.db_value
    from typeclasses_attribute a
    join objects_objectdb_db_attributes m on m.attribute_id = a.id
    join objects_objectdb o on o.id = m.objectdb_id
    where a.db_key = ?
"""


def _read_skills(db_path):
    """
    Purpose: Read every object's skills Attribute out of one database.

    Entry:
        db_path points at an sqlite database file.

    Exit/Returns:
        Returns {object_id: (object_key, attribute_row_id, decoded_dict)}.
        decoded_dict is None when nothing could be decoded.

    Module Globals:
        _ATTR_QUERY read.
        _SKILLS_ATTR read.

    Methodology:
        Opened read-only via a URI, so pointing this at the live database can
        never modify it. Each value is base64+pickle; a value that will not
        unpickle normally is handed to recovery.decode_legacy_blob, which is
        the whole reason a pre-reorganisation character is restorable at all.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/08/2026
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    found = {}

    for obj_id, obj_key, attr_id, raw in conn.execute(_ATTR_QUERY, (_SKILLS_ATTR,)):
        decoded = _decode_value(raw)
        found[obj_id] = (obj_key, attr_id, decoded)

    conn.close()

    return found


def _decode_value(raw):
    """
    Purpose: Turn one stored Attribute value into a plain skills dict.

    Entry:
        raw is the base64 text sqlite holds for the Attribute.

    Exit/Returns:
        Returns a `str -> {level, xp}` dict, or None if unreadable.

    Module Globals:
        None.

    Methodology:
        recovery.decode_legacy_blob already does base64, a rescue unpickle
        that remaps moved modules, and the legacy tuple-key normalisation.
        Reusing it means the script and the running game agree on what a
        legacy blob means, rather than carrying a second decoder that could
        drift from it.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/08/2026
    """
    if raw is None:
        return None

    return recovery.decode_legacy_blob(raw)


def _resolve_backup(path):
    """
    Purpose: Give back a plain .db3 path, decompressing a .gz into a temp file.

    Entry:
        path names a .db3 or .db3.gz backup.

    Exit/Returns:
        Returns (usable_path, temp_dir_or_None). The caller removes the temp
        directory when it is not None.

    Module Globals:
        _GZIP_SUFFIX read.

    Methodology:
        sqlite cannot open a gzip stream, so a compressed backup is expanded
        into a temporary directory rather than beside the backup itself --
        writing next to the backups would leave the prune in backup_db.py
        looking at files it did not create.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/08/2026
    """
    is_compressed = path.endswith(_GZIP_SUFFIX)

    if not is_compressed:
        return path, None

    temp_dir = tempfile.mkdtemp(prefix="skillrestore_")
    basename = os.path.basename(path[: -len(_GZIP_SUFFIX)])
    target = os.path.join(temp_dir, basename)

    with gzip.open(path, "rb") as source:
        with open(target, "wb") as dest:
            shutil.copyfileobj(source, dest)

    return target, temp_dir


def _total_level(skills):
    """
    Sum levels across a decoded skills dict.

    None means UNREADABLE and 0 means readable-but-empty. Conflating the two
    made the 09/08/2026 restore report "total level unreadable" for a
    character whose skills were merely an empty dict, which hid the fact that
    the previous run had already reset them.
    """
    if skills is None:
        return None

    total = 0

    for record in skills.values():
        total += record.get(_LEVEL_KEY, 0)

    return total


def _candidate_ports():
    """Flatten _LIVENESS_PORT_SETTINGS into the ports actually configured."""
    from django.conf import settings

    ports = []

    for name in _LIVENESS_PORT_SETTINGS:
        value = getattr(settings, name, None)

        if value is None:
            continue

        if isinstance(value, int):
            ports.append(value)
            continue

        for entry in value:
            if isinstance(entry, int):
                ports.append(entry)

    return ports


def _port_is_open(port):
    """True when something accepts a local TCP connection on `port`."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.settimeout(_PROBE_TIMEOUT_SECONDS)

    try:
        probe.connect((_PROBE_HOST, port))
        return True
    except Exception:
        return False
    finally:
        probe.close()


def _server_is_running():
    """
    Purpose: Decide whether an Evennia server is up and would clobber a write.

    Entry:
        None.

    Exit/Returns:
        Returns True when a server appears to be running.

    Module Globals:
        _PID_FILES read.
        _PID_DIR read.

    Methodology:
        A pid file alone is NOT sufficient evidence here and relying on one
        would have made this script unsafe in exactly the situation it was
        written for: on 09/08/2026 the development server was running, with a
        client attached, and no pid file existed anywhere under server/.
        A pid file is also the opposite failure -- a stale one left by a crash
        reports a server that is gone.

        So the authoritative check is a TCP probe of the ports the running
        Server and Portal hold open, read from settings rather than typed
        here. The pid files are kept only as a second, weaker signal.

    Notes/References:
        The ports come from settings so a port change reaches this check
        without an edit -- the same reason backup_db.py reads the database
        path from settings instead of hardcoding it.

    Author: Nick Hobar
    Creation date: 09/08/2026
    """
    for port in _candidate_ports():
        if _port_is_open(port):
            return True

    for name in _PID_FILES:
        candidate = os.path.join(_PID_DIR, name)

        if os.path.exists(candidate):
            return True

    return False


def _build_plan(live, backup, only):
    """
    Purpose: Decide which characters would be restored, and why.

    Entry:
        live and backup are _read_skills results. only is a set of character
        keys to restrict to, or an empty set for no restriction.

    Exit/Returns:
        Returns a list of dicts describing each candidate restore.

    Module Globals:
        None.

    Methodology:
        A character is a candidate only when the backup can be decoded AND
        its total level is strictly HIGHER than what live holds. That
        comparison is the safety property: it makes the script incapable of
        overwriting progress earned since the backup was taken, so running it
        with too old a backup does nothing rather than rolling a player back.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/08/2026
    """
    plan = []

    for obj_id, (obj_key, attr_id, live_skills) in sorted(live.items()):
        restrict = len(only) > 0

        if restrict and obj_key not in only:
            continue

        backup_entry = backup.get(obj_id)

        if backup_entry is None:
            continue

        backup_skills = backup_entry[2]

        if not backup_skills:
            continue

        live_total = _total_level(live_skills)
        backup_total = _total_level(backup_skills)
        live_number = live_total or 0

        if backup_total <= live_number:
            continue

        plan.append({
            "obj_id": obj_id,
            "obj_key": obj_key,
            "attr_id": attr_id,
            "live_total": live_total,
            "backup_total": backup_total,
            "skills": backup_skills,
        })

    return plan


def _encode_value(skills):
    """
    Purpose: Render a skills dict exactly as Evennia stores one on disk.

    Entry:
        skills is a plain `str -> {level, xp}` dict.

    Exit/Returns:
        Returns the base64 TEXT that belongs in typeclasses_attribute.db_value.

    Module Globals:
        None.

    Methodology:
        Two layers, and both are mandatory. Attribute.value stores
        `to_pickle(value)` into the field, and PickledObjectField then
        base64-encodes it on the way to the column -- so the bytes in the
        column are `dbsafe_encode(to_pickle(value))`, not a bare pickle.

        Writing `dbserialize(...)` here instead produced a raw pickle in a
        TEXT column on 09/08/2026. Evennia read it back, failed to base64
        decode it, swallowed the failure per from_db_value, and handed the
        game a value it could not use -- so a restore that reported success
        left both characters exactly as broken as before. _verify_written is
        what makes that failure mode impossible to repeat silently.

    Notes/References:
        Both helpers are imported from Evennia rather than reimplemented, so
        a future change to its storage format reaches this script.

    Author: Nick Hobar
    Creation date: 09/08/2026
    """
    return recovery.encode_attribute_value(skills)


def _verify_written(conn, plan):
    """
    Purpose: Read every row just written back and confirm it decodes to what
    the plan intended.

    Entry:
        conn is the open connection the write happened on, before commit.
        plan is the list from _build_plan.

    Exit/Returns:
        Returns a list of human-readable mismatch descriptions. Empty means
        every row verified.

    Module Globals:
        None.

    Methodology:
        Reads through the SAME decoder the game and the report use, so this
        checks the bytes that landed in the column rather than the Python
        object that was meant to land there. A restore whose own report says
        "Restored 2" while the database holds something unreadable is worse
        than a restore that refuses, because it sends the operator away
        believing the incident is closed.

        Runs before commit so a mismatch can be rolled back.

    Notes/References:
        None.

    Author: Nick Hobar
    Creation date: 09/08/2026
    """
    problems = []

    for row in plan:
        stored = conn.execute(
            "select db_value from typeclasses_attribute where id = ?",
            (row["attr_id"],),
        ).fetchone()

        if stored is None:
            problems.append(f"{row['obj_key']}: attribute row vanished")
            continue

        decoded = _decode_value(stored[0])

        if decoded is None:
            problems.append(f"{row['obj_key']}: written value does not decode")
            continue

        if decoded != row["skills"]:
            problems.append(
                f"{row['obj_key']}: written value decodes to something else "
                f"(total {_total_level(decoded)} vs {row['backup_total']})"
            )

    return problems


def _apply(plan, safety_copy):
    """
    Purpose: Write the planned skills back into the live database.

    Entry:
        plan is the list from _build_plan. safety_copy is a path already
        holding a copy of the live database.

    Exit/Returns:
        Returns the number of Attribute rows written, or None when the
        written rows failed verification and the transaction was rolled back.

    Module Globals:
        _LIVE_DB read.

    Methodology:
        Each row is rewritten by its own Attribute id, so nothing here can
        touch an Attribute other than the ones the plan named. The whole set
        is one transaction: a half-applied restore is worse than none, since
        it would leave the operator unsure which characters had been done.

    Notes/References:
        The safety copy is taken by the caller BEFORE this runs.

    Author: Nick Hobar
    Creation date: 09/08/2026
    """
    conn = sqlite3.connect(_LIVE_DB)
    written = 0

    try:
        for row in plan:
            encoded = _encode_value(row["skills"])
            conn.execute(
                "update typeclasses_attribute set db_value = ? where id = ?",
                (encoded, row["attr_id"]),
            )
            written += 1

        problems = _verify_written(conn, plan)

        if problems:
            conn.rollback()
            print("  ! REFUSING to commit -- written rows did not verify:")

            for problem in problems:
                print(f"  !   {problem}")

            print(f"  ! live db unchanged; safety copy at {safety_copy}")
            return None

        conn.commit()
    except Exception:
        conn.rollback()
        print(f"  ! write failed and was rolled back; live db unchanged")
        print(f"  ! safety copy is at {safety_copy}")
        raise
    finally:
        conn.close()

    return written


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", help="path to a .db3 or .db3.gz backup")
    parser.add_argument("--apply", action="store_true",
                        help="write to the live database (default: report only)")
    parser.add_argument("--only", action="append", default=[],
                        help="restrict to this character key; repeatable")
    parser.add_argument("--force", action="store_true",
                        help="allow --apply while a server pid file exists")
    args = parser.parse_args()

    backup_path, temp_dir = _resolve_backup(args.backup)

    try:
        live = _read_skills(_LIVE_DB)
        backup = _read_skills(backup_path)
        plan = _build_plan(live, backup, set(args.only))

        print(f"live   : {_LIVE_DB}")
        print(f"backup : {args.backup}")
        print(f"characters with a skills attribute: live {len(live)}, "
              f"backup {len(backup)}\n")

        if not plan:
            print("Nothing to restore -- no character's backup total level "
                  "exceeds what the live database already holds.")
            return 0

        print(f"{len(plan)} character(s) would be restored:\n")

        for row in plan:
            live_shown = row["live_total"]

            if live_shown is None:
                live_shown = "unreadable"

            print(f"  #{row['obj_id']:<6} {row['obj_key']:<20} "
                  f"total level {live_shown} -> {row['backup_total']}")

            for skill_key in sorted(row["skills"]):
                record = row["skills"][skill_key]
                print(f"       {skill_key:<16} level {record['level']:>3}  "
                      f"xp {record['xp']}")

            print("")

        if not args.apply:
            print("Report only. Re-run with --apply to write.")
            return 0

        if _server_is_running() and not args.force:
            print("REFUSING: a server pid file is present. Evennia caches "
                  "Attributes in its idmapper and would overwrite this "
                  "restore on the next save.")
            print("Stop the server (evennia stop), then re-run. Use --force "
                  "only if you know the pid file is stale.")
            return 1

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safety_copy = f"{_LIVE_DB}.{_SAFETY_PREFIX}{stamp}"
        shutil.copy2(_LIVE_DB, safety_copy)
        print(f"safety copy of the live database: {safety_copy}")

        written = _apply(plan, safety_copy)

        if written is None:
            return 1

        print(f"Restored {written} character(s).")

        return 0
    finally:
        if temp_dir is not None:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
