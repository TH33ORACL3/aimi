#!/usr/bin/env python3
"""Record user-confirmed Gmail accounts without storing credentials."""
from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "aimi.db"
BACKUP_DIR = ROOT / "backups"
CONFIRMED_AT = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
SOURCE = "Aubrey confirmed in chat on 2026-08-13"

ACCOUNTS = (
    ("vibecodeai@gmail.com", "Vibe Code AI"),
    ("gptcodeshop@gmail.com", "GPT Code Shop"),
    ("azlabsai@gmail.com", "AZ Labs"),
    ("hashtag3d@gmail.com", "HashTag3D"),
    ("aubrey.zemba@gmail.com", "Aubrey Zemba"),
    ("tokoo.co.za@gmail.com", "Tokoo"),
    ("th33oracl3@gmail.com", "TH33ORACL3"),
    ("azlabs.ai@gmail.com", "AZ Labs"),
    ("buyandsaveza@gmail.com", "Buy and Save"),
    ("azdm.org@gmail.com", "AZDM"),
    ("midjourneygcs@gmail.com", "Midjourney GCS"),
    ("gptcodeshoppro@gmail.com", "GPT Code Shop Pro"),
)


def main() -> None:
    BACKUP_DIR.mkdir(exist_ok=True)
    backup = BACKUP_DIR / f"aimi.db.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite"
    shutil.copy2(DB, backup)

    with sqlite3.connect(DB) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript((ROOT / "subscription_upgrade.sql").read_text(encoding="utf-8"))
        for email, label in ACCOUNTS:
            connection.execute(
                """INSERT INTO personal_email_accounts(
                    email_address, account_label, provider, ownership_status,
                    confirmed_at, confirmation_source, confidence, notes
                ) VALUES (?, ?, 'gmail', 'confirmed', ?, ?, 'user_confirmed', ?)
                ON CONFLICT(email_address) DO UPDATE SET account_label=excluded.account_label,
                    ownership_status=excluded.ownership_status,
                    confirmed_at=excluded.confirmed_at,
                    confirmation_source=excluded.confirmation_source,
                    confidence=excluded.confidence,
                    notes=excluded.notes""",
                (email, label, CONFIRMED_AT, SOURCE, "User-confirmed personal or business account"),
            )
        connection.commit()

    print(f"Recorded {len(ACCOUNTS)} unique Gmail accounts")
    print(f"Backup: {backup}")


if __name__ == "__main__":
    main()
