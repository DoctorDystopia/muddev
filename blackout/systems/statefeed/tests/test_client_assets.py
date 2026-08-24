"""
GNU License or generic module header.
Author: Nick Hobar
Creation date: 08/23/2026
Description: Guards on what the webclient page is allowed to load, and on the
             module graph it loads it through.

             Companion to test_client_constants.py. That module guards facts
             the client RETYPES; this one guards what the client FETCHES.

             TWO KINDS OF ASSET, and the distinction is the whole structure
             here, because the webclient now loads them by two different
             mechanisms:

               - CLASSIC assets are named by a <script>/<link> tag in
                 base.html. GoldenLayout and favico.js are these, and must
                 stay these: they are Evennia's own dependencies, read as
                 globals by Evennia's own plugins.
               - MODULE assets are reached through the ES module graph rooted
                 at blackout_main.js. Nothing but the entry point is named in
                 the template at all, so "is it mentioned in base.html" is not
                 a question that can be asked of them.

             THE GRAPH WALK. For module assets the check is reachability: parse
             the `import` statements out of blackout_main.js, resolve them, and
             recurse. That is a stronger guard than the tag-spotting it
             replaced -- it catches a typo'd import path, a file moved without
             its importers updated, and a module orphaned by having its last
             importer deleted, none of which a text search for a filename would
             notice.

             It also catches the thing that actually happened while this was
             being written: a rename left blackout_inventory.js importing
             `INVENTORY_INVENTORY_SWAP_TEMPLATE`, which no module exports. That
             was caught by a browser; a graph walk that checks exports catches
             it without one.

             WHY BANNED HOSTS ARE A DENYLIST. jQuery, Bootstrap and popper are
             still fetched from CDNs with SRI hashes, inherited from Evennia's
             stock template; moving them is a separate decision with its own
             testing, and failing the suite for them today would just train
             someone to widen the assertion. What is banned is the two specific
             hosts that were removed for cause, so that removal cannot
             silently regress.
"""

import os
import re
import unittest


# ─── Private constant definitions ────────────────────────────────────────────

# The game dir (blackout/), four levels up from
# systems/statefeed/tests/test_client_assets.py.
_GAME_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

_TEMPLATE = os.path.join(
    _GAME_DIR, "web", "templates", "webclient", "base.html")

_STATIC_WEBCLIENT = os.path.join(_GAME_DIR, "web", "static", "webclient")

_JS_ROOT = os.path.join(_STATIC_WEBCLIENT, "js")

# The ES module the page's one module tag points at.
_ENTRY_POINT = os.path.join(_JS_ROOT, "blackout_main.js")

# host fragment -> why it was removed, quoted back in the failure message so
# whoever hits this does not have to go and find out.
_BANNED_HOSTS: dict = {
    "rawgit.com":
        "RawGit shut down in October 2019 and only works via a redirect. A "
        "failed favico fetch aborts plugin_handler.init() -- which has no "
        "try/catch -- and blanks the whole client. Vendored as "
        "webclient/js/vendor/favico.min.js.",
    "golden-layout.com":
        "Unpinned and un-SRI'd, and GoldenLayout is the layout engine: if it "
        "does not load, the client renders blank rather than degrading. "
        "Vendored as webclient/js/vendor/goldenlayout.min.js.",
}

# Assets loaded by a tag in base.html, and what breaks without each. Paths are
# relative to web/static/webclient/.
_CLASSIC_ASSETS: dict = {
    "js/vendor/goldenlayout.min.js": "the entire layout -- blank page without it",
    "js/vendor/favico.min.js": "plugin init after notifications.js -- blank page",
    "js/plugins/hotkeys.js":
        "WASD/vi movement keys. Stays CLASSIC and must: it has to load before "
        "Evennia's default_in.js, and a module runs after every classic "
        "script by definition, so it could never be early enough",
    "css/vendor/goldenlayout-base.css": "all pane chrome",
    "css/vendor/goldenlayout-dark-theme.css": "the dark theme",
    "js/blackout_main.js": "every Blackout pane -- it is the module entry point",
}

