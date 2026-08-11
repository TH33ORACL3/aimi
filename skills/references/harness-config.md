# Changing the model in any harness

AIMI records how every harness is configured so any agent can point any harness at
any provider/model route quickly. The single entry point is:

```bash
aimi harness-fragment <harness> <provider> <model>
```

It returns the exact config fragment to apply (config path, format, apply steps)
for that harness. The `harness_provider_support` table in `aimi.db` holds the
per-(harness, provider) config schema, and `harness-fragment` reads it plus the
catalogue route data (base URL, API style, auth env var, context, max tokens).

Supported harness ids: `pi`, `droid`, `opencode`, `zcode`, `codex-cli`, `mistral-vibe`,
`antigravity-cli`, `cline`, `aside`, `claude-code`, `grok-build`.

## Per-harness recipes

| Harness | Config location | Format | Apply |
|---|---|---|---|
| **Pi** | `~/.pi/agent/models.json` + `~/.pi/agent/settings.json` | JSON | `aimi pi-register <p> <m> --apply` then `aimi pi-select <p> <m> --apply` |
| **Aside** | `~/.aside/u/0/models.json` + `~/.aside/u/0/credentials.json` | JSON | `aimi aside-register <p> <m> --apply`, then restart Aside. Invoke with `aside -m <p>/<m>` |
| **Grok Build** | `~/.grok/config.toml` | TOML | `aimi grok-config <p> <m>` → append `[model.*]` block. Thinking models need `api_backend = "messages"` |
| **Claude Code** | `~/.zshrc` (`ANTHROPIC_*` env) + local proxy for OpenAI-only providers | env | Anthropic-compatible: set `ANTHROPIC_BASE_URL`/`AUTH_TOKEN`/`MODEL`. OpenAI-only (e.g. Cline): local translation proxy `~/bin/claude-cline-proxy.py` + `claude-cline` launcher |
| **Droid** | `~/.factory/settings.json` → `customModels[]` | JSON | append `{id:"custom:<p>:<m>", provider, model, baseUrl, apiKey, displayName, maxOutputTokens}` |
| **OpenCode** | `~/.config/opencode/opencode.json` | JSON | add `provider.<id>` block with `options.baseURL` and `models.<id>`; auth via the provider env var |
| **ZCode** | `~/.zcode/v2/config.json` | JSON | add `provider.<key>` block (`source="custom"`, `kind="openai-compatible"`) with `options.baseURL` and `models.<id>` map. **apiKey is stored literally** in `options.apiKey` — substitute the current value of the provider env var, and restart the ZCode app so it reloads config.json |
| **Cline** | `~/.cline/data/settings/providers.json` | JSON | add `providers.<id>.settings` with `provider`, `model`, `auth` (OAuth managed by the app) |
| **Mistral Vibe** | `~/.vibe/config.toml` | TOML | add a `[models.*]` entry; set `active_model` |
| **Antigravity CLI** | `~/.gemini/antigravity-cli/settings.json` | JSON | set the `model` field |
| **Codex CLI** | `~/.codex/config.toml` | TOML | set `model = "<id>"` and `[model_providers."<p>"]` with `name`, `base_url`, `env_key` |

## Privacy rules (important)

- **Secrets never enter the catalogue.** Fragments reference the provider's
  `auth_env_var` name (e.g. `$CLINE_API_KEY`), never the key value. Keys live only
  in the local credential file `~/.config/aimi/credentials.env` (mode 0600) or the
  harness's own 0600 config.
- **ZCode is the exception to env-var references.** Its `options.apiKey` field stores
  the literal key, so the apply step must embed the actual value (from the provider
  `auth_env_var`) rather than a `$ENV` reference. This mirrors the existing custom
  providers that ZCode already ships with. Keys still never enter the catalogue DB.
- For reasoning-capable custom routes, AIMI emits a `thinkingLevelMap` covering
  `off`, `minimal`, `low`, `medium`, `high`, and `xhigh`, which makes those levels
  selectable in Aside. `ultrabrowse` is not part of the model JSON; it is Aside's
  proactive mode and is selected with `aside --effort ultrabrowse`. The CLI can
  accept that flag, but the live account plan still controls whether Ultrabrowse
  is unlocked; custom JSON cannot bypass the plan gate.
- The Claude Code ↔ Cline routing is a **local** translation proxy on
  `127.0.0.1:8090`; nothing leaves the machine except the request to the provider.
- Claude Code env vars in `~/.zshrc` are exported normally; no key values are
  stored there (the proxy owns the ClinePass key).

## Claude Code specifics

- Claude Code speaks only the **Anthropic Messages API**.
- Anthropic-compatible providers (e.g. DeepSeek via `https://api.deepseek.com/anthropic`)
  route directly with `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_MODEL`.
- OpenAI-compatible providers (e.g. ClinePass) need the local proxy
  `~/bin/claude-cline-proxy.py` + the `claude-cline` launcher.
- For ClinePass, use the **subscription-namespaced** model id `cline-pass/<model>`.
  The bare `deepseek/deepseek-v4-flash` id is a free-tier bucket with a daily cap
  (`INFERENCE_CAP_ERROR` 429); `cline-pass/` bills the subscription quota.
