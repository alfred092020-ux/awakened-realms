import type { LogresGlobalBattleKitSnapshot } from './LogresGlobalBattleKit'

/*
 * CONFIRMED ORIGINAL: five weapon/control positions in Global launch video
 * 3.0.4 at 01:30-02:15 and Equipment at 03:20-04:00. Source SHA256:
 * 488e4564622d708f8bd5ff433fb9307ee1eb50f16832d3921242bb5ff3be7d6f.
 * The three normal-skill subslots are a separate recovered client setting.
 * Existing screen coordinates are RECONSTRUCTED, not native layout proof.
 */
export const LOGRES_BATTLE_PRESENTATION_PROVENANCE = Object.freeze({
  weaponControlCount: 'CONFIRMED ORIGINAL',
  layout: 'RECONSTRUCTED',
  historicalResult: 'UNRESOLVED',
  syntheticResolution: 'RECONSTRUCTED',
} as const)

// Explicit development/test presentation mode, never an authorization boundary.
// Ordinary weapon input must not invoke the synthetic victory/reward shortcut.
export function isLogresBattleHarness(search: string): boolean {
  const values = new URLSearchParams(search).getAll('logresBattleHarness')
  return values.length === 1 && values[0] === '1'
}

export function createLogresBattlePresentation(
  snapshot: Readonly<LogresGlobalBattleKitSnapshot>,
  search: string,
) {
  return Object.freeze({
    provenance: LOGRES_BATTLE_PRESENTATION_PROVENANCE,
    weaponPanels: snapshot.weaponPanels,
    normalSkillSlotCount: snapshot.normalSkillSlotCount,
    epLabel: snapshot.epCap === null
      ? `EP ${snapshot.currentEp}`
      : `EP ${snapshot.currentEp}/${snapshot.epCap}`,
    showDemoControls: isLogresBattleHarness(search),
    historicalResult: null,
  })
}
