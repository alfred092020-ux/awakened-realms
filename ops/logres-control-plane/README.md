# Logres Control-Plane Source

This directory versions the VM control-plane helpers that are safe to deploy from Git.

Runtime state is **not** stored here. The live database, logs, private reverse-engineering evidence, and credentials remain under `/home/ubuntu/logres/control`, `/home/ubuntu/logres/private`, and user configuration paths.

## Safety

- Never deploy secrets from this tree.
- Never add `openai_api_key`, GitHub tokens, SQLite runtime databases, logs, or private evidence to the manifest.
- The deployment manifest is explicit and fail-closed.
- Each deployed file is written to a sibling temporary file, fsynced, chmodded, then atomically replaced.
- `--dry-run` validates every manifest source but does not create the target root.

## Deploy

```bash
python3 scripts/logres/deploy_control_plane.py \
  --source ops/logres-control-plane \
  --target /home/ubuntu/logres \
  --dry-run
```

Remove `--dry-run` only after reviewing the manifest and passing the relevant tests.

The committed defaults remain fail-closed: automatic OpenAI and Copilot dispatch are disabled in Git. Live routing is enabled only in runtime-only `/home/ubuntu/logres/control/autoflow.json` after current model pricing is configured, doctor is clean, and the staged AI/Copilot safety gates pass. Copilot must target `feat/logres-reconstruction`, remain on isolated `copilot/*` branches, use draft PRs, pass scope and verification gates, and never auto-merge.

## Lead chat continuity

A fresh Lead chat does not depend on the previous conversation window. The control plane can reconstruct takeover state from Git, Brain, SQLite task state, merge/preflight state, and current Lead snapshots.

Use `logres-lead takeover` for a non-mutating readiness check. When the fresh Lead is ready to assume ownership, use `logres-lead takeover --apply`. The apply path fails closed if integration is dirty, out of sync with origin, or currently locked by another integration operation. It increments the Lead generation, preserves/requeues any legacy Lead development branches, refreshes canonical control surfaces, and writes `control/LEAD_TAKEOVER.txt` with exact next-state context.

Lead remains integration/review reserve. Takeover never modifies `main`, never auto-merges candidate work, and never discards dirty worker branches.

## Autonomy v2

`logres-autonomy` is the policy-gated supervisor for continuous integration flow. Committed defaults keep it disabled. Runtime-only configuration must explicitly enable `autonomy.enabled`, `auto_preflight_enabled`, and `auto_apply_preflight_enabled`.

A cycle reconciles deterministic control state, requires a clean doctor, zero actionable route failures, zero open regressions, healthy VM resources, and an untripped circuit breaker. It then chooses a resource-aware merge-preflight batch. Automatic apply is allowed only for a still-current preflight that passes `logres-merge-preflight validate`, is pinned to the exact result SHA, and has an exact-SHA full-E2E PASS.

The merge train accepts actor `autonomy` only when all of the following are true: runtime autonomy policy is enabled, `LOGRES_AUTONOMY_APPLY=1`, and `LOGRES_AUTONOMY_PREFLIGHT_ID` exactly matches the requested preflight. Legacy merge paths remain Lead-only.

The supervisor never modifies `main`. Candidate branches remain immutable, scope-checked and origin-verified. Integration remains `feat/logres-reconstruction`. Two consecutive automatic apply failures trip the default circuit breaker; later automatic applies stop until the circuit is explicitly reset.

Useful commands:

```bash
logres-autonomy status
logres-autonomy cycle --dry-run
logres-autonomy cycle
logres-autonomy reset-circuit
```

Copilot READY-task selection is critical-path aware rather than alphabetical: priority still dominates, then tasks are favored when they shorten the longest remaining dependency chain or unlock more downstream work. Runtime Copilot capacity remains bounded by the existing eligibility, scope, dependency, concurrency, and backpressure checks.

### Autonomy v3 hot-loop scheduling

Autonomy v3 separates the hot paths so they do not block each other. The five-minute `logres-autopilot-watch` owns Brain, AI/Copilot, lease, blocker and VM-health orchestration. A dedicated one-minute `logres-autonomy cycle` cron owns merge/preflight progression.

