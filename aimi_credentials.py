#!/usr/bin/env python3
"""Load AIMI-only credentials from a private user-level env file.

AIMI must not share its OpenRouter usage with unrelated harnesses. The
credential file is outside the repository and is deliberately loaded by the
AIMI Python entry points rather than exported globally from ~/.zshrc.
"""
from __future__ import annotations

import os
import shlex
from pathlib import Path

CREDENTIALS_PATH = Path.home() / ".config" / "aimi" / "credentials.env"
LOCAL_TYPESAFE_PATH = Path(__file__).resolve().parent / ".env.typesafe"


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        if path.stat().st_mode & 0o077:
            return {}
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    results: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[7:].lstrip()
        if "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        name = name.strip()
        if not name or not name.replace("_", "a").isalnum() or name[0].isdigit():
            continue
        try:
            parsed = shlex.split(value, comments=False, posix=True)
        except ValueError:
            continue
        if parsed:
            results[name] = parsed[0]
    return results


def load_aimi_credentials() -> None:
    """Load simple shell-style KEY=value entries without printing secrets.

    An explicitly supplied process environment wins over the local file. The
    file is expected to be mode 0600; callers can inspect its permissions but
    must never print its contents.
    """
    entries = _parse_env_file(CREDENTIALS_PATH)
    local_entries = _parse_env_file(LOCAL_TYPESAFE_PATH)
    combined = {**entries, **local_entries}

    for name, value in combined.items():
        os.environ.setdefault(name, value)

    # When running within AIMI, route TypeSafe Jev operations through the AIMI-specific key
    aimi_typesafe = os.environ.get("AIMI_TYPESAFE_API_KEY") or local_entries.get("TYPESAFE_API_KEY")
    if aimi_typesafe:
        os.environ["TYPESAFE_API_KEY"] = aimi_typesafe
        os.environ["TYPESAFE_JEV_API_KEY"] = aimi_typesafe


def get_aimi_typesafe_key() -> str:
    """Return the AIMI TypeSafe API key without printing or logging it."""
    load_aimi_credentials()
    return os.environ.get("TYPESAFE_API_KEY", "")


load_aimi_credentials()
