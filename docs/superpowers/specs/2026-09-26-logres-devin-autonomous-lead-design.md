# Logres Devin Autonomous Lead — Design

Date: 2026-09-26
Task: DEVIN-AUTONOMOUS-LEAD-001
Status: design approved in chat; written spec pending review

## Purpose

Build one persistent Devin Executive Lead that keeps Logres moving when no human chat is active.
It must coordinate existing Brain, swarm, verification, capacity, and evolution systems rather than replace them.
The top-level objective remains visible game completion and fidelity; infrastructure work is justified only by measurable critical-path value.

## Non-goals

- No direct merges or protected-branch pushes.
- No credential changes, spending-limit changes, or paid-model authorization.
- No verification bypass, gate weakening, or self-approval of unverified changes.
- No second scheduler, second task database, or duplicate worker ownership model.
- No autonomous modification of protected security boundaries.

## Runtime shape

`logres-devin-lead` is a supervised long-running service with one active leader at a time.
A database-backed election lease prevents split brain; the service heartbeats and renews only while healthy.
The process supports an explicit emergency pause switch that stops new work while preserving evidence and existing worktrees.
Systemd restarts crashes, but the process must reconstruct state from Brain rather than from in-memory assumptions.
## Planning cycle

Before every planning cycle the Lead reads authoritative live state:

- Brain tasks, dependencies, claims, leases, blockers, and milestones.
- Integration queue, preflight status, regressions, and verification receipts.
- Elastic Capacity plan, host pressure, verifier saturation, quota knowledge, and worker availability.
- Recent task latency, failure/rework rate, queue age, and current critical path.
- Existing recovery artifacts and worktrees before creating replacement work.

The Lead first refreshes stale state, then identifies the highest-value unmet critical-path predicate.
It must prefer game/release progress over control-plane expansion unless the infrastructure blocker measurably prevents that progress.
Each cycle has bounded work-generation and assignment budgets so one bad signal cannot create a task storm.

## Task decomposition

New work is created only when no semantically equivalent active or queued task exists.
Every generated task must include lane, priority, bounded title, explicit file scope when known, acceptance criteria, dependencies, estimated effort, evidence policy, and concurrency key.
Dependency-cycle detection runs before persistence; cyclic proposals are rejected and recorded as Lead decisions.
The fixed infrastructure-to-game-work budget prevents recursive autonomy work from dominating reconstruction work.
Cooldowns prevent repeated task generation from the same unresolved predicate.

## Assignment and routing

Implementation routes through the existing governed swarm/router; the Lead does not launch arbitrary processes.
Research routes to existing research lanes; verification uses existing verifier lanes; ChatGPT/Copilot are used only when they improve throughput without duplicate ownership.
Free SWE-2 Max is preferred for routine Devin planning/engineering, with existing model-routing evidence allowed to choose another free variant for bounded work.
Paid fallback remains disabled unless the existing budget policy explicitly authorizes it.
## Monitoring, recovery, and handoff

The Lead tracks each owned task until terminal state or explicit handoff.
It renews healthy leases, detects stale sessions, preserves dirty worktrees, and records recovery artifacts before reassigning work.
Verification failures are classified before repair work is created; infrastructure failures must not be misreported as product failures.
Failed exact SHAs remain immutable and quarantined; repairs use distinct candidate SHAs.
The Lead never discards evidence merely to free capacity.

ChatGPT↔Devin consultation uses Brain messages for architecture uncertainty, security boundaries, conflicting evidence, repeated failure, and high-cost decisions.
When exact-chat wake is available, the Lead may request it through the existing guarded phone bridge; if unavailable, the Brain message remains authoritative.
Lease acknowledgement is required before assuming a delegated ChatGPT worker is active.

## Safety and authority boundaries

The Lead can create, assign, renew, release, block, and decompose ordinary Brain work within policy.
It cannot integrate code, approve its own candidate, write protected branches, alter credentials, widen privileged execution, or raise spending authority.
Security-sensitive infrastructure changes remain independently verified and fail closed.
The existing signed Nexus privileged boundary remains the only privileged worker-control path.
Emergency pause disables new assignments/task creation but keeps observation, heartbeat, evidence persistence, and safe cleanup active.

## Metrics and governed evolution

Each cycle records critical-path completions, median task latency, queue age, verification pass rate, regression/rework rate, worker utilization, and resource contention.
The Lead publishes these metrics to the existing Factory Metrics/governed-evolution surfaces rather than changing itself directly.
Evolution proposals run in shadow, require objective improvement evidence, independent verification, bounded promotion, and rollback.
Department mix, model routing, concurrency, task decomposition, and context packing may evolve; protected boundaries may not.
## Configuration and persistence

`devin_lead.json` defines cycle cadence, election/heartbeat TTLs, task-generation caps, cooldowns, infrastructure budget, recovery thresholds, and emergency-pause location.
The service persists every planning decision, assignment, recovery, escalation, and pause/resume transition to Brain provenance.
No correctness-critical state exists only in memory; restart reconstructs authority from Brain, integration state, runtime health, and existing worktrees.

## Verification strategy

`test_devin_lead.py` must cover single-leader election, lease expiry/takeover, pause semantics, crash-safe restart reconstruction, semantic dedupe, generation caps, dependency-cycle rejection, infrastructure budget enforcement, routing decisions, stale-worker recovery, paid-model refusal, and provenance persistence.
Tests must prove the Lead cannot directly merge or mutate protected authority surfaces.
A dry-run/status mode must make one planning cycle inspectable without dispatching work.
Fast gate must pass before shared full-E2E preflight; integration remains under the existing merge train.

## Deployment

The source surface is limited to:

- `ops/logres-control-plane/bin/logres-devin-lead`
- `ops/logres-control-plane/config/devin_lead.json`
- `ops/logres-control-plane/lib/logres_devin_lead.py`
- `ops/logres-control-plane/systemd/logres-devin-lead.service`
- `ops/logres-control-plane/tests/test_devin_lead.py`

Runtime deployment must use the canonical control-plane manifest in a separate closure task if those files are not already covered.
The service is not considered operational until source is integrated, runtime is exact-SHA deployed, doctor is green, and a supervised dry-run plus bounded live cycle succeed.

## Acceptance mapping

This design satisfies task criteria 1–12 by making the Lead persistent, Brain-authoritative, game-goal-first, bounded in task generation, routed through existing worker engines, recovery-aware, budget-safe, non-integrating, metric-driven, anti-runaway, evolution-fed, and fully provenance-persistent.
