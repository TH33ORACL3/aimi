# Feature Requests

## [FEAT-20260721-001] evidence-first-personal-model-registry

**Logged**: 2026-07-21T21:15:00+02:00
**Priority**: high
**Status**: in_progress
**Area**: backend

### Requested Capability
A comprehensive personal model intelligence system that discovers models/providers, proves release/spec/pricing facts, inventories local harnesses, optimizes Pi ordering, generates configurations, tracks free windows and monitors new releases.

### User Context
Aubrey uses many harnesses and providers and wants effortless model swapping now, with a sanitized GitHub version later.

### Complexity Estimate
complex

### Suggested Implementation
Continue enriching canonical model evidence, runtime compatibility handshakes, task-specific order profiles, notification policy and historical model coverage on top of the completed SQLite/evidence/monitoring foundation.

### Metadata
- Frequency: first_time
- Related Features: `modelctl.py`, `monitor_endpoints.py`

---

## [FEAT-20260826-001] news-eligibility-for-model-discovery

**Logged**: 2026-08-26T14:23:18+02:00
**Priority**: high
**Status**: in_progress
**Area**: backend

### Requested Capability
Prevent bulk endpoint discoveries from generating website/X news posts, while retaining news candidates for same-day official releases and meaningful aggregator additions.

### User Context
A manual endpoint refresh can expose hundreds of pre-existing model IDs. Treating every `model_added` record as news creates false announcements and unnecessary editorial work.

### Complexity Estimate
medium

### Suggested Implementation
Classify discovery events using run-level batch context, official release-date evidence, and aggregator/provider first-seen semantics. Make the notifier/release desk skip bulk sync events and add deterministic regression tests.

### Metadata
- Frequency: first_time
- Related Features: `model_discovery_notifier`, `model_release_desk`, `endpoint_change_log`
, `export_sanitized.py`
