"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/23/2026
Description: Drift guards for the facts the Godot client retypes.

             A client cannot import Python. Thus, the client code spells out
             some server facts again: which areas, floor types, and skill
             categories exist. Nothing checks the copies, and
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
               - A server fact with NO client entry is FINE. Each table has a
                 documented fallback row, so a new area or floor type needs no
                 client edit. Asserting a census here would fail the moment content is
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

from world import areas as _area_table
from world import floor_types as _floor_table

from .. import clientexport as _clientexport
from .. import constants as const


# ─── Private constant definitions ────────────────────────────────────────────

# The game dir (blackout/), five levels up from
# systems/interface/statefeed/tests/test_client_constants.py.
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

# The repo root, one further up, because the Godot client is a sibling of the
# game dir rather than inside it.
_REPO_ROOT = os.path.dirname(_GAME_DIR)

# Which skill category is drawn in which colour. The Godot pane's only: the
# browser client has no skills screen, and a table one client does not have is
# not drift.
_SKILL_CATEGORY_SOURCES: tuple = (
    os.path.join(_REPO_ROOT, "godot", "world", "skill_palette.gd"),
)

# The fog and the light of each area (DESIGN-0011 section 6.7). Each key
# names a row of world/areas.py, the table that the `areas` layer of a chunk
# file names.
_AREA_LOOK_SOURCES: tuple = (
    os.path.join(_REPO_ROOT, "godot", "world", "area_look.gd"),
)

# The colour of each floor type (DESIGN-0011 section 6.8). Each key names a row
# of world/floor_types.py.
_FLOOR_PALETTE_SOURCES: tuple = (
    os.path.join(_REPO_ROOT, "godot", "world", "terrain", "floor_palette.gd"),
)

# Which whole FAMILY stands in a packed model's place -- tier 2 of the mesh
# ladder, one asset key covering every entity of a family. The corpse family is
# the case it was built for: a corpse's asset key is the key of whichever NPC
# left it, so art aimed at keys would need one model per creature.
#
# Only the VALUE side is checked here, and that is the whole design. The keys
# are generated constants (`_Const.FAMILY_CORPSE`), so a family renamed
# server-side is a GDScript parse error and needs no guard; the asset key is a
# bare string naming a build artefact, and nothing else would ever report it
# wrong.
_FAMILY_MODEL_SOURCES: tuple = (
    os.path.join(_REPO_ROOT, "godot", "world", "meshes", "family_shapes.gd"),
)

# Where each equipment frame sits on the paper doll. The Godot pane's only: the
# browser client had no equipment screen, and a table one client does not have
# is not drift.
_DOLL_LAYOUT_SOURCES: tuple = (
    os.path.join(_REPO_ROOT, "godot", "world", "doll_layout.gd"),
)

# Anchored on `var MODELS` rather than on the bare name, and carrying an
# optional `: Dictionary` annotation: this one is a `static var` because its
# siblings in the same file are (a GDScript `const` may not hold a computed
# value), and an unanchored `MODELS` would also match a `TILE_MODELS` in any
# file this is ever pointed at.
_FAMILY_MODEL_TABLE_RE = re.compile(
    r"var\s+MODELS\s*(?::\s*\w+\s*)?:?=\s*\{(.*?)\}", re.DOTALL)

# The value half of a family row. The KEY is a constant reference rather than a
# quoted string -- `_Const.FAMILY_CORPSE: "corpse_skeleton"` -- so the pair
# regex above cannot read this table and a value-only match is not laziness but
# the shape of the source.
_TABLE_VALUE_RE = re.compile(r':\s*"([^"]+)"')

# The area table. Each row is itself a dictionary, so the match ends at a
# closing brace at the start of a line, for the reason `_DOLL_ROWS_RE` gives.
_AREA_LOOK_TABLE_RE = re.compile(
    r"const\s+LOOKS\s*:?=\s*\{(.*?)^\}", re.DOTALL | re.MULTILINE)

# A row key: one tab of indent, a quoted name, and the opening brace of its row.
# A field inside a row sits at two tabs, so this never reads a field name.
_AREA_LOOK_KEY_RE = re.compile(r'^\t"([^"]+)"\s*:\s*\{', re.MULTILINE)

# The floor palette. A row is one tab of indent, a quoted name, and a Color.
_FLOOR_PALETTE_TABLE_RE = re.compile(
    r"const\s+COLORS\s*:?=\s*\{(.*?)^\}", re.DOTALL | re.MULTILINE)
_FLOOR_PALETTE_KEY_RE = re.compile(r'^\t"([^"]+)"\s*:\s*Color\(', re.MULTILINE)

