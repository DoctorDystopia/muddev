#!/usr/bin/env bash
#
# Runs the tile sync with --apply: stop the server, sync, start the server.
# Extra arguments pass through to sync_tile_objects.py.
#
# The server keeps the tile room index in memory, so the sync must not run
# beside it. Thus, if the stop fails, the script stops before the sync.
#
# Usage:
#   ./scripts/sync_tile_objects_apply.sh

set -u

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
GAME_DIR="$(dirname "$SCRIPT_DIR")"
EVENV_DIR="$(cd "$GAME_DIR/../evenv" && pwd)"

# The virtualenv is not on PATH. Use its own python and evennia.
if [ -f "$EVENV_DIR/Scripts/python.exe" ]; then
    PYTHON="$EVENV_DIR/Scripts/python.exe"
    EVENNIA="$EVENV_DIR/Scripts/evennia.exe"
else
    PYTHON="$EVENV_DIR/bin/python"
    EVENNIA="$EVENV_DIR/bin/evennia"
fi

cd "$GAME_DIR" || exit 1

echo "=== Stopping Evennia ==="
if ! "$EVENNIA" stop; then
    echo "The server did not stop. No sync ran." >&2
    exit 1
fi

echo "=== Tile sync (--apply) ==="
"$PYTHON" "$SCRIPT_DIR/sync_tile_objects.py" --apply "$@"
SYNC_STATUS=$?

echo "=== Starting Evennia ==="
"$EVENNIA" start

exit $SYNC_STATUS
