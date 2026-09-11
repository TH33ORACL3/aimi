# Errors

## [ERR-20260831-DESK-001] model-release desk inspection command mismatch

**Logged**: 2026-08-31T02:29:00+02:00
**Priority**: low
**Status**: resolved
**Area**: config

### Summary
Initial model-release desk inspection used `aimi where` and `aimi timeline` without their required model/date arguments, and one shell probe had an unmatched quote.

### Error
```text
usage: aimi where ... model
usage: aimi timeline ... --since SINCE
/bin/bash: unexpected EOF while looking for matching `''
```

### Context
- The durable batch required a read of `where`, `route`, `timeline` and `changes` for `glm-5.3-flash`.
- The CLI help was then checked and the commands were rerun with the exact positional/date arguments.

### Suggested Fix
Use `./aimi commands` or subcommand help before constructing automated inspection calls, and keep URL/regex shell quoting in separate variables when probes contain nested quotes.

### Metadata
- Reproducible: yes
- Related Files: `model_release_desk.py`, `.learnings/ERRORS.md`
- Tags: aimi, model-release-desk, cli, shell-quoting

### Resolution
- **Resolved**: 2026-08-31T02:30:00+02:00
- **Notes**: Corrected to `aimi where 'glm-5.3-flash'`, `aimi route cline 'cline-pass/glm-5.3-flash'`, `aimi timeline --since 2026-08-29 --until 2026-08-29`, and dated `aimi changes`.
---

## [ERR-20260827-MERGE-001] Merge Gateway Pi invalid API header

**Logged**: 2026-08-27T10:47:00+02:00
**Priority**: critical
**Status**: resolved
**Area**: config

### Summary
Pi's Merge Gateway request failed because the configured `!zsh -lic` API-key command returned interactive session-restore text together with the key, producing an invalid multiline Bearer header.

### Error
```text
Error: Headers.append: "Bearer Restored session: Thu Aug 27 10:33:22 SAST 2026
 mg_..." is an invalid header value.
