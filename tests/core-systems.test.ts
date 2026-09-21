import {
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from 'vitest'

import {
  createStartingStats,
} from '../src/game/combat/CombatStats'

import {
  CriticalHitSystem,
} from '../src/game/combat/CriticalHitSystem'

import {
  EnergySystem,
} from '../src/game/combat/EnergySystem'

import {
  InventorySystem,
} from '../src/game/inventory/InventorySystem'

import {
  ConsumableSystem,
} from '../src/game/inventory/ConsumableSystem'

import {
  EquipmentSystem,
} from '../src/game/inventory/EquipmentSystem'

import {
  LootTableSystem,
} from '../src/game/loot/LootTableSystem'

import {
  SaveSystem,
} from '../src/game/persistence/SaveSystem'

describe(
  'Awakened Realms core systems',
  () => {
    beforeEach(() => {
      localStorage.clear()
    })

    describe(
      'InventorySystem',
      () => {
        it(
          'stacks items and respects inventory capacity',
          () => {
            const inventory =
              new InventorySystem(
                [],
                2,
              )

            const added =
              inventory.addItem(
                'slime-gel',
                120,
              )

            expect(added)
              .toBe(120)

            expect(
              inventory.countItem(
                'slime-gel',
              ),
            ).toBe(120)

            expect(
              inventory.getUsedSlots(),
            ).toBe(2)

            expect(
              inventory.addItem(
                'minor-potion',
                1,
              ),
            ).toBe(0)
          },
        )

        it(
          'removes inventory quantities correctly',
          () => {
            const inventory =
              new InventorySystem()

            inventory.addItem(
              'slime-gel',
              10,
            )

            expect(
              inventory.removeItem(
                'slime-gel',
                4,
              ),
            ).toBe(4)

            expect(
              inventory.countItem(
                'slime-gel',
              ),
            ).toBe(6)
          },
        )
      },
    )

    describe(
      'ConsumableSystem',
      () => {
        it(
          'heals the player and consumes one potion',
          () => {
            const inventory =
              new InventorySystem()

            inventory.addItem(
              'minor-potion',
              1,
            )

            const stats =
              createStartingStats()

            stats.hp = 50

            const system =
              new ConsumableSystem()

            const result =
              system.use(
                'minor-potion',
                inventory,
                stats,
              )

            expect(result.used)
              .toBe(true)

            expect(stats.hp)
              .toBe(95)

            expect(
              inventory.countItem(
                'minor-potion',
              ),
            ).toBe(0)
          },
        )

        it(
          'does not consume a potion at full HP',
          () => {
            const inventory =
              new InventorySystem()

            inventory.addItem(
              'minor-potion',
              1,
            )

            const stats =
              createStartingStats()

            const system =
              new ConsumableSystem()

            const result =
              system.use(
                'minor-potion',
                inventory,
                stats,
              )

            expect(result.used)
              .toBe(false)

            expect(
              inventory.countItem(
                'minor-potion',
              ),
            ).toBe(1)
          },
        )
      },
    )

    describe(
      'EquipmentSystem',
      () => {
        it(
          'applies and removes equipment bonuses without changing base stats',
          () => {
            const inventory =
              new InventorySystem()

            inventory.addItem(
              'novice-blade',
              1,
            )

            const stats =
              createStartingStats()

            const equipment =
              new EquipmentSystem()

            const equipped =
              equipment.equip(
                'novice-blade',
                inventory,
                stats,
              )

            expect(
              equipped.changed,
            ).toBe(true)

            expect(
              stats.attack,
            ).toBe(32)

            expect(
              equipment.getBaseStats(
                stats,
              ).attack,
            ).toBe(26)

            const removed =
              equipment.unequip(
                'weapon',
                inventory,
                stats,
              )

            expect(
              removed.changed,
            ).toBe(true)

            expect(
              stats.attack,
            ).toBe(26)

            expect(
              inventory.countItem(
                'novice-blade',
              ),
            ).toBe(1)
          },
        )
      },
    )

    describe(
      'CriticalHitSystem',
      () => {
        it(
          'produces critical damage when the roll succeeds',
          () => {
            vi.spyOn(
              Math,
              'random',
            ).mockReturnValue(
              0.1,
            )

            const result =
              CriticalHitSystem.roll(
                100,
              )

            expect(
              result.critical,
            ).toBe(true)

            expect(
              result.damage,
            ).toBe(175)
          },
        )

        it(
          'produces normal damage when the roll fails',
          () => {
            vi.spyOn(
              Math,
              'random',
            ).mockReturnValue(
              0.9,
            )

            const result =
              CriticalHitSystem.roll(
                100,
              )

            expect(
              result.critical,
            ).toBe(false)

            expect(
              result.damage,
            ).toBe(100)
          },
        )
      },
    )

    describe(
      'EnergySystem',
      () => {
        it(
          'gains EP from attacks and does not regenerate passively',
          () => {
            const changed =
              vi.fn()

            const energy =
              new EnergySystem(
                100,
                0,
                changed,
              )

            expect(
              energy.getEnergy(),
            ).toBe(0)

            energy.update(
              1000,
            )

            expect(
              energy.getEnergy(),
            ).toBe(0)

            expect(
              energy.gainFromAttack(50),
            ).toBe(50)

            expect(
              energy.getEnergy(),
            ).toBe(50)

            expect(
              energy.spend(45),
            ).toBe(true)

            expect(
              energy.getEnergy(),
            ).toBe(5)

            expect(
              changed,
            ).toHaveBeenCalled()
          },
        )
      },
    )

    describe(
      'LootTableSystem',
      () => {
        it(
          'returns deterministic loot when randomness is controlled',
          () => {
            vi.spyOn(
              Math,
              'random',
            ).mockReturnValue(
              0,
            )

            const loot =
              new LootTableSystem()

            const drops =
              loot.roll([
                {
                  itemId:
                    'slime-gel',

                  chance:
                    1,

                  minQuantity:
                    2,

                  maxQuantity:
                    2,
                },
              ])

            expect(drops)
              .toEqual([
                {
                  itemId:
                    'slime-gel',

                  quantity:
                    2,
                },
              ])
          },
        )
      },
    )

    describe(
      'SaveSystem',
      () => {
        it(
          'persists progression, inventory, and equipment',
          () => {
            const save =
              new SaveSystem()

            const stats =
              createStartingStats()

            stats.level = 4
            stats.xp = 37
            stats.maxHp = 180
            stats.hp = 25
            stats.attack = 41
            stats.coins = 999

            save.save(
              stats,
              [
                {
                  itemId:
                    'minor-potion',

                  quantity:
                    5,
                },
              ],
              {
                weapon:
                  'novice-blade',
              },
            )

            const loaded =
              save.load(
                createStartingStats(),
              )

            expect(
              loaded.level,
            ).toBe(4)

            expect(
              loaded.xp,
            ).toBe(37)

            expect(
              loaded.maxHp,
            ).toBe(180)

            expect(
              loaded.hp,
            ).toBe(180)

            expect(
              loaded.attack,
            ).toBe(41)

            expect(
              loaded.coins,
            ).toBe(999)

            expect(
              save.loadInventory(),
            ).toEqual([
              {
                itemId:
                  'minor-potion',

                quantity:
                  5,
              },
            ])

            expect(
              save.loadEquipment(),
            ).toEqual({
              weapon:
                'novice-blade',
            })
          },
        )
      },
    )
  },
)
