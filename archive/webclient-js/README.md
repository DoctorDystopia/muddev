# Archive: the three.js/GoldenLayout webclient

**Retired permanently on 2026-09-03.** Superseded by the Godot client in
[`godot/`](../../godot/README.md), which is now the sole canonical Blackout
client on every platform, including the public website.

This directory is outside `blackout/` on purpose: nothing under `blackout/`
may import, template-load, or serve anything in here, so the archive cannot
be accidentally revived by a stray path reference. It exists purely for
grep-and-read reference.

## What's here

- `js/` — the ES-module webclient (`blackout_main.js` entry point, the 3D
  world and inventory panes, mesh/model resolvers, vendored three.js r159 and
  GoldenLayout).
- `css/` — vendored GoldenLayout stylesheets.
- `templates-webclient/` — the Django templates (`base.html`, `webclient.html`)
  that used to render `/webclient/`.
- `jstests/` — the `node --test` harness that covered `js/`.

## What's NOT here

`blackout/web/static/webclient/models/` (the `.glb` asset tree) was **not**
moved. It's shared infrastructure the Godot client and the deploy pipeline
both still depend on — see `deploy/webexport/README.md` and
`deploy/webexport/publish.sh`.

## Full history

Every file here has its complete commit history preserved through the
`git mv` that created this directory. The state of the repo immediately
before this retirement is also tagged:

```bash
git show archive/webclient-js:blackout/web/static/webclient/js/blackout_main.js
```

## Background

- `docs/old/2026-08-23-ENG-0004-webclient-architecture.md` — full
  architecture audit of what's archived here.
- `docs/old/2026-08-25-ENG-0005-godot-vs-webclient.md` — the decision record
  for replacing this client with Godot.
- `docs/old/2026-08-25-ENG-0006-godot-option-a-plan.md` — the implementation
  plan; §8 is the retirement checklist this archival follows.
