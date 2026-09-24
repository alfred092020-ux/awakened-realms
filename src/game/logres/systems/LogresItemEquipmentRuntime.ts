import {
  applyReconstructedLogresInventoryGrant,
  createReconstructedLogresInventory,
  type ReconstructedLogresInventoryGrantInput,
  type ReconstructedLogresInventoryState,
} from '../server/LogresInventoryAuthority'
import {
  LOGRES_GLOBAL_3024_ITEMS,
  LOGRES_GLOBAL_3024_SYSTEMS_UNRESOLVED,
} from './LogresGlobal3024SystemsEvidence'

export const LOGRES_ITEM_EQUIPMENT_PROVENANCE =
  'RECONSTRUCTED_SERVER_AUTHORITY' as const

export interface LogresInventoryEntryRef {
  readonly grantKey: string
  readonly itemKey: string
}

export interface LogresItemEquipmentState {
  readonly provenance: typeof LOGRES_ITEM_EQUIPMENT_PROVENANCE
  readonly inventory: Readonly<ReconstructedLogresInventoryState>
  readonly equippedBySlot:
    Readonly<Record<string, Readonly<LogresInventoryEntryRef>>>
  readonly appliedCommandIds: readonly string[]
  readonly revision: number
}

export const LOGRES_ITEM_EQUIPMENT_EVIDENCE = Object.freeze({
  itemMoveRequest: LOGRES_GLOBAL_3024_ITEMS.requests.itemMove,
  itemProjection: LOGRES_GLOBAL_3024_ITEMS.serverProjection.itemInfo,
  itemBoxProjection: LOGRES_GLOBAL_3024_ITEMS.serverProjection.itemBoxInfo,
  keyClasses: LOGRES_GLOBAL_3024_ITEMS.keyClasses,
  authorityInterpretation: LOGRES_GLOBAL_3024_ITEMS.authorityInterpretation,
  unresolvedHistoricalItems:
    LOGRES_GLOBAL_3024_SYSTEMS_UNRESOLVED.filter(
      (value) => value.includes('historical item source payload corpus'),
    ),
  slotPolicy:
    'Equipment slot keys are reconstruction-local identifiers until original slot semantics are recovered.',
} as const)

function requireIdentity(value: string, label: string): string {
  const normalized = value.trim()
  if (!normalized) throw new Error(`${label} must be non-empty`)
  return normalized
}

function cloneState(state: LogresItemEquipmentState): LogresItemEquipmentState {
  const equipped:
    Record<string, Readonly<LogresInventoryEntryRef>> = {}
  for (const [slot, ref] of Object.entries(state.equippedBySlot)) {
    equipped[slot] = Object.freeze({ ...ref })
  }
  return Object.freeze({
    provenance: LOGRES_ITEM_EQUIPMENT_PROVENANCE,
    inventory: state.inventory,
    equippedBySlot: Object.freeze(equipped),
    appliedCommandIds: Object.freeze([...state.appliedCommandIds]),
    revision: state.revision,
  })
}

function inventoryHasRef(
  inventory: Readonly<ReconstructedLogresInventoryState>,
  ref: LogresInventoryEntryRef,
): boolean {
  return inventory.entries.some(
    (entry) =>
      entry.grantKey === ref.grantKey &&
      entry.itemKey === ref.itemKey,
  )
}

export function createLogresItemEquipmentState(): LogresItemEquipmentState {
  return cloneState({
    provenance: LOGRES_ITEM_EQUIPMENT_PROVENANCE,
    inventory: createReconstructedLogresInventory(),
    equippedBySlot: Object.freeze({}),
    appliedCommandIds: Object.freeze([]),
    revision: 0,
  })
}

export class LogresItemEquipmentAuthority {
  private stateValue: LogresItemEquipmentState

  constructor(
    initialState: LogresItemEquipmentState =
      createLogresItemEquipmentState(),
  ) {
    this.stateValue = cloneState(initialState)
  }

  get state(): LogresItemEquipmentState {
    return cloneState(this.stateValue)
  }

  applyReward(
    input: ReconstructedLogresInventoryGrantInput,
  ): LogresItemEquipmentState {
    const result =
      applyReconstructedLogresInventoryGrant(
        this.stateValue.inventory,
        input,
      )
    if (!result.applied) return this.state

    this.stateValue = cloneState({
      ...this.stateValue,
      inventory: result.state,
      revision: this.stateValue.revision + 1,
    })
    return this.state
  }

  equip(
    slotKey: string,
    ref: LogresInventoryEntryRef,
    commandId: string,
  ): LogresItemEquipmentState {
    const slot = requireIdentity(slotKey, 'Equipment slotKey')
    const command = requireIdentity(commandId, 'Equipment commandId')
    const normalizedRef = Object.freeze({
      grantKey: requireIdentity(ref.grantKey, 'Equipment grantKey'),
      itemKey: requireIdentity(ref.itemKey, 'Equipment itemKey'),
    })

    if (this.stateValue.appliedCommandIds.includes(command)) {
      return this.state
    }
    if (!inventoryHasRef(this.stateValue.inventory, normalizedRef)) {
      throw new Error('Equipment item reference must exist in authoritative inventory')
    }

    this.stateValue = cloneState({
      ...this.stateValue,
      equippedBySlot: Object.freeze({
        ...this.stateValue.equippedBySlot,
        [slot]: normalizedRef,
      }),
      appliedCommandIds: [
        ...this.stateValue.appliedCommandIds,
        command,
      ],
      revision: this.stateValue.revision + 1,
    })
    return this.state
  }

  unequip(
    slotKey: string,
    commandId: string,
  ): LogresItemEquipmentState {
    const slot = requireIdentity(slotKey, 'Equipment slotKey')
    const command = requireIdentity(commandId, 'Equipment commandId')

    if (this.stateValue.appliedCommandIds.includes(command)) {
      return this.state
    }

    const equipped = { ...this.stateValue.equippedBySlot }
    delete equipped[slot]
    this.stateValue = cloneState({
      ...this.stateValue,
      equippedBySlot: Object.freeze(equipped),
      appliedCommandIds: [
        ...this.stateValue.appliedCommandIds,
        command,
      ],
      revision: this.stateValue.revision + 1,
    })
    return this.state
  }
}
