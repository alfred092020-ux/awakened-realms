# Nexus Control Center

Mobile-first PWA for Nexus Core Inc autonomous operations. It is a visual projection of Brain/Git truth with an SSE live stream. Operator actions are recorded as governed Brain `CONTROL_REQUEST` intents to Lead; the browser never receives shell, GitHub, Brain DB, or VM credentials.

## Run on the VM

```bash
export NEXUS_CONTROL_CENTER_TOKEN='long-random-secret'
python3 server.py --host 127.0.0.1 --port 8787
```

Expose it only through authenticated HTTPS (for example the existing private tunnel/access layer). The server refuses a non-loopback bind without a token.

## Real-time model

`/api/events` uses Server-Sent Events. Fast Brain/Git state is sampled about every 2 seconds; the heavier control-plane task inventory reconciles about every 30 seconds. The UI explicitly shows LIVE / RECONNECTING / STALE.

## Governance

Control buttons do not directly mutate Git, services, or Brain DB. They emit allow-listed `CONTROL_REQUEST` events for Lead/Nexus to evaluate under existing leases, claims, preflight and project policy.
