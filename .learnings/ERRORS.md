# Errors

## [ERR-20260807-001] Vercel model-list parsing

**Logged**: 2026-08-07T01:02:22+02:00
**Priority**: low
**Status**: resolved
**Area**: infra

### Summary
Initial `jq` formatting assumed scalar pricing values, but Vercel's model API returns a nested pricing object and some null fields.

### Error
```text
object is not valid in a csv row
null cannot be parsed as a number
```

### Context
- Endpoint: `GET https://ai-gateway.vercel.sh/v1/models`
- The endpoint itself succeeded and returned 317 models.

### Suggested Fix
Extract `pricing.input` and `pricing.output` as strings, treating null as unknown before classifying zero-price routes.

### Metadata
- Reproducible: yes
- Related Files: `/tmp/vercel-ai-gateway-models.json`
- Tags: vercel, ai-gateway, jq

### Resolution
- **Resolved**: 2026-08-07T01:02:22+02:00

---

## [ERR-20260805-001] Agent exploration request

**Logged**: 2026-08-05T10:33:28+02:00
**Priority**: low
**Status**: pending
**Area**: infra

### Summary
The read-only Explore agent could not start because the configured provider credit balance was below the requested maximum token budget.

### Error
```text
402: This request requires more credits, or fewer max_tokens. You requested up to 64000 tokens, but can only afford 60845.
```

### Context
- Attempted a read-only codebase search for the model-discovery Telegram notifier.
- Continued with direct local `rg`/`fd` inspection instead.

### Suggested Fix
Use a lower-token agent request or direct local search when the target repository is already known.

### Metadata
- Reproducible: unknown
- Related Files: `model_discovery_notifier.py`
- Tags: agent, credits, exploration

---

## [ERR-20260805-002] notifier unit test expectation

**Logged**: 2026-08-05T10:37:00+02:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
The first focused notifier test run failed because the new formatter correctly displayed the fixture's known context/output values while the test expected them to be unknown.

### Error
```text
AssertionError: 'Context window: Unknown' not found
```

### Context
- Test: `test_route_addition_and_removal_are_queued_and_sent_once`
- The synthetic route fixture contains a 1,000-token context and 200-token output limit.

### Suggested Fix
Align assertions with the fixture's explicit metadata.

### Metadata
- Reproducible: yes
- Related Files: `tests/test_model_discovery_notifier.py`, `model_discovery_notifier.py`
- Tags: tests, formatter, metadata

### Resolution
- **Resolved**: 2026-08-05T10:37:00+02:00
- **Notes**: Updated the assertions to expect the known context/output values and unknown input/capability values.

---

## [ERR-20260805-003] Python 3.11 notifier syntax compatibility

**Logged**: 2026-08-05T10:38:00+02:00
**Priority**: high
**Status**: resolved
**Area**: tests

### Summary
The initial formatting implementation used nested quote expressions in f-strings that parse on Python 3.14 but fail under the Hermes job's supported Python 3.11 runtime.

### Error
```text
SyntaxError: f-string: unmatched '('
```

### Context
- Python 3.14 `py_compile` passed.
- Hermes venv import under Python 3.11 failed at `format_route_card`.

### Suggested Fix
Avoid quote-heavy expressions inside f-strings and compute route/endpoint values before constructing the formatted lines.

### Metadata
- Reproducible: yes
- Related Files: `model_discovery_notifier.py`, `~/.hermes/scripts/model-catalogue-discovery-notifier.sh`
- Tags: python311, syntax, compatibility

### Resolution
- **Resolved**: 2026-08-05T10:38:00+02:00
- **Notes**: Precomputed `route_id` and `endpoint`; the notifier now avoids Python 3.11-incompatible nested f-string expressions.

---

## [ERR-20260805-004] GenRM special-format shell test

**Logged**: 2026-08-05T11:37:10+02:00
**Priority**: medium
**Status**: resolved
**Area**: tests

### Summary
A one-off Hyperfine test for the GenRM-specific message format initially did not execute successfully.

### Error
```text
Command terminated with non-zero exit code 127, then the corrected bash wrapper exited 2.
```

### Context
- The first attempt used shell features under Hyperfine's default shell.
- The second attempt used a temporary bash script but still exited before reporting an HTTP result, so it was not used as evidence.
- The standard AIMI handshake retest completed separately and returned the same HTTP 404 as the first test.

### Suggested Fix
Use the already verified `catalogue test` path for route availability, or debug the temporary script without enabling shell tracing that could expose credentials.

### Metadata
- Reproducible: unknown
- Related Files: `handshake.py`
- Tags: hyperfine, nvidia-nim, genrm

### Resolution
- **Resolved**: 2026-08-05T11:38:25+02:00
- **Notes**: Re-ran the official GenRM input format through a corrected bash wrapper. It returned HTTP 404 with no choices, confirming the hosted route remains unavailable.

## [ERR-20260805-AIMI-001] documented_catalogue_wrapper_path

**Logged**: 2026-08-05T18:59:02Z
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
The AIMI skill-documented `./scripts/catalogue` wrapper path is absent in the current checkout.

### Error
```
/bin/bash: ./scripts/catalogue: No such file or directory
```

### Context
- Attempted `./scripts/catalogue summary` and `./scripts/catalogue changes --provider ollama-cloud --limit 20` from the AIMI project root.
- The skill documents the wrapper, but the local project requires its actual available entry point.

### Suggested Fix
Inspect the current project entry points before invoking the documented wrapper.

### Metadata
- Reproducible: yes
- Related Files: /Users/TH33_ORACL3/AZ Labs/2 - Testing/AIMI
- Tags: aimi, catalogue, wrapper-path

### Resolution
- **Resolved**: 2026-08-05T18:59:02Z
- **Notes**: Continuing by locating the local `aimi` entry point and using the live Ollama endpoint directly where appropriate.

---

## [ERR-20260811-001] free-image-health-query

**Logged**: 2026-08-11T14:22:02+02:00
**Priority**: low
**Status**: pending
**Area**: tooling

### Summary
A diagnostic SQLite query referenced a non-existent `free_model_probe_status.result_description` column.

### Error
```text
Parse error in 3rd command line argument: no such column: s.result_description
```

### Context
- Querying free image-generation route health in `aimi.db`.
- The query otherwise used the correct provider/model filters.

### Suggested Fix
Inspect the live table schema before selecting probe fields; use only columns present in `free_model_probe_status`.

### Metadata
- Reproducible: yes
- Related Files: `aimi.db`, `schema_v2.sql`
- Tags: aimi, sqlite, schema

---

## [ERR-20260811-002] image-harness-query

**Logged**: 2026-08-11T14:22:02+02:00
**Priority**: low
**Status**: pending
**Area**: tooling

### Summary
A diagnostic SQLite query used guessed column names for the cached harness-model table.

### Error
```text
Parse error in 3rd command line argument: no such column: h.harness_id
```

### Context
- Querying whether image-generation candidates are configured in a local harness.
- The live table uses `configured_model_identifier` and `installation_id` instead.

### Suggested Fix
Inspect the live table schema before joining cached harness records.

### Metadata
- Reproducible: yes
- Related Files: `aimi.db`, `schema_v2.sql`
- Tags: aimi, sqlite, harness, schema

---

## [ERR-20260811-003] image-provider-test-python-command

**Logged**: 2026-08-11T16:34:57+02:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
The default `python` command is not installed on this macOS environment.

### Error
```text
/bin/bash: python: command not found
```

### Context
- Checking whether `huggingface_hub` was installed before testing an image endpoint.
- The environment provides `python3` instead.

### Suggested Fix
Use `python3` for local Python checks and scripts.

### Metadata
- Reproducible: yes
- Related Files: none
- Tags: python, macos, image-generation, testing

### Resolution
- **Resolved**: 2026-08-11T16:34:57+02:00
- **Notes**: Re-ran the import check with `python3`; `huggingface_hub` is installed.

---

## [ERR-20260811-004] cloudflare-image-response-shape

**Logged**: 2026-08-11T16:34:57+02:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
The first Cloudflare Workers AI image test assumed the REST response was a raw image, but the endpoint returned JSON containing a base64-encoded image.

### Error
```text
HTTP 200; content_type=application/json; file=JSON data
```

### Context
- Route: `@cf/black-forest-labs/flux-1-schnell`
- The provider returned `success: true` and `result.image`; the test harness classified it as a failure because it only accepted image MIME types.

### Suggested Fix
Decode `.result.image` from the successful JSON response before validating the generated image file.

