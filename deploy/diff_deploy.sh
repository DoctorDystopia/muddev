#!/usr/bin/env bash
#
# deploy/diff_deploy.sh -- the pipeline of full_deploy.sh, but each leg runs
# only when its inputs changed since the last deploy.
#
# Each leg compares its inputs with a record in deploy/.deploy_state/ (git
# ignores it). A leg writes its record only after it succeeds. Thus, a failed
# leg runs again on the next deploy.
#
#   Leg           Inputs                                 Runs when
#   constants     statefeed/constants.py                 always (the check is cheap)
#   tile sync     world/chunks/*.json                    a chunk file differs from
#                                                         the tile sync stamp
#   reboot        the Portal plugins and their           one of them changed
#                 server.conf imports
#   reload        the other server code in blackout/     it changed
#   Godot export  godot/, minus the exclude_filter of    it changed, or no build
#                 the Web preset                          exists
#   R2 publish    the export + the model tree            always, and publish.sh
#                                                         uploads only changed files
#   site deploy   worker/, wrangler.jsonc, dist/ of      it changed
#                 playblackout-site
#
# The tile sync stops Evennia, and it demolishes the contents of each changed
# tile. The script prints the changed chunk files before it starts.
#
# Read deploy/README.md before changing this.
#
# Usage:
#   deploy/diff_deploy.sh [--tiles] [--reboot] [--skip-godot] [--dry-run] [--baseline]
#
#   --tiles       run the tile sync, also with no chunk change
#   --reboot      evennia reboot, also with no Portal plugin change
#   --skip-godot  skip the export, the publish, and the site deploy
#   --dry-run     print the plan of each leg. Change nothing, write no record
#   --baseline    record the current server, Godot, and site inputs as
#                  deployed, and do nothing else. Run it one time, right after
#                  a full_deploy.sh. The R2 record and the tile sync stamp
#                  need no baseline: publish.sh and the sync write them

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
SITE_DIR="$( cd "$REPO_ROOT/../playblackout-site" 2>/dev/null && pwd )" || SITE_DIR=""
STATE_DIR="$SCRIPT_DIR/.deploy_state"
BUILD_DIR="$SCRIPT_DIR/webexport/build"

PYTHON="$REPO_ROOT/evenv/Scripts/python.exe"
EVENNIA="$REPO_ROOT/evenv/Scripts/evennia.exe"
GODOT_BIN="${GODOT_BIN:-/c/Users/NickR/Downloads/Godot_v4.7.1-stable_win64.exe/Godot_v4.7.1-stable_win64_console.exe}"

# The server leg ignores these. Each one has its own leg or needs no deploy.
SERVER_EXCLUDES=(
    ":(exclude)blackout/world/chunks"
    ":(exclude)blackout/assets"
    ":(exclude)blackout/web/static/webclient/models"
    ":(exclude)blackout/scripts"
    ":(exclude)blackout/analysis"
    ":(exclude)blackout/profiling"
    ":(exclude)*/tests/*"
    ":(exclude)*.md"
)

FORCE_TILES=0
FORCE_REBOOT=0
DO_GODOT=1
DRY_RUN=0
BASELINE=0

while [ "$#" -gt 0 ]; do
    case "$1" in
        --tiles)      FORCE_TILES=1 ;;
        --reboot)     FORCE_REBOOT=1 ;;
        --skip-godot) DO_GODOT=0 ;;
        --dry-run)    DRY_RUN=1 ;;
        --baseline)   BASELINE=1 ;;
        -h|--help)
            awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"
            exit 0 ;;
        *) echo "Unknown argument: $1" >&2
           echo "Usage: diff_deploy.sh [--tiles] [--reboot] [--skip-godot] [--dry-run] [--baseline]" >&2
           exit 2 ;;
    esac
    shift
done

NOW_DIR="$( mktemp -d )"
trap 'rm -rf "$NOW_DIR"' EXIT

run() {
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "[dry-run] $*"
    else
        echo "+ $*"
        "$@"
    fi
}

step() { echo; echo "=== $* ==="; }

# --- Input lists ---------------------------------------------------------------
# A list is one "sha256 *path" line for each file, in path order. A record is
# the list of the last deploy. Two lists that differ name the changed files.

# Hash the files that git lists for the pathspecs, tracked and untracked.
# A tracked file that is gone from the disk drops out of the list.
hash_git_files() {
    ( cd "$REPO_ROOT" \
        && git ls-files -co --exclude-standard -z -- "$@" \
        | xargs -0 -r sha256sum 2>/dev/null ) | sort -k 2 || true
}

