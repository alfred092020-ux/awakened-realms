import {
  LOGRES_GLOBAL_3024_ECONOMY,
  LOGRES_GLOBAL_3024_ITEMS,
  LOGRES_GLOBAL_3024_SYSTEMS_UNRESOLVED,
} from '../systems/LogresGlobal3024SystemsEvidence'

export const LOGRES_ECONOMY_PROVENANCE =
  'RECONSTRUCTED_SERVER_AUTHORITY' as const
export const LOGRES_ECONOMY_PARAMETER_PROVENANCE =
  'RECONSTRUCTED_EXPLICIT_PARAMETER' as const

export interface LogresEconomyCost {
  readonly currencyKey: string
  readonly amount: number
}

export interface LogresShopProduct {
  readonly provenance: typeof LOGRES_ECONOMY_PARAMETER_PROVENANCE
  readonly productKey: string
  readonly originalProductId: string | null
  readonly cost: LogresEconomyCost
  readonly rewardItemKey: string
  readonly rewardQuantity: number
}

export type LogresRecipeKind = 'ENHANCEMENT' | 'CRAFT'

export interface LogresEconomyRecipe {
  readonly provenance: typeof LOGRES_ECONOMY_PARAMETER_PROVENANCE
  readonly recipeKey: string
  readonly originalRecipeId: string | null
  readonly kind: LogresRecipeKind
  readonly cost: LogresEconomyCost
  readonly requiredInputItemKey: string | null
  readonly resultItemKey: string
}

export interface LogresEconomyParameters {
  readonly products: Readonly<Record<string, LogresShopProduct>>
  readonly recipes: Readonly<Record<string, LogresEconomyRecipe>>
}

export interface LogresEconomyOperation {
  readonly commandId: string
  readonly kind: 'PURCHASE' | LogresRecipeKind
  readonly sourceKey: string
  readonly currencyKey: string
  readonly spent: number
  readonly resultItemKey: string
  readonly resultQuantity: number
}

export interface LogresEconomyState {
  readonly provenance: typeof LOGRES_ECONOMY_PROVENANCE
  readonly balances: Readonly<Record<string, number>>
  readonly operations: readonly LogresEconomyOperation[]
  readonly appliedCommandIds: readonly string[]
  readonly revision: number
}

export const LOGRES_ECONOMY_EVIDENCE = Object.freeze({
  buyRequest: LOGRES_GLOBAL_3024_ITEMS.requests.buy,
  sellRequest: LOGRES_GLOBAL_3024_ITEMS.requests.sell,
  fusionRequest: LOGRES_GLOBAL_3024_ITEMS.requests.fusion,
  evolutionGraphRequest: LOGRES_GLOBAL_3024_ITEMS.requests.evolutionGraph,
  gachaDraw: LOGRES_GLOBAL_3024_ECONOMY.gacha.draw,
  authorityInterpretation: LOGRES_GLOBAL_3024_ECONOMY.authorityInterpretation,
  unresolvedCatalog:
    LOGRES_GLOBAL_3024_SYSTEMS_UNRESOLVED.filter(
      (value) => value.includes('historical production catalog contents'),
    ),
  parameterPolicy:
    'Historical prices, recipe costs and formulas are never guessed; all executable economy data must be supplied as explicit reconstructed parameters.',
} as const)

function requireIdentity(value: string, label: string): string {
  const normalized = value.trim()
  if (!normalized) throw new Error(`${label} must be non-empty`)
  return normalized
}

function requireAmount(value: number, label: string, allowZero = false): number {
  if (!Number.isSafeInteger(value) || value < 0 || (!allowZero && value === 0)) {
    throw new Error(`${label} must be a ${allowZero ? 'non-negative' : 'positive'} safe integer`)
  }
  return value
}

function optionalId(value: string | null, label: string): string | null {
  return value === null ? null : requireIdentity(value, label)
}

export function createLogresShopProduct(
  input: Omit<LogresShopProduct, 'provenance'>,
): LogresShopProduct {
  return Object.freeze({
    provenance: LOGRES_ECONOMY_PARAMETER_PROVENANCE,
    productKey: requireIdentity(input.productKey, 'Economy productKey'),
    originalProductId: optionalId(input.originalProductId, 'Economy originalProductId'),
    cost: Object.freeze({
      currencyKey: requireIdentity(input.cost.currencyKey, 'Economy currencyKey'),
      amount: requireAmount(input.cost.amount, 'Economy price'),
    }),
    rewardItemKey: requireIdentity(input.rewardItemKey, 'Economy rewardItemKey'),
    rewardQuantity: requireAmount(input.rewardQuantity, 'Economy rewardQuantity'),
  })
}