### Metadata
- Reproducible: yes
- Related Files: temporary Cloudflare image test script
- Tags: cloudflare, workers-ai, image-generation, response-format

### Resolution
- **Resolved**: 2026-08-11T16:34:57+02:00
- **Notes**: Confirmed the response is successful and updated the test logic to base64-decode the image payload.

---

## [ERR-20260811-003] pi-install-settings

**Logged**: 2026-08-11T16:03:00+02:00
**Priority**: medium
**Status**: resolved
**Area**: config

### Summary
`pi install` rewrote the future default model/provider to the active session's environment values.

### Error
```text
Before: deepseek-v4-flash-free / opencode-zen
After:  gpt-5.6-luna / github-copilot
```

### Context
- Ran `PI_TELEMETRY=false pi install npm:pi-agentsmd` from a Pi session exporting `PI_MODEL=gpt-5.6-luna` and `PI_PROVIDER=openai-codex`.
- The package installed successfully, but `~/.pi/agent/settings.json` changed its default model/provider.

### Suggested Fix
After every `pi install`, verify `defaultModel` and `defaultProvider`. When installing from a live Pi session, preserve the prior settings or run the install from a shell without runtime model/provider environment variables.

### Metadata
- Reproducible: unknown
- Related Files: `~/.pi/agent/settings.json`
- Tags: pi, package-install, settings, model-default

### Resolution
- **Resolved**: 2026-08-11T16:03:00+02:00
- **Notes**: Restored `deepseek-v4-flash-free` / `opencode-zen` and verified `pi-agentsmd` remains installed.

---

## [ERR-20260811-CCR-SHELL] Inline verification shell quoting

**Logged**: 2026-08-11T15:54:00+02:00
**Priority**: low
**Status**: resolved
**Area**: infra

### Summary
A long inline Bash verification command failed before execution because nested JSON/Python quoting produced an unmatched shell quote.

### Error
```text
/bin/bash: -c: line 1: syntax error: unexpected end of file
```

### Context
- During the final CCR verification pass.
- No configuration command in that failed shell reached the system.

### Suggested Fix
Use a quoted temporary script for multi-layer Bash/Python/JSON checks instead of embedding nested quoting in one command string.

### Metadata
- Reproducible: yes
- Related Files: `/tmp/verify-ccr.sh`
- Tags: shell, quoting, verification

### Resolution
- **Resolved**: 2026-08-11T15:54:00+02:00
- **Notes**: Reran the verification through a temporary script; all three CCR routes passed.

---

## [ERR-20260811-005] cloudflare-image-content-filter

**Logged**: 2026-08-11T16:39:22+02:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
Cloudflare FLUX rejected a harmless apple test prompt as NSFW, while a neutral vase prompt succeeded.

### Error
```text
HTTP 400: AiError: Input prompt contains NSFW content.
```

### Context
- Route: `@cf/black-forest-labs/flux-1-schnell`
- The same route returned a valid 1024x1024 JPEG for a neutral watercolor vase prompt.

### Suggested Fix
Use neutral prompts when smoke-testing the route; treat this as a content-filter false positive, not an endpoint outage.

### Metadata
- Reproducible: yes
- Related Files: temporary Cloudflare image test script
- Tags: cloudflare, workers-ai, image-generation, content-filter

### Resolution
- **Resolved**: 2026-08-11T16:39:22+02:00
- **Notes**: Retested with a neutral prompt; generation passed.

---

## [ERR-20260811-006] huggingface-explicit-provider-deprecated-model

**Logged**: 2026-08-11T16:39:22+02:00
**Priority**: medium
**Status**: resolved
**Area**: tests

### Summary
Hugging Face's `hf-inference` provider returned HTTP 410 for FLUX models documented in the generic quickstart.

### Error
```text
410 Gone: The requested model is deprecated and no longer supported by provider hf-inference
```

### Context
- Models tested: `black-forest-labs/FLUX.1-dev` and `black-forest-labs/FLUX.1-schnell`.
- Hugging Face `provider="auto"` selected a live provider and generated a valid 512x512 PNG successfully.

### Suggested Fix
Use Hugging Face InferenceClient with `provider="auto"` for current provider routing; do not hard-code `hf-inference` for these FLUX models.

### Metadata
- Reproducible: yes
- Related Files: temporary Hugging Face image test script
- Tags: huggingface, inference-providers, image-generation, provider-routing

### Resolution
- **Resolved**: 2026-08-11T16:39:22+02:00
- **Notes**: The auto-routed FLUX.1-schnell request passed with a valid image.

---

## [ERR-20260811-007] aimi-cloudflare-query-lock

**Logged**: 2026-08-11T16:46:45+02:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
A concurrent SQLite writer temporarily locked `aimi.db` during a Cloudflare model query.

### Error
```text
Parse error in 3rd command line argument: database is locked (5)
```

### Context
- A read query ran while the endpoint monitor or another AIMI process held the database lock.
- A separate legacy-table read completed successfully.

### Suggested Fix
Use SQLite busy timeout/WAL-aware reads and retry after a short bounded delay when the monitor is writing.

### Metadata
- Reproducible: transient
- Related Files: `aimi.db`, `provider_models_v2`
- Tags: aimi, sqlite, wal, cloudflare

### Resolution
- **Resolved**: 2026-08-11T16:46:45+02:00
- **Notes**: Retry the query with `PRAGMA busy_timeout` after the active writer releases the lock.

---

## [ERR-20260811-008] search-shell-quoting

**Logged**: 2026-08-11T16:53:59+02:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
A dual-engine search command broke because an apostrophe inside a single-quoted Antigravity prompt terminated the shell string.

### Error
```text
/bin/bash: -c: line 1: syntax error near unexpected token `newline'
```

### Context
- The prompt included `provider's` inside a single-quoted shell argument.
- Neither search process started.

### Suggested Fix
Use a temporary script or avoid apostrophes in shell-quoted prompts; verify the command before launch.

### Metadata
- Reproducible: yes
- Related Files: temporary search command
- Tags: shell, quoting, search, agy, firecrawl

### Resolution
- **Resolved**: 2026-08-11T16:53:59+02:00
- **Notes**: Rerun with a temporary script and quote-safe prompt text.

---

## [ERR-20260811-009] cloudflare-glm-5.2-free-plan

**Logged**: 2026-08-11T16:58:52+02:00
**Priority**: medium
**Status**: resolved
**Area**: tests

### Summary
Cloudflare's GLM-5.2 route is listed in the catalogue but is unavailable on the current Workers Free plan.

### Error
```text
HTTP 403: Model @cf/zai-org/glm-5.2 is not available on the Workers Free plan; upgrade required.
```

### Context
- Direct route test used the exact prompt `Reply with exactly OK`.
- Cloudflare rejected the request before inference, so no model output or paid inference was incurred.

### Suggested Fix
Check plan-level model eligibility, not only the account-wide Neurons allocation, before recommending a Cloudflare route as usable for free.

### Metadata
- Reproducible: yes
- Related Files: `aimi.db`, temporary GLM test script
- Tags: cloudflare, workers-ai, glm, free-plan, testing

### Resolution
- **Resolved**: 2026-08-11T16:58:52+02:00
- **Notes**: Reported GLM-5.2 as paid-plan-only on the current account; no configuration was changed.

---

## [ERR-20260811-010] cloudflare-kimi-free-plan

**Logged**: 2026-08-11T17:00:58+02:00
**Priority**: medium
**Status**: resolved
**Area**: tests

### Summary
Cloudflare's Kimi K2.7 Code route is listed in the catalogue but unavailable on the current Workers Free plan.

### Error
```text
HTTP 403: Model @cf/moonshotai/kimi-k2.7-code is not available on the Workers Free plan; upgrade required.
```

### Context
- Direct route test used the exact prompt `Reply with exactly OK`.
- GLM-5.2 returned the same plan-gating result in the same batch; Gemma 4 passed.

### Suggested Fix
Check account plan eligibility per model before presenting Cloudflare catalogue entries as usable on the Free plan.

### Metadata
- Reproducible: yes
- Related Files: `aimi.db`, temporary Cloudflare text test script
- Tags: cloudflare, workers-ai, kimi, free-plan, testing
- See Also: ERR-20260811-009

### Resolution
- **Resolved**: 2026-08-11T17:00:58+02:00
- **Notes**: Reported Kimi K2.7 Code as paid-plan-only on the current account; no configuration was changed.

---

## [ERR-20260811-011] hyperfine-unsupported-timeout

**Logged**: 2026-08-11T17:04:29+02:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
The installed Hyperfine version does not support a `--timeout` flag.

