import { describe, expect, it } from 'vitest'
import {
  LOGRES_ACTOR_CONTENT_EVIDENCE,
  LOGRES_ACTOR_CONTENT_MANIFEST,
  LOGRES_NPC_ACTOR_CONTENT_MANIFEST,
  LOGRES_PLAYER_ACTOR_CONTENT_MANIFEST,
} from '../src/game/logres/generated/actors/LogresActorContent'

describe('evidence-backed actor content coverage', () => {
  it('uses stable unique actor keys and a versioned manifest', () => {
    expect(LOGRES_ACTOR_CONTENT_MANIFEST.schemaVersion)
      .toBe('actor-content-v1')
    const keys = LOGRES_ACTOR_CONTENT_MANIFEST.entries
      .map((entry) => entry.key)
    expect(new Set(keys).size).toBe(keys.length)
  })

  it('records the tutorial armored NPC as confirmed presence without inventing identity', () => {
    const npc = LOGRES_NPC_ACTOR_CONTENT_MANIFEST.entries[0]
    expect(LOGRES_ACTOR_CONTENT_EVIDENCE.tutorialNpcLandmark)
      .toEqual({
        id: 'armored-male-npc-near-player-start',
        label: 'CONFIRMED ORIGINAL',
      })
    expect(LOGRES_ACTOR_CONTENT_EVIDENCE.firstContactStage?.label)
      .toBe('CONFIRMED ORIGINAL')
    expect(npc.presenceConfidence).toBe('CONFIRMED_ORIGINAL_VIDEO')
    expect(npc.displayName).toBeNull()
    expect(npc.historicalCharacterRef).toBeNull()
    expect(npc.historicalNpcId).toBeNull()
    expect(npc.historicalRoleId).toBeNull()
  })

  it('keeps unresolved NPC presentation and dialogue explicit', () => {
    const npc = LOGRES_NPC_ACTOR_CONTENT_MANIFEST.entries[0]
    expect(npc.presentation.runtimeAssetKey).toBeNull()
    expect(npc.presentation.confidence).toBe('UNKNOWN')
    expect(npc.interaction?.requestMessage).toBe('C_GMCL_CHAR_TALK_REQ')
    expect(npc.interaction?.historicalDialoguePayloadConfidence)
      .toBe('UNRESOLVED')
    expect(npc.reconstructedBinding.scriptProvenance)
      .toBe('RECONSTRUCTED_SCRIPT')
  })

  it('marks player art as current-JP reference instead of historical Global original', () => {
    const player = LOGRES_PLAYER_ACTOR_CONTENT_MANIFEST.entries[0]
    expect(player.presentation.confidence)
      .toBe('CURRENT_JP_REFERENCE_ONLY')
    expect(player.presentation.source)
      .toBe('RECOVERED_CURRENT_JP_PRIVATE_DERIVATIVE')
    expect(player.presentation.historicalGlobalBodyId)
      .toBe('UNRESOLVED')
    expect(player.presentation.historicalGlobalEquipmentIds)
      .toBe('UNRESOLVED')
  })

  it('does not allow reconstructed guide dialogue to imply original text', () => {
    expect(
      LOGRES_ACTOR_CONTENT_MANIFEST.evidenceCeilings.some(
        (value) => value.includes('never be presented as recovered historical Global dialogue'),
      ),
    ).toBe(true)
  })
})