Idle autonomy ticks use a cheap fast path: coordinator/merge state is refreshed and, when there is no integration backlog or verified current-base preflight, the cycle exits without running the heavy doctor/resource probes.

Use `logres-autonomy-cron install` to install the managed one-minute autonomy line and remove the obsolete standalone `logres-merge-preflight run` cron. The installer is idempotent and saves the previous crontab under `control/cron-backups/`.

Copilot dispatch now scans beyond ineligible READY tasks. Research/manual/leased/conflicting tasks are skipped with reasons while the router keeps scanning for the next safe critical-path implementation candidate, up to the configured dispatch limit.

## Auto-saturating hybrid worker swarm

`logres-swarm` continuously fills safe free worker capacity instead of waiting for a human to open another chat. Committed defaults keep the swarm disabled; runtime configuration must explicitly set `swarm.enabled=true`.

The swarm counts active Brain leases and active Copilot jobs against the same global worker ceiling. READY implementation/regression work is offered to the existing bounded Copilot router. READY research/evidence work is assigned atomically to virtual `auto-research-N` workers and executed by `logres-research-agent`.

Research agents are evidence-only. They do not edit the repository. Each job builds a deterministic local evidence bundle from the task packet and indexed Logres helpers, then uses the configured OpenAI Responses model with built-in web search when enabled. Results use a strict provenance schema, explicitly grade every acceptance criterion, write a hashed artifact under `artifacts/swarm-research/`, post Brain evidence, and either complete the task or leave it `BLOCKED_EVIDENCE`. Transient worker failures return the task to READY. Per-task retry ceilings prevent infinite loops.

The research agent shares the existing `api_usage` budget ledger, so autonomous research obeys the same OpenAI budget state and model-rate accounting as the evidence router. Current-JP evidence remains reference-only unless independently tied to recovered Global evidence.

A managed one-minute `LOGRES_SWARM_V1` cron refills capacity alongside the one-minute integration autonomy loop. Stale research processes are detected, their leases are recovered, and safe READY work can immediately refill the slot.

Useful commands:

```bash
logres-swarm status
logres-swarm tick --dry-run
logres-swarm tick
```

## Beyond Plus Ultra: provenance graph + self-optimizing scheduler

The control plane now has a materialized knowledge graph and optimizer layer. `logres-knowledge refresh` projects tasks, dependencies, Brain discoveries, hashed evidence artifacts, cited public sources, and immutable integration commits into SQLite `knowledge_nodes` / `knowledge_edges`.

Evidence confidence and provenance are separate dimensions. A confirmed current-JP observation is still clamped to supported-inference strength when the target task requires historical Global authority. Multiple weaker claims cannot silently aggregate into confirmed-original truth.

`logres-optimizer plan` ranks READY work inside the existing priority policy using critical-path length, downstream unlock count, evidence gap, expected duration, and observed engine success. Research scheduling therefore attacks the highest-value unresolved evidence gaps instead of simply taking alphabetical/shortest tasks. Copilot uses the same optimizer for implementation/regression/code candidates.

Terminal swarm outcomes feed `optimizer_observations` with duration and API cost. The scheduler can therefore learn from actual worker results while retaining deterministic priority, dependency, concurrency, scope, budget, and provenance gates.

Lead shortcuts:

```bash
logres-lead knowledge stats
logres-lead knowledge query "Millennium Tree"
logres-lead knowledge task G17-TUT-001
logres-lead optimizer plan --limit 12
logres-lead swarm status
```

## Hybrid local + UpCloud verification

The remote pool can offload the unit-test lane while the canonical VM keeps the private-hydrated browser E2E lane authoritative. The remote worker receives only an immutable 40-character source SHA and an allow-listed verification/build npm script. It has no deploy, merge, publish, push, release, tag, or version authority.

Committed defaults keep hybrid verification disabled. Runtime `remote_pool.hybrid_verify_enabled=true` enables the optimization after both UpCloud workers pass health/canary checks.