### Error
```text
error: unexpected argument '--timeout' found
```

### Context
- Preparing a bounded batch test for all Cloudflare image-generation routes.
- The individual curl commands already use `--max-time 180`.

### Suggested Fix
Use the request-level curl timeout and omit the unsupported Hyperfine option.

### Metadata
- Reproducible: yes
- Related Files: temporary Cloudflare image test script
- Tags: hyperfine, cloudflare, image-generation, testing

### Resolution
- **Resolved**: 2026-08-11T17:04:29+02:00
- **Notes**: Rerun the same batch without Hyperfine's unsupported flag.

---

## [ERR-20260811-012] flux2-retry-shell-command

**Logged**: 2026-08-11T17:04:29+02:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
The first retry command for FLUX.2 dev escaped the shell conjunction incorrectly and never invoked the test script.

### Error
```text
mkdir: .../test_flux2_dev_retry.sh: File exists
```

### Context
- A retry directory was created inside a Hyperfine command using an incorrectly escaped `&&`.
- No Cloudflare request was sent by this failed retry.

### Suggested Fix
Create the directory before Hyperfine and use `env VAR=value command` for per-command environment variables.

### Metadata
- Reproducible: yes
- Related Files: temporary Cloudflare image test script
- Tags: shell, hyperfine, cloudflare, image-generation

### Resolution
- **Resolved**: 2026-08-11T17:04:29+02:00
- **Notes**: Rerun the retry with a pre-created directory and `env`.

---

## [ERR-20260811-013] cloudflare-image-raw-response

**Logged**: 2026-08-11T17:04:29+02:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
Several Cloudflare image routes returned raw JPEG/PNG bodies with HTTP 200 instead of the JSON/base64 response shape used by FLUX.

### Error
```text
HTTP 200 with a valid image body was initially classified as FAIL because the test parser expected JSON.
```

### Context
- Affected routes included SDXL Lightning, Phoenix, DreamShaper, SD 1.5 img2img, and SDXL Base.
- `file` and PIL validation confirmed valid image outputs; DreamShaper's one-step output was black and was retested with documented default steps.

### Suggested Fix
Detect the response content type and validate raw image bodies before parsing JSON errors.

### Metadata
- Reproducible: yes
- Related Files: temporary Cloudflare image test script
- Tags: cloudflare, workers-ai, image-generation, response-format
- See Also: ERR-20260811-004

### Resolution
- **Resolved**: 2026-08-11T17:04:29+02:00
- **Notes**: Classified successful raw image responses correctly; reran DreamShaper with 20 steps and received a nonblank PNG.

---

## [ERR-20260811-014] cloudflare-sd15-inpainting

**Logged**: 2026-08-11T17:04:29+02:00
**Priority**: medium
**Status**: pending
**Area**: tests

### Summary
Cloudflare's Stable Diffusion 1.5 inpainting route returned an internal image-decoding error for valid JPEG and PNG base64 inputs.

### Error
```text
HTTP 500: UnidentifiedImageError: cannot identify image file <_io.BytesIO ...>
```

### Context
- Route: `@cf/runwayml/stable-diffusion-v1-5-inpainting`
- Tested with a valid 256x256 source image and mask using both JPEG and PNG `image_b64` payloads.

### Suggested Fix
Treat the route as currently broken or incompatible with the documented REST payload; investigate with Cloudflare before enabling it.

### Metadata
- Reproducible: yes
- Related Files: temporary Cloudflare image test script
- Tags: cloudflare, workers-ai, stable-diffusion, inpainting

---

## [ERR-20260812-001] ccr-diagnostic-shell-quoting

**Logged**: 2026-08-12T16:41:00+02:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
Two CCR log-filter commands failed because nested Perl and shell quotes were not balanced.

### Error
```text
/bin/bash: unexpected EOF while looking for matching quote
```

### Context
- The commands combined Bash, Perl regexes, and both quote styles.
- No configuration or runtime data was changed.

### Suggested Fix
Prefer structured SQLite/JQ projections and simple fixed filters over nested shell sanitization expressions.

### Metadata
- Reproducible: yes
- Related Files: `~/.claude-code-router/`
- Tags: ccr, shell, quoting, diagnostics

### Resolution
- **Resolved**: 2026-08-12T16:43:00+02:00
- **Notes**: Replaced the fragile filters with SQLite column selection and JQ key redaction.

---

## [ERR-20260812-002] ccr-backup-secret-search-scope

**Logged**: 2026-08-12T16:47:00+02:00
**Priority**: high
**Status**: resolved
**Area**: config

### Summary
A broad recursive CCR search included an old backup JSON file containing literal provider credentials in internal tool output.

### Error
```text
Backup configuration content bypassed the intended structured redaction path.
```

### Context
- The search excluded the large model catalogue but did not exclude every backup directory.
- No secret is included in the user-facing response.

### Suggested Fix
Never recursively print CCR configuration backups. Query live SQLite fields structurally, exclude `backups-*/**`, and project only provider names, model IDs, endpoints, and routing fields.

### Metadata
- Reproducible: yes
- Related Files: `~/.claude-code-router/backups-*/`
- Tags: ccr, secrets, backups, diagnostics

### Resolution
- **Resolved**: 2026-08-12T16:48:00+02:00
- **Notes**: Subsequent diagnostics used structured redaction and no credentials are reported outward.

---

## [ERR-20260812-003] codex-quota-script-exec-bit

**Logged**: 2026-08-12T16:44:00+02:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
The installed `codex-quota.py` file is not executable directly.

### Error
```text
Permission denied
```

### Context
- Direct invocation failed before reading quota data.
- Running the same script with `python3` succeeded.

### Suggested Fix
Invoke this installed skill as `python3 ~/.agents/skills/codex-quota/codex-quota.py` unless its executable bit is deliberately added.

### Metadata
- Reproducible: yes
- Related Files: `~/.agents/skills/codex-quota/codex-quota.py`
- Tags: codex, quota, permissions, python

### Resolution
- **Resolved**: 2026-08-12T16:45:00+02:00
- **Notes**: Used `python3`; cached quota had no primary or secondary window values.

---

## [ERR-20260812-004] backup-reaper-dry-run-flag

**Logged**: 2026-08-12T16:50:00+02:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
The installed backup reaper rejected the documented `--dry-run` flag.

### Error
```text
backup-reaper: error: unrecognized arguments: --dry-run
```

### Context
- `backup-reaper --smoke-test` passed first.
- The installed command performs a dry run by default when called with no arguments.

### Suggested Fix
Use `backup-reaper` with no arguments for dry-run output; reserve `--apply` for pruning.

### Metadata
- Reproducible: yes
- Related Files: `~/.local/bin/backup-reaper`, `~/.agents/backup-inventory.md`
- Tags: backups, reaper, cli, documentation-drift

### Resolution
- **Resolved**: 2026-08-12T16:50:00+02:00
- **Notes**: Reran without arguments; it reported 24 files that would be pruned and made no deletions.

---

## [ERR-20260812-005] aimi-harness-models-jq-shape

**Logged**: 2026-08-12T18:02:00+02:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
A jq filter assumed `aimi harness-models pi` returned an object with a `models` array, but the command returns a top-level array.

### Error
```text
jq: error: Cannot index array with string ("models")
```

### Context
- Attempted to filter Pi's live model inventory for `grok-4.6`.
- The command's JSON output is a top-level array of model records.

### Suggested Fix
Filter with `.[] | select(...)`, not `.models[]`.

### Metadata
- Reproducible: yes
- Related Files: `aimi`
- Tags: aimi, jq, output-contract

### Resolution
- **Resolved**: 2026-08-12T18:02:00+02:00
- **Notes**: Inspected the JSON type and corrected the filter shape.

---

## [ERR-20260812-006] hermes-cron-list-json

**Logged**: 2026-08-12T18:42:00+02:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
The installed Hermes CLI does not support `hermes cron list --json`.

### Error
```text
hermes: error: unrecognized arguments: --json
```

### Context
- The current Hermes docs/skill list cron commands but do not promise JSON output for `cron list`.
- The live cron inventory was needed before editing the AIMI job.

### Suggested Fix
Use `hermes cron list` and treat the installed CLI help as authoritative.

### Metadata
- Reproducible: yes
- Related Files: `~/.agents/skills/hermes-cli/SKILL.md`
- Tags: hermes, cron, cli, json

### Resolution
- **Resolved**: 2026-08-12T18:43:00+02:00
- **Notes**: Read the plain-text live inventory and confirmed the target job.

---