# The Portal plugin modules from the settings, and each server.conf module
# that they import, at any depth. `evennia reload` restarts only the Server
# process, so a change here needs `evennia reboot`.
portal_files() {
    ( cd "$REPO_ROOT/blackout" && "$PYTHON" - ) <<'PY'
import ast, os, sys
sys.path.insert(0, ".")
from server.conf import settings
seen, queue = set(), list(settings.PORTAL_SERVICES_PLUGIN_MODULES)
while queue:
    module = queue.pop()
    path = module.replace(".", "/") + ".py"
    if module in seen or not os.path.isfile(path):
        continue
    seen.add(module)
    print("blackout/" + path)
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("server.conf"):
            queue.append(node.module)
        elif isinstance(node, ast.Import):
            queue += [a.name for a in node.names if a.name.startswith("server.conf")]
PY
}

# The exclude_filter of the Web export preset, as git pathspecs. The export
# leaves those files out, so a change to them needs no export.
godot_excludes() {
    awk '/^\[preset\.[0-9]+\]$/ { web = 0 }
         /^name="Web"$/         { web = 1 }
         web && /^exclude_filter=/ {
             sub(/^exclude_filter="/, ""); sub(/"$/, "")
             n = split($0, parts, ",")
             for (i = 1; i <= n; i++) if (parts[i] != "") print ":(exclude)godot/" parts[i]
         }' "$REPO_ROOT/godot/export_presets.cfg"
}

site_list() {
    ( cd "$SITE_DIR" \
        && find worker dist wrangler.jsonc -type f -print0 2>/dev/null \
        | sort -z | xargs -0 -r sha256sum ) || true
}

# Print each changed path of a leg. Return 0 if the leg has a change.
leg_changed() {
    local record="$STATE_DIR/$1.list"
    local now="$NOW_DIR/$1.list"

    if [ ! -f "$record" ]; then
        echo "  no record of an earlier deploy -- every input counts as changed"
        return 0
    fi
    if cmp -s "$record" "$now"; then
        return 1
    fi
    { diff "$record" "$now" || true; } \
        | sed -n 's/^[<>] [0-9a-f]\{64\} [ *]//p' | sort -u | sed 's/^/  changed: /'
    return 0
}

write_record() {
    if [ "$DRY_RUN" -eq 0 ]; then
        mkdir -p "$STATE_DIR"
        cp "$NOW_DIR/$1.list" "$STATE_DIR/$1.list"
    fi
}

# Print each chunk file that differs from the tile sync stamp. Return 0 if
# one differs. syncstamp.py owns the digest rule, so this reads it.
chunks_changed() {
    ( cd "$REPO_ROOT/blackout" && "$PYTHON" - ) <<'PY'
import sys
sys.path.insert(0, ".")
from systems.core.tilegrid import constants as const, syncstamp
stamped = syncstamp.read_stamp(syncstamp.stamp_path("."))
if stamped is None:
    print("  no tile sync stamp -- every chunk file counts as changed")
    sys.exit(0)
changes = syncstamp.changed_files(const.CHUNK_DIRECTORY, stamped)
for name, state in changes:
    print(f"  {state:8} {name}")
sys.exit(0 if changes else 1)
PY
}

hash_git_files blackout "${SERVER_EXCLUDES[@]}" > "$NOW_DIR/server.list"
# Python on Windows prints CRLF, and a path with a CR names no file.
mapfile -t PORTAL_FILES < <( portal_files | tr -d '\r' )
if [ "${#PORTAL_FILES[@]}" -eq 0 ]; then
    echo "Found no Portal plugin module in the settings." >&2
    exit 1
fi
hash_git_files "${PORTAL_FILES[@]}" > "$NOW_DIR/portal.list"
mapfile -t GODOT_EXCLUDES < <( godot_excludes )
hash_git_files godot "${GODOT_EXCLUDES[@]}" > "$NOW_DIR/godot.list"
if [ -n "$SITE_DIR" ]; then
    site_list > "$NOW_DIR/site.list"
fi

