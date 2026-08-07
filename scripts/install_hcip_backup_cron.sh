#!/usr/bin/env bash
# Install a daily cron job for HCIP backups (use if the Flask app is not always running).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/apps/backend"
PYTHON="${PYTHON:-python3}"
LOG_DIR="${HCIP_DATA_HOME:-$ROOT/../hcip-data}/backups"
mkdir -p "$LOG_DIR"
CRON_LINE="15 2 * * * cd \"$BACKEND\" && \"$PYTHON\" -m app.database.scripts.backup_hcip --force >> \"$LOG_DIR/cron.log\" 2>&1"
( crontab -l 2>/dev/null | grep -v 'app.database.scripts.backup_hcip' || true; echo "$CRON_LINE" ) | crontab -
echo "Installed cron:"
echo "  $CRON_LINE"
echo "Manual run: cd \"$BACKEND\" && $PYTHON -m app.database.scripts.backup_hcip --force"
