# Deploying Blackout — start here

This is the one file that connects the other three docs. Each of them owns one
layer, and none of them tells you which layers a given change affects:

| Doc | Owns |
|---|---|
| [`blackout/README.md`](../blackout/README.md) | Server operations — reload/reboot, the tile sync, tests |
| [`deploy/cloudflared/README.md`](cloudflared/README.md) | The tunnel that makes `game.playblackout.io` reachable |
| [`deploy/webexport/README.md`](webexport/README.md) | Building and publishing the Godot client |
| [`docs/old/2026-08-21-INFRA-0001-public-hosting.md`](../docs/old/2026-08-21-INFRA-0001-public-hosting.md) | Why the architecture is shaped this way |

**The mental model behind the table below:** this machine *is* production for
the game server. Python has no push, build, or upload step. `cloudflared`
tunnels straight into whatever runs and serves from disk on this box.

The Godot client is the one real exception. It is a ~38 MiB binary that cannot
live on Evennia's webserver or as a Cloudflare static asset (25 MiB cap either
way). Thus, only the client has a real build → publish → deploy pipeline into
R2 and a Worker in the sibling `playblackout-site` repo.

That asymmetry is the whole reason that "deploy" does not mean one thing here.

## What did you touch?

`diff_deploy.sh` reads this table for you. It finds the changed rows and runs
only their legs. Refer to "Deploy only what changed" below.

