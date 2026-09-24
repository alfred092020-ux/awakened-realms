import type {
  LogresGlobalBattleKitInput,
} from '../../battle/LogresGlobalBattleKit'

export const LOGRES_COMBAT_CONTENT_SCHEMA_VERSION =
  'combat-content-v1' as const

export type LogresCombatContentConfidence =
  | 'CONFIRMED_GLOBAL_3_0_24'
  | 'SUPPORTED_INFERENCE'
  | 'CURRENT_JP_LINEAGE_REFERENCE_ONLY'
  | 'RECONSTRUCTED_PLAYABILITY'
  | 'UNKNOWN'

export const LOGRES_COMBAT_CONTENT_EVIDENCE =
  Object.freeze({
    nativeBattleAuthority:
      Object.freeze({
        path:
          '/home/ubuntu/logres/artifacts/global-3.0.24-battle-native-authority-20260924.json',
        sha256:
          'f2e11dbf5fce6732f39f84fd9a87c73f1318d8f6ed621b13651e09ca74356513',
        confidence:
          'CONFIRMED_GLOBAL_3_0_24',
      }),
    nativeBattleSurface:
      Object.freeze({
        path:
          '/home/ubuntu/logres/artifacts/global-3024-battle-native-surface-20260924.json',
        sha256:
          '3aa8b87730ac8c9ea896ee37aaf224654aab9f90eec812537e9fb5a4c1567716',
        confidence:
          'CONFIRMED_GLOBAL_3_0_24',
      }),
    resourceGraph:
      Object.freeze({
        path:
          '/home/ubuntu/logres/artifacts/global-jp-resource-semantic-graph-20260924.json',
        sha256:
          'fdd4921dbab864840c1106a5ff2196da2c57b29a5517eca0e4a603a1e1f25ab3',
        confidence:
          'CONFIRMED_GLOBAL_3_0_24',
      }),
    battleMultiSkillReserveSetting:
      Object.freeze({
        path:
          '/home/ubuntu/logres/private/global-apk/3.0.24/re/mbn-extracted/json_resource.mbn/battle_multi_skill_reserve_setting.json',
        sha256:
          'e0de1600da056d1a6d380d5c40eae44e92b3fc7fea520621d8572c029a249a66',
        confidence:
          'CONFIRMED_GLOBAL_3_0_24',
      }),
    battleTexts:
      Object.freeze({
        path:
          '/home/ubuntu/logres/private/global-apk/3.0.24/re/mbn-extracted/json_resource.mbn/battle_texts.json',
        sha256:
          '02a8e0fc8ab62b3f4f5ec777f10ff1a027ce47b881f2087ce35bc207d17b5aa2',
        confidence:
          'CONFIRMED_GLOBAL_3_0_24',
      }),
    boutCharacterViewSetting:
      Object.freeze({
        path:
          '/home/ubuntu/logres/private/global-apk/3.0.24/re/mbn-extracted/json_resource.mbn/bout_character_view_info_setting.json',
        sha256:
          'c48b074b3ffd56a1eb1c49ca498f55ec61ff27bacb0f6a120ace861dd616332c',
        confidence:
          'CONFIRMED_GLOBAL_3_0_24',
      }),
    exactBattlePackage:
      Object.freeze({
        resourceNode:
          'resource:global-cache:Battle.mbn',
        path:
          'Battle.mbn',
        sha256:
          '65b8cb1e49e91effe33d8cc934e35bbd08068b09c7443061d8aaeb67245606fc',
        lineage:
          'GLOBAL_JP_IDENTICAL',
        confidence:
          'CONFIRMED_GLOBAL_3_0_24',
      }),
  } as const)

export const LOGRES_ENEMY_CONTENT_MANIFEST =
  Object.freeze({
    version:
      LOGRES_COMBAT_CONTENT_SCHEMA_VERSION,
    entries:
      Object.freeze([
        Object.freeze({
          key:
            'tutorial-green-jell',
          displayName:
            'Green Jell',
          identityConfidence:
            'CONFIRMED_GLOBAL_3_0_24' as const,
          historicalInternalId:
            null,
          historicalShapeId:
            null,
          historicalBattlePosition:
            null,
          bossClassification:
            'UNKNOWN' as const,
          stats:
            Object.freeze({
              hp:
                null,
              attack:
                null,
              defense:
                null,
              element:
                null,
            }),
          presentation:
            Object.freeze({
              runtimeArtRef:
                'enm_001_000_000_green_jell_reference',
              currentJpResourcePath:
                'avatar/enm_001_000_000.mbn',
              currentJpResourceSha1:
                '21123af65e10563820bea001b1981a7d427477f8',
              currentJpResourceSize:
                28437,
              currentJpResourceTimestamp:
                1519646916,
              presentationConfidence:
                'CURRENT_JP_LINEAGE_REFERENCE_ONLY' as const,
              historicalGlobalVisualApplication:
                'SUPPORTED_INFERENCE' as const,
            }),
          evidenceIds:
            Object.freeze([
              'global-tutorial:green-jell-behavior',
              'global-battle:bout-character-appearance-surface',
              'resource:jp-current:avatar/enm_001_000_000.mbn',
            ] as const),
        }),
      ] as const),
    evidenceCeilings:
      Object.freeze([
        'Historical Global enemy stat tables are not present in the recovered bootstrap evidence.',
        'Green Jell historical Global internal enemy/shape ID remains unresolved.',
        'Current-JP enm_001_000_000 presentation bytes are lineage reference only, not confirmed historical Global artwork.',
      ] as const),
  } as const)