When enabled, `logres-verify-farm` starts the exact-SHA unit suite on the heavy UpCloud worker while the local VM performs build + private-hydrated Playwright E2E. If the remote lane is unreachable, times out, or fails, the farm automatically runs the original local hydrated unit-test lane. A remote outage therefore cannot weaken the authoritative gate or strand integration.

`logres-lead pool status` shows remote worker health and capacity. `logres-remote-pool run` remains restricted to safe verification/build scripts and can fail over only when the caller explicitly marks verification work reassignable.

## Research frontier governor

`logres-frontier` prevents autonomous evidence work from turning one unresolved historical predicate into an unbounded tree of `AUTO-RE-` and `UNBLOCK-` tasks.

Every generated research escalation now receives explicit lineage: root task, parent task, normalized predicate hash, origin, and generated depth. Equivalent blocker or AI events share one semantic frontier even when event IDs, route IDs, or artifact hashes differ. A generated research child is the single bounded escalation for that predicate; generated descendants are forbidden.

A frontier whose child finishes `BLOCKED_EVIDENCE` becomes `SATURATED`. Further identical evidence events remain advisory instead of manufacturing more work. A completed child resolves the frontier. Evidence artifacts are never deleted.

`logres-frontier reconcile` backfills lineage for historical generated tasks and reports recursive descendants. `logres-frontier reconcile --apply` safely supersedes only non-active recursive generated descendants, preserves their evidence, and converts exhausted auto-routed hard dependencies into evidence ceilings so root tasks no longer remain permanently `BLOCKED_DEP`.

The five-minute autopilot runs the bounded reconciliation automatically before AI/Copilot routing.

Useful commands:

```bash
logres-frontier status
logres-frontier reconcile
logres-frontier reconcile --apply
logres-lead frontier status
```

## User-space autonomy supervisor

`logres-supervisor` is the authoritative recurring-work scheduler for the control plane. It removes correctness dependence on mutating the host crontab, which can fail inside hardened `no_new_privs` execution contexts even when the existing cron bootstrap continues to run.

The supervisor is single-flight via `/tmp/logres-supervisor.lock`, publishes `control/supervisor-heartbeat.json`, and owns bounded cadences for autonomy, swarm refill, autopilot/frontier routing, Lead snapshots, health snapshots, control backups, evidence refresh, preview cleanup, and maintenance. Existing cron entries remain a harmless bootstrap/fallback and share the same autonomy/swarm/preview locks, so duplicate work is suppressed.

`logres-swarm tick` ensures the supervisor is alive. This means the already-installed swarm cron can resurrect the supervisor after a VM restart without requiring a privileged scheduler write. Runtime deployment now requires a healthy supervisor but treats crontab reconciliation as best-effort legacy compatibility.

Useful commands:

```bash
logres-supervisor status --json
logres-supervisor ensure
logres-supervisor tick
```

## Adaptive resource broker

`logres-resource-broker` is the placement layer between the task optimizer and the available execution engines. It keeps authority and provenance policy separate from compute choice.

For exact-SHA verification, the broker scores the Heavy and Light UpCloud workers using live reachability, free slots, CPU, available memory, observed success rate, and script-specific median runtime. New remote results persist the npm script that produced them, so placement improves from real workload history instead of static machine labels. Legacy results remain a weak role-level prior.

`logres-verify-farm` now asks the remote pool for `auto` placement. The selected machine may change as capacity and measured performance change. Local private-hydrated build/E2E remains authoritative, and any remote failure still falls back to the local unit-test lane. Remote workers retain no merge/deploy/push authority.

The broker also exposes bounded plans for research and implementation. Safe research prefers the budget-gated OpenAI lane, scoped implementation prefers Copilot, and any task whose evidence policy is private/local-only is forced to the local lane.

Useful commands:

