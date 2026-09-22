# Studio continuity checkpoint — 2026-09-22

Integration only: `feat/logres-reconstruction`. Never touch `main` or integrate
`agent/logres-playable-slice-core-001`. One active writer; isolated read-only
QA and evidence reviews can run concurrently. Clear reviewed work first;
keep research bounded to dependencies of playable integration.

Live integration was reconciled at `ff1753d15234c8c0c659ee5ce0289a59e8f26475`,
then guarded MERGE job `merge-logres-public-convexhull-source-001` advanced it
to `9a9bf7f446b792a8384d4444489b083d4b764a6c`. Fetch live before any next PATCH.
Oracle job `oracle-job-public-convexhull-source-001` completed successfully;
see `RENDERER_PROOF.md` for its exact result commit and limitations.

## Inherited specialist lanes

All nine latest studio Oracle summaries reported success, exit 0, error null;
their reports had no errors. They are metadata scans, not finished systems.
Keep these results; do not duplicate completed scans.

| Lane | Latest evidence branch suffix | Result commit prefix | Next dependency |
|---|---|---|---|
| Tutorial/onboarding | tutorial-evidence-001 | 1d68a44 | Prove map/spawn/sequence |
| Player/movement | movement-evidence-002 | 8856535 | Field geometry, collision and native speed |
| Battle | battle-evidence-001 | 3a6cb68 | Field encounter and authoritative battle slice |
| NPC/quest | npc-quest-evidence-002 | c01cd6d | Field interaction and authoritative quest state |
| Inventory/equipment | inventory-equipment-evidence-002 | 9f7359d | Original UI semantics and server inventory |
| Shop/gacha | shop-gacha-evidence-002 | 9822d15 | Original UI semantics and server transactions |
| UI/UX | ui-evidence-002 | 0c32a3a | World/HUD camera separation |
| Motion/VFX/audio | motion-vfx-audio-evidence-002 | c2b9406 | Field entities and evidenced timing |
| Protocol/backend | protocol-backend-evidence-001 | 17ed44d | Server-authoritative vertical gameplay slices |

Branch prefix: `agent/oracle-job-studio-`. Preserve map/rendering, data/evidence,
localization and QA/regression lanes alongside these specialist lanes.
No claim is made that prior chat agents remain running after handoff.

Tutorial scans locate JSON tutorial resources and skit candidates C_36_01_00
and C_41_01_01, but do not prove an initial sequence. Movement `walk` hits are
in `system.mbn:motion.tbl`; numeric battle-timer `move_speed` is not evidence
of field-player speed. Keyword occurrence alone is not a gameplay contract.

## Dependency-aware backlog

1. Authentic static terrain proof: connect decoded XY/normalized UVs to private
   atlas pixels; retain explicit unresolved rendering policies.
2. Prove Z producer, texture orientation and camera/depth behavior; then attach
   faithful field rendering to the runtime. Keep proof map out of tutorial.
3. Movement/collision with evidenced coordinate conversion and server state.
4. Field interaction, then encounter/quest/inventory vertical slices with
   replacement-server authority. Label server-only recreation RECONSTRUCTED.

Merge-ready candidate preserved: `agent/logres-client-config-crosswalk-002`,
`e3db9d2d0e238045c249269dcaa59f28e8515564`, adds only a structural config
crosswalk script and its test. Not integrated at the checkpoint base.
Read-only QA passed its self-test and actual index scan (64 shared, 2
Global-only, 41 JP-only); input index blob matches integration. Rebase its
two-file patch through Control Sheet with the next exact live SHA, run full
verification, review final compare, then guarded merge. Never merge Oracle
dispatch/result branches or private assets.