```

### Context
- Provider: `merge-gateway`
- Model: `deepseek/deepseek-v4-flash`
- The existing providers use normal `$ENV_VAR` references; the Merge entry was changed to a command substitution to work around an earlier visibility issue.
- The command's interactive zsh startup output is outside the pipeline, so filtering only the `printf` output cannot remove it.

### Suggested Fix
Remove the interactive command substitution and use Pi's normal environment-variable API-key reference after verifying the scoped provider/model registration and the actual launching environment. If a launcher-independent secret source is required, use a dedicated non-interactive secret lookup that emits only the key, not an interactive shell.

### Metadata
- Reproducible: yes
- Related Files: `~/.pi/agent/models.json`, `~/.pi/agent/settings.json`, `~/.zshrc`
- Tags: pi, merge-gateway, api-key, invalid-header, session-restore

### Resolution
- **Resolved**: 2026-08-27T11:08:15+02:00
- **Notes**: Removed the interactive `!zsh -lic` API-key command and restored Pi's normal `$MERGE_API_KEY` provider reference. This preserves the same working convention as the other providers and prevents session-restore output from entering the Authorization header. Fresh home-directory zsh auth/list checks passed; a real Pi request returned exactly `OK` with provider/model metadata confirming the Merge route and no error/fallback.
## [ERR-20260827-AIMI] incorrect model-release desk inspection invocations
**Logged**: 2026-08-27T18:16:48+02:00
**Priority**: low
**Status**: resolved
**Area**: config

### Summary
Initial AIMI inspection used unsupported --json flags and omitted required positional/date arguments; editorial path in the skill was absent.

### Error
aimi where/route/timeline required arguments; aimi changes does not accept --json; the documented editorial checkout path was not present.

### Context
- Corrected by reading command help and using the required positional arguments.

### Suggested Fix
Use ./aimi commands or subcommand help before machine-readable inspection, and resolve the live editorial checkout when the documented path is unavailable.

### Metadata
- Reproducible: yes
- Related Files: .learnings/ERRORS.md

### Resolution
- **Resolved**: 2026-08-27T18:18:00+02:00
- **Notes**: Continued with corrected read-only commands.
---
## [ERR-20260827-ASIDE] local upload path outside Aside session directory
**Logged**: 2026-08-27T18:25:30+02:00
**Priority**: medium
**Status**: resolved
**Area**: config

### Summary
Aside rejected the persistent model-release-desk asset path for X media upload because setInputFiles only accepts paths inside its session directory.

### Error
Path escapes the session directory

### Context
- X browser account preflight succeeded as @TH33ORACL3.
- Upload attempted through the browser as required by the post-to-x skill.

### Suggested Fix
Use an allowed Aside session-local upload path or pass an in-memory file payload.

### Metadata
- Reproducible: yes
- Related Files: /Users/TH33_ORACL3/.hermes/ops/model-release-desk/assets/20260827-05f336ad68/inclusionai-ling-3-flash-fin-openrouter-twitter.png

### Resolution
- **Resolved**: 2026-08-27T18:26:00+02:00
- **Notes**: Will upload the verified image as an in-memory buffer or through an allowed session-local path.
---
## [ERR-20260827-ASIDE-PWD] assumed Aside pwd helper callable
**Logged**: 2026-08-27T18:26:10+02:00
**Priority**: low
**Status**: resolved
**Area**: config

### Summary
Aside exports pwd as a non-callable value or does not expose it as a function.

### Error
TypeError: pwd is not a function

### Context
- Attempted to locate the session directory for a permitted upload path.

### Suggested Fix
Inspect the value directly or avoid filesystem-path uploads by using an in-memory buffer.

### Metadata
- Reproducible: yes
- Related Files: .learnings/ERRORS.md

### Resolution
- **Resolved**: 2026-08-27T18:26:20+02:00
- **Notes**: Continue with in-memory upload.
---
## [ERR-20260827-ASIDE-BUFFER] setInputFiles object payload unsupported
**Logged**: 2026-08-27T18:27:30+02:00
**Priority**: low
**Status**: resolved
**Area**: config

### Summary
Aside setInputFiles rejected a single in-memory file object.

### Error
TypeError: xn.map is not a function

### Context
- X root post text was filled in a fresh @TH33ORACL3 browser session.

### Suggested Fix
Pass the in-memory file object in an array, matching Playwright file-list semantics.

### Metadata
- Reproducible: yes
- Related Files: .learnings/ERRORS.md

### Resolution
- **Resolved**: 2026-08-27T18:28:00+02:00
- **Notes**: Retrying with an array payload.
---
## [ERR-20260827-JQ-SANITIZE] nested credential redaction missed

**Logged**: 2026-08-27T21:40:30+02:00
**Priority**: high
**Status**: pending
**Area**: config

### Summary
A jq sanitization expression removed only top-level credential keys and printed nested Cline access and refresh tokens while inspecting provider configuration.

### Error
```
jq: error (at ~/.cline/data/settings/providers.json:39): Cannot index number with string ("apiKey")
```
The fallback inspection then emitted nested `accessToken` and `refreshToken` values because the redaction was not recursive.

### Context
- Attempted to inspect Cline provider metadata without exposing secrets.
- The provider file stores credentials below `.providers.cline.settings.auth`.
- Follow-up endpoint calls use a shell variable and print only model metadata.

### Suggested Fix
Use a recursive allowlist or explicitly delete nested credential objects before printing; never inspect config JSON with a shallow key filter.

### Metadata
- Reproducible: yes
- Related Files: ~/.cline/data/settings/providers.json
- Tags: jq, secrets, cline, redaction

---

## [ERR-20260831-HAL-001] Hal Pi delegation inherited newly changed target model

**Logged**: 2026-08-31T19:39:03+02:00
**Priority**: medium
**Status**: resolved
**Area**: config

### Summary
The first remote Hal Pi delegation failed because the local `halctl pi` launcher had already been changed to pass the requested OpenRouter model, but Hal did not yet have that route registered or an OpenRouter key available to the prompting agent.

### Error
```text
No API key found for openrouter.
```

### Context
- The local Hal launcher default was changed before using it to prompt Hal's existing working Pi agent.
- `halctl pi --direct -p ...` therefore attempted to run the delegation prompt itself with the new target route.
- The delegation must temporarily use the known-working Hal prompt model while changing the target Pi configuration.

### Suggested Fix
Use `HAL_PI_MODEL=opencode/deepseek-v4-flash-free halctl pi --direct -p ...` for the configuration handoff, then verify the target route and launcher separately.

### Metadata
- Reproducible: yes
- Related Files: `/Users/TH33_ORACL3/.agents/skills/hal-vps/scripts/halctl`
- Tags: hal, pi, delegation, openrouter, launcher

### Resolution
- **Resolved**: 2026-08-31T19:44:00+02:00
- **Notes**: Re-ran the handoff with a working route override where possible; when Hal's available prompting routes had no credentials, completed the target settings change through the guarded root-side Hal path instead.

---

## [ERR-20260831-HAL-002] Hal Pi wrapper default route unavailable

**Logged**: 2026-08-31T19:39:51+02:00
**Priority**: medium
**Status**: resolved
**Area**: config

### Summary
The known documented `opencode/deepseek-v4-flash-free` override was unavailable on Hal, so the remote Pi agent could not be used for the configuration handoff with that route.

### Error
```text
400: {"type":"server_error","message":"Error from provider (Console): Upstream request failed: Model is unavailable."}
```

### Context
- The failed command was `HAL_PI_MODEL=opencode/deepseek-v4-flash-free halctl pi --direct -p ...`.
- Hal's current documented Pi settings default is `opencode-go/ox-alpha-free`, while the wrapper's former hard-coded default was stale.

### Suggested Fix
Use Hal's current configured `opencode-go/ox-alpha-free` route for the one-time remote configuration handoff, then verify the OpenRouter route independently.

### Metadata
- Reproducible: yes
- Related Files: `/Users/TH33_ORACL3/.agents/skills/hal-vps/scripts/halctl`
- Tags: hal, pi, opencode, wrapper, stale-default

### Resolution
- **Resolved**: 2026-08-31T19:44:00+02:00
- **Notes**: Confirmed the wrapper default was stale, then replaced it with the requested OpenRouter route and documented the current value.

---

## [ERR-20260831-HAL-003] Hal Pi prompting route has no credential

**Logged**: 2026-08-31T19:40:25+02:00
**Priority**: medium
**Status**: pending
**Area**: config

### Summary
Hal's documented current `opencode-go/ox-alpha-free` route also could not start the remote Pi handoff because the ubuntu environment has no OpenCode Go API key.

### Error
```text
No API key found for opencode-go.
```

### Context
- The direct remote test used `HAL_PI_MODEL=opencode-go/ox-alpha-free halctl pi --direct -p 'Reply with exactly OK'`.
- Pi emitted its model-registry warnings, then stopped before executing the prompt.

### Suggested Fix
Inspect the remote ubuntu Pi configuration with the approved Hal control path and make the narrow JSON change directly if no working remote agent route is available; never print or copy credentials.

### Metadata
- Reproducible: yes
- Related Files: `/home/ubuntu/.pi/agent/settings.json`, `/home/ubuntu/.pi/agent/models.json`
- Tags: hal, pi, opencode-go, credentials, delegation

---

## [ERR-20260831-HAL-004] Remote JSON inspection shell quoting error

**Logged**: 2026-08-31T19:40:53+02:00
**Priority**: low
**Status**: resolved
**Area**: config

### Summary
The first root-side read-only inspection of Hal's Pi JSON files failed because nested shell quoting removed the comma in a Python `join` expression.

### Error
```text
SyntaxError: f-string: expecting a valid expression after '{'
```

### Context
- The inspection was sent through `halctl run` as a nested heredoc.
- No remote file was modified.

### Suggested Fix
Use simple `jq` field projections or a separately transferred script instead of deeply nested inline shell quoting.

### Metadata
- Reproducible: yes
- Related Files: `/home/ubuntu/.pi/agent/settings.json`, `/home/ubuntu/.pi/agent/models.json`
- Tags: hal, pi, shell-quoting, jq

### Resolution
- **Resolved**: 2026-08-31T19:44:00+02:00
- **Notes**: Replaced the nested heredoc inspection with a base64-encoded standard-library Python script; no remote file was changed by the failed attempt.

---

## [ERR-20260831-HAL-005] Hal lacks jq for config inspection

**Logged**: 2026-08-31T19:41:15+02:00
**Priority**: low
**Status**: resolved
**Area**: config

### Summary
The read-only Hal Pi config inspection attempted to use `jq`, but the remote server does not have `jq` installed.

### Error
```text
bash: line 1: jq: command not found
```

### Context
- No remote file was modified.
- Python's standard-library JSON parser is available and is sufficient for a sanitized read.

### Suggested Fix
Use a base64-encoded short Python inspection script for remote JSON reads, avoiding shell-quoting collisions and any package installation.

### Metadata
- Reproducible: yes
- Related Files: `/home/ubuntu/.pi/agent/settings.json`, `/home/ubuntu/.pi/agent/models.json`
- Tags: hal, pi, jq, inspection

### Resolution
- **Resolved**: 2026-08-31T19:44:00+02:00
- **Notes**: Used the standard-library Python fallback and did not install packages on Hal.

---

## [ERR-20260831-HAL-006] Remote model registry shape assumption

**Logged**: 2026-08-31T19:43:20+02:00
**Priority**: low
**Status**: resolved
**Area**: config

### Summary
The guarded Hal Pi settings update refused to write because it assumed the OpenRouter `models` registry was a mapping, while Hal stores it as a list of model objects.

### Error
```text
target route is not registered in models.json
```

### Context
- The preceding sanitized inspection had already confirmed the target model ID was present, but the update guard only handled mapping membership.
- The guard failed before changing any file.

### Suggested Fix
Normalize both supported registry shapes when checking an existing model ID, then retain the same exact-default and atomic-write guards.

### Metadata
- Reproducible: yes
- Related Files: `/home/ubuntu/.pi/agent/models.json`
- Tags: hal, pi, models-json, guard, config-shape

### Resolution
- **Resolved**: 2026-08-31T19:44:00+02:00
- **Notes**: Updated the guard to accept the remote list-shaped registry, then changed only the requested default fields with atomic-write and post-write validation.

---

## [ERR-20260901-AIMI-001] concurrent live harness scans

**Logged**: 2026-09-01T10:54:20+02:00
**Priority**: medium
**Status**: pending
**Area**: config

### Summary
Two concurrent `catalogue harness-models` calls both triggered the write-enabled live AIMI harness scan, causing SQLite lock and duplicate-entry errors.

### Error
```text
sqlite3.OperationalError: database is locked
sqlite3.IntegrityError: UNIQUE constraint failed: model_order_profile_entries.profile_id, model_order_profile_entries.provider_id, model_order_profile_entries.model_identifier
```

### Context
- Ran Pi and Grok Build live harness scans concurrently while checking model wiring feasibility.
- The scan is not read-only despite the command being a read query; it refreshes AIMI tables.
- No intended model or harness configuration was changed by these failed scans.

### Suggested Fix
Run only one live AIMI harness scan at a time. For parallel feasibility checks, inspect local harness config files directly or use cached catalogue reads, then run one serialized refresh when required.

### Metadata
- Reproducible: yes
- Related Files: `scan_local_harnesses.py`, `~/.pi/agent/settings.json`, `~/.grok/config.toml`
- Tags: aimi, sqlite, locking, harness-scan, concurrency

---

## [ERR-20260901-SEC-001] broad config search exposed credential-bearing backups

**Logged**: 2026-09-01T11:03:00+02:00
**Priority**: high
**Status**: pending
**Area**: config

### Summary
A broad recursive search across CCR package data and backup files emitted literal credential-bearing configuration while inspecting protocol support.

### Error
```text
The search output included credential values from existing CCR backup/config JSON.
```

### Context
- The search covered `/opt/homebrew/lib/node_modules/@musistudio/claude-code-router` and `~/.claude-code-router`, including historical backups.
- No credential was intentionally requested or written.
- The output was not sent to the user, but the inspection scope was too broad.

### Suggested Fix
Restrict searches to source/package files, exclude backups and logs by path before execution, and use allowlisted field extraction for all credential-bearing config. Never print full provider config documents.

### Metadata
- Reproducible: yes
- Related Files: `~/.claude-code-router/backups-*`, `/opt/homebrew/lib/node_modules/@musistudio/claude-code-router/dist/main/cli.js`
- Tags: secrets, redaction, config-inspection, backups, rg

---

## [ERR-20260901-TEST-001] importlib smoke harness omitted sys.modules registration

**Logged**: 2026-09-01T11:18:00+02:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
A one-off Python import smoke test for the new bridge failed because the custom `importlib` loader did not register the module in `sys.modules` before applying `@dataclass`.

### Error
```text
AttributeError: 'NoneType' object has no attribute '__dict__'
```

### Context
- The bridge itself passed `python3 -m py_compile`.
- The failure was in the test harness, not bridge execution.

### Suggested Fix
Register dynamically loaded modules in `sys.modules`, or invoke the script through Python's normal module/script loader for smoke tests.

### Metadata
- Reproducible: yes
- Related Files: `~/bin/github-copilot-bridge.py`
- Tags: python, importlib, dataclass, smoke-test

### Resolution
- **Resolved**: 2026-09-01T11:18:30+02:00
- **Notes**: Retested with normal module execution/registered import; syntax remains valid.

---

## [ERR-20260901-COPILOT-001] image detector assumed string content type

**Logged**: 2026-09-01T11:24:00+02:00
**Priority**: medium
**Status**: resolved
**Area**: config

### Summary
The first Grok request reached the bridge, but recursive image detection attempted to put a list-valued `type` field into a set and raised before forwarding the request.

### Error
```text
TypeError: cannot use 'list' as a set element (unhashable type: 'list')
```

### Context
- Triggered by Grok's Responses request payload containing a non-string `type` value in nested content.
- The request was not forwarded upstream and Grok timed out waiting for a response.

### Suggested Fix
Guard the content-type membership check with `isinstance(kind, str)` before comparing against image content types.

### Metadata
- Reproducible: yes
- Related Files: `~/bin/github-copilot-bridge.py`, `~/.grok/github-copilot-bridge.error.log`
- Tags: github-copilot, grok, proxy, image-detection, python

### Resolution
- **Resolved**: 2026-09-01T11:24:30+02:00
- **Notes**: Added the string-type guard; launchd will restart the bridge after the controlled reload.

---

## [ERR-20260901-COPILOT-002] bridge chat smoke returned HTTP 400

**Logged**: 2026-09-01T11:35:00+02:00
**Priority**: medium
**Status**: resolved
**Area**: config

### Summary
The first direct OpenAI Chat Completions smoke request to the extended Copilot bridge returned HTTP 400 before the response shape could be checked.

### Error
```text
curl: (22) The requested URL returned error: 400
```

### Context
- Endpoint: `http://127.0.0.1:8094/v1/chat/completions`
- Model: `gpt-5.6-luna`
- Request used `stream:false` and `max_tokens:8`.
- Native Grok routes had passed earlier; this was the first CCR-compatibility path test.

