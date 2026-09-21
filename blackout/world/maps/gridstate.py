"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/20/2026
Description: Whether the grid Script's stored map data can still be read.

             THE XYZGRID CONTRIB PICKLES LEGEND CLASSES INTO A DATABASE ROW.
             `XYZGrid.db.map_data` holds each map's `legend`, and a legend
             value is a CLASS -- `CopperPoleNode`, `MutantCrabNPCNode`,
             `ToOasisOutskirtsNode`. Evennia pickles it by its import path, so
             the row names `world.maps.azm_plains.CopperPoleNode`.

             Rename that class and the row names nothing. Evennia's
             unserializer cannot resolve the path, gives up, and returns the
             RAW BASE64 STRING it was handed. Nothing raises. Every later read
             then fails somewhere else entirely:

               - `self.db.map_data[zcoord] = mapdata` -> 'str' object does not
                 support item assignment, which aborted a rebuild mid-run and
                 left the server stopped.
               - `set(grid.db.map_data or {})` -> a set of single characters,
                 which reads to the prune as a list of maps to remove.

             That happened on 09/20/2026, when `RustyPoleNode` became
             `CopperPoleNode` on azm_plains.

             This is CLAUDE.md's "an import path belongs in the code, never in
             a database row", arriving through a contrib rather than through
             our own code. We cannot stop the contrib from writing the row, so
             the next best thing is to NOTICE it. The stored map data is
             regenerable from `world/maps/*.py` in full, so an unreadable row
             is never worth keeping -- `XYZGrid.add_maps` refills it from
             source in the same run that clears it.

             Importable on purpose. `scripts/map_sync.py` is the only caller,
             and that directory is import-unsafe, so the rule lives here where
             a test can reach it.
"""

from collections.abc import MutableMapping


# ─── Private constant definitions ────────────────────────────────────────────

# What an operator is told when the row cannot be read. Written as a template
# rather than assembled at the call site, because the recovery instruction is
# the part that matters and it must not be rewritten by the next caller.
_UNREADABLE_TEMPLATE = (
    "  grid map_data is unreadable (%s, %d chars). A legend class was renamed "
    "or moved, so the stored pickle names a class that no longer exists.\n"
    "  Clearing it. add_maps refills it from world/maps/*.py in this run."
)

# What a dry run says instead. Same fact, no promise that anything changed.
_DRY_RUN_TEMPLATE = (
    "  grid map_data is unreadable (%s, %d chars). A legend class was renamed "
    "or moved, so the stored pickle names a class that no longer exists.\n"
    "  A real run clears it and refills it from world/maps/*.py."
)


def map_data_is_readable(value):
    """
    Purpose: Say whether `XYZGrid.db.map_data` came back as map data.

    Entry:
        value - whatever `grid.db.map_data` returned. `None` on a grid that
                has never registered a map.

    Exit/Returns:
        Returns True when the value is usable as map data, False when Evennia
        handed back an unresolved pickle.

    Module Globals:
        None

    Methodology:
        Tests for a MAPPING rather than for `str`, and the direction is the
        point. A `dict` written through Evennia comes back as a `_SaverDict`,
        which is a MutableMapping and not a `dict` subclass, so an
        `isinstance(value, dict)` check would call every healthy grid broken.
        Anything that is not a mapping is not map data, whatever type the
        failure happens to produce.

        `None` is readable. A grid with no maps registered yet is the state
        every fresh database starts in, and clearing it would be a repair of
        nothing.

    Notes/References:
        The module docstring has how an unreadable row is produced.

    Author: Nick Hobar
    Creation date: 09/20/2026
    """
    if value is None:
        return True

    return isinstance(value, MutableMapping)


def describe_unreadable_map_data(value, dry_run=False):
    """
    Purpose: The operator-facing report for an unreadable map_data row.

    Entry:
        value   - the unreadable value, for its type and size.
        dry_run - True to describe the repair rather than promise it.

    Exit/Returns:
        Returns the text to print. Never raises, whatever `value` is.

    Module Globals:
        _UNREADABLE_TEMPLATE and _DRY_RUN_TEMPLATE read.

    Methodology:
        Names the CAUSE, not the symptom. The operator reading this line did
        not rename a class on purpose to break the grid -- they renamed one to
        add a copper pole, and the traceback they got named neither the class
        nor the map. The size is included because it is what tells a reader
        the row held real data rather than a stray write.

    Notes/References:
        None

    Author: Nick Hobar
    Creation date: 09/20/2026
    """
    template = _UNREADABLE_TEMPLATE

    if dry_run:
        template = _DRY_RUN_TEMPLATE

    return template % (type(value).__name__, len(str(value)))
