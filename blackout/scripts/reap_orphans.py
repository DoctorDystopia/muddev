"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/28/2026
Description: Operator script. Destroys the objects that map rebuilds exiled to
             DEFAULT_HOME before GridTile.at_object_delete existed to destroy
             them in place.

             Evennia's `clear_contents` does not delete a room's contents; it
             moves each of them to its home, rewriting that home to
             `settings.DEFAULT_HOME` whenever the home IS the room being
             deleted. Nothing the spawners create passes `home=`, so every
             gathering node, facility, bank and NPC on the grid was exiled to
             Limbo rather than destroyed on each rebuild.

             `systems/spawning/teardown.py` closes that going forward. This
             closes the backlog: on 08/28/2026 the development database held
             623 objects standing in Limbo with 197 more nested inside them,
             against 23 real non-exit objects on the entire live grid.

             The rule is that Limbo is the fallback DESTINATION for a homeless
             object, not a place anything lives. A player character standing
             there is passing through and is left alone; anything else is
             debris. `TEARDOWN_EXEMPT_TAG` is the escape hatch for a prop that
             must genuinely sit there.

             Stranded grid rooms -- those tagged with a z-coordinate belonging
             to no map at all -- are NOT this script's business. map_sync.py
             reaps those, and since it now diffs the database rather than the
             grid's own registry it can finally see them. Run a rebuild.

             DESTRUCTIVE, and unlike map_sync.py it undoes nothing that a
             rebuild puts back. It therefore REPORTS BY DEFAULT and deletes
             only when passed --apply, in the shape the moderator egg's one
             irreversible entry uses: count what will be destroyed, show it,
             then act. Run deliberately, never import.

Usage:
    ../evenv/Scripts/python.exe scripts/reap_orphans.py [--apply] [--limit N]

    With no flags it changes nothing and prints what it would destroy.
    --limit caps how many example lines are listed, not how many are reaped.
"""

import os
import sys

# The game dir (blackout/), one level up from this file in scripts/. See the
# same note in map_sync.py: running `python scripts/reap_orphans.py` puts THIS
# file's directory on sys.path[0], not the caller's cwd.
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_APPLY_FLAG = "--apply"
_LIMIT_FLAG = "--limit"
_DEFAULT_EXAMPLE_LIMIT = 20


def _bootstrap_evennia():
    """Bring Django/Evennia up so ObjectDB and the typeclasses are usable."""
    if _GAME_DIR not in sys.path:
        sys.path.insert(0, _GAME_DIR)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.conf.settings")

    import django

    django.setup()

    import evennia

    evennia._init()


def _parse_limit(argv):
    """Read the --limit value out of argv, falling back to the default."""
    limit = _DEFAULT_EXAMPLE_LIMIT

    if _LIMIT_FLAG not in argv:
        return limit

    position = argv.index(_LIMIT_FLAG)
    try:
        limit = int(argv[position + 1])
    except (IndexError, ValueError):
        raise RuntimeError(f"{_LIMIT_FLAG} needs a whole number after it.")

    return limit


def get_default_home():
    """
    Purpose: Fetch the room that homeless objects are sent to.

    Entry:
        No conditions. Evennia must already be bootstrapped.

    Exit/Returns:
        Returns the DEFAULT_HOME room. Raises RuntimeError if the setting
        names a row that does not exist.

    Module Globals:
        None

    Methodology:
        Read settings.DEFAULT_HOME, strip its leading '#', and fetch the row.

    Notes/References:
        Resolved the same way evennia/objects/objects.py:1354 resolves it, so
        this script and `clear_contents` cannot disagree about which room is
        the sink being drained.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    from django.conf import settings
    from evennia.objects.models import ObjectDB

    dbref = settings.DEFAULT_HOME.lstrip("#")
    home_id = int(dbref)

    try:
        home = ObjectDB.objects.get(id=home_id)
    except ObjectDB.DoesNotExist:
        raise RuntimeError(
            f"settings.DEFAULT_HOME (= '{settings.DEFAULT_HOME}') does not exist. "
            "Nothing to reap, and a great deal else is broken."
        )

    return home


