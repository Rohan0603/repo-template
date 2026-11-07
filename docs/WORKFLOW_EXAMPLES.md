# Copy-ready issue and comment examples

These are **examples only**. Replace numbers, SHA values, and links. Never assert that a test ran or approval happened because the example contains those words.

## A. Chief creates a new implementation issue

**GitHub Issue:** `#142 Add idempotent request replay guard`

**Project Status:** `Backlog`; labels: `chief`.

**Outcome:** On repeated identical request IDs, return the persisted result without issuing another external side effect. Supports concurrency control and retry-safety.

**Baseline:** `main` observed SHA `<actual-sha>`; existing files: `<paths>`; API version `<version>`.

**Dependencies:** `#139 durable request store` (native `blocked by`). Explicitly record status and evidence before Ready.

**In scope:** storage-level uniqueness, read-before-write, restart recovery, unit/concurrency tests; no provider change or new runtime permissions.

**Acceptance:**
- Given the same request ID and payload on retried calls, when second call arrives, then exactly one side effect is attempted and a stable result is returned.
- Given same ID but different payload, then fail safely with a specified conflict status.
- Given restart after a committed result, then replay returns the persisted result.
- Given a concurrent collision, then the losing worker returns/retries according to documented policy without double execution.

**Exact checks:** `<real-command>` (unit tests), `<real-command>` (integration), `<real-command>` (lint), CI `<workflow-name>`. Record all PASS/FAIL/NOT RUN.

**Failure/rollback:** Protect existing migration path, require forward/backward schema compatibility and an explicit backout plan. Risk `Elevated` if live data migration applies.

**Chief prepares handoff:**

```text
<!-- handoff-id:142-chief-worker-001 -->
CHIEF RESPONSE/HANDOFF — 2026-11-07T12:00:00Z
DoR: PASS on issue #142; #139 Done verified by commit <sha>.
Decision: choose database unique constraint + recorded replay result.
Approved file scope: <paths>. Rejected: in-memory-only deduplication.
Worker instructions: implement Given/When/Then cases above and capture actual commands/CI.
Risk: Normal for fixture implementation; any production migration escalates.
Next action: change chief -> worker and Project Status -> Ready; read back.
```

Before Worker begins, a real API read-back must show **only** `worker`, `Status=Ready`, and the HANDOFF comment.

## B. Worker requests Chief assistance

```text
<!-- handoff-id:142-worker-chief-002 -->
REQUEST FOR CHIEF — 2026-11-07T15:15:00Z
Current head: <commit-sha>, branch feat/142-replay.
Problem: recorded replay payload can contain sensitive account identifiers.
Evidence: failing negative test <path>, command <command>, exit 1.
Options: hash canonical payload with salt; store redacted fields; encrypt payload.
Decision needed: approved retention/trust boundary and compatibility of old records.
Blocked scope: persistence schema change. Other changes paused to avoid rework.
Next action: change worker -> chief; Project Status -> Blocked; read back.
```

Chief cannot silently invent approval. Research alternatives, record source-backed choice and if needed `chief`+`human` while the Project is `Blocked`. When resolved, post an actionable Chief handoff, remove `human` if present, change `chief` → `worker`, and restore the correct Project status.

## C. Human-only gate, with Chief managing labels

```text
HUMAN ACTION REQUIRED — 2026-11-07T16:00:00Z
Owner must approve deployment of migration #142 on exact PR head <sha>.
Why human: production irreversible data changes; owner release approval required.
Acceptance evidence: issue comment with scope, head SHA and explicit approval.
Until then: chief + human; Project Status=Blocked; no merge/deploy.
```

After the owner records an action, Chief verifies the head and evidence, posts `HUMAN RESOLVED`, **removes `human` itself**, and completes the authorized workflow. The human never has to relabel issues.

## D. Worker completion and Chief acceptance

```text
REVIEW HANDOFF — 2026-11-07T17:00:00Z
Issue #142, PR #188, exact head <sha>, base main@<sha>.
Changed: <file paths>. Acceptance matrix: <table with proof URLs>.
Checks: <command 1> exit 0, <command 2> exit 0; CI <URL> success on <sha>.
NOT RUN: hardware integration; linked validation #191 with owner.
Security/rollback: <specific impacts>. Remaining risk <...>.
Next action: worker -> chief; Project Status=In Review; independent review.
```

Chief reviews the exact head and may request changes (`chief` → `worker`) or authorize a deliberate normal-risk merge after real CI/reviewer gates. For elevated/critical, require owner approval on exact head. Post CLOSEOUT with final merged SHA and verify Project Done + closed issue.

## E. Discussion → actionable decision

Research discussion: `D#21: Compare SQLite-backed lease vs. GitHub-only advisory lease`. Chief and specialists debate options in Discussions. Chief summarizes the approved outcome in issue `#210 ADR: Dispatch serialization`, links the Discussion, records real sources/version dates, and creates blocked-by implementation issues with DoR. No Worker executes a task directly from D#21.
