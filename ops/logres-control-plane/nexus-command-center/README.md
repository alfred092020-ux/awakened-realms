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

The `android/` directory contains a minimal native Android shell for Nexus Command Center. It uses the platform WebView, preserves the existing server-side authentication/session model, blocks cleartext HTTP, cancels TLS errors, and accepts only an `https://` Command Center address.

Build a debug APK:

```bash
ops/logres-control-plane/nexus-command-center/android/build_apk.sh
```

The first launch asks for the private HTTPS Command Center URL. The URL is stored locally in app preferences. The Nexus access token is not persisted by the wrapper; authentication remains inside the Command Center's HttpOnly session. Long-press inside the app to reload or change the configured server.

## Controls

Direct: force refresh, Wake Lead event, supervisor tick, bounded autonomy cycle, exact ref verification, guarded preflight (explicit typed confirmation + busy check).

Governed requests: pause/resume autonomy, retry task, stale-lease release, Samsung/device QA. These intentionally flow through Lead/Nexus policy until a canonical direct primitive exists.

## Safety and evidence

The service never exposes shell/GitHub/Brain DB credentials to the browser. Every control action appends a server-side audit record. The UI never fabricates progress percentages; it displays only values emitted by Brain/control-plane truth.