### Suggested Fix
Inspect the bridge's sanitized error response and request translation, then make one targeted correction before retrying.

### Metadata
- Reproducible: yes
- Related Files: `~/bin/github-copilot-bridge.py`
- Tags: github-copilot, ccr, chat-completions, smoke-test

### Resolution
- **Resolved**: 2026-09-01T11:37:00+02:00
- **Notes**: Copilot Responses requires at least 16 `max_output_tokens`; the bridge now clamps CCR's 8-token smoke cap to 16. GPT and Claude chat-compatibility smoke calls both pass.

---

## [ERR-20260901-CLI-001] rg encoding flag typo

**Logged**: 2026-09-01T11:46:00+02:00
**Priority**: low
**Status**: resolved
**Area**: config

### Summary
A backup-reaper output filter used ripgrep's `-E` encoding flag instead of the `-e` pattern flag.

### Error
```text
rg: error parsing flag -E: grep config error: unknown encoding
```

### Context
- The backup-reaper command itself completed; only the output filter failed.
- The command was rerun with `rg -e` and confirmed the registered Grok and CCR backup patterns.

### Suggested Fix
Use `rg -e '<pattern>'` for patterns; reserve `-E` for encoding only when explicitly needed.

### Metadata
- Reproducible: yes
- Related Files: `.learnings/ERRORS.md`, `~/.agents/backup-inventory.md`
- Tags: rg, cli, backup-reaper, flags

