# Nexus Command Center — Branch & Worktree Reconciliation

External CONSTRUCTION mission record (not governed Nexus product execution).
Baseline: `feat/logres-reconstruction` @ `ed4a96e89c0b24ac69fa3502e7fb87111d656b89`.

## Unique valid work preserved

| Source | State | Disposition |
|---|---|---|
| `worker/chatgpt-nexus-control-center-android-complete-003` (c149487) & `worker/chatgpt-ncc-approval-inbox-006` (8884e83) | Identical `nexus-control-center-android/` standalone project (native skeleton: SSE client, Google sign-in deps, SystemGraphView) | Design + dependency set + package identity carried into `nexus-command-center/android/` native rewrite |
| `worker_chatgpt-control-center-cert-001-...` worktree (uncommitted) | Strongest UI baseline: native multi-tab MainActivity replacing the WebView shell (Overview/Tasks/System/Admin, SSE reconnect, governed controls, honest Google-sign-in note) | Adopted and substantially extended into the finished five-tab app |
| `worker/chatgpt-ncc-native-api-realtime-008` (766c282) | `nexus-native-command-api/` realtime backend (supersedes `-007` f6c8cca) | Adopted at `ops/logres-control-plane/nexus-native-command-api/` and extended (Lead-snapshot telemetry, richer approvals, audit, evidence, graph, capabilities, emergency governed actions, Google session exchange) |
| `worker/chatgpt-nexus-executive-world-model-foundation` (d491a69) | Brain-side `lib/logres_executive*`, `logres_world_model.py` — different workstream, not NCC app scope | Preserved on its own branch; not merged here |

## Demonstrably obsolete / stale (left intact on origin branches, not carried)

- `nexus-command-center/android` **WebView shell** — replaced in place; the
  mission forbids WebView/browser wrappers. History retains it.
- `android/` game-client edits on 199deea / c149487 / 8884e83 — gutted the
  Capacitor game `MainActivity` into a telemetry viewer; wrong approach,
  excluded (game client untouched).
- `nexus-control-center/` web variants (40cee25, 1f4e865, 2243551, 80fe23b,
  cc89722, 66bbedf, 30900a2, 8e6ab41, dbb592a, 1274868, and ~40 retry-alias
  branches) — all are ancestors of feat or contain older copies of the same
  app; feat's versions are strictly newer (e.g. env-config timeouts, `[hidden]`
  auth fix + test).
- `worker_chatgpt-nexus-control-center-preflight-003` pid/token files and
  `worker_chatgpt-nexus-control-center-accuracy-preview-001` conflicted adds —
  runtime leftovers / superseded content; left in place, not read.
- `tmp/nexus-final-candidate` (d8a46fb) — old test commit, unrelated content.
- Remote-only NCC-named branches (verified-progress, throughput-arch,
  phone-agent, remote-pool, capability-broker, merge-preflight persistence) —
  unrelated Brain workstreams; remain on their branches.

## Authority boundaries

The app and its backend are owner control surfaces, never root authority:
control actions are audit-logged `CONTROL_REQUEST` posts to Lead via Brain,
approval decisions carry the exact SHA, and emergency stop/revoke require
typed confirmation and still pass through governance.
