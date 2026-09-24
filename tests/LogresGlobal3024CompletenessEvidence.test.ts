import { describe, expect, it } from 'vitest'

import {
  LOGRES_GLOBAL_3024_COMPLETENESS_COUNTS,
  LOGRES_GLOBAL_3024_COMPLETENESS_PROVENANCE,
  LOGRES_GLOBAL_3024_COMPLETION_DEFINITION,
  LOGRES_GLOBAL_3024_EVIDENCE_CEILINGS,
  LOGRES_GLOBAL_3024_LFS_CATEGORY_COUNTS,
  LOGRES_GLOBAL_3024_REVERSE_ENGINEERING_STATUS,
} from '../src/game/logres/reverse/LogresGlobal3024CompletenessEvidence'

describe('Global 3.0.24 reverse-engineering completeness ledger', () => {
  it('accounts for every first-party lfs class and method entry', () => {
    const rows = Object.values(LOGRES_GLOBAL_3024_LFS_CATEGORY_COUNTS)
    expect(rows.reduce((sum, row) => sum + row[0], 0)).toBe(2372)
    expect(rows.reduce((sum, row) => sum + row[1], 0)).toBe(19467)
    expect(LOGRES_GLOBAL_3024_COMPLETENESS_COUNTS.lfsUnclassified)
      .toBe(0)
  })

  it('accounts for the recovered GmCl protocol surface', () => {
    expect(LOGRES_GLOBAL_3024_COMPLETENESS_COUNTS.gmclMessageIds)
      .toBe(631)
    expect(LOGRES_GLOBAL_3024_COMPLETENESS_COUNTS.gmclTypeMethodFamilies)
      .toBe(537)
    expect(LOGRES_GLOBAL_3024_COMPLETENESS_COUNTS.gmclConstructorTypes)
      .toBe(533)
  })

  it('accounts for Java and packaged APK content', () => {
    expect(LOGRES_GLOBAL_3024_COMPLETENESS_COUNTS.aimingJavaFiles)
      .toBe(33)
    expect(LOGRES_GLOBAL_3024_COMPLETENESS_COUNTS.apkFiles)
      .toBe(156)
    expect(LOGRES_GLOBAL_3024_COMPLETENESS_COUNTS.bootstrapMbnPackages)
      .toBe(23)
    expect(LOGRES_GLOBAL_3024_COMPLETENESS_COUNTS.decodedBootstrapMbnMembers)
      .toBe(461)
  })

  it('accounts for original source-path evidence', () => {
    expect(LOGRES_GLOBAL_3024_COMPLETENESS_COUNTS.recoveredOriginalSourcePaths)
      .toBe(139)
    expect(LOGRES_GLOBAL_3024_COMPLETENESS_COUNTS.recoveredSourceModuleFamilies)
      .toBe(22)
    expect(LOGRES_GLOBAL_3024_COMPLETION_DEFINITION).toHaveLength(6)
  })

  it('marks only external evidence ceilings as remaining', () => {
    expect(LOGRES_GLOBAL_3024_COMPLETENESS_PROVENANCE)
      .toContain('EXPLICIT_EXTERNAL_EVIDENCE_CEILINGS')
    expect(LOGRES_GLOBAL_3024_EVIDENCE_CEILINGS.length).toBeGreaterThan(0)
    expect(LOGRES_GLOBAL_3024_REVERSE_ENGINEERING_STATUS)
      .toBe('FIRST_PARTY_APK_SURFACE_FULLY_ACCOUNTED')
  })
})
