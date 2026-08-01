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


def load_aimi_credentials() -> None:
    """Load simple shell-style KEY=value entries without printing secrets.

    An explicitly supplied process environment wins over the local file. The
    file is expected to be mode 0600; callers can inspect its permissions but
    must never print its contents.
    """
    if not CREDENTIALS_PATH.exists():
        return
    try:
        # Refuse to load a credential file readable by group/others. This keeps
        # a mistaken chmod from silently widening access to the API key.
        if CREDENTIALS_PATH.stat().st_mode & 0o077:
            return
        lines = CREDENTIALS_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
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
            os.environ.setdefault(name, parsed[0])


load_aimi_credentials()
