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
