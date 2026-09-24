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