| Changed | Do this |
|---|---|
| Game logic (`systems/`, `typeclasses/`, `commands/`, `items/`, `world/*.py`) | `evennia reload` from `blackout/` |
| A `server/conf/*.py` module named in `PORTAL_SERVICES_PLUGIN_MODULES` (e.g. `godot_websocket.py`) | `evennia reboot`, not `reload` — Portal plugins are only read at Portal start, and `reload` restarts the Server process only |
| Chunk files (`world/chunks/*.json`) | `full_deploy.sh --tiles`: it stops Evennia, runs `scripts/sync_tile_objects.py --apply`, and starts Evennia |
| `systems/interface/statefeed/constants.py` | Regenerate the generated client file **before** anything else touches it — see below |
| Godot client (`godot/**`) | The full export → publish → deploy pipeline — see below |
| `deploy/cloudflared/config.yml` | Manual, rare, needs an elevated shell — copy to `C:\ProgramData\cloudflared\`, substitute the tunnel id, `Restart-Service Cloudflared`. Not part of routine deploys; see the cloudflared README |
| Django templates / non-plugin settings (`web/templates/`, most of `server/conf/settings.py`) | `evennia reload` |

## Regenerating client constants

If a change adds, renames, or removes a name in
`systems/interface/statefeed/constants.py`, render the client file again before
you trust the client:

```bash
python scripts/export_client_constants.py
```

This command writes `godot/autoload/blackout_constants.gd` from the one Python
source. The file is committed. The client has no build step of its own for it,
and must not get one only to load a constant. Thus, the committed copy is the
artifact that the client actually reads.

```bash
python scripts/export_client_constants.py --check
```

writes nothing, and exits non-zero if a committed copy is stale. The test suite
runs this check. A deploy script must run it first, so that the script fails
loudly and does not ship a Godot export with a stale `.gd` inside it.

**Order matters:** regenerate *before* you export the Godot client. The export
compiles the `.gd` file into the binary. If you export first, the fix never
leaves this machine.

## The Godot client pipeline

The pipeline has three steps, always in this order.
[`deploy/webexport/README.md`](webexport/README.md) gives them in full:

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

**Always publish before you deploy.** A publish with no deploy leaves the old
client live. A deploy with no publish 404s `/play`.

## The full pipeline, in order

This section gives everything above as one sequence. `full_deploy.sh` in this
directory runs exactly this sequence, in this order:

```bash
./deploy/full_deploy.sh              # constants -> reload -> Godot export/publish/deploy -> verify
./deploy/full_deploy.sh --tiles      # ... with a tile sync instead of a plain reload
./deploy/full_deploy.sh --reboot     # ... evennia reboot instead of reload
./deploy/full_deploy.sh --skip-godot # server-only, no Godot leg
./deploy/full_deploy.sh --dry-run    # print every command instead of running it
```

Later steps are safe to run even when only part of this sequence applies. If
the inputs of a step did not change, treat the step as a no-op.

1. Run `python scripts/export_client_constants.py --check`. It fails fast if
   the generated client files are stale, before anything else runs.
2. If `world/chunks/**` changed, stop Evennia, run
   `scripts/sync_tile_objects.py --apply` from `blackout/`, and start Evennia.
   `full_deploy.sh --tiles` does all three. If it ran, skip step 3.

   The sync needs the server down, because the server keeps the tile room
   index in memory. Without `--apply`, the sync only prints its plan, and
   `full_deploy.sh --tiles --dry-run` does that. The xyzgrid map rebuild that
   stood here went to `archive/xyzgrid-maps/` on 09/25/2026.
3. Otherwise, reload the game server with `evennia reload` from `blackout/`.
   If a `PORTAL_SERVICES_PLUGIN_MODULES` entry changed, use `evennia reboot`
   instead. `reboot` also restarts the Portal, so expect a brief player
   disconnect that `reload` does not cause.
4. If `godot/**` changed, or step 1 regenerated `blackout_constants.gd`, run
   export → `publish.sh` → `wrangler deploy`, in that order (see above).
5. Verify the deploy (below).

## Deploy only what changed

`diff_deploy.sh` runs the same sequence as `full_deploy.sh`, with the same
flags. But a leg runs only when its inputs changed since its last successful
run:

```bash
./deploy/diff_deploy.sh              # each changed leg, then verify
./deploy/diff_deploy.sh --dry-run    # print the plan of each leg. Change nothing
./deploy/diff_deploy.sh --tiles      # also run the tile sync with no chunk change
./deploy/diff_deploy.sh --reboot     # also reboot with no Portal plugin change
./deploy/diff_deploy.sh --skip-godot # server legs only
./deploy/diff_deploy.sh --baseline   # write the deploy records, deploy nothing
```

| Leg | Inputs | Runs when |
|---|---|---|
| Constants | `statefeed/constants.py` | Always. The check is cheap |
| Tile sync | `world/chunks/*.json` | A chunk file is different from the tile sync stamp |
| Reboot | The Portal plugin modules, and each `server.conf` module that they import | One of them changed |
| Reload | The other server code under `blackout/` | It changed |
| Godot export | `godot/`, minus the `exclude_filter` of the Web preset | It changed, or `webexport/build/` has no export |
| R2 publish | The export and the model tree | Always. `publish.sh --changed-only` uploads only the files that changed |
| Site deploy | `worker/`, `wrangler.jsonc`, and `dist/` of `playblackout-site` | One of them changed |

The script prints each changed file before a leg starts. A tile sync stops
and starts Evennia, so it also does the work of a reboot and a reload. A
reboot also does the work of a reload.

**Three facts that the script reads, and does not copy:**

- The tile sync stamp decides the tile sync. `syncstamp.changed_files` gives
  the result, so the digest rule keeps one owner. The tile sync writes the
  stamp. Thus, the tile sync needs no deploy record.
- `settings.PORTAL_SERVICES_PLUGIN_MODULES` gives the Portal plugin list. The
  script follows each `server.conf` import of a plugin. On 10/05/2026, the
  list was `godot_websocket.py`, `websocket.py`, `bbcode.py`, and
  `portal_services_plugins.py`.
- `godot/export_presets.cfg` gives the files that the export leaves out. A
  change to the terrain editor addon thus starts no export.

**The site deploy is not tied to the publish.** The worker reads each R2
object on each request, and it has no edge cache. Thus, a new R2 object needs
no `wrangler deploy`. Only a change to the worker, to `wrangler.jsonc`, or to
`dist/` needs one. Neither script runs `astro build`. Build `dist/` in the
site repo before a deploy.

### The records

The deploy records and the publish record are in `deploy/.deploy_state/`, and
git ignores that directory. They describe what this machine last deployed,
not the repo.

- **A deploy record** is the input list of one leg: one `sha256 *path` line
  for each file. Two lists that differ name the changed files.
- **The publish record** gives the SHA-256 of each R2 key at its last upload.
  `publish.sh` writes it after each upload, also in a full deploy. Thus, a
  diff deploy after a full deploy uploads nothing.

A leg writes its deploy record only after it succeeds. Thus, a leg that fails
runs again on the next diff deploy. A dry run writes no record.

**With no record, a leg counts every input as changed.** The first diff
deploy on a machine is a full deploy, and it uploads all 45 MiB. To prevent
that, do these steps one time:

1. Run `./deploy/full_deploy.sh`. It writes the publish record.
2. Run `./deploy/diff_deploy.sh --baseline`. It writes the deploy records of
   the server, the Godot client, and the site.

If a different machine or a manual `wrangler r2 object put` writes the bucket,
the publish record is wrong. Delete `deploy/.deploy_state/r2_<bucket>.tsv`.
The next publish then uploads every file.

`publish.sh` never deletes an R2 object. It lists each key in the publish
record that has no local file, and it leaves that key in the bucket. A player
with an old client open can still ask for the old art.

## Verifying it actually landed

```bash
curl -sS -o /dev/null -w "%{http_code}\n" https://game.playblackout.io/
```

`200` is good. `530`/`error code: 1033` means that the tunnel is down, not
Evennia. `502` means that the tunnel is up and Evennia is not. Make sure that
`evennia start` ran. For full detail, refer to
[`deploy/cloudflared/README.md`](cloudflared/README.md).

For the Godot client, `deploy/webexport/publish.sh` (with no `--dry-run`)
prints every key that it wrote. A `curl` against
`https://playblackout.io/client/index.wasm` confirms that the worker serves the
new build, not a stale cached one.

## What's deliberately left out of any deploy script

- **`deploy/cloudflared/config.yml` changes.** They are rare and need an
  elevated shell. A broken tunnel config silently stops the whole site in the
  background. Make this change by hand, as the cloudflared README tells you.
  Before you leave, make sure that you see `UDP=4` and a `200`.
- **Anything under `blackout/scripts/` other than `export_client_constants.py`
  and `sync_tile_objects.py`.** That directory acts on the live database (see
  the warning in `CLAUDE.md`). Do not add anything from it to an automated
  pipeline without the same scrutiny that the tile sync gets. The cutover
  (`move_to_tile_world.py`) is a one-time operator step and stays out.
