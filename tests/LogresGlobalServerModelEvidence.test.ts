import { describe, expect, it } from 'vitest'

import {
  LOGRES_GLOBAL_SERVER_MODEL_CONSTRUCTOR_GUARDRAIL,
  LOGRES_GLOBAL_SERVER_MODEL_ENTITIES,
  LOGRES_GLOBAL_SERVER_MODEL_EXTERNAL_CEILINGS,
  LOGRES_GLOBAL_SERVER_MODEL_JP_POLICY,
  LOGRES_GLOBAL_SERVER_MODEL_PROVENANCE,
  LOGRES_GLOBAL_SERVER_MODEL_RELATIONSHIPS,
  LOGRES_GLOBAL_SERVER_MODEL_SEMANTICS,
  LOGRES_GLOBAL_SERVER_MODEL_SOURCE,
} from '../src/game/logres/reverse/LogresGlobalServerModelEvidence'

describe('Global 3.0.24 client-observed server boundary model', () => {
  it('publishes nine bounded projection entities from Global evidence', () => {
    expect(LOGRES_GLOBAL_SERVER_MODEL_PROVENANCE)
      .toBe('CONFIRMED_GLOBAL_3_0_24_CLIENT_OBSERVED_SERVER_BOUNDARY_MODEL')
    expect(Object.keys(LOGRES_GLOBAL_SERVER_MODEL_ENTITIES)).toHaveLength(9)
    expect(LOGRES_GLOBAL_SERVER_MODEL_ENTITIES.character.identityOrCorrelationTypes)
      .toContain('t_CUID')
    expect(LOGRES_GLOBAL_SERVER_MODEL_ENTITIES.field.identityOrCorrelationTypes)
      .toContain('t_AreaUID')
    expect(LOGRES_GLOBAL_SERVER_MODEL_ENTITIES.battle.identityOrCorrelationTypes)
      .toContain('t_BattleSystemUID')
  })

  it('anchors large record shapes to original Global constructors', () => {
    expect(LOGRES_GLOBAL_SERVER_MODEL_ENTITIES.inventory.recordShapes.t_ItemInfoOne)
      .toBe(65)
    expect(LOGRES_GLOBAL_SERVER_MODEL_ENTITIES.inventory.recordShapes.t_ItemDetail)
      .toBe(20)
    expect(LOGRES_GLOBAL_SERVER_MODEL_ENTITIES.quest.recordShapes.t_QuestAcceptRequestParam)
      .toBe(12)
    expect(LOGRES_GLOBAL_SERVER_MODEL_ENTITIES.battle.recordShapes.t_BoutEventHeader)
      .toBe(4)
  })

  it('publishes ten client-observed relationships with message evidence', () => {
    expect(LOGRES_GLOBAL_SERVER_MODEL_RELATIONSHIPS).toHaveLength(10)
    const rewardToInventory = LOGRES_GLOBAL_SERVER_MODEL_RELATIONSHIPS.find(
      (row) =>
        row.source === 'RewardProjection'
        && row.target === 'InventoryProjection',
    )
    expect(rewardToInventory?.relation).toBe('MAY_UPDATE')
    expect(rewardToInventory?.evidenceMessages).toContain('S_GMCL_ITEM_INFO')
  })

  it('does not turn client projections into database or server implementation claims', () => {
    expect(LOGRES_GLOBAL_SERVER_MODEL_SEMANTICS)
      .toContain('not claims about database tables')
    expect(LOGRES_GLOBAL_SERVER_MODEL_CONSTRUCTOR_GUARDRAIL)
      .toContain('not independently proven database rows')
    expect(LOGRES_GLOBAL_SERVER_MODEL_EXTERNAL_CEILINGS)
      .toContain(
        'Persistence/database schema, transaction boundaries, locking and commit order.',
      )
  })

  it('keeps current JP subordinate to recovered Global authority', () => {
    expect(LOGRES_GLOBAL_SERVER_MODEL_JP_POLICY)
      .toContain('JP does not define the historical Global server model')
    expect(LOGRES_GLOBAL_SERVER_MODEL_SOURCE.protocolSchemaSha256).toHaveLength(64)
    expect(LOGRES_GLOBAL_SERVER_MODEL_SOURCE.modelArtifactSha256)
      .toBe('8d21821cbd07de50d34d06ee547ec71dd3ae3f8df27c2a5a5187d165d1e3e369')
  })
})