# Assets that must be REACHABLE from the module graph rather than named in the
# template. three.js and its addons arrive through the import map, so the
# template names them only as bare-specifier targets.
_MODULE_ASSETS: tuple = (
    "js/vendor/three/three.module.js",
    "js/vendor/three/addons/loaders/GLTFLoader.js",
    "js/vendor/three/addons/utils/BufferGeometryUtils.js",
    "js/blackout_meshes.js",
    "js/blackout_models.js",
    "js/blackout_channels.js",
    "js/generated/blackout_constants.js",
    "js/plugins/blackout3d.js",
    "js/plugins/blackout_inventory.js",
)

# The bare specifiers the import map defines, and where each resolves to under
# web/static/webclient/. A prefix mapping ends in "/" in both halves, exactly
# as the import-map spec requires.
_IMPORT_MAP: dict = {
    "three": "js/vendor/three/three.module.js",
    "three/addons/": "js/vendor/three/addons/",
}

# `import ... from "spec"` and bare `import "spec"`, single or double quoted.
#
# ANCHORED to the start of a line, and the specifier clause cannot cross a `;`.
# Both matter: an unanchored version matched the word "import" inside the
# comment "Force every material in an import opaque." in blackout_meshes.js and
# then ran its lazy `.*? from` 170 lines down into a `console.warn` string,
# reporting a nonsense specifier. Every real import in this tree is a top-level
# statement at column 0.
_IMPORT_RE = re.compile(
    r"""^import\s+(?:[^;]*?\sfrom\s+)?["']([^"']+)["']""", re.MULTILINE)

# `export const NAME` / `export { A, B }` / `export function NAME`.
_EXPORT_CONST_RE = re.compile(r"^export\s+(?:const|let|var|function|class)\s+(\w+)",
                              re.MULTILINE)
_EXPORT_LIST_RE = re.compile(r"^export\s*\{([^}]*)\}", re.MULTILINE)

# The named bindings of an import statement: the `{ A, B as C }` clause.
_IMPORT_NAMES_RE = re.compile(
    r"""^import\s+\{([^}]*)\}\s+from\s+["']([^"']+)["']""", re.MULTILINE)

# A commented-out block, stripped before hosts are read. A CDN URL sitting
# inside `<!-- ... -->` is not loaded, and the template carries several such
# blocks of disabled stock plugins.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# JavaScript comments, stripped before any "does this file mention X" check.
# The panes explain at length what they no longer do -- blackout3d.js names
# `window.blackoutConstants` in a comment about having stopped reading it --
# and prose describing a removed pattern must not read as the pattern.
_JS_COMMENT_RE = re.compile(r"/\*.*?\*/|//.*?$", re.DOTALL | re.MULTILINE)


# ─── Private helper routines ─────────────────────────────────────────────────

def _live_markup() -> str:
    """
    Purpose: Read base.html with commented-out regions removed.

    Entry:
        None.

    Exit/Returns:
        The template's live markup as text.

    Module Globals:
        _TEMPLATE, _HTML_COMMENT_RE read.

    Methodology:
        Strip HTML comments first. The template disables several stock plugins
        by commenting them out, and one of those blocks names a CDN -- a URL
        the browser never requests should not fail a test about what the page
        loads.

    Notes/References:
        The prose explaining WHY each host was vendored also lives in comments,
        and naming a banned host there is correct rather than a regression;
        stripping comments is what makes that possible.
    """
    with open(_TEMPLATE, "r", encoding="utf-8") as handle:
        markup = handle.read()

    return _HTML_COMMENT_RE.sub("", markup)


