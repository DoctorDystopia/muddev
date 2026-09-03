# JavaScript tests

Run from this directory:

```bash
node --import ./register.mjs --test
```

**No dependencies, no `package.json`, no `node_modules`.** `node --test` is
built in, and `register.mjs` installs a resolver hook that does for Node what
the `<script type="importmap">` in `base.html` does for the browser. That is
the whole toolchain, and keeping it at zero cost is the reason these tests
exist at all rather than being planned and never written.

## What belongs here

**Pure logic, reachable without a browser.** `tileAction` is the model case: a
tile in, an action or null out, reading only feed state the module has already
recorded. No DOM, no canvas, no WebGL.

**Not** rendering, layout, or input. A headless browser would be needed for
those, and the cost is high for a pane that is by design non-essential — if it
is closed or broken, nothing about play changes. See
`docs/old/2026-08-23-ENG-0004-webclient-architecture.md`, §4.6.

**Not** anything the server decides. The rules about which tile affords what
live in `systems/statefeed/serializers.py` and are tested in
`systems/statefeed/tests/test_tile_actions.py`. These tests cover only that the
CLIENT reads the server's answer correctly — the two halves of one contract,
tested on the side that owns each half.

## Loading a pane

A pane is an ES module that registers itself with `window.plugin_handler` as it
evaluates, and reads `window.Evennia` when binding channels. Node has neither,
so stub the globals **before** importing the pane — a static `import` is hoisted
above any assignment in the file body, so the pane would evaluate first and
throw on `window` being undefined. Use `await import(...)` after the stubs.

`tileaction.test.mjs` shows the pattern.

## Why not ESLint

There is no linter here yet, deliberately, and the gap is narrower than it
looks. The `no-undef` class of mistake that actually bit this layer was
**cross-module** — a rename left a pane importing a symbol no module exported —
and that is already caught, with no dependencies, by the import-graph walk in
`systems/statefeed/tests/test_client_assets.py`, which resolves every import
and checks every named binding against the target's exports.

What a linter would add on top is within-file coverage: a typo'd local, an
unused variable, a shadowed name. Real, but it costs an `npm install` and a
`node_modules` in a repo that otherwise has no JavaScript toolchain. Worth
doing deliberately, not by accident.
