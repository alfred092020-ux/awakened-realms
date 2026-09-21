import {
  WeaponBattleState,
  type BattleWeapon,
} from '../logres/battle/WeaponBattleState'

import {
  LOGRES_CLIENT_FACTS,
} from '../logres/generated/ExtractedClientFacts'

const DEVELOPMENT_WEAPONS: BattleWeapon[] = [
  {
    itemId: 'development-weapon-slot-1',
    skillId: 'development-skill-slot-1',
  },
]

export class EnergySystem {
  private readonly battleState:
    WeaponBattleState

  private readonly onChanged:
    () => void

  constructor(
    maximum = 100,
    _legacyRegenerationPerSecond = 0,
    onChanged: () => void = () => {},
    battleState?: WeaponBattleState,
  ) {
    this.battleState =
      battleState ??
      new WeaponBattleState(
        DEVELOPMENT_WEAPONS,
        maximum,
      )

    this.onChanged = onChanged
  }

  update(_delta: number) {
    /*
     * Logres client evidence confirms EP
     * recovers through attacks.
     *
     * Passive regeneration is intentionally
     * disabled.
     */
  }

  gainFromAttack(amount: number) {
    if (
      !LOGRES_CLIENT_FACTS
        .battle
        .epRecoversByAttack
    ) {
      return 0
    }

    const gained =
      this.battleState.gainEp(amount)

    if (gained > 0) {
      this.onChanged()
    }

    return gained
  }

  canSpend(amount: number) {
    return (
      this.battleState
        .getSnapshot()
        .ep >= amount
    )
  }

  spend(amount: number) {
    const spent =
      this.battleState
        .spendEp(amount)

    if (spent) {
      this.onChanged()
    }

    return spent
  }

  getEnergy() {
    return (
      this.battleState
        .getSnapshot()
        .ep
    )
  }

  getMaximum() {
    return (
      this.battleState
        .getSnapshot()
        .maxEp
    )
  }

  getBattleState() {
    return this.battleState
  }
}
