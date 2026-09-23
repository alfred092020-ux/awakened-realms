import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_GLOBAL_BATTLE_KIT_PROVENANCE,
  LOGRES_GLOBAL_NORMAL_SKILL_SLOT_COUNT,
  LOGRES_GLOBAL_WEAPON_SLOT_LIMIT,
  LogresGlobalBattleKit,
  type LogresGlobalWeaponPanelInput,
} from '../src/game/logres/battle/LogresGlobalBattleKit'

function weapon(
  weaponRef: string,
  normalSkillRef: string,
  specialSkillRef: string,
  specialEpCost: number,
): LogresGlobalWeaponPanelInput {
  return {
    unlocked: true,
    weaponRef,
    normalSkillRef,
    specialSkillRef,
    specialEpCost,
  }
}

describe(
  'Global Logres five-weapon battle kit',
  () => {
    it(
      'keeps five weapon panels separate from the three normal-skill setting',
      () => {
        const kit =
          new LogresGlobalBattleKit({
            weaponPanels: [
              weapon('w1', 'n1', 's1', 3),
            ],
            selectedWeaponSlot: 0,
            currentEp: 0,
            epCap: null,
          })

        expect(
          kit.snapshot(),
        ).toMatchObject({
          provenance:
            LOGRES_GLOBAL_BATTLE_KIT_PROVENANCE,
          weaponSlotLimit: 5,
          normalSkillSlotCount: 3,
          selectedWeaponSlot: 0,
        })

        expect(
          LOGRES_GLOBAL_WEAPON_SLOT_LIMIT,
        ).toBe(5)

        expect(
          LOGRES_GLOBAL_NORMAL_SKILL_SLOT_COUNT,
        ).toBe(3)

        expect(
          kit.snapshot().weaponPanels,
        ).toHaveLength(5)
      },
    )

    it(
      'uses the sword-marker slide selection for the normal attack weapon',
      () => {
        const kit =
          new LogresGlobalBattleKit({
            weaponPanels: [
              weapon('w1', 'n1', 's1', 3),
              weapon('w2', 'n2', 's2', 4),
            ],
            selectedWeaponSlot: 0,
            currentEp: 10,
            epCap: null,
          })

        expect(
          kit.createNormalAttack(),
        ).toEqual({
          type: 'normal-attack',
          weaponSlot: 0,
          weaponRef: 'w1',
          skillRef: 'n1',
        })

        kit.slideWeaponMarkerTo(1)

        expect(
          kit.createNormalAttack(),
        ).toEqual({
          type: 'normal-attack',
          weaponSlot: 1,
          weaponRef: 'w2',
          skillRef: 'n2',
        })
      },
    )

    it(
      'taps a weapon panel for its EP special without changing the selected normal weapon',
      () => {
        const kit =
          new LogresGlobalBattleKit({
            weaponPanels: [
              weapon('w1', 'n1', 's1', 3),
              weapon('w2', 'n2', 's2', 4),
            ],
            selectedWeaponSlot: 0,
            currentEp: 10,
            epCap: null,
          })

        expect(
          kit.tapWeaponPanel(1),
        ).toEqual({
          type: 'special-skill',
          weaponSlot: 1,
          weaponRef: 'w2',
          skillRef: 's2',
          epCost: 4,
        })

        /*
         * Tapping emits client intent. It must not mutate
         * the projected EP balance before server acceptance.
         */
        expect(
          kit.snapshot().currentEp,
        ).toBe(10)

        expect(
          kit.snapshot().selectedWeaponSlot,
        ).toBe(0)
      },
    )

    it(
      'recovers EP on normal-attack hit without inventing a fixed recovery amount',
      () => {
        const kit =
          new LogresGlobalBattleKit({
            weaponPanels: [
              weapon('w1', 'n1', 's1', 3),
            ],
            selectedWeaponSlot: 0,
            currentEp: 2,
            epCap: 10,
          })

        expect(
          kit.recordNormalAttackHit(3),
        ).toBe(5)

        expect(
          kit.recordNormalAttackHit(20),
        ).toBe(10)
      },
    )

    it(
      'keeps unresolved special cost unusable instead of inventing a value',
      () => {
        const kit =
          new LogresGlobalBattleKit({
            weaponPanels: [
              {
                unlocked: true,
                weaponRef: 'w1',
                normalSkillRef: 'n1',
                specialSkillRef: 's1',
                specialEpCost: null,
              },
            ],
            selectedWeaponSlot: 0,
            currentEp: 10,
            epCap: null,
          })

        expect(
          () => kit.tapWeaponPanel(0),
        ).toThrow(
          'Weapon special skill is unresolved',
        )
      },
    )

    it(
      'rejects locked, over-capacity, and insufficient-EP actions',
      () => {
        expect(
          () =>
            new LogresGlobalBattleKit({
              weaponPanels: Array.from(
                { length: 6 },
                (_, index) =>
                  weapon(
                    `w${index}`,
                    `n${index}`,
                    `s${index}`,
                    1,
                  ),
              ),
              selectedWeaponSlot: 0,
              currentEp: 0,
              epCap: null,
            }),
        ).toThrow(
          'at most five weapon slots',
        )

        const kit =
          new LogresGlobalBattleKit({
            weaponPanels: [
              weapon('w1', 'n1', 's1', 5),
            ],
            selectedWeaponSlot: 0,
            currentEp: 4,
            epCap: null,
          })

        expect(
          () => kit.tapWeaponPanel(0),
        ).toThrow(
          'Not enough EP',
        )

        expect(
          () => kit.slideWeaponMarkerTo(4),
        ).toThrow(
          'Weapon slot is not equipped',
        )
      },
    )
  },
)
