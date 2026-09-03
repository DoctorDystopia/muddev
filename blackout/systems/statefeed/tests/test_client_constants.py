"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/23/2026
Description: Drift guards for the facts the Godot client retypes.

             A client cannot import Python, so a handful of facts the server
             owns -- which room kinds exist, which maps exist -- are spelled out
             again in the client's own language. Nothing checks the copies, and
             they have already drifted: `ROOM_KIND_COLORS` named a room kind
             ("Pole clearing") that no map has ever declared, so both the metal
             and the rusty pole clearings silently rendered a hash colour rather
             than the authored one. The dead key had also been copied into the
             now-retired browser webclient (archive/webclient-js/), which is
             exactly the kind of drift this module exists to catch regardless
             of which client is asking.

             The asymmetry below is deliberate and is the whole design:

               - A client key naming NOTHING is a bug. It is dead weight that
                 looks like configuration, and the thing it was meant to
                 configure is silently getting the fallback.
               - A server fact with NO client entry is FINE. Both tables are
                 explicitly documented as having a fallback -- room kinds hash
                 to a stable hue, maps not named in the layout order fall in
                 after the named ones -- so a new room or map needs no client
                 edit. Asserting a census here would fail the moment content is
                 added as intended, which CLAUDE.md names as the way a test
                 trains people to edit it rather than read it.

             Reads the client sources as TEXT. That is not laziness: parsing is
             cheap and total here, whereas executing GDScript from a Django
             test would mean a runtime dependency for a check whose whole
             value is that it costs nothing to keep running.

             Every table below is looked up in whatever client files are
             present, and a missing file is skipped rather than failed -- so a
             client can gain or lose a screen with no edit here. The vacuity
             guard in `test_at_least_one_client_table_was_found` is what stops
             "skipped everything" from reading as "passed".
