import { describe, expect, it } from 'vitest'
import {
  createOpeningTutorialQuestContentInstance,
  LOGRES_QUEST_CONTENT_EVIDENCE,
  LOGRES_QUEST_CONTENT_MANIFEST,
} from '../src/game/logres/generated/quests/LogresQuestContent'
import {
  createUnresolvedTutorialQuestInstance,
} from '../src/game/logres/server/LogresQuestInstanceAuthority'

describe('evidence-backed quest content coverage', () => {
  it('uses a versioned stable quest manifest', () => {
    expect(LOGRES_QUEST_CONTENT_MANIFEST.schemaVersion)
      .toBe('quest-content-v1')
    const keys = LOGRES_QUEST_CONTENT_MANIFEST.entries.map((entry) => entry.key)
    expect(new Set(keys).size).toBe(keys.length)
  })

  it('records the original tutorial sequence without fabricating quest identity', () => {
    const quest = LOGRES_QUEST_CONTENT_MANIFEST.entries[0]
    expect(quest.key).toBe('opening-tutorial')
    expect(quest.existenceConfidence).toBe('CONFIRMED_ORIGINAL_VIDEO')
    expect(quest.historicalQuestRecordId).toBeNull()
    expect(quest.historicalQuestUid).toBeNull()
    expect(quest.historicalMapId).toBeNull()
    expect(quest.historicalRoomId).toBeNull()
    expect(quest.confirmedSequence).toEqual([
      'npc-first-contact',
      'field-control-visible',
      'quest-start-win-battle',
      'guided-field-encounter',
      'battle-entry',
      'first-attack-guidance',
    ])
  })

  it('binds the declared tutorial content to the existing unresolved runtime instance', () => {
    expect(createOpeningTutorialQuestContentInstance())
      .toEqual(createUnresolvedTutorialQuestInstance())
    expect(createOpeningTutorialQuestContentInstance()).toEqual({
      provenance: 'RECONSTRUCTED',
      instanceKey: 'opening-tutorial',
      questRecordId: null,
      mapId: null,
      roomId: null,
      playerSpawn: null,
      objectiveIds: [],
      encounterIds: [],
      npcStateIds: [],
      tutorialOverlayIds: [],
      rules: {
        timeLimitSeconds: null,
        defeatLimit: null,
        battleCapacity: null,
        requiredPower: null,
      },
    })
  })

  it('pins confirmed Global quest protocol and quest-start presentation evidence', () => {
    expect(LOGRES_QUEST_CONTENT_EVIDENCE.acceptRequest.name)
      .toBe('C_GMCL_QUEST_ACCEPT_REQ')
    expect(LOGRES_QUEST_CONTENT_EVIDENCE.statePushSequence)
      .toContain('S_GMCL_QUEST_INFO_STATE_RESULT')
    expect(LOGRES_QUEST_CONTENT_EVIDENCE.questStartText.sourceLabel)
      .toBe('CONFIRMED ORIGINAL')
    expect(LOGRES_QUEST_CONTENT_EVIDENCE.questStartBackground.sourceLabel)
      .toBe('CONFIRMED ORIGINAL')
  })

  it('keeps unresolved historical quest payloads behind explicit evidence ceilings', () => {
    expect(LOGRES_QUEST_CONTENT_EVIDENCE.unresolvedHistoricalQuestCorpus)
      .toHaveLength(1)
    const quest = LOGRES_QUEST_CONTENT_MANIFEST.entries[0]
    expect(quest.objectives).toEqual([])
    expect(quest.encounters).toEqual([])
    expect(quest.npcStateIds).toEqual([])
    expect(quest.tutorialOverlayIds).toEqual([])
    expect(quest.rules).toEqual({
      timeLimitSeconds: null,
      defeatLimit: null,
      battleCapacity: null,
      requiredPower: null,
    })
  })
})
