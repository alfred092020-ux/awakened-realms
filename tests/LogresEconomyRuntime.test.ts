import { describe, expect, it } from 'vitest'
import {
  LOGRES_ECONOMY_EVIDENCE,
  LogresEconomyAuthority,
  createLogresEconomyRecipe,
  createLogresEconomyState,
  createLogresShopProduct,
} from '../src/game/logres/economy/LogresEconomyRuntime'

const product = createLogresShopProduct({
  productKey: 'shop-potion',
  originalProductId: null,
  cost: { currencyKey: 'gold', amount: 25 },
  rewardItemKey: 'potion',
  rewardQuantity: 1,
})
const enhancement = createLogresEconomyRecipe({
  recipeKey: 'enhance-sword',
  originalRecipeId: null,
  kind: 'ENHANCEMENT',
  cost: { currencyKey: 'gold', amount: 40 },
  requiredInputItemKey: 'sword',
  resultItemKey: 'sword-plus-one',
})
const craft = createLogresEconomyRecipe({
  recipeKey: 'craft-gem',
  originalRecipeId: null,
  kind: 'CRAFT',
  cost: { currencyKey: 'gold', amount: 10 },
  requiredInputItemKey: null,
  resultItemKey: 'gem',
})

function authority(balance = 100) {
  return new LogresEconomyAuthority(
    createLogresEconomyState({ gold: balance }),
    {
      products: { 'shop-potion': product },
      recipes: {
        'enhance-sword': enhancement,
        'craft-gem': craft,
      },
    },
  )
}

describe('Logres economy authority', () => {
  it('binds recovered buy/fusion authority but keeps catalog values reconstructed', () => {
    expect(LOGRES_ECONOMY_EVIDENCE.buyRequest.name)
      .toBe('C_GMCL_BUY_ITEM_REQ')
    expect(LOGRES_ECONOMY_EVIDENCE.fusionRequest.name)
      .toBe('C_GMCL_FUSION')
    expect(LOGRES_ECONOMY_EVIDENCE.parameterPolicy)
      .toContain('never guessed')
  })

  it('executes an explicit shop purchase atomically', () => {
    const runtime = authority()
    const state = runtime.purchase('shop-potion', 'purchase-1')
    expect(state.balances.gold).toBe(75)
    expect(state.operations).toEqual([
      expect.objectContaining({
        kind: 'PURCHASE',
        sourceKey: 'shop-potion',
        spent: 25,
        resultItemKey: 'potion',
      }),
    ])
  })

  it('keeps repeated commands idempotent', () => {
    const runtime = authority()
    const first = runtime.purchase('shop-potion', 'same-command')
    const repeated = runtime.purchase('shop-potion', 'same-command')
    expect(repeated).toEqual(first)
    expect(repeated.balances.gold).toBe(75)
    expect(repeated.revision).toBe(1)
  })

  it('does not partially mutate an unaffordable transaction', () => {
    const runtime = authority(20)
    const before = runtime.state
    expect(() => runtime.purchase('shop-potion', 'too-expensive'))
      .toThrow('insufficient authoritative balance')
    expect(runtime.state).toEqual(before)
  })

  it('supports explicit enhancement and crafting recipe boundaries', () => {
    const runtime = authority()
    const enhanced = runtime.applyRecipe('enhance-sword', 'sword', 'enhance-1')
    expect(enhanced.balances.gold).toBe(60)
    expect(enhanced.operations.at(-1)?.kind).toBe('ENHANCEMENT')
    const crafted = runtime.applyRecipe('craft-gem', null, 'craft-1')
    expect(crafted.balances.gold).toBe(50)
    expect(crafted.operations.at(-1)?.kind).toBe('CRAFT')
  })

  it('fails closed for unknown prices, recipes, and mismatched recipe inputs', () => {
    const runtime = authority()
    expect(() => runtime.purchase('missing', 'missing-buy'))
      .toThrow('refusing to invent historical price')
    expect(() => runtime.applyRecipe('missing', null, 'missing-recipe'))
      .toThrow('refusing to invent historical formula')
    expect(() => runtime.applyRecipe('enhance-sword', 'wrong', 'bad-input'))
      .toThrow('does not match explicit reconstructed recipe')
  })
})
