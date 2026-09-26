# Logres Devin Autonomous Lead Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one persistent, supervised Devin Executive Lead that continuously plans, assigns, recovers, and records Logres work while preserving Brain authority, verification gates, spending limits, credential boundaries, and game-first priorities.

**Architecture:** `logres-devin-lead` is a thin service over existing Brain, Elastic Capacity, swarm/router, verifier, and supervisor surfaces. `logres_devin_lead.py` owns deterministic planning/election/recovery logic; the CLI owns status/run/tick/pause/resume commands; `devin_lead.json` carries bounded policy; the systemd unit provides crash restart. The Lead never merges or invents a parallel task database.

**Tech Stack:** Python 3, SQLite/WAL Brain DB, existing `logres-brain`, `logres-capacity`, `logres-swarm`, systemd user service, JSON config/state.

**Spec:** `docs/superpowers/specs/2026-09-26-logres-devin-autonomous-lead-design.md`

## Global Constraints

- Target integration branch is `feat/logres-reconstruction`; never modify `main`.
- Brain remains the single task/lease/provenance authority.
- Prefer visible Logres game completion/fidelity over new infrastructure unless measurable critical-path value justifies the latter.
- Use free SWE-2 Max for routine Devin planning/engineering; never authorize paid models unless existing budget policy explicitly permits it.
- Never merge, push protected branches, weaken verification gates, modify credentials, widen privilege boundaries, or increase spending limits.
- Enforce single-leader election, heartbeat, emergency pause, bounded generation, semantic dedupe, cooldowns, cycle rejection, and an infrastructure-to-game-work budget.
- Persist every planning decision, assignment, recovery, and escalation to Brain.
- Reuse `logres-capacity` and `logres-swarm`; do not build a second scheduler.

## Review Focus

- Split-brain startup: a second Lead process must fail closed while a healthy leader lease/heartbeat is current. Covered in Task 1 tests.
- Paused mode: emergency pause must stop task creation/dispatch/recovery while heartbeat/status remain healthy and observable. Covered in Task 1 and Task 5 tests.
- Stale or contradictory Brain data: planning must refresh dependencies/leases/integration state before action and must not assign blocked/terminal/owned tasks. Covered in Task 2 and Task 3 tests.
- Runaway task creation: duplicate fingerprints, dependency cycles, cooldown breaches, generation caps, or infrastructure-budget violations must suppress creation. Covered in Task 3 tests.
- Partial worker/verifier failure: lost workers or failed verification must preserve evidence/worktrees, create bounded recovery/escalation, and never auto-approve the Lead's own changes. Covered in Task 4 tests.

---

### Task 1: Leader lifecycle, policy, pause, and heartbeat

**Files:**
- Create: `ops/logres-control-plane/config/devin_lead.json`
- Create: `ops/logres-control-plane/lib/logres_devin_lead.py`
- Create: `ops/logres-control-plane/tests/test_devin_lead.py`

**Interfaces:**
- Produces: `load_lead_policy(path: Path) -> dict`, `acquire_leader(conn, *, instance_id: str, now: float, ttl_seconds: int) -> bool`, `renew_leader(...) -> bool`, `read_pause(root: Path) -> dict`, `write_heartbeat(root: Path, payload: dict) -> None`.
- Consumes: existing Brain SQLite tables and filesystem root only; no dispatch yet.

- [ ] **Step 1: Write failing lifecycle tests**
  Add `test_single_leader_election`, `test_stale_leader_can_be_reclaimed`, `test_pause_blocks_actions_but_keeps_heartbeat`, and `test_policy_rejects_paid_default`.
- [ ] **Step 2: Run lifecycle tests and confirm RED**
  Run: `python3 -m unittest ops/logres-control-plane/tests/test_devin_lead.py -k 'leader or pause or policy'`
  Expected: failures because lifecycle functions/config do not exist.
- [ ] **Step 3: Implement minimal lifecycle primitives**
  Add a `devin_lead_runtime` SQLite table only if absent, store one current leader lease, use atomic JSON heartbeat writes under `control/devin-lead-heartbeat.json`, and read emergency pause from `control/devin-lead.pause`.
- [ ] **Step 4: Run lifecycle tests and confirm GREEN**
  Expected: all Task 1 tests PASS.
- [ ] **Step 5: Commit**
  `git add ops/logres-control-plane/config/devin_lead.json ops/logres-control-plane/lib/logres_devin_lead.py ops/logres-control-plane/tests/test_devin_lead.py && git commit -m "feat: add Devin lead lifecycle guard"`

### Task 2: Deterministic planning snapshot and game-first prioritization

**Files:**
- Modify: `ops/logres-control-plane/lib/logres_devin_lead.py`
- Modify: `ops/logres-control-plane/tests/test_devin_lead.py`