export function createLogresEconomyRecipe(
  input: Omit<LogresEconomyRecipe, 'provenance'>,
): LogresEconomyRecipe {
  return Object.freeze({
    provenance: LOGRES_ECONOMY_PARAMETER_PROVENANCE,
    recipeKey: requireIdentity(input.recipeKey, 'Economy recipeKey'),
    originalRecipeId: optionalId(input.originalRecipeId, 'Economy originalRecipeId'),
    kind: input.kind,
    cost: Object.freeze({
      currencyKey: requireIdentity(input.cost.currencyKey, 'Economy currencyKey'),
      amount: requireAmount(input.cost.amount, 'Economy recipe cost'),
    }),
    requiredInputItemKey:
      input.requiredInputItemKey === null
        ? null
        : requireIdentity(input.requiredInputItemKey, 'Economy requiredInputItemKey'),
    resultItemKey: requireIdentity(input.resultItemKey, 'Economy resultItemKey'),
  })
}

function cloneState(state: LogresEconomyState): LogresEconomyState {
  return Object.freeze({
    provenance: LOGRES_ECONOMY_PROVENANCE,
    balances: Object.freeze({ ...state.balances }),
    operations: Object.freeze(
      state.operations.map((operation) => Object.freeze({ ...operation })),
    ),
    appliedCommandIds: Object.freeze([...state.appliedCommandIds]),
    revision: state.revision,
  })
}

export function createLogresEconomyState(
  balances: Readonly<Record<string, number>>,
): LogresEconomyState {
  const normalized: Record<string, number> = {}
  for (const [rawKey, value] of Object.entries(balances)) {
    normalized[requireIdentity(rawKey, 'Economy currencyKey')] =
      requireAmount(value, 'Economy balance', true)
  }
  return cloneState({
    provenance: LOGRES_ECONOMY_PROVENANCE,
    balances: Object.freeze(normalized),
    operations: Object.freeze([]),
    appliedCommandIds: Object.freeze([]),
    revision: 0,
  })
}

export class LogresEconomyAuthority {
  private stateValue: LogresEconomyState
  private readonly parameters: LogresEconomyParameters

  constructor(
    state: LogresEconomyState,
    parameters: LogresEconomyParameters,
  ) {
    this.stateValue = cloneState(state)
    this.parameters = parameters
  }

  get state(): LogresEconomyState {
    return cloneState(this.stateValue)
  }

  private commit(
    commandId: string,
    kind: LogresEconomyOperation['kind'],
    sourceKey: string,
    cost: LogresEconomyCost,
    resultItemKey: string,
    resultQuantity: number,
  ): LogresEconomyState {
    const command = requireIdentity(commandId, 'Economy commandId')
    if (this.stateValue.appliedCommandIds.includes(command)) return this.state

    const balance = this.stateValue.balances[cost.currencyKey] ?? 0
    if (balance < cost.amount) {
      throw new Error('Economy transaction has insufficient authoritative balance')
    }

    const nextBalances = {
      ...this.stateValue.balances,
      [cost.currencyKey]: balance - cost.amount,
    }
    const operation = Object.freeze({
      commandId: command,
      kind,
      sourceKey,
      currencyKey: cost.currencyKey,
      spent: cost.amount,
      resultItemKey,
      resultQuantity,
    })

    this.stateValue = cloneState({
      ...this.stateValue,
      balances: Object.freeze(nextBalances),
      operations: [...this.stateValue.operations, operation],
      appliedCommandIds: [...this.stateValue.appliedCommandIds, command],
      revision: this.stateValue.revision + 1,
    })
    return this.state
  }

  purchase(productKey: string, commandId: string): LogresEconomyState {
    const key = requireIdentity(productKey, 'Economy productKey')
    const product = this.parameters.products[key]
    if (!product) {
      throw new Error('Economy product data is unresolved; refusing to invent historical price')
    }
    return this.commit(
      commandId,
      'PURCHASE',
      key,
      product.cost,
      product.rewardItemKey,
      product.rewardQuantity,
    )
  }

  applyRecipe(
    recipeKey: string,
    inputItemKey: string | null,
    commandId: string,
  ): LogresEconomyState {
    const key = requireIdentity(recipeKey, 'Economy recipeKey')
    const recipe = this.parameters.recipes[key]
    if (!recipe) {
      throw new Error('Economy recipe data is unresolved; refusing to invent historical formula')
    }
    const actualInput =
      inputItemKey === null ? null : requireIdentity(inputItemKey, 'Economy inputItemKey')
    if (recipe.requiredInputItemKey !== actualInput) {
      throw new Error('Economy recipe input does not match explicit reconstructed recipe')
    }
    return this.commit(
      commandId,
      recipe.kind,
      key,
      recipe.cost,
      recipe.resultItemKey,
      1,
    )
  }
}
