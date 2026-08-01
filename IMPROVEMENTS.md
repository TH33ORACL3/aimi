# AIMI improvement plan

Status as of 2026-08-01. Items in "Done" shipped in commits `78fdd2f` and `590772d`.
Everything under "Needs a decision" and "Proposed" is deliberately **not** implemented,
because it either changes authoritative data or changes a policy Aubrey set.

---

## Done

| Area | Change | Evidence |
|---|---|---|
| Install | `schema_v2.sql` regenerated from the live database; 11 missing tables/views restored | fresh-checkout install smoke test passes 12/12 commands |
| Install | `dump_schema.py` + `schema_file_matches_database` validator check | drift can no longer go unnoticed |
| Install | Skill installs to `ai-model-index`, not a competing `model-catalogue` dir | no stray directory created |
| Install | Wrapper resolves the project via `AIMI_HOME` → repo layout → `project-path` marker | works from repo and from the installed copy |
| Evidence | 12 424 stored paths rewritten to project-relative form | 885 broken references repaired, 0 missing |
| Evidence | `referenced_snapshots_present` validator check | a missing capture now fails validation |
| Storage | Content-addressed snapshots; identical payloads reuse the existing capture | 4 694 duplicates removed, 323 MB reclaimed, 578 MB → 247 MB |
| Storage | 10 stale database backups deleted | 101 MB → 22 MB |
| Safety | CLI opens the database read-only except `changes-review` | a query cannot corrupt the catalogue |
| Safety | WAL journalling | monitor and reader no longer contend |
| Correctness | `doctor` compares ordered Pi lists, not list lengths | equal-length drift no longer reports healthy |
| Agent UX | `changes-review`, `commands` manifest, `version`, help text on all 33 commands | `aimi commands` is machine-readable |

---

## Needs a decision (these block validation)

### 1. 460 false-positive `model_changed` rows
Ids **1547–2006**, all detected 2026-07-31, Mistral (260), OpenCode Go (120), OpenCode Zen (80).
Verified: the only difference is `provider_created_at`, derived from a provider `created`
field that is a *retrieval* timestamp. The fingerprint fix already excludes it, and a fresh
poll now reports all three providers unchanged, so these are historical residue of exactly
the class already corrected once (the 184 removed on 31 July).

- **Option A** — delete the 460 rows and correct their monitoring runs to `unchanged`, as done for the previous 184.
- **Option B** — keep them and mark reviewed with a note explaining they are known noise.
- **Option C** — leave untouched.

### 2. 1 548 substantive unreviewed changes
Largest groups: OpenRouter `model_added` 402, `pricing_changed` 275, `model_changed` 192
(genuine pricing/limit changes), NVIDIA NIM `model_added` 120, OpenAI `model_added` 120.
`aimi changes-review` can accept these in filtered batches with a recorded note. It will not
accept anything without one. Recommend reviewing per provider, not in one sweep.

### 3. Pi order: live 34 vs preferred 36
10 preferred entries are missing from the live config and 8 live entries are not in the
preferred list, including `github-copilot/gemini-3.6-flash`, `claude-opus-4.8`,
`opencode-zen/ling-3.0-flash-free` and `huggingface/deepseek-ai/DeepSeek-V4-Flash`.
Either the AGENTS.md list is stale or the live config drifted. This determines whether we
fix the config or update the durable preference, and only Aubrey can say which.

### 4. 14 claims without an immutable capture
12 come from a local Grok thinking-test session (`file://~/.grok/sessions/...`), 2 from
DeepSeek's reasoning API docs. Either capture the session transcript and doc pages as
immutable evidence, or downgrade those claims to unverified.

---

## Proposed — database

1. **Retire v1 leftovers.** `model_capabilities` (745 rows), `pricing_evidence` (175),
   `configurable_models` (746), `provider_summary`, `model_aliases` (0) and `harness_templates`
   are referenced by nothing except the schema. They duplicate v2 data or are dead. Audit each,
   then either drop it or wire it into the CLI. Dropping data needs approval.
2. **Compact `monitoring_runs`.** 8 489 rows in 11 days is ~280 k/year for what is mostly
   "polled, unchanged". Keep full rows for 30 days, then roll older ones into a daily
   per-target aggregate, the same pattern already used by `free_model_probe_daily`.
3. **Compress snapshots.** 247 MB of JSON gzips to roughly a tenth. Store `.json.gz` and verify
   by hashing the decompressed bytes so `response_sha256` keeps its current meaning.
4. **Fix the legacy `idx_catagory` index name** (typo, from v1).
5. **Record schema migrations.** `user_version` is now 2; add a `schema_migrations` table so
   future changes are ordered and replayable rather than applied ad hoc.

## Proposed — CLI

6. **`aimi test <provider> <model>`.** Rule 10 requires a sanitized handshake before enabling a
   newly discovered route, but there is no command to run one and record it in `handshake_tests`.
   This is the biggest missing verb.
7. **`aimi health-run`.** `free-health` only reads. Wrap `free_model_health.py` so an agent can
   refresh health without leaving the CLI.
8. **Data-driven `recommend`.** Scoring hardcodes a family list (`glm`, `kimi`, `nemotron 3`) and
   a `%code%` name match. Replace with capability and benchmark columns so new models rank
   without a code change.
9. **Harness writes beyond Pi.** The skill documents config paths for Droid, OpenCode, Codex,
   Cline, Aside, Antigravity and Vibe, but only Pi has register/select/remove commands.
10. **Consolidate search.** `where`, `model-info` and `maker-models` overlap; an agent has to
    guess. Keep them as aliases over one implementation with explicit flags.

## Proposed — skill

11. **Shrink SKILL.md.** It is 28 KB and loads in full on every use. Move the Grok thinking
    detail, harness testing tables and command cookbook into `references/`, keeping the core
    rules and intent routing under ~10 KB.
12. **Parity test.** Add a check that every `catalogue`/`aimi` command named in SKILL.md exists
    in `aimi commands`. The skill currently documents wrapper verbs that are easy to drift.
13. **Single source for the Pi order.** The durable order lives in both `~/.pi/agent/AGENTS.md`
    and the database profile. Name one as authoritative and have the other cite it.

## Proposed — monitoring

14. **Alert when a model in Pi's order disappears from its endpoint.** The notifier alerts on
    additions only. A removal or an ended free window that affects a model actually configured
    in a harness is the higher-value alert.
15. **Weekly free-health job.** 80 of 146 free routes are red and untested since the scheduled
    jobs were removed, so free-model answers get less reliable each week. Free-only, bounded,
    exact-OK, per the existing rules.

## Proposed — testing

16. **`selftest.py`.** The fresh-checkout install test run tonight was ad hoc. Make it a script:
    clean checkout, install, run every read command, assert exit 0, assert validation passes on
    an empty database. This is what protects the cross-platform claim.
