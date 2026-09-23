import {
  LogresGlobalBattleKit,
  type LogresGlobalBattleKitInput,
} from '../battle/LogresGlobalBattleKit'

import {
  ReconstructedLogresEncounterAuthority,
  type ReconstructedLogresBattleEntryIntent,
} from './ReconstructedLogresEncounterAuthority'

export const LOGRES_RECONSTRUCTED_BATTLE_ENTRY_BRIDGE_PROVENANCE =
  'RECONSTRUCTED' as const

export const LOGRES_BATTLE_SCENE_KEY =
  'LogresBattleScene' as const

export type ReconstructedLogresBattleEntryPhase =
  | 'field'
  | 'entry-requested'
  | 'entry-response-received'
  | 'battle-ready'

export interface ReconstructedLogresBattleLaunch {
  provenance:
    typeof LOGRES_RECONSTRUCTED_BATTLE_ENTRY_BRIDGE_PROVENANCE
  sceneKey:
    typeof LOGRES_BATTLE_SCENE_KEY
  battleSystemRef:
    | string
    | null
  sceneData:
    Readonly<LogresGlobalBattleKitInput>
}

function freezeSceneData(
  input: LogresGlobalBattleKitInput,
): Readonly<LogresGlobalBattleKitInput> {
  const validated =
    new LogresGlobalBattleKit(
      input,
    )
      .snapshot()

  return Object.freeze({
    weaponPanels:
      Object.freeze(
        validated.weaponPanels.map(
          (panel) =>
            Object.freeze({
              unlocked:
                panel.unlocked,
              weaponRef:
                panel.weaponRef,
              normalSkillRef:
                panel.normalSkillRef,
              specialSkillRef:
                panel.specialSkillRef,
              specialEpCost:
                panel.specialEpCost,
            }),
        ),
      ),
    selectedWeaponSlot:
      validated.selectedWeaponSlot,
    currentEp:
      validated.currentEp,
    epCap:
      validated.epCap,
  })
}

/**
 * Map-independent field encounter -> battle scene handoff.
 *
 * RECONSTRUCTED boundary:
 * - BattleEntry_Response is recorded but never treated as battle start.
 * - Authoritative battle initialization is what makes the client battle-ready.
 * - Original area/symbol/map identities remain owned by encounter authority.
 * - Weapon/EP data is supplied explicitly; unresolved historical values are
 *   never synthesized here.
 */
export class ReconstructedLogresBattleEntryBridge {
  private phase:
    ReconstructedLogresBattleEntryPhase =
      'field'

  private launch:
    Readonly<ReconstructedLogresBattleLaunch> | null =
      null

  private readonly encounter:
    ReconstructedLogresEncounterAuthority

  constructor(
    encounter:
      ReconstructedLogresEncounterAuthority,
  ) {
    this.encounter =
      encounter
  }

  requestEntry():
    Readonly<ReconstructedLogresBattleEntryIntent> {
    if (
      this.phase !==
      'field'
    ) {
      throw new Error(
        'Battle entry bridge is not in field phase',
      )
    }

    const intent =
      this.encounter
        .createBattleEntryIntent()

    this.phase =
      'entry-requested'

    return intent
  }

  recordEntryResponse(
    input: {
      rawCode: number
      retryDelaySeconds?:
        | number
        | null
    },
  ): void {
    if (
      this.phase !==
      'entry-requested'
    ) {
      throw new Error(
        'Battle entry response arrived without a pending bridge request',
      )
    }

    this.encounter
      .recordBattleEntryResponse(
        input,
      )

    this.phase =
      'entry-response-received'
  }

  recordBattleInitialized(
    input: {
      battleSystemRef:
        | string
        | null
      battleKit:
        LogresGlobalBattleKitInput
    },
  ): Readonly<ReconstructedLogresBattleLaunch> {
    if (
      this.phase !==
        'entry-requested' &&
      this.phase !==
        'entry-response-received'
    ) {
      throw new Error(
        'Battle initialization requires a prior entry request',
      )
    }

    /*
     * Validate and freeze the battle kit before mutating encounter state so a
     * malformed battle payload cannot partially initialize the encounter.
     */
    const sceneData =
      freezeSceneData(
        input.battleKit,
      )

    this.encounter
      .markBattleInitialized(
        input.battleSystemRef,
      )

    this.launch =
      Object.freeze({
        provenance:
          LOGRES_RECONSTRUCTED_BATTLE_ENTRY_BRIDGE_PROVENANCE,
        sceneKey:
          LOGRES_BATTLE_SCENE_KEY,
        battleSystemRef:
          input.battleSystemRef,
        sceneData,
      })

    this.phase =
      'battle-ready'

    return this.launch
  }

  snapshot():
    Readonly<{
      provenance:
        typeof LOGRES_RECONSTRUCTED_BATTLE_ENTRY_BRIDGE_PROVENANCE
      phase:
        ReconstructedLogresBattleEntryPhase
      launch:
        Readonly<ReconstructedLogresBattleLaunch> | null
    }> {
    return Object.freeze({
      provenance:
        LOGRES_RECONSTRUCTED_BATTLE_ENTRY_BRIDGE_PROVENANCE,
      phase:
        this.phase,
      launch:
        this.launch,
    })
  }
}
