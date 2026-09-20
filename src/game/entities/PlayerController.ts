import Phaser from 'phaser'
import { VirtualJoystick } from '../input/VirtualJoystick'

export type FacingDirection = 'up' | 'down' | 'left' | 'right'

export class PlayerController {
  private readonly player: Phaser.Physics.Arcade.Sprite
  private readonly cursors?: Phaser.Types.Input.Keyboard.CursorKeys
  private readonly joystick: VirtualJoystick
  private readonly speed = 260

  private facing: FacingDirection = 'down'
  private moving = false

  constructor(
    scene: Phaser.Scene,
    player: Phaser.Physics.Arcade.Sprite,
    joystick: VirtualJoystick,
  ) {
    this.player = player
    this.joystick = joystick

    if (scene.input.keyboard) {
      this.cursors = scene.input.keyboard.createCursorKeys()
    }
  }

  update() {
    let x = 0
    let y = 0

    const joystickDirection = this.joystick.getDirection()

    if (joystickDirection.lengthSq() > 0.01) {
      x = joystickDirection.x
      y = joystickDirection.y
    } else if (this.cursors) {
      if (this.cursors.left.isDown) x -= 1
      if (this.cursors.right.isDown) x += 1
      if (this.cursors.up.isDown) y -= 1
      if (this.cursors.down.isDown) y += 1
    }

    const direction = new Phaser.Math.Vector2(x, y)

    if (direction.lengthSq() === 0) {
      this.player.setVelocity(0, 0)
      this.moving = false
      return
    }

    if (direction.length() > 1) {
      direction.normalize()
    }

    this.updateFacing(direction)

    this.player.setVelocity(
      direction.x * this.speed,
      direction.y * this.speed,
    )

    this.moving = true
  }

  getFacing() {
    return this.facing
  }

  isMoving() {
    return this.moving
  }

  private updateFacing(direction: Phaser.Math.Vector2) {
    if (Math.abs(direction.x) > Math.abs(direction.y)) {
      this.facing = direction.x < 0 ? 'left' : 'right'
    } else {
      this.facing = direction.y < 0 ? 'up' : 'down'
    }

    if (this.facing === 'left') {
      this.player.setFlipX(true)
    } else if (this.facing === 'right') {
      this.player.setFlipX(false)
    }
  }
}
