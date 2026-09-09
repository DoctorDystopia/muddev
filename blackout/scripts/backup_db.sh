#!/usr/bin/env bash
#
# Backs up the live Evennia database to server/backups/, pruning older
# backups beyond the retention count. Thin wrapper around backup_db.py so
# cron has a single, argument-free-by-default target.
#
# Usage:
#   ./scripts/backup_db.sh                  # defaults: keep 14, server/backups
#   ./scripts/backup_db.sh --keep 30
#   ./scripts/backup_db.sh --dest /var/backups/blackout

set -u

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
GAME_DIR="$(dirname "$SCRIPT_DIR")"
EVENV_DIR="$(cd "$GAME_DIR/../evenv" && pwd)"

if [ -f "$EVENV_DIR/Scripts/python.exe" ]; then
    PYTHON="$EVENV_DIR/Scripts/python.exe"
else
    PYTHON="$EVENV_DIR/bin/python"
fi

cd "$GAME_DIR" || exit 1

"$PYTHON" "$SCRIPT_DIR/backup_db.py" "$@"
exit $?
