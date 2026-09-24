import { describe, expect, it } from 'vitest'

import {
  LOGRES_RECONSTRUCTION_CLOSURE_ARTIFACT,
  LOGRES_RECONSTRUCTION_CLOSURE_ARTIFACT_SHA256,
  LOGRES_RECONSTRUCTION_CLOSURE_COUNTS,
  LOGRES_RECONSTRUCTION_CLOSURE_FACTS_SHA256,
  LOGRES_RECONSTRUCTION_CLOSURE_DOMAIN_COVERAGE,
  LOGRES_RECONSTRUCTION_CLOSURE_GAPS,
  LOGRES_RECONSTRUCTION_CLOSURE_ID,
  LOGRES_RECONSTRUCTION_CLOSURE_POLICY,
  LOGRES_RECONSTRUCTION_CLOSURE_PROVENANCE,
} from '../src/game/logres/reverse/LogresReconstructionClosureEvidence'

describe('OMEGA exhaustive reconstruction closure', () => {
  it('accounts for the entire required Global first-party surface', () => {
    expect(LOGRES_RECONSTRUCTION_CLOSURE_PROVENANCE)
      .toBe('OMEGA_EXHAUSTIVE_RECONSTRUCTION_CLOSURE_WITH_TERMINAL_CEILINGS')

    expect(LOGRES_RECONSTRUCTION_CLOSURE_COUNTS.lfsClasses).toBe(2372)
    expect(LOGRES_RECONSTRUCTION_CLOSURE_COUNTS.lfsMethods).toBe(19467)
    expect(LOGRES_RECONSTRUCTION_CLOSURE_COUNTS.protocolMessages).toBe(631)
    expect(LOGRES_RECONSTRUCTION_CLOSURE_COUNTS.protocolConstructorTypes)
      .toBe(533)
    expect(LOGRES_RECONSTRUCTION_CLOSURE_COUNTS.criticalStateTransitions)
      .toBe(28)
  })

  it('has a complete classification partition', () => {
    const counts = LOGRES_RECONSTRUCTION_CLOSURE_COUNTS

    expect(
      counts.covered
      + counts.evidenceKnownNotImplemented
      + counts.implementationWithWeakerEvidence
      + counts.externallyUnrecoverable
      + counts.unresolved,
    ).toBe(counts.factsTotal)

    expect(counts.factsTotal).toBe(26584)
    expect(counts.covered).toBe(1038)
    expect(counts.evidenceKnownNotImplemented).toBe(23406)
  })

  it('does not upgrade JP lineage into confirmed Global coverage', () => {
    const jp = LOGRES_RECONSTRUCTION_CLOSURE_DOMAIN_COVERAGE
      .currentJpMapLineageReference

    expect(jp.implementationWithWeakerEvidence).toBe(11)
    expect(jp.unresolved).toBe(2105)
    expect(jp).not.toHaveProperty('covered')

    expect(LOGRES_RECONSTRUCTION_CLOSURE_POLICY)
      .toContain(
        'Current-JP-only maps and changed resources remain weaker lineage references and never backfill Global.',
      )
  })

  it('does not let umbrella package references cover every member', () => {
    const members = LOGRES_RECONSTRUCTION_CLOSURE_DOMAIN_COVERAGE
      .globalPackageMember

    expect(
      members.covered + members.evidenceKnownNotImplemented,
    ).toBe(LOGRES_RECONSTRUCTION_CLOSURE_COUNTS.globalPackageMembers)

    expect(members.covered).toBe(65)
    expect(members.evidenceKnownNotImplemented).toBe(396)

    expect(LOGRES_RECONSTRUCTION_CLOSURE_POLICY)
      .toContain(
        'Package-member coverage requires the member entry itself; a package-level reference does not cover every member.',
      )
  })

  it('uses strict protocol/function bindings for critical transitions', () => {
    const transitions = LOGRES_RECONSTRUCTION_CLOSURE_DOMAIN_COVERAGE
      .criticalStateTransition

    expect(transitions.covered).toBe(23)
    expect(transitions.evidenceKnownNotImplemented).toBe(5)

    expect(LOGRES_RECONSTRUCTION_CLOSURE_POLICY)
      .toContain(
        'Critical-transition coverage requires the exact Global message or a directly bound Global function; generic action or trigger prose does not count.',
      )
  })

  it('turns external evidence ceilings into terminal facts', () => {
    expect(LOGRES_RECONSTRUCTION_CLOSURE_COUNTS.externalEvidenceCeilings)
      .toBe(9)
    expect(
      LOGRES_RECONSTRUCTION_CLOSURE_DOMAIN_COVERAGE
        .externalEvidenceCeiling
        .externallyUnrecoverable,
    ).toBe(9)

    const external = LOGRES_RECONSTRUCTION_CLOSURE_GAPS
      .find(row => row.status === 'TERMINAL_EXTERNAL_CEILING')

    expect(external?.suggestedTask).toBeNull()
  })

  it('emits one bounded advisory candidate for each researchable gap', () => {
    const researchable = LOGRES_RECONSTRUCTION_CLOSURE_GAPS
      .filter(row => row.status === 'RESEARCHABLE_BOUNDED')

    expect(researchable).toHaveLength(3)
    expect(new Set(researchable.map(row => row.key)).size).toBe(3)
    expect(LOGRES_RECONSTRUCTION_CLOSURE_COUNTS.boundedResearchCandidates)
      .toBe(3)

    expect(LOGRES_RECONSTRUCTION_CLOSURE_POLICY)
      .toContain(
        'At most one advisory research candidate is emitted per canonical gap; AUTO-RE and UNBLOCK parents are forbidden.',
      )
    expect(LOGRES_RECONSTRUCTION_CLOSURE_POLICY)
      .toContain(
        'Closure emits no automatic task creation, merge or deployment action.',
      )
  })

  it('is hash-bound to a deterministic closure artifact', () => {
    expect(LOGRES_RECONSTRUCTION_CLOSURE_ID).toHaveLength(64)
    expect(LOGRES_RECONSTRUCTION_CLOSURE_FACTS_SHA256)
      .toBe('bec04a87dfedd20202653f3d01e0a4ae1e68fa906c287d9e3dd63d95dc93c9bf')
    expect(LOGRES_RECONSTRUCTION_CLOSURE_ARTIFACT_SHA256)
      .toBe('dbfda735f3c6820dbd9956b6e2d3fca36bc642f4091a0067187d62cfbdaecda2')
    expect(LOGRES_RECONSTRUCTION_CLOSURE_ARTIFACT)
      .toContain('global-reconstruction-closure-20260924.json')
  })
})
