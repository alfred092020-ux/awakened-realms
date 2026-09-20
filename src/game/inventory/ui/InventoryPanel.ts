import Phaser from 'phaser'

import {
  getItemDefinition,
} from '../ItemCatalog'

import type {
  InventorySystem,
} from '../InventorySystem'

import type {
  EquipmentSystem,
} from '../EquipmentSystem'

import type {
  EquipmentSlot,
  ItemDefinition,
  ItemRarity,
} from '../ItemTypes'

export interface InventoryPanelResult {
  message: string
}

export interface InventoryPanelCallbacks {
  onUseItem: (
    itemId: string,
  ) => InventoryPanelResult

  onEquipItem: (
    itemId: string,
  ) => InventoryPanelResult

  onUnequipSlot: (
    slot: EquipmentSlot,
  ) => InventoryPanelResult

  onVisibilityChanged: (
    visible: boolean,
  ) => void
}

export class InventoryPanel {
  private readonly scene:
    Phaser.Scene

  private readonly inventory:
    InventorySystem

  private readonly equipment:
    EquipmentSystem

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
    equipment: EquipmentSystem,
    callbacks: InventoryPanelCallbacks,
  ) {
    this.scene = scene
    this.inventory = inventory
    this.equipment = equipment
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
      )

    const title = scene.add.text(
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

    const subtitle = scene.add.text(
      72,
      81,
      'Tap an item to inspect or equip it',
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
        625,
        '',
        {
          fontFamily:
            'Arial, sans-serif',
          fontSize: '15px',
          color: '#e7cb7a',
          wordWrap: {
            width: 440,
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
      () => this.close(),
    )
  }

  toggle() {
    if (this.opened) {
      this.close()
      return
    }

    this.open()
  }

  open() {
    this.opened = true
    this.statusText.setText('')
    this.refresh()

    this.container.setVisible(
      true,
    )

    this.callbacks
      .onVisibilityChanged(
        true,
      )
  }

  close() {
    this.opened = false

    this.container.setVisible(
      false,
    )

    this.callbacks
      .onVisibilityChanged(
        false,
      )
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
    this.renderEquipment()
    this.renderDetails()
  }

  private renderCapacity() {
    this.addDynamic(
      this.scene.add.text(
        470,
        78,
        `Slots ${this.inventory.getUsedSlots()} / ${this.inventory.getCapacity()}`,
        {
          fontFamily:
            'Arial, sans-serif',
          fontSize: '15px',
          color: '#c7b8e9',
        },
      ),
    )
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
          definition
            ? this.getRarityColor(
                definition.rarity,
              )
            : 0x394454,
          0.85,
        )

      this.addDynamic(slot)

      if (
        !stack ||
        !definition
      ) {
        this.addDynamic(
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
            .setOrigin(0.5),
        )

        continue
      }

      slot.setInteractive()

      slot.on(
        'pointerdown',
        () => {
          this.selectedItemId =
            stack.itemId

          this.statusText
            .setText('')

          this.refresh()
        },
      )

      this.addDynamic(
        this.scene.add.text(
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
        ),
      )

      this.addDynamic(
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
          .setOrigin(1, 1),
      )
    }
  }

  private renderEquipment() {
    this.addDynamic(
      this.scene.add.text(
        720,
        120,
        'EQUIPMENT',
        {
          fontFamily:
            'Arial, sans-serif',
          fontSize: '18px',
          fontStyle: 'bold',
          color: '#f0d789',
        },
      ),
    )

    const slots:
      EquipmentSlot[] = [
        'weapon',
        'armor',
        'accessory',
      ]

    slots.forEach(
      (slot, index) => {
        const y =
          157 +
          index * 50

        const itemId =
          this.equipment
            .getEquippedItem(
              slot,
            )

        const definition =
          itemId
            ? getItemDefinition(
                itemId,
              )
            : undefined

        const row =
          this.scene.add
            .rectangle(
              940,
              y,
              440,
              40,
              0x172131,
              0.98,
            )
            .setStrokeStyle(
              2,
              definition
                ? this.getRarityColor(
                    definition.rarity,
                  )
                : 0x405066,
            )

        this.addDynamic(row)

        this.addDynamic(
          this.scene.add
            .text(
              730,
              y,
              slot.toUpperCase(),
              {
                fontFamily:
                  'Arial, sans-serif',
                fontSize: '12px',
                fontStyle: 'bold',
                color: '#8fa8b7',
              },
            )
            .setOrigin(0, 0.5),
        )

        this.addDynamic(
          this.scene.add
            .text(
              820,
              y,
              definition
                ? `${definition.name} ${this.getEquipmentBonusText(definition)}`
                : 'Empty',
              {
                fontFamily:
                  'Arial, sans-serif',
                fontSize: '13px',
                color: definition
                  ? '#e8edf2'
                  : '#667487',
              },
            )
            .setOrigin(0, 0.5),
        )

        if (!definition) {
          return
        }

        const removeButton =
          this.scene.add
            .rectangle(
              1135,
              y,
              82,
              28,
              0x713847,
              0.96,
            )
            .setStrokeStyle(
              2,
              0xdf909e,
            )
            .setInteractive()

        const removeText =
          this.scene.add
            .text(
              1135,
              y,
              'REMOVE',
              {
                fontFamily:
                  'Arial, sans-serif',
                fontSize: '11px',
                fontStyle: 'bold',
                color: '#ffffff',
              },
            )
            .setOrigin(0.5)

        removeButton.on(
          'pointerdown',
          () => {
            const result =
              this.callbacks
                .onUnequipSlot(
                  slot,
                )

            this.statusText
              .setText(
                result.message,
              )

            this.refresh()
          },
        )

        this.addDynamic(
          removeButton,
        )

        this.addDynamic(
          removeText,
        )
      },
    )
  }

  private renderDetails() {
    if (!this.selectedItemId) {
      this.addDynamic(
        this.scene.add.text(
          720,
          325,
          'Select an item from the bag.',
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize: '20px',
            color: '#8fa0ae',
          },
        ),
      )

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

    this.addDynamic(
      this.scene.add.text(
        720,
        310,
        definition.name,
        {
          fontFamily:
            'Arial, sans-serif',
          fontSize: '28px',
          fontStyle: 'bold',
          color: rarityColor,
        },
      ),
    )

    this.addDynamic(
      this.scene.add.text(
        720,
        348,
        `${definition.rarity.toUpperCase()} • ${definition.category.toUpperCase()}`,
        {
          fontFamily:
            'Arial, sans-serif',
          fontSize: '15px',
          fontStyle: 'bold',
          color: rarityColor,
        },
      ),
    )

    this.addDynamic(
      this.scene.add.text(
        720,
        378,
        `Owned: ${quantity}`,
        {
          fontFamily:
            'Arial, sans-serif',
          fontSize: '16px',
          color: '#d7dde5',
        },
      ),
    )

    this.addDynamic(
      this.scene.add.text(
        720,
        410,
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
      ),
    )

    const equipmentBonus =
      this.getEquipmentBonusText(
        definition,
      )

    if (equipmentBonus) {
      this.addDynamic(
        this.scene.add.text(
          720,
          475,
          `Bonus: ${equipmentBonus}`,
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize: '15px',
            fontStyle: 'bold',
            color: '#9bd8ad',
          },
        ),
      )
    }

    if (
      definition.equipmentSlot
    ) {
      this.renderActionButton(
        'EQUIP',
        0x456e9d,
        0x9fc8f5,
        () => {
          const result =
            this.callbacks
              .onEquipItem(
                definition.id,
              )

          this.statusText
            .setText(
              result.message,
            )

          this.refresh()
        },
      )

      return
    }

    if (
      definition.category ===
      'consumable'
    ) {
      this.renderActionButton(
        'USE ITEM',
        0x367b66,
        0x9ee0c8,
        () => {
          const result =
            this.callbacks
              .onUseItem(
                definition.id,
              )

          this.statusText
            .setText(
              result.message,
            )

          this.refresh()
        },
      )

      return
    }

    this.addDynamic(
      this.scene.add.text(
        720,
        525,
        'This item is not directly usable.',
        {
          fontFamily:
            'Arial, sans-serif',
          fontSize: '15px',
          color: '#8997a8',
        },
      ),
    )
  }

  private renderActionButton(
    label: string,
    fillColor: number,
    borderColor: number,
    onPress: () => void,
  ) {
    const button =
      this.scene.add
        .rectangle(
          815,
          545,
          190,
          52,
          fillColor,
          0.96,
        )
        .setStrokeStyle(
          3,
          borderColor,
        )
        .setInteractive()

    const text =
      this.scene.add
        .text(
          815,
          545,
          label,
          {
            fontFamily:
              'Arial, sans-serif',
            fontSize: '17px',
            fontStyle: 'bold',
            color: '#ffffff',
          },
        )
        .setOrigin(0.5)

    button.on(
      'pointerdown',
      onPress,
    )

    this.addDynamic(button)
    this.addDynamic(text)
  }

  private getEquipmentBonusText(
    definition: ItemDefinition,
  ) {
    const bonuses: string[] = []

    if (
      definition.attackBonus
    ) {
      bonuses.push(
        `+${definition.attackBonus} ATK`,
      )
    }

    if (
      definition.maxHpBonus
    ) {
      bonuses.push(
        `+${definition.maxHpBonus} HP`,
      )
    }

    return bonuses.join('  ')
  }

  private addDynamic(
    object:
      Phaser.GameObjects.GameObject,
  ) {
    this.dynamicObjects.push(
      object,
    )

    this.container.add(
      object,
    )
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
