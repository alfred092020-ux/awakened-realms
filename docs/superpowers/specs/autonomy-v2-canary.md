# Autonomy v2 integration canary

This file is a deliberately inert, docs-only proof packet for the Logres control plane.

Acceptance signal:

- candidate is isolated from main;
- worker scope and fast gate pass;
- shared full-E2E merge preflight validates the exact candidate SHA;
- logres-autonomy applies the verified preflight through the policy-gated autonomy actor;
- canonical feat/logres-reconstruction advances to the preflight result SHA without a second gameplay gate;
- the autonomy circuit breaker remains untripped.

The canary changes no gameplay behavior, runtime evidence, assets, or production configuration.