def _resolve(specifier: str, importer: str):
    """
    Purpose: Turn one import specifier into an absolute path.

    Entry:
        specifier - what the import statement named.
        importer  - absolute path of the file that named it.

    Exit/Returns:
        The absolute path the specifier resolves to, or None for a specifier
        the import map does not cover and that is not relative.

    Module Globals:
        _IMPORT_MAP, _STATIC_WEBCLIENT read.

    Methodology:
        Relative specifiers resolve against the importer's directory, which is
        what a browser does. Bare specifiers go through the import map: an
        exact key first, then any prefix key ending in "/", longest first --
        the same precedence the import-map spec defines, so that `three` and
        `three/addons/` cannot be matched in the wrong order.

    Notes/References:
        A None result is reported by the caller rather than ignored; a bare
        specifier no map entry covers is a module the browser could not load.
    """
    if specifier.startswith("."):
        return os.path.normpath(
            os.path.join(os.path.dirname(importer), specifier))

    if specifier in _IMPORT_MAP:
        return os.path.join(
            _STATIC_WEBCLIENT, *_IMPORT_MAP[specifier].split("/"))

    for prefix in sorted(_IMPORT_MAP, key=len, reverse=True):
        if prefix.endswith("/") and specifier.startswith(prefix):
            tail = specifier[len(prefix):]
            base = _IMPORT_MAP[prefix]

            return os.path.join(
                _STATIC_WEBCLIENT, *(base.split("/") + tail.split("/")))

    return None


def _walk_graph():
    """
    Purpose: Walk the ES module graph from the entry point.

    Entry:
        None.

    Exit/Returns:
        A tuple (reached, missing, unresolved):
            reached    - set of absolute paths successfully visited.
            missing    - list of (importer, specifier) whose file is absent.
            unresolved - list of (importer, specifier) no import-map entry
                         covers.

    Module Globals:
        _ENTRY_POINT, _IMPORT_RE read.

    Methodology:
        Depth-first from the entry point, reading each file's import
        statements. three.module.js is visited but not parsed for imports: it
        is a 1.2MB vendored bundle with none, and regexing it every run costs
        more than it could ever catch.

    Notes/References:
        Regex rather than a real parser. The imports in this tree are all plain
        static `import` statements at the top of a file; nothing here uses
        dynamic import() or an export-from chain.
    """
    reached, missing, unresolved = set(), [], []
    queue = [_ENTRY_POINT]

    while queue:
        path = queue.pop()

        if path in reached:
            continue

        if not os.path.isfile(path):
            continue

        reached.add(path)

        # The one true leaf; see Methodology.
        if os.path.basename(path) == "three.module.js":
            continue

        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()

        for specifier in _IMPORT_RE.findall(source):
            target = _resolve(specifier, path)

            if target is None:
                unresolved.append((path, specifier))
                continue

            if not os.path.isfile(target):
                missing.append((path, specifier))
                continue

            queue.append(target)

    return reached, missing, unresolved


def _exported_names(path) -> set:
    """
    Purpose: Every name a module exports.

    Entry:
        path - absolute path to a JavaScript module.

    Exit/Returns:
        A set of exported binding names.

    Module Globals:
        _EXPORT_CONST_RE, _EXPORT_LIST_RE read.

    Methodology:
        Covers the two forms this tree uses: `export const NAME` (and
        let/var/function/class) and a trailing `export { A, B }` list.

    Notes/References:
        None
    """
    with open(path, "r", encoding="utf-8") as handle:
        source = handle.read()

    names = set(_EXPORT_CONST_RE.findall(source))

    for group in _EXPORT_LIST_RE.findall(source):
        for piece in group.split(","):
            piece = piece.strip()

            if piece:
                names.add(piece.split()[-1])

    return names


def _relative(path) -> str:
    """Path relative to web/static/webclient/, in forward slashes."""
    return os.path.relpath(path, _STATIC_WEBCLIENT).replace(os.sep, "/")


# ─── Tests ───────────────────────────────────────────────────────────────────

class BannedHostTests(unittest.TestCase):
    """The two hosts removed for cause must not come back."""

    def test_no_banned_host_is_loaded(self):
        """
        A `<script src>` or `<link href>` pointing at either host is a
        regression, not a preference. See _BANNED_HOSTS for the reason each was
        removed; the reason is repeated in the failure message.
        """
        markup = _live_markup()

        for host, reason in _BANNED_HOSTS.items():
            with self.subTest(host=host):
                self.assertNotIn(
                    host, markup,
                    "base.html loads from %s again.\n\n%s" % (host, reason))


