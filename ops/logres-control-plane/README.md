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
