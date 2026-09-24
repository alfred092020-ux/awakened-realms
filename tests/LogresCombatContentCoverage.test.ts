import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LogresGlobalBattleKit,
} from '../src/game/logres/battle/LogresGlobalBattleKit'

import {
  LOGRES_GLOBAL_3024_BATTLE_UNRESOLVED,
} from '../src/game/logres/battle/LogresGlobal3024BattleEvidence'

import {
  createLogresTutorialCombatContentBattleKitInput,
  LOGRES_BOSS_CONTENT_MANIFEST,
  LOGRES_COMBAT_CONTENT_EVIDENCE,
  LOGRES_COMBAT_CONTENT_MANIFEST,
  LOGRES_ENEMY_CONTENT_MANIFEST,
  LOGRES_SKILL_CONTENT_MANIFEST,
} from '../src/game/logres/generated/combat/LogresCombatContent'

function unique(
  values: readonly string[],
): boolean {
  return new Set(
    values,
  ).size ===
    values.length
}

describe(
  'evidence-backed combat content coverage',
  () => {
    it(
      'uses a versioned stable manifest with unique content keys',
      () => {
        expect(
          LOGRES_COMBAT_CONTENT_MANIFEST
            .schemaVersion,
        ).toBe(
          'combat-content-v1',
        )

        expect(
          LOGRES_COMBAT_CONTENT_MANIFEST
            .clientVersion,
        ).toBe(
          '3.0.24',
        )

        expect(
          LOGRES_COMBAT_CONTENT_MANIFEST
            .historicalAuthority,
        ).toBe(
          'GLOBAL_3_0_24_CLIENT_AND_BOOTSTRAP',
        )

        const keys = [
          ...LOGRES_ENEMY_CONTENT_MANIFEST
            .entries
            .map(
              entry =>
                entry.key,
            ),
          ...LOGRES_SKILL_CONTENT_MANIFEST
            .entries
            .map(
              entry =>
                entry.key,
            ),
          ...LOGRES_SKILL_CONTENT_MANIFEST
            .schemaCapabilities
            .map(
              entry =>
                entry.key,
            ),
        ]

        expect(
          unique(
            keys,
          ),
        ).toBe(
          true,
        )
      },
    )

    it(
      'keeps confirmed Green Jell tutorial identity separate from JP presentation lineage',
      () => {
        const enemy =
          LOGRES_ENEMY_CONTENT_MANIFEST
            .entries[
              0
            ]

        expect(
          enemy.displayName,
        ).toBe(
          'Green Jell',
        )

        expect(
          enemy.identityConfidence,
        ).toBe(
          'CONFIRMED_GLOBAL_3_0_24',
        )

        expect(
          enemy.historicalInternalId,
        ).toBeNull()

        expect(
          enemy.historicalShapeId,
        ).toBeNull()

        expect(
          enemy.presentation
            .currentJpResourcePath,
        ).toBe(
          'avatar/enm_001_000_000.mbn',
        )

        expect(
          enemy.presentation
            .presentationConfidence,
        ).toBe(
          'CURRENT_JP_LINEAGE_REFERENCE_ONLY',
        )

        expect(
          enemy.presentation
            .historicalGlobalVisualApplication,
        ).toBe(
          'SUPPORTED_INFERENCE',
        )

        expect(
          enemy.presentation
            .currentJpResourceSha1,
        ).toBe(
          '21123af65e10563820bea001b1981a7d427477f8',
        )
      },
    )

    it(
      'does not fabricate enemy stats or boss classification',
      () => {
        const enemy =
          LOGRES_ENEMY_CONTENT_MANIFEST
            .entries[
              0
            ]

        expect(
          enemy.stats,
        ).toEqual({
          hp:
            null,
          attack:
            null,
          defense:
            null,
          element:
            null,
        })

        expect(
          enemy.bossClassification,
        ).toBe(
          'UNKNOWN',
        )

        expect(
          LOGRES_GLOBAL_3024_BATTLE_UNRESOLVED,
        ).toContain(
          'server-side enemy stat formulas',
        )

        expect(
          LOGRES_GLOBAL_3024_BATTLE_UNRESOLVED,
        ).toContain(
          'exact historical tutorial opponent stats',
        )
      },
    )

    it(
      'keeps historical boss content empty behind an explicit evidence ceiling',
      () => {
        expect(
          LOGRES_BOSS_CONTENT_MANIFEST
            .entries,
        ).toHaveLength(
          0,
        )

        expect(
          LOGRES_BOSS_CONTENT_MANIFEST
            .coverage
            .status,
        ).toBe(
          'EXPLICIT_EVIDENCE_CEILING',
        )

        expect(
          LOGRES_BOSS_CONTENT_MANIFEST
            .coverage
            .confidence,
        ).toBe(
          'UNKNOWN',
        )

        expect(
          LOGRES_BOSS_CONTENT_MANIFEST
            .coverage
            .doNotInfer,
        ).toContain(
          'Do not classify Green Jell as a boss.',
        )
      },
    )

    it(
      'distinguishes reconstructed playable skill content from confirmed Global schema capabilities',
      () => {
        const playable =
          LOGRES_SKILL_CONTENT_MANIFEST
            .entries[
              0
            ]

        expect(
          playable.kind,
        ).toBe(
          'PLAYABLE_RECONSTRUCTION',
        )

        expect(
          playable.confidence,
        ).toBe(
          'RECONSTRUCTED_PLAYABILITY',
        )

        expect(
          playable.runtimeSkillRef,
        ).toBe(
          'reconstructed-normal-attack',
        )

        expect(
          playable.historicalSkillUid,
        ).toBeNull()

        for (
          const capability of
          LOGRES_SKILL_CONTENT_MANIFEST
            .schemaCapabilities
        ) {
          expect(
            capability.kind,
          ).toBe(
            'GLOBAL_SCHEMA_CAPABILITY',
          )

          expect(
            capability.confidence,
          ).toBe(
            'CONFIRMED_GLOBAL_3_0_24',
          )

          expect(
            capability.runtimeSkillRef,
          ).toBeNull()

          expect(
            capability.historicalSkillUid,
          ).toBeNull()
        }
      },
    )

    it(
      'leaves unresolved historical skill mechanics nullable instead of inventing values',
      () => {
        const allSkills = [
          ...LOGRES_SKILL_CONTENT_MANIFEST
            .entries,
          ...LOGRES_SKILL_CONTENT_MANIFEST
            .schemaCapabilities,
        ]

        for (
          const skill of
          allSkills
        ) {
          expect(
            skill.mechanics,
          ).toEqual({
            damageFormula:
              null,
            cooldownSeconds:
              null,
            recastSeconds:
              null,
            epCost:
              null,
            targetRule:
              null,
          })
        }

        expect(
          LOGRES_GLOBAL_3024_BATTLE_UNRESOLVED,
        ).toContain(
          'server-side damage formulas',
        )

        expect(
          LOGRES_GLOBAL_3024_BATTLE_UNRESOLVED,
        ).toContain(
          'exact cooldown and recast values',
        )
      },
    )

    it(
      'pins exact recovered Global battle package and bootstrap resource hashes',
      () => {
        expect(
          LOGRES_COMBAT_CONTENT_EVIDENCE
            .exactBattlePackage,
        ).toMatchObject({
          resourceNode:
            'resource:global-cache:Battle.mbn',
          sha256:
            '65b8cb1e49e91effe33d8cc934e35bbd08068b09c7443061d8aaeb67245606fc',
          lineage:
            'GLOBAL_JP_IDENTICAL',
        })

        expect(
          LOGRES_COMBAT_CONTENT_EVIDENCE
            .battleMultiSkillReserveSetting
            .sha256,
        ).toBe(
          'e0de1600da056d1a6d380d5c40eae44e92b3fc7fea520621d8572c029a249a66',
        )

        expect(
          LOGRES_COMBAT_CONTENT_EVIDENCE
            .battleTexts
            .sha256,
        ).toBe(
          '02a8e0fc8ab62b3f4f5ec777f10ff1a027ce47b881f2087ce35bc207d17b5aa2',
        )

        expect(
          LOGRES_COMBAT_CONTENT_MANIFEST
            .globalBattleResourceFacts
            .multiSkillReserveTypes,
        ).toEqual({
          type1:
            0,
          type2:
            3,
          type3:
            5,
          type4:
            7,
        })

        expect(
          LOGRES_COMBAT_CONTENT_MANIFEST
            .globalBattleResourceFacts
            .enemyHpGaugeColor,
        ).toEqual([
          255,
          0,
          0,
        ])
      },
    )

    it(
      'is directly consumable by the existing battle runtime without invented special mechanics',
      () => {
        const input =
          createLogresTutorialCombatContentBattleKitInput()

        const kit =
          new LogresGlobalBattleKit(
            input,
          )

        const snapshot =
          kit.snapshot()

        expect(
          snapshot
            .selectedWeaponSlot,
        ).toBe(
          0,
        )

        expect(
          snapshot
            .weaponPanels[
              0
            ],
        ).toMatchObject({
          weaponRef:
            'reconstructed-tutorial-weapon',
          normalSkillRef:
            'reconstructed-normal-attack',
          specialSkillRef:
            null,
          specialEpCost:
            null,
        })

        expect(
          kit.createNormalAttack(),
        ).toEqual({
          type:
            'normal-attack',
          weaponSlot:
            0,
          weaponRef:
            'reconstructed-tutorial-weapon',
          skillRef:
            'reconstructed-normal-attack',
        })
      },
    )

    it(
      'never labels current-JP-only enemy presentation as confirmed historical Global content',
      () => {
        for (
          const enemy of
          LOGRES_ENEMY_CONTENT_MANIFEST
            .entries
        ) {
          if (
            enemy.presentation
              .currentJpResourcePath !==
            null
          ) {
            expect(
              enemy.presentation
                .presentationConfidence,
            ).not.toBe(
              'CONFIRMED_GLOBAL_3_0_24',
            )
          }
        }

        expect(
          LOGRES_COMBAT_CONTENT_MANIFEST
            .currentJpRole,
        ).toBe(
          'LINEAGE_REFERENCE_ONLY',
        )
      },
    )
  },
)