class ClassicAssetTests(unittest.TestCase):
    """Assets the page loads with a tag must exist and be named in the tag."""

    def test_required_classic_assets_exist(self):
        for relative, breaks in _CLASSIC_ASSETS.items():
            with self.subTest(asset=relative):
                path = os.path.join(_STATIC_WEBCLIENT, *relative.split("/"))

                self.assertTrue(
                    os.path.isfile(path),
                    "%s is missing. Without it: %s." % (relative, breaks))

    def test_the_template_names_every_classic_asset(self):
        """
        A vendored file nothing loads is dead weight, and -- worse -- means the
        page is getting that dependency from somewhere else, or not at all.
        Checked by basename, because the template reaches them through
        `{% static %}` rather than by literal path.
        """
        markup = _live_markup()

        for relative in _CLASSIC_ASSETS:
            with self.subTest(asset=relative):
                self.assertIn(
                    os.path.basename(relative), markup,
                    "base.html never names %s, so it is not loaded."
                    % relative)

    def test_hotkeys_still_precedes_default_in(self):
        """
        The one ordering constraint the module conversion could NOT absorb.

        hotkeys.js must load before Evennia's default_in.js or keyboard input
        breaks -- and a module script runs after every classic script by
        definition, so converting it would have silently broken movement keys
        while every other pane kept working. It stays classic, and this is what
        stops someone tidying it into blackout_main.js.
        """
        markup = _live_markup()
        hotkeys = markup.find("hotkeys.js")
        default_in = markup.find("default_in.js")

        self.assertNotEqual(hotkeys, -1, "hotkeys.js is not loaded at all")
        self.assertNotEqual(default_in, -1, "default_in.js is not loaded")
        self.assertLess(
            hotkeys, default_in,
            "hotkeys.js must come before default_in.js in base.html, and must "
            "stay a classic script -- a module cannot be early enough.")


class ModuleGraphTests(unittest.TestCase):
    """The ES module graph rooted at blackout_main.js must be whole."""

    def test_the_entry_point_exists(self):
        """
        Everything below walks from here. Its absence would make every other
        check in this class pass over an empty graph.
        """
        self.assertTrue(
            os.path.isfile(_ENTRY_POINT),
            "%s is missing; base.html's module tag points at nothing."
            % _ENTRY_POINT)

    def test_every_import_resolves_to_a_file(self):
        """
        A typo'd path, or a file moved without its importers updated. In a
        browser this is a load error that takes the whole graph down -- so both
        panes vanish, not just the one with the bad import.
        """
        _, missing, unresolved = _walk_graph()

        for importer, specifier in missing:
            with self.subTest(importer=_relative(importer), imports=specifier):
                self.fail(
                    "%s imports '%s', which does not exist."
                    % (_relative(importer), specifier))

        for importer, specifier in unresolved:
            with self.subTest(importer=_relative(importer), imports=specifier):
                self.fail(
                    "%s imports bare specifier '%s', which the import map in "
                    "base.html does not cover. Add it there and to _IMPORT_MAP "
                    "in this test." % (_relative(importer), specifier))

    def test_every_module_asset_is_reachable(self):
        """
        Reachability, not "is it mentioned somewhere". A module nothing imports
        is dead code that looks live, and for three.js and its addons there is
        no tag naming them at all -- they arrive through the import map.
        """
        reached, _, _ = _walk_graph()
        reached_relative = {_relative(p) for p in reached}

        for relative in _MODULE_ASSETS:
            with self.subTest(asset=relative):
                self.assertIn(
                    relative, reached_relative,
                    "%s is not reachable from blackout_main.js. Either nothing "
                    "imports it, or something on the path to it is broken."
                    % relative)

    def test_every_imported_name_is_actually_exported(self):
        """
        The failure this was written for. A rename left
        blackout_inventory.js importing `INVENTORY_INVENTORY_SWAP_TEMPLATE`,
        which no module exports; the browser refused the whole graph and both
        panes disappeared.

        A missing export is a load-time error in a browser, which is a real
        improvement on the `undefined` a missing global used to give -- but it
        takes down every module in the graph, so it is worth catching here.
        """
        reached, _, _ = _walk_graph()

        for path in sorted(reached):
            if os.path.basename(path) == "three.module.js":
                continue

            with open(path, "r", encoding="utf-8") as handle:
                source = handle.read()

            for names, specifier in _IMPORT_NAMES_RE.findall(source):
                target = _resolve(specifier, path)

                if target is None or not os.path.isfile(target):
                    continue

                # three.js's exports are not worth parsing out of a 1.2MB
                # bundle; a wrong name there is a browser error either way.
                if os.path.basename(target) == "three.module.js":
                    continue

                exported = _exported_names(target)

                for piece in names.split(","):
                    piece = piece.strip()

                    if not piece:
                        continue

                    wanted = piece.split()[0]

                    with self.subTest(importer=_relative(path), name=wanted):
                        self.assertIn(
                            wanted, exported,
                            "%s imports '%s' from %s, which does not export "
                            "it." % (_relative(path), wanted,
                                     _relative(target)))

    def test_the_generated_constants_are_reachable(self):
        """
        Generating a file nothing loads is worse than not generating it: the
        panes would keep hand-typed copies and the generated one would agree
        with nothing.

        This used to check that base.html named the file. It no longer does and
        should not -- nothing but the entry point is named there now -- so the
        question became reachability.
        """
        reached, _, _ = _walk_graph()
        reached_relative = {_relative(p) for p in reached}

        self.assertIn(
            "js/generated/blackout_constants.js", reached_relative,
            "Nothing in the module graph imports the generated constants.")


