import { describe, expect, it } from 'vitest'

import {
  LOGRES_GLOBAL_3024_LONGTAIL_COUNTS,
  LOGRES_GLOBAL_3024_LONGTAIL_FEATURES,
  LOGRES_GLOBAL_3024_LONGTAIL_PROVENANCE,
  LOGRES_GLOBAL_3024_LONGTAIL_ROUTING,
  LOGRES_GLOBAL_3024_LONGTAIL_UNRESOLVED,
} from '../src/game/logres/reverse/LogresGlobal3024LongTailEvidence'

describe('Global 3.0.24 long-tail evidence', () => {
  it('accounts for every residual first-party class family', () => {
    expect(LOGRES_GLOBAL_3024_LONGTAIL_PROVENANCE)
      .toBe('CONFIRMED_ORIGINAL_GLOBAL_3_0_24_FIRST_PARTY_RESIDUAL_CLASS_SURFACE')
    expect(LOGRES_GLOBAL_3024_LONGTAIL_COUNTS.residualClasses).toBe(223)
    expect(LOGRES_GLOBAL_3024_LONGTAIL_COUNTS.unclassifiedClasses).toBe(0)
  })

  it('routes infrastructure and presentation residuals explicitly', () => {
    expect(LOGRES_GLOBAL_3024_LONGTAIL_COUNTS.runtimeInfrastructure)
      .toEqual({ classes: 58, methods: 393 })
    expect(LOGRES_GLOBAL_3024_LONGTAIL_COUNTS.presentationPending)
      .toEqual({ classes: 46, methods: 286 })
  })

  it('recovers named long-tail features', () => {
    expect(LOGRES_GLOBAL_3024_LONGTAIL_FEATURES.collaboration)
      .toContain('FFRK')
    expect(LOGRES_GLOBAL_3024_LONGTAIL_FEATURES.sixthSense)
      .toContain('Workbench')
    expect(LOGRES_GLOBAL_3024_LONGTAIL_FEATURES.handover)
      .toContain('Handover')
  })

  it('eliminates the formerly ambiguous residual classes', () => {
    expect(LOGRES_GLOBAL_3024_LONGTAIL_ROUTING.ownManager)
      .toBe('core_player_session_state')
    expect(LOGRES_GLOBAL_3024_LONGTAIL_ROUTING.sdkOperator)
      .toBe('gplus_sns_sdk_feature')
    expect(LOGRES_GLOBAL_3024_LONGTAIL_ROUTING.webapi)
      .toBe('network_webapi_helper')
  })

  it('keeps external-service ceilings explicit', () => {
    expect(LOGRES_GLOBAL_3024_LONGTAIL_UNRESOLVED[0])
      .toContain('discontinued external collaboration services')
  })
})
