import {
  RUN_BALANCE,
} from './RunBalance'

import {
  RUN_UPGRADES,
  getRunUpgrade,
} from './UpgradeCatalog'

import {
  SeededRandom,
} from './SeededRandom'

import type {
  RunEnemyState,
  RunPlayerStats,
  RunResult,
  RunSnapshot,
  UpgradeDefinition,
  UpgradeId,
  RunModifiers,
} from './RunTypes'

import {
  DEFAULT_RUN_MODIFIERS,
} from './RunTypes'

export function createEnemyForWave(
  wave: number,
): RunEnemyState {
  const safeWave =
    Math.max(
      1,
      Math.floor(wave),
    )

  const boss =
    safeWave %
      RUN_BALANCE.bossEvery ===
    0

  const baseHp =
    22 +
    safeWave * 8

  const baseAttack =
    2 +
    Math.floor(
      safeWave * 0.8,
    )

  const hp =
    boss
      ? Math.round(
          baseHp * 2.6,
        )
      : baseHp

  const attack =
    boss
      ? Math.round(
          baseAttack * 1.35,
        )
      : baseAttack

  return {
    wave:
      safeWave,

    boss,

    hp,

    maxHp:
      hp,

    attack,

    attackIntervalMs:
      Math.max(
        650,
        1450 -
          safeWave * 7,
      ),

    xpReward:
      boss
        ? (
            30 +
            safeWave * 7
          )
        : (
            10 +
            safeWave * 3
          ),

    goldReward:
      boss
        ? (
            15 +
            safeWave * 4
          )
        : (
            2 +
            Math.floor(
              safeWave * 1.2,
            )
          ),
  }
}

export class RunEngine {
  private readonly seed:
    number

  private readonly random:
    SeededRandom

  private status:
    RunSnapshot['status'] =
      'running'

  private elapsedMs = 0

  private wave = 1
  private kills = 0

  private level = 1
  private xp = 0

  private xpToNext: number =
    RUN_BALANCE
      .startingXpToNext

  private gold = 0

  private readonly player:
    RunPlayerStats

  private enemy:
    RunEnemyState | null

  private pendingUpgrades:
    UpgradeDefinition[] = []

  private pendingUpgradeCount =
    0

  private playerAttackTimerMs:
    number

  private enemyAttackTimerMs:
    number

  constructor(
    seed: number,
    modifiers:
      RunModifiers =
        DEFAULT_RUN_MODIFIERS,
  ) {
    this.seed =
      seed >>> 0

    this.random =
      new SeededRandom(
        this.seed,
      )

    this.player = {
      hp:
        Math.round(
          RUN_BALANCE.startingHp *
          modifiers.hpMultiplier,
        ),

      maxHp:
        Math.round(
          RUN_BALANCE.startingHp *
          modifiers.hpMultiplier,
        ),

      attack:
        Math.round(
          RUN_BALANCE.startingAttack *
          modifiers.attackMultiplier,
        ),

      attackIntervalMs:
        Math.max(
          180,
          Math.round(
            RUN_BALANCE
              .startingAttackIntervalMs /
            modifiers
              .attackSpeedMultiplier,
          ),
        ),

      critChance:
        RUN_BALANCE
          .startingCritChance,

      critMultiplier:
        RUN_BALANCE
          .critMultiplier,

      damageReduction:
        0,

      healOnKill:
        0,
    }

    this.enemy =
      createEnemyForWave(
        this.wave,
      )

    this.playerAttackTimerMs =
      this.player
        .attackIntervalMs

    this.enemyAttackTimerMs =
      this.enemy
        .attackIntervalMs
  }

