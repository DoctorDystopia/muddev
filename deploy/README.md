# Deploying Blackout — start here

This is the one file that ties the other three together. Each of them owns
one layer and none of them tells you which layers a given change touches:

| Doc | Owns |
|---|---|
| [`blackout/README.md`](../blackout/README.md) | Server operations — reload/reboot, map rebuild, tests |
| [`deploy/cloudflared/README.md`](cloudflared/README.md) | The tunnel that makes `game.playblackout.io` reachable |
| [`deploy/webexport/README.md`](webexport/README.md) | Building and publishing the Godot client |
| [`docs/old/2026-08-21-INFRA-0001-public-hosting.md`](../docs/old/2026-08-21-INFRA-0001-public-hosting.md) | Why the architecture is shaped this way |

**The mental model that makes the table below make sense:** this machine *is*
production for the game server. There is no push/build/upload step for
Python — `cloudflared` tunnels straight into whatever is running and being
served from disk on this box. The Godot client is the one genuine exception:
it is a ~38 MiB binary that cannot live on Evennia's
webserver or as a Cloudflare static asset (25 MiB cap either way), so it alone
has a real build → publish → deploy pipeline into R2 and a Worker in the
sibling `playblackout-site` repo.

That asymmetry is the whole reason "deploy" doesn't mean one thing here.

## What did you touch?

| Changed | Do this |
|---|---|
| Game logic (`systems/`, `typeclasses/`, `commands/`, `items/`, `world/*.py` other than maps) | `evennia reload` from `blackout/` |
| A `server/conf/*.py` module named in `PORTAL_SERVICES_PLUGIN_MODULES` (e.g. `godot_websocket.py`) | `evennia reboot`, not `reload` — Portal plugins are only read at Portal start, and `reload` restarts the Server process only |
| Maps (`world/maps/*.py`, `scripts/map_manifest.json`) | `scripts/clean_and_reload_all_maps.ps1` / `.sh` — stops Evennia, syncs the grid, spawns, reloads, all in one |
| `systems/statefeed/constants.py` | Regenerate the generated client file **before** anything else touches it — see below |
| Godot client (`godot/**`) | The full export → publish → deploy pipeline — see below |
| `deploy/cloudflared/config.yml` | Manual, rare, needs an elevated shell — copy to `C:\ProgramData\cloudflared\`, substitute the tunnel id, `Restart-Service Cloudflared`. Not part of routine deploys; see the cloudflared README |
| Django templates / non-plugin settings (`web/templates/`, most of `server/conf/settings.py`) | `evennia reload` |

## Regenerating client constants

Anything that adds, renames, or removes a name in `systems/statefeed/constants.py`
has to be re-rendered before the client can be trusted:

```bash
python scripts/export_client_constants.py
```

This writes `godot/autoload/blackout_constants.gd` from the one Python
source. It's committed — the client has no build step of its own for it and
must not acquire one just to load a constant, so the committed copy is the
artifact it actually reads.

```bash
python scripts/export_client_constants.py --check
```

writes nothing and exits non-zero if a committed copy is stale — this is what
the test suite runs, and what a deploy script should run first so it fails
loud rather than shipping a Godot export with a stale `.gd` baked into it.

**Order matters:** regenerate *before* exporting the Godot client. The `.gd`
file is compiled into the binary at export time — export first and the fix
never leaves this machine.

## The Godot client pipeline

Three steps, always in this order, spelled out in full in
[`deploy/webexport/README.md`](webexport/README.md):

```bash
# 1. Export (release, not debug — debug dials localhost, not production)
"/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe" \
    --headless --path godot --export-release "Web" deploy/webexport/build/index.html

# 2. Publish the client build AND the model/art tree to R2 (they must land together —
#    the client fetches art at runtime and falls back to family-shape geometry
#    on anything the manifest doesn't have)
./deploy/webexport/publish.sh          # --dry-run lists the keys first, uploads nothing

# 3. Deploy the site so the worker actually routes the new R2 keys
cd ../playblackout-site && npx wrangler deploy
```

**Publish before deploy, always.** A publish with no deploy leaves the old
client live; a deploy with no publish 404s `/play`.

## The full pipeline, in order

Everything above, laid out as one sequence. `full_deploy.sh` in this
directory runs exactly this, in this order:

```bash
./deploy/full_deploy.sh              # constants -> reload -> Godot export/publish/deploy -> verify
./deploy/full_deploy.sh --maps       # ... with a map rebuild instead of a plain reload
./deploy/full_deploy.sh --reboot     # ... evennia reboot instead of reload
./deploy/full_deploy.sh --skip-godot # server-only, no Godot leg
./deploy/full_deploy.sh --dry-run    # print every command instead of running it
```

Later steps are safe to run even when only part of this applies; treat each
as a no-op if its inputs didn't change.

1. `python scripts/export_client_constants.py --check` — fail fast if the
   generated client files are stale before anything else runs.
2. If `world/maps/**` or `scripts/map_manifest.json` changed:
   `scripts/clean_and_reload_all_maps.ps1` / `.sh` (this already stops and
   reloads Evennia itself — skip step 3 if this ran).

   Safe to run unattended as of 08/28/2026. The spawn used to be a separate
   `evennia xyzgrid spawn` step, which asks for confirmation on stdin and
   offers no way to decline the question — so `full_deploy.sh --maps` would
   hang on a terminal and raise `EOFError` without one. It now happens inside
   `map_sync.py`, whose exit code the wrapper actually checks.
3. Otherwise, reload the game server:
   `evennia reload` from `blackout/` — or `evennia reboot` if a
   `PORTAL_SERVICES_PLUGIN_MODULES` entry changed. `reboot` restarts the
   Portal too, so expect a brief player disconnect that `reload` doesn't
   cause.
4. If `godot/**` changed, or step 1 regenerated `blackout_constants.gd`:
   export → `publish.sh` → `wrangler deploy`, in that order (see above).
5. Verify (below).

## Verifying it actually landed

```bash
curl -sS -o /dev/null -w "%{http_code}\n" https://game.playblackout.io/
```

`200` is good. `530`/`error code: 1033` means the tunnel is down, not
Evennia. `502` means the tunnel is up and Evennia is not — check
`evennia start` ran. Full detail in
[`deploy/cloudflared/README.md`](cloudflared/README.md).

For the Godot client, `deploy/webexport/publish.sh` (no `--dry-run`) prints
every key it wrote; a `curl` against
`https://playblackout.io/client/index.wasm` confirms the worker is actually
serving the new build rather than a stale cached one.

## What's deliberately left out of any deploy script

- **`deploy/cloudflared/config.yml` changes.** Rare, needs an elevated shell,
  and a broken tunnel config takes the whole site down silently in the
  background. Do this by hand, per the cloudflared README, and confirm `UDP=4`
  and a `200` afterward before walking away.
- **Anything under `blackout/scripts/` other than `export_client_constants.py`
  and the map rebuild scripts.** That directory acts on the live database —
  see the warning in `CLAUDE.md` — and nothing in it should be added to an
  automated pipeline without the same scrutiny `map_sync.py` already gets.
