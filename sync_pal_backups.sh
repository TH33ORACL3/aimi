#!/bin/bash
set -euo pipefail

# Automated backup sync for AIMI database from Pal VPS to Mac Katara.
# Synchronizes verified SQLite snapshots, validates integrity, and prunes older copies.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${ROOT_DIR}/backups"
mkdir -p "$BACKUP_DIR"

echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] Syncing AIMI snapshots from Pal VPS..."
rsync -avz --include='aimi.db.bak-*.sqlite' --exclude='*' pal:/root/aimi/backups/ "$BACKUP_DIR/"

# Find most recent snapshot by modification / sort time
LATEST=$(ls -1t "$BACKUP_DIR"/aimi.db.bak-*.sqlite 2>/dev/null | head -n 1 || true)

if [[ -z "$LATEST" || ! -f "$LATEST" ]]; then
  echo "Error: No SQLite backup files found in $BACKUP_DIR" >&2
  exit 1
fi

echo "Validating latest snapshot: $(basename "$LATEST")"
INTEGRITY=$(sqlite3 "$LATEST" "PRAGMA integrity_check;")
if [[ "$INTEGRITY" != *"ok"* ]]; then
  echo "Error: SQLite integrity check failed for $LATEST: $INTEGRITY" >&2
  exit 2
fi

echo "Snapshot $(basename "$LATEST") verified (integrity: ok)."

# Keep local backups to 7 most recent to preserve disk space (macOS / BSD compatible)
ls -1t "$BACKUP_DIR"/aimi.db.bak-*.sqlite 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null || true

echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] AIMI backup sync completed successfully."
