# Errors

## [ERR-20260721-001] bird

**Logged**: 2026-07-21T21:15:00+02:00
**Priority**: medium
**Status**: resolved
**Area**: infra

### Summary
Read-only X verification failed because bird had no usable authentication cookies.

### Error
`Missing auth_token` and `Missing ct0`.

### Context
Four official model-release posts were tested with Hyperfine and bird.

### Suggested Fix
Do not retry the same path. Use Firecrawl extraction for known official X URLs and preserve immutable local captures.

### Metadata
- Reproducible: yes
- Related Files: `evidence/x/`

### Resolution
All four official posts were successfully captured through Firecrawl.

---

## [ERR-20260721-002] endpoint-monitor

**Logged**: 2026-07-21T21:15:00+02:00
**Priority**: high
**Status**: resolved
**Area**: backend

### Summary
Volatile endpoint fields generated false change records.

### Error
OpenCode Zen reported all 14 models changed and OpenCode Go all 22 changed on the second baseline run.

### Context
The provider returned regenerated `created` values despite stable model IDs.

### Suggested Fix
Exclude volatile provider fields and determine change status from normalized records.

### Metadata
- Reproducible: yes
- Related Files: `monitor_endpoints.py`

### Resolution
Implemented and independently reran; all nine providers returned unchanged.
