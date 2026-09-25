---
description: "Logres Devin worker guardrails: branch isolation, scope, evidence, verification"
trigger: always_on
---

# Logres Devin Guardrails

- Work only inside the isolated worker worktree on the Brain-leased
  `worker/*` branch. NEVER touch `main` or `feat/logres-reconstruction`;
  never merge, rebase, cherry-pick, push, or integrate directly.
- Modify files only inside the task's declared scopes. The task packet is
  the contract — never invent Logres behavior without repository evidence.
- Never read, print, or modify credentials, tokens, dotenv files, SSH keys,
  or Devin/Windsurf/OpenAI configuration. Redact token-like strings in
  output and logs. Do not pass secrets on command lines.
- Default model is `swe-2-max`, only when `devin models list` reports it as
  `Free`. Paid models require explicit operator opt-in.
- Losing the Brain lease stops the worker immediately — the Devin process
  group is terminated (SIGTERM, bounded grace, SIGKILL), and transient
  renewal failures terminate before the lease TTL can expire.
- Failed attempts are preserved, never discarded: all changed state
  (including untracked files) is snapshotted into recovery commits under
  `refs/logres/attempts/<task>/` before any cleanup or READY release, and
  the attempt ref plus failure stage is recorded in the job artifact.
- Production unattended workers require OS-level isolation: the Devin
  native `--sandbox` or an external launcher isolation marker. The `smart`
  permission mode is attended-only; Devin allow/deny config is
  defense-in-depth, not an OS boundary.
- Run focused repo-local verification before handoff; hand off through
  `bin/logres-finish-task`. Failures return the task to READY and are never
  marked complete.