**Interfaces:**
- Produces: `collect_planning_snapshot(conn, root: Path, policy: dict) -> dict`, `score_ready_task(task: dict, snapshot: dict, policy: dict) -> tuple`, `select_frontier(snapshot: dict, policy: dict) -> list[dict]`.
- Consumes: Brain tasks/leases/dependencies/scopes, integration queue/preflight state, regressions, `capacity-state.json`, swarm worker state, milestone/task metadata.

- [ ] **Step 1: Write failing snapshot/prioritization tests**
  Add `test_snapshot_refreshes_tasks_dependencies_leases_and_verification`, `test_game_critical_path_beats_noncritical_infrastructure`, `test_blocked_terminal_or_owned_tasks_are_excluded`, and `test_resource_pressure_reduces_frontier_size`.
- [ ] **Step 2: Run Task 2 tests and confirm RED**
  Run: `python3 -m unittest ops/logres-control-plane/tests/test_devin_lead.py -k 'snapshot or frontier or priority'`
- [ ] **Step 3: Implement snapshot and scoring**
  Read all planning inputs fresh per cycle; rank P0/P1 visible-game/critical-path work before control-plane work unless the latter explicitly unblocks the critical path; use capacity pressure and verifier backlog only to bound frontier size, never to alter task truth.
- [ ] **Step 4: Run Task 2 tests and confirm GREEN**
- [ ] **Step 5: Commit**
  `git add ops/logres-control-plane/lib/logres_devin_lead.py ops/logres-control-plane/tests/test_devin_lead.py && git commit -m "feat: plan Devin lead work from Brain state"`

### Task 3: Bounded task creation, dedupe, routing, and assignment

**Files:**
- Modify: `ops/logres-control-plane/lib/logres_devin_lead.py`
- Modify: `ops/logres-control-plane/tests/test_devin_lead.py`

**Interfaces:**
- Produces: `proposal_fingerprint(proposal: dict) -> str`, `validate_proposal(conn, proposal: dict, snapshot: dict, policy: dict) -> tuple[bool, str]`, `create_bounded_task(conn, proposal: dict) -> str | None`, `route_task(task: dict, snapshot: dict, policy: dict) -> dict`, `dispatch_plan(root: Path, routes: list[dict], *, execute: bool) -> dict`.
- Consumes: existing Brain task tables, semantic/concurrency metadata, `logres-capacity tick`, `logres-swarm tick`, existing free-model/budget policy.

- [ ] **Step 1: Write failing generation/routing tests**
  Add `test_duplicate_fingerprint_is_suppressed`, `test_dependency_cycle_is_rejected`, `test_generation_cap_and_cooldown_hold`, `test_infrastructure_budget_preserves_game_slots`, `test_free_devin_is_preferred_for_safe_implementation`, and `test_paid_route_is_never_enabled_by_lead`.
- [ ] **Step 2: Run Task 3 tests and confirm RED**
- [ ] **Step 3: Implement bounded decomposition, generation, and routing**
  Decompose unmet milestone criteria into bounded proposals, then limit each cycle with policy `max_new_tasks_per_cycle`; reject matching semantic fingerprint/concurrency key/cycle; preserve explicit acceptance/scope/dependencies; route implementation through existing swarm/capacity and research through existing research lanes. Do not call model APIs directly from the Lead.
- [ ] **Step 4: Run Task 3 tests and confirm GREEN**
- [ ] **Step 5: Commit**
  `git add ops/logres-control-plane/lib/logres_devin_lead.py ops/logres-control-plane/tests/test_devin_lead.py && git commit -m "feat: bound Devin lead task routing"`

### Task 4: Monitoring, recovery, metrics, and provenance

**Files:**
- Modify: `ops/logres-control-plane/lib/logres_devin_lead.py`
- Modify: `ops/logres-control-plane/tests/test_devin_lead.py`

**Interfaces:**
- Produces: `inspect_owned_work(conn, snapshot: dict, policy: dict) -> list[dict]`, `plan_recoveries(conn, observations: list[dict], policy: dict) -> list[dict]`, `record_lead_event(conn, *, event_type: str, subject: str, body: str, task_id: str | None, dedupe_key: str) -> int`, `compute_lead_metrics(conn, snapshot: dict) -> dict`.
- Consumes: Brain leases/events, swarm jobs, verification queue/results, regression rows, task recovery records.

- [ ] **Step 1: Write failing recovery/provenance tests**
  Add `test_stale_worker_recovery_preserves_evidence`, `test_failed_verification_creates_bounded_repair_not_auto_approval`, `test_every_assignment_recovery_and_escalation_records_brain_event`, and `test_metrics_report_latency_rework_queue_pass_rate_utilization_and_contention`.
