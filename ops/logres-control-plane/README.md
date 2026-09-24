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

Automatic OpenAI and Copilot routing remains disabled until the staged rollout task explicitly enables it.
