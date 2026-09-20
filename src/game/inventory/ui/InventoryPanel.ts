import Phaser from 'phaser'

import {
  getItemDefinition,
} from '../ItemCatalog'

import type {
  InventorySystem,
} from '../InventorySystem'

import type {
  ItemRarity,
} from '../ItemTypes'

export interface InventoryUseResult {
  used: boolean
  message: string
}

export interface InventoryPanelCallbacks {
  onUseItem: (
    itemId: string,
  ) => InventoryUseResult

  onVisibilityChanged: (
    visible: boolean,
  ) => void
}

export class InventoryPanel {
  private readonly scene: Phaser.Scene
  private readonly inventory:
    InventorySystem

  private readonly callbacks:
    InventoryPanelCallbacks

  private readonly container:
    Phaser.GameObjects.Container

  private readonly dynamicObjects:
    Phaser.GameObjects.GameObject[] = []

  private readonly statusText:
    Phaser.GameObjects.Text

  private opened = false
  private selectedItemId?: string

  constructor(
    scene: Phaser.Scene,
    inventory: InventorySystem,
    callbacks: InventoryPanelCallbacks,
  ) {
    this.scene = scene
    this.inventory = inventory
    this.callbacks = callbacks

    this.container = scene.add
      .container(0, 0)
      .setScrollFactor(0)
      .setDepth(700)
      .setVisible(false)

    const blocker = scene.add
      .rectangle(
        scene.scale.width / 2,
        scene.scale.height / 2,
        scene.scale.width,
        scene.scale.height,
        0x03050a,
        0.72,
      )
      .setInteractive()

    const panel = scene.add
      .rectangle(
        scene.scale.width / 2,
        scene.scale.height / 2,
        scene.scale.width - 70,
        scene.scale.height - 55,
        0x0b101b,
        0.98,
      )
      .setStrokeStyle(
        3,
        0xb99b58,
        0.95,
      )

    const title = scene.add
      .text(
        72,
        48,
        'RANGER INVENTORY',
        {
          fontFamily:
            'Arial, sans-serif',
          fontSize: '25px',
          fontStyle: 'bold',
          color: '#f0d789',
        },
      )

    const subtitle = scene.add
      .text(
        72,
        81,
        'Tap an item to inspect it',
        {
          fontFamily:
            'Arial, sans-serif',
          fontSize: '14px',
          color: '#8fa8a2',
        },
      )

    const closeButton = scene.add
      .rectangle(
        scene.scale.width - 92,
        67,
        58,
        44,
        0x6f3341,
        0.95,
      )
      .setStrokeStyle(
        2,
        0xe59a9a,
      )
      .setInteractive()

    const closeText = scene.add
      .text(
        scene.scale.width - 92,
        67,
        'X',
        {
          fontFamily:
            'Arial, sans-serif',
          fontSize: '22px',
          fontStyle: 'bold',
          color: '#ffffff',
        },
      )
      .setOrigin(0.5)

    const detailsPanel = scene.add
      .rectangle(
        948,
        357,
        500,
        500,
        0x111927,
        0.96,
      )
      .setStrokeStyle(
        2,
        0x58677d,
      )

    this.statusText = scene.add
      .text(
        720,
        575,
        '',
        {
          fontFamily:
            'Arial, sans-serif',
          fontSize: '15px',
          color: '#e7cb7a',
          wordWrap: {
            width: 450,
          },
        },
      )

    this.container.add([
      blocker,
      panel,
      title,
      subtitle,
      detailsPanel,
      closeButton,
      closeText,
      this.statusText,
    ])

    closeButton.on(
      'pointerdown',
      () => {
        this.close()
      },
    )
  }

  toggle() {
    if (this.opened) {
      this.close()
    } else {
      this.open()
    }
  }

  open() {
    this.opened = true
    this.statusText.setText('')
    this.refresh()
    this.container.setVisible(true)

    this.callbacks
      .onVisibilityChanged(true)
  }

  close() {
    this.opened = false
    this.container.setVisible(false)

    this.callbacks
      .onVisibilityChanged(false)
  }

  refresh() {
    for (
      const object of
        this.dynamicObjects
    ) {
      object.destroy()
    }

    this.dynamicObjects.length = 0

    const stacks =
      this.inventory.getStacks()

    if (
      this.selectedItemId &&
      !stacks.some(
        (stack) =>
          stack.itemId ===
          this.selectedItemId,
      )
    ) {
      this.selectedItemId =
        undefined
    }

    if (
      !this.selectedItemId &&
      stacks.length > 0
    ) {
      this.selectedItemId =
        stacks[0]?.itemId
    }

    this.renderCapacity()
    this.renderSlots(stacks)
    this.renderDetails()
  }

  private renderCapacity() {
    const text = this.scene.add
      .text(
        480,
        78,
        `Slots ${this.inventory.getUsedSlots()} / ${this.inventory.getCapacity()}`,
        {
          fontFamily:
            'Arial, sans-serif',
          fontSize: '15px',
          color: '#c7b8e9',
        },
      )

    this.addDynamic(text)
  }