class ImportMapTests(unittest.TestCase):
    """The template's import map must match what this test resolves against."""

    def test_the_template_declares_every_mapped_specifier(self):
        """
        _IMPORT_MAP above is this test's copy of the map in base.html -- the
        exact duplication this whole audit is about, unavoidable because the
        map lives in a Django template. So it is checked rather than trusted.
        """
        markup = _live_markup()

        self.assertIn(
            'type="importmap"', markup,
            "base.html has no import map, so no bare specifier resolves.")

        for specifier, target in _IMPORT_MAP.items():
            with self.subTest(specifier=specifier):
                self.assertIn(
                    '"%s"' % specifier, markup,
                    "The import map does not declare '%s'." % specifier)
                self.assertIn(
                    target.rsplit("/", 1)[-1] or target, markup,
                    "The import map declares '%s' but does not point at %s."
                    % (specifier, target))

    def test_the_import_map_precedes_the_module_tag(self):
        """
        An import map must appear before any module that uses it; a browser
        rejects one added afterwards. Both live in the same template block, so
        this is a one-line mistake away.
        """
        markup = _live_markup()
        import_map = markup.find('type="importmap"')
        module_tag = markup.find('type="module"')

        self.assertNotEqual(module_tag, -1, "no module tag in base.html")
        self.assertLess(
            import_map, module_tag,
            "The import map must come before the module tag that relies on "
            "it, or the browser ignores it and every bare specifier fails.")