## [ERR-20260812-007] explore-agent-openrouter-credit

**Logged**: 2026-08-12T18:45:00+02:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
Two read-only Explore agents failed before using tools because their requested output budget exceeded the remaining OpenRouter credit.

### Error
```text
HTTP 402: requested up to 64000 tokens; remaining credit supported 43917
```

### Context
- The agents were only intended to map notifier and editorial automation surfaces.
- Both failed at startup with zero tool calls, so no delegated work was duplicated.

### Suggested Fix
Use a model/provider whose output budget fits available credit, or perform the bounded known-path inspection directly.

### Metadata
- Reproducible: unknown
- Related Files: none
- Tags: subagent, openrouter, credits, exploration

### Resolution
- **Resolved**: 2026-08-12T18:46:00+02:00
- **Notes**: Continued with direct inspection of known files and CLI state.

---

## [ERR-20260812-008] grok-classification-investigation-noise

**Logged**: 2026-08-12T18:56:00+02:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
A parallel AIMI lookup pass produced avoidable environment errors while investigating Grok 4.6 classification.

### Error
```text
Live harness scan failed: sqlite3.OperationalError: database is locked
Provider/model query failed: no such table: field_level_claims
cd: .../AZ Labs - Live: No such file or directory
```

### Context
- `where --refresh-harnesses` and `harness-models` were launched concurrently, causing two writers to contend on AIMI's SQLite WAL.
- A stale SQL table name was queried outside the supported AIMI schema.
- The editorial skill's old repository path differed from the actual `AZLabs` checkout.

### Suggested Fix
Run one live harness scan at a time, use `catalogue where ... --no-harnesses` for read-only lookups, query only schema-backed tables, and verify canonical repository paths before `cd`.

### Metadata
- Reproducible: yes
- Related Files: `aimi`, `scan_local_harnesses.py`, `~/.agents/skills/azlabs-editorial-publishing/SKILL.md`
- Tags: aimi, sqlite, worktree, path, investigation

### Resolution
- **Resolved**: 2026-08-12T18:57:00+02:00
- **Notes**: Re-ran read-only lookups serially, validated the classifier against a temporary DB copy, and verified the live AZLabs article without modifying unrelated files.

---

## [ERR-20260812-009] claude-3p-desktop-write-race

**Logged**: 2026-08-12T18:50:00+02:00
**Priority**: high
**Status**: resolved
**Area**: config

### Summary
The first semantic repair wrote Desktop-owned config while Claude was running, and Desktop immediately rewrote it.

### Error
```text
Repair completed with unresolved claude_desktop_config.json drift.
```

### Context
- CCR fallback and seven other semantic changes applied successfully.
- Only the running Electron app's preference file raced.

### Suggested Fix
Defer Desktop profile and preference writes while the app is running; merge them after a controlled quit.

### Metadata
- Reproducible: yes
- Related Files: `~/.claude/3p-persistence/claude-3p.py`, `~/Library/Application Support/Claude-3p/claude_desktop_config.json`
- Tags: claude-desktop, persistence, race, semantic-merge

### Resolution
- **Resolved**: 2026-08-12T18:51:00+02:00
- **Notes**: Added deferred Desktop writes and applied them during the approved stopped-app repair.

---

## [ERR-20260812-010] claude-3p-process-detector

**Logged**: 2026-08-12T18:52:00+02:00
**Priority**: medium
**Status**: resolved
**Area**: tests

### Summary
The first Desktop relaunch validator mistook diagnostic shell text or an exiting helper for a non-bypass Claude worker.

### Error
```text
Desktop relaunched but an active agent is not in bypass mode
```

### Context
- Saved session metadata already showed bypassPermissions and clean model IDs.
- Live post-relaunch requests used Sol through Codex successfully.

### Suggested Fix
Anchor detection to actual Claude Desktop CLI executable prefixes and wait for old helper children to exit before reopening.

### Metadata
- Reproducible: yes
- Related Files: `~/.claude/3p-persistence/claude-3p.py`
- Tags: claude-desktop, process-detection, false-positive, relaunch

### Resolution
- **Resolved**: 2026-08-12T18:53:00+02:00
- **Notes**: Anchored process matching and added bounded child-exit/start waits.

---

## [ERR-20260812-011] claude-security-hook-unqualified-model

**Logged**: 2026-08-12T19:05:00+02:00
**Priority**: high
**Status**: resolved
**Area**: config

### Summary
A plain Claude smoke test failed because an official security hook spawned an unqualified Anthropic Opus model against CCR.

### Error
```text
API Error: 400 All target providers failed.
```

### Context
- CCR fallback was correctly off, so the bad auxiliary model failed visibly rather than substituting DeepSeek.
- The main desired model route itself was healthy.

### Suggested Fix
Set `SECURITY_REVIEW_MODEL` to a configured CCR model alias and inject the desired main model alias explicitly in the terminal launcher.

### Metadata
- Reproducible: yes
- Related Files: `~/bin/claude`, `~/.claude/3p-persistence/desired-state.json`
- Tags: claude-code, security-hook, ccr, model-routing, no-fallback

### Resolution
- **Resolved**: 2026-08-12T19:07:00+02:00
- **Notes**: Final Hyperfine smoke returned OK; main DeepSeek and auxiliary GPT-5.6 Luna requests each used OpenCode Go with HTTP 200 and one attempt.

---

## [ERR-20260812-012] azlabs-editorial-stale-repo-path

**Logged**: 2026-08-12T19:12:00+02:00
**Priority**: medium
**Status**: resolved
**Area**: docs

### Summary
The editorial skill's canonical repository path used a directory name that no longer exists.

### Error
```text
cd: /Users/TH33_ORACL3/AZ Labs/3 - Production/AZ Labs_SMB Acquire_Previews/AZ Labs - Live: No such file or directory
```

### Context
- The live repository is now `/Users/TH33_ORACL3/AZ Labs/3 - Production/AZ Labs_SMB Acquire_Previews/AZLabs`.
- The repository remote still correctly points to `AZLabsAI/AZLabs.ai`.

### Suggested Fix
Update the canonical repository path in the `azlabs-editorial-publishing` skill after explicit approval to edit the global skill library.

### Metadata
- Reproducible: yes
- Related Files: `/Users/TH33_ORACL3/.agents/skills/azlabs-editorial-publishing/SKILL.md`
- Tags: editorial, repository-path, stale-documentation

### Resolution
- **Resolved**: 2026-08-12T19:12:00+02:00
- **Notes**: Located and used the verified AZLabs repository without changing the global skill file.

---

## [ERR-20260812-013] cline-extension-package-jq-input

**Logged**: 2026-08-12T19:17:00+02:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
A jq scan of local extension package files referenced a nonexistent `input_filename` value after stdin piping.

### Error
```text
jq: parse error: Invalid numeric literal
```

### Context
- The scan was an optional local Cline installation check.
- No Cline installation was found, and the official source/API investigation continued unaffected.

### Suggested Fix
Pass the filename explicitly with `--arg file "$f"` when piping each package.json into jq.

### Metadata
- Reproducible: yes
- Related Files: none
- Tags: jq, cline, extension-scan, diagnostics

### Resolution
- **Resolved**: 2026-08-12T19:17:00+02:00
- **Notes**: Used GitHub source search to locate Cline's actual live model-catalog endpoint.

---

## [ERR-20260812-014] aimi-timeline-missing-since

**Logged**: 2026-08-12T21:06:17+02:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
The AIMI timeline command was called with a model query, but the command requires a `--since` time range.

### Error
```text
usage: aimi timeline [-h] --since SINCE [--until UNTIL]
aimi timeline: error: the following arguments are required: --since
```

### Context
- Attempted `./aimi timeline 'LFM2.5-2.6B'` during a model-release desk run.
- The timeline command is day/time based rather than model-query based.

### Suggested Fix
Call `./aimi timeline --since <ISO-8601> --until <ISO-8601>` and filter the returned JSON by canonical model or route when needed.

### Metadata
- Reproducible: yes
- Related Files: `aimi`
- Tags: aimi, timeline, cli, release-desk

### Resolution
- **Resolved**: 2026-08-12T21:06:17+02:00
- **Notes**: Corrected the invocation to use the SAST-day UTC bounds from the input package.

---

## [ERR-20260812-015] bird-read-auth-unavailable

**Logged**: 2026-08-12T21:07:50+02:00
**Priority**: medium
**Status**: pending
**Area**: config

### Summary
The read-only Bird client could not search X because no usable X cookies or token credentials were available.

