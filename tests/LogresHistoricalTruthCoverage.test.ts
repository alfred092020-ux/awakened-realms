import { describe, expect, it } from 'vitest'
import {
  assertLogresHistoricalTruthCoverage,
  LOGRES_HISTORICAL_EVIDENCE_PRECEDENCE,
  LOGRES_RELEASE_CRITICAL_HISTORICAL_CLAIMS,
  LOGRES_RELEASE_CRITICAL_HISTORICAL_DOMAINS,
  type LogresHistoricalTruthClaim,
} from '../src/game/logres/reverse/LogresHistoricalTruthCoverage'

describe('Logres historical truth coverage', () => {
  it('covers every declared release-critical historical domain', () => {
    expect(() =>
      assertLogresHistoricalTruthCoverage(
        LOGRES_RELEASE_CRITICAL_HISTORICAL_CLAIMS,
      ),
    ).not.toThrow()

    const domains = new Set(
      LOGRES_RELEASE_CRITICAL_HISTORICAL_CLAIMS.map(
        (claim) => claim.domain,
      ),
    )
    expect([...domains].sort()).toEqual(
      [...LOGRES_RELEASE_CRITICAL_HISTORICAL_DOMAINS].sort(),
    )
  })

  it('pins evidence precedence with Global ahead of current JP', () => {
    expect(LOGRES_HISTORICAL_EVIDENCE_PRECEDENCE).toEqual([
      'GLOBAL_3_0_24',
      'ORIGINAL_GLOBAL_GAMEPLAY',
      'CURRENT_JP_REFERENCE',
      'RECONSTRUCTED',
    ])
  })

  it('keeps the tutorial map and retired server semantics explicitly unknown', () => {
    const tutorialMap =
      LOGRES_RELEASE_CRITICAL_HISTORICAL_CLAIMS.find(
        (claim) => claim.id === 'opening-tutorial-map-identity',
      )
    const server =
      LOGRES_RELEASE_CRITICAL_HISTORICAL_CLAIMS.find(
        (claim) => claim.id === 'retired-server-internal-semantics',
      )

    expect(tutorialMap?.confidence).toBe('UNKNOWN')
    expect(tutorialMap?.evidenceCeiling).toContain('UNRESOLVED')
    expect(server?.confidence).toBe('UNKNOWN')
    expect(server?.evidenceCeiling).toContain('retired authoritative server')
  })

  it('fails on an uncited confirmed historical claim', () => {
    const bad: LogresHistoricalTruthClaim = {
      id: 'uncited-global',
      domain: 'BOOT',
      statement: 'This must not pass.',
      confidence: 'CONFIRMED_ORIGINAL_GLOBAL_3_0_24',
      evidenceRefs: [],
      evidenceCeiling: null,
      contradictions: [],
    }

    expect(() => assertLogresHistoricalTruthCoverage([
      ...LOGRES_RELEASE_CRITICAL_HISTORICAL_CLAIMS,
      bad,
    ])).toThrow('requires explicit Global evidence')
  })

  it('fails if current-JP-only evidence is promoted to confirmed Global truth', () => {
    const bad: LogresHistoricalTruthClaim = {
      id: 'jp-only-promoted',
      domain: 'ASSETS',
      statement: 'Current JP cannot establish this as Global historical truth.',
      confidence: 'CONFIRMED_ORIGINAL_GLOBAL_3_0_24',
      evidenceRefs: ['current-jp:some-resource'],
      evidenceCeiling: null,
      contradictions: [],
    }

    expect(() => assertLogresHistoricalTruthCoverage([
      ...LOGRES_RELEASE_CRITICAL_HISTORICAL_CLAIMS,
      bad,
    ])).toThrow('requires explicit Global evidence')
  })

  it('fails when an unknown claim lacks an evidence ceiling', () => {
    const claims = LOGRES_RELEASE_CRITICAL_HISTORICAL_CLAIMS.map(
      (claim) =>
        claim.id === 'retired-server-internal-semantics'
          ? { ...claim, evidenceCeiling: null }
          : claim,
    ) as readonly LogresHistoricalTruthClaim[]

    expect(() => assertLogresHistoricalTruthCoverage(claims))
      .toThrow('requires an explicit evidence ceiling')
  })
})