  private renderSlots(
    stacks: ReturnType<
      InventorySystem['getStacks']
    >,
  ) {
    const startX = 76
    const startY = 122

    const cellWidth = 116
    const cellHeight = 76

    const columns = 5

    for (
      let index = 0;
      index <
        this.inventory.getCapacity();
      index += 1
    ) {
      const column =
        index % columns

      const row =
        Math.floor(
          index / columns,
        )

      const x =
        startX +
        column * cellWidth

      const y =
        startY +
        row * cellHeight

      const stack =
        stacks[index]

      const definition =
        stack
          ? getItemDefinition(
              stack.itemId,
            )
          : undefined

      const selected =
        stack?.itemId ===
        this.selectedItemId

      const borderColor =
        definition
          ? this.getRarityColor(
              definition.rarity,
            )
          : 0x394454

      const slot = this.scene.add
        .rectangle(
          x + 52,
          y + 31,
          104,
          61,
          selected
            ? 0x273248
            : 0x151e2c,
          0.98,
        )
        .setStrokeStyle(
          selected
            ? 4
            : 2,
          borderColor,
          selected
            ? 1
            : 0.75,
        )

      this.addDynamic(slot)

      if (!stack || !definition) {
        const empty =
          this.scene.add
            .text(
              x + 52,
              y + 31,
              '—',
              {
                fontFamily:
                  'Arial, sans-serif',
                fontSize: '17px',
                color: '#4f5c6d',
              },
            )
            .setOrigin(0.5)

        this.addDynamic(empty)
        continue
      }

      slot.setInteractive()

      slot.on(
        'pointerdown',
        () => {
          this.selectedItemId =
            stack.itemId

          this.statusText.setText('')
          this.refresh()
        },
      )

      const name =
        this.scene.add
          .text(
            x + 7,
            y + 9,
            definition.name,
            {
              fontFamily:
                'Arial, sans-serif',
              fontSize: '12px',
              fontStyle: 'bold',
              color: '#edf1f5',
              wordWrap: {
                width: 90,
              },
            },
          )

      const quantity =
        this.scene.add
          .text(
            x + 94,
            y + 48,
            `x${stack.quantity}`,
            {
              fontFamily:
                'Arial, sans-serif',
              fontSize: '12px',
              fontStyle: 'bold',
              color: '#f0d789',
            },
          )
          .setOrigin(1, 1)

      this.addDynamic(name)
      this.addDynamic(quantity)
    }
  }

  private renderDetails() {
    if (!this.selectedItemId) {
      const empty =
        this.scene.add
          .text(
            720,
            145,
            'Your bag is empty.',
            {
              fontFamily:
                'Arial, sans-serif',
              fontSize: '20px',
              color: '#8fa0ae',
            },
          )

      this.addDynamic(empty)
      return
    }

    const definition =
      getItemDefinition(
        this.selectedItemId,
      )

    if (!definition) {
      return
    }

    const quantity =
      this.inventory.countItem(
        definition.id,
      )

    const rarityColor =
      this.getRarityCss(
        definition.rarity,
      )

    const name =
      this.scene.add
        .text(
          720,
          135,
          definition.name,
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize: '28px',
            fontStyle: 'bold',
            color: rarityColor,
          },
        )

    const rarity =
      this.scene.add
        .text(
          720,
          178,
          `${definition.rarity.toUpperCase()} • ${definition.category.toUpperCase()}`,
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize: '15px',
            fontStyle: 'bold',
            color: rarityColor,
          },
        )

    const amount =
      this.scene.add
        .text(
          720,
          210,
          `Owned: ${quantity}`,
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize: '16px',
            color: '#d7dde5',
          },
        )

    const description =
      this.scene.add
        .text(
          720,
          255,
          definition.description,
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize: '17px',
            color: '#bec8d3',
            lineSpacing: 8,
            wordWrap: {
              width: 440,
            },
          },
        )

    this.addDynamic(name)
    this.addDynamic(rarity)
    this.addDynamic(amount)
    this.addDynamic(description)

    if (
      definition.category ===
        'consumable'
    ) {
      const useButton =
        this.scene.add
          .rectangle(
            815,
            500,
            190,
            58,
            0x367b66,
            0.96,
          )
          .setStrokeStyle(
            3,
            0x9ee0c8,
          )
          .setInteractive()

      const useText =
        this.scene.add
          .text(
            815,
            500,
            'USE ITEM',
            {
              fontFamily:
                'Arial, sans-serif',
              fontSize: '17px',
              fontStyle: 'bold',
              color: '#ffffff',
            },
          )
          .setOrigin(0.5)

      useButton.on(
        'pointerdown',
        () => {
          const result =
            this.callbacks
              .onUseItem(
                definition.id,
              )

          this.statusText.setText(
            result.message,
          )

          this.refresh()
        },
      )

      this.addDynamic(useButton)
      this.addDynamic(useText)
      return
    }

    const note =
      this.scene.add
        .text(
          720,
          490,
          definition.category ===
            'weapon'
            ? 'Equipment support arrives in the next progression batch.'
            : 'This item is not directly usable.',
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize: '15px',
            color: '#8997a8',
            wordWrap: {
              width: 430,
            },
          },
        )

    this.addDynamic(note)
  }

  private addDynamic(
    object: Phaser.GameObjects.GameObject,
  ) {
    this.dynamicObjects.push(
      object,
    )

    this.container.add(object)
  }

  private getRarityColor(
    rarity: ItemRarity,
  ) {
    switch (rarity) {
      case 'uncommon':
        return 0x68d391
      case 'rare':
        return 0x61a8ff
      case 'epic':
        return 0xb67cff
      case 'legendary':
        return 0xffc857
      default:
        return 0x9fa9b5
    }
  }

  private getRarityCss(
    rarity: ItemRarity,
  ) {
    switch (rarity) {
      case 'uncommon':
        return '#68d391'
      case 'rare':
        return '#61a8ff'
      case 'epic':
        return '#b67cff'
      case 'legendary':
        return '#ffc857'
      default:
        return '#c8d0d9'
    }
  }
}