def find_orphans(home):
    """
    Purpose: List the debris standing in the fallback home room.

    Entry:
        home is the DEFAULT_HOME room.

    Exit/Returns:
        Returns a list of objects that should be destroyed. Player characters,
        exits and tag-exempt objects are excluded.

    Module Globals:
        None

    Methodology:
        Filter the room's direct contents through the same predicate a room
        teardown uses.

    Notes/References:
        Direct contents only. What is nested inside an orphan is reached by
        `teardown.demolish` recursing into it, and must NOT be listed here as
        well -- an object counted twice is one this script tries to delete
        after it is already gone.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    from systems.spawning import teardown

    orphans = []
    standing = list(home.contents)

    for obj in standing:
        spared = teardown.survives_teardown(obj)
        if spared:
            continue
        orphans.append(obj)

    return orphans


def count_subtree(orphans):
    """
    Purpose: Total the orphans and everything nested inside them.

    Entry:
        orphans is the list from find_orphans.

    Exit/Returns:
        Returns the number of database rows a reap would remove.

    Module Globals:
        None

    Methodology:
        Walk each orphan's contents breadth-first, counting as it goes.

    Notes/References:
        The nested half is not a rounding error. Deleting a shopkeep evicts
        its stock to Limbo rather than destroying it, which is how 197 of the
        820 rows in the 08/28/2026 backlog got there -- an operator told only
        the direct count would watch the number refuse to fall.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    total = 0
    pending = list(orphans)

    while pending:
        obj = pending.pop()
        total += 1
        held = list(obj.contents)
        pending.extend(held)

    return total


def describe(orphans, limit):
    """Print a typeclass census, then up to `limit` example rows."""
    census = {}

    for obj in orphans:
        path = obj.typeclass_path
        census[path] = census.get(path, 0) + 1

    ranked = sorted(census.items(), key=lambda pair: pair[1], reverse=True)

    for path, count in ranked:
        print(f"  {count:5d}  {path}")

    print()

    for obj in orphans[:limit]:
        held = len(obj.contents)
        print(f"    #{obj.id} '{obj.key}' (holding {held})")

    remaining = len(orphans) - limit
    if remaining > 0:
        print(f"    ... and {remaining} more")


def reap(orphans):
    """
    Purpose: Destroy every orphan, and everything inside it, innermost first.

    Entry:
        orphans is the list from find_orphans.

    Exit/Returns:
        Returns the number of objects actually deleted.

    Module Globals:
        None

    Methodology:
        Hand each orphan to teardown.demolish, which recurses into contents
        before deleting the container.

    Notes/References:
        Depth-first is the whole point. Deleting a container first runs
        `clear_contents` on it, which sends its contents back to Limbo -- so a
        naive sweep would delete 623 rows and create 197 new orphans in the
        same pass.

    Author: Nick Hobar
    Creation date: 08/28/2026
    """
    from systems.spawning import teardown

    destroyed = 0

    for obj in orphans:
        destroyed += teardown.demolish(obj)

    return destroyed


def _run(apply_changes, limit):
    """Report the orphan backlog, and drain it when asked to."""
    home = get_default_home()
    print(f"=== Orphans standing in {home.key} (#{home.id}) ===")

    orphans = find_orphans(home)

    if not orphans:
        print("  none -- nothing to reap.")
        return

    subtree = count_subtree(orphans)
    print(f"{len(orphans)} object(s) standing here, {subtree} counting their contents.")
    print()
    describe(orphans, limit)
    print()

    if not apply_changes:
        print(f"Reported only. Re-run with {_APPLY_FLAG} to destroy these.")
        return

    destroyed = reap(orphans)
    print(f"Destroyed {destroyed} object(s).")

    left = find_orphans(home)
    if left:
        print(f"WARNING: {len(left)} object(s) still standing. See the server log.")


def main(argv):
    """Entry point. Bootstraps Evennia, then reports or drains the backlog."""
    apply_changes = _APPLY_FLAG in argv

    _bootstrap_evennia()

    try:
        limit = _parse_limit(argv)
        _run(apply_changes, limit)
    except Exception as exc:
        print(f"Aborting: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