export const LOGRES_BOSS_CONTENT_MANIFEST =
  Object.freeze({
    version:
      LOGRES_COMBAT_CONTENT_SCHEMA_VERSION,
    entries:
      Object.freeze([] as const),
    coverage:
      Object.freeze({
        status:
          'EXPLICIT_EVIDENCE_CEILING' as const,
        confidence:
          'UNKNOWN' as const,
        reason:
          'No concrete historical Global boss ID/name/stat tuple is recoverable from the current first-party Global 3.0.24 client/bootstrap corpus.',
        doNotInfer:
          Object.freeze([
            'Do not classify Green Jell as a boss.',
            'Do not promote current-JP enemy packages into historical Global boss entries.',
            'Do not invent boss HP, damage, defense, element, skills, drops, or encounter placement.',
          ] as const),
      }),
  } as const)

export type LogresCombatSkillEntry = Readonly<{
  key: string
  kind:
    | 'PLAYABLE_RECONSTRUCTION'
    | 'GLOBAL_SCHEMA_CAPABILITY'
  runtimeSkillRef:
    string | null
  historicalSkillUid:
    string | null
  confidence:
    LogresCombatContentConfidence
  mechanics: Readonly<{
    damageFormula: string | null
    cooldownSeconds: number | null
    recastSeconds: number | null
    epCost: number | null
    targetRule: string | null
  }>
  evidenceIds:
    readonly string[]
}>

const UNKNOWN_SKILL_MECHANICS =
  Object.freeze({
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
  } as const)

export const LOGRES_SKILL_CONTENT_MANIFEST =
  Object.freeze({
    version:
      LOGRES_COMBAT_CONTENT_SCHEMA_VERSION,
    entries:
      Object.freeze([
        Object.freeze({
          key:
            'tutorial-reconstructed-normal-attack',
          kind:
            'PLAYABLE_RECONSTRUCTION',
          runtimeSkillRef:
            'reconstructed-normal-attack',
          historicalSkillUid:
            null,
          confidence:
            'RECONSTRUCTED_PLAYABILITY',
          mechanics:
            UNKNOWN_SKILL_MECHANICS,
          evidenceIds:
            Object.freeze([
              'runtime:LogresFieldEncounterController',
              'runtime:LogresGlobalBattleKit',
            ]),
        } satisfies LogresCombatSkillEntry),
      ] as const),
    schemaCapabilities:
      Object.freeze([
        Object.freeze({
          key:
            'global-command-skill-intent',
          kind:
            'GLOBAL_SCHEMA_CAPABILITY',
          runtimeSkillRef:
            null,
          historicalSkillUid:
            null,
          confidence:
            'CONFIRMED_GLOBAL_3_0_24',
          mechanics:
            UNKNOWN_SKILL_MECHANICS,
          evidenceIds:
            Object.freeze([
              'lfs::BattleSystem::requestToUseCommandSkill',
              'C_GMCL_BATTLE_USE_SKILL_REQ_Response',
              'S_GMCL_BATTLE_BOUT_EVENT_EXECUTE_SKILL',
            ]),
        } satisfies LogresCombatSkillEntry),
        Object.freeze({
          key:
            'global-charge-recast-skill-events',
          kind:
            'GLOBAL_SCHEMA_CAPABILITY',
          runtimeSkillRef:
            null,
          historicalSkillUid:
            null,
          confidence:
            'CONFIRMED_GLOBAL_3_0_24',
          mechanics:
            UNKNOWN_SKILL_MECHANICS,
          evidenceIds:
            Object.freeze([
              'CHARGE_SKILL',
              'FAILED_CHARGE',
              'RECAST_SKILL',
              'RESET_RECAST_SKILL',
              'SEAL_SKILL',
            ]),
        } satisfies LogresCombatSkillEntry),
        Object.freeze({
          key:
            'global-reaction-skill-events',
          kind:
            'GLOBAL_SCHEMA_CAPABILITY',
          runtimeSkillRef:
            null,
          historicalSkillUid:
            null,
          confidence:
            'CONFIRMED_GLOBAL_3_0_24',
          mechanics:
            UNKNOWN_SKILL_MECHANICS,
          evidenceIds:
            Object.freeze([
              'SELECT_REACTION_SKILL',
              'EXECUTE_REACTION_SKILL',
              'C_GMCL_BATTLE_USE_REACTION_SKILL_REQ_Response',
            ]),
        } satisfies LogresCombatSkillEntry),
      ] as const),
    evidenceCeilings:
      Object.freeze([
        'Concrete historical SkillUID-to-name/content tables were not recovered from the Global bootstrap corpus.',
        'Server-side damage formulas are unresolved.',
        'Exact cooldown/recast values are unresolved.',
        'Exact EP arithmetic/caps for every skill are unresolved.',
      ] as const),
  } as const)