### Resolution
- **Resolved**: 2026-09-01T11:46:30+02:00
- **Notes**: Corrected the filter and verified both backup locations are registered and covered.

---

## [ERR-20260901-GROK-001] Grok max-effort test hit disk quota

**Logged**: 2026-09-01T12:07:30+02:00
**Priority**: high
**Status**: resolved
**Area**: infra

### Summary
The first Grok max-effort smoke request returned a response, but Grok could not persist its session because the filesystem was full.

### Error
```text
No space left on device: FS_DISK_QUOTA_EXCEEDED (os error 28)
```

### Context
- Test: `grok -p 'reply OK' -m github-copilot-gpt-5-6-luna --reasoning-effort max`
- The upstream model returned `OK`; Grok then failed while writing session state.
- Hyperfine stopped after the first non-zero benchmark, so the remaining max-effort models were not tested in this pass.

### Suggested Fix
When a Grok project session hits its storage quota, rerun bounded smoke tests from a small writable directory such as `/tmp`; do not delete session history without approval.

### Metadata
- Reproducible: yes
- Related Files: `~/.grok/`, `~/.grok/config.toml`
- Tags: grok, disk-full, quota, max-effort, smoke-test

### Resolution
- **Resolved**: 2026-09-01T12:12:30+02:00
- **Notes**: Local disk still had approximately 11 GiB free; the failure was scoped to Grok's project/session persistence. Running with `--cwd /tmp` allowed all five max-effort tests to complete successfully.

