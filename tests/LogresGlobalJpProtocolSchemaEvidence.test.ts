import { describe, expect, it } from 'vitest'

import {
  LOGRES_GLOBAL_JP_PROTOCOL_CHANGED_CRITICAL,
  LOGRES_GLOBAL_JP_PROTOCOL_SCHEMA_ARTIFACT,
  LOGRES_GLOBAL_JP_PROTOCOL_SCHEMA_COUNTS,
  LOGRES_GLOBAL_JP_PROTOCOL_SCHEMA_POLICY,
  LOGRES_GLOBAL_JP_PROTOCOL_SCHEMA_PROVENANCE,
  LOGRES_GLOBAL_JP_PROTOCOL_STABLE_CRITICAL,
} from '../src/game/logres/reverse/LogresGlobalJpProtocolSchemaEvidence'

describe('Global -> JP protocol schema genealogy', () => {
  it('accounts for every Global message schema at top level', () => {
    expect(LOGRES_GLOBAL_JP_PROTOCOL_SCHEMA_PROVENANCE)
      .toBe('GLOBAL_3_0_24_PROTOCOL_AUTHORITY_WITH_BOUNDED_CURRENT_JP_LINEAGE')
    expect(LOGRES_GLOBAL_JP_PROTOCOL_SCHEMA_COUNTS.globalMessages).toBe(631)
    expect(
      LOGRES_GLOBAL_JP_PROTOCOL_SCHEMA_COUNTS.globalGeneratorSchemaMessages
      + LOGRES_GLOBAL_JP_PROTOCOL_SCHEMA_COUNTS.globalHandlerSchemaMessages
    ).toBe(631)
    expect(
      LOGRES_GLOBAL_JP_PROTOCOL_SCHEMA_COUNTS.globalUnresolvedTopLevelSchemas
    ).toBe(0)
  })

  it('quantifies stable and changed current-JP lineage', () => {
    expect(LOGRES_GLOBAL_JP_PROTOCOL_SCHEMA_COUNTS.currentJpPresentGlobalMessages)
      .toBe(470)
    expect(LOGRES_GLOBAL_JP_PROTOCOL_SCHEMA_COUNTS.identicalTopLevelSchemas)
      .toBe(367)
    expect(LOGRES_GLOBAL_JP_PROTOCOL_SCHEMA_COUNTS.changedTopLevelSchemas)
      .toBe(92)
  })

  it('keeps known stable critical messages transferable', () => {
    expect(LOGRES_GLOBAL_JP_PROTOCOL_STABLE_CRITICAL)
      .toContain('C_GMCL_FIELD_INFO_REQ_Response')
    expect(LOGRES_GLOBAL_JP_PROTOCOL_STABLE_CRITICAL)
      .toContain('C_GMCL_BATTLE_ENTRY_REQ')
    expect(LOGRES_GLOBAL_JP_PROTOCOL_STABLE_CRITICAL)
      .toContain('S_GMCL_BATTLE_BOUT_EVENT_DROP')
  })

  it('blocks backporting changed critical schemas', () => {
    expect(LOGRES_GLOBAL_JP_PROTOCOL_CHANGED_CRITICAL.characterCreateRequest.global)
      .not.toBe(
        LOGRES_GLOBAL_JP_PROTOCOL_CHANGED_CRITICAL.characterCreateRequest.currentJp
      )
    expect(LOGRES_GLOBAL_JP_PROTOCOL_CHANGED_CRITICAL.areaEnter.globalFieldCount)
      .toBe(16)
    expect(LOGRES_GLOBAL_JP_PROTOCOL_CHANGED_CRITICAL.areaEnter.currentJpFieldCount)
      .toBe(19)
    expect(LOGRES_GLOBAL_JP_PROTOCOL_CHANGED_CRITICAL.battleUseSkillRequest.global)
      .not.toBe(
        LOGRES_GLOBAL_JP_PROTOCOL_CHANGED_CRITICAL.battleUseSkillRequest.currentJp
      )
  })

  it('keeps nested constructor evidence weaker than wire-order evidence', () => {
    expect(
      LOGRES_GLOBAL_JP_PROTOCOL_SCHEMA_POLICY
        .GLOBAL_BINARY_DERIVED_CONSTRUCTOR_SHAPE
    ).toContain('not independently proven')
    expect(
      LOGRES_GLOBAL_JP_PROTOCOL_SCHEMA_POLICY
        .JP_LINEAGE_OPCODE_STABLE_SCHEMA_CHANGED
    ).toContain('must not be backported')
    expect(LOGRES_GLOBAL_JP_PROTOCOL_SCHEMA_ARTIFACT)
      .toContain('global-jp-protocol-schema')
  })
})
