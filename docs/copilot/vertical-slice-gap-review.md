# Vertical Slice Gap Review

## Scope

Audit scope: the currently playable Logres reconstruction path from title through reward/inventory.

Excluded active reverse-engineering lanes (not recommended here):
- Global APK battle
- Global APK field / movement / collision / NPC / encounter
- Global APK onboarding
- Global APK protocol

This report separates repository facts from inference and proposes exactly one bounded next task.

## Stage status

| Stage | Status | Repository facts | Supporting tests |
| --- | --- | --- | --- |
| Title entry | Implemented | `src/game/scenes/LogresTitleScene.ts` renders the title background/logo and advances to `LogresWorldSelectScene` on start input. | `e2e/logres-smoke.spec.mjs` |
| World select | Implemented | `src/game/scenes/LogresWorldSelectScene.ts` exposes one reconstructed world card and stores `logres.world.selectedId` before starting `LogresCharacterCreateScene`. | `e2e/logres-world-select-input.spec.mjs` |
| Character create -> tutorial field handoff | Implemented | `src/game/scenes/LogresCharacterCreateScene.ts` builds `C_GMCL_CHAR_CREATE_REQ`, sends it through `submitCharacterCreateToReplacementServer`, stores the response in registry, and starts `LogresFieldScene`. | `tests/CharacterCreateProtocol.test.ts`, `tests/LogresReplacementServer.test.ts` |
| Tutorial field / encounter launch | Implemented | `src/game/scenes/LogresFieldScene.ts` loads the playable field runtime, launches `ReconstructedLogresEncounterAuthority`, bridges into `LogresBattleScene`, and records encounter/battle provenance in registry. | `tests/LogresPlayableFieldRuntime.test.ts`, `tests/ReconstructedLogresEncounterAuthority.test.ts`, `tests/ReconstructedLogresBattleEntryBridge.test.ts`, `e2e/logres-playable-field.spec.mjs`, `e2e/logres-demo01-loop.spec.mjs` |
| Battle -> reward persistence | Implemented | `src/game/scenes/LogresBattleScene.ts` calls `completeReconstructedLogresDemoBattle`, which records result/reward stages and persists inventory via `applyReconstructedLogresBattleRewardGrant`. | `tests/ReconstructedLogresBattleResolutionFlow.test.ts`, `tests/ReconstructedLogresRewardInventoryAdapter.test.ts`, `tests/LogresInventoryAuthority.test.ts`, `tests/ReconstructedLogresDemoBattleLoop.test.ts`, `e2e/logres-demo01-loop.spec.mjs` |
| Returned field reward/inventory acknowledgment | Missing | The battle scene stores `logres.demo01.inventory`, `logres.demo01.rewardApplied`, and `logres.demo01.resolution`, but `src/game/scenes/LogresFieldScene.ts` has no `logres.demo01.*` consumer after returning from battle. | `e2e/logres-demo01-loop.spec.mjs` only verifies registry state after return, not visible reward/inventory presentation |

## Single highest-value safe remaining gap

**Gap:** add a clearly reconstructed post-battle reward/inventory acknowledgment on the returned field scene.

### Facts

1. `src/game/scenes/LogresBattleScene.ts` already persists the post-battle outputs needed for a field-side acknowledgment:
   - `resolveDemo01Battle()` stores `logres.demo01.inventory`, `logres.demo01.rewardApplied`, and `logres.demo01.resolution`.
   - The same method then enables `RETURN TO MILLENNIUM TREE`, which restarts `LogresFieldScene`.
2. `src/game/logres/battle/ReconstructedLogresDemoBattleLoop.ts` already drives the reconstructed reward/inventory path all the way to `field-return-ready` and returns the updated inventory ledger.
3. `src/game/logres/server/LogresInventoryAuthority.ts` and `src/game/logres/battle/ReconstructedLogresRewardInventoryAdapter.ts` already provide tested reward persistence and idempotency boundaries.
4. `src/game/logres/battle/ReconstructedLogresBattleResolutionFlow.ts` distinguishes `reward-ready`, `reward-presented`, `field-return-ready`, and optional field overlay state, so the reward/inventory handoff is already modeled as a separate concern.
5. `src/game/scenes/LogresFieldScene.ts` loads Global `quest_texts.json` and `inventory_text.json`, but the current returned-field flow does not consume the stored reward/inventory state at all.
6. `e2e/logres-demo01-loop.spec.mjs` proves the data survives the loop, but its final assertions only inspect registry state (`inventoryRevision`, `inventoryEntries`, `rewardApplied`, `phase`) after the field reloads.

### Inference