### Error
```text
Missing auth_token and ct0. Safari and Chrome cookie reads were denied or unavailable.
```

### Context
- Attempted a read-only search for `"LFM2.5-2.6B"` during a model-release verification run.
- `bird check` confirmed both required credentials were missing.
- Liquid AI's official announcement page independently established the model's publication date, so X evidence was not required for the release decision.

### Suggested Fix
Restore Bird's read-only credentials for @Prompt_Lee, then rerun `bird check` before future X searches.

### Metadata
- Reproducible: yes
- Related Files: `/Users/TH33_ORACL3/.config/bird/config.json5`
- Tags: bird, x, authentication, release-desk

---

## [ERR-20260812-016] bsd-date-colon-timezone-format

**Logged**: 2026-08-12T21:08:38+02:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
BSD `date` did not support the GNU `%:z` timezone directive and emitted a literal `:z` in package JSON.

### Error
```text
"created_at": "2026-08-12T21:08:38:z"
```

### Context
- The release-desk package requires a valid ISO-8601 timestamp.
- The first atomic write passed structural checks that did not parse the timestamp.

### Suggested Fix
Generate ISO-8601 timestamps with Python `datetime.now().astimezone().isoformat(timespec="seconds")` on macOS and validate with `datetime.fromisoformat` before the atomic rename.

### Metadata
- Reproducible: yes
- Related Files: `/Users/TH33_ORACL3/.hermes/ops/model-release-desk/packages/20260812-7299095f13.json`
- Tags: macos, bsd-date, iso-8601, json

### Resolution
- **Resolved**: 2026-08-12T21:09:00+02:00
- **Notes**: Rewrote the package atomically with a parsed ISO-8601 timestamp and stronger validation.

---

## [ERR-20260812-017] stale-aimi-verification-subcommands

**Logged**: 2026-08-12T21:36:00+02:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
The AI-model-index skill instructed verification with `aimi scan` and `aimi validate`, but the installed AIMI CLI exposes neither subcommand.

### Error
```text
argument <command>: invalid choice: 'scan'
argument <command>: invalid choice: 'validate'
```

### Context
- Applied `aimi pi-register openrouter liquid/lfm-2.5-2.6b:free --apply` and `aimi pi-select openrouter liquid/lfm-2.5-2.6b:free --apply` successfully.
- The stale verification commands ran afterward and failed; the Pi write itself was unaffected.
- Available checks used instead: `aimi harness-models pi`, `aimi pi-order`, `aimi order-diff pi`, and `aimi doctor`.

### Suggested Fix
Update the AI-model-index skill and any workflow references to use the current CLI manifest. Keep `aimi doctor` as the integrity check unless a future CLI adds a dedicated validation command.

### Metadata
- Reproducible: yes
- Related Files: `/Users/TH33_ORACL3/.agents/skills/ai-model-index/SKILL.md`, `/Users/TH33_ORACL3/AZ Labs/2 - Testing/AIMI/aimi`
- Tags: aimi, cli, stale-docs, verification

### Resolution
- **Resolved**: 2026-08-12T21:36:00+02:00
- **Notes**: Verified the new route is enabled at Pi position 19, present at the provider, and `aimi doctor` reports no Pi-enabled models missing at provider.

---

## [ERR-20260812-018] pi-ollama-lfm2.5-smoke-timeout

**Logged**: 2026-08-12T21:56:00+02:00
**Priority**: medium
**Status**: resolved
**Area**: config

### Summary
The newly enabled local Ollama LFM2.5-2.6B route did not complete Pi's full tool-enabled `Reply with exactly OK` smoke test within 240 seconds.

### Error
```text
Command timed out after 240 seconds
```

### Context
- Route: `ollama/hf.co/LiquidAI/LFM2.5-2.6B-GGUF:Q4_K_M`
- Pi settings write succeeded at position 20.
- Ollama reports the model loaded on GPU with a 128K context.
- The route is reasoning-capable and Pi's current configured reasoning level is high.
- Direct Ollama OpenAI-compatible request returned `OK`; Pi with `--thinking off --no-tools` returned `OK` in 12.1s; Pi with `--thinking minimal --no-tools` returned `OK` in 7.8s; Pi with `--thinking high --no-tools` returned `OK` in 12.6s.

### Suggested Fix
Use the local route for text-only or explicitly no-tools tasks. If tool-enabled Pi use is required, run a separate bounded tool-call compatibility test before routing tools to this model.

### Metadata
- Reproducible: yes
- Related Files: `/Users/TH33_ORACL3/.pi/agent/models.json`, `/Users/TH33_ORACL3/.pi/agent/settings.json`
- Tags: pi, ollama, lfm2.5, timeout, reasoning, tools

### Resolution
- **Resolved**: 2026-08-12T21:58:00+02:00
- **Notes**: The Ollama route is wired and works through Pi for no-tools prompts. The timeout is isolated to the full tool-enabled smoke prompt; no configuration rollback was needed.

---

## [ERR-20260813-019] aside-x-session-preflight-routing

**Logged**: 2026-08-13T13:38:00+02:00
**Priority**: medium
**Status**: resolved
**Area**: tooling

### Summary
Fresh Aside CLI sessions could not attach Profile 0, and a resumed session retained its no-credit OpenCode model despite CLI model overrides.

### Error
```text
Aside Browser profile for account u0 is not connected to the daemon.
OpenAI API error (401): Insufficient balance.
```

### Context
- X publishing required a logged-in browser UI and account verification.
- Opening Aside and x.com did not bind a fresh CLI session to Profile 0.
- Resuming an existing bound session worked, but its stored model route overrode `-p` and `-m` CLI flags.

### Suggested Fix
Resume a recent browser-bound X session whose stored model route is healthy, or create a fresh bound task inside the Aside UI before invoking CLI automation.

### Metadata
- Reproducible: yes
- Related Files: `/Users/TH33_ORACL3/.aside/u/0/state.db`, `/Users/TH33_ORACL3/.agents/skills/aside-browser/SKILL.md`
- Tags: aside, x, browser-binding, model-routing, credits

### Resolution
- **Resolved**: 2026-08-13T13:38:00+02:00
- **Notes**: Switched to the existing X-bound session `OoxT0wTvhMODD3Kd`, configured for the working OpenCode Go route.

---

## [ERR-20260813-Aside-beachball] aside-profile-iconservices-loop

**Logged**: 2026-08-13T14:56:00+02:00
**Priority**: high
**Status**: resolved
**Area**: tooling

### Summary
Aside 1.0.813.1 repeatedly beachballed because its AZ Labs profile spawned excessive renderer/UI work and entered an IconServices/AppKit loop.

### Error
```text
Aside main process reached ~100% CPU; renderer count rose to 33 and total Aside RSS reached ~5.6 GB.
macOS fault report: ExcUserFault_Aside-2026-08-13-141913.ips; hot path included NSWorkspace setIcon:forFile:options: via IconServices.
```

### Context
- Trigger became apparent after registering additional Cline models, but rolling Cline back from 11 models to the last-known-good single `cline-pass/deepseek-v4-flash` model did not stop the loop.
- A clean disposable Aside profile stayed responsive at ~1–18% CPU, proving the app binary was not inherently broken.
- Four duplicate X replies routines were active and were paused during containment.
- Stale session/tab restore files, stale browser bindings, old failed sessions, service-worker cache, and third-party extension state were quarantined or archived reversibly.

### Suggested Fix
Keep Cline at one model until the profile is stable; retain the quarantined artifacts for rollback. Reintroduce extensions/models one at a time only after Aside remains stable.

### Metadata
- Reproducible: yes before profile cleanup, no after cleanup
- Related Files: `~/.aside/u/0/models.json`, `~/.aside/u/0/settings.json`, `~/.aside/u/0/state.db`, `~/Library/Application Support/Aside/Default/Service Worker/`, `~/Library/Application Support/Aside/Default/Extensions/`
- Tags: aside, beachball, cline, iconservices, renderer-leak, profile-corruption

### Resolution
- **Resolved**: 2026-08-13T14:56:00+02:00
- **Notes**: Cline restored to one model; invalid default repaired; duplicate X routines paused; stale sessions archived; restore files, service-worker cache, and third-party extension state quarantined. Aside passed a two-minute stability test at ~0.5–2% CPU and ~1.35 GB total RSS, and `https://example.com` opened in 655 ms.

---
## [ERR-20260813-020] aimi-timeline-and-bird-auth

**Logged**: 2026-08-13T18:45:00+02:00
**Priority**: medium
**Status**: resolved
**Area**: config