---

## [ERR-20260901-GROK-002] native minimal effort not mapped for Copilot

**Logged**: 2026-09-01T12:13:00+02:00
**Priority**: medium
**Status**: resolved
**Area**: config

### Summary
The bridge mapped `minimal` for CCR's translated Responses requests but not for Grok's native Responses requests, so Copilot rejected the effort value.

### Error
```text
Unsupported value: 'minimal' is not supported with the 'gpt-5.6-luna' model. Supported values are: 'none', 'low', 'medium', 'high', 'xhigh', and 'max'.
```

### Context
- Test: `grok --cwd /tmp -p 'reply OK' -m github-copilot-gpt-5-6-luna --reasoning-effort minimal`
- Copilot's native GPT route accepts `low` as the provider value; Pi's public picker maps `minimal` to `low`.
- The max tests passed because `max` is accepted natively.

### Suggested Fix
Normalize `reasoning.effort` in native Responses payloads before forwarding, mapping `minimal` to `low` and `off`/`none` to no reasoning.

### Metadata
- Reproducible: yes
- Related Files: `~/bin/github-copilot-bridge.py`
- Tags: github-copilot, grok, reasoning, minimal, responses

### Resolution
- **Resolved**: 2026-09-01T12:15:00+02:00
- **Notes**: Added native Responses normalization. Luna minimal/low/medium/high/xhigh, Sonnet xhigh, and Opus minimal/xhigh all passed; max also passed for all five models.

---

## [ERR-20260902-SEC-001] targeted config search emitted a credential value

**Logged**: 2026-09-02T11:48:08+02:00
**Priority**: high
**Status**: pending
**Area**: config

### Summary
A recursive search for the local NVIDIA proxy matched an environment file and emitted the value of a credential-bearing variable.

