import { describe, expect, it } from 'vitest'
import {
  LOGRES_EQUIPMENT_CONTENT_MANIFEST,
  LOGRES_ITEM_CONTENT_EVIDENCE,
  LOGRES_ITEM_CONTENT_MANIFEST,
} from '../src/game/logres/generated/items/LogresItemContent'
import {
  LOGRES_PLAYABLE_BATTLE_REWARD_ITEM_KEY,
} from '../src/game/logres/battle/ReconstructedLogresPlayableBattleLoop'

describe('evidence-backed item and equipment content coverage', () => {
  it('uses a versioned stable item manifest', () => {
    expect(LOGRES_ITEM_CONTENT_MANIFEST.schemaVersion)
      .toBe('item-content-v1')
    const keys = LOGRES_ITEM_CONTENT_MANIFEST.entries.map((entry) => entry.key)
    expect(new Set(keys).size).toBe(keys.length)
  })

  it('binds the playable reward item without pretending it is historical Global content', () => {
    const item = LOGRES_ITEM_CONTENT_MANIFEST.entries[0]
    expect(item.key).toBe(LOGRES_PLAYABLE_BATTLE_REWARD_ITEM_KEY)
    expect(item.kind).toBe('RECONSTRUCTED_REWARD_ITEM')
    expect(item.confidence).toBe('RECONSTRUCTED_PLAYABILITY')
    expect(item.historicalItemId).toBeNull()
    expect(item.displayName).toBeNull()
    expect(item.rarity).toBeNull()
    expect(item.itemType).toBeNull()
    expect(item.effect).toBeNull()
  })

  it('keeps unknown statistics and equipment slot nullable', () => {
    const item = LOGRES_ITEM_CONTENT_MANIFEST.entries[0]
    expect(item.attack).toBeNull()
    expect(item.defense).toBeNull()
    expect(item.element).toBeNull()
    expect(item.equipmentSlot).toBeNull()
  })

  it('represents confirmed Global equipment capability separately from content', () => {
    expect(LOGRES_ITEM_CONTENT_EVIDENCE.itemInfoProjection.name)
      .toBe('S_GMCL_ITEM_INFO')
    expect(LOGRES_ITEM_CONTENT_EVIDENCE.itemMoveRequest.name)
      .toBe('C_GMCL_ITEM_MOVE_REQ')
    expect(LOGRES_EQUIPMENT_CONTENT_MANIFEST.entries)
      .toHaveLength(0)
    expect(LOGRES_EQUIPMENT_CONTENT_MANIFEST.schemaCapabilities)
      .toHaveLength(2)
    expect(
      LOGRES_EQUIPMENT_CONTENT_MANIFEST.schemaCapabilities.every(
        (entry) => entry.confidence === 'CONFIRMED_GLOBAL_3_0_24',
      ),
    ).toBe(true)
  })

  it('keeps the historical production catalog behind an explicit evidence ceiling', () => {
    expect(LOGRES_ITEM_CONTENT_EVIDENCE.unresolvedHistoricalItemCorpus)
      .toHaveLength(1)
    expect(LOGRES_EQUIPMENT_CONTENT_MANIFEST.coverage.status)
      .toBe('EXPLICIT_EVIDENCE_CEILING')
    expect(LOGRES_ITEM_CONTENT_MANIFEST.evidenceCeilings.join(' '))
      .toContain('must not be assigned an original item ID')
  })
})
