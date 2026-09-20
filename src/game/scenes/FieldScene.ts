import Phaser from 'phaser'

export class FieldScene extends Phaser.Scene {
  private player!: Phaser.Physics.Arcade.Sprite
  private cursors!: Phaser.Types.Input.Keyboard.CursorKeys
  private target?: Phaser.Math.Vector2
  private readonly speed = 260

  constructor() {
    super('FieldScene')
  }

  create() {
    const worldWidth = 2400
    const worldHeight = 1600

    this.physics.world.setBounds(0, 0, worldWidth, worldHeight)
    this.cameras.main.setBounds(0, 0, worldWidth, worldHeight)

    this.createTextures()
    this.createWorld(worldWidth, worldHeight)

    this.player = this.physics.add
      .sprite(600, 700, 'player')
      .setDepth(20)
      .setCollideWorldBounds(true)

    this.player.body?.setSize(38, 48)

    const obstacles = this.physics.add.staticGroup()

    const obstaclePositions = [
      [850, 550],
      [1120, 800],
      [1450, 520],
      [1650, 980],
      [700, 1100],
      [1900, 650],
    ]

    obstaclePositions.forEach(([x, y]) => {
      obstacles.create(x, y, 'crystal')
    })

    this.physics.add.collider(this.player, obstacles)

    this.cameras.main.startFollow(this.player, true, 0.09, 0.09)
    this.cameras.main.setZoom(1)

    if (this.input.keyboard) {
      this.cursors = this.input.keyboard.createCursorKeys()
    }

    this.input.on('pointerdown', (pointer: Phaser.Input.Pointer) => {
      const worldPoint = this.cameras.main.getWorldPoint(pointer.x, pointer.y)

      this.target = new Phaser.Math.Vector2(worldPoint.x, worldPoint.y)

      this.tweens.add({
        targets: this.add
          .circle(worldPoint.x, worldPoint.y, 12, 0xffe08a, 0.75)
          .setDepth(30),
        radius: 38,
        alpha: 0,
        duration: 350,
        onComplete: (_tween, targets) => {
          targets[0].destroy()
        },
      })
    })

    this.createHUD()
  }

  update() {
    if (!this.player) return

    let vx = 0
    let vy = 0

    if (this.cursors) {
      if (this.cursors.left.isDown) vx -= 1
      if (this.cursors.right.isDown) vx += 1
      if (this.cursors.up.isDown) vy -= 1
      if (this.cursors.down.isDown) vy += 1
    }

    if (vx !== 0 || vy !== 0) {
      this.target = undefined

      const direction = new Phaser.Math.Vector2(vx, vy)
        .normalize()
        .scale(this.speed)

      this.player.setVelocity(direction.x, direction.y)
      return
    }

    if (this.target) {
      const distance = Phaser.Math.Distance.Between(
        this.player.x,
        this.player.y,
        this.target.x,
        this.target.y,
      )

      if (distance < 12) {
        this.player.setVelocity(0, 0)
        this.target = undefined
        return
      }

      this.physics.moveTo(
        this.player,
        this.target.x,
        this.target.y,
        this.speed,
      )

      return
    }

    this.player.setVelocity(0, 0)
  }

  private createWorld(width: number, height: number) {
    this.add.rectangle(
      width / 2,
      height / 2,
      width,
      height,
      0x182b32,
    )

    const graphics = this.add.graphics()

    for (let x = 0; x < width; x += 160) {
      for (let y = 0; y < height; y += 160) {
        const alternate = (x / 160 + y / 160) % 2 === 0

        graphics.fillStyle(
          alternate ? 0x1e3538 : 0x213b3d,
          0.8,
        )

        graphics.fillRect(x, y, 160, 160)
      }
    }

    for (let i = 0; i < 100; i++) {
      const x = Phaser.Math.Between(40, width - 40)
      const y = Phaser.Math.Between(40, height - 40)

      this.add.circle(
        x,
        y,
        Phaser.Math.Between(2, 5),
        0x8ec9a3,
        Phaser.Math.FloatBetween(0.15, 0.4),
      )
    }

    this.add
      .text(600, 470, 'STARFALL MEADOW', {
        fontFamily: 'Arial, sans-serif',
        fontSize: '42px',
        fontStyle: 'bold',
        color: '#e7ddb5',
        stroke: '#142027',
        strokeThickness: 5,
      })
      .setOrigin(0.5)

    this.add
      .text(600, 520, 'The First Frontier', {
        fontFamily: 'Arial, sans-serif',
        fontSize: '20px',
        color: '#a8c6bc',
      })
      .setOrigin(0.5)
  }

  private createTextures() {
    if (!this.textures.exists('player')) {
      const g = this.make.graphics({ x: 0, y: 0 }, false)

      g.fillStyle(0x31234b)
      g.fillCircle(32, 34, 27)

      g.fillStyle(0xf0d0b1)
      g.fillCircle(32, 25, 15)

      g.fillStyle(0x3b2b65)
      g.fillTriangle(14, 26, 32, 2, 50, 26)

      g.fillStyle(0xe7c05f)
      g.fillCircle(32, 31, 4)

      g.generateTexture('player', 64, 68)
      g.destroy()
    }

    if (!this.textures.exists('crystal')) {
      const g = this.make.graphics({ x: 0, y: 0 }, false)

      g.fillStyle(0x604f8f)
      g.fillTriangle(32, 0, 10, 60, 54, 60)

      g.fillStyle(0xa998e3, 0.8)
      g.fillTriangle(32, 8, 24, 52, 45, 52)

      g.generateTexture('crystal', 64, 64)
      g.destroy()
    }
  }

  private createHUD() {
    const camera = this.cameras.main

    const panel = this.add
      .rectangle(24, 24, 300, 94, 0x090d18, 0.82)
      .setOrigin(0)
      .setScrollFactor(0)
      .setDepth(100)

    panel.setStrokeStyle(2, 0xb79852, 0.75)

    this.add
      .text(44, 39, 'RANGER', {
        fontFamily: 'Arial, sans-serif',
        fontSize: '18px',
        fontStyle: 'bold',
        color: '#f0d789',
      })
      .setScrollFactor(0)
      .setDepth(101)

    this.add
      .text(44, 69, 'HP  120 / 120', {
        fontFamily: 'Arial, sans-serif',
        fontSize: '17px',
        color: '#d8e6df',
      })
      .setScrollFactor(0)
      .setDepth(101)

    this.add
      .text(44, 94, 'Lv. 1   •   Starfall Meadow', {
        fontFamily: 'Arial, sans-serif',
        fontSize: '14px',
        color: '#8fa8a2',
      })
      .setScrollFactor(0)
      .setDepth(101)

    this.add
      .text(camera.width - 28, camera.height - 26, 'TAP THE FIELD TO MOVE', {
        fontFamily: 'Arial, sans-serif',
        fontSize: '17px',
        color: '#c7c4b8',
      })
      .setOrigin(1)
      .setScrollFactor(0)
      .setDepth(101)
  }
}