### Summary
The first AIMI timeline invocation used the wrong argument shape, and Bird could not read local browser cookies.

### Error
`aimi timeline` requires `--since`; Bird reported missing `auth_token` and `ct0` after cookie access failures.

### Context
- Attempted `./aimi timeline 'Gemini 3.7 Flash'` instead of a date range.
- Attempted official-account search with Bird's default browser-cookie authentication.

### Suggested Fix
Use `./aimi timeline --since <ISO> --until <ISO>`. For Bird, run `bird check` and use the configured Sweetistics engine when available.

### Metadata
- Reproducible: yes
- Related Files: aimi, ~/.config/bird/config.json5

### Resolution
- **Resolved**: 2026-08-13T18:46:00+02:00
- **Notes**: Reran AIMI timeline with the required date-range flags; Bird verification continues via explicit engine preflight.

---
## [ERR-20260813-021] firecrawl-empty-output-and-bird-engine

**Logged**: 2026-08-13T18:46:00+02:00
**Priority**: low
**Status**: resolved
**Area**: config

### Summary
Firecrawl wrote no output file for zero-result searches, and the installed Bird build rejected the documented `--engine` option.

### Error
`jq: Could not open file`; `bird: unknown option '--engine'`.

### Context
- Official-domain searches returned no results, then unconditional jq reads failed.
- Bird v0.8.0 on this machine has no `--engine` CLI option despite the skill reference.

### Suggested Fix
Guard Firecrawl output reads with `test -s`. Use Bird's available authentication path only; if unavailable, record X verification as blocked and continue with official web pages.

### Metadata
- Reproducible: yes
- Related Files: .firecrawl/, ~/.agents/skills/bird/SKILL.md

### Resolution
- **Resolved**: 2026-08-13T18:48:00+02:00
- **Notes**: Switched to direct official-page scraping and guarded no-result output.

---
## [ERR-20260813-022] editorial-repository-path-missing

**Logged**: 2026-08-13T18:47:00+02:00
**Priority**: medium
**Status**: pending
**Area**: config

### Summary
The canonical repository path documented by the editorial skill does not exist on this machine.

### Error
`cd: /Users/TH33_ORACL3/AZ Labs/3 - Production/AZ Labs_SMB Acquire_Previews/AZ Labs - Live: No such file or directory`

### Context
- Duplicate-check preflight for a candidate model release.
- Because `cd` was not guarded with `&&` or `set -e`, later read-only Git commands ran in the AIMI checkout instead.

### Suggested Fix
Update the editorial skill with the current repository path. Guard future directory changes with `cd "$REPO" || exit 1` before any Git command.

### Metadata
- Reproducible: yes
- Related Files: ~/.agents/skills/azlabs-editorial-publishing/SKILL.md

---

## [ERR-20260813-023] telegram-shell-quoting

**Logged**: 2026-08-13T18:48:00+02:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
A nested `zsh -lc` Telegram command broke on single-quoted jq syntax.

### Error
`syntax error near unexpected token '('`

### Context
- The outer Bash command and inner zsh script both used single-quote boundaries.
- Telegram credentials and package output were unaffected.

### Suggested Fix
Use the Python standard library for Telegram requests when the message requires multiline HTML and nested shell quoting.

### Metadata
- Reproducible: yes
- Related Files: ~/.agents/skills/notify-telegram/SKILL.md

### Resolution
- **Resolved**: 2026-08-13T18:48:00+02:00
- **Notes**: Sent the Telegram notification successfully with Python; Telegram returned message ID 756.

---
## [ERR-20260813-024] aside-cli-broken-symlink

**Logged**: 2026-08-13T19:31:00+02:00
**Priority**: medium
**Status**: resolved
**Area**: config

### Summary
Aside CLI was absent from PATH because its existing symlink pointed to a missing app bundle after the Aside update.

### Error
`~/.local/bin/aside: broken symbolic link to ~/.aside/cli/Aside CLI.app/Contents/MacOS/aside`

### Context
- Required for the authorised X browser publication step.
- Aside.app itself was installed and running.

### Suggested Fix
Re-run Aside's official CLI installer from `https://releases.aside.com/install.sh`, then verify the CLI version before browser work.

### Metadata
- Reproducible: yes
- Related Files: ~/.local/bin/aside, ~/.aside/cli/

### Resolution
- **Resolved**: 2026-08-13T19:31:00+02:00
- **Notes**: Reinstalled official Aside CLI 1.26.810.1915 and verified `aside exec --help`.

---
## [ERR-20260813-025] x-browser-authentication-blocked

**Logged**: 2026-08-13T19:36:00+02:00
**Priority**: high
**Status**: pending
**Area**: config

### Summary
Automatic X publication could not run because the Aside browser profile was signed out of @TH33ORACL3.

### Error
`https://x.com/home` showed the sign-in page. The saved exact @TH33ORACL3 credential autofilled, but X did not complete login.

### Context
- Gemini 3.7 Flash article and final 1200x630 social card were already live.
- Account safety check prevented posting from any other account.
- No root post or reply was created.

### Suggested Fix
Sign @TH33ORACL3 into X in Aside, verify `twitter.getMe()` or the visible profile, then retry the preserved exact thread from package `20260813-b62e166166`.

### Metadata
- Reproducible: yes
- Related Files: ~/.aside/u/0/, ~/.hermes/ops/model-release-desk/packages/20260813-b62e166166.json

---

## [ERR-20260813-026] x-media-upload-stuck

**Logged**: 2026-08-13T21:36:30+02:00
**Priority**: high
**Status**: pending
**Area**: tooling

### Summary
Aside could publish text to X, but X never completed media processing for the verified 1200x630 social image.

### Error
```text
X remained on "Preparing media..." for both PNG and JPEG uploads. The same failure occurred in compose, Premium edit, direct file-input, and browser-native file-chooser flows.
```

### Context
- The image was a valid non-empty 1200x630 PNG downloaded from the live AZ Labs Twitter-image route.
- X posted the approved root text after the stalled upload cleared, but the resulting post had no media.
- The article reply posted and its `in_reply_to_status_id_str` was verified with Syndication.
- Telegram delivery succeeded with message ID 759; the surrounding command returned non-zero only because its optional reply-poll window ended without a user response.

### Suggested Fix
Debug X's media-upload requests in Aside network capture before the next release. Do not treat an enabled Post button or a selected file as proof that media attached; verify the published post exposes media before marking a visual thread complete.

### Metadata
- Reproducible: yes
- Related Files: /Users/TH33_ORACL3/.hermes/ops/model-release-desk/assets/20260813-311a6d5b07/gemini-3-7-flash-twitter.png, /Users/TH33_ORACL3/.aside/u/0/
- Tags: x, aside, media-upload, release-desk

---

## [ERR-20260814-027] aimi-release-desk-argument-query

**Logged**: 2026-08-14T04:49:18+02:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
The release-desk inspection initially invoked argument-requiring AIMI commands without model/date arguments.

### Error
```text
usage: aimi where [-h] [--refresh-harnesses] [--no-harnesses] model
aimi where: error: the following arguments are required: model
```

### Context
- The combined command stopped after `./aimi where`, so route, timeline and changes did not run.
- Package: `20260814-756881a473`.

### Suggested Fix
Read command help first or pass the trigger model/provider and same-day date range directly.

### Metadata
- Reproducible: yes
- Related Files: aimi
- Tags: aimi, release-desk, cli

### Resolution
- **Resolved**: 2026-08-14T04:49:18+02:00
- **Notes**: Reran all four commands with `deepseek-v4-pro:0813`, `ollama-cloud`, and the 2026-08-14 date range.

---

## [ERR-20260814-028] editorial-repository-path-drift

**Logged**: 2026-08-14T04:49:18+02:00
**Priority**: medium
**Status**: pending
**Area**: docs

### Summary
The editorial skill's canonical repository path no longer exists.

### Error
```text
fatal: cannot change to '/Users/TH33_ORACL3/AZ Labs/3 - Production/AZ Labs_SMB Acquire_Previews/AZ Labs - Live': No such file or directory
```

### Context
- The live checkout was found at `/Users/TH33_ORACL3/AZ Labs/3 - Production/AZ Labs_SMB Acquire_Previews/AZLabs`.
- No repository write was needed because this batch was a duplicate provider alias, not a new release.

### Suggested Fix
Update the `azlabs-editorial-publishing` skill's canonical repository path after confirming the move is permanent.

### Metadata
- Reproducible: yes
- Related Files: /Users/TH33_ORACL3/.agents/skills/azlabs-editorial-publishing/SKILL.md
- Tags: editorial, path, documentation

