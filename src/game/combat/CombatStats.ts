export interface PlayerStats {
  level: number
  xp: number
  xpToNext: number
  hp: number
  maxHp: number
  attack: number
  coins: number
}

export function createStartingStats(): PlayerStats {
  return {
    level: 1,
    xp: 0,
    xpToNext: 100,
    hp: 120,
    maxHp: 120,
    attack: 26,
    coins: 0,
  }
}