_SKILL_CATEGORY_TABLE_RE = re.compile(
    r"SKILL_CATEGORY_COLORS\s*:?=\s*\{(.*?)\}", re.DOTALL)

# The doll's rows. Anchored on the CLOSING bracket at the start of a line,
# because every row inside the table is itself a bracketed list: a lazy
# `\[(.*?)\]` stops at the end of the first row and reads one row as the whole
# doll.
_DOLL_ROWS_RE = re.compile(r"ROWS[^=]*=\s*\[(.*?)^\]", re.DOTALL | re.MULTILINE)

# The one frame the doll draws across its whole width, declared beside the
# rows rather than inside them. Checked with them, because it names a wield
# location the same way and fails the same way.
_DOLL_WIDE_SLOT_RE = re.compile(r'WIDE_SLOT\s*:?=\s*"([^"]+)"')

# A double-quoted string that is a table KEY -- followed by a colon. This is
# what keeps `Color("cc6633")` on the GDScript value side out of the key set.
_TABLE_KEY_RE = re.compile(r'"([^"]+)"\s*:')

# Any double-quoted string. Safe for the layout order, which holds only strings.
_QUOTED_RE = re.compile(r'"([^"]+)"')

# A `//` or `#` comment line, stripped before keys are read so a room kind
# named inside a comment is not mistaken for a live entry.
_COMMENT_RE = re.compile(r"(//|#).*$", re.MULTILINE)

# Where each generated client module is written. Read from the renderer rather
# than restated, which is the same rule this whole module exists to enforce.
_GENERATED_OUTPUTS: dict = _clientexport.output_paths()

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


def _extract_area_look_keys(source):
    """
    Purpose: Read the area names out of the fog and light table.

    Entry:
        source - client source text, comments already stripped.

    Exit/Returns:
        A list of area names, or None when the file declares no table.

    Module Globals:
        _AREA_LOOK_TABLE_RE, _AREA_LOOK_KEY_RE read.

    Methodology:
        1. Find the table body.
        2. Read each key at one tab of indent.

    Notes/References:
        DESIGN-0011 section 6.7.

    Author: Nick Hobar
    Creation date: 09/24/2026
    """
    match = _AREA_LOOK_TABLE_RE.search(source)

    if not match:
        return None

    return _AREA_LOOK_KEY_RE.findall(match.group(1))