---

## [ERR-20260814-029] bird-auth-unavailable

**Logged**: 2026-08-14T04:49:18+02:00
**Priority**: high
**Status**: pending
**Area**: tooling

### Summary
Bird could not verify the official DeepSeek X account because no readable X cookies were available.

### Error
```text
Missing auth_token
Missing ct0
Missing required credentials
```

### Context
- `bird whoami` and a bounded `from:deepseek_ai` search both failed.
- The failure recurred at 06:02 SAST for package `20260814-ac2a41af69` during a bounded `from:dotsstudioai` search.
- DeepSeek's official API documentation and anonymous `synd` reads still provided primary release evidence.
- No X write was attempted with Bird.

### Suggested Fix
Restore Bird's read-only @Prompt_Lee credentials or cookie access, then rerun `bird whoami`.

### Metadata
- Reproducible: yes
- Related Files: /Users/TH33_ORACL3/.config/bird/config.json5
- Tags: bird, x, auth, release-desk

---

## [ERR-20260814-030] telegram-reply-poll-empty-json

**Logged**: 2026-08-14T04:52:23+02:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
The optional Telegram reply poll passed malformed fallback JSON to jq after an empty long-poll response.

### Error
```text
jq: parse error: Unmatched '}' at line 1, column 24
```

### Context
- Telegram notification message 762 had already delivered successfully.
- Only the optional post-send reply check failed.

### Suggested Fix
Validate the curl response with `jq -e` first, then assign a literal `{\"result\":[]}` fallback.

### Metadata
- Reproducible: yes
- Related Files: /Users/TH33_ORACL3/.agents/skills/notify-telegram/SKILL.md
- Tags: telegram, jq, polling

### Resolution
- **Resolved**: 2026-08-14T04:52:23+02:00
- **Notes**: Retried with JSON validation and a safe literal fallback; no new user reply was present.

---

## [ERR-20260814-031] aimi-timeline-argument-recurrence

**Logged**: 2026-08-14T05:58:20+02:00
**Priority**: high
**Status**: resolved
**Area**: tooling

### Summary
The release desk again passed a model name to `aimi timeline`, although this command accepts only a date range.

### Error
```text
usage: aimi timeline [-h] --since SINCE [--until UNTIL]
aimi timeline: error: the following arguments are required: --since
```

### Context
- Attempted `./aimi timeline 'Dots3-Note Preview'` for package `20260814-ac2a41af69`.
- The combined shell command stopped before `aimi changes` because it used `&&`.
- This is the third recorded recurrence of the same release-desk argument error.

### Suggested Fix
Release-desk automation should call `./aimi timeline --since <SAST-day-start-UTC> --until <SAST-day-end-UTC>` and filter JSON afterward. Run independent read-only commands without an `&&` chain so one syntax error does not suppress the rest.

### Metadata
- Reproducible: yes
- Related Files: `aimi`
- Tags: aimi, timeline, release-desk, recurring
- See Also: ERR-20260812-014, ERR-20260813-020

### Resolution
- **Resolved**: 2026-08-14T05:58:20+02:00
- **Notes**: Corrected the run to use the input package's UTC day bounds.

---

## [ERR-20260814-032] azlabs-build-missing-database-url

**Logged**: 2026-08-14T06:08:00+02:00
**Priority**: medium
**Status**: pending
**Area**: config

### Summary
The AZ Labs production build and local server emit Gateway errors when `DATABASE_URL` is absent, even though the editorial route builds and returns HTTP 200.

### Error
```text
Error: DATABASE_URL is not set — the AZ Labs Gateway cannot start.
```

### Context
- `pnpm build` compiled, type-checked, generated all 157 static pages, and exited successfully.
- The local production server returned HTTP 200 for the article, sitemap, social images, and both audio files.
- The skill correctly forbids copying secret `.env.local` files into editorial worktrees.

### Suggested Fix
Make Gateway initialisation lazy for routes that need it, or document a non-secret build-time stub supported by the application. Do not copy production credentials into isolated editorial worktrees.

### Metadata
- Reproducible: yes
- Related Files: `/Users/TH33_ORACL3/AZ Labs/3 - Production/AZ Labs_SMB Acquire_Previews/AZLabs/src/lib/gateway/`
- Tags: azlabs, build, database-url, editorial, gateway

---

## [ERR-20260814-033] gh-pr-create-before-push

**Logged**: 2026-08-14T06:10:11+02:00
**Priority**: medium
**Status**: resolved
**Area**: tooling

### Summary
`gh pr create` ran before the new editorial branch had been pushed to GitHub.

### Error
```text
GraphQL: Head sha can't be blank, Base sha can't be blank, No commits between main and editorial/dots3-note-preview-open-weights, Head ref must be a branch
```

### Context
- The local commit existed at `d1d0ce4`.
- The workflow omitted `git push --set-upstream origin <branch>` before `gh pr create`.

### Suggested Fix
Always push the head branch after committing and before calling `gh pr create`.

### Metadata
- Reproducible: yes
- Related Files: `/Users/TH33_ORACL3/.agents/skills/azlabs-editorial-publishing/SKILL.md`
- Tags: github, pr, push, editorial

### Resolution
- **Resolved**: 2026-08-14T06:10:11+02:00
- **Notes**: Pushed the branch and retried PR creation.

---

## [ERR-20260814-034] release-desk-verification-fallbacks

**Logged**: 2026-08-14T06:38:09+02:00
**Priority**: medium
**Status**: resolved
**Area**: tooling

### Summary
The release-desk verification hit three non-blocking tool errors: a missing AIMI argument, Firecrawl rejecting Meta's domain, and unavailable Bird credentials.

### Error
```text
usage: aimi where [-h] [--refresh-harnesses] [--no-harnesses] model
Error: We apologize for the inconvenience but we do not support this site.
Missing auth_token / ct0: Bird credentials unavailable.
```

### Context
- The first command called `./aimi where` without the required model argument.
- Firecrawl Search found Meta's official pages, but Firecrawl Scrape refused `research.meta.ai`.
- Bird could not read X because no supported browser cookies or Sweetistics key were available.

### Suggested Fix
Pass the trigger model to every AIMI lookup. When Firecrawl blocks an official domain, fetch the HTTP 200 primary page directly and extract its embedded metadata. Treat Bird as optional when a conclusive maker-owned release page is available, while reporting the credential limitation.

### Metadata
- Reproducible: yes
- Related Files: `aimi`, `.firecrawl/meta-muse-release.html`
- Tags: release-desk, aimi, firecrawl, bird, verification

### Resolution
- **Resolved**: 2026-08-14T06:38:09+02:00
- **Notes**: Re-ran AIMI with `muse-spark-1.2`, extracted Meta's official 5 August publication date directly, and completed the batch as candidate-only without relying on X evidence.

---

## [ERR-20260814-035] editorial-repository-path-drift

**Logged**: 2026-08-14T08:05:20+02:00
**Priority**: medium
**Status**: resolved
**Area**: config

### Summary
The editorial skill's canonical repository path no longer exists; the live checkout is now the sibling `AZLabs` directory.

### Error
```text
cd: /Users/TH33_ORACL3/AZ Labs/3 - Production/AZ Labs_SMB Acquire_Previews/AZ Labs - Live: No such file or directory
```

### Context
- The documented path ends in `AZ Labs - Live`.
- The verified checkout is `/Users/TH33_ORACL3/AZ Labs/3 - Production/AZ Labs_SMB Acquire_Previews/AZLabs`.
- Its origin is `https://github.com/AZLabsAI/AZLabs.ai.git`.

### Suggested Fix
Update the editorial skill's canonical path after confirming no other workflow still depends on the old location. Until then, resolve the checkout by its verified Git remote instead of guessing.

### Metadata
- Reproducible: yes
- Related Files: `/Users/TH33_ORACL3/.agents/skills/azlabs-editorial-publishing/SKILL.md`
- Tags: editorial, repository, path-drift
- See Also: ERR-20260814-034

### Resolution
- **Resolved**: 2026-08-14T08:05:20+02:00
- **Notes**: Located and verified the `AZLabs` checkout without changing its unrelated untracked files.

---

## [ERR-20260814-036] firecrawl-no-results-output-contract

**Logged**: 2026-08-14T08:05:20+02:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
`firecrawl search -o <path>` creates no output file when the search returns no results, so an unconditional follow-up `jq` fails.

### Error
```text
No results found.
jq: error: Could not open file .firecrawl/glm53-zai.json: No such file or directory
```

