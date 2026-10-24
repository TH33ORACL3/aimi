#!/bin/bash
set -euo pipefail
# Short Hermes tick. It only claims/launches a detached release worker and
# returns immediately, leaving the single Pal cron slot available for other jobs.
AIMI_DIR="${AIMI_DIR:-${HOME}/aimi}"
PYTHON_BIN="${AIMI_PYTHON_BIN:-/usr/bin/python3.14}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi
if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  echo "AIMI release dispatcher requires Python 3.11+." >&2
  exit 1
fi
export AIMI_RELEASE_DESK_MODEL="${AIMI_RELEASE_DESK_MODEL:-deepseek/deepseek-v4-pro}"

# /tmp is a 128 MB tmpfs that fills easily (Node compile-cache, scrape caches,
# pi subprocess temp files). When it hits 100% the detached Node worker dies
# with ENOSPC on write. Redirect temp storage to the root filesystem, which
# has ~16 GB free. /var/tmp is persistent and on the same disk as /root.
export TMPDIR="${TMPDIR:-/var/tmp}"
if [[ ! -d "$TMPDIR" ]]; then
  TMPDIR=/tmp
fi

exec "$PYTHON_BIN" "$AIMI_DIR/model_release_worker.py" dispatch