```bash
logres-resource-broker remote-role test --json
logres-resource-broker plan --workload verification --script test
logres-resource-broker task GJP-FUNC-MATCH-001
```
\n## Health and index self-healing\n\nThe user supervisor keeps both `logres-sync-health` and `logres-code-index` fresh every five minutes. This closes a gap where the environment could remain healthy but report a stale synchronization failure or code-index SHA after canonical advanced.\n\n`logres-sync-health` treats SQLite `database is locked` from concurrent Brain writers as transient infrastructure contention. Brain health/ownership probes retry with bounded exponential backoff before declaring synchronization failed. Persistent failures still fail closed.\n\n`logres-code-index` now has a single-flight lock, an explicit non-mutating `status` mode, environment-overridable repo/index paths for verification, and keeps its existing atomic SQLite replacement. Concurrent index refreshes return a successful `code_index_busy` no-op instead of duplicating expensive ctags work.\n\nSupervisor order refreshes the code index and environment synchronization before the periodic doctor snapshot, so canonical changes converge automatically without depending on manual maintenance.\n
## Automatic regression isolation

A failed shared preflight no longer has to stall every good candidate behind it. If an exact-SHA full-E2E preflight fails with multiple candidates, the next autonomy cycle automatically reduces the batch to one candidate. This turns the merge train into a deterministic isolation pass without guessing which commit was responsible.

If that single immutable candidate fails full E2E by itself, its exact integration-queue row becomes `QUARANTINED`. The branch, SHA, failed preflight packet, logs, and generated regression remain preserved. The queue does not mutate or silently retry the failed SHA, and unrelated READY candidates can continue through verification.

Failures on an old integration base do not reduce later batch sizes, and a single-candidate failure does not poison future unrelated batches. This keeps isolation local to the evidence that actually failed.

## Evidence impact and invalidation reviews

`logres-impact` turns explicit Brain `EVIDENCE_CONFLICT` events into bounded downstream impact reviews. It never rewrites historical truth, confidence, code, merge state, or `main`.

The impact planner walks the task dependency graph in reverse from the conflicted source task, collects all transitive dependent tasks, and attaches any integrated exact-SHA commits produced by those tasks. Each explicit conflict is fingerprinted and stored once in `impact_incidents`.

When `logres-impact scan --apply` finds a new conflict, it creates one evidence-first `IMPACT-REVIEW-...` task with the source task, downstream tasks, and integrated commits captured in its acceptance criteria. Repeated scans are idempotent.

Autopilot runs the impact scan after frontier reconciliation and before AI/Copilot routing. This gives new contradictory evidence a deterministic path into repair work without allowing weak or later-version evidence to silently invalidate Global reconstruction claims.

Useful commands:

```bash
logres-impact task G17-TUT-001
logres-impact scan
logres-impact scan --apply
logres-impact status
```

## Mission graph foundation

`logres-mission` stores the full-game objective hierarchy outside any ChatGPT
conversation. The default graph begins at `LOGRES_COMPLETE` and expands into
client, gameplay, content, fidelity, quality, Android and release objectives.

The mission graph is deliberately fail-closed. A leaf objective with no mapped
task or milestone is `UNCOVERED`, never implicitly complete. Existing tasks and
milestones provide completion evidence, while missing coverage remains visible
for later bounded planning and task synthesis.

Initialize or refresh the canonical graph with:

```bash
logres-mission init
logres-mission status
logres-mission tree
logres-mission gaps
logres-mission objective BATTLE
```

Configuration refreshes are idempotent and preserve the runtime database as the
operational source of truth. The current goal watchdog remains the descriptive
milestone-progress layer. Mission planning sits above it and does not replace
task optimizer or merge authority.

## Regression repair lifecycle

A regression repair is not considered resolved merely because the worker finishes its branch. `logres-finish-task` now leaves the regression row `OPEN` after the repair candidate passes its fast gate and is handed off.

The coordinator is allowed to queue that immutable repair SHA normally. Only after the repair candidate reaches `INTEGRATED` does regression reconciliation move the regression to `RESOLVED`; at that point the original conflicting candidate can be superseded safely.

This prevents a circular failure mode where finishing the repair made the regression terminal too early, which caused the coordinator to suppress the repair candidate before shared full-E2E preflight could ever run.