### Context
- Official-domain searches for `GLM-5.3` correctly returned no results.
- The shell command assumed the requested output path would exist even for an empty result set.

### Suggested Fix
Guard the parser with `if [ -f "$OUTPUT" ]` and emit an explicit empty result object when Firecrawl returns no matches.

### Metadata
- Reproducible: yes
- Related Files: `.firecrawl/`
- Tags: firecrawl, search, empty-results, jq

### Resolution
- **Resolved**: 2026-08-14T08:05:20+02:00
- **Notes**: The broad follow-up search used a file-existence guard and completed successfully.

---

## [ERR-20260814-037] bsd-date-timezone-format-recurrence

**Logged**: 2026-08-14T09:00:25+02:00
**Priority**: high
**Status**: resolved
**Area**: tooling

### Summary
The release desk repeated the documented BSD `date` `%:z` error and briefly wrote an invalid `created_at` value before the final atomic correction.

### Error
```text
"created_at": "2026-08-14T09:00:14:z"
```

### Context
- macOS BSD `date` printed the GNU `%:z` directive literally.
- Structural JSON validation did not initially enforce an ISO-8601 timestamp pattern.
- The invalid file was replaced atomically before completion.

### Suggested Fix
Release-desk package generation must use Python `datetime.now().astimezone().isoformat(timespec="seconds")` directly. Never call BSD `date` with `%:z`. Keep the ISO-8601 regex or `datetime.fromisoformat` check inside the atomic-write command.

### Metadata
- Reproducible: yes
- Related Files: `/Users/TH33_ORACL3/.hermes/ops/model-release-desk/packages/20260814-9e41f0b66e.json`
- Tags: macos, bsd-date, iso-8601, release-desk, recurrence
- See Also: ERR-20260812-016

### Resolution
- **Resolved**: 2026-08-14T09:00:25+02:00
- **Notes**: Rewrote the contract atomically with Python-generated ISO-8601 time and validated the timezone offset before rename.

---

## [ERR-20260814-BACKUP] backup-reaper --dry-run

**Logged**: 2026-08-14T19:48:10+02:00
**Priority**: low
**Status**: resolved
**Area**: config

### Summary
The installed `backup-reaper` does not accept the documented `--dry-run` flag.

### Error
```
backup-reaper: error: unrecognized arguments: --dry-run
```

### Context
The backup inventory was updated for CCR and ZCode backup locations. The smoke test passed; the bare `backup-reaper` command is the installed dry-run mode.

### Suggested Fix
Use `backup-reaper --smoke-test` for validation and bare `backup-reaper` for the dry run on this machine.

### Metadata
- Reproducible: yes
- Related Files: `~/.agents/backup-inventory.md`
- Tags: backup-reaper, cli-drift, macos

### Resolution
- **Resolved**: 2026-08-14T19:50:00+02:00
- **Notes**: Ran the supported bare dry run successfully; one unrelated existing CCR backup would be pruned.

---

## [ERR-20260814-ZCODE-DIFF] validation_script

**Logged**: 2026-08-14T19:52:55+02:00
**Priority**: low
**Status**: resolved
**Area**: config

### Summary
The first ZCode backup diff checker inverted the labels for added JSON keys and failed its assertion.

### Error
```
AssertionError: expected nested modelDisplayNames additions were not found
```

### Context
The config itself parsed correctly. The checker treated a provider-level `modelDisplayNames` object as a removed key because its comparison labels were reversed.

### Suggested Fix
Use a focused provider/model assertion for configuration writes and verify model IDs are unchanged; do not rely on the flawed generic diff labels.

### Metadata
- Reproducible: yes
- Related Files: `~/.zcode/v2/config.json`
- Tags: zcode, validation, config

### Resolution
- **Resolved**: 2026-08-14T19:53:00+02:00
- **Notes**: Corrected the validation to assert the exact three additions and unchanged model IDs; validation passed.

---

## [ERR-20260814-ZCODE-LAUNCH] process_check

**Logged**: 2026-08-14T19:53:30+02:00
**Priority**: low
**Status**: resolved
**Area**: config

### Summary
The first ZCode restart check matched only the full executable path and missed macOS's process name `ZCode`.

### Error
```
ZCode=not-running
```

### Context
`open -a ZCode` had launched the app; `pgrep` used an overly narrow path pattern. A broader process check confirmed the app and local host processes were running.

### Suggested Fix
For Electron apps, verify both the app process name and the bundle path.

### Metadata
- Reproducible: yes
- Related Files: `/Applications/ZCode.app`, `~/.zcode/v2/config.json`
- Tags: zcode, macos, process-check

### Resolution
- **Resolved**: 2026-08-14T19:54:00+02:00
- **Notes**: Rechecked with `pgrep -fl 'ZCode|zcode'`; ZCode running and config preserved.

---

## [ERR-20260814-038] aimi-release-desk-cli-arguments

**Logged**: 2026-08-14T20:46:00+02:00
**Priority**: high
**Status**: resolved
**Area**: tooling

### Summary
The release desk again called `aimi route` with a combined route string and `aimi timeline` with a model name.

### Error
```text
usage: aimi route [-h] provider model
aimi route: error: the following arguments are required: model
usage: aimi timeline [-h] --since SINCE [--until UNTIL]
aimi timeline: error: the following arguments are required: --since
```

### Context
- Package `20260814-e4fdd9866f` supplied two Cloudflare route candidates.
- The first inspection used `cloudflare-ai/model` as one argument and passed each model name to `timeline`.
- Read-only `where` and `changes` still ran because the shell used `|| true`; no catalogue writes occurred.

### Suggested Fix
Call `./aimi route <provider> <model>` with two arguments. Call `./aimi timeline --since <ISO> --until <ISO>` once per package and filter the JSON by model aliases.

### Metadata
- Reproducible: yes
- Related Files: `aimi`
- Tags: aimi, route, timeline, release-desk, recurring
- See Also: ERR-20260814-031, ERR-20260813-020

### Resolution
- **Resolved**: 2026-08-14T20:47:00+02:00
- **Notes**: Reran both route lookups with separate arguments and the timeline with bounded UTC dates.

---

## [ERR-20260814-039] release-desk-known-fallback-recurrence

**Logged**: 2026-08-14T20:50:00+02:00
**Priority**: medium
**Status**: resolved
**Area**: tooling

### Summary
The release desk reused a stale editorial checkout path, BSD `date` rejected `%:z`, Bird lacked cookies, and the Telegram response projection hid the delivered message ID.

### Error
```text
cd: .../AZ Labs - Live: No such file or directory
2026-08-14T20:48:22:z
Missing auth_token / ct0
{"ok":true,"result":{"message_id":null,"date":null,"chat_id":null}}
```

### Context
- The verified website checkout is the sibling `AZLabs` directory.
- macOS BSD `date` does not support GNU `%:z`.
- Anonymous syndication still verified the existing X thread and reply relationship.
- Telegram accepted the notification; only the local `jq` projection read result fields from the wrong object level.

### Suggested Fix
Resolve the editorial checkout by verified Git remote, use Python `datetime.now().astimezone().isoformat()`, treat Bird as optional when syndication is sufficient, and project Telegram fields from `.result`.

### Metadata
- Reproducible: yes
- Related Files: `/Users/TH33_ORACL3/.agents/skills/azlabs-editorial-publishing/SKILL.md`, `/Users/TH33_ORACL3/.agents/skills/notify-telegram/SKILL.md`
- Tags: editorial, path-drift, bsd-date, bird, telegram, release-desk
- See Also: ERR-20260814-035, ERR-20260814-037, ERR-20260814-034

### Resolution
- **Resolved**: 2026-08-14T20:50:00+02:00
- **Notes**: Used the verified `AZLabs` checkout, generated ISO time with Python, verified X through syndication, and retained Telegram's successful delivery status without sending a duplicate notification.

---
## [ERR-20260815-001] release-desk-verification-commands

**Logged**: 2026-08-15T03:36:46+02:00
**Priority**: low
**Status**: pending
**Area**: config

### Summary
The first AIMI timeline call omitted its required date flag, and Bird could not access X because local read credentials were unavailable.

### Error
`aimi timeline` requires `--since`; Bird reported missing `auth_token` and `ct0`.

### Context
- Corrected AIMI with an explicit SAST-day UTC window.
- Continued verification from official maker pages; Bird remained read-only and unused for posting.

### Suggested Fix
Use `./aimi timeline --since <ISO> --until <ISO>` and run `bird check` before release-desk social verification.

### Metadata
- Reproducible: yes
- Related Files: .learnings/ERRORS.md

---
