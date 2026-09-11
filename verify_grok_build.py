#!/usr/bin/env python3
"""Capture, compare, and smoke-test a real Grok Build installation.

This verifier deliberately reads only portable Grok configuration and user
assets. It never reads auth.json, MCP credentials, sessions, logs, caches, or
provider key values.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "aimi-grok-build-manifest/v2"
DEFAULT_PROMPT = "Reply exactly OK"
SENSITIVE_KEY = re.compile(
    r"^(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|"
    r"auth[_-]?token|authorization|bearer(?:[_-]?token)?|password|secret|"
    r"credential(?:s)?)$",
    re.IGNORECASE,
)
SENSITIVE_VALUE = re.compile(
    r"(?i)(?:xai-[A-Za-z0-9_-]{20,}|sk-(?:or-)?[A-Za-z0-9_-]{20,}|"
    r"nvapi-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|"
    r"bearer\s+[A-Za-z0-9._~-]{20,}|eyJ[A-Za-z0-9_-]{30,})"
)
SAFE_REFERENCE_KEYS = {
    "env_key",
    "env_http_headers",
    "bearer_token_env_var",
    "oauth_client_secret_env_var",
    "token_header",
    "auth_token_ttl",
}
SENSITIVE_PATH_PARTS = {
    "auth.json",
    "mcp_credentials.json",
    "sessions",
    "logs",
    "debug",
    "cache",
    "marketplace-cache",
    "relocations",
    "memtrace",
    "upload_queue",
    "backups",
}


def grok_home() -> Path:
    return Path(os.environ.get("GROK_HOME", "~/.grok")).expanduser().resolve()


def normalise_string(value: str, home: Path, cwd: Path | None = None) -> str:
    result = value.replace("\\", "/")
    user_home = home.parent
    replacements = [
        (str(home), "$HOME/.grok"),
        (str(home).replace("\\", "/"), "$HOME/.grok"),
        (str(user_home), "$HOME"),
        (str(user_home).replace("\\", "/"), "$HOME"),
    ]
    if cwd is not None:
        replacements.extend([(str(cwd), "$CWD"), (str(cwd).replace("\\", "/"), "$CWD")])
    for source, target in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
        if source:
            result = result.replace(source, target)
    return result.replace("\\", "/")


def redact(value: Any, key: str = "", *, home: Path | None = None, cwd: Path | None = None) -> Any:
    """Redact secret values while retaining model metadata and env names."""
    home = home or grok_home()
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for name, item in value.items():
            name_text = str(name)
            if SENSITIVE_KEY.fullmatch(name_text) and name_text.lower() not in SAFE_REFERENCE_KEYS:
                output[name_text] = "<redacted>" if item not in (None, "", [], {}) else item
            else:
                output[name_text] = redact(item, name_text, home=home, cwd=cwd)
        return output
    if isinstance(value, list):
        return [redact(item, key, home=home, cwd=cwd) for item in value]
    if isinstance(value, str):
        if SENSITIVE_KEY.fullmatch(key) and key.lower() not in SAFE_REFERENCE_KEYS:
            return "<redacted>" if value else value
        return normalise_string(SENSITIVE_VALUE.sub("<redacted>", value), home, cwd)
    return value


def run_command(argv: list[str], *, cwd: Path | None = None, timeout: float = 180.0) -> dict[str, Any]:
    executable = Path(argv[0]).suffix.lower() if argv else ""
    exec_argv = ["cmd.exe", "/d", "/c", *argv] if os.name == "nt" and executable in {".cmd", ".bat"} else argv
    try:
        completed = subprocess.run(
            exec_argv,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            env=os.environ.copy(),
        )
        return {
            "argv": argv,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except FileNotFoundError as exc:
        return {"argv": argv, "exit_code": 127, "stdout": "", "stderr": str(exc)}
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode(errors="replace")
        stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode(errors="replace")
        return {"argv": argv, "exit_code": 124, "stdout": stdout, "stderr": stderr + "\ncommand timed out"}


def parse_json_output(stdout: str) -> Any:
    text = stdout.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overlay.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Path, *, home: Path, cwd: Path | None = None) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return {
            "exists": True,
            "mode": oct(path.stat().st_mode & 0o777),
            "data": redact(data, home=home, cwd=cwd),
        }
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return {"exists": True, "parse_error": f"{type(exc).__name__}: {exc}"}


def parse_models_output(stdout: str) -> dict[str, Any]:
    default: str | None = None
    available: list[str] = []
    logged_in: bool | None = None
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if line.lower().startswith("default model:"):
            default = line.split(":", 1)[1].strip()
        elif line.lower().startswith("you are logged in"):
            logged_in = True
        elif line.startswith("- ") or line.startswith("* "):
            model = line[2:].strip()
            if model.endswith(" (default)"):
                model = model[: -len(" (default)")].rstrip()
            if model:
                available.append(model)
    return {"default": default, "available": available, "logged_in": logged_in}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_portable_assets(home: Path) -> Iterable[dict[str, Any]]:
    """Return hashes for user rules/skills without following sensitive roots."""
    roots = [home / "rules", home / "skills"]
    visited_dirs: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for directory, dirnames, filenames in os.walk(root, followlinks=True):
            directory_path = Path(directory)
            try:
                real_directory = directory_path.resolve()
                relative_directory = directory_path.relative_to(home)
            except (OSError, ValueError):
                dirnames[:] = []
                continue
            if real_directory in visited_dirs:
                dirnames[:] = []
                continue
            visited_dirs.add(real_directory)
            dirnames[:] = [
                name for name in dirnames
                if name not in SENSITIVE_PATH_PARTS
                and name not in {"__pycache__", ".git"}
            ]
            for filename in sorted(filenames):
                path = directory_path / filename
                relative = relative_directory / filename
                if any(part in SENSITIVE_PATH_PARTS for part in relative.parts):
                    continue
                try:
                    item = {
                        "path": relative.as_posix(),
                        "bytes": path.stat().st_size,
                        "sha256": sha256(path),
                    }
                    yield item
                except OSError:
                    continue


def dependency_inventory(home: Path) -> list[dict[str, Any]]:
    """Inventory applicable bridge/provider files without reading credentials."""
    user_home = home.parent
    candidates = [
        user_home / "bin" / "github-copilot-bridge.py",
        user_home / "bin" / "nim-normalize-proxy.py",
        user_home / "Library" / "LaunchAgents" / "ai.azlabs.github-copilot-bridge.plist",
        user_home / ".config" / "azlabs" / "aura-worker.env",
        user_home / ".pi" / "agent" / "auth.json",
    ]
    inventory: list[dict[str, Any]] = []
    for path in candidates:
        item: dict[str, Any] = {
            "path": normalise_string(str(path), home),
            "exists": path.exists(),
        }
        if not path.exists():
            inventory.append(item)
            continue
        try:
            item["mode"] = oct(path.stat().st_mode & 0o777)
            item["bytes"] = path.stat().st_size
            if path.name == "auth.json":
                item["credential_store"] = True
            elif path.suffix == ".env":
                names: list[str] = []
                for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                    match = re.match(r"\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=", line)
                    if match:
                        names.append(match.group(1))
                item["environment_names"] = sorted(set(names))
            else:
                item["sha256"] = sha256(path)
        except OSError:
            item["read_error"] = True
        inventory.append(item)
    return inventory


def comparable_inspect(inspect: Any) -> Any:
    if not isinstance(inspect, dict):
        return inspect
    # These fields describe external Claude/Cursor installations or project
    # discovery and are intentionally recorded in the manifest but not used for
    # cross-platform Grok parity.
    config_sources = inspect.get("configSources")
    if isinstance(config_sources, dict) and isinstance(config_sources.get("layers"), list):
        config_sources = {
            **config_sources,
            "layers": [
                layer for layer in config_sources["layers"]
                if isinstance(layer, dict) and layer.get("role") != "env_overlay"
            ],
        }
    selected = {
        "grokVersion": inspect.get("grokVersion"),
        "channel": inspect.get("channel"),
        "configSources": config_sources,
        "configWarnings": inspect.get("configWarnings"),
        "externalCompat": inspect.get("externalCompat"),
        "loginPolicy": inspect.get("loginPolicy"),
        "marketplaces": inspect.get("marketplaces"),
        "mcpServers": inspect.get("mcpServers"),
        "lspServers": inspect.get("lspServers"),
        "agents": inspect.get("agents"),
        "skills": inspect.get("skills"),
    }
    skills = selected.get("skills")
    if isinstance(skills, list):
        selected["skills"] = [
            {
                key: item[key]
                for key in ("name", "userInvocable", "invocableAs", "source")
                if isinstance(item, dict) and key in item
            }
            for item in skills
            if isinstance(item, dict)
            and isinstance(item.get("source"), dict)
            and str(item["source"].get("path", "")).startswith("$HOME/.grok/skills/")
        ]
    return selected


def parse_version(stdout: str) -> str | None:
    match = re.search(r"\bgrok\s+([0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9._-]+)?)\b", stdout, re.IGNORECASE)
    return match.group(1) if match else None


def capture_manifest(*, grok_command: str = "grok", cwd: Path | None = None) -> dict[str, Any]:
    home = grok_home()
    cwd = (cwd or Path.cwd()).resolve()
    version = run_command([grok_command, "--version"], cwd=cwd)
    models = run_command([grok_command, "models"], cwd=cwd)
    inspect_result = run_command([grok_command, "inspect", "--json"], cwd=cwd)
    inspect: Any = None
    inspect_error: str | None = None
    if inspect_result["exit_code"] == 0:
        try:
            inspect = redact(parse_json_output(inspect_result["stdout"]), home=home, cwd=cwd)
        except (json.JSONDecodeError, TypeError) as exc:
            inspect_error = f"{type(exc).__name__}: {exc}"
    config_layers: dict[str, Any] = {}
    for name in ("config.toml", "managed_config.toml", "requirements.toml"):
        config_layers[name] = load_config(home / name, home=home, cwd=cwd)
    config_layer = config_layers["config.toml"]
    config_data = config_layer.get("data", {})
    effective_config = config_data if isinstance(config_data, dict) else {}
    raw_overlay = os.environ.get("GROK_CONFIG", "").strip()
    if raw_overlay:
        try:
            parsed_overlay = json.loads(raw_overlay)
        except json.JSONDecodeError:
            parsed_overlay = None
        if isinstance(parsed_overlay, dict):
            effective_config = deep_merge(effective_config, parsed_overlay)
    config_layer["effective_data"] = redact(effective_config, home=home, cwd=cwd)
    model_summary = parse_models_output(models["stdout"])
    model_config = effective_config.get("model", {}) if isinstance(effective_config, dict) else {}
    env_refs: set[str] = set()
    if isinstance(model_config, dict):
        for definition in model_config.values():
            if not isinstance(definition, dict):
                continue
            for key in ("env_key", "env_http_headers", "bearer_token_env_var", "oauth_client_secret_env_var"):
                value = definition.get(key)
                if isinstance(value, str):
                    env_refs.add(value)
                elif isinstance(value, list):
                    env_refs.update(item for item in value if isinstance(item, str))
                elif isinstance(value, dict):
                    env_refs.update(item for item in value.values() if isinstance(item, str))
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "captured_at": run_command(["date", "+%Y-%m-%dT%H:%M:%S%z"])["stdout"].strip(),
        "host": {
            "platform": sys.platform,
            "machine": os.environ.get("PROCESSOR_ARCHITECTURE") or getattr(os, "uname", lambda: type("U", (), {"machine": "unknown"})())().machine,
        },
        "grok_home": "$HOME/.grok",
        "cwd": "$CWD",
        "commands": {
            "version": {**version, "stdout": redact(version["stdout"], home=home, cwd=cwd), "stderr": redact(version["stderr"], home=home, cwd=cwd)},
            "models": {**models, "stdout": redact(models["stdout"], home=home, cwd=cwd), "stderr": redact(models["stderr"], home=home, cwd=cwd)},
            "inspect_json": {**inspect_result, "stdout": redact(inspect_result["stdout"], home=home, cwd=cwd), "stderr": redact(inspect_result["stderr"], home=home, cwd=cwd)},
        },
        "version": parse_version(version["stdout"]),
        "models": model_summary,
        "config_layers": config_layers,
        "environment_reference_names": sorted(env_refs),
        "dependency_inventory": dependency_inventory(home),
        "assets": sorted(iter_portable_assets(home), key=lambda item: item["path"]),
        "inspect": inspect,
        "inspect_parse_error": inspect_error,
    }
    return redact(manifest, home=home, cwd=cwd)


def secret_hits(value: Any) -> list[str]:
    text = json.dumps(value, sort_keys=True)
    return sorted(set(match.group(0) for match in SENSITIVE_VALUE.finditer(text)))


def comparable_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    config = manifest.get("config_layers", {}).get("config.toml", {})
    config = {
        "exists": config.get("exists", False),
        "data": config.get("effective_data", config.get("data")),
    }
    assets = [
        {
            key: item[key]
            for key in ("path", "bytes", "sha256")
            if isinstance(item, dict) and key in item
        }
        for item in manifest.get("assets", [])
        if isinstance(item, dict)
    ]
    return {
        "version": manifest.get("version"),
        "models": {
            "default": manifest.get("models", {}).get("default"),
            "available": manifest.get("models", {}).get("available", []),
        },
        "config": config,
        "environment_reference_names": manifest.get("environment_reference_names", []),
        "assets": assets,
        "inspect": comparable_inspect(manifest.get("inspect")),
    }


def diff_values(left: Any, right: Any, path: str = "$") -> list[dict[str, Any]]:
    if type(left) is not type(right):
        return [{"path": path, "source": left, "target": right}]
    if isinstance(left, dict):
        differences: list[dict[str, Any]] = []
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                differences.append({"path": f"{path}.{key}", "source": left.get(key), "target": right.get(key)})
            else:
                differences.extend(diff_values(left[key], right[key], f"{path}.{key}"))
        return differences
    if isinstance(left, list):
        differences = []
        for index in range(max(len(left), len(right))):
            if index >= len(left) or index >= len(right):
                differences.append({"path": f"{path}[{index}]", "source": left[index] if index < len(left) else None, "target": right[index] if index < len(right) else None})
            else:
                differences.extend(diff_values(left[index], right[index], f"{path}[{index}]"))
        return differences
    return [] if left == right else [{"path": path, "source": left, "target": right}]


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"manifest is not an object: {path}")
    hits = secret_hits(data)
    if hits:
        raise ValueError(f"secret-shaped values found in {path}: {hits}")
    return data


def compare(source_path: Path, target_path: Path) -> int:
    source = load_manifest(source_path)
    target = load_manifest(target_path)
    differences = diff_values(comparable_manifest(source), comparable_manifest(target))
    result = {
        "schema": SCHEMA,
        "source": str(source_path),
        "target": str(target_path),
        "status": "passed" if not differences else "failed",
        "differences": differences,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not differences else 1


def model_ids(manifest: dict[str, Any]) -> list[str]:
    available = manifest.get("models", {}).get("available", [])
    if isinstance(available, list) and available:
        return [item for item in available if isinstance(item, str)]
    config = manifest.get("config_layers", {}).get("config.toml", {}).get("data", {})
    custom = config.get("model", {}) if isinstance(config, dict) else {}
    return list(custom) if isinstance(custom, dict) else []


def shell_quote(value: str) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline([value])
    return shlex.quote(value)


def hyperfine_command(argv: list[str], stdout_path: Path, stderr_path: Path) -> str:
    command = " ".join(shell_quote(item) for item in argv)
    return f"{command} > {shell_quote(str(stdout_path))} 2> {shell_quote(str(stderr_path))}"


def run_hyperfine(command: str, *, timeout: float) -> dict[str, Any]:
    return run_command(
        [
            "hyperfine",
            "--runs",
            "1",
            "--warmup",
            "0",
            "--show-output",
            command,
        ],
        timeout=timeout,
    )


def smoke(*, manifest_path: Path, grok_command: str, output_path: Path | None, timeout: float) -> int:
    manifest = load_manifest(manifest_path)
    home = grok_home()
    models = model_ids(manifest)
    if not models:
        payload = {"schema": SCHEMA, "prompt": DEFAULT_PROMPT, "models": [], "passed": False, "records": [], "error": "manifest contains no model IDs"}
        rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if output_path:
            output_path.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return 1

    use_hyperfine = shutil.which("hyperfine") is not None
    records: list[dict[str, Any]] = []
    for model in models:
        argv = [grok_command, "-m", model, "-p", DEFAULT_PROMPT]
        attempts = 1 if use_hyperfine else 2
        for attempt in range(1, attempts + 1):
            if use_hyperfine:
                with tempfile.TemporaryDirectory(prefix="grok-smoke-", dir=home) as directory:
                    response_path = Path(directory) / "stdout.txt"
                    error_path = Path(directory) / "stderr.txt"
                    command = hyperfine_command(argv, response_path, error_path)
                    runner_result = run_hyperfine(command, timeout=timeout)
                    response_stdout = response_path.read_text(encoding="utf-8", errors="replace") if response_path.exists() else ""
                    response_stderr = error_path.read_text(encoding="utf-8", errors="replace") if error_path.exists() else ""
                safe_runner_stdout = redact(runner_result["stdout"])
                safe_runner_stderr = redact(runner_result["stderr"])
                safe_stdout = redact(response_stdout)
                safe_stderr = redact(response_stderr)
                exit_code = runner_result["exit_code"]
            else:
                runner_result = run_command(argv, timeout=timeout)
                safe_runner_stdout = ""
                safe_runner_stderr = ""
                safe_stdout = redact(runner_result["stdout"])
                safe_stderr = redact(runner_result["stderr"])
                exit_code = runner_result["exit_code"]
            ok = exit_code == 0 and bool(re.search(r"\bOK\b", safe_stdout, re.IGNORECASE))
            records.append({
                "model": model,
                "attempt": attempt,
                "runner": "hyperfine" if use_hyperfine else "direct-twice",
                "argv": argv,
                "exit_code": exit_code,
                "ok": ok,
                "stdout": safe_stdout,
                "stderr": safe_stderr,
                "runner_stdout": safe_runner_stdout,
                "runner_stderr": safe_runner_stderr,
            })
    payload = {
        "schema": SCHEMA,
        "prompt": DEFAULT_PROMPT,
        "models": models,
        "runner": "hyperfine" if use_hyperfine else "direct-twice",
        "passed": all(item["ok"] for item in records) and len(records) == len(models) * (1 if use_hyperfine else 2),
        "records": records,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output_path:
        output_path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if payload["passed"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture_parser = subparsers.add_parser("capture", help="invoke the real Grok CLI and write a redacted manifest")
    capture_parser.add_argument("--output", type=Path, required=True)
    capture_parser.add_argument("--cwd", type=Path, default=Path.cwd())
    capture_parser.add_argument("--grok", default="grok")

    compare_parser = subparsers.add_parser("compare", help="compare two redacted manifests")
    compare_parser.add_argument("source", type=Path)
    compare_parser.add_argument("target", type=Path)

    smoke_parser = subparsers.add_parser("smoke", help="invoke the real Grok CLI for each manifest model")
    smoke_parser.add_argument("--manifest", type=Path, required=True)
    smoke_parser.add_argument("--output", type=Path)
    smoke_parser.add_argument("--grok", default="grok")
    smoke_parser.add_argument("--timeout", type=float, default=300.0)

    args = parser.parse_args(argv)
    if args.command == "capture":
        manifest = capture_manifest(grok_command=args.grok, cwd=args.cwd)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({
            "status": "passed" if manifest["commands"]["version"]["exit_code"] == 0 and manifest["commands"]["models"]["exit_code"] == 0 and manifest["commands"]["inspect_json"]["exit_code"] == 0 else "failed",
            "version": manifest["version"],
            "model_count": len(model_ids(manifest)),
            "asset_count": len(manifest["assets"]),
            "output": str(args.output),
        }, indent=2, sort_keys=True))
        return 0 if all(manifest["commands"][name]["exit_code"] == 0 for name in ("version", "models", "inspect_json")) else 1
    if args.command == "compare":
        return compare(args.source, args.target)
    return smoke(manifest_path=args.manifest, grok_command=args.grok, output_path=args.output, timeout=args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