"""

import os
import re
import unittest

from .. import clientexport as _clientexport
from .. import constants as const


# ─── Private constant definitions ────────────────────────────────────────────

# The game dir (blackout/), four levels up from
# systems/statefeed/tests/test_client_constants.py.
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

# The repo root, one further up, because the Godot client is a sibling of the
# game dir rather than inside it.
_REPO_ROOT = os.path.dirname(_GAME_DIR)

# Where each client spells out the two tables. A path that does not exist is
# skipped; see the module docstring.
_ROOM_KIND_TABLE_SOURCES: tuple = (
    # Both tables moved out of world_view.gd on 08/28/2026, when the minimap
    # became a second pane drawing the same map. This path moved WITH them, in
    # the same change, because a source this scanner cannot find is one it
    # silently stops checking -- which is the whole reason for the vacuity
    # guard further down.
    os.path.join(_REPO_ROOT, "godot", "world", "map_palette.gd"),
)

_MAP_ORDER_SOURCES: tuple = _ROOM_KIND_TABLE_SOURCES

# Which skill category is drawn in which colour. The Godot pane's only: the
# browser client has no skills screen, and a table one client does not have is
# not drift.
_SKILL_CATEGORY_SOURCES: tuple = (
    os.path.join(_REPO_ROOT, "godot", "world", "skill_palette.gd"),
)

# Which map is surfaced with which terrain model. The Godot pane's only, for
# now: the browser pane still draws every tile as a plain coloured slab, and a
# table one client does not have is not drift.
_TERRAIN_TABLE_SOURCES: tuple = (
    os.path.join(_REPO_ROOT, "godot", "world", "map_palette.gd"),
)

# The table assignment, in either language. JS writes
# `const ROOM_KIND_COLORS = {`, GDScript writes `const ROOM_KIND_COLORS := {`;
# one optional colon covers both.
_ROOM_KIND_TABLE_RE = re.compile(
    r"ROOM_KIND_COLORS\s*:?=\s*\{(.*?)\}", re.DOTALL)

_MAP_ORDER_RE = re.compile(
    r"Z_LAYOUT_ORDER\s*:?=\s*\[(.*?)\]", re.DOTALL)

_TERRAIN_TABLE_RE = re.compile(
    r"TILE_MODELS\s*:?=\s*\{(.*?)\}", re.DOTALL)

_SKILL_CATEGORY_TABLE_RE = re.compile(
    r"SKILL_CATEGORY_COLORS\s*:?=\s*\{(.*?)\}", re.DOTALL)

# `"map name": "asset_key"` -- both halves of a terrain row at once, because
# the two are checked against DIFFERENT sources and a row read as two loose
# lists could not say which map named the bad key.
_TABLE_PAIR_RE = re.compile(r'"([^"]+)"\s*:\s*"([^"]+)"')

# A double-quoted string that is a table KEY -- followed by a colon. This is
# what keeps `Color("cc6633")` on the GDScript value side out of the key set.
_TABLE_KEY_RE = re.compile(r'"([^"]+)"\s*:')

# Any double-quoted string. Safe for the layout order, which holds only strings.
_QUOTED_RE = re.compile(r'"([^"]+)"')

# A `//` or `#` comment line, stripped before keys are read so a room kind
# named inside a comment is not mistaken for a live entry.
_COMMENT_RE = re.compile(r"(//|#).*$", re.MULTILINE)

# Where a map module declares the room key for a coordinate.
_PROTOTYPE_KEY = "key"

# Where each generated client module is written. Read from the renderer rather
# than restated, which is the same rule this whole module exists to enforce.
_GENERATED_OUTPUTS: dict = _clientexport.output_paths()

# The map modules to read. Deliberately NOT a directory scan of world/maps:
# manifest.py is not a map and neo_cairo.py is a map that exists but is not
# active, and both have to be included for different reasons -- see
# server_room_kinds. Naming them costs one line per map and cannot pick up
# something that is not a map at all.
#
# This never reaches blackout/scripts/, which CLAUDE.md marks import-unsafe.
_MAP_MODULE_NAMES: tuple = (
    "world.maps.oasis",
    "world.maps.oasis_outskirts",
    "world.maps.neo_cairo",
)


# ─── Private helper routines ─────────────────────────────────────────────────

def _read_source(path):
    """
    Purpose: Read a client source file, or report that it is not here.

    Entry:
        path - absolute path to a JavaScript or GDScript file.

    Exit/Returns:
        The file's text with comment tails stripped, or None when the file does
        not exist.

    Module Globals:
        _COMMENT_RE read.

    Methodology:
        Comments are removed before any table is matched, because both client
        tables carry explanatory comments that themselves name room kinds. A
        `map_transition` mentioned in prose is not an entry.

    Notes/References:
        A missing file is not an error. The Godot client is developed on
        `godot-client-prototype`; see the module docstring.
    """
    if not os.path.isfile(path):
        return None

    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()

    return _COMMENT_RE.sub("", text)


def _extract_room_kind_keys(source):
    """
    Purpose: Pull the authored room-kind names out of a client's colour table.

    Entry:
        source - client source text, comments already stripped.

    Exit/Returns:
        A list of the table's keys, or None when the file declares no table.

    Module Globals:
        _ROOM_KIND_TABLE_RE, _TABLE_KEY_RE read.

    Methodology:
        Match the table body, then take only quoted strings followed by a
        colon. The colon is what separates a key from a value, which matters
        for GDScript, where the value is `Color("cc6633")` and the hex is
        itself a quoted string.

    Notes/References:
        None
    """
    match = _ROOM_KIND_TABLE_RE.search(source)

    if not match:
        return None

    return _TABLE_KEY_RE.findall(match.group(1))


def _extract_map_order(source):
    """
    Purpose: Pull the authored map names out of a client's layout order.

    Entry:
        source - client source text, comments already stripped.

    Exit/Returns:
        A list of the map names, or None when the file declares no order.

    Module Globals:
        _MAP_ORDER_RE, _QUOTED_RE read.

    Methodology:
        The list holds nothing but strings in both languages, so every quoted
        run inside it is an entry.

    Notes/References:
        None
    """
    match = _MAP_ORDER_RE.search(source)

    if not match:
        return None

    return _QUOTED_RE.findall(match.group(1))


def _extract_terrain_rows(source):
    """
    Purpose: Pull the map -> terrain-asset rows out of a client's table.

    Entry:
        source - client source text, comments already stripped.

    Exit/Returns:
        A list of (map_name, asset_key) pairs, or None when the file declares
        no table.

    Module Globals:
        _TERRAIN_TABLE_RE, _TABLE_PAIR_RE read.

    Methodology:
        Both halves are read together. They are checked against different
        sources -- the map modules and the model manifest -- so a failure has
        to be able to name the row it came from rather than the half.

    Notes/References:
        None
    """
    match = _TERRAIN_TABLE_RE.search(source)

    if not match:
        return None

    return _TABLE_PAIR_RE.findall(match.group(1))


def _packed_asset_keys():
    """
    Purpose: Every asset key the build manifest knows how to produce.

    Entry:
        None.

    Exit/Returns:
        A set of asset-key strings.

    Module Globals:
        None.

    Methodology:
        Read from assets/model_manifest.json through pack_model, which CLAUDE.md
        already names as the one file deciding which models exist. NOT from the
        served tree: a key whose .glb has simply not been packed on this
        machine yet is a build state, not a client typo, and failing on it
        would make the check depend on whether someone had run the packer.

    Notes/References:
        assets/ is import-safe by design; see test_model_budgets.py.
    """
    from assets import pack_model

    return {asset_key for _source, asset_key in pack_model.load_manifest()}


def _map_modules():
    """
    Purpose: Import the map modules named above.

    Entry:
        None.

    Exit/Returns:
        A list of imported module objects.

    Module Globals:
        _MAP_MODULE_NAMES read.

    Methodology:
        A plain importlib call per name. The map modules are pure data: they
        build dicts and reference typeclasses by dotted string, so importing
        one touches no database.

    Notes/References:
        Import-safety is why these are named individually rather than globbed.
        See _MAP_MODULE_NAMES.
    """
    from importlib import import_module

    return [import_module(name) for name in _MAP_MODULE_NAMES]


def _server_room_kinds():
    """
    Purpose: Every room kind the server could ever report.

    Entry:
        None.

    Exit/Returns:
        A set of room-kind strings.

    Module Globals:
        _PROTOTYPE_KEY, const read.

    Methodology:
        Read the `key` of every entry in every map module's PROTOTYPES table,
        including the ('*', '*') wildcard, which is the kind for every
        coordinate a map does not override. Add the one kind no map declares:
        ROOM_KIND_TRANSITION, which serializers.room_kind synthesises for a
        node that spawns no room.

        Modules OUTSIDE the manifest are included on purpose. The manifest
        decides which maps are live, but a client may name a map it is being
        built for ahead of activation -- Z_LAYOUT_ORDER names
        "trade town sector 1" today, whose module exists and is not yet in the
        manifest. Checking against the manifest would make that forward
        reference an error, which is exactly backwards: the point of the check
        is to catch a name that matches NOTHING.

    Notes/References:
        serializers.room_kind is the routine whose output this mirrors.
    """
    kinds = {const.ROOM_KIND_TRANSITION}

    for module in _map_modules():
        prototypes = getattr(module, "PROTOTYPES", {})

        for prototype in prototypes.values():
            key = prototype.get(_PROTOTYPE_KEY, "")

            if key:
                kinds.add(key)

    return kinds


def _server_map_names():
    """
    Purpose: Every zcoord a map module declares.

    Entry:
        None.

    Exit/Returns:
        A set of map-name strings.

    Module Globals:
        None

    Methodology:
        Read `zcoord` off every XYMAP_DATA a module exposes through
        XYMAP_DATA_LIST, which is the list the xyzgrid parser itself reads and
        therefore the shape that supports several maps in one module.

    Notes/References:
        Same manifest reasoning as _server_room_kinds: a declared-but-inactive
        map still counts as a real name.
    """
    names = set()

    for module in _map_modules():
        for data in getattr(module, "XYMAP_DATA_LIST", []):
            zcoord = data.get("zcoord", "")

            if zcoord:
                names.add(zcoord)

    return names


def _server_skill_categories():
    """
    Purpose: Every category a registered skill actually declares.

    Entry:
        No conditions.

    Exit/Returns:
        A set of category name strings.

    Module Globals:
        None.

    Methodology:
        Read off the skill classes, which are the one owner of a skill's
        category -- the same relationship _server_room_kinds draws with the map
        modules. Derived rather than listed, so a category introduced with a
        new skill needs no edit here.

    Notes/References:
        The registry walks skill_defs/ at first touch. That package is safe to
        import; blackout/scripts/ is the directory this file must never reach,
        and it does not.
    """
    from systems.progression.skills.registry import SKILL_REGISTRY

    return set(str(cls.category) for cls in SKILL_REGISTRY.values())


# ─── Tests ───────────────────────────────────────────────────────────────────


class ClientSkillCategoryTests(unittest.TestCase):
    """Every skill category a client colours by name must be one that exists."""

    def test_no_client_names_a_category_that_does_not_exist(self):
        """
        A key matching no skill's category is dead configuration: the band it
        was meant to colour is silently drawing the fallback instead, which
        looks like a styling choice rather than a typo. That is exactly how the
        dead "Pole clearing" room kind survived in two clients.

        The reverse is deliberately NOT checked. A category with no entry draws
        the fallback and the grid is complete without it, which is what lets a
        skill added on the server reach the pane with no client edit at all.
        """
        known = _server_skill_categories()

        for path in _SKILL_CATEGORY_SOURCES:
            source = _read_source(path)

            if source is None:
                continue

            match = _SKILL_CATEGORY_TABLE_RE.search(source)

            if match is None:
                continue

            for key in _TABLE_KEY_RE.findall(match.group(1)):
                with self.subTest(client=os.path.basename(path), category=key):
                    self.assertIn(
                        key, known,
                        "'%s' is coloured by %s but no skill declares it. "
                        "Skills it was meant to band are falling through to "
                        "the fallback hue." % (key, os.path.basename(path)))

    def test_a_client_that_is_here_declares_the_table(self):
        """
        The vacuity guard for the check above, in the shape ClientTerrainTile
        Tests uses: that check SKIPS a file whose table it cannot match, so
        renaming SKILL_CATEGORY_COLORS would turn it green while checking
        nothing.

        A client file that is not here at all is still skipped -- the Godot
        client lives on a branch, per the module docstring. What is caught is
        the file being present and the table having moved out of it.
        """
        for path in _SKILL_CATEGORY_SOURCES:
            source = _read_source(path)

            if source is None:
                continue

            with self.subTest(client=os.path.basename(path)):
                self.assertIsNotNone(
                    _SKILL_CATEGORY_TABLE_RE.search(source),
                    "%s exists but declares no SKILL_CATEGORY_COLORS table. "
                    "Either it was renamed or the palette was removed; the "
                    "drift check on it is now inert." % path)



class ClientRoomKindTests(unittest.TestCase):
    """Every room kind a client colours by name must be a kind that exists."""

    def test_no_client_names_a_room_kind_that_does_not_exist(self):
        """
        A key matching no map prototype is dead configuration: the room it was
        meant to colour is silently getting the hash fallback instead.
        """
        known = _server_room_kinds()

        for path in _ROOM_KIND_TABLE_SOURCES:
            source = _read_source(path)

            if source is None:
                continue

            keys = _extract_room_kind_keys(source)

            if keys is None:
                continue

            for key in keys:
                with self.subTest(client=os.path.basename(path), kind=key):
                    self.assertIn(
                        key, known,
                        "'%s' is coloured by %s but no map declares it. "
                        "Rooms it was meant to colour are falling through to "
                        "the hashed hue." % (key, os.path.basename(path)))


class ClientMapOrderTests(unittest.TestCase):
    """Every map a client places by name must be a map that exists."""

    def test_no_client_names_a_map_that_does_not_exist(self):
        """
        A layout-order entry matching no module is a typo that costs nothing
        visible -- the named map simply never matches, and every real map falls
        into arrival order behind it.

        A map that exists but is not in the manifest is NOT an error here; see
        _server_map_names.
        """
        known = _server_map_names()

        for path in _MAP_ORDER_SOURCES:
            source = _read_source(path)

            if source is None:
                continue

            names = _extract_map_order(source)

            if names is None:
                continue

            for name in names:
                with self.subTest(client=os.path.basename(path), map=name):
                    self.assertIn(
                        name, known,
                        "'%s' is placed by %s but no map module declares that "
                        "zcoord." % (name, os.path.basename(path)))


class ClientTerrainTileTests(unittest.TestCase):
    """Every map surfaced with terrain art must name a real map and real art."""

    def _rows(self):
        """Every terrain row every client present declares, with its file."""
        rows = []

        for path in _TERRAIN_TABLE_SOURCES:
            source = _read_source(path)

            if source is None:
                continue

            found = _extract_terrain_rows(source)

            if found is None:
                continue

            for name, asset_key in found:
                rows.append((os.path.basename(path), name, asset_key))

        return rows

    def test_a_client_that_is_here_declares_the_table(self):
        """
        The vacuity guard for the two checks below, in the shape this table
        needs it: both skip a client whose table they cannot match, so renaming
        TILE_MODELS would turn them green while checking nothing.

        A client file that is not here at all is still skipped -- the Godot
        client lives on a branch, per the module docstring.
        """
        for path in _TERRAIN_TABLE_SOURCES:
            source = _read_source(path)

            if source is None:
                continue

            with self.subTest(client=os.path.basename(path)):
                self.assertIsNotNone(
                    _extract_terrain_rows(source),
                    "%s exists but declares no TILE_MODELS table. Either it "
                    "was renamed or the terrain layer was removed; the drift "
                    "checks on it are now inert." % path)

    def test_no_client_surfaces_a_map_that_does_not_exist(self):
        """
        A key matching no map module is dead configuration of the worst kind
        here: the map it meant to surface keeps the plain slab, which is
        exactly what an unnamed map looks like, so nothing about the result
        says the name was wrong.
        """
        known = _server_map_names()

        for client, name, _asset_key in self._rows():
            with self.subTest(client=client, map=name):
                self.assertIn(
                    name, known,
                    "'%s' is surfaced by %s but no map module declares that "
                    "zcoord, so nothing is drawn and nothing says so."
                    % (name, client))

    def test_every_terrain_asset_is_one_the_build_can_produce(self):
        """
        The other half, and it fails the same way round: an asset key with no
        manifest row is never fetched, never 404s, and leaves the slab.

        This is the direction the asymmetry in the module docstring does NOT
        cover, and deliberately. A room kind with no colour entry is fine
        because the fallback is a colour; a map naming art that cannot exist
        has no fallback worth having -- it is simply a line that does nothing.
        """
        known = _packed_asset_keys()

        for client, name, asset_key in self._rows():
            with self.subTest(client=client, asset_key=asset_key):
                self.assertIn(
                    asset_key, known,
                    "%s surfaces '%s' with '%s', which assets/"
                    "model_manifest.json does not build. The map keeps its "
                    "plain slab and nothing reports it."
                    % (client, name, asset_key))


class ClientTableDiscoveryTests(unittest.TestCase):
    """The guard that stops every test above from passing vacuously."""

    def test_at_least_one_client_table_was_found(self):
        """
        Every check in this module skips a client it cannot find. Renaming a
        file, moving the static tree, or breaking the table's spelling would
        therefore turn the whole module green while checking nothing. This is
        the test that fails instead.
        """
        found = []

        for path in _ROOM_KIND_TABLE_SOURCES:
            source = _read_source(path)

            if source is None:
                continue

            if _extract_room_kind_keys(source):
                found.append(path)

        self.assertTrue(
            found,
            "No client declared a ROOM_KIND_COLORS table. Either the clients "
            "moved or the table was renamed; every drift check in this module "
            "is now inert.")


class GeneratedConstantsTests(unittest.TestCase):
    """The committed generated modules must match a fresh render."""

    def _rendered(self, language):
        """Render one language, importing lazily so a broken renderer names itself."""
        from .. import clientexport

        return clientexport.render(language)

    def test_every_language_has_an_output_path(self):
        """
        The renderer is the authority on what can be rendered; the export
        script is the authority on where it goes. A language in one and not the
        other means a client was added and nobody said where its file lives --
        which would otherwise surface as the export script silently doing less
        than it looks like it does.
        """
        from .. import clientexport

        for language in clientexport.languages():
            with self.subTest(language=language):
                self.assertIn(
                    language, _GENERATED_OUTPUTS,
                    "clientexport renders %r but no output path is declared "
                    "for it in scripts/export_client_constants.py."
                    % language)

    def test_committed_files_match_a_fresh_render(self):
        """
        The generated file is committed, because the client has no build step
        of its own for it and must not acquire one just to load a constant.
        That trade only holds if a stale copy fails loudly, which is this
        test.
        """
        for language, path in _GENERATED_OUTPUTS.items():
            with self.subTest(language=language):
                self.assertTrue(
                    os.path.isfile(path),
                    "%s has never been generated. Run:\n"
                    "    python scripts/export_client_constants.py" % path)

                with open(path, "r", encoding="utf-8", newline="") as handle:
                    committed = handle.read()

                self.assertEqual(
                    committed, self._rendered(language),
                    "%s is out of date with systems/statefeed/constants.py. "
                    "Run:\n    python scripts/export_client_constants.py"
                    % os.path.basename(path))
