# Learnings

## [LRN-20260721-001] correction

**Logged**: 2026-07-21T23:35:57+02:00
**Priority**: high
**Status**: promoted
**Area**: backend

### Summary
A model route answer must include what happened in the latest test, not only when it was tested.

### Details
A `last_tested_at` timestamp without the test status, outcome/reply or error is incomplete and not useful for judging route health. Route tables should show the latest result alongside the timestamp, including HTTP status, harness and latency when available.

### Suggested Action
Keep `last_test` structured in `modelctl where`, `modelctl route`, and related model-info output. Agents must render both the timestamp and outcome in user-facing model tables.

### Metadata
- Source: user_feedback
- Related Files: `modelctl.py`, `/Users/TH33_ORACL3/.agents/skills/model-catalogue/SKILL.md`, `/Users/TH33_ORACL3/.pi/agent/AGENTS.md`
- Tags: model-catalogue, handshake-tests, reporting, user-preference

### Resolution
- **Resolved**: 2026-07-21T23:36:35+02:00
- **Notes**: Added structured `last_test` output with result/outcome fields and promoted the rule to durable agent memory and the canonical model-catalogue skill.
