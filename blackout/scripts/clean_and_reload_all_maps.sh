#!/usr/bin/env bash

# Resolve the directory of this script, then the game directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
GAME_DIR="$(dirname "$SCRIPT_DIR")"

# Resolve the virtual environment directory (one level up from GAME_DIR)
EVENV_DIR="$(cd "$GAME_DIR/../evenv" && pwd)"

# Detect if we are on Windows (Git Bash) or Linux/macOS to find the correct venv paths
if [ -f "$EVENV_DIR/Scripts/python.exe" ]; then
    PYTHON="$EVENV_DIR/Scripts/python.exe"
    EVENNIA="$EVENV_DIR/Scripts/evennia.exe"
else
    PYTHON="$EVENV_DIR/bin/python"
    EVENNIA="$EVENV_DIR/bin/evennia"
fi

# Change to the game directory
cd "$GAME_DIR" || exit 1

MANIFEST="$SCRIPT_DIR/map_manifest.json"

echo "=== Reading map manifest ==="
if ! MAPS=$("$PYTHON" -c 'import json, sys; print("\n".join(m["module"] for m in json.load(open(sys.argv[1]))["maps"]))' "$MANIFEST"); then
    echo "Error: failed to parse $MANIFEST" >&2
    exit 1
fi
if [ -z "$MAPS" ]; then
    echo "Error: map manifest $MANIFEST contains no maps" >&2
    exit 1
fi

echo "=== Stopping Evennia ==="
"$EVENNIA" stop

echo "=== Cleaning up old map data ==="
if ! "$PYTHON" "$SCRIPT_DIR/xyz_cleanup.py"; then
    echo "Error: Cleanup failed" >&2
    exit 1
fi

echo "=== Adding maps ==="
while IFS= read -r MODULE; do
    echo "  Adding $MODULE"
    if ! "$EVENNIA" xyzgrid add "$MODULE"; then
        echo "Error: failed to add $MODULE" >&2
        exit 1
    fi
done <<< "$MAPS"

echo "=== Spawning maps ==="
"$EVENNIA" xyzgrid spawn

echo "=== Reloading Evennia ==="
"$EVENNIA" reload

echo "=== Done ==="