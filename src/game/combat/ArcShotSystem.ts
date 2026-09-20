import Phaser from 'phaser'
import type { Enemy } from '../entities/Enemy'
import type { PlayerStats } from './CombatStats'
import type { TargetingSystem } from './TargetingSystem'

export interface ArcShotCallbacks {
  onEnemyKilled: (enemy: Enemy) => void
  onMessage: (message: string) => void
  onEnergyChanged: () => void
}

export class ArcShotSystem {
  private readonly scene: Phaser.Scene
  private readonly player: Phaser.Physics.Arcade.Sprite
  private readonly stats: PlayerStats
  private readonly targeting: TargetingSystem
  private readonly callbacks: ArcShotCallbacks

  private energy = 100
  private readonly maxEnergy = 100
  private readonly cost = 25
  private ready = true

  constructor(
    scene: Phaser.Scene,
    player: Phaser.Physics.Arcade.Sprite,
    stats: PlayerStats,
    targeting: TargetingSystem,
    callbacks: ArcShotCallbacks,
  ) {
    this.scene = scene
    this.player = player
    this.stats = stats
    this.targeting = targeting
    this.callbacks = callbacks
  }

  update(delta: number) {
    const previous = Math.floor(this.energy)

    this.energy = Math.min(
      this.maxEnergy,
      this.energy + delta * 0.008,
    )

    if (Math.floor(this.energy) !== previous) {
      this.callbacks.onEnergyChanged()
    }
  }

  cast() {
    if (!this.ready) {
      this.callbacks.onMessage(
        'Arc Shot cooling down',
      )
      return
    }

    if (this.energy < this.cost) {
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
      ) > 430
    ) {
      this.callbacks.onMessage(
        'Target too far',
      )
      return
    }

    this.energy -= this.cost
    this.ready = false

    this.callbacks.onEnergyChanged()

    this.scene.time.delayedCall(
      2600,
      () => {
        this.ready = true
      },
    )

    const projectile = this.scene.add
      .circle(
        this.player.x,
        this.player.y,
        9,
        0x62dcff,
        1,
      )
      .setStrokeStyle(
        4,
        0xe8fbff,
        0.95,
      )
      .setDepth(80)

    const trail = this.scene.add
      .circle(
        this.player.x,
        this.player.y,
        18,
        0x62dcff,
        0.22,
      )
      .setDepth(79)

    this.scene.tweens.add({
      targets: [projectile, trail],
      x: target.sprite.x,
      y: target.sprite.y,
      duration: 230,
      ease: 'Quad.easeIn',
      onComplete: () => {
        projectile.destroy()
        trail.destroy()

        if (target.isDead()) {
          return
        }

        this.createImpact(
          target.sprite.x,
          target.sprite.y,
        )

        const killed = target.damage(
          Math.round(
            this.stats.attack * 1.8,
          ),
        )

        if (killed) {
          this.targeting.clearTarget(target)
          this.callbacks.onEnemyKilled(target)
        }
      },
    })
  }

  getEnergy() {
    return Math.floor(this.energy)
  }

  getMaxEnergy() {
    return this.maxEnergy
  }

  private createImpact(
    x: number,
    y: number,
  ) {
    const impact = this.scene.add
      .circle(
        x,
        y,
        12,
        0x62dcff,
        0.8,
      )
      .setStrokeStyle(
        4,
        0xe9fbff,
        0.9,
      )
      .setDepth(81)

    this.scene.tweens.add({
      targets: impact,
      radius: 58,
      alpha: 0,
      duration: 280,
      onComplete: () =>
        impact.destroy(),
    })

    this.scene.cameras.main.shake(
      90,
      0.002,
    )
  }
}
