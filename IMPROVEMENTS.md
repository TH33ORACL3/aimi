# AIMI improvement plan

Status updated 2026-08-27. Items in "Done" shipped in commits `78fdd2f` and `590772d`,
plus the approved notification QoL patch in this working tree. Everything under "Needs a
decision" and "Proposed" is deliberately **not** implemented, because it either changes
authoritative data or changes a policy Aubrey set.

---

## Done

### Round 3 (2026-08-27, approved)

| Area | Change |
|---|---|
| Phone alerts | Added unambiguous `🆕 ADDED`, `🗑️ REMOVED`, `⏰ FREE ACCESS ENDED`, `🔄 RESYNC`, and provider-status labels. |
| Phone alerts | Removed suppressed bulk-sync routes from the new-model cards and replaced them with a resync/endpoint-observation summary. |
| Delivery | Long Telegram alerts now split into bounded parts; the durable outbox records the next part and advances the watermark only after all parts succeed. |
| Health | Weekly free-model SQLite connections now wait up to 30 seconds and retry transient lock errors with bounded backoff. |
| Release desk | Pi verification timeout is bounded to 15 minutes by default, configurable with `AIMI_RELEASE_DESK_PI_TIMEOUT_SECONDS`. |
| Tests/docs | Added formatter, split-delivery, retry, and updated job/status documentation coverage. |

---

### Round 2 (2026-08-01, after review)

| Area | Change |
|---|---|
| Event log | 460 volatile-timestamp false positives removed, 15 monitoring runs corrected to `unchanged` (`correct_volatile_changes.py`, reusing the monitor's own volatile-field definition) |
| Event log | Remaining 1 668 changes reviewed in labelled per-provider batches; backlog is zero |
| Validation | Pi order check replaced. The recorded order is a snapshot, not a preference, so drift is now a metric. The real check is whether an enabled model still exists at its provider |
| Evidence | `repair_claims.py`: 2 claims linked to a real 45 KB capture of DeepSeek's docs, 12 downgraded to `unverified` because their source file no longer exists |
| Validation | `confident_claims_have_capture` replaces the blunt check: only claims asserting confidence need a capture |
| CLI | `aimi test <provider> <model>` — one sanitized handshake, green/orange/red, recorded in `handshake_tests`, refuses paid/subscription routes without `--allow-paid` |
| Alerts | Discovery notifier now reports **removals as well as additions at every provider**, flags removals that match a locally configured model, and summarises long provider sweeps to stay inside Telegram's limit |
| Monitoring | Weekly job `aimi-free-model-health-weekly` (`2cbae684a4a1`) restored, covering every verified free route including NVIDIA NIM |
| Diagnostics | Empty provider error bodies no longer stored as `{}`; the HTTP status and alternative fields are used instead |

**Validation now passes 16/16.**

### Round 1 (2026-08-01)

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

### RESOLVED — 460 false-positive rows (deleted)
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

## Needs a decision

### 1. NVIDIA NIM "red" routes are mostly not entitlement failures
The first weekly health pass returned 41 green, 1 orange, 83 red, and 79 of the red are NVIDIA NIM.
Once empty error bodies were made legible, the actual causes were:

- **HTTP 404 `Function '<uuid>': Not found for account`** — the route is listed on NIM's public
  `/v1/models` endpoint but is not enabled for Aubrey's account. It is not broken; it is not available.
- **HTTP 529 `Service temporarily overloaded`** — transient. `deepseek-v4-flash` failed in the batch
  and returned exact `OK` minutes earlier and later.

Calling both of these "red" makes the free-model picture look far worse than it is, and re-probing
unentitled routes every week wastes developer-tier quota.

- **Option A** — add a `not_entitled` state for account-scoped 404s, exclude them from weekly probing, and re-check them monthly.
- **Option B** — treat 529 as orange (inconclusive, like rate limiting) and retry once before recording.
- **Option C** — both.
- **Option D** — leave the classification as it is.

### 2. Pi order in AGENTS.md
`~/.pi/agent/AGENTS.md` still says "Keep Pi's `enabledModels` order as follows" over a 36-model list.
You have said that number moves up and down normally, so that wording reads as a hard invariant it
was never meant to be. Suggested replacement: keep the list as a *reference snapshot* with a note
that live config wins and the count fluctuating is expected. Say the word and I will edit it.

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

6. ~~`aimi test <provider> <model>`~~ **Done.**
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

14. ~~Alert when a model disappears~~ **Done**, and expanded to every provider for both additions
    and removals, with local-impact flagging.
15. ~~Weekly free-health job~~ **Done** (`2cbae684a4a1`).
16. **Filter non-chat routes out of health probes.** Some listed routes are embedding, rerank or
    vision models that can never satisfy an exact-OK chat handshake. Detect them from modalities or
    task metadata rather than probing them weekly.

## Proposed — testing

16. **`selftest.py`.** The fresh-checkout install test run tonight was ad hoc. Make it a script:
    clean checkout, install, run every read command, assert exit 0, assert validation passes on
    an empty database. This is what protects the cross-platform claim.