def _extract_family_model_assets(source):
    """
    Purpose: Pull the asset keys a client's family -> model table names.

    Entry:
        source - client source text, comments already stripped.

    Exit/Returns:
        A list of asset-key strings, or None when the file declares no table.

    Module Globals:
        _FAMILY_MODEL_TABLE_RE, _TABLE_VALUE_RE read.

    Methodology:
        Values only. The key side is a generated constant, which the GDScript
        parser already checks better than any regex could: rename a family
        server-side and the client fails to parse rather than drawing a box.

        Comments have already been stripped by _read_source, which matters more
        for this table than for the others -- its entries carry several lines of
        prose each and the reasoning in them names asset keys.

    Notes/References:
        godot/world/meshes/family_shapes.gd, MODELS.
    """
    match = _FAMILY_MODEL_TABLE_RE.search(source)

    if not match:
        return None

    return _TABLE_VALUE_RE.findall(match.group(1))


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
        Read from the model records in assets/models/, which decide which
        models exist: every record's key and every alias. NOT from the served
        tree: a key whose .glb has not been built on this machine yet is a
        build state, not a client typo. The pipeline check owns that state.

    Notes/References:
        assets/ is import-safe by design; see test_model_budgets.py.
    """
    from assets.pipeline import records

    return {key for record in records.load_all() for key in record.keys}


def _extract_doll_slots(source):
    """
    Purpose: Pull every wield location a client's paper doll places.

    Entry:
        source - client source text, comments already stripped.

    Exit/Returns:
        A list of the slot names in the doll table, in reading order, or None
        when the file declares no table.

    Module Globals:
        _DOLL_ROWS_RE, _QUOTED_RE read.

    Methodology:
        The rows hold nothing but quoted slot names and a GAP constant
        reference, so every quoted string in the table body is a slot.

    Notes/References:
        The wide slot is declared beside the table rather than inside it.
        _extract_wide_slot reads that one, because it is a NAME FOR one of
        these squares and not a square of its own.
    """
    match = _DOLL_ROWS_RE.search(source)

    if not match:
        return None

    return _QUOTED_RE.findall(match.group(1))


def _extract_wide_slot(source):
    """
    Purpose: Pull the slot a client's doll draws across its whole width.

    Entry:
        source - client source text, comments already stripped.

    Exit/Returns:
        The slot name, or None when the file declares no such constant.

    Module Globals:
        _DOLL_WIDE_SLOT_RE read.

    Methodology:
        A single quoted value on its own constant.

    Notes/References:
        None
    """
    match = _DOLL_WIDE_SLOT_RE.search(source)

    if not match:
        return None

    return match.group(1)


def _server_equipment_slots():
    """
    Purpose: Every wield location the server can send a frame for.

    Entry:
        No conditions.

    Exit/Returns:
        A set of slot value strings.

    Module Globals:
        None.

    Methodology:
        Read off WieldLocation, which is the one owner of which slots exist.
        `_serialize_slot_frames` walks SLOT_DISPLAY_ORDER over that same enum,
        so this is the set the client can ever be asked to draw.

    Notes/References:
        None
    """
    from items.equipment.constants import WieldLocation

    return set(str(slot.value) for slot in WieldLocation)


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
    from systems.gameplay.progression.skills.registry import SKILL_REGISTRY

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



class ClientAreaLookTests(unittest.TestCase):
    """Every area that the fog and light table names must be a real area."""

    def test_a_client_that_is_here_declares_the_table(self):
        """
        The vacuity guard. The check below skips a file whose table it cannot
        match. Thus, a renamed LOOKS table or a changed row shape would turn it
        green while it checks nothing.
        """
        for path in _AREA_LOOK_SOURCES:
            source = _read_source(path)

            if source is None:
                continue

            keys = _extract_area_look_keys(source)

            with self.subTest(client=os.path.basename(path)):
                self.assertTrue(
                    keys,
                    "%s exists but no LOOKS row was found. Either the table "
                    "was renamed or a row key is not at one tab of indent. "
                    "The drift check on it is now inert." % path)

    def test_no_client_names_an_area_that_does_not_exist(self):
        """
        A key that names no area is dead configuration. The area that it
        meant to colour gets the fallback fog, and nothing says why.

        An area with no row is fine. It gets the fallback, so new content
        needs no client edit.
        """
        known = _area_table.AREAS

        for path in _AREA_LOOK_SOURCES:
            source = _read_source(path)

            if source is None:
                continue

            for name in _extract_area_look_keys(source) or ():
                with self.subTest(client=os.path.basename(path), area=name):
                    self.assertIn(
                        name, known,
                        "'%s' has a fog and light row in %s, but "
                        "world/areas.py has no such area."
                        % (name, os.path.basename(path)))


class ClientFloorPaletteTests(unittest.TestCase):
    """Every floor type that the floor palette names must be a real one."""

    def _palette_keys(self):
        """Return (client file name, keys) for each palette file here."""
        found = []

        for path in _FLOOR_PALETTE_SOURCES:
            source = _read_source(path)

            if source is None:
                continue

            match = _FLOOR_PALETTE_TABLE_RE.search(source)
            keys = []

            if match:
                keys = _FLOOR_PALETTE_KEY_RE.findall(match.group(1))

            found.append((os.path.basename(path), keys))

        return found

    def test_a_client_that_is_here_declares_the_table(self):
        """
        The vacuity guard. A renamed COLORS table or a changed row shape
        would turn the check below green while it checks nothing.
        """
        for client, keys in self._palette_keys():
            with self.subTest(client=client):
                self.assertTrue(keys, "%s declares no COLORS row" % client)

    def test_no_client_names_a_floor_type_that_does_not_exist(self):
        """
        A key that names no floor type is dead configuration. A floor type
        with no key is fine: it gets a stable hashed colour.
        """
        for client, keys in self._palette_keys():
            for name in keys:
                with self.subTest(client=client, floor=name):
                    self.assertIn(name, _floor_table.FLOOR_TYPES)


class ClientFamilyModelTests(unittest.TestCase):
    """A family standing in a model's place must name art that can exist."""

    def _rows(self):
        """Every family model every client present names, with its file."""
        rows = []

        for path in _FAMILY_MODEL_SOURCES:
            source = _read_source(path)

            if source is None:
                continue

            found = _extract_family_model_assets(source)

            if found is None:
                continue

            for asset_key in found:
                rows.append((os.path.basename(path), asset_key))

        return rows

    def test_a_client_that_is_here_declares_the_table(self):
        """
        The vacuity guard, in the shape this table needs it: the check below
        skips a client whose table it cannot match, so renaming MODELS would
        turn it green while checking nothing.

        A client that declares an EMPTY table still passes -- the table is
        optional and a client with no family art is a legitimate state.
        """
        for path in _FAMILY_MODEL_SOURCES:
            source = _read_source(path)

            if source is None:
                continue

            with self.subTest(client=os.path.basename(path)):
                self.assertIsNotNone(
                    _extract_family_model_assets(source),
                    "%s exists but declares no MODELS table. Either it was "
                    "renamed or family art was removed; the drift check on it "
                    "is now inert." % path)

    def test_every_family_model_is_one_the_build_can_produce(self):
        """
        An asset key with no manifest row is never fetched and never 404s: the
        family silently keeps its procedural shape, which is indistinguishable
        from a family that was never given art at all.

        The same direction the terrain check runs in, and for the same reason
        the module docstring gives for that one. The asymmetry it describes --
        a server fact with no client entry is fine -- still holds on the other
        side: a family with no row here draws its shape, which is the whole
        reason content never waits on art.
        """
        known = _packed_asset_keys()

        for client, asset_key in self._rows():
            with self.subTest(client=client, asset_key=asset_key):
                self.assertIn(
                    asset_key, known,
                    "%s stands a family in for '%s', which assets/"
                    "models/ has no record for. The family keeps its "
                    "procedural shape and nothing reports it."
                    % (client, asset_key))


