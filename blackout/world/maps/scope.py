"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 09/17/2026
Description: Owner of a rebuild's SCOPE -- the answer to "which part of the
             world does this run touch". `scripts/map_sync.py` rebuilt every
             map in the manifest on every run, so a one-tile edit to the
             smallest map paid for the largest one. This module turns the
             operator's `--map` and `--tile` flags into the set of maps and
             tiles a run may purge and respawn.

             Parsing lives here, beside world.maps.manifest, for the same
             reason the manifest reader does: the format gets exactly one
             reader, and the operator script stays a thin CLI on top of it.

             Pure data. Importing this module touches no database and boots no
             Evennia, so it is safe to import from tests.
"""

from dataclasses import dataclass

# How an operator writes one tile on the command line: "<zcoord>:<x>,<y>".
_TILE_ZCOORD_SEPARATOR = ":"
_TILE_COORD_SEPARATOR = ","
_TILE_COORD_COUNT = 2

_TILE_FORMAT_HINT = "<zcoord>:<x>,<y>, for example 'oasis:12,4'"


class ScopeError(RuntimeError):
    """Raised when a --map or --tile argument names nothing the manifest lists."""


@dataclass(frozen=True)
class TileRef:
    """One map coordinate a run rebuilds: the map, and the X,Y of the tile on it."""

    zcoord: str
    x: int
    y: int

    @property
    def xy(self):
        """The coordinate as the (X, Y) tuple the xyzgrid contrib expects."""
        return (self.x, self.y)


@dataclass(frozen=True)
class RebuildScope:
    """
    What one run of the map sync may purge and respawn.

    whole_maps holds the z-coordinates rebuilt end to end. tiles holds the
    individual tiles rebuilt on maps that are NOT in whole_maps. is_full is
    True only for a run the operator gave no scope flags at all, which is the
    one run allowed to remove maps the manifest no longer lists.
    """

    whole_maps: tuple
    tiles: tuple
    is_full: bool

    @property
    def zcoords(self):
        """Every z-coordinate this run touches, whole maps first, without repeats."""
        found = list(self.whole_maps)

        for tile in self.tiles:
            already_listed = tile.zcoord in found
            if not already_listed:
                found.append(tile.zcoord)

        return tuple(found)

    def tiles_of(self, zcoord):
        """Every TileRef this run rebuilds on one map, as a tuple."""
        matching = [tile for tile in self.tiles if tile.zcoord == zcoord]

        return tuple(matching)

    def is_whole_map(self, zcoord):
        """True when this run rebuilds the named map end to end rather than by tile."""
        return zcoord in self.whole_maps

    def describe(self):
        """
        Purpose: Render the scope as one line an operator can check the run
                 against before it deletes anything.

        Entry:
            No conditions.

        Exit/Returns:
            Returns a human-readable string.

        Module Globals:
            None

        Methodology:
            Name the whole maps first, then each tile-scoped map with its
            coordinates, so the two halves of a mixed run stay legible.

        Notes/References:
            The script prints this instead of echoing the raw flags. A scope
            that resolved differently from what the operator typed -- a map
            flag that swallowed a tile flag, say -- has to be visible.

        Author: Nick Hobar
        Creation date: 09/17/2026
        """
        if self.is_full:
            return "every map in the manifest"

        parts = list(self.whole_maps)
        tiled_zcoords = [zcoord for zcoord in self.zcoords if zcoord not in self.whole_maps]

        for zcoord in tiled_zcoords:
            coords = [f"({tile.x},{tile.y})" for tile in self.tiles_of(zcoord)]
            parts.append(f"{zcoord} tiles {' '.join(coords)}")

        return "; ".join(parts)


def _known_zcoords(entries):
    """The manifest's z-coordinates as a list, used for membership and error text."""
    zcoords = [entry.zcoord for entry in entries]

    return zcoords