The last user-visible gap in the current playable slice is not reward persistence itself; it is the missing field-side acknowledgment that a reward was received and recorded. Because the required data is already emitted by the current battle/reward code, the safest next step is to consume those existing outputs without reopening the active battle, field-movement, onboarding, or protocol lanes.

## Why this does not conflict with the active lanes

- It can be implemented as a **read-only consumer** of already-emitted registry state:
  - `logres.demo01.inventory`
  - `logres.demo01.rewardApplied`
  - `logres.demo01.resolution`
- It does **not** require changing:
  - encounter eligibility or battle-entry logic
  - pathfinding / movement / collision behavior
  - world-select or character-create sequencing
  - protocol tuple formats or replacement-server request validation
- It stays on the presentation side of the existing reconstructed reward/inventory boundary instead of duplicating the excluded reverse-engineering work.

## Exact files, symbols, and tests supporting this pick

### Files and symbols

- `src/game/scenes/LogresBattleScene.ts`
  - `resolveDemo01Battle()`
  - registry keys: `logres.demo01.inventory`, `logres.demo01.rewardApplied`, `logres.demo01.resolution`, `logres.demo01.battleStatus`
- `src/game/scenes/LogresFieldScene.ts`
  - `preload()` loads `logres-quest-text-en` and `logres-inventory-text-en`
  - no `logres.demo01.*` consumer exists in this scene
- `src/game/logres/battle/ReconstructedLogresDemoBattleLoop.ts`
  - `completeReconstructedLogresDemoBattle()`
- `src/game/logres/battle/ReconstructedLogresBattleResolutionFlow.ts`
  - `recordRewardStage()`
  - `markRewardPresented()`
  - `markFieldReturnReady()`
  - `queueFieldOverlay()`
- `src/game/logres/battle/ReconstructedLogresRewardInventoryAdapter.ts`
  - `applyReconstructedLogresBattleRewardGrant()`
- `src/game/logres/server/LogresInventoryAuthority.ts`
  - `createReconstructedLogresInventory()`
  - `applyReconstructedLogresInventoryGrant()`

### Tests

- `tests/ReconstructedLogresDemoBattleLoop.test.ts`
- `tests/ReconstructedLogresBattleResolutionFlow.test.ts`
- `tests/ReconstructedLogresRewardInventoryAdapter.test.ts`
- `tests/LogresInventoryAuthority.test.ts`
- `tests/ReconstructedLogresEncounterAuthority.test.ts`
- `tests/ReconstructedLogresBattleEntryBridge.test.ts`
- `tests/LogresPlayableFieldRuntime.test.ts`
- `tests/CharacterCreateProtocol.test.ts`
- `tests/LogresReplacementServer.test.ts`
- `e2e/logres-world-select-input.spec.mjs`
- `e2e/logres-demo01-loop.spec.mjs`
- `e2e/logres-smoke.spec.mjs`

## One bounded next task

Add one **explicitly RECONSTRUCTED** post-return reward/inventory summary layer in `src/game/scenes/LogresFieldScene.ts` that:

1. only appears when `logres.demo01.resolution?.phase === 'field-return-ready'`
2. reads the already-persisted `logres.demo01.rewardApplied` flag and latest `logres.demo01.inventory` ledger entry
3. presents that information as reconstructed field-side acknowledgment rather than invented original Global reward UI
4. can be dismissed or cleared without changing encounter, movement, onboarding, or protocol contracts

## Exact verification gates for that next task

1. **Targeted unit coverage** for the new reward/inventory presentation decision logic, including:
   - no overlay when no `logres.demo01.resolution` exists
   - no overlay when the phase is not `field-return-ready`
   - correct reconstructed summary when `rewardApplied === true`
   - idempotent behavior when the same inventory grant is already present
2. **Update `e2e/logres-demo01-loop.spec.mjs`** so it verifies both:
   - the existing registry state (`rewardApplied`, `inventoryRevision`, `inventoryEntries`, `phase`)
   - one visible field-side reconstructed reward/inventory acknowledgment after returning to `LogresFieldScene`
3. **Keep these existing regressions green:**
   - `npx vitest run tests/ReconstructedLogresDemoBattleLoop.test.ts tests/ReconstructedLogresBattleResolutionFlow.test.ts tests/ReconstructedLogresRewardInventoryAdapter.test.ts tests/LogresInventoryAuthority.test.ts tests/ReconstructedLogresEncounterAuthority.test.ts tests/ReconstructedLogresBattleEntryBridge.test.ts tests/LogresPlayableFieldRuntime.test.ts tests/CharacterCreateProtocol.test.ts tests/LogresReplacementServer.test.ts`
   - `npx playwright test e2e/logres-world-select-input.spec.mjs e2e/logres-demo01-loop.spec.mjs`
   - `npm run build`