class ClientDollLayoutTests(unittest.TestCase):
    """Every square on a client's paper doll must be a slot that exists."""

    def test_no_client_places_a_slot_that_does_not_exist(self):
        """
        A square named for no wield location is worse than a dead colour. The
        server never sends a frame for it, so the doll draws a hole the player
        can never fill, and the slot it was meant to be is either missing or
        sitting in the leftover strip.

        The reverse is deliberately NOT checked, which is the asymmetry this
        whole module is built on. A slot no doll places falls into that
        leftover strip, so a wield location added to the enum reaches the pane
        with no client edit at all.
        """
        known = _server_equipment_slots()

        for path in _DOLL_LAYOUT_SOURCES:
            source = _read_source(path)

            if source is None:
                continue

            slots = _extract_doll_slots(source)

            if slots is None:
                continue

            for slot in sorted(set(slots) | {_extract_wide_slot(source)} - {None}):
                with self.subTest(client=os.path.basename(path), slot=slot):
                    self.assertIn(
                        slot, known,
                        "'%s' has a square on %s but no WieldLocation carries "
                        "that value. The doll draws a frame the server can "
                        "never fill." % (slot, os.path.basename(path)))

    def test_no_client_places_one_slot_twice(self):
        """
        One slot in two squares is one frame drawn in two places, and only the
        occupied one would ever show the item. The client's own
        `DollLayout.placed_slots` is what the pane reads to decide what the
        leftover strip holds, so a repeat also hides the strip's real job.
        """
        for path in _DOLL_LAYOUT_SOURCES:
            source = _read_source(path)

            if source is None:
                continue

            slots = _extract_doll_slots(source)

            if slots is None:
                continue

            with self.subTest(client=os.path.basename(path)):
                self.assertEqual(
                    len(slots), len(set(slots)),
                    "%s places a slot in more than one square: %s"
                    % (path, sorted(slots)))

    def test_a_client_that_is_here_declares_the_table(self):
        """
        The vacuity guard for the two checks above, in the shape the terrain
        and skill-category tests use: both SKIP a file whose table they cannot
        match, so renaming ROWS would turn them green while checking nothing.
        """
        for path in _DOLL_LAYOUT_SOURCES:
            source = _read_source(path)

            if source is None:
                continue

            with self.subTest(client=os.path.basename(path)):
                self.assertIsNotNone(
                    _extract_doll_slots(source),
                    "%s exists but declares no ROWS table. Either it was "
                    "renamed or the doll moved out of it; the drift check on "
                    "it is now inert." % path)


    def test_the_wide_slot_is_one_of_the_squares_the_table_places(self):
        """
        The wide slot NAMES one of the doll's own squares -- the row the client
        draws only while that slot is worn. A name matching no row is a row
        that is drawn always and a constant that decides nothing, which is the
        two-hand frame back as a permanent dead square.
        """
        for path in _DOLL_LAYOUT_SOURCES:
            source = _read_source(path)

            if source is None:
                continue

            slots = _extract_doll_slots(source)
            wide = _extract_wide_slot(source)

            if slots is None or wide is None:
                continue

            with self.subTest(client=os.path.basename(path)):
                self.assertIn(
                    wide, slots,
                    "%s draws '%s' across the doll but no row holds it."
                    % (path, wide))


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

        # The area look table since DESIGN-0011 Phase 4b. The room kind table
        # went with the xyzgrid maps.
        for path in _AREA_LOOK_SOURCES:
            source = _read_source(path)

            if source is None:
                continue

            if _extract_area_look_keys(source):
                found.append(path)

        self.assertTrue(
            found,
            "No client declared a LOOKS table. Either the clients moved or "
            "the table was renamed. Every drift check in this module is now "
            "inert.")


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
                    "%s is out of date with systems/interface/statefeed/constants.py. "
                    "Run:\n    python scripts/export_client_constants.py"
                    % os.path.basename(path))
