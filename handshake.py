#!/usr/bin/env python3
"""One small sanitized API handshake against a single provider route.

The catalogue's rules require a real handshake before enabling a newly
discovered route, but there was no way to run one and record it. This module
performs exactly one tiny request, classifies the outcome with the same three
colours the free-model health job uses, and returns a result that can be stored
in `handshake_tests`.

It never stores credentials, request headers, or raw provider bodies. Error text
is reduced to a short sanitized message with any token-shaped value removed.
"""
from __future__ import annotations

import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from aimi_credentials import load_aimi_credentials

load_aimi_credentials()

VERSION = "aimi-handshake/1.0"
PROMPT = "Reply with exactly OK"
# Anything token-shaped is removed before an error is stored or printed.
SECRET_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"(?<![A-Za-z0-9_-])nvapi-[A-Za-z0-9_-]{12,}"),
    re.compile(r"(?<![A-Za-z0-9_-])gh[pousr]_[A-Za-z0-9]{12,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{12,}"),
)
# Free semantics that do not incur a charge for a single tiny request.
NO_CHARGE_OFFERS = {"genuine_zero_price", "temporary_free_window", "free_tier_quota"}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sanitize(text: str | None, limit: int = 300) -> str | None:
    if not text:
        return None
    cleaned = " ".join(str(text).split())
    for pattern in SECRET_PATTERNS:
        cleaned = pattern.sub("[redacted]", cleaned)
    return cleaned[:limit]


def colour(status: str) -> str:
    """Three-state colour, matching the free-model health contract."""
    if status == "ok":
        return "green"
    if status == "rate_limited":
        return "orange"
    if status in ("missing_credential", "missing_base_url"):
        return "untested"
    return "red"


def describe(result: dict) -> str:
    status = result["status"]
    if status == "ok":
        return f"Returned exactly OK in {result['latency_ms']} ms"
    if status == "unexpected_response":
        return f"Reachable but replied {result.get('reply')!r} instead of exactly OK"
    if status == "rate_limited":
        return f"Rate limited (HTTP {result.get('http_status')}); availability inconclusive"
    if status == "unauthorized":
        return f"Rejected the credential (HTTP {result.get('http_status')})"
    if status == "missing_credential":
        return result.get("error_message") or "No credential available"
    if status == "timeout":
        return result.get("error_message") or "Timed out"
    return f"{status}: {result.get('error_message') or 'no detail'}"


def error_body(raw: bytes, status: int) -> str:
    try:
        payload = json.loads(raw.decode("utf-8", "replace"))
        message = payload.get("error", {})
        if isinstance(message, dict):
            message = message.get("message") or message.get("code") or json.dumps(message)
        elif not isinstance(message, str):
            message = json.dumps(message)
        # An empty error object tells us nothing. Try the other fields providers
        # commonly use before reporting the bare status, so a failure stays
        # diagnosable instead of showing '{}'.
        if message in ("{}", "[]", "null", ""):
            for key in ("detail", "message", "title", "type", "status"):
                value = payload.get(key)
                if value:
                    message = value if isinstance(value, str) else json.dumps(value)
                    break
            else:
                message = f"HTTP {status} with an empty error body"
    except Exception:
        message = raw.decode("utf-8", "replace")
    return sanitize(message or f"HTTP {status}")


def run(provider_id: str, model_identifier: str, base_url: str | None, auth_env_var: str | None,
        prompt: str = PROMPT, timeout: int = 45, max_tokens: int = 128) -> dict:
    """Perform one handshake and return a structured, sanitized result."""
    started = time.perf_counter()
    result = {
        "provider_id": provider_id,
        "model_identifier": model_identifier,
        "tested_at": now(),
        "prompt": prompt,
        "status": "configuration_error",
        "http_status": None,
        "latency_ms": None,
        "reply": None,
        "error_category": None,
        "error_message": None,
        "runner_version": VERSION,
    }
    base = (base_url or "").rstrip("/")
    if not base:
        result.update(status="missing_base_url", error_category="missing_base_url",
                      error_message="Provider base URL is not configured")
        return result
    key = os.getenv(auth_env_var) if auth_env_var else None
    if auth_env_var and not key:
        result.update(status="missing_credential", error_category="missing_credential",
                      error_message=f"Missing credential environment variable {auth_env_var}")
        return result

    payload = json.dumps({
        "model": model_identifier,
        "messages": [{"role": "user", "content": prompt}],
        # Providers that spend output budget on hidden reasoning still need room
        # to emit the final visible token.
        "max_tokens": max_tokens,
        "temperature": 0,
    }).encode()
    headers = {"Content-Type": "application/json", "User-Agent": "AZ-Labs-aimi-handshake/1.0"}
    if key:
        headers["Authorization"] = "Bearer " + key
    request = urllib.request.Request(base + "/chat/completions", data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            result["http_status"] = response.status
        data = json.loads(body)
        # Some OpenAI-compatible gateways (e.g. ClinePass) wrap the standard
        # response in a {"data": {...}} envelope. Unwrap it so the reply is read
        # from the same shape every other provider returns.
        if isinstance(data, dict) and isinstance(data.get("data"), dict) and "choices" in data["data"]:
            data = data["data"]
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        result["reply"] = sanitize(content, 200)
        usage = data.get("usage") or {}
        result["input_tokens"] = usage.get("prompt_tokens")
        result["output_tokens"] = usage.get("completion_tokens")
        if str(content).strip() == "OK":
            result["status"] = "ok"
        else:
            result.update(status="unexpected_response", error_category="unexpected_response",
                          error_message="Final response was not exactly OK")
    except urllib.error.HTTPError as exc:
        result["http_status"] = exc.code
        message = error_body(exc.read(), exc.code)
        if exc.code == 429:
            status = "rate_limited"
        elif exc.code in (401, 403):
            status = "unauthorized"
        else:
            status = "http_error"
        result.update(status=status, error_category=f"http_{exc.code}", error_message=message)
    except (TimeoutError, socket.timeout):
        result.update(status="timeout", error_category="timeout",
                      error_message=f"Request exceeded {timeout}s")
    except Exception as exc:  # noqa: BLE001 - the category is recorded, not swallowed
        result.update(status="network_error", error_category=type(exc).__name__,
                      error_message=sanitize(str(exc)))

    result["latency_ms"] = round((time.perf_counter() - started) * 1000)
    return result
