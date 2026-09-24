import { execFileSync } from 'node:child_process'
import { expect, test } from '@playwright/test'

test(
  'reward inventory equips and unequips one authoritative ledger item idempotently',
  async () => {
    const script = String.raw`
import { LogresItemEquipmentAuthority } from './src/game/logres/systems/LogresItemEquipmentRuntime.ts'

const authority = new LogresItemEquipmentAuthority()
authority.applyReward({
  grantKey: 'e2e-battle',
  entries: [{
    itemKey: 'e2e-weapon',
    originalItemId: null,
    quantity: 1,
  }],
})
authority.equip(
  'main-weapon',
  { grantKey: 'e2e-battle', itemKey: 'e2e-weapon' },
  'equip-1',
)
authority.equip(
  'main-weapon',
  { grantKey: 'e2e-battle', itemKey: 'e2e-weapon' },
  'equip-1',
)
authority.unequip('main-weapon', 'unequip-1')
authority.unequip('main-weapon', 'unequip-1')
console.log(JSON.stringify(authority.state))
`

    const output = execFileSync(
      './node_modules/.bin/tsx',
      ['-e', script],
      { cwd: process.cwd(), encoding: 'utf8' },
    ).trim().split('\n').at(-1)

    if (!output) throw new Error('Item/equipment E2E produced no state')
    const state = JSON.parse(output)
    expect(state.inventory.entries).toHaveLength(1)
    expect(state.equippedBySlot).toEqual({})
    expect(state.appliedCommandIds).toEqual(['equip-1', 'unequip-1'])
    expect(state.revision).toBe(3)
  },
)
