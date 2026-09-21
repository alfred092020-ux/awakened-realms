export const MAX_ACTIVE_WEAPONS = 5

export interface BattleWeapon {
  itemId: string
  skillId: string
}

export interface WeaponBattleSnapshot {
  weapons: BattleWeapon[]
  activeWeaponIndex: number
  ep: number
  maxEp: number
}

export class WeaponBattleState {
  private readonly weapons:
    BattleWeapon[]

  private activeWeaponIndex = 0
  private ep = 0
  private readonly maxEp: number

  constructor(
    weapons: BattleWeapon[],
    maxEp = 10,
  ) {
    if (
      weapons.length < 1 ||
      weapons.length >
        MAX_ACTIVE_WEAPONS
    ) {
      throw new Error(
        `Battle loadout requires 1-${MAX_ACTIVE_WEAPONS} weapons.`,
      )
    }

    this.weapons =
      weapons.map(
        (weapon) => ({
          ...weapon,
        }),
      )

    this.maxEp =
      Math.max(
        1,
        Math.floor(maxEp),
      )
  }

  getActiveWeapon() {
    return (
      this.weapons[
        this.activeWeaponIndex
      ]
    )
  }

  switchWeapon(index: number) {
    if (
      index < 0 ||
      index >=
        this.weapons.length
    ) {
      return false
    }

    this.activeWeaponIndex =
      index

    return true
  }

  gainEp(amount: number) {
    if (amount <= 0) {
      return 0
    }

    const before =
      this.ep

    this.ep =
      Math.min(
        this.maxEp,
        this.ep +
          Math.floor(amount),
      )

    return this.ep - before
  }

  spendEp(amount: number) {
    const cost =
      Math.floor(amount)

    if (
      cost < 0 ||
      this.ep < cost
    ) {
      return false
    }

    this.ep -= cost

    return true
  }

  getSnapshot():
    WeaponBattleSnapshot {
    return {
      weapons:
        this.weapons.map(
          (weapon) => ({
            ...weapon,
          }),
        ),

      activeWeaponIndex:
        this.activeWeaponIndex,

      ep:
        this.ep,

      maxEp:
        this.maxEp,
    }
  }
}
