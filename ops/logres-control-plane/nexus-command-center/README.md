# Nexus Command Center

Production mobile-first control surface for Nexus Core Inc autonomous operations.

## Architecture

The browser authenticates once with the Nexus access token. The backend converts it into an HttpOnly session cookie; the token is never stored in browser storage. Live state is pushed over a real WebSocket connection from a bounded background publisher. Fast worker/event changes are sampled every second and pushed only when state changes. Heavy Git, Brain health and dashboard reconciliation runs independently from the one-second live stream so a slow dashboard query cannot freeze worker/event updates.

The UI exposes Brain, Git, workers, pipeline, runtime pressure, event history and governed operator controls. Operator mode requires re-authentication. Direct controls are allow-listed and audited. Actions without a safe direct primitive remain governed Brain requests rather than bypassing project policy.

## Run

Create `/home/ubuntu/.config/nexus-control-center.env`:

```
NEXUS_CONTROL_CENTER_TOKEN=<long-random-secret>
NEXUS_CONTROL_CENTER_FAST_POLL=1
NEXUS_CONTROL_CENTER_FULL_POLL=10
```

Then install/start the included user service and expose only through authenticated HTTPS/private access.


## Android APK

The `android/` directory contains the **fully native** Nexus Command Center
Android app — no WebView, no browser wrapper. It talks to the sibling
`../nexus-native-command-api` backend over Bearer-authenticated HTTPS and a
Server-Sent Events realtime stream.

Surfaces: an animated *Live Nexus* system map (parallel authority/worker/task/
verification/approval lanes driven only by authoritative snapshot events, with
a reduced-motion static fallback), the task board with plain-language
summaries + live elapsed timers + dependency edges, the Approval Required
inbox (action/reason/scope/risk/evidence/rollback + Approve/Decline), the
activity + audit + certification-evidence timeline, and governed admin
controls including typed-confirmation emergency stop and lease revoke. All
control paths are requests to Lead governance — the app is an owner surface,
never root authority. Explicit states: AUTONOMOUS, APPROVAL_REQUIRED, BLOCKED,
VERIFYING, FAILED, DONE. Missing backend capabilities render *unavailable*,
never fabricated.

Sign-in: Google identity via Android Credential Manager, exchanged for a
backend session at `POST /api/session/google` (server verifies the ID token
with Google when `NEXUS_NATIVE_API_GOOGLE_CLIENT_ID` is configured). Control
requests additionally require the Nexus access token unless the operator sets
`NEXUS_NATIVE_API_ALLOW_GOOGLE_AUTH=1`. Cleartext is allowed only to
loopback/emulator hosts; all other traffic requires HTTPS.

Build a debug APK:

```bash
ops/logres-control-plane/nexus-command-center/android/build_apk.sh
```

The first launch asks for the private backend address and the access token.

## Controls

Direct: force refresh, Wake Lead event, supervisor tick, bounded autonomy cycle, exact ref verification, guarded preflight (explicit typed confirmation + busy check).

Governed requests: pause/resume autonomy, retry task, stale-lease release, Samsung/device QA. These intentionally flow through Lead/Nexus policy until a canonical direct primitive exists.

## Safety and evidence

The service never exposes shell/GitHub/Brain DB credentials to the browser. Every control action appends a server-side audit record. The UI never fabricates progress percentages; it displays only values emitted by Brain/control-plane truth.
