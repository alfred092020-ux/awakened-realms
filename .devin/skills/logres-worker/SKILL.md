---
name: logres-worker
description: Execute a Brain-leased Logres worker task inside its isolated worktree with branch, scope, evidence, and verification guardrails
argument-hint: "[task-id]"
triggers:
  - user
  - model
---

# Logres Worker Guardrails

You are executing a Logres worker task inside an isolated git worktree that the
Logres Brain already leased to this worker. Follow these rules exactly.

## Branch isolation

- Stay on the leased `worker/*` branch shown by `git branch --show-current`.
- NEVER checkout, switch, merge, rebase, cherry-pick, push, or integrate into
  `main` or `feat/logres-reconstruction`. Those branches are hard-refused.
- Leave edits uncommitted unless the task harness explicitly asks you to
  commit. The harness verifies, commits, and hands off the work.

## Scope

- Modify or create files only inside the task's declared scopes
  (`task_scopes` in the control database / the worker packet).
- Never touch credentials, tokens, dotenv files, SSH keys, or
  Devin/Windsurf/OpenAI configuration or secrets. Never print credential
  contents; redact token-like strings in any output or log you produce.

## Evidence

- The task packet is the contract. Implement only what it requires and cite
  repository files as evidence.
- Never invent original Logres behavior that the packet or repository does
  not support. If evidence is missing, report the blocker instead of
  guessing.
- Do not weaken or delete tests to hide a defect.

## Model policy

- Default model is `swe-2-max`, and only when `devin models list` reports it
  with `cost_tier` `Free`.
- Never silently use a paid model. Paid models require explicit opt-in from
  the operator (`--allow-paid` / `LOGRES_DEVIN_ALLOW_PAID=1`).

## Lease loss stops work

- Losing the Brain lease stops the worker immediately: an authoritative
  "not lease owner" renewal answer, or failed ownership/branch revalidation
  before commit/finish, terminates the Devin process group at once
  (SIGTERM, bounded grace, then SIGKILL).
- Transient renewal errors are retried but never allowed to outlive the
  lease: the run is terminated before the lease TTL expires, measured from
  the last successful renewal — not by counting failures.

## Failed attempts are preserved

- Failed attempts are never discarded. Before any cleanup or READY release
  the harness snapshots all changed state — including untracked files —
  into a recovery commit under `refs/logres/attempts/<task>/<stamp>-<stage>`
  without moving the leased branch HEAD, and records the attempt ref and
  failure stage in the job artifact.
- An attempt ref is recovery data, never a candidate SHA. A retry starts
  from a clean worktree while prior work stays inspectable and recoverable.

## Unattended execution requires OS isolation

- Production unattended workers must run under OS-level isolation: either
  the Devin native sandbox (`--sandbox`, which fails closed when the
  platform cannot enforce it) or an external isolation marker supplied by
  the OS/systemd/container launcher (`--isolation` /
  `LOGRES_DEVIN_ISOLATION` / `devin.isolation`).
- The `smart` permission mode is an attended compatibility default only —
  it is not proof of unattended isolation. Devin CLI allow/deny permission
  config is defense-in-depth, never an OS boundary.

## Verification and handoff

- Run focused, repo-local verification only (the task's declared test scope).
  Do not run global integration or performance gates yourself.
- The finish path is `bin/logres-finish-task <worker> <task> <branch>` from
  the deployed control root. Never merge, cherry-pick, or push directly.
- On any failure or interruption the task returns to `READY` — it is never
  marked complete. The Brain lease is renewed while the worker runs, so an
  interrupted run stays recoverable.
