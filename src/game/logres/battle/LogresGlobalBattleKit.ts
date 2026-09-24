import {
  LOGRES_CLIENT_FACTS,
} from '../generated/ExtractedClientFacts'

export const LOGRES_GLOBAL_WEAPON_SLOT_LIMIT =
  5 as const

export const LOGRES_GLOBAL_NORMAL_SKILL_SLOT_COUNT =
  LOGRES_CLIENT_FACTS
    .equipment
    .normalSkillSlots

export const LOGRES_GLOBAL_BATTLE_KIT_PROVENANCE =
  Object.freeze({
    weaponSlotLimit:
      'SUPPORTED_INFERENCE_GLOBAL_2017',
    normalSkillSlotCount:
      'CONFIRMED_ORIGINAL_GLOBAL_CLIENT',
    weaponPanelBehavior:
      'CONFIRMED_ORIGINAL_OFFICIAL_HELP',
    epRecovery:
      'CONFIRMED_ORIGINAL_GLOBAL_TUTORIAL',
  } as const)

export const LOGRES_RECONSTRUCTED_PLAYABILITY_FALLBACK_PROVENANCE =
  'RECONSTRUCTED_PLAYABILITY_FALLBACK' as const

export interface LogresGlobalWeaponPanelInput {
  unlocked: boolean
  weaponRef: string | null
  normalSkillRef: string | null
  specialSkillRef: string | null
  specialEpCost: number | null
}

export interface LogresGlobalWeaponPanel
  extends LogresGlobalWeaponPanelInput {
  slotIndex: number
}

type EquippedLogresGlobalWeaponPanel =
  Readonly<
    LogresGlobalWeaponPanel & {
      weaponRef: string
    }
  >

export interface LogresGlobalBattleKitInput {
  weaponPanels:
    readonly LogresGlobalWeaponPanelInput[]
  selectedWeaponSlot:
    number | null
  currentEp: number
  epCap: number | null
}

export interface LogresGlobalBattleKitSnapshot {
  provenance:
    typeof LOGRES_GLOBAL_BATTLE_KIT_PROVENANCE
  weaponSlotLimit:
    typeof LOGRES_GLOBAL_WEAPON_SLOT_LIMIT
  normalSkillSlotCount: number
  weaponPanels:
    readonly Readonly<LogresGlobalWeaponPanel>[]
  selectedWeaponSlot:
    number | null
  currentEp: number
  epCap: number | null
}
export interface LogresNormalAttackCommand {
  type: 'normal-attack'
  weaponSlot: number
  weaponRef: string
  skillRef: string
}

export interface LogresSpecialSkillCommand {
  type: 'special-skill'
  weaponSlot: number
  weaponRef: string
  skillRef: string
  epCost: number
}

