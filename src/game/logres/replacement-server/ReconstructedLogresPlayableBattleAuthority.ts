import type {
  LogresNormalAttackCommand,
  LogresSpecialSkillCommand,
} from '../battle/LogresGlobalBattleKit'

export const LOGRES_PLAYABLE_BATTLE_AUTHORITY_PROVENANCE =
  'RECONSTRUCTED_SERVER_AUTHORITY_STUB' as const

/*
 * RECONSTRUCTED replacement-server battle rule.
 *
 * Global evidence proves the client request/projection boundaries, battle
 * initialization/result sequencing, and server ownership of the ordered battle
 * event stream. It does not recover the retired production damage formula,
 * tutorial enemy HP, or authoritative result decision.
 *
 * Demo 0.2 therefore resolves the tutorial enemy after three distinct accepted
 * client commands. This is a reconstruction-local playability rule, not a
 * historical Global combat formula.
 */
export const LOGRES_PLAYABLE_BATTLE_COMMANDS_TO_VICTORY =
  3 as const

export type ReconstructedLogresPlayableBattleCommand =
  | Readonly<LogresNormalAttackCommand>
  | Readonly<LogresSpecialSkillCommand>

export type ReconstructedLogresPlayableBattlePhase =
  | 'active'
  | 'victory-ready'

export interface ReconstructedLogresPlayableBattleAuthoritySnapshot {
  provenance:
    typeof LOGRES_PLAYABLE_BATTLE_AUTHORITY_PROVENANCE
  phase:
    ReconstructedLogresPlayableBattlePhase
  acceptedCommandCount: number
  acceptedCommandIds:
    readonly string[]
  victoryThreshold:
    typeof LOGRES_PLAYABLE_BATTLE_COMMANDS_TO_VICTORY
  historicalDamageFormulaRecovered:
    false
  historicalEnemyHpRecovered:
    false
  resultAuthority:
    'RECONSTRUCTED'
}

export interface ReconstructedLogresPlayableBattleCommandResult {
  provenance:
    typeof LOGRES_PLAYABLE_BATTLE_AUTHORITY_PROVENANCE
  accepted: true
  duplicate: boolean
  commandId: string
  outcome:
    | 'continue'
    | 'victory'
  snapshot:
    Readonly<ReconstructedLogresPlayableBattleAuthoritySnapshot>
}

function requireNonEmpty(
  value: string,
  label: string,
): string {
  const normalized =
    value.trim()

  if (!normalized) {
    throw new Error(
      `${label} must be non-empty`,
    )
  }

  return normalized
}

function requireSlot(
  value: number,
): number {
  if (
    !Number.isSafeInteger(
      value,
    ) ||
    value < 0 ||
    value > 4
  ) {
    throw new Error(
      'Playable battle command weaponSlot must be an integer from 0 through 4',
    )
  }

  return value
}

function validateCommand(
  command:
    ReconstructedLogresPlayableBattleCommand,
): void {
  requireSlot(
    command.weaponSlot,
  )

  requireNonEmpty(
    command.weaponRef,
    'Playable battle command weaponRef',
  )

  requireNonEmpty(
    command.skillRef,
    'Playable battle command skillRef',
  )

  if (
    command.type ===
    'special-skill'
  ) {
    if (
      !Number.isSafeInteger(
        command.epCost,
      ) ||
      command.epCost < 0
    ) {
      throw new Error(
        'Playable battle special epCost must be a non-negative safe integer',
      )
    }
  } else if (
    command.type !==
    'normal-attack'
  ) {
    const unreachable:
      never =
        command

    throw new Error(
      `Unsupported playable battle command: ${String(
        unreachable,
      )}`,
    )
  }
}

function freezeSnapshot(
  phase:
    ReconstructedLogresPlayableBattlePhase,
  acceptedCommandIds:
    readonly string[],
): Readonly<ReconstructedLogresPlayableBattleAuthoritySnapshot> {
  return Object.freeze({
    provenance:
      LOGRES_PLAYABLE_BATTLE_AUTHORITY_PROVENANCE,
    phase,
    acceptedCommandCount:
      acceptedCommandIds.length,
    acceptedCommandIds:
      Object.freeze([
        ...acceptedCommandIds,
      ]),
    victoryThreshold:
      LOGRES_PLAYABLE_BATTLE_COMMANDS_TO_VICTORY,
    historicalDamageFormulaRecovered:
      false as const,
    historicalEnemyHpRecovered:
      false as const,
    resultAuthority:
      'RECONSTRUCTED' as const,
  })
}

export class ReconstructedLogresPlayableBattleAuthority {
  private phase:
    ReconstructedLogresPlayableBattlePhase =
      'active'

  private readonly acceptedCommandIds:
    string[] = []

  submitCommand(
    input: {
      commandId: string
      command:
        ReconstructedLogresPlayableBattleCommand
    },
  ): ReconstructedLogresPlayableBattleCommandResult {
    const commandId =
      requireNonEmpty(
        input.commandId,
        'Playable battle commandId',
      )

    validateCommand(
      input.command,
    )

    if (
      this.acceptedCommandIds
        .includes(
          commandId,
        )
    ) {
      return Object.freeze({
        provenance:
          LOGRES_PLAYABLE_BATTLE_AUTHORITY_PROVENANCE,
        accepted:
          true as const,
        duplicate:
          true,
        commandId,
        outcome:
          this.phase ===
            'victory-ready'
            ? 'victory'
            : 'continue',
        snapshot:
          this.snapshot(),
      })
    }

    if (
      this.phase !==
      'active'
    ) {
      throw new Error(
        'Playable battle is already resolved',
      )
    }

    this.acceptedCommandIds
      .push(
        commandId,
      )

    if (
      this.acceptedCommandIds
        .length >=
      LOGRES_PLAYABLE_BATTLE_COMMANDS_TO_VICTORY
    ) {
      this.phase =
        'victory-ready'
    }

    return Object.freeze({
      provenance:
        LOGRES_PLAYABLE_BATTLE_AUTHORITY_PROVENANCE,
      accepted:
        true as const,
      duplicate:
        false,
      commandId,
      outcome:
        this.phase ===
          'victory-ready'
          ? 'victory'
          : 'continue',
      snapshot:
        this.snapshot(),
    })
  }

  snapshot():
    Readonly<ReconstructedLogresPlayableBattleAuthoritySnapshot> {
    return freezeSnapshot(
      this.phase,
      this.acceptedCommandIds,
    )
  }
}
