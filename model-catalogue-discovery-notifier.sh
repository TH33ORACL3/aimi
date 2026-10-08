#!/bin/bash
set -euo pipefail
# Consolidated model discovery + release desk entrypoint.
#
# 1) Polls all provider endpoints, records changes, and Telegram-alerts on
#    route add/remove via model_discovery_notifier.py (durable outbox).
# 2) This script is only the fast, deterministic detector. Editorial Pi work is
#    dispatched separately by the every-minute Hermes queue worker so long
#    builds cannot occupy Pal's single cron slot or delay endpoint polls.

PYTHON_BIN=""
CANDIDATES=(
  "${AIMI_PYTHON_BIN:-}"
  /usr/local/bin/python3.14
  /usr/local/bin/python3.13
  /usr/local/bin/python3.12
  /usr/local/bin/python3.11
  /usr/bin/python3.14
  /usr/bin/python3
  /opt/homebrew/bin/python3
)
for candidate in "${CANDIDATES[@]}"; do
  if [[ -n "$candidate" && -x "$candidate" ]] && "$candidate" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >/dev/null 2>&1; then
    PYTHON_BIN="$candidate"
    break
  fi
done
if [[ -z "$PYTHON_BIN" ]]; then
  echo "AIMI notifier requires Python 3.11 or newer; no supported interpreter was found." >&2
  exit 1
fi

AIMI_DIR="${AIMI_DIR:-${HOME}/aimi}"
if [[ ! -d "$AIMI_DIR" && -d "${HOME}/AZ Labs/2 - Testing/AIMI" ]]; then
  AIMI_DIR="${HOME}/AZ Labs/2 - Testing/AIMI"
fi

exec "$PYTHON_BIN" "$AIMI_DIR/model_discovery_notifier.py"
