#!/usr/bin/env bash

# Resolve the directory of this script, then the game directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
GAME_DIR="$(dirname "$SCRIPT_DIR")"

# Resolve the virtual environment directory (one level up from GAME_DIR)
EVENV_DIR="$(cd "$GAME_DIR/../.venv" && pwd)"

# Detect if we are on Windows (Git Bash) or Linux/macOS to find the correct venv paths
if [ -f "$EVENV_DIR/Scripts/python" ]; then
    PYTHON="$EVENV_DIR/Scripts/python"
    EVENNIA="$EVENV_DIR/bin/evennia"
else
    PYTHON="$EVENV_DIR/bin/python"
    EVENNIA="$EVENV_DIR/bin/evennia"
fi

# Change to the game directory
cd "$GAME_DIR" || exit 1

echo "=== Stopping Evennia ==="
"$EVENNIA" stop

echo "=== Cleaning up old map data ==="
if ! "$PYTHON" "$SCRIPT_DIR/xyz_cleanup.py"; then
    echo "Error: Cleanup failed" >&2
    exit 1
fi

echo "=== Adding maps ==="
"$EVENNIA" xyzgrid add world.maps.test_neo_cairo
"$EVENNIA" xyzgrid add world.maps.test_oasis
"$EVENNIA" xyzgrid add world.maps.test_oasis_outskirts

echo "=== Spawning maps ==="
"$EVENNIA" xyzgrid spawn

echo "=== Reloading Evennia ==="
"$EVENNIA" reload

echo "=== Done ==="