  advance(
    deltaMs: number,
  ) {
    if (
      this.status !==
        'running' ||
      deltaMs <= 0
    ) {
      return
    }

    let remaining =
      deltaMs

    let safety = 0

    while (
      remaining > 0 &&
      this.status ===
        'running'
    ) {
      safety += 1

      if (safety > 10000) {
        throw new Error(
          'Run simulation safety limit reached.',
        )
      }

      if (!this.enemy) {
        this.spawnCurrentWave()
      }

      const enemy =
        this.enemy

      if (!enemy) {
        break
      }

      const nextEventMs =
        Math.min(
          this.playerAttackTimerMs,
          this.enemyAttackTimerMs,
        )

      if (
        nextEventMs >
        remaining
      ) {
        this.playerAttackTimerMs -=
          remaining

        this.enemyAttackTimerMs -=
          remaining

        this.elapsedMs +=
          remaining

        remaining = 0

        break
      }

      this.playerAttackTimerMs -=
        nextEventMs

      this.enemyAttackTimerMs -=
        nextEventMs

      this.elapsedMs +=
        nextEventMs

      remaining -=
        nextEventMs

      if (
        this.playerAttackTimerMs <=
        0
      ) {
        this.performPlayerAttack()

        this.playerAttackTimerMs +=
          this.player
            .attackIntervalMs
      }

      if (
        this.status !==
          'running' ||
        !this.enemy
      ) {
        continue
      }

      if (
        this.enemyAttackTimerMs <=
        0
      ) {
        this.performEnemyAttack()

        if (
          this.enemy
        ) {
          this.enemyAttackTimerMs +=
            this.enemy
              .attackIntervalMs
        }
      }
    }
  }

  chooseUpgrade(
    upgradeId: UpgradeId,
  ) {
    if (
      this.status !==
      'upgrade'
    ) {
      throw new Error(
        'No upgrade choice is currently available.',
      )
    }

    const offered =
      this.pendingUpgrades
        .some(
          (upgrade) =>
            upgrade.id ===
            upgradeId,
        )

    if (!offered) {
      throw new Error(
        'Upgrade was not offered.',
      )
    }

    this.applyUpgrade(
      upgradeId,
    )

    this.pendingUpgradeCount =
      Math.max(
        0,
        this.pendingUpgradeCount -
          1,
      )

    if (
      this.pendingUpgradeCount >
      0
    ) {
      this.generateUpgradeChoices()
      return
    }

    this.pendingUpgrades = []
    this.status = 'running'

    if (!this.enemy) {
      this.spawnCurrentWave()
    }
  }

  getSnapshot():
    RunSnapshot {
    return {
      seed:
        this.seed,

      status:
        this.status,

      elapsedMs:
        this.elapsedMs,

      wave:
        this.wave,

      kills:
        this.kills,

      level:
        this.level,

      xp:
        this.xp,

      xpToNext:
        this.xpToNext,

      gold:
        this.gold,

      player: {
        ...this.player,
      },

      enemy:
        this.enemy
          ? {
              ...this.enemy,
            }
          : null,

      pendingUpgrades:
        this.pendingUpgrades
          .map(
            (upgrade) => ({
              ...upgrade,
            }),
          ),
    }
  }

  getResult():
    RunResult | undefined {
    if (
      this.status !== 'dead' &&
      this.status !== 'won'
    ) {
      return undefined
    }

    return {
      won:
        this.status ===
        'won',

      waveReached:
        this.wave,

      kills:
        this.kills,

      gold:
        this.gold,

      essence:
        Math.floor(
          this.kills / 3,
        ) +
        (
          this.status ===
          'won'
            ? 25
            : 0
        ),

      elapsedMs:
        this.elapsedMs,
    }
  }

  private performPlayerAttack() {
    const enemy =
      this.enemy

    if (!enemy) {
      return
    }

    const critical =
      this.random.next() <
      this.player
        .critChance

    const damage =
      Math.max(
        1,
        Math.round(
          this.player.attack *
            (
              critical
                ? this.player
                    .critMultiplier
                : 1
            ),
        ),
      )

    enemy.hp =
      Math.max(
        0,
        enemy.hp - damage,
      )

    if (enemy.hp <= 0) {
      this.defeatEnemy()
    }
  }

