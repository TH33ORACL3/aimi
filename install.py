#!/usr/bin/env python3
"""Cross-platform, agent-first installer for AIMI."""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def check_python() -> None:
    if sys.version_info < (3, 11):
        raise SystemExit(f"AIMI requires Python 3.11 or newer; found {sys.version.split()[0]}")


def initialise_database() -> Path:
    db = ROOT / "aimi.db"
    schema = ROOT / "schema_v2.sql"
    if not db.exists():
        with sqlite3.connect(db) as conn:
            conn.executescript(schema.read_text(encoding="utf-8"))
    return db


def install_skill(target: Path) -> Path:
    source = ROOT / "skills"
    if target.exists() and target.resolve() == source.resolve():
        return target
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        destination = target / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Install and initialise AIMI for an agent")
    parser.add_argument("--skill-dir", type=Path, default=Path.home() / ".agents" / "skills" / "model-catalogue")
    parser.add_argument("--no-skill", action="store_true", help="Only initialise AIMI; do not install the skill")
    args = parser.parse_args()
    check_python()
    db = initialise_database()
    skill = None if args.no_skill else install_skill(args.skill_dir.expanduser())
    print(f"AIMI ready: {ROOT}")
    print(f"Database: {db}")
    if skill:
        print(f"Skill: {skill / 'SKILL.md'}")
    print(f"Run: {sys.executable} {ROOT / 'aimi'} summary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
