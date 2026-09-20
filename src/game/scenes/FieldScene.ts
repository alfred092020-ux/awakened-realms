import Phaser from 'phaser'
import { PlayerController } from '../entities/PlayerController'
import { VirtualJoystick } from '../input/VirtualJoystick'
import { Enemy } from '../entities/Enemy'
import {
  createStartingStats,
  type PlayerStats,
} from '../combat/CombatStats'

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

  private stats: PlayerStats = createStartingStats()
  private enemies: Enemy[] = []

  private attackButton!: Phaser.GameObjects.Arc

  private hpText!: Phaser.GameObjects.Text
  private levelText!: Phaser.GameObjects.Text
  private xpText!: Phaser.GameObjects.Text
  private coinText!: Phaser.GameObjects.Text

  private playerDead = false
  private attackReady = true

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
    this.createCombatUI()

    this.spawnEnemy(1280, 720)
    this.spawnEnemy(1520, 900)
    this.spawnEnemy(1780, 600)

    this.refreshHUD()
  }

  update() {
    if (!this.playerController) return

    if (!this.dialogueVisible) {
      this.playerController.update()
    } else {
      this.player.setVelocity(0, 0)
    }

    this.updateInteractionState()

    if (!this.playerDead && !this.dialogueVisible) {
      for (const enemy of this.enemies) {
        enemy.update(
          this.player,
          (damage) => this.damagePlayer(damage),
        )
      }
    } else {
      for (const enemy of this.enemies) {
        enemy.sprite.setVelocity(0, 0)
      }
    }
  }


  private spawnEnemy(x: number, y: number) {
    const enemy = new Enemy(this, x, y)

    this.enemies.push(enemy)

    this.physics.add.collider(
      enemy.sprite,
      this.player,
    )
  }

  private createCombatUI() {
    const x = this.scale.width - 115
    const y = this.scale.height - 120

    this.attackButton = this.add
      .circle(x, y, 62, 0x8d3344, 0.94)
      .setStrokeStyle(4, 0xf0a06c)
      .setScrollFactor(0)
      .setDepth(210)
      .setInteractive()

    this.add
      .text(x, y, 'ATTACK', {
        fontFamily: 'Arial, sans-serif',
        fontSize: '17px',
        fontStyle: 'bold',
        color: '#fff0c9',
      })
      .setOrigin(0.5)
      .setScrollFactor(0)
      .setDepth(211)

    this.attackButton.on('pointerdown', () => {
      this.playerAttack()
    })
  }

  private playerAttack() {
    if (
      this.playerDead ||
      this.dialogueVisible ||
      !this.attackReady
    ) {
      return
    }

    const target = this.getNearestLivingEnemy()

    if (!target) {
      this.showCombatMessage('No enemy nearby')
      return
    }

    const distance = target.distanceTo(
      this.player.x,
      this.player.y,
    )

    if (distance > 155) {
      this.showCombatMessage('Out of range')
      return
    }

    this.attackReady = false

    this.time.delayedCall(420, () => {
      this.attackReady = true
    })

    this.tweens.add({
      targets: this.player,
      scaleX: 1.18,
      scaleY: 0.88,
      yoyo: true,
      duration: 90,
    })

    const killed = target.damage(
      this.stats.attack,
    )

    if (killed) {
      this.rewardEnemy(target)
    }
  }

  private getNearestLivingEnemy() {
    let nearest: Enemy | undefined
    let nearestDistance = Number.MAX_VALUE

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

  private rewardEnemy(enemy: Enemy) {
    this.stats.coins += 12
    this.stats.xp += 40

    this.showCombatMessage('+40 XP   +12 coins')

    while (this.stats.xp >= this.stats.xpToNext) {
      this.stats.xp -= this.stats.xpToNext
      this.stats.level += 1
      this.stats.xpToNext =
        Math.floor(this.stats.xpToNext * 1.35)

      this.stats.maxHp += 20
      this.stats.hp = this.stats.maxHp
      this.stats.attack += 5

      this.showCombatMessage(
        `LEVEL UP!  Lv. ${this.stats.level}`,
      )
    }

    this.refreshHUD()

    this.time.delayedCall(3000, () => {
      const x = enemy.sprite.x
      const y = enemy.sprite.y

      enemy.destroy()

      this.enemies = this.enemies.filter(
        (item) => item !== enemy,
      )

      this.spawnEnemy(x, y)
    })
  }

  private damagePlayer(amount: number) {
    if (this.playerDead) return

    this.stats.hp = Math.max(
      0,
      this.stats.hp - amount,
    )

    this.refreshHUD()

    const damageText = this.add
      .text(
        this.player.x,
        this.player.y - 70,
        `-${amount}`,
        {
          fontFamily: 'Arial, sans-serif',
          fontSize: '22px',
          fontStyle: 'bold',
          color: '#ff8b8b',
          stroke: '#35151c',
          strokeThickness: 4,
        },
      )
      .setOrigin(0.5)
      .setDepth(70)

    this.tweens.add({
      targets: damageText,
      y: damageText.y - 32,
      alpha: 0,
      duration: 550,
      onComplete: () => damageText.destroy(),
    })

    this.cameras.main.shake(
      100,
      0.003,
    )

    if (this.stats.hp <= 0) {
      this.defeatPlayer()
    }
  }

  private defeatPlayer() {
    this.playerDead = true
    this.player.setVelocity(0, 0)

    if (this.player.body) {
      this.player.body.enable = false
    }

    this.showCombatMessage(
      'DEFEATED • Respawning...',
    )

    this.player.setAlpha(0.35)

    this.time.delayedCall(2200, () => {
      this.stats.hp = this.stats.maxHp

      this.player.setPosition(600, 700)
      this.player.setAlpha(1)

      if (this.player.body) {
        this.player.body.enable = true
      }

      this.playerDead = false

      this.refreshHUD()
      this.showCombatMessage('Returned to Starfall')
    })
  }

  private refreshHUD() {
    if (!this.hpText) return

    this.hpText.setText(
      `HP  ${this.stats.hp} / ${this.stats.maxHp}`,
    )

    this.levelText.setText(
      `Lv. ${this.stats.level}   •   Starfall Meadow`,
    )

    this.xpText.setText(
      `XP ${this.stats.xp} / ${this.stats.xpToNext}`,
    )

    this.coinText.setText(
      `${this.stats.coins} coins`,
    )
  }

  private showCombatMessage(message: string) {
    const text = this.add
      .text(
        this.scale.width / 2,
        105,
        message,
        {
          fontFamily: 'Arial, sans-serif',
          fontSize: '24px',
          fontStyle: 'bold',
          color: '#ffe7a3',
          stroke: '#17101d',
          strokeThickness: 5,
        },
      )
      .setOrigin(0.5)
      .setScrollFactor(0)
      .setDepth(500)

    this.tweens.add({
      targets: text,
      y: 80,
      alpha: 0,
      duration: 1100,
      onComplete: () => text.destroy(),
    })
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

    if (!this.textures.exists('slime')) {
      const g = this.make.graphics(
        { x: 0, y: 0 },
        false,
      )

      g.fillStyle(0x57b779)
      g.fillEllipse(36, 40, 64, 48)

      g.fillStyle(0x91e4a8, 0.8)
      g.fillEllipse(25, 28, 24, 16)

      g.fillStyle(0x14231b)
      g.fillCircle(24, 39, 4)
      g.fillCircle(47, 39, 4)

      g.fillStyle(0xc8ffd4)
      g.fillCircle(23, 38, 1.5)
      g.fillCircle(46, 38, 1.5)

      g.generateTexture('slime', 72, 64)
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
      .rectangle(
        24,
        24,
        330,
        138,
        0x090d18,
        0.86,
      )
      .setOrigin(0)
      .setScrollFactor(0)
      .setDepth(100)

    panel.setStrokeStyle(
      2,
      0xb79852,
      0.75,
    )

    this.add
      .text(44, 38, 'RANGER', {
        fontFamily: 'Arial, sans-serif',
        fontSize: '18px',
        fontStyle: 'bold',
        color: '#f0d789',
      })
      .setScrollFactor(0)
      .setDepth(101)

    this.hpText = this.add
      .text(44, 67, '', {
        fontFamily: 'Arial, sans-serif',
        fontSize: '17px',
        color: '#d8e6df',
      })
      .setScrollFactor(0)
      .setDepth(101)

    this.levelText = this.add
      .text(44, 93, '', {
        fontFamily: 'Arial, sans-serif',
        fontSize: '14px',
        color: '#8fa8a2',
      })
      .setScrollFactor(0)
      .setDepth(101)

    this.xpText = this.add
      .text(44, 118, '', {
        fontFamily: 'Arial, sans-serif',
        fontSize: '14px',
        color: '#a9c8dc',
      })
      .setScrollFactor(0)
      .setDepth(101)

    this.coinText = this.add
      .text(235, 118, '', {
        fontFamily: 'Arial, sans-serif',
        fontSize: '14px',
        color: '#e9cb6f',
      })
      .setScrollFactor(0)
      .setDepth(101)
  }
}
