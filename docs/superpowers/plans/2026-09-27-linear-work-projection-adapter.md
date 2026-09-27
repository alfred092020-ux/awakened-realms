# Linear Work Projection Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Project canonical Brain tasks into bounded, deterministic Linear issue intents while routing external drift into review proposals and preserving Brain/Git authority.

**Architecture:** Add one pure adapter module over the existing `logres_integration` primitives. The adapter reads canonical task/task-metadata/task-acceptance rows, emits only `title`, `description`, `priority`, and target-configured `team/project/labels`, plans idempotent create/update intents, and turns observed managed-field drift into proposals. It never calls Linear directly and never mutates Brain task, lease, evidence, branch, or integration-authority tables.

**Tech Stack:** Python 3.12, SQLite, stdlib `unittest`, existing `logres_integration` intent/binding/proposal APIs.

**Spec:** `/home/ubuntu/logres/control/packets/BRAIN-PLUGIN-LINEAR-ADAPTER-001-chatgpt-system-finish.txt`

## Global Constraints

- Integration branch is `feat/logres-reconstruction`; never touch `main`.
- Live Linear writes are out of scope and remain in `BRAIN-PLUGIN-LINEAR-CANARY-001`.
- Use capability `linear.issue.write` before creating any write intent.
- Linear may never mutate Brain leases, integration authority, evidence confidence, Git branches, or `main`.
- Projection payloads must be deterministic, bounded, sanitized, and compatible with Linear `save_issue` fields.

## Review Focus

- Missing/disabled target returns a bounded non-write result.
- Missing/expired `linear.issue.write` capability creates no write intent.
- Repeated identical projections reuse the same intent instead of multiplying writes.
- Human edits to managed Linear fields create proposals and never mutate canonical Brain task rows.
- Oversized task titles/acceptance text truncate deterministically without destabilizing projection hashes.

---

### Task 1: Deterministic Task Projection and Write Intent Planning

**Files:**
- Create: `ops/logres-control-plane/lib/logres_integration_linear.py`
- Test: `ops/logres-control-plane/tests/test_integration_linear.py`

**Interfaces:**
- Consumes: `register_target`, `compatible_capabilities`, `create_intent`, `get_binding`, `canonical_hash` from `logres_integration`.
- Produces: `project_task(conn, task_id, target_key) -> dict` and `plan_task_sync(conn, task_id, target_key, chat_id, now_epoch) -> dict`.

- [ ] **Step 1: Write failing projection/create/update/disabled/missing-capability tests.**
- [ ] **Step 2: Run `python3 -m unittest ops.logres-control-plane.tests.test_integration_linear -v` and confirm RED.**
- [ ] **Step 3: Implement bounded deterministic projection and idempotent create/update intent planning.**
- [ ] **Step 4: Run the Linear adapter tests and confirm GREEN.**
- [ ] **Step 5: Commit the projection/planning slice.**

### Task 2: Drift-to-Proposal and Authority Boundaries

**Files:**
- Modify: `ops/logres-control-plane/lib/logres_integration_linear.py`
- Modify: `ops/logres-control-plane/tests/test_integration_linear.py`

**Interfaces:**
- Consumes: `create_proposal`, `upsert_binding`, `canonical_hash` from `logres_integration`.
- Produces: `observe_issue(conn, task_id, target_key, provider_entity_id, observed) -> dict`.

- [ ] **Step 1: Write failing drift/idempotence/no-authority-mutation tests.**
- [ ] **Step 2: Run the focused tests and confirm RED.**
- [ ] **Step 3: Implement managed-field comparison and idempotent proposal creation only.**
- [ ] **Step 4: Run focused + generic integration tests, then the full control-plane suite.**
- [ ] **Step 5: Run scope/fast/build, commit/push exact SHA, and send it through independent L3 + exact candidate verification.**
