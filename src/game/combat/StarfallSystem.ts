import Phaser from 'phaser'
import type { Enemy } from '../entities/Enemy'
import type { PlayerStats } from './CombatStats'
import type { TargetingSystem } from './TargetingSystem'
import type { EnergySystem } from './EnergySystem'
import { CriticalHitSystem } from './CriticalHitSystem'

export interface StarfallCallbacks {
  onEnemyKilled: (enemy: Enemy) => void
  onMessage: (message: string) => void
}

export class StarfallSystem {
  private readonly scene: Phaser.Scene
  private readonly player: Phaser.Physics.Arcade.Sprite
  private readonly stats: PlayerStats
  private readonly targeting: TargetingSystem
  private readonly energy: EnergySystem
  private readonly callbacks: StarfallCallbacks

  private enemies: Enemy[] = []
  private ready = true

  private readonly cost = 45
  private readonly cooldown = 5200
  private readonly castRange = 430
  private readonly blastRadius = 230

  constructor(
    scene: Phaser.Scene,
    player: Phaser.Physics.Arcade.Sprite,
    stats: PlayerStats,
    targeting: TargetingSystem,
    energy: EnergySystem,
    callbacks: StarfallCallbacks,
  ) {
    this.scene = scene
    this.player = player
    this.stats = stats
    this.targeting = targeting
    this.energy = energy
    this.callbacks = callbacks
  }

  setEnemies(enemies: Enemy[]) {
    this.enemies = enemies
  }

  cast() {
    if (!this.ready) {
      this.callbacks.onMessage(
        'Starfall cooling down',
      )
      return
    }

    if (!this.energy.canSpend(this.cost)) {
      this.callbacks.onMessage(
        'Not enough EP',
      )
      return
    }

    const target = this.targeting.getTarget()

    if (!target) {
      this.callbacks.onMessage(
        'No target',
      )
      return
    }

    if (
      target.distanceTo(
        this.player.x,
        this.player.y,
      ) > this.castRange
    ) {
      this.callbacks.onMessage(
        'Target too far',
      )
      return
    }

    this.energy.spend(this.cost)
    this.ready = false

    this.scene.time.delayedCall(
      this.cooldown,
      () => {
        this.ready = true
      },
    )

    const centerX = target.sprite.x
    const centerY = target.sprite.y

    this.createCastMarker(
      centerX,
      centerY,
    )

    this.scene.time.delayedCall(
      350,
      () => {
        this.strike(
          centerX,
          centerY,
        )
      },
    )
  }

  private createCastMarker(
    x: number,
    y: number,
  ) {
    const marker = this.scene.add
      .ellipse(
        x,
        y + 18,
        this.blastRadius * 2,
        this.blastRadius,
        0x6d4acb,
        0.12,
      )
      .setStrokeStyle(
        5,
        0xc9b5ff,
        0.85,
      )
      .setDepth(13)

    marker.setScale(0.25)

    this.scene.tweens.add({
      targets: marker,
      scaleX: 1,
      scaleY: 1,
      alpha: 0.45,
      duration: 330,
      ease: 'Quad.easeOut',
      onComplete: () => {
        marker.destroy()
      },
    })
  }

  private strike(
    x: number,
    y: number,
  ) {
    this.createMeteor(
      x,
      y,
      0,
    )

    this.createMeteor(
      x - 80,
      y + 35,
      80,
    )

    this.createMeteor(
      x + 85,
      y - 25,
      150,
    )

    this.scene.time.delayedCall(
      190,
      () => {
        this.applyDamage(
          x,
          y,
        )
      },
    )
  }

  private createMeteor(
    x: number,
    y: number,
    delay: number,
  ) {
    this.scene.time.delayedCall(
      delay,
      () => {
        const startX = x + 130
        const startY = y - 360

        const glow = this.scene.add
          .circle(
            startX,
            startY,
            25,
            0xb894ff,
            0.25,
          )
          .setDepth(89)

        const meteor = this.scene.add
          .circle(
            startX,
            startY,
            12,
            0xf2e8ff,
            1,
          )
          .setStrokeStyle(
            6,
            0x9d72ff,
            0.95,
          )
          .setDepth(90)

        this.scene.tweens.add({
          targets: [
            meteor,
            glow,
          ],
          x,
          y,
          duration: 230,
          ease: 'Quad.easeIn',
          onComplete: () => {
            meteor.destroy()
            glow.destroy()

            this.createImpact(
              x,
              y,
            )
          },
        })
      },
    )
  }

  private createImpact(
    x: number,
    y: number,
  ) {
    const flash = this.scene.add
      .circle(
        x,
        y,
        18,
        0xe9ddff,
        0.9,
      )
      .setDepth(91)

    const ring = this.scene.add
      .circle(
        x,
        y,
        22,
        0x9d72ff,
        0.18,
      )
      .setStrokeStyle(
        5,
        0xc9b5ff,
        0.9,
      )
      .setDepth(90)

    this.scene.tweens.add({
      targets: flash,
      radius: 60,
      alpha: 0,
      duration: 260,
      onComplete: () =>
        flash.destroy(),
    })

    this.scene.tweens.add({
      targets: ring,
      radius: 95,
      alpha: 0,
      duration: 360,
      onComplete: () =>
        ring.destroy(),
    })
  }

  private applyDamage(
    x: number,
    y: number,
  ) {
    const damage = Math.round(
      this.stats.attack * 1.45,
    )

    for (const enemy of this.enemies) {
      if (enemy.isDead()) {
        continue
      }

      const distance =
        Phaser.Math.Distance.Between(
          enemy.sprite.x,
          enemy.sprite.y,
          x,
          y,
        )

      if (distance > this.blastRadius) {
        continue
      }

      const hit =
        CriticalHitSystem.roll(
          damage,
        )

      const killed = enemy.damage(
        hit.damage,
        hit.critical,
      )

      if (killed) {
        this.targeting.clearTarget(
          enemy,
        )

        this.callbacks.onEnemyKilled(
          enemy,
        )
      }
    }

    this.scene.cameras.main.shake(
      160,
      0.004,
    )
  }
}
