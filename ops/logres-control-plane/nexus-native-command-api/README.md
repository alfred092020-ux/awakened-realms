# Nexus Native Command API

Authoritative realtime read surface + governed control bridge for the Nexus
Command Center **native Android app** (`../nexus-command-center/android`).

- `GET /api/snapshot` — full authoritative snapshot (tasks, workers, leases,
  claims, dependencies, recovery, verification, milestones, approvals inbox,
  graph, evidence, system metrics, capabilities, per-source staleness).
- `GET /api/events` — Server-Sent Events stream of snapshot revisions.
- `GET /api/approvals`, `POST /api/approvals/register` — approval inbox.
- `GET /api/audit`, `GET /api/evidence` — activity/audit + certification evidence.
- `POST /api/control` — governed control requests (pause/resume autonomy,
  preflight, verify-ref, emergency stop, lease revoke) and approval decisions.
  All requests are audit-logged and posted to Brain for Lead governance — the
  API never executes them itself.

Truth contract: `UNKNOWN_OR_STALE_NEVER_ZERO`. Missing backend capabilities are
reported in `capabilities` as `false`; the app must render them *unavailable*.

Run: `python3 server.py --host 127.0.0.1 --port 8787`
Auth: `Authorization: Bearer $NEXUS_NATIVE_API_TOKEN` (loopback bypasses only
when no token configured). Set `NEXUS_NATIVE_API_TOKEN` before any non-loopback
bind — the server refuses otherwise.

Tests: `python3 test_server.py`
