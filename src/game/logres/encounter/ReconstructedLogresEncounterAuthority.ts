import {
  LOGRES_GLOBAL_BATTLE_ENTRY_ACCEPTED_RESPONSE_CODE,
  LOGRES_GLOBAL_BATTLE_ENTRY_RETRY_RESPONSE_CODE,
  LOGRES_GLOBAL_BATTLE_ENTRY_RETRY_SECONDS,
} from './LogresGlobalEncounterNativeEvidence'

export const LOGRES_RECONSTRUCTED_ENCOUNTER_PROVENANCE =
  'RECONSTRUCTED' as const

export interface ReconstructedLogresMapPosition {
  x: number
  y: number
}

export interface ReconstructedLogresEncounterEligibility {
  globalEncounterAllowed: boolean
  encounterEnabled: boolean
  entryStateEligible: boolean
  questAllowsEncounter: boolean
  distanceEligible: boolean
}

export interface ReconstructedLogresBattleEntryIntent {
  provenance:
    typeof LOGRES_RECONSTRUCTED_ENCOUNTER_PROVENANCE
  encounterKey: string
  areaRef:
    | string
    | null
  symbolRef:
    | string
    | null
  mapPosition:
    | Readonly<ReconstructedLogresMapPosition>
    | null
  rawEntryState:
    | number
    | null
}

export interface ReconstructedLogresCollisionSymbolObservation {
  areaRef:
    | string
    | null
  symbolRef:
    | string
    | null
  mapPosition:
    | Readonly<ReconstructedLogresMapPosition>
    | null
}

export interface ReconstructedLogresPartyEncounterObservation {
  areaRef:
    | string
    | null
  symbolRef:
    | string
    | null
  mapPosition:
    | Readonly<ReconstructedLogresMapPosition>
    | null
  rawRangeOrRadius:
    | number
    | null
}

export interface ReconstructedLogresEncounterSnapshot {
  provenance:
    typeof LOGRES_RECONSTRUCTED_ENCOUNTER_PROVENANCE
  encounterKey: string
  areaRef:
    | string
    | null
  symbolRef:
    | string
    | null
  mapPosition:
    | Readonly<ReconstructedLogresMapPosition>
    | null
  rawEntryState:
    | number
    | null
  eligibility:
    Readonly<ReconstructedLogresEncounterEligibility>
  requestPending: boolean
  lastResponseCode:
    | number
    | null
  retryDelaySeconds:
    | number
    | null
  entryAccepted: boolean
  battleInitialized: boolean
  battleSystemRef:
    | string
    | null
  lastCollisionSymbol:
    | Readonly<ReconstructedLogresCollisionSymbolObservation>
    | null
  lastPartyEncounter:
    | Readonly<ReconstructedLogresPartyEncounterObservation>
    | null
}

function localKey(
  value: string,
): string {
  const normalized =
    value.trim()

  if (!normalized) {
    throw new Error(
      'Encounter key must be non-empty',
    )
  }

  return normalized
}

function optionalRef(
  value:
    | string
    | null,
  label: string,
): string | null {
  if (value === null) {
    return null
  }

  const normalized =
    value.trim()

  if (!normalized) {
    throw new Error(
      `${label} must be null or non-empty`,
    )
  }

  return normalized
}

function optionalSafeInteger(
  value:
    | number
    | null,
  label: string,
): number | null {
  if (value === null) {
    return null
  }

  if (
    !Number.isSafeInteger(
      value,
    )
  ) {
    throw new Error(
      `${label} must be null or a safe integer`,
    )
  }

  return value
}

function optionalNonNegativeFinite(
  value:
    | number
    | null,
  label: string,
): number | null {
  if (value === null) {
    return null
  }

  if (
    !Number.isFinite(
      value,
    ) ||
    value < 0
  ) {
    throw new Error(
      `${label} must be null or a non-negative finite number`,
    )
  }

  return value
}

function freezePosition(
  value:
    | ReconstructedLogresMapPosition
    | null,
): Readonly<ReconstructedLogresMapPosition> | null {
  if (value === null) {
    return null
  }

  if (
    !Number.isFinite(
      value.x,
    ) ||
    !Number.isFinite(
      value.y,
    )
  ) {
    throw new Error(
      'Encounter map position must contain finite coordinates',
    )
  }

  return Object.freeze({
    x:
      value.x,
    y:
      value.y,
  })
}

function freezeEligibility(
  value:
    ReconstructedLogresEncounterEligibility,
): Readonly<ReconstructedLogresEncounterEligibility> {
  return Object.freeze({
    globalEncounterAllowed:
      value.globalEncounterAllowed,
    encounterEnabled:
      value.encounterEnabled,
    entryStateEligible:
      value.entryStateEligible,
    questAllowsEncounter:
      value.questAllowsEncounter,
    distanceEligible:
      value.distanceEligible,
  })
}