### Error
```text
A search output included the value assigned to NVIDIA_API_KEY in an environment file.
```

### Context
- The search was intended to locate the process and launcher for the local NVIDIA endpoint on port 8765.
- The value was not included in the user-facing response and was not written to a project file.
- The search scope included environment files that should have been excluded.

### Suggested Fix
Exclude `*.env` and other secret-bearing files before searching, and inspect only filenames, process arguments, and allowlisted configuration fields. Do not print full environment files or process environments.

### Metadata
- Reproducible: yes
- Related Files: `~/bin/nim-normalize-proxy.py`, `~/.config/azlabs/aura-worker.env`
- Tags: secrets, config-inspection, rg, nvidia-nim

---

## [ERR-20260902-TEST-001] hyperfine jobs flag unsupported

**Logged**: 2026-09-02T11:52:18+02:00
**Priority**: low
**Status**: resolved
**Area**: tests

### Summary
The installed Hyperfine version rejected the attempted `--jobs` concurrency flag before running the OpenRouter smoke tests.

### Error
```text
unexpected argument '--jobs' found
```

### Context
- The command was intended to test four OpenRouter models through Grok Build in one Hyperfine invocation.
- No model request was made by the failed command.

### Suggested Fix
Use the installed Hyperfine syntax without `--jobs`; keep one run, zero warmups, and `--show-output` for the bounded model smoke tests.

### Metadata
- Reproducible: yes
- Related Files: `.learnings/ERRORS.md`
- Tags: hyperfine, openrouter, grok, smoke-test

### Resolution
- **Resolved**: 2026-09-02T11:52:30+02:00
- **Notes**: The test command will be rerun with the supported Hyperfine flags.

---

## [ERR-20260902-PIREG-001] concurrent-pi-registration

**Logged**: 2026-09-02T21:38:06+02:00
**Priority**: high
**Status**: resolved
**Area**: config

### Summary
Two Pi route registrations were launched concurrently and collided on AIMI's shared temporary `models.json.tmp` file.

### Error
```text
json.decoder.JSONDecodeError: Extra data: line 999 column 3 (char 26681)
```

### Context
- Attempted to register `opencode-go/muse-spark-1.3-contributor` and `opencode-zen/muse-spark-1.3-contributor-free` in parallel.
- AIMI creates the fixed temporary path `~/.pi/agent/models.json.tmp`; the original `models.json` remained valid and unchanged.
- The invalid temporary file was isolated and removed before retrying sequentially.

### Suggested Fix
Run AIMI Pi configuration writes sequentially, never in parallel, and validate the JSON and backup state after each write.

### Metadata
- Reproducible: yes
- Related Files: `aimi`, `~/.pi/agent/models.json`
- Tags: pi, aimi, concurrency, atomic-write, config

### Resolution
- **Resolved**: 2026-09-02T21:38:06+02:00
- **Notes**: No partial Pi config write occurred; the failed temporary file was cleaned up and registrations will be applied one at a time.

---

## [ERR-20260902-PISMOKE-001] opencode-muse-1.3-quota-limits

**Logged**: 2026-09-02T21:43:27+02:00
**Priority**: medium
**Status**: pending
**Area**: tests

### Summary
Pi resolved both newly registered Muse Spark 1.3 routes, but neither smoke test returned the required exact `OK` because the providers rate-limited the configured accounts.

### Error
```text
opencode-go: HTTP 429 GoUsageLimitError - Monthly usage limit reached; resets in 16 days.
opencode-zen: HTTP 429 FreeUsageLimitError - Rate limit exceeded; try again later.
```

### Context
- Hyperfine ran one pass per route with `pi --model ... -p 'reply OK'`.
- The model-specific provider errors confirm Pi reached the intended routes, but they do not prove a successful completion.
- Grok Build was intentionally not modified because Aubrey's condition requires working Pi tests first.

### Suggested Fix
Retry the Zen route after its rate limit clears. Do not spend available Go balance or alter the Grok configuration without explicit approval; only wire Grok after a green exact-OK Pi test.

### Metadata
- Reproducible: unknown
- Related Files: `~/.pi/agent/models.json`, `~/.pi/agent/settings.json`, `~/.grok/config.toml`
- Tags: pi, opencode-go, opencode-zen, muse-spark-1.3, quota, rate-limit

---

## [ERR-20260902-SCAN-001] local-harness-scan-duplicate

**Logged**: 2026-09-02T21:43:27+02:00
**Priority**: medium
**Status**: pending
**Area**: tooling

### Summary
The post-write local AIMI harness scan failed on an existing duplicate model-order row.

### Error
```text
sqlite3.IntegrityError: UNIQUE constraint failed: model_order_profile_entries.profile_id, model_order_profile_entries.provider_id, model_order_profile_entries.model_identifier
```

