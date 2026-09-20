import Phaser from 'phaser'
import { Enemy } from '../entities/Enemy'

export class TargetingSystem {
  private readonly scene: Phaser.Scene
  private readonly player: Phaser.Physics.Arcade.Sprite
  private readonly ring: Phaser.GameObjects.Ellipse

  private enemies: Enemy[] = []
  private target?: Enemy

  constructor(
    scene: Phaser.Scene,
    player: Phaser.Physics.Arcade.Sprite,
  ) {
    this.scene = scene
    this.player = player

    this.ring = scene.add
      .ellipse(0, 0, 86, 38)
      .setStrokeStyle(4, 0xffd65c, 0.95)
      .setDepth(12)
      .setVisible(false)

    this.scene.tweens.add({
      targets: this.ring,
      scaleX: 1.12,
      scaleY: 1.12,
      alpha: 0.55,
      yoyo: true,
      repeat: -1,
      duration: 650,
    })
  }

  setEnemies(enemies: Enemy[]) {
    this.enemies = enemies
  }

  update() {
    if (
      this.target &&
      !this.target.isDead() &&
      this.target.distanceTo(
        this.player.x,
        this.player.y,
      ) <= 520
    ) {
      this.updateRing()
      return
    }

    this.target = this.findNearest(520)

    if (!this.target) {
      this.ring.setVisible(false)
      return
    }

    this.updateRing()
  }

  getTarget() {
    this.update()
    return this.target
  }

  clearTarget(enemy?: Enemy) {
    if (
      enemy &&
      this.target !== enemy
    ) {
      return
    }

    this.target = undefined
    this.ring.setVisible(false)
  }

  private findNearest(
    maximumDistance: number,
  ) {
    let nearest: Enemy | undefined
    let nearestDistance = maximumDistance

    for (const enemy of this.enemies) {
      if (enemy.isDead()) continue

      const distance = enemy.distanceTo(
        this.player.x,
        this.player.y,
      )

      if (distance < nearestDistance) {
        nearest = enemy
        nearestDistance = distance
      }
    }

    return nearest
  }

  private updateRing() {
    if (!this.target) return

    this.ring
      .setPosition(
        this.target.sprite.x,
        this.target.sprite.y + 22,
      )
      .setVisible(true)
  }
}