function requireOptionalRef(
  value: string | null,
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
function requireNonNegativeInteger(
  value: number,
  label: string,
): number {
  if (
    !Number.isSafeInteger(
      value,
    ) ||
    value < 0
  ) {
    throw new Error(
      `${label} must be a non-negative safe integer`,
    )
  }

  return value
}

function normalizePanel(
  input: LogresGlobalWeaponPanelInput,
  slotIndex: number,
): Readonly<LogresGlobalWeaponPanel> {
  const weaponRef =
    requireOptionalRef(
      input.weaponRef,
      'Weapon ref',
    )
  const normalSkillRef =
    requireOptionalRef(
      input.normalSkillRef,
      'Normal skill ref',
    )
  const specialSkillRef =
    requireOptionalRef(
      input.specialSkillRef,
      'Special skill ref',
    )

  const specialEpCost =
    input.specialEpCost === null
      ? null
      : requireNonNegativeInteger(
          input.specialEpCost,
          'Special EP cost',
        )

  if (
    !input.unlocked &&
    (
      weaponRef !== null ||
      normalSkillRef !== null ||
      specialSkillRef !== null ||
      specialEpCost !== null
    )
  ) {
    throw new Error(
      'Locked weapon slots cannot contain battle data',
    )
  }

  if (
    weaponRef === null &&
    (
      normalSkillRef !== null ||
      specialSkillRef !== null ||
      specialEpCost !== null
    )
  ) {
    throw new Error(
      'Weapon skills require an equipped weapon',
    )
  }

  if (
    specialSkillRef === null &&
    specialEpCost !== null
  ) {
    throw new Error(
      'Special EP cost requires a special skill',
    )
  }

  return Object.freeze({
    slotIndex,
    unlocked:
      input.unlocked,
    weaponRef,
    normalSkillRef,
    specialSkillRef,
    specialEpCost,
  })
}

function emptyLockedPanel(
  slotIndex: number,
): Readonly<LogresGlobalWeaponPanel> {
  return Object.freeze({
    slotIndex,
    unlocked: false,
    weaponRef: null,
    normalSkillRef: null,
    specialSkillRef: null,
    specialEpCost: null,
  })
}
export class LogresGlobalBattleKit {
  private readonly weaponPanels:
    readonly Readonly<LogresGlobalWeaponPanel>[]
  private selectedWeaponSlot:
    number | null
  private currentEp: number
  private readonly epCap:
    number | null

  constructor(
    input: LogresGlobalBattleKitInput,
  ) {
    if (
      input.weaponPanels.length >
      LOGRES_GLOBAL_WEAPON_SLOT_LIMIT
    ) {
      throw new Error(
        'Global battle kit supports at most five weapon slots',
      )
    }

    const panels =
      Array.from(
        {
          length:
            LOGRES_GLOBAL_WEAPON_SLOT_LIMIT,
        },
        (_, slotIndex) => {
          const panel =
            input.weaponPanels[
              slotIndex
            ]

          return panel
            ? normalizePanel(
                panel,
                slotIndex,
              )
            : emptyLockedPanel(
                slotIndex,
              )
        },
      )
    this.weaponPanels =
      Object.freeze(
        panels,
      )

    this.currentEp =
      requireNonNegativeInteger(
        input.currentEp,
        'Current EP',
      )

    this.epCap =
      input.epCap === null
        ? null
        : requireNonNegativeInteger(
            input.epCap,
            'EP cap',
          )

    if (
      this.epCap !== null &&
      this.currentEp >
        this.epCap
    ) {
      throw new Error(
        'Current EP cannot exceed EP cap',
      )
    }

    this.selectedWeaponSlot =
      input.selectedWeaponSlot

    if (
      this.selectedWeaponSlot !==
      null
    ) {
      this.requireEquippedWeapon(
        this.selectedWeaponSlot,
      )
    }
  }
  snapshot():
    Readonly<LogresGlobalBattleKitSnapshot> {
    return Object.freeze({
      provenance:
        LOGRES_GLOBAL_BATTLE_KIT_PROVENANCE,
      weaponSlotLimit:
        LOGRES_GLOBAL_WEAPON_SLOT_LIMIT,
      normalSkillSlotCount:
        LOGRES_GLOBAL_NORMAL_SKILL_SLOT_COUNT,
      weaponPanels:
        this.weaponPanels,
      selectedWeaponSlot:
        this.selectedWeaponSlot,
      currentEp:
        this.currentEp,
      epCap:
        this.epCap,
    })
  }

  slideWeaponMarkerTo(
    slotIndex: number,
  ): void {
    this.requireEquippedWeapon(
      slotIndex,
    )

    this.selectedWeaponSlot =
      slotIndex
  }

  createNormalAttack():
    Readonly<LogresNormalAttackCommand> {
    if (
      this.selectedWeaponSlot ===
      null
    ) {
      throw new Error(
        'No weapon is selected for normal attack',
      )
    }
    const panel =
      this.requireEquippedWeapon(
        this.selectedWeaponSlot,
      )

    if (
      panel.normalSkillRef ===
      null
    ) {
      throw new Error(
        'Selected weapon has no resolved normal skill',
      )
    }

    return Object.freeze({
      type:
        'normal-attack',
      weaponSlot:
        panel.slotIndex,
      weaponRef:
        panel.weaponRef,
      skillRef:
        panel.normalSkillRef,
    })
  }

  tapWeaponPanel(
    slotIndex: number,
  ):
    | Readonly<LogresSpecialSkillCommand>
    | Readonly<LogresNormalAttackCommand> {
    const panel =
      this.requireEquippedWeapon(
        slotIndex,
      )

    if (
      panel.specialSkillRef ===
      null ||
      panel.specialEpCost ===
      null
    ) {
      if (panel.normalSkillRef === null) {
        throw new Error(
          'Weapon special and normal skills are unresolved',
        )
      }

      return this.createNormalAttackForSlot(slotIndex)
    }

    if (
      this.currentEp <
      panel.specialEpCost
    ) {
      throw new Error(
        'Not enough EP for weapon special skill',
      )
    }

    /*
     * A panel tap is client intent only.
     *
     * Do not spend EP here. The historical server remains
     * authoritative for accepted skill execution and resource
     * state. This projection only checks whether the current
     * observed EP is sufficient to offer the action.
     */
    return Object.freeze({
      type:
        'special-skill',
      weaponSlot:
        panel.slotIndex,
      weaponRef:
        panel.weaponRef,
      skillRef:
        panel.specialSkillRef,
      epCost:
        panel.specialEpCost,
    })
  }

  createNormalAttackForSlot(
    slotIndex: number,
  ):
    Readonly<LogresNormalAttackCommand> {
    const panel =
      this.requireEquippedWeapon(
        slotIndex,
      )

    if (
      panel.normalSkillRef ===
      null
    ) {
      throw new Error(
        'Selected weapon has no resolved normal skill',
      )
    }

    return Object.freeze({
      type:
        'normal-attack',
      weaponSlot:
        panel.slotIndex,
      weaponRef:
        panel.weaponRef,
      skillRef:
        panel.normalSkillRef,
    })
  }

  recordNormalAttackHit(
    epGain: number,
  ): number {
    const gain =
      requireNonNegativeInteger(
        epGain,
        'Normal attack EP gain',
      )
    const next =
      this.currentEp +
      gain

    this.currentEp =
      this.epCap === null
        ? next
        : Math.min(
            next,
            this.epCap,
          )

    return this.currentEp
  }

  private requireEquippedWeapon(
    slotIndex: number,
  ): EquippedLogresGlobalWeaponPanel {
    if (
      !Number.isSafeInteger(
        slotIndex,
      ) ||
      slotIndex < 0 ||
      slotIndex >=
        LOGRES_GLOBAL_WEAPON_SLOT_LIMIT
    ) {
      throw new Error(
        'Weapon slot index is out of range',
      )
    }

    const panel =
      this.weaponPanels[
        slotIndex
      ]

    if (
      !panel ||
      !panel.unlocked ||
      panel.weaponRef ===
        null
    ) {
      throw new Error(
        'Weapon slot is not equipped',
      )
    }

    return panel as
      EquippedLogresGlobalWeaponPanel
  }
}