### Context
- `skills/scripts/catalogue scan` was run after the Pi configuration write.
- The Pi JSON files are valid and `pi --list-models`/`pi-order` confirmed both new entries; the failure occurred while refreshing the local catalogue's harness inventory.

### Suggested Fix
Repair the duplicate-safe model-order scan path before relying on `catalogue scan` for local validation. Do not alter the Pi configuration as a workaround.

### Metadata
- Reproducible: unknown
- Related Files: `scan_local_harnesses.py`, `aimi.db`
- Tags: aimi, harness-scan, sqlite, duplicate

---

## [ERR-20260905-DROID-001] pi-droid bridge auth and model-selection defects

**Logged**: 2026-09-05T00:52:00+02:00
**Priority**: high
**Status**: resolved
**Area**: config

### Summary
The published `@victormilk/pi-droid@0.1.1` bridge passed a literal environment-variable name to Droid and did not forward the Pi-selected model into the Droid session.

### Error
```text
Pi smoke test: Error: 401 status code (no body)
Runtime probe: Cannot read properties of undefined (reading 'modelId')
```

### Context
- Pi provider config used `apiKey: "FACTORY_API_KEY"`; Pi requires `$FACTORY_API_KEY` for environment interpolation.
- The installed SDK 0.2 session exposes `initResult.settings`, not the newer `.settings` getter.
- The bridge registered multiple model IDs but created the Droid session without `modelId`.

### Suggested Fix
Use `$FACTORY_API_KEY`, track the selected model/reasoning in bridge state, pass `modelId` and `reasoningEffort` to `createSession`, and use `updateSettings` when Pi switches models.

### Metadata
- Reproducible: yes
- Related Files: `~/.pi/agent/npm/node_modules/@victormilk/pi-droid/src/providers.ts`, `~/.pi/agent/npm/node_modules/@victormilk/pi-droid/src/discovery.ts`
- Tags: pi, droid, factory, sdk, api-key, model-selection

### Resolution
- **Resolved**: 2026-09-05T00:52:00+02:00
- **Notes**: Patched the pinned local package, added the four requested live model IDs and reasoning maps, and verified all four through Pi with exact `OK` responses.
---

## [ERR-20260907-ASIDE-001] aside skill name mismatch

**Logged**: 2026-09-07T11:09:47Z
**Priority**: low
**Status**: pending
**Area**: infra

### Summary
`aside skills show x-twitter` failed even though the Aside task exposed an X/Twitter skill named `x-twitter` in its output.

### Error
```text
Unknown skill: x-twitter. Run 'aside skills list'.
```

### Context
- Attempted to inspect the matching Aside X skill before using the REPL for an approved media post.
- The earlier `aside` task supplied the X/Twitter skill instructions inline, but the local `aside skills` command did not accept that name.

### Suggested Fix
Use the existing `post-to-x` skill and browser DOM workflow; if the Aside X skill needs inspection, run `aside skills list` first and use the exact locally registered name.

### Metadata
- Reproducible: yes
- Related Files: `/Users/TH33_ORACL3/.agents/skills/post-to-x/SKILL.md`
- Tags: aside, x, skills, cli
---

## [ERR-20260907-RESEARCH-001] Antigravity shell wrapper unmatched quote

**Logged**: 2026-09-07T23:14:30+02:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
The first Antigravity research launch failed before execution because the inline shell wrapper had an unmatched quote. The parallel Firecrawl batch completed successfully.

### Error
```text
/bin/bash: -c: line 47: unexpected EOF while looking for matching `"'
```

### Context
- Intended command: one `agy --dangerously-skip-permissions --print ... --model ...` process writing raw evidence to the dated research folder.
- The prompt was embedded in a long nested shell command, which made quote diagnosis ambiguous.
- No Antigravity request was sent by the failed wrapper.

### Suggested Fix
Write the structured prompt to a file first, then pass it to the single `agy` process with shell file substitution. Keep the Firecrawl batch separate and verify raw output files by size.

### Metadata
- Reproducible: unknown
- Related Files: `/Users/TH33_ORACL3/AZ Labs/4 - Research/2026-09-07_rapidmlx-qwen35-4b-m4-mini-fact-check/`
- Tags: agy, research, shell-quoting, firecrawl

### Resolution
- **Resolved**: 2026-09-07T23:15:00+02:00
- **Notes**: Retrying with a prompt file and a simpler `agy` invocation; no source/config files are being changed.
---

## [ERR-20260907-BIRD-001] Bird read unavailable without Safari cookies

**Logged**: 2026-09-07T23:12:41+02:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
The authenticated Bird X reader could not read the target post because no Safari Twitter cookies were available.

### Error
```text
No Twitter cookies found in Safari. Make sure you are logged into x.com in Safari.
```

### Context
- Attempted read: `bird read https://x.com/rapidmlx/status/2097010453574733958?s=20 --json-full`.
- Anonymous `synd 2097010453574733958 --json` returned the complete tweet text and media metadata, so no user-facing fact-check evidence was lost.

