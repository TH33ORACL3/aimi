#!/usr/bin/env python3
"""Dispatch short Hermes ticks to one detached, durable release worker."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import model_release_desk as desk

STATE_DIR = Path.home() / ".hermes" / "cron" / "model-release-desk-worker"
ACTIVE_FILE = STATE_DIR / "active.json"
DISPATCH_LOCK = STATE_DIR / "dispatcher.lock"
WORKER_RUNS = desk.RUNS / "detached-workers"
VERSION = "model-release-worker/1.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def read_json(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def process_matches(pid: int, run_id: str) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        command = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
    except (OSError, ProcessLookupError):
        return False
    return "model_release_worker.py" in command and run_id in command


def systemd_unit_active(unit_name: str) -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "--quiet", unit_name],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def release_lock_is_held() -> bool:
    """Avoid recovering a stale queue claim while a manual release worker is active."""
    desk.LOCK.parent.mkdir(parents=True, exist_ok=True)
    with desk.LOCK.open("w", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return False


def recover_abandoned_batch(queue: dict, error: str) -> None:
    batch = queue.get("active_batch")
    if not isinstance(batch, dict):
        return
    endpoint_ids = {int(value) for value in batch.get("endpoint_change_ids", [])}
    items = [item for item in queue.get("pending", []) if desk.event_key(item) in endpoint_ids]
    desk.mark_attempt_failure(queue, items, error)


def finish_dead_worker(state: dict, queue: dict) -> dict:
    active = state.get("active") or {}
    result_path = Path(str(active.get("result_path") or ""))
    result = read_json(result_path) if str(result_path) else None
    if result is None or result.get("status") == "running":
        recover_abandoned_batch(
            queue,
            f"Detached release worker {active.get('run_id')} exited before writing a terminal result",
        )
        result = {
            "run_id": active.get("run_id"),
            "status": "interrupted",
            "completed_at": utc_now(),
            "error": "Worker exited before a terminal result; queued routes remain retryable.",
            "log_path": active.get("log_path"),
        }
    state["active"] = None
    result.setdefault("reported", False)
    state["last_result"] = result
    write_json(ACTIVE_FILE, state)
    return result


def report_worker_failure(state: dict, result: dict) -> int:
    result["reported"] = True
    state["last_result"] = result
    write_json(ACTIVE_FILE, state)
    print(
        f"AIMI detached release worker {result.get('run_id')} "
        f"{result.get('status')}: {desk.safe_error(result.get('error') or 'see worker log')}"
    )
    return 1


def worker_main(run_id: str, result_path: Path) -> int:
    run_dir = WORKER_RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    status: dict[str, Any] = {
        "run_id": run_id,
        "pid": os.getpid(),
        "status": "running",
        "started_at": utc_now(),
    }
    write_json(result_path, status)
    command = [
        sys.executable,
        str(desk.PROJECT / "model_release_desk.py"),
        "process",
        "--seed-days",
        "1",
        "--digest",
        f"detached worker {run_id}",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=desk.PROJECT,
            capture_output=True,
            text=True,
            timeout=desk.PI_TIMEOUT_SECONDS + 120,
            check=False,
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        exit_code = result.returncode
        worker_status = "completed" if exit_code == 0 else "failed"
        error = desk.safe_error(stderr or stdout or f"worker exited {exit_code}") if exit_code else None
    except subprocess.TimeoutExpired as exc:
        stdout = str(exc.stdout or "")
        stderr = str(exc.stderr or "")
        exit_code = 124
        worker_status = "failed"
        error = f"Detached worker exceeded {exc.timeout}s"
    except Exception as exc:
        stdout = ""
        stderr = ""
        exit_code = 1
        worker_status = "failed"
        error = f"{type(exc).__name__}: {desk.safe_error(exc)}"

    stdout_path = run_dir / "stdout.txt"
    stderr_path = run_dir / "stderr.txt"
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    status.update(
        {
            "status": worker_status,
            "exit_code": exit_code,
            "completed_at": utc_now(),
            "error": error,
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
        }
    )
    write_json(result_path, status)
    return 0 if exit_code == 0 else 1


def dispatch_once() -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with DISPATCH_LOCK.open("w", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0

        state = read_json(ACTIVE_FILE) or {"version": VERSION, "active": None, "last_result": None}
        active = state.get("active")
        if isinstance(active, dict):
            unit_name = str(active.get("unit_name") or "")
            is_active = (
                systemd_unit_active(unit_name)
                if unit_name
                else process_matches(int(active.get("pid") or 0), str(active.get("run_id") or ""))
            )
            if is_active:
                return 0
            queue = desk.load_queue()
            result = finish_dead_worker(state, queue)
            if result.get("status") in {"failed", "interrupted"} and not result.get("reported"):
                return report_worker_failure(state, result)

        previous_result = state.get("last_result")
        if isinstance(previous_result, dict) and previous_result.get("status") in {"failed", "interrupted"} and not previous_result.get("reported"):
            return report_worker_failure(state, previous_result)

        if release_lock_is_held():
            return 0

        queue = desk.load_queue()
        if not state.get("active") and isinstance(queue.get("active_batch"), dict):
            recover_abandoned_batch(queue, "Recovered a stale Hermes release-batch claim before dispatch.")
            queue = desk.load_queue()
        pending = [item for item in queue.get("pending", []) if isinstance(item, dict)]
        ready = desk.ready_for_processing(pending)
        if not ready:
            return 0

        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        run_dir = WORKER_RUNS / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        result_path = STATE_DIR / "results" / f"{run_id}.json"
        log_path = run_dir / "launcher.log"
        environment = os.environ.copy()
        environment.setdefault("AIMI_RELEASE_DESK_MODEL", "openai-codex/gpt-5.6-luna")
        unit_name = f"aimi-model-release-worker-{run_id.lower()}.service"
        model = environment.get("AIMI_RELEASE_DESK_MODEL", "openai-codex/gpt-5.6-luna")
        environment_options = [
            f"--setenv={name}={environment[name]}"
            for name in ("AIMI_RELEASE_DESK_MODEL", "AIMI_RELEASE_DESK_PI_TIMEOUT_SECONDS", "AIMI_TELEGRAM_TARGET")
            if name in environment
        ]
        if not any(value.startswith("--setenv=AIMI_RELEASE_DESK_MODEL=") for value in environment_options):
            environment_options.append(f"--setenv=AIMI_RELEASE_DESK_MODEL={model}")
        command = [
            "systemd-run",
            "--quiet",
            "--no-block",
            "--collect",
            f"--unit={unit_name}",
            f"--property=WorkingDirectory={desk.PROJECT}",
            *environment_options,
            sys.executable,
            str(Path(__file__).resolve()),
            "worker",
            run_id,
            str(result_path),
        ]
        try:
            launched = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"Could not launch detached AIMI worker: {desk.safe_error(exc)}")
            return 1
        if launched.returncode != 0:
            print(f"systemd could not start the AIMI worker: {desk.safe_error(launched.stderr or launched.stdout)}")
            return 1
        write_json(
            ACTIVE_FILE,
            {
                "version": VERSION,
                "active": {
                    "run_id": run_id,
                    "unit_name": unit_name,
                    "started_at": utc_now(),
                    "result_path": str(result_path),
                    "log_path": str(log_path),
                },
                "last_result": state.get("last_result"),
            },
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("dispatch", "worker"))
    parser.add_argument("run_id", nargs="?")
    parser.add_argument("result_path", nargs="?")
    args = parser.parse_args(argv)
    if args.action == "dispatch":
        return dispatch_once()
    if not args.run_id or not args.result_path:
        parser.error("worker requires run_id and result_path")
    return worker_main(args.run_id, Path(args.result_path))


if __name__ == "__main__":
    raise SystemExit(main())