export const LOGRES_TUTORIAL_RECONSTRUCTED_WEAPON_ENTRY =
  Object.freeze({
    key:
      'tutorial-reconstructed-weapon',
    runtimeWeaponRef:
      'reconstructed-tutorial-weapon',
    historicalItemUid:
      null,
    confidence:
      'RECONSTRUCTED_PLAYABILITY' as const,
    normalSkillKey:
      'tutorial-reconstructed-normal-attack',
    specialSkillKey:
      null,
  } as const)

function requirePlayableSkill(
  key: string,
): LogresCombatSkillEntry {
  const entry =
    LOGRES_SKILL_CONTENT_MANIFEST
      .entries
      .find(
        value =>
          value.key ===
          key,
      )

  if (
    !entry ||
    entry.confidence !==
      'RECONSTRUCTED_PLAYABILITY' ||
    entry.runtimeSkillRef ===
      null
  ) {
    throw new Error(
      'Combat-content skill is not a playable reconstructed entry: ' +
      key,
    )
  }

  return entry
}

export function createLogresTutorialCombatContentBattleKitInput():
  LogresGlobalBattleKitInput {
  const normalSkill =
    requirePlayableSkill(
      LOGRES_TUTORIAL_RECONSTRUCTED_WEAPON_ENTRY
        .normalSkillKey,
    )

  return {
    weaponPanels: [
      {
        unlocked:
          true,
        weaponRef:
          LOGRES_TUTORIAL_RECONSTRUCTED_WEAPON_ENTRY
            .runtimeWeaponRef,
        normalSkillRef:
          normalSkill.runtimeSkillRef,
        specialSkillRef:
          null,
        specialEpCost:
          null,
      },
    ],
    selectedWeaponSlot:
      0,
    currentEp:
      0,
    epCap:
      null,
  }
}

export const LOGRES_COMBAT_CONTENT_MANIFEST =
  Object.freeze({
    schemaVersion:
      LOGRES_COMBAT_CONTENT_SCHEMA_VERSION,
    clientVersion:
      '3.0.24' as const,
    historicalAuthority:
      'GLOBAL_3_0_24_CLIENT_AND_BOOTSTRAP' as const,
    currentJpRole:
      'LINEAGE_REFERENCE_ONLY' as const,
    enemies:
      LOGRES_ENEMY_CONTENT_MANIFEST,
    bosses:
      LOGRES_BOSS_CONTENT_MANIFEST,
    skills:
      LOGRES_SKILL_CONTENT_MANIFEST,
    reconstructedTutorialWeapon:
      LOGRES_TUTORIAL_RECONSTRUCTED_WEAPON_ENTRY,
    evidence:
      LOGRES_COMBAT_CONTENT_EVIDENCE,
    globalBattleResourceFacts:
      Object.freeze({
        exactBattlePackage:
          Object.freeze({
            path:
              'Battle.mbn',
            sha256:
              '65b8cb1e49e91effe33d8cc934e35bbd08068b09c7443061d8aaeb67245606fc',
            lineage:
              'GLOBAL_JP_IDENTICAL' as const,
          }),
        bootstrapSkillUiMembers:
          Object.freeze([
            Object.freeze({
              entry:
                'skill01_parts01.png',
              sha256:
                'd80fa79f2312d66be67f198eaf44c2f8b934d661b43e5df493c35a685db45514',
            }),
            Object.freeze({
              entry:
                'skill02_parts01.png',
              sha256:
                '624fb541b6f729085e5785ad26fbe245608569b82497ad62faee44947f2a4490',
            }),
            Object.freeze({
              entry:
                'skill_base.png',
              sha256:
                '5b7b7a0ad0ff7cce6fd581a0b404f3030b8129fba710c5ecfa0bb22c438845b7',
            }),
          ] as const),
        multiSkillReserveTypes:
          Object.freeze({
            type1:
              0,
            type2:
              3,
            type3:
              5,
            type4:
              7,
          } as const),
        enemyHpGaugeColor:
          Object.freeze([
            255,
            0,
            0,
          ] as const),
      }),
  } as const)
