# Logres AI + Copilot Autoflow Control-Plane Design

Date: 2026-09-23
Project: Logres reconstruction
Repository: alfred092020-ux/awakened-realms
Integration branch: feat/logres-reconstruction
Status: Design approved in conversation; implementation not yet authorized

## 1. Purpose

Extend the existing Logres control plane so recovered evidence, OpenAI analysis, Copilot implementation, verification, and Lead integration form one restart-safe production line.

The intended outcome is lower critical-path latency, not maximum agent activity. New evidence should be routed quickly to the right specialist, implementation-ready work should be dispatched without manual coordination, and verified work should enter the existing integration queue without bypassing current safety gates.

## 2. Non-negotiable constraints

- Never modify, merge, or target `main`.
- `feat/logres-reconstruction` remains the only integration branch.
- Lead remains the only integration authority.
- `control.sqlite` plus Brain Network remain the coordination source of truth.
- Do not create a second task database or competing orchestrator.
- Global 3.0.24 / recovered target-client evidence outranks later/current JP evidence where they conflict.
- AI analysis is advisory. It cannot promote a historical claim to canonical truth by itself.
- Copilot is an implementation/review worker, not a historical-evidence authority.
- Existing exact-SHA verification, scope checks, merge preflight, regression capture, and merge train remain mandatory.
## 3. Existing system to reuse

The live control plane already provides the majority of the orchestration substrate:

- `logres-autopilot-watch`: stale-lane, lease, resource, verification, integration-queue, and safe-capacity monitoring.
- `logres-autoflow-plan`: dependency and readiness view from `control.sqlite`.
- `logres-dispatch`: task-scoped command execution.
- `logres-worker-start` / coordinator: atomic acquisition and mutually-safe worker waves.
- `logres-blocker-router`: Brain BLOCKER/EVIDENCE_CONFLICT -> focused research task.
- `logres-regression-capture` / supersession: verification or integration failures -> focused repair work.
- `logres-merge-queue`, `logres-merge-preflight`, `logres-merge-train`: exact-SHA verified integration flow.
- `logres-sync-oracle-evidence`: Oracle evidence synchronization.
- `logres-ai`: bounded, cached OpenAI evidence analyzer.
- Brain Network: durable events, leases, discoveries, decisions, and handoffs.

The new work must extend these components rather than replacing them.

## 4. Target architecture

Brain events and task state feed a routing layer. The router classifies work into evidence analysis, research, implementation, verification, or existing failure handling.

```text
Brain / control.sqlite
        |
   route classifier
   /      |       \
OpenAI  Copilot  existing routers
   |      |       |
Brain   verify   blocker/regression
   \      |      /
      merge train
          |
         Lead
```
## 5. Component boundaries

### 5.1 Evidence router

A new `logres-ai-router` processes new eligible evidence/artifact events. It does not interpret historical truth. It decides only whether a bounded OpenAI analysis is useful and records the routing decision before dispatch.

Eligible examples:
- large native/Ghidra outputs;
- Oracle result bundles;
- cross-version comparisons;
- protocol catalogs;
- recovered state-machine traces;
- conflicting evidence bundles.

Ineligible examples:
- one-line symbol lookups;
- trivially readable build errors;
- already analyzed artifact/question pairs;
- small deterministic outputs where grep/indexed lookup is sufficient.

### 5.2 OpenAI evidence worker

Reuse `logres-ai`. Required behavior:
- input sampling/cap remains bounded;
- strict evidence labels remain enforced;
- structured JSON output remains enforced;
- reasoning remains disabled for extraction-style work;
- artifact SHA + question SHA dedupe prevents duplicate spending;
- invalid/incomplete output never enters Brain as accepted evidence;
- cached results may be reposted without another API request;
- `store=False` remains the API default for private RE artifacts.

OpenAI results are advisory evidence summaries. Canonical project evidence status still requires deterministic provenance and project rules.
### 5.3 AI-result router

A second routing stage consumes validated `logres-ai` results.

- CONFIRMED ORIGINAL with adequate source anchors -> update/create an evidence packet and make dependent implementation work eligible when dependencies are satisfied.
- SUPPORTED INFERENCE with adequate source anchors -> implementation becomes eligible only when the task evidence_policy explicitly permits inference-backed reconstruction; otherwise route to review/research.
- UNRESOLVED -> create or update a focused research packet.
- VERSION SENSITIVE -> create a target-version cross-check task.
- contradiction -> emit EVIDENCE_CONFLICT and reuse `logres-blocker-router`.
- AI label incompatible with provenance -> mark REVIEW_REQUIRED rather than accepting the label.

