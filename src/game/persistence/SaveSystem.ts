import type { PlayerStats } from '../combat/CombatStats'

interface SavedPlayerProgress {
  version: 1
  level: number
  xp: number
  xpToNext: number
  maxHp: number
  attack: number
  coins: number
}

export class SaveSystem {
  private readonly storageKey =
    'awakened-realms.player-progress.v1'

  load(
    fallback: PlayerStats,
  ): PlayerStats {
    try {
      const raw = localStorage.getItem(
        this.storageKey,
      )

      if (!raw) {
        return { ...fallback }
      }

      const parsed: unknown =
        JSON.parse(raw)

      if (!this.isValidSave(parsed)) {
        return { ...fallback }
      }

      return {
        level: parsed.level,
        xp: parsed.xp,
        xpToNext: parsed.xpToNext,
        hp: parsed.maxHp,
        maxHp: parsed.maxHp,
        attack: parsed.attack,
        coins: parsed.coins,
      }
    } catch {
      return { ...fallback }
    }
  }

  save(stats: PlayerStats) {
    const progress: SavedPlayerProgress = {
      version: 1,
      level: stats.level,
      xp: stats.xp,
      xpToNext: stats.xpToNext,
      maxHp: stats.maxHp,
      attack: stats.attack,
      coins: stats.coins,
    }

    try {
      localStorage.setItem(
        this.storageKey,
        JSON.stringify(progress),
      )

      return true
    } catch {
      return false
    }
  }

  clear() {
    try {
      localStorage.removeItem(
        this.storageKey,
      )

      return true
    } catch {
      return false
    }
  }

  private isValidSave(
    value: unknown,
  ): value is SavedPlayerProgress {
    if (
      typeof value !== 'object' ||
      value === null
    ) {
      return false
    }

    const save =
      value as Partial<SavedPlayerProgress>

    return (
      save.version === 1 &&
      this.isValidNumber(save.level, 1) &&
      this.isValidNumber(save.xp, 0) &&
      this.isValidNumber(
        save.xpToNext,
        1,
      ) &&
      this.isValidNumber(
        save.maxHp,
        1,
      ) &&
      this.isValidNumber(
        save.attack,
        1,
      ) &&
      this.isValidNumber(
        save.coins,
        0,
      )
    )
  }

  private isValidNumber(
    value: unknown,
    minimum: number,
  ) {
    return (
      typeof value === 'number' &&
      Number.isFinite(value) &&
      value >= minimum
    )
  }
}
