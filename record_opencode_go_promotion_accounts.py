#!/usr/bin/env python3
"""Record user-confirmed OpenCode Go promotion registration accounts."""
from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "aimi.db"
BACKUP_DIR = ROOT / "backups"
PROMOTION = "OpenCode Go $5 first-month plan or trial promotion"
CONFIRMED_AT = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
SOURCE = "Aubrey confirmed in chat on 2026-08-13"

ACCOUNTS = (
    ("gptcodeshop@gmail.com", "GPT Code Shop", "used"),
    ("vibecodeai@gmail.com", "Vibe Code AI", "used"),
    ("hashtag3d@gmail.com", "HashTag3D", "not_used"),
)


def main() -> None:
    BACKUP_DIR.mkdir(exist_ok=True)
    backup = BACKUP_DIR / f"aimi.db.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite"
    shutil.copy2(DB, backup)

    with sqlite3.connect(DB) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript((ROOT / "subscription_upgrade.sql").read_text(encoding="utf-8"))
        product = connection.execute(
            "SELECT subscription_product_id FROM subscription_products WHERE product_slug=?",
            ("opencode-go",),
        ).fetchone()
        if product is None:
            raise SystemExit("OpenCode Go subscription product is missing; run ingest_subscriptions.py first")
        product_id = product[0]
        for email, label, status in ACCOUNTS:
            connection.execute(
                """INSERT INTO subscription_promotion_accounts(
                    subscription_product_id, registration_email, account_label,
                    promotion_name, promotion_status, confirmed_at,
                    confirmation_source, confidence, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'user_confirmed', ?)
                ON CONFLICT(subscription_product_id, registration_email, promotion_name)
                DO UPDATE SET account_label=excluded.account_label,
                              promotion_status=excluded.promotion_status,
                              confirmed_at=excluded.confirmed_at,
                              confirmation_source=excluded.confirmation_source,
                              confidence=excluded.confidence,
                              notes=excluded.notes""",
                (
                    product_id,
                    email,
                    label,
                    PROMOTION,
                    status,
                    CONFIRMED_AT,
                    SOURCE,
                    "Used the promotion" if status == "used" else "User confirmed this email was not used",
                ),
            )
        connection.commit()

    print(f"Recorded {len(ACCOUNTS)} OpenCode Go promotion accounts")
    print(f"Backup: {backup}")


if __name__ == "__main__":
    main()
