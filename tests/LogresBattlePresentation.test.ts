import { describe, expect, it } from 'vitest'
import { LogresGlobalBattleKit } from '../src/game/logres/battle/LogresGlobalBattleKit'
import { createLogresBattlePresentation, isLogresBattleHarness } from '../src/game/logres/battle/LogresBattlePresentation'

function snapshot(epCap: number | null = null) {
  return new LogresGlobalBattleKit({
    weaponPanels: [{
      unlocked: true, weaponRef: 'reconstructed-weapon',
      normalSkillRef: null, specialSkillRef: null, specialEpCost: null,
    }],
    selectedWeaponSlot: 0, currentEp: 0, epCap,
  }).snapshot()
}

describe('Global battle presentation boundary', () => {
  it('keeps five weapon controls distinct from normal-skill subslots', () => {
    const view = createLogresBattlePresentation(snapshot(), '')
    expect(view.weaponPanels).toHaveLength(5)
    expect(view.normalSkillSlotCount).toBe(3)
    expect(view.weaponPanels.filter(panel => panel.weaponRef !== null)).toHaveLength(1)
    expect(view.weaponPanels[0].specialSkillRef).toBeNull()
    expect(view.weaponPanels[0].specialEpCost).toBeNull()
    expect(view.historicalResult).toBeNull()
    expect(view.provenance).toMatchObject({
      weaponControlCount: 'CONFIRMED ORIGINAL',
      layout: 'RECONSTRUCTED',
      historicalResult: 'UNRESOLVED',
    })
  })

  it('does not invent an unknown EP cap', () => {
    expect(createLogresBattlePresentation(snapshot(), '').epLabel).toBe('EP 0')
    expect(createLogresBattlePresentation(snapshot(5), '').epLabel).toBe('EP 0/5')
  })

  it.each(['', '?logresBattleHarness=0', '?logresBattleHarness=true',
    '?logresBattleHarness=11', '?other=1',
    '?logresBattleHarness=1&logresBattleHarness=0'])(
    'keeps synthetic victory controls off for %s', search => {
      expect(isLogresBattleHarness(search)).toBe(false)
      expect(createLogresBattlePresentation(snapshot(), search).showDemoControls).toBe(false)
    },
  )

  it('allows only the explicit synthetic battle harness', () => {
    expect(isLogresBattleHarness('?logresBattleHarness=1')).toBe(true)
    expect(createLogresBattlePresentation(snapshot(), '?logresBattleHarness=1').showDemoControls).toBe(true)
  })
})