### Suggested Fix
Use `synd` for single-tweet retrieval when Bird cookies are unavailable; use Bird only when surrounding X context, search or replies are required.

### Metadata
- Reproducible: unknown
- Related Files: `/Users/TH33_ORACL3/.agents/skills/bird/SKILL.md`
- Tags: bird, x, cookies, syndication

### Resolution
- **Resolved**: 2026-09-07T23:12:41+02:00
- **Notes**: Continued with the documented anonymous syndication fallback; no browser login or cookie changes were made.
---

## [ERR-20260907-FIRECRAWL-001] feedback subcommand unavailable

**Logged**: 2026-09-07T23:29:00+02:00
**Priority**: low
**Status**: pending
**Area**: tooling

### Summary
The installed Firecrawl CLI accepted search and scrape operations but did not provide the documented `feedback` subcommand.

### Error
```text
unknown command 'feedback'
```

### Context
- Attempted to submit the documented endpoint feedback for four completed scrape jobs.
- The research and verification artifacts were already written successfully.
- The installed CLI reported v1.16.0, while the local skill documents feedback commands that are not present in this binary.

### Suggested Fix
Check `firecrawl --help` before submitting feedback; if the installed CLI lacks the command, retain the scrape IDs and use the supported feedback mechanism when the CLI is upgraded.

### Metadata
- Reproducible: yes
- Related Files: `/Users/TH33_ORACL3/AZ Labs/4 - Research/2026-09-07_token-harbor-deepseek-v4-flash-fact-check/`
- Tags: firecrawl, cli, feedback, version-mismatch
---

## [ERR-20260907-PROVIDER-CHECK-001] verification helper fallbacks

**Logged**: 2026-09-07T23:31:40+02:00
**Priority**: low
**Status**: resolved
**Area**: tooling

### Summary
The first Antigravity verification call timed out, AIMI rejected the unsupported `--json` flag, and a primary Firecrawl batch hit its per-minute limit.

### Error
```text
Error: timeout waiting for response
ami: error: unrecognized arguments: --json
Rate limit exceeded. Consumed (req/min): 16, Remaining (req/min): 0
```

### Context
- Provider/free-API fact check for the X post at status `2096970679354785877`.
- Retried Antigravity with a simpler prompt and the supported Gemini 3.8 Flash (Low) route.
- Used AIMI's default JSON output without `--json`.
- Switched targeted Firecrawl scrapes to the secondary key, then corroborated with official pages fetched directly.

### Suggested Fix
Use the documented default JSON output for AIMI, keep Antigravity prompts short with a longer bounded timeout, and switch Firecrawl accounts on 429s as the skill requires.

### Metadata
- Reproducible: yes
- Related Files: `/Users/TH33_ORACL3/.agents/skills/ai-model-index/SKILL.md`, `/Users/TH33_ORACL3/.agents/skills/search/SKILL.md`
- Tags: aimi, agy, firecrawl, provider-verification

### Resolution
- **Resolved**: 2026-09-07T23:31:40+02:00
- **Notes**: Verification completed using the successful retry and official provider pages; no catalogue writes were made.
---

## [ERR-20260908-HARNESS-001] AIMI remote-write and Grok model-key mismatch

**Logged**: 2026-09-08T13:50:00+02:00
**Priority**: medium
**Status**: resolved
**Area**: config

### Summary
The Pal-forwarding `aimi` write commands targeted `/root` instead of the local Mac harness files, and the generated Grok configuration key differed from the underlying model ID expected by `grok -m`.

### Error
```text
Aside account dir not found: /root/.aside/u/0
Couldn't set model 'openrouter-nvidia-nemotron-3-ultra-550b-a55b:free': unknown model id
```

### Context
- Local Mac harness files were updated directly after inspecting the generated fragments.
- Grok already listed the generated config key `openrouter-nemotron-3-ultra-free`; using that key passed the smoke test.
- The unintended remote Pi registration was restored from its timestamped backup.

### Suggested Fix
Do not use Pal-forwarding `aimi` write commands for Mac harness configuration. Use local config writers or the exact harness-specific apply path, then smoke-test the harness's registered model key.

### Metadata
- Reproducible: yes
- Related Files: `~/.aside/u/0/models.json`, `~/.pi/agent/models.json`, `~/.grok/config.toml`, `~/.factory/settings.json`, `~/.zcode/v2/config.json`
- Tags: aimi, pal-forwarding, harnesses, grok

### Resolution
- **Resolved**: 2026-09-08T13:52:00+02:00
- **Notes**: Local configurations validated; Pi, Aside, Droid, and Grok smoke tests passed. ZCode configuration validated but no local ZCode CLI smoke-test binary is installed.
---