# --- Baseline ------------------------------------------------------------------
if [ "$BASELINE" -eq 1 ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "[dry-run] would record server, portal, godot, and site in $STATE_DIR"
        exit 0
    fi
    mkdir -p "$STATE_DIR"
    for LEG in server portal godot site; do
        if [ -f "$NOW_DIR/$LEG.list" ]; then
            cp "$NOW_DIR/$LEG.list" "$STATE_DIR/$LEG.list"
            echo "recorded $LEG"
        fi
    done
    exit 0
fi

# --- 1. Client constants -----------------------------------------------------
# A regenerated file is under godot/, so step 3 sees it and exports.
step "1/4 Client constants"
if ( cd "$REPO_ROOT/blackout" && "$PYTHON" scripts/export_client_constants.py --check ); then
    echo "up to date"
else
    echo "stale -- regenerating"
    ( cd "$REPO_ROOT/blackout" && run "$PYTHON" scripts/export_client_constants.py )
    echo "regenerated -- review and commit:"
    git -C "$REPO_ROOT" diff --stat -- godot/autoload/blackout_constants.gd
    hash_git_files godot "${GODOT_EXCLUDES[@]}" > "$NOW_DIR/godot.list"
fi

# --- 2. Server: tile sync, reboot, reload, or nothing ------------------------
# The tile sync stops and starts Evennia, so it also covers a reboot and a
# reload. A reboot also covers a reload.
step "2/4 Game server"
DO_TILES="$FORCE_TILES"
if [ "$DO_TILES" -eq 0 ] && chunks_changed; then
    DO_TILES=1
fi

if [ "$DO_TILES" -eq 1 ]; then
    echo "tile sync (stops and starts Evennia)"
    if [ "$DRY_RUN" -eq 1 ]; then
        ( cd "$REPO_ROOT/blackout" && "$PYTHON" scripts/sync_tile_objects.py )
    else
        ( cd "$REPO_ROOT/blackout" && run "$EVENNIA" stop )
        ( cd "$REPO_ROOT/blackout" && run "$PYTHON" scripts/sync_tile_objects.py --apply )
        ( cd "$REPO_ROOT/blackout" && run "$EVENNIA" start )
    fi
    write_record server
    write_record portal
elif [ "$FORCE_REBOOT" -eq 1 ] || leg_changed portal; then
    echo "reboot (Portal plugin)"
    ( cd "$REPO_ROOT/blackout" && run "$EVENNIA" reboot )
    write_record server
    write_record portal
elif leg_changed server; then
    echo "reload"
    ( cd "$REPO_ROOT/blackout" && run "$EVENNIA" reload )
    write_record server
else
    echo "unchanged, skipped"
fi

# --- 3. Godot client: export -> publish -> site deploy -----------------------
if [ "$DO_GODOT" -eq 0 ]; then
    step "3/4 Godot client -- skipped (--skip-godot)"
elif [ -z "$SITE_DIR" ]; then
    step "3/4 Godot client"
    echo "No playblackout-site checkout beside $REPO_ROOT -- skipping." >&2
else
    step "3/4 Godot client: export -> publish -> site deploy"

    NEED_EXPORT=0
    if [ ! -f "$BUILD_DIR/index.wasm" ]; then
        echo "  no export in $BUILD_DIR"
        NEED_EXPORT=1
    elif leg_changed godot; then
        NEED_EXPORT=1
    fi

    if [ "$NEED_EXPORT" -eq 1 ]; then
        run "$GODOT_BIN" --headless --path "$REPO_ROOT/godot" --export-release "Web" \
            "$BUILD_DIR/index.html"
    else
        echo "export: godot/ unchanged, skipped"
    fi

    # Always run: a model can change with no change under godot/. A dry run
    # of publish.sh reads only, so it runs here and lists the changed keys.
    if [ "$DRY_RUN" -eq 1 ]; then
        bash "$SCRIPT_DIR/webexport/publish.sh" --changed-only --dry-run
    else
        run bash "$SCRIPT_DIR/webexport/publish.sh" --changed-only
    fi
    write_record godot

    # The worker reads each R2 object on each request. Thus, a new object
    # needs no site deploy. Only a change to the worker or to dist/ does.
    if leg_changed site; then
        ( cd "$SITE_DIR" && run npx wrangler deploy )
        write_record site
    else
        echo "site deploy: worker, wrangler.jsonc, and dist/ unchanged, skipped"
    fi
fi

# --- 4. Verify -----------------------------------------------------------------
step "4/4 Verify"
if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] skipped verification requests"
else
    CODE="$( curl -sS -o /dev/null -w '%{http_code}' https://game.playblackout.io/ || true )"
    echo "game.playblackout.io -> $CODE"
    if [ "$CODE" != "200" ]; then
        echo "  not 200 -- see deploy/cloudflared/README.md ('Is it actually up?')" >&2
    fi

    if [ "$DO_GODOT" -eq 1 ] && [ -n "$SITE_DIR" ]; then
        WASM_CODE="$( curl -sS -o /dev/null -w '%{http_code}' https://playblackout.io/client/index.wasm || true )"
        echo "playblackout.io/client/index.wasm -> $WASM_CODE"
    fi
fi

echo
echo "Done."
