import Phaser from 'phaser'

export class VirtualJoystick {
  private readonly scene: Phaser.Scene
  private readonly base: Phaser.GameObjects.Arc
  private readonly knob: Phaser.GameObjects.Arc
  private readonly vector = new Phaser.Math.Vector2()
  private pointerId?: number
  private readonly radius = 72

  constructor(scene: Phaser.Scene, x: number, y: number) {
    this.scene = scene

    this.base = scene.add
      .circle(x, y, this.radius, 0x101725, 0.48)
      .setStrokeStyle(3, 0xd8c179, 0.55)
      .setScrollFactor(0)
      .setDepth(200)

    this.knob = scene.add
      .circle(x, y, 31, 0xe2c775, 0.72)
      .setScrollFactor(0)
      .setDepth(201)

    this.base.setInteractive(
      new Phaser.Geom.Circle(this.radius, this.radius, this.radius),
      Phaser.Geom.Circle.Contains,
    )

    this.base.on('pointerdown', (pointer: Phaser.Input.Pointer) => {
      this.pointerId = pointer.id
      this.updatePointer(pointer)
    })

    scene.input.on('pointermove', (pointer: Phaser.Input.Pointer) => {
      if (pointer.id === this.pointerId && pointer.isDown) {
        this.updatePointer(pointer)
      }
    })

    scene.input.on('pointerup', (pointer: Phaser.Input.Pointer) => {
      if (pointer.id === this.pointerId) {
        this.release()
      }
    })
  }

  getDirection() {
    return this.vector.clone()
  }

  private updatePointer(pointer: Phaser.Input.Pointer) {
    const dx = pointer.x - this.base.x
    const dy = pointer.y - this.base.y

    const distance = Math.min(
      Math.sqrt(dx * dx + dy * dy),
      this.radius,
    )

    const angle = Math.atan2(dy, dx)

    const offsetX = Math.cos(angle) * distance
    const offsetY = Math.sin(angle) * distance

    this.knob.setPosition(
      this.base.x + offsetX,
      this.base.y + offsetY,
    )

    if (distance < 8) {
      this.vector.set(0, 0)
      return
    }

    const strength = distance / this.radius

    this.vector.set(
      Math.cos(angle) * strength,
      Math.sin(angle) * strength,
    )
  }

  private release() {
    this.pointerId = undefined
    this.vector.set(0, 0)
    this.knob.setPosition(this.base.x, this.base.y)

    this.scene.tweens.add({
      targets: this.knob,
      scale: 1.08,
      yoyo: true,
      duration: 70,
    })
  }
}
