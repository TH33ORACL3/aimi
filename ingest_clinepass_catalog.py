#!/usr/bin/env python3
"""Deliberately refresh AIMI from Cline's authenticated ClinePass catalogue.

This is the bounded, backed-up entrypoint for a manual Cline catalogue refresh.
Scheduled monitoring continues through monitor_endpoints.py.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import re
import sqlite3

import monitor_endpoints

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get("AIMI_DB", ROOT / "aimi.db")).expanduser().resolve()
INVENTORY = Path.home() / ".agents" / "backup-inventory.md"
BACKUP_DIR = ROOT / "backups"


def backup_policy() -> dict:
    text = INVENTORY.read_text(encoding="utf-8")
    match = re.search(r"## CONFIG.*?```json\s*(\{.*?\})\s*```", text, re.S)
    if not match:
        raise RuntimeError(f"Cannot parse backup inventory: {INVENTORY}")
    config = json.loads(match.group(1))
    for item in config.get("locations", []):
        if Path(item["path"]).expanduser() == BACKUP_DIR:
            return item
    raise RuntimeError(f"AIMI backup directory is not registered: {BACKUP_DIR}")


def create_backup() -> Path:
    policy = backup_policy()
    BACKUP_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    target = BACKUP_DIR / f"aimi.db.bak-clinepass-{stamp}.sqlite"
    source = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
        destination.execute("PRAGMA journal_mode=DELETE")
    finally:
        destination.close()
        source.close()
    Path(f"{target}-wal").unlink(missing_ok=True)
    Path(f"{target}-shm").unlink(missing_ok=True)
    os.chmod(target, 0o600)
    check = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("AIMI backup integrity check failed")
    finally:
        check.close()
    backups = sorted(BACKUP_DIR.glob(policy["pattern"]), key=lambda path: path.stat().st_mtime, reverse=True)
    for old in backups[int(policy["keep"]):]:
        old.unlink()
    return target


def validate(connection: sqlite3.Connection) -> dict:
    routes = connection.execute(
        "SELECT COUNT(*) FROM provider_models_v2 WHERE provider_id='cline' AND model_identifier LIKE 'cline-pass/%' AND endpoint_status='available'"
    ).fetchone()[0]
    qwen = connection.execute(
        "SELECT COUNT(*) FROM provider_models_v2 WHERE provider_id='cline' AND model_identifier='cline-pass/qwen3.8-max' AND endpoint_status='available'"
    ).fetchone()[0]
    links = connection.execute(
        "SELECT COUNT(*) FROM subscription_model_access sma JOIN provider_models_v2 pm USING(provider_model_id) WHERE pm.provider_id='cline' AND pm.model_identifier LIKE 'cline-pass/%' AND sma.access_type='subscription_included'"
    ).fetchone()[0]
    target = connection.execute(
        "SELECT COUNT(*) FROM monitoring_targets WHERE provider_id='cline' AND url='https://api.cline.bot/api/v1/ai/cline/recommended-models' AND enabled=1"
    ).fetchone()[0]
    result = {"clinepass_routes": routes, "qwen3.8_max": bool(qwen), "subscription_links": links, "monitor_target": bool(target)}
    if result != {"clinepass_routes": 12, "qwen3.8_max": True, "subscription_links": 12, "monitor_target": True}:
        raise RuntimeError(f"ClinePass post-ingestion validation failed: {result}")
    return result


def main() -> int:
    backup = create_backup()
    print(f"backup: {backup}")
    monitor_endpoints.DB = DB
    status = monitor_endpoints.main(["--provider", "cline"])
    if status:
        return status
    connection = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        summary = validate(connection)
    finally:
        connection.close()
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