No result may automatically change canonical historical status solely because the model selected a stronger confidence label.

### 5.4 Copilot router

A new `logres-copilot-router` dispatches only bounded implementation/review/test/tooling tasks.

Eligibility requires:
- task status READY;
- allowed work type;
- satisfied hard dependencies;
- evidence policy satisfied;
- acceptance criteria present;
- explicit or derivable file scope;
- no active conflicting claims/leases;
- no unresolved historical decision required;
- task is not integration work.

Dispatch rules:
- base branch must be `feat/logres-reconstruction`;
- work must use isolated `copilot/*` branches;
- PR target must be `feat/logres-reconstruction`;
- `main` is forbidden;
- Copilot cannot self-merge;
- current task ID, evidence packet, allowed files, forbidden files, acceptance criteria, and required tests are embedded in the assignment.
### 5.5 Copilot return path

Copilot has no privileged integration path.

A completed Copilot PR is reconciled to:
1. branch + exact candidate SHA;
2. scope check;
3. forbidden-file check;
4. fast verification;
5. full-e2e where policy requires it;
6. normal integration queue;
7. normal merge preflight;
8. Lead-controlled integration.

If the branch moved after queueing, existing immutable-candidate behavior applies. If integration advanced while Copilot worked, the candidate is revalidated against current integration.

## 6. Durable state additions

Add only the state required to make routing restart-safe and auditable.

### `route_jobs`
Tracks source event/task, route kind, dedupe key, state, attempt count, timestamps, and last error.

### `route_decisions`
Append-only rationale: source event, chosen route, provenance/evidence summary, and policy reason. This is audit data, not a replacement for Brain events.

### `copilot_jobs`
Tracks task ID, GitHub issue/session/PR identifiers, base SHA, branch, candidate SHA, state, timestamps, and failure reason.

### `api_usage`
Tracks task, artifact SHA, model, input/output/cached/reasoning tokens when available, estimated cost, status, and timestamp.

Existing task, dependency, lease, verification, integration-queue, and Brain tables remain authoritative for their current responsibilities.
## 7. State machines and dedupe

### Evidence artifact
`NEW -> ROUTED -> AI_RUNNING -> AI_VALIDATED -> BRAIN_POSTED -> COMPLETE`

Terminal alternatives:
`SKIPPED_DETERMINISTIC`, `DUPLICATE_CACHE`, `FAILED_BOUNDED`.

### Copilot
`ELIGIBLE -> ASSIGNING -> ACTIVE -> PR_READY -> VERIFYING -> QUEUED`

Terminal alternatives:
`SUPERSEDED`, `BLOCKED_EVIDENCE`, `SCOPE_VIOLATION`, `FAILED_BOUNDED`.

Deterministic dedupe keys:
- OpenAI: artifact SHA + question SHA.
- Copilot: task ID + task revision/updated_at + base integration SHA.
- failure route: candidate SHA + failure kind.
- evidence reroute: source event ID + resolution type.

A route must be durably recorded before external dispatch so restart reconciliation never loses ownership.

## 8. Failure and retry policy

- transient OpenAI/network failure: at most one bounded retry;
- incomplete/invalid AI response: one safe retry, then FAILED_BOUNDED;
- rate limit: defer with backoff, do not spin;
- API unavailable or budget exhausted: deterministic workflow continues;
- Copilot compile/test failure: create/update a focused repair task;
- Copilot evidence ambiguity: BLOCKED_EVIDENCE -> research routing;
- scope violation: reject candidate and emit conflict;
- merge conflict: reuse current integration-conflict/regression flow;
- historical contradiction: EVIDENCE_CONFLICT -> blocker router.

No infinite retries and no silent weakening of acceptance criteria.
## 9. Capacity and backpressure

Initial limits:
- OpenAI analyses: maximum 1 active by default, configurable to 2.
- Copilot: maximum 2 active jobs, maximum 1 queued.
- Oracle/native: existing scheduler limits.
- Lead integration: always serialized.

Pause new Copilot dispatch when:
- more than four candidates are READY_FOR_INTEGRATION;
- verification backlog exceeds three;
- integration conflict backlog exists above configured threshold;
- VM resource guard reports pressure.

The coordinator's mutually-safe wave remains the authority for file/concurrency safety. The router never invents a parallel wave independently.

## 10. Cost controls

OpenAI automatic use follows this order:
1. deterministic index/search first;
2. SHA/question cache lookup;
3. bounded low-cost model;
4. bounded input/output;
5. no polling calls;
6. escalate only when a critical ambiguity survives.