- [ ] **Step 2: Run Task 4 tests and confirm RED**
- [ ] **Step 3: Implement recovery and metrics**
  Renew healthy owned leases, recover only stale/failed work through existing Brain/swarm recovery semantics, emit bounded repair proposals, preserve worktrees/evidence, and persist deduped provenance events. Metrics are observational and feed governed evolution; they do not self-promote policy.
- [ ] **Step 4: Run Task 4 tests and confirm GREEN**
- [ ] **Step 5: Commit**
  `git add ops/logres-control-plane/lib/logres_devin_lead.py ops/logres-control-plane/tests/test_devin_lead.py && git commit -m "feat: recover and measure Devin lead work"`

### Task 5: CLI loop, persistent service, status, and integration gate

**Files:**
- Create: `ops/logres-control-plane/bin/logres-devin-lead`
- Create: `ops/logres-control-plane/systemd/logres-devin-lead.service`
- Modify: `ops/logres-control-plane/lib/logres_devin_lead.py`
- Modify: `ops/logres-control-plane/tests/test_devin_lead.py`

**Interfaces:**
- Produces CLI commands: `logres-devin-lead tick [--dry-run]`, `run`, `status [--json]`, `pause --reason <text>`, `resume`.
- Produces library entrypoints: `lead_tick(root: Path, *, execute: bool = True) -> dict`, `run_forever(root: Path, *, interval_seconds: int) -> int`.
- Service: `Restart=always`, bounded restart delay, no privileged user, invokes deployed `/home/ubuntu/logres/bin/logres-devin-lead run`.

- [ ] **Step 1: Write failing CLI/service tests**
  Add `test_tick_dry_run_has_no_side_effects`, `test_run_refuses_second_leader`, `test_pause_resume_cli`, `test_status_reports_heartbeat_frontier_metrics_and_last_decision`, `test_service_restarts_and_runs_unprivileged`, and `test_paused_run_loop_does_not_dispatch`.
- [ ] **Step 2: Run Task 5 tests and confirm RED**
- [ ] **Step 3: Implement CLI and run loop**
  Each cycle: acquire/renew leader → heartbeat → refresh snapshot → honor pause → inspect/recover → compute capacity → plan bounded work → execute existing capacity/swarm routing → record decisions/metrics → sleep. Exceptions are recorded and the loop remains fail-closed.
- [ ] **Step 4: Run complete focused suite**
  Run: `python3 -m unittest ops/logres-control-plane/tests/test_devin_lead.py`
  Expected: all tests PASS.
- [ ] **Step 5: Run static and fast gates**
  Run: `python3 -m py_compile ops/logres-control-plane/bin/logres-devin-lead ops/logres-control-plane/lib/logres_devin_lead.py && git diff --check && /home/ubuntu/logres/bin/logres-gate fast`
  Expected: PASS.
- [ ] **Step 6: Commit**
  `git add ops/logres-control-plane/bin/logres-devin-lead ops/logres-control-plane/systemd/logres-devin-lead.service ops/logres-control-plane/lib/logres_devin_lead.py ops/logres-control-plane/tests/test_devin_lead.py && git commit -m "feat: run persistent autonomous Devin lead"`

### Task 6: Candidate verification, Brain handoff, and runtime activation dependency

**Files:**
- No new source files in this task.
- Runtime deployment manifest is intentionally outside this task's five-file scope and must be handled by the existing deployment-closure workflow once `scripts/logres/deploy_control_plane.py` is unclaimed.

- [ ] **Step 1: Run scope and candidate gates**
  Run `logres-scope-check DEVIN-AUTONOMOUS-LEAD-001` and `logres-gate candidate HEAD`; expected PASS.
- [ ] **Step 2: Handoff immutable candidate**
  Run `logres-finish-task chatgpt-devinlead DEVIN-AUTONOMOUS-LEAD-001`; expected branch push, immutable SHA, integration-review record, and READY_FOR_PREFLIGHT.
- [ ] **Step 3: Require shared preflight and canonical apply**
  Do not manually merge; only apply a VERIFIED exact-SHA merge preflight.
- [ ] **Step 4: Close deployment separately if needed**
  Verify deployed `bin/logres-devin-lead`, `lib/logres_devin_lead.py`, `config/devin_lead.json`, and `systemd/logres-devin-lead.service`; if absent, create/finish the narrow deployment-closure task after the manifest claim clears.
- [ ] **Step 5: Operational proof**
  Start/ensure the deployed user service, verify one healthy leader heartbeat, verify a second instance fails closed, exercise pause/resume, run one dry planning cycle, then confirm Brain provenance and zero protected-branch/credential/spend mutations.
