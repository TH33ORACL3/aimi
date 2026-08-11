# Repository Guidelines

## Project Structure & Module Organization

AIMI is an evidence-first Python catalogue for AI models, provider routes, and local harnesses. The executable `aimi` is the primary CLI. Operational boundaries live in top-level Python modules, including `monitor_endpoints.py`, `refresh_catalog.py`, `free_model_health.py`, `model_discovery_notifier.py`, `handshake.py`, and `scan_local_harnesses.py`. `schema_v2.sql` defines the SQLite schema; `tests/` contains the `unittest` suite; `skills/` contains the installable cross-agent skill. `aimi.db`, raw `evidence/`, `snapshots/`, and local harness inventories are private runtime data and must remain uncommitted.

## Build, Test, and Development Commands

```bash
python3 install.py                         # initialise DB and install the skill
python3 install.py --upgrade               # apply new schema objects safely
./aimi summary                             # inspect catalogue totals
./aimi commands                            # print the complete CLI manifest
python3 -m unittest discover -s tests -p 'test_*.py'
./validate_catalogue.py                     # integrity, evidence, pricing, and secrets
./dump_schema.py --check                    # verify schema_v2.sql matches the DB
./scan_local_harnesses.py                   # refresh local harness inventory
```

Use `python` on systems where it maps to Python 3.11+, or `py` on Windows.

## Coding Style & Naming Conventions

Target **Python 3.11+**, because scheduled jobs run under Python 3.11. Use only the standard library, four-space indentation, type hints, and `from __future__ import annotations` in new modules. Keep CLI output stable JSON where existing commands use JSON. Keep database schema statements idempotent with `IF NOT EXISTS`. Prefer small, explicit boundary modules over hidden side effects.

## Testing Guidelines

Name tests `test_*.py` and test behavior, state transitions, sanitization, and exact output contracts with `unittest`. Use temporary databases and `AIMI_DB` copies for writable scenarios. Do not make live provider calls in ordinary tests, expose credentials, or test paid/unverified routes.

## Data Safety and Catalogue Rules

The CLI is read-only by default; only explicitly approved write commands may mutate the database. Store environment-variable names, never API-key values. A route is testable as free only when its no-charge offer is verified; paid, subscription, unknown, or unverified routes require explicit `--allow-paid`. Review endpoint changes with `./aimi changes-review --note ...`; never bulk-accept changes just to satisfy validation.

## Commit and Pull Request Guidelines

Use concise imperative subjects, optionally with prefixes such as `feat:`, `fix:`, `test:`, or `docs:`. Pull requests should explain catalogue or schema impact, include the validation/test commands run, identify evidence sources, and call out any privacy or credential-handling changes.