def _require_listed(zcoord, entries):
    """
    Purpose: Refuse a z-coordinate the manifest does not list.

    Entry:
        zcoord is an operator-supplied string; entries is a list of MapEntry.

    Exit/Returns:
        Returns the z-coordinate unchanged. Raises ScopeError if it is not in
        the manifest.

    Module Globals:
        None

    Methodology:
        Compare against the manifest's own list, and name every valid
        alternative in the error.

    Notes/References:
        This runs before the script deletes anything. A misspelled map name
        must cost an error message, never a rebuild of the wrong map.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """
    listed = _known_zcoords(entries)

    if zcoord not in listed:
        raise ScopeError(
            f"'{zcoord}' is not a map in the manifest. Listed maps: {', '.join(listed)}."
        )

    return zcoord


def parse_tile_ref(text, entries):
    """
    Purpose: Turn one `--tile` argument into a TileRef.

    Entry:
        text is an operator-supplied string of the form "<zcoord>:<x>,<y>";
        entries is a list of MapEntry.

    Exit/Returns:
        Returns a TileRef. Raises ScopeError on any malformed field or on a
        map the manifest does not list.

    Module Globals:
        _TILE_ZCOORD_SEPARATOR, _TILE_COORD_SEPARATOR, _TILE_COORD_COUNT,
        _TILE_FORMAT_HINT read.

    Methodology:
        Split on the map separator first, then on the coordinate separator,
        and convert both coordinates to int.

    Notes/References:
        The map name is mandatory even when the run scopes only one map. A
        bare "12,4" would read as a coordinate on whichever map the operator
        happened to list first, and a rebuild must never guess which tile it
        is about to destroy.

        Coordinates are MAP coordinates -- the X,Y an XYZRoom reports -- not
        character positions in the map string. world/maps/map_glyph_legend.md
        covers the difference.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """
    raw = text.strip()
    zcoord, separator, coords = raw.partition(_TILE_ZCOORD_SEPARATOR)

    if not separator or not zcoord.strip():
        raise ScopeError(f"Tile '{raw}' is not of the form {_TILE_FORMAT_HINT}.")

    fields = coords.split(_TILE_COORD_SEPARATOR)

    if len(fields) != _TILE_COORD_COUNT:
        raise ScopeError(f"Tile '{raw}' needs exactly two coordinates: {_TILE_FORMAT_HINT}.")

    try:
        x = int(fields[0].strip())
        y = int(fields[1].strip())
    except ValueError as exc:
        raise ScopeError(f"Tile '{raw}' has a non-numeric coordinate: {exc}") from exc

    listed = _require_listed(zcoord.strip(), entries)

    return TileRef(zcoord=listed, x=x, y=y)


def build_scope(map_args, tile_args, entries):
    """
    Purpose: Resolve the operator's scope flags into the maps and tiles one
             run may touch.

    Entry:
        map_args is a list of `--map` values; tile_args is a list of `--tile`
        values; entries is the manifest's list of MapEntry.

    Exit/Returns:
        Returns a RebuildScope. Raises ScopeError on an unlisted map or a
        malformed tile.

    Module Globals:
        None

    Methodology:
        Validate every map name, parse every tile, then drop the tiles whose
        map is already being rebuilt end to end. Manifest order is preserved
        so the run reports its maps the way the operator's file lists them.

    Notes/References:
        A map named by BOTH flags is rebuilt whole, because the whole map is
        the superset. This resolves rather than refuses, and RebuildScope.describe
        reports what it resolved to, so the wider run is never silent.

        Giving no flags returns is_full=True, and that flag is what lets the
        script keep removing maps the manifest dropped. A scoped run must not
        reach a map the operator did not name, and pruning is by definition
        about maps that are named nowhere.

    Author: Nick Hobar
    Creation date: 09/17/2026
    """
    named_maps = [_require_listed(value.strip(), entries) for value in map_args]
    parsed_tiles = [parse_tile_ref(value, entries) for value in tile_args]

    is_full = not named_maps and not parsed_tiles

    if is_full:
        return RebuildScope(
            whole_maps=tuple(_known_zcoords(entries)),
            tiles=(),
            is_full=True,
        )

    ordered_maps = [zcoord for zcoord in _known_zcoords(entries) if zcoord in named_maps]
    kept_tiles = [tile for tile in parsed_tiles if tile.zcoord not in ordered_maps]

    return RebuildScope(
        whole_maps=tuple(ordered_maps),
        tiles=tuple(kept_tiles),
        is_full=False,
    )
