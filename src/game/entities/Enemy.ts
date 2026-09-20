import Phaser from 'phaser'

export class Enemy {
  readonly sprite: Phaser.Physics.Arcade.Sprite
  private readonly scene: Phaser.Scene

  private hp = 70
  private readonly maxHp = 70

  private readonly aggroRange = 360
  private readonly attackRange = 78
  private readonly speed = 105

  private lastAttack = 0
  private dead = false
  private knockbackUntil = 0

  private hpBackground: Phaser.GameObjects.Rectangle
  private hpBar: Phaser.GameObjects.Rectangle

  constructor(
    scene: Phaser.Scene,
    x: number,
    y: number,
  ) {
    this.scene = scene

    this.sprite = scene.physics.add
      .sprite(x, y, 'slime')
      .setDepth(18)

    this.sprite.body?.setSize(48, 38)

    this.hpBackground = scene.add
      .rectangle(x, y - 48, 58, 7, 0x24171c)
      .setDepth(30)

    this.hpBar = scene.add
      .rectangle(x - 29, y - 48, 58, 7, 0x75d66d)
      .setOrigin(0, 0.5)
      .setDepth(31)
  }

  update(
    player: Phaser.Physics.Arcade.Sprite,
    onAttack: (damage: number) => void,
  ) {
    if (this.dead) return

    this.hpBackground.setPosition(
      this.sprite.x,
      this.sprite.y - 48,
    )

    this.hpBar.setPosition(
      this.sprite.x - 29,
      this.sprite.y - 48,
    )

    if (
      this.scene.time.now <
      this.knockbackUntil
    ) {
      return
    }

    const distance = Phaser.Math.Distance.Between(
      this.sprite.x,
      this.sprite.y,
      player.x,
      player.y,
    )

    if (distance > this.aggroRange) {
      this.sprite.setVelocity(0, 0)
      return
    }

    if (distance > this.attackRange) {
      this.scene.physics.moveToObject(
        this.sprite,
        player,
        this.speed,
      )

      return
    }

    this.sprite.setVelocity(0, 0)

    const now = this.scene.time.now

    if (now - this.lastAttack >= 1100) {
      this.lastAttack = now
      onAttack(12)

      this.scene.tweens.add({
        targets: this.sprite,
        scaleX: 1.18,
        scaleY: 0.82,
        yoyo: true,
        duration: 100,
      })
    }
  }

  damage(
    amount: number,
    critical = false,
  ) {
    if (this.dead) return false

    this.hp = Math.max(0, this.hp - amount)

    this.hpBar.width =
      58 * (this.hp / this.maxHp)

    this.scene.tweens.add({
      targets: this.sprite,
      alpha: 0.25,
      yoyo: true,
      duration: 70,
      repeat: 1,
    })

    const damageText = this.scene.add
      .text(
        this.sprite.x,
        this.sprite.y - 70,
        critical
          ? `CRIT! -${amount}`
          : `-${amount}`,
        {
          fontFamily: 'Arial, sans-serif',
          fontSize: critical
            ? '30px'
            : '22px',
          fontStyle: 'bold',
          color: critical
            ? '#fff36b'
            : '#fff0b8',
          stroke: critical
            ? '#8a3215'
            : '#35151c',
          strokeThickness: critical
            ? 6
            : 4,
        },
      )
      .setOrigin(0.5)
      .setDepth(60)

    this.scene.tweens.add({
      targets: damageText,
      y: damageText.y - 35,
      alpha: 0,
      duration: 600,
      onComplete: () => damageText.destroy(),
    })

    if (this.hp <= 0) {
      this.die()
      return true
    }

    return false
  }

  isDead() {
    return this.dead
  }

  reactToHit(
    sourceX: number,
    sourceY: number,
    strength = 180,
  ) {
    if (this.dead) {
      return
    }

    const dx =
      this.sprite.x - sourceX

    const dy =
      this.sprite.y - sourceY

    const length = Math.hypot(
      dx,
      dy,
    )

    const normalX =
      length > 0.001
        ? dx / length
        : 1

    const normalY =
      length > 0.001
        ? dy / length
        : 0

    this.sprite.setVelocity(
      normalX * strength,
      normalY * strength,
    )

    this.knockbackUntil =
      this.scene.time.now + 140

    this.scene.tweens.add({
      targets: this.sprite,
      scaleX: 1.14,
      scaleY: 0.86,
      duration: 70,
      yoyo: true,
    })
  }

  distanceTo(x: number, y: number) {
    return Phaser.Math.Distance.Between(
      this.sprite.x,
      this.sprite.y,
      x,
      y,
    )
  }

  destroy() {
    this.sprite.destroy()
    this.hpBackground.destroy()
    this.hpBar.destroy()
  }

  private die() {
    this.dead = true

    this.sprite.setVelocity(0, 0)

    if (this.sprite.body) {
      this.sprite.body.enable = false
    }

    this.hpBackground.setVisible(false)
    this.hpBar.setVisible(false)

    this.scene.tweens.add({
      targets: this.sprite,
      alpha: 0,
      scaleX: 1.35,
      scaleY: 0.35,
      duration: 350,
    })
  }
}