Budget policy is configuration, not hard-coded business logic. Default thresholds:
- 50% estimated project budget: informational notice;
- 75%: reduce automatic non-P0 analysis;
- final 15-20%: reserve for critical blockers;
- near exhaustion: stop automatic API dispatch, preserve manual/critical override.

No API secret is stored in SQLite, Brain, logs, prompts, or repository files.
## 11. Health, recovery, and telemetry

Extend `logres-doctor`, `logres-autopilot-watch`, and `logres-lead brief` with compact status:

OpenAI:
- credential present without secret disclosure;
- API reachability;
- latest successful run/error;
- active/pending routes;
- cache hit count/rate;
- estimated spend.

Copilot:
- GitHub authentication;
- active/queued jobs;
- stale job age;
- open Copilot PR count;
- base/target branch policy violations.

Router:
- last processed Brain event/cursor;
- route queue depth;
- oldest waiting route;
- failed bounded routes;
- reconciliation lag.

On restart, unfinished records are reconciled against Brain, SQLite, GitHub, cached AI results, and current integration. Completed external work is adopted; stale work is marked and routed rather than duplicated.

## 12. Loop prevention and lineage

Every child route records its parent route/source event. Before creating a research or repair task, the system checks whether the same unresolved claim already has an active child.

Repeated unresolved analysis updates the existing lineage instead of spawning an unbounded chain of tasks.

## 13. Rollout

Phase 1: schema + route-decision ledger + dry-run classifier. No automatic external dispatch.

Phase 2: enable automatic artifact -> OpenAI routing for a narrow allowlist of RE artifact types. Validate cost, dedupe, recovery, and Brain posting.

Phase 3: enable Copilot dispatch in report/review mode, then bounded implementation tasks after successful reconciliation tests.

Phase 4: connect Copilot candidates to the existing verification/integration queue automatically.

Phase 5: add backpressure, budget thresholds, health summaries, and restart reconciliation as mandatory gates before declaring autoflow production-ready.
## 14. Testing strategy

Unit tests:
- route classification and priority;
- provenance/confidence guard;
- deterministic dedupe keys;
- budget policy;
- Copilot eligibility;
- retry ceilings;
- lineage loop prevention;
- state transition validity.

Integration tests:
- synthetic Brain artifact -> cached AI result -> evidence event;
- unresolved AI result -> one focused research task;
- duplicate event -> no duplicate API call/task;
- eligible Copilot task -> assignment record with correct base branch;
- forbidden/main target -> hard rejection;
- Copilot candidate -> normal verification queue;
- restart during AI/Copilot route -> reconciliation without duplicate work;
- backpressure -> dispatch pause and automatic resume.

Regression requirements:
- existing Brain health must remain PASS;
- existing worker-start atomic acquisition tests remain PASS;
- existing blocker/regression routing remains unchanged;
- merge-preflight and exact-SHA protections remain unchanged;
- no new code path may integrate directly.

## 15. Acceptance criteria

The architecture is complete when:
- new eligible artifacts can be routed automatically to OpenAI with zero duplicate charge for identical artifact/question pairs;
- AI results deterministically become evidence packets or focused research work without promoting unsupported historical claims;
- implementation-ready tasks can be assigned to Copilot without manual GitHub mechanics;
- Copilot results enter the existing verification and integration queue exactly like other workers;
- crashes/restarts reconcile unfinished routes without duplicate dispatch;
- Lead brief exposes router/OpenAI/Copilot health in one compact view;
- budget/backpressure policies demonstrably pause dispatch without blocking deterministic work;
- `main` remains unreachable by all automated routing paths.

## 16. Explicit non-goals

- autonomous merging into integration or main;
- replacing Brain or `control.sqlite`;
- replacing Oracle/Ghidra/native reverse engineering with model inference;
- automatically declaring historical truth from AI output;
- maximizing worker count for its own sake;
- GitHub Issues/PRs becoming the project source of truth;
- background API polling that spends credits without new work.

## 17. Success metric

Primary metric: critical-path latency from new evidence to verified integration-ready candidate.

Secondary metrics: evidence-to-route time, DONE-to-verified time, verified-to-integration-ready time, duplicate work prevented, API cache hit rate, Copilot pass rate, verification failure rate, merge-conflict rate, and useful active-lane occupancy.

The production philosophy is:

Oracle/native discovers. OpenAI digests. Brain records. Router directs. ChatGPT/Lead resolves judgment. Copilot and workers build. Verification judges. Lead integrates. The user tests the resulting APK.