  private performEnemyAttack() {
    const enemy =
      this.enemy

    if (!enemy) {
      return
    }

    const multiplier =
      Math.max(
        0,
        1 -
          this.player
            .damageReduction,
      )

    const damage =
      Math.max(
        1,
        Math.round(
          enemy.attack *
            multiplier,
        ),
      )

    this.player.hp =
      Math.max(
        0,
        this.player.hp -
          damage,
      )

    if (
      this.player.hp <= 0
    ) {
      this.status = 'dead'
      this.pendingUpgrades = []
    }
  }

  private defeatEnemy() {
    const enemy =
      this.enemy

    if (!enemy) {
      return
    }

    this.kills += 1

    this.gold +=
      enemy.goldReward

    this.xp +=
      enemy.xpReward

    if (
      this.player
        .healOnKill > 0
    ) {
      this.player.hp =
        Math.min(
          this.player.maxHp,
          this.player.hp +
            this.player
              .healOnKill,
        )
    }

    this.enemy = null

    if (
      this.wave >=
      RUN_BALANCE.maximumWave
    ) {
      this.status = 'won'
      return
    }

    this.wave += 1

    this.processLevelUps()

    if (
      this.pendingUpgradeCount >
      0
    ) {
      this.status = 'upgrade'
      this.generateUpgradeChoices()
      return
    }

    this.spawnCurrentWave()
  }

  private processLevelUps() {
    while (
      this.xp >=
      this.xpToNext
    ) {
      this.xp -=
        this.xpToNext

      this.level += 1

      this.xpToNext =
        Math.floor(
          this.xpToNext *
            1.28,
        ) +
        4

      this.pendingUpgradeCount +=
        1
    }
  }

  private generateUpgradeChoices() {
    const shuffled =
      this.random.shuffle(
        RUN_UPGRADES,
      )

    this.pendingUpgrades =
      shuffled
        .slice(
          0,
          RUN_BALANCE
            .upgradeChoices,
        )
        .map(
          (upgrade) => ({
            ...upgrade,
          }),
        )
  }

  private applyUpgrade(
    upgradeId: UpgradeId,
  ) {
    const definition =
      getRunUpgrade(
        upgradeId,
      )

    if (!definition) {
      throw new Error(
        'Unknown run upgrade.',
      )
    }

    switch (upgradeId) {
      case 'power-surge':
        this.player.attack =
          Math.max(
            1,
            Math.round(
              this.player.attack *
                1.2,
            ),
          )

        break

      case 'vital-core': {
        const oldMaximum =
          this.player.maxHp

        this.player.maxHp =
          Math.ceil(
            this.player.maxHp *
              1.25,
          )

        this.player.hp =
          Math.min(
            this.player.maxHp,
            this.player.hp +
              (
                this.player.maxHp -
                oldMaximum
              ),
          )

        break
      }

      case 'quickening':
        this.player
          .attackIntervalMs =
          Math.max(
            180,
            Math.round(
              this.player
                .attackIntervalMs *
                0.85,
            ),
          )

        this.playerAttackTimerMs =
          Math.min(
            this.playerAttackTimerMs,
            this.player
              .attackIntervalMs,
          )

        break

      case 'critical-eye':
        this.player
          .critChance =
          Math.min(
            0.75,
            this.player
              .critChance +
              0.08,
          )

        break

      case 'aegis':
        this.player
          .damageReduction =
          Math.min(
            0.6,
            this.player
              .damageReduction +
              0.08,
          )

        break

      case 'renewal':
        this.player
          .healOnKill +=
          6

        break
    }
  }

  private spawnCurrentWave() {
    this.enemy =
      createEnemyForWave(
        this.wave,
      )

    this.playerAttackTimerMs =
      Math.min(
        this.playerAttackTimerMs,
        this.player
          .attackIntervalMs,
      )

    this.enemyAttackTimerMs =
      this.enemy
        .attackIntervalMs
  }
}
