export interface DamageResult {
  damage: number
  critical: boolean
}

export class CriticalHitSystem {
  static roll(
    baseDamage: number,
    criticalChance = 0.15,
    criticalMultiplier = 1.75,
  ): DamageResult {
    const critical =
      Math.random() < criticalChance

    return {
      damage: Math.round(
        baseDamage *
          (critical
            ? criticalMultiplier
            : 1),
      ),
      critical,
    }
  }
}
