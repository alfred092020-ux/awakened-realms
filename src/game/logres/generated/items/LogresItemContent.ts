import {
  LOGRES_PLAYABLE_BATTLE_REWARD_ITEM_KEY,
} from '../../battle/ReconstructedLogresPlayableBattleLoop'
import {
  LOGRES_GLOBAL_3024_ITEMS,
  LOGRES_GLOBAL_3024_SYSTEMS_UNRESOLVED,
} from '../../systems/LogresGlobal3024SystemsEvidence'

export const LOGRES_ITEM_CONTENT_SCHEMA_VERSION =
  'item-content-v1' as const

export const LOGRES_ITEM_CONTENT_EVIDENCE = Object.freeze({
  itemInfoProjection:
    LOGRES_GLOBAL_3024_ITEMS.serverProjection.itemInfo,
  itemBoxProjection:
    LOGRES_GLOBAL_3024_ITEMS.serverProjection.itemBoxInfo,
  itemMoveRequest:
    LOGRES_GLOBAL_3024_ITEMS.requests.itemMove,
  itemUseRequest:
    LOGRES_GLOBAL_3024_ITEMS.requests.itemUse,
  equipmentClasses:
    LOGRES_GLOBAL_3024_ITEMS.keyClasses,
  authorityInterpretation:
    LOGRES_GLOBAL_3024_ITEMS.authorityInterpretation,
  unresolvedHistoricalItemCorpus:
    LOGRES_GLOBAL_3024_SYSTEMS_UNRESOLVED.filter(
      (value) => value.includes('historical item source payload corpus'),
    ),
} as const)

const UNKNOWN_ITEM_FIELDS = Object.freeze({
  historicalItemId: null,
  displayName: null,
  rarity: null,
  itemType: null,
  equipmentSlot: null,
  attack: null,
  defense: null,
  element: null,
  effect: null,
} as const)

export const LOGRES_ITEM_CONTENT_MANIFEST = Object.freeze({
  schemaVersion: LOGRES_ITEM_CONTENT_SCHEMA_VERSION,
  entries: Object.freeze([
    Object.freeze({
      key: LOGRES_PLAYABLE_BATTLE_REWARD_ITEM_KEY,
      kind: 'RECONSTRUCTED_REWARD_ITEM' as const,
      confidence: 'RECONSTRUCTED_PLAYABILITY' as const,
      runtimeItemKey: LOGRES_PLAYABLE_BATTLE_REWARD_ITEM_KEY,
      ...UNKNOWN_ITEM_FIELDS,
      evidenceIds: Object.freeze([
        'runtime:ReconstructedLogresPlayableBattleLoop',
        'protocol:S_GMCL_ITEM_INFO',
        'protocol:S_GMCL_ITEM_BOX_INFO',
      ] as const),
    }),
  ] as const),
  evidenceCeilings: Object.freeze([
    'The recovered Global corpus confirms item/inventory/equipment protocol surfaces but not the historical production item catalog.',
    'The playable tutorial reward item is reconstruction-local and must not be assigned an original item ID, name, rarity, stats or effect without primary evidence.',
  ] as const),
} as const)

export const LOGRES_EQUIPMENT_CONTENT_MANIFEST = Object.freeze({
  schemaVersion: LOGRES_ITEM_CONTENT_SCHEMA_VERSION,
  entries: Object.freeze([] as const),
  schemaCapabilities: Object.freeze([
    Object.freeze({
      key: 'global-equipment-selection-surface',
      kind: 'GLOBAL_SCHEMA_CAPABILITY' as const,
      confidence: 'CONFIRMED_GLOBAL_3_0_24' as const,
      runtimeItemKey: null,
      historicalItemId: null,
      classNames: Object.freeze([
        'SelectEquipment',
        'ChangeEquipment',
        'EquipmentBoardList',
        'EquipmentDetailWindow',
      ] as const),
      evidenceIds: Object.freeze([
        'class:SelectEquipment',
        'class:ChangeEquipment',
        'class:EquipmentBoardList',
        'class:EquipmentDetailWindow',
      ] as const),
    }),
    Object.freeze({
      key: 'global-item-move-equipment-boundary',
      kind: 'GLOBAL_SCHEMA_CAPABILITY' as const,
      confidence: 'CONFIRMED_GLOBAL_3_0_24' as const,
      runtimeItemKey: null,
      historicalItemId: null,
      requestMessage:
        LOGRES_GLOBAL_3024_ITEMS.requests.itemMove.name,
      evidenceIds: Object.freeze([
        'protocol:C_GMCL_ITEM_MOVE_REQ',
        'type:t_ItemMoveParam',
      ] as const),
    }),
  ] as const),
  coverage: Object.freeze({
    status: 'EXPLICIT_EVIDENCE_CEILING' as const,
    reason:
      'No concrete historical Global equipment item ID/name/stat tuple is recovered yet; schema capabilities are represented without fabricating equipment content.',
  }),
} as const)