export class ReconstructedLogresEncounterAuthority {
  private readonly encounterKey:
    string

  private areaRef:
    | string
    | null

  private symbolRef:
    | string
    | null

  private mapPosition:
    | Readonly<ReconstructedLogresMapPosition>
    | null

  private rawEntryState:
    | number
    | null

  private eligibility:
    Readonly<ReconstructedLogresEncounterEligibility>

  private requestPending =
    false

  private lastResponseCode:
    | number
    | null =
      null

  private retryDelaySeconds:
    | number
    | null =
      null

  private entryAccepted =
    false

  private battleInitialized =
    false

  private battleSystemRef:
    | string
    | null =
      null

  private lastCollisionSymbol:
    | Readonly<ReconstructedLogresCollisionSymbolObservation>
    | null =
      null

  private lastPartyEncounter:
    | Readonly<ReconstructedLogresPartyEncounterObservation>
    | null =
      null

  constructor(
    input: {
      encounterKey: string
      areaRef:
        | string
        | null
      symbolRef:
        | string
        | null
      mapPosition:
        | ReconstructedLogresMapPosition
        | null
      rawEntryState:
        | number
        | null
      eligibility:
        ReconstructedLogresEncounterEligibility
    },
  ) {
    this.encounterKey =
      localKey(
        input.encounterKey,
      )

    this.areaRef =
      optionalRef(
        input.areaRef,
        'Encounter areaRef',
      )

    this.symbolRef =
      optionalRef(
        input.symbolRef,
        'Encounter symbolRef',
      )

    this.mapPosition =
      freezePosition(
        input.mapPosition,
      )

    this.rawEntryState =
      optionalSafeInteger(
        input.rawEntryState,
        'Encounter rawEntryState',
      )

    this.eligibility =
      freezeEligibility(
        input.eligibility,
      )
  }

  updateEligibility(
    value:
      ReconstructedLogresEncounterEligibility,
  ): void {
    if (
      this.requestPending
    ) {
      throw new Error(
        'Cannot replace encounter eligibility while an entry request is pending',
      )
    }

    this.eligibility =
      freezeEligibility(
        value,
      )
  }

  updateIdentity(
    input: {
      areaRef:
        | string
        | null
      symbolRef:
        | string
        | null
      mapPosition:
        | ReconstructedLogresMapPosition
        | null
      rawEntryState:
        | number
        | null
    },
  ): void {
    if (
      this.requestPending
    ) {
      throw new Error(
        'Cannot replace encounter identity while an entry request is pending',
      )
    }

    this.areaRef =
      optionalRef(
        input.areaRef,
        'Encounter areaRef',
      )

    this.symbolRef =
      optionalRef(
        input.symbolRef,
        'Encounter symbolRef',
      )

    this.mapPosition =
      freezePosition(
        input.mapPosition,
      )

    this.rawEntryState =
      optionalSafeInteger(
        input.rawEntryState,
        'Encounter rawEntryState',
      )
  }

  createBattleEntryIntent():
    Readonly<ReconstructedLogresBattleEntryIntent> {
    if (
      this.battleInitialized
    ) {
      throw new Error(
        'Encounter already initialized a battle',
      )
    }

    if (
      this.requestPending
    ) {
      throw new Error(
        'Battle entry request is already pending',
      )
    }

    if (
      this.retryDelaySeconds !==
        null &&
      this.retryDelaySeconds >
        0
    ) {
      throw new Error(
        `Battle entry retry wait has not elapsed: ${this.retryDelaySeconds} seconds remaining`,
      )
    }

    if (
      this.entryAccepted
    ) {
      throw new Error(
        'Encounter battle entry was already accepted',
      )
    }

    const blockers =
      Object.entries(
        this.eligibility,
      )
        .filter(
          ([, allowed]) =>
            !allowed,
        )
        .map(
          ([key]) =>
            key,
        )

    if (
      blockers.length > 0
    ) {
      throw new Error(
        `Encounter is not eligible for battle entry: ${blockers.join(', ')}`,
      )
    }

    this.requestPending =
      true

    this.lastResponseCode =
      null

    this.retryDelaySeconds =
      null

    return Object.freeze({
      provenance:
        LOGRES_RECONSTRUCTED_ENCOUNTER_PROVENANCE,
      encounterKey:
        this.encounterKey,
      areaRef:
        this.areaRef,
      symbolRef:
        this.symbolRef,
      mapPosition:
        this.mapPosition,
      rawEntryState:
        this.rawEntryState,
    })
  }

