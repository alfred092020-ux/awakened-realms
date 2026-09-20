import Phaser from 'phaser'
import { PlayerController } from '../entities/PlayerController'
import { VirtualJoystick } from '../input/VirtualJoystick'

export class FieldScene extends Phaser.Scene {
  private player!: Phaser.Physics.Arcade.Sprite
  private playerController!: PlayerController
  private npc!: Phaser.Physics.Arcade.Sprite

  private interactButton!: Phaser.GameObjects.Arc
  private interactLabel!: Phaser.GameObjects.Text
  private interactionHint!: Phaser.GameObjects.Text

  private dialoguePanel!: Phaser.GameObjects.Rectangle
  private dialogueName!: Phaser.GameObjects.Text
  private dialogueText!: Phaser.GameObjects.Text
  private dialogueVisible = false

  private readonly interactionRange = 145

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

    this.npc = this.physics.add
      .staticSprite(930, 820, 'npc')
      .setDepth(20)

    this.add
      .text(this.npc.x, this.npc.y - 58, 'Lyra', {
        fontFamily: 'Arial, sans-serif',
        fontSize: '17px',
        fontStyle: 'bold',
        color: '#f4dd91',
        stroke: '#10151c',
        strokeThickness: 4,
      })
      .setOrigin(0.5)
      .setDepth(21)

    this.player = this.physics.add
      .sprite(600, 700, 'player')
      .setDepth(20)
      .setCollideWorldBounds(true)

    this.player.body?.setSize(38, 48)

    this.physics.add.collider(this.player, obstacles)
    this.physics.add.collider(this.player, this.npc)

    this.cameras.main.startFollow(this.player, true, 0.09, 0.09)

    this.createHUD()

    const joystick = new VirtualJoystick(
      this,
      125,
      this.scale.height - 125,
    )

    this.playerController = new PlayerController(
      this,
      this.player,
      joystick,
    )

    this.createInteractionUI()
    this.createDialogueUI()
  }

  update() {
    if (!this.playerController) return

    if (!this.dialogueVisible) {
      this.playerController.update()
    } else {
      this.player.setVelocity(0, 0)
    }

    this.updateInteractionState()
  }

  private updateInteractionState() {
    const distance = Phaser.Math.Distance.Between(
      this.player.x,
      this.player.y,
      this.npc.x,
      this.npc.y,
    )

    const canInteract = distance <= this.interactionRange

    this.interactButton.setVisible(canInteract && !this.dialogueVisible)
    this.interactLabel.setVisible(canInteract && !this.dialogueVisible)
    this.interactionHint.setVisible(canInteract && !this.dialogueVisible)
  }

  private interactWithNpc() {
    const distance = Phaser.Math.Distance.Between(
      this.player.x,
      this.player.y,
      this.npc.x,
      this.npc.y,
    )

    if (distance > this.interactionRange) return

    this.dialogueVisible = true

    this.dialoguePanel.setVisible(true)
    this.dialogueName.setVisible(true)
    this.dialogueText.setVisible(true)

    this.interactButton.setVisible(false)
    this.interactLabel.setVisible(false)
    this.interactionHint.setVisible(false)
  }

  private closeDialogue() {
    this.dialogueVisible = false

    this.dialoguePanel.setVisible(false)
    this.dialogueName.setVisible(false)
    this.dialogueText.setVisible(false)
  }

  private createInteractionUI() {
    const x = this.scale.width - 115
    const y = this.scale.height - 120

    this.interactButton = this.add
      .circle(x, y, 58, 0xb99145, 0.88)
      .setStrokeStyle(4, 0xf1dc91)
      .setScrollFactor(0)
      .setDepth(220)
      .setInteractive()

    this.interactLabel = this.add
      .text(x, y, 'TALK', {
        fontFamily: 'Arial, sans-serif',
        fontSize: '18px',
        fontStyle: 'bold',
        color: '#17121c',
      })
      .setOrigin(0.5)
      .setScrollFactor(0)
      .setDepth(221)

    this.interactionHint = this.add
      .text(x, y - 83, 'Lyra', {
        fontFamily: 'Arial, sans-serif',
        fontSize: '16px',
        color: '#f0dfaa',
      })
      .setOrigin(0.5)
      .setScrollFactor(0)
      .setDepth(221)

    this.interactButton.on('pointerdown', () => {
      this.interactWithNpc()
    })

    this.interactButton.setVisible(false)
    this.interactLabel.setVisible(false)
    this.interactionHint.setVisible(false)
  }

  private createDialogueUI() {
    const width = this.scale.width
    const height = this.scale.height

    this.dialoguePanel = this.add
      .rectangle(
        width / 2,
        height - 120,
        width - 300,
        190,
        0x090d18,
        0.95,
      )
      .setStrokeStyle(3, 0xc4a75c)
      .setScrollFactor(0)
      .setDepth(300)
      .setInteractive()

    this.dialogueName = this.add
      .text(190, height - 190, 'LYRA • STARFALL SCOUT', {
        fontFamily: 'Arial, sans-serif',
        fontSize: '20px',
        fontStyle: 'bold',
        color: '#e8cb74',
      })
      .setScrollFactor(0)
      .setDepth(301)

    this.dialogueText = this.add
      .text(
        190,
        height - 150,
        'The crystals have been restless since dawn.\nStay alert, Ranger. Something is waking beyond the meadow.',
        {
          fontFamily: 'Arial, sans-serif',
          fontSize: '20px',
          color: '#e2e5e4',
          lineSpacing: 10,
          wordWrap: {
            width: width - 390,
          },
        },
      )
      .setScrollFactor(0)
      .setDepth(301)

    this.dialoguePanel.on('pointerdown', () => {
      this.closeDialogue()
    })

    this.dialoguePanel.setVisible(false)
    this.dialogueName.setVisible(false)
    this.dialogueText.setVisible(false)
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
      this.add.circle(
        Phaser.Math.Between(40, width - 40),
        Phaser.Math.Between(40, height - 40),
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

    if (!this.textures.exists('npc')) {
      const g = this.make.graphics({ x: 0, y: 0 }, false)

      g.fillStyle(0x274c5d)
      g.fillCircle(32, 34, 27)

      g.fillStyle(0xf2d2b5)
      g.fillCircle(32, 25, 15)

      g.fillStyle(0xd4b85e)
      g.fillTriangle(13, 26, 32, 3, 51, 26)

      g.fillStyle(0x80d6d1)
      g.fillCircle(32, 32, 4)

      g.generateTexture('npc', 64, 68)
      g.destroy()
    }
  }

  private createHUD() {
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
  }
}
