# Devin Autonomy Launch Gate Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore fail-closed unattended Devin dispatch without false nftables failures, duplicate scheduler dispatch, or certificate invalidation from unrelated gameplay commits.

**Architecture:** Keep root authority inside the existing typed Nexus operations. Swarm will accept exactly one unprivileged preflight blind spot, `network_policy`, only after the root Nexus provision operation succeeds and every other required preflight check passes. Certificate freshness will compare the certified isolation-surface hashes against both current source bytes and deployed runtime hashes. Capacity dispatch will reuse the same `/tmp/logres-swarm.cron.lock` single-flight contract as Supervisor and legacy cron.

**Tech Stack:** Python 3, unittest, SQLite-backed Logres control plane, Nexus Commander typed privileged operations, flock.

**Spec:** `/home/ubuntu/logres/control/packets/DEVIN-AUTONOMY-LAUNCH-GATE-REPAIR-001-chatgpt-autonomyrepair.txt`

## Global Constraints

- Never modify `main`; target integration remains `feat/logres-reconstruction`.
- Automatic Devin models remain free-only, with `swe-2-max` preferred.
- Generic privileged exec remains disabled. Root work uses typed Nexus operations only.
- Any missing, malformed, or mismatched isolation evidence fails closed.
- Keep the diff inside the task's declared scopes.

## Review Focus

- A root provision failure must never be masked by preflight reconciliation.
- A preflight with any blocker besides `network_policy` must remain blocked.
- Missing or malformed certificate surface hashes must block unattended Devin.
- A deployed runtime hash mismatch for any certified isolation file must block unattended Devin.
- A concurrent Capacity/cron/Supervisor tick must exit through the shared lock without acquiring a second worker.

---

### Task 1: Sustainable isolation certificate freshness

**Files:**
- Modify: `ops/logres-control-plane/lib/logres_swarm.py`
- Modify: `ops/logres-control-plane/bin/logres-swarm`
- Test: `ops/logres-control-plane/tests/test_swarm.py`

**Interfaces:**
- Produces: `isolation_surface_hashes(checkout: Path, certificate: dict) -> dict[str, str]`
- Produces: `isolation_certificate_gate(certificate: dict, current_surface: dict, runtime_deployment: dict) -> tuple[bool, str | None]`
- Consumes certificate `recertification.isolation_surface_sha256` and runtime deployment `files` hashes.

- [ ] Step 1: Replace the HEAD-equality regression test with tests proving an unrelated integration SHA change stays allowed when source/deployed critical hashes match, while source mismatch, deployed mismatch, missing surface evidence, and uncertified state fail closed.
- [ ] Step 2: Run `python3 ops/logres-control-plane/tests/test_swarm.py` and verify the new tests fail for the expected HEAD-bound behavior.
- [ ] Step 3: Implement current-source hash collection from the certificate's exact critical file keys and gate comparisons against both source and normalized runtime-deployment file keys. Treat `integration_sha` as provenance only.
- [ ] Step 4: Update `bin/logres-swarm` to compute current surface hashes and call the new gate without using integration HEAD as freshness authority.
- [ ] Step 5: Run `python3 ops/logres-control-plane/tests/test_swarm.py` and verify green.
- [ ] Step 6: Commit the Task 1 change.

### Task 2: Privileged network-proof reconciliation

**Files:**
- Modify: `ops/logres-control-plane/lib/logres_swarm.py`
- Modify: `ops/logres-control-plane/bin/logres-swarm`
- Test: `ops/logres-control-plane/tests/test_swarm.py`

**Interfaces:**
- Produces: `privileged_network_preflight_ready(preflight_report: dict, provision_ok: bool) -> tuple[bool, str | None]`
- Consumes typed Nexus provision success plus the JSON report from `logres-devin-isolate preflight --json`.

- [ ] Step 1: Add tests proving root provision plus exactly one `network_policy` blocker is accepted, while provision failure, additional blockers, failed required checks, malformed reports, or a missing unit remain blocked.
- [ ] Step 2: Run the focused swarm tests and verify RED.
- [ ] Step 3: Implement the reconciliation helper. It must accept normal `production_ready=true`, or exactly the `network_policy` visibility blocker after successful typed root provision with every other required check green.
- [ ] Step 4: Update `bin/logres-swarm` to use the helper instead of requiring preflight rc=0/`production_ready=true` directly. Preserve cleanup and fail-closed release behavior.
- [ ] Step 5: Run the focused swarm tests and verify green.
- [ ] Step 6: Commit the Task 2 change.

### Task 3: Shared swarm dispatch lock

**Files:**
- Modify: `ops/logres-control-plane/lib/logres_capacity.py`
- Test: `ops/logres-control-plane/tests/test_capacity.py`

**Interfaces:**
- Produces: Capacity invokes the existing swarm binary through `/usr/bin/flock -n -E 0 /tmp/logres-swarm.cron.lock`.
- Consumes: the same lock contract already used by `logres_supervisor._locked()` and legacy swarm cron.

- [ ] Step 1: Change the capacity test to require the shared flock argv and preserve temporary overlay environment behavior.
- [ ] Step 2: Run `python3 ops/logres-control-plane/tests/test_capacity.py` and verify RED because Capacity currently invokes swarm directly.
- [ ] Step 3: Implement the minimal flock wrapper in `execute_swarm_tick`.
- [ ] Step 4: Run capacity tests and verify green.
- [ ] Step 5: Commit the Task 3 change.

### Task 4: Verification, integration handoff, deployment proof, and autonomy resume

**Files:**
- No new production files expected.

**Interfaces:**
- Consumes: Tasks 1 through 3.
- Produces: verified candidate, exact-SHA integration/deployment evidence, refreshed isolation certificate, one real unattended `swe-2-max` job, and resumed autonomy only after proof.

- [ ] Step 1: Run both focused test files, `git diff --check`, and Python compilation on changed Python executables/modules.
- [ ] Step 2: Run the repository's full test command required by the worker gate, then `logres-gate fast`.
- [ ] Step 3: Run `logres-finish-task chatgpt-autonomyrepair DEVIN-AUTONOMY-LAUNCH-GATE-REPAIR-001` and monitor the verified integration handoff. Do not directly merge or push the protected integration branch.
- [ ] Step 4: After Lead integrates the exact verified SHA, deploy the canonical control plane and verify deployed file hashes.
- [ ] Step 5: Refresh the production isolation certificate so its critical surface includes the repaired swarm security gate as well as the existing Devin isolation core. Verify current source hashes and deployed runtime hashes match.
- [ ] Step 6: Run full E2E on the exact integrated SHA.
- [ ] Step 7: Enable swarm, resume the Devin Lead and Supervisor baton, then observe one real unattended `swe-2-max` launch through typed Nexus root provision, systemd isolation, native `--sandbox`, job tracking, and cleanup.
- [ ] Step 8: If the live proof passes, leave autonomy running. If any gate fails, return to paused fail-closed state and record the exact blocker.