  recordBattleEntryResponse(
    input: {
      rawCode: number
    },
  ): void {
    if (
      !this.requestPending
    ) {
      throw new Error(
        'No battle entry request is pending',
      )
    }

    this.requestPending =
      false

    const rawCode =
      optionalSafeInteger(
        input.rawCode,
        'Battle entry response code',
      )

    this.lastResponseCode =
      rawCode

    /*
     * CONFIRMED GLOBAL 3.0.24:
     * Encounter::receiveBattleEntryResponse writes 1.0f to its wait timer for
     * response code 2, and marks the separate local entry-accepted flag for
     * response code 1. Other response-code meanings remain unresolved here.
     *
     * The code-2 delay is intentionally not caller-configurable: the recovered
     * Global client writes exactly 1.0f, and allowing another duration here
     * would silently weaken the evidence-backed retry gate.
     */
    this.retryDelaySeconds =
      rawCode ===
        LOGRES_GLOBAL_BATTLE_ENTRY_RETRY_RESPONSE_CODE
        ? LOGRES_GLOBAL_BATTLE_ENTRY_RETRY_SECONDS
        : null

    if (
      rawCode ===
        LOGRES_GLOBAL_BATTLE_ENTRY_ACCEPTED_RESPONSE_CODE
    ) {
      this.entryAccepted =
        true
    }
  }

  elapseRetryDelay(
    elapsedSeconds:
      number,
  ): void {
    if (
      this.retryDelaySeconds ===
        null
    ) {
      throw new Error(
        'No battle entry retry wait is active',
      )
    }

    const elapsed =
      optionalNonNegativeFinite(
        elapsedSeconds,
        'Battle entry retry elapsed seconds',
      )

    if (
      elapsed !==
        this.retryDelaySeconds
    ) {
      throw new Error(
        `Battle entry retry wait requires exactly ${this.retryDelaySeconds} seconds`,
      )
    }

    this.retryDelaySeconds =
      null
  }

  markBattleInitialized(
    battleSystemRef:
      | string
      | null,
  ): void {
    this.requestPending =
      false

    this.retryDelaySeconds =
      null

    this.battleInitialized =
      true

    this.battleSystemRef =
      optionalRef(
        battleSystemRef,
        'Battle system ref',
      )
  }

  observeCollisionSymbol(
    input: {
      areaRef:
        | string
        | null
      symbolRef:
        | string
        | null
      mapPosition:
        | ReconstructedLogresMapPosition
        | null
    },
  ): void {
    this.lastCollisionSymbol =
      Object.freeze({
        areaRef:
          optionalRef(
            input.areaRef,
            'Collision areaRef',
          ),
        symbolRef:
          optionalRef(
            input.symbolRef,
            'Collision symbolRef',
          ),
        mapPosition:
          freezePosition(
            input.mapPosition,
          ),
      })
  }

  observePartyMemberEncounter(
    input: {
      areaRef:
        | string
        | null
      symbolRef:
        | string
        | null
      mapPosition:
        | ReconstructedLogresMapPosition
        | null
      rawRangeOrRadius:
        | number
        | null
    },
  ): void {
    this.lastPartyEncounter =
      Object.freeze({
        areaRef:
          optionalRef(
            input.areaRef,
            'Party encounter areaRef',
          ),
        symbolRef:
          optionalRef(
            input.symbolRef,
            'Party encounter symbolRef',
          ),
        mapPosition:
          freezePosition(
            input.mapPosition,
          ),
        rawRangeOrRadius:
          optionalNonNegativeFinite(
            input.rawRangeOrRadius,
            'Party encounter raw range/radius',
          ),
      })
  }

  snapshot():
    Readonly<ReconstructedLogresEncounterSnapshot> {
    return Object.freeze({
      provenance:
        LOGRES_RECONSTRUCTED_ENCOUNTER_PROVENANCE,
      encounterKey:
        this.encounterKey,
      areaRef:
        this.areaRef,
      symbolRef:
        this.symbolRef,
      mapPosition:
        this.mapPosition,
      rawEntryState:
        this.rawEntryState,
      eligibility:
        this.eligibility,
      requestPending:
        this.requestPending,
      lastResponseCode:
        this.lastResponseCode,
      retryDelaySeconds:
        this.retryDelaySeconds,
      entryAccepted:
        this.entryAccepted,
      battleInitialized:
        this.battleInitialized,
      battleSystemRef:
        this.battleSystemRef,
      lastCollisionSymbol:
        this.lastCollisionSymbol,
      lastPartyEncounter:
        this.lastPartyEncounter,
    })
  }
}