class PaneModuleTests(unittest.TestCase):
    """The panes must actually BE modules that use the shared ones."""

    # The panes, and what each must import. Reachability alone does not cover
    # this: a file with no imports at all is trivially "reachable" from
    # blackout_main.js and trivially satisfies "every import resolves".
    #
    # That gap is not hypothetical. A `git checkout --` on blackout_inventory.js
    # reverted it to its pre-module form mid-session -- an IIFE reading globals
    # that no longer exist -- and every check in ModuleGraphTests above still
    # passed. The pane loaded, registered, and silently bound no channel,
    # because `window.blackoutChannels` was gone and its guard returned false.
    # A browser caught it; this is what catches it here.
    _PANES: dict = {
        "js/plugins/blackout3d.js": (
            "../generated/blackout_constants.js",
            "../blackout_meshes.js",
            "../blackout_channels.js",
        ),
        "js/plugins/blackout_inventory.js": (
            "../generated/blackout_constants.js",
            "../blackout_meshes.js",
            "../blackout_channels.js",
        ),
    }

    def _source(self, relative, strip_comments=False):
        path = os.path.join(_STATIC_WEBCLIENT, *relative.split("/"))

        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()

        return _JS_COMMENT_RE.sub("", source) if strip_comments else source

    def test_every_pane_imports_what_it_depends_on(self):
        """
        A pane that stopped importing the shared modules would read them off
        globals that no longer exist -- and the failure is quiet: the pane
        registers, draws, and binds nothing.
        """
        for pane, required in self._PANES.items():
            source = self._source(pane)
            specifiers = set(_IMPORT_RE.findall(source))

            for specifier in required:
                with self.subTest(pane=pane, imports=specifier):
                    self.assertIn(
                        specifier, specifiers,
                        "%s does not import %s. If it went back to reading a "
                        "global, it will register and then silently do "
                        "nothing." % (pane, specifier))

    def test_no_pane_reads_a_blackout_global(self):
        """
        The globals the module conversion removed. Reading one now gets
        `undefined`, which is exactly the silent-failure mode imports were
        adopted to end -- so their absence is asserted rather than assumed.

        `window.Evennia`, `window.plugins` and `window.plugin_handler` are NOT
        here on purpose: those are Evennia's own classic globals, there is
        nothing to import them from, and reading them off `window` is correct.
        """
        banned = ("window.blackoutConstants", "window.blackoutMeshes",
                  "window.blackoutChannels", "window.THREE")

        for pane in self._PANES:
            source = self._source(pane, strip_comments=True)

            for name in banned:
                with self.subTest(pane=pane, reads=name):
                    self.assertNotIn(
                        name, source,
                        "%s reads %s, which no longer exists. Import it "
                        "instead." % (pane, name))


class TemplateRenderTests(unittest.TestCase):
    """base.html must actually compile and render.

    Every other check in this module reads the template as TEXT. That is right
    for what they ask -- which hosts are named, in what order -- but it means
    none of them would notice the template being unparseable, and an
    unparseable template is a 500 on the whole webclient rather than a
    degraded pane.

    It is not hypothetical. A prose comment added during the module conversion
    wrote the `static` tag's name in braces, as an example, inside an HTML
    comment:

        ... and {% templatetag openblock %} static {% templatetag closeblock %}
        is used so the paths follow STATIC_URL ...

    Django compiles template tags REGARDLESS of HTML comments -- the comment is
    stripped by the browser, long after the engine has parsed the file -- so a
    tag with no argument raised TemplateSyntaxError and the page 500'd. The
    text-based checks all passed, because the text was exactly what they
    expected it to be.
    """

    def test_the_webclient_template_renders(self):
        from django.template.loader import render_to_string

        html = render_to_string("webclient/webclient.html", {
            "game_name": "Blackout",
            "websocket_enabled": True,
            "websocket_port": 4002,
        })

        self.assertIn("importmap", html)
        self.assertIn('type="module"', html)

    def test_the_rendered_import_map_points_at_real_files(self):
        """
        The map is JSON built by template tags, so a mistake in it renders
        cleanly and fails only in the browser. Parse what the tags actually
        produced and check each target exists on disk.
        """
        import json

        from django.conf import settings
        from django.template.loader import render_to_string

        html = render_to_string("webclient/webclient.html", {
            "game_name": "Blackout",
            "websocket_enabled": True,
            "websocket_port": 4002,
        })

        match = re.search(
            r'<script type="importmap">(.*?)</script>', html, re.DOTALL)

        self.assertIsNotNone(match, "no import map in the rendered page")

        imports = json.loads(match.group(1))["imports"]
        static_url = settings.STATIC_URL

        for specifier, url in imports.items():
            with self.subTest(specifier=specifier):
                self.assertTrue(
                    url.startswith(static_url),
                    "'%s' maps to %s, which is not under STATIC_URL (%s)."
                    % (specifier, url, static_url))

                relative = url[len(static_url):].rstrip("/")
                path = os.path.join(
                    _GAME_DIR, "web", "static", *relative.split("/"))
                exists = os.path.isfile(path) or os.path.isdir(path)

                self.assertTrue(
                    exists,
                    "The import map sends '%s' to %s, which does not exist "
                    "at %s." % (specifier, url, path))
