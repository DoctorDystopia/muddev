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
