import {
  QUEST_DEFINITIONS,
  QUEST_ORDER,
} from './QuestCatalog'

import type {
  QuestDefinition,
  QuestId,
  QuestInteractionResult,
  QuestProgressResult,
  QuestSaveData,
  QuestState,
  QuestStatus,
} from './QuestTypes'

interface LegacyQuestSave {
  version: 1
  questId: string
  status:
    | 'available'
    | 'active'
    | 'ready'
    | 'completed'
  progress: number
}

export class QuestSystem {
  private readonly storageKey =
    'awakened-realms.quests.v2'

  private readonly legacyStorageKey =
    'awakened-realms.quests.v1'

  private state:
    QuestSaveData

  constructor() {
    this.state =
      this.load()

    if (this.syncUnlocks()) {
      this.save()
    }
  }

  recordEnemyDefeat(
    enemyId: string,
  ): QuestProgressResult {
    for (
      const questId of
      QUEST_ORDER
    ) {
      const definition =
        QUEST_DEFINITIONS[
          questId
        ]

      const quest =
        this.state.quests[
          questId
        ]

      if (
        quest.status !==
          'active' ||
        definition
          .targetEnemyId !==
          enemyId
      ) {
        continue
      }

      quest.progress =
        Math.min(
          definition
            .requiredKills,
          quest.progress + 1,
        )

      const becameReady =
        quest.progress >=
        definition
          .requiredKills

      if (becameReady) {
        quest.status =
          'ready'
      }

      this.save()

      return {
        changed: true,
        becameReady,
        questId,
      }
    }

    return {
      changed: false,
      becameReady: false,
    }
  }

  interact(
    questId: QuestId =
      'meadow-menace',
  ): QuestInteractionResult {
    const definition =
      QUEST_DEFINITIONS[
        questId
      ]

    const quest =
      this.state.quests[
        questId
      ]

    switch (
      quest.status
    ) {
      case 'locked':
        return this.result(
          questId,
          definition
            .lockedMessage,
        )

      case 'available':
        quest.status =
          'active'

        quest.progress = 0

        this.save()

        return {
          ...this.result(
            questId,
            definition
              .acceptMessage,
          ),

          accepted: true,
        }

      case 'active':
        return this.result(
          questId,
          [
            'Keep going, Ranger.',
            `${definition.progressLabel}: ${quest.progress} / ${definition.requiredKills}`,
          ].join('\n'),
        )

      case 'ready':
        quest.status =
          'completed'

        this.syncUnlocks()
        this.save()

        return {
          questId,

          message:
            definition
              .readyMessage,

          accepted: false,
          claimed: true,

          rewardCoins:
            definition
              .rewardCoins,

          rewardItems:
            definition
              .rewardItems.map(
                (reward) => ({
                  ...reward,
                }),
              ),
        }

      case 'completed':
        return this.result(
          questId,
          definition
            .completedMessage,
        )
    }
  }

  getDefinition(
    questId: QuestId =
      'meadow-menace',
  ): QuestDefinition {
    return QUEST_DEFINITIONS[
      questId
    ]
  }

  getStatus(
    questId: QuestId =
      'meadow-menace',
  ): QuestStatus {
    return this.state
      .quests[questId]
      .status
  }

  getProgress(
    questId: QuestId =
      'meadow-menace',
  ) {
    const definition =
      QUEST_DEFINITIONS[
        questId
      ]

    return Math.min(
      this.state
        .quests[questId]
        .progress,

      definition
        .requiredKills,
    )
  }

  getTrackedQuestId():
    QuestId {
    const ready =
      QUEST_ORDER.find(
        (questId) =>
          this.getStatus(
            questId,
          ) === 'ready',
      )

    if (ready) {
      return ready
    }

    const active =
      QUEST_ORDER.find(
        (questId) =>
          this.getStatus(
            questId,
          ) === 'active',
      )

    if (active) {
      return active
    }

    const available =
      QUEST_ORDER.find(
        (questId) =>
          this.getStatus(
            questId,
          ) ===
          'available',
      )

    if (available) {
      return available
    }

    return 'moonveil-hunt'
  }

  getTrackerText() {
    const questId =
      this.getTrackedQuestId()

    const definition =
      QUEST_DEFINITIONS[
        questId
      ]

    const quest =
      this.state.quests[
        questId
      ]

    switch (
      quest.status
    ) {
      case 'locked':
        return [
          definition.title
            .toUpperCase(),
          'Locked',
        ].join('\n')

      case 'available':
        return [
          definition.title
            .toUpperCase(),
          `Talk to ${definition.giverName}`,
        ].join('\n')

      case 'active':
        return [
          definition.title
            .toUpperCase(),
          `${definition.progressLabel} ${quest.progress} / ${definition.requiredKills}`,
        ].join('\n')

      case 'ready':
        return [
          definition.title
            .toUpperCase(),
          `Return to ${definition.giverName}`,
        ].join('\n')

      case 'completed':
        return [
          definition.title
            .toUpperCase(),
          'Completed',
        ].join('\n')
    }
  }

  getNpcLabel(
    questId: QuestId =
      'meadow-menace',
  ) {
    const definition =
      QUEST_DEFINITIONS[
        questId
      ]

    const status =
      this.getStatus(
        questId,
      )

    const name =
      definition
        .giverName
        .toUpperCase()

    switch (status) {
      case 'locked':
        return `${name} • GROVE WARDEN`

      case 'available':
        return `${name} • QUEST AVAILABLE`

      case 'active':
        return `${name} • QUEST IN PROGRESS`

      case 'ready':
        return `${name} • QUEST COMPLETE`

      case 'completed':
        return `${name} • FRONTIER ALLY`
    }
  }

  getMarkerState(
    questId: QuestId =
      'meadow-menace',
  ) {
    const status =
      this.getStatus(
        questId,
      )

    switch (status) {
      case 'locked':
        return {
          visible: false,
          text: '',
          color: '#ffffff',
        }

      case 'available':
        return {
          visible: true,
          text: '!',
          color: '#f3d46b',
        }

      case 'active':
        return {
          visible: true,
          text: '•',
          color: '#9fc7ff',
        }

      case 'ready':
        return {
          visible: true,
          text: '?',
          color: '#8ff0a4',
        }

      case 'completed':
        return {
          visible: false,
          text: '',
          color: '#ffffff',
        }
    }
  }

  private result(
    questId: QuestId,
    message: string,
  ): QuestInteractionResult {
    return {
      questId,
      message,

      accepted: false,
      claimed: false,

      rewardCoins: 0,
      rewardItems: [],
    }
  }

  private createDefault():
    QuestSaveData {
    return {
      version: 2,

      quests: {
        'meadow-menace': {
          status:
            'available',
          progress: 0,
        },

        'moonveil-hunt': {
          status:
            'locked',
          progress: 0,
        },
      },
    }
  }

  private syncUnlocks() {
    let changed = false

    for (
      const questId of
      QUEST_ORDER
    ) {
      const definition =
        QUEST_DEFINITIONS[
          questId
        ]

      if (
        !definition
          .requiresQuestId
      ) {
        continue
      }

      const quest =
        this.state.quests[
          questId
        ]

      const requirement =
        this.state.quests[
          definition
            .requiresQuestId
        ]

      if (
        quest.status ===
          'locked' &&
        requirement.status ===
          'completed'
      ) {
        quest.status =
          'available'

        changed = true
      }
    }

    return changed
  }

  private load():
    QuestSaveData {
    try {
      const raw =
        localStorage.getItem(
          this.storageKey,
        )

      if (raw) {
        const parsed:
          unknown =
          JSON.parse(raw)

        if (
          this.isValidSave(
            parsed,
          )
        ) {
          return parsed
        }
      }

      const legacyRaw =
        localStorage.getItem(
          this.legacyStorageKey,
        )

      if (legacyRaw) {
        const legacy:
          unknown =
          JSON.parse(
            legacyRaw,
          )

        if (
          this.isValidLegacy(
            legacy,
          )
        ) {
          const migrated =
            this.migrateLegacy(
              legacy,
            )

          localStorage.setItem(
            this.storageKey,
            JSON.stringify(
              migrated,
            ),
          )

          return migrated
        }
      }
    } catch {
      return this.createDefault()
    }

    return this.createDefault()
  }

  private migrateLegacy(
    legacy:
      LegacyQuestSave,
  ): QuestSaveData {
    const progress =
      Math.max(
        0,
        Math.min(
          5,
          legacy.progress,
        ),
      )

    const first:
      QuestState = {
        status:
          legacy.status,
        progress,
      }

    const second:
      QuestState = {
        status:
          legacy.status ===
            'completed'
            ? 'available'
            : 'locked',

        progress: 0,
      }

    return {
      version: 2,

      quests: {
        'meadow-menace':
          first,

        'moonveil-hunt':
          second,
      },
    }
  }

  private save() {
    try {
      localStorage.setItem(
        this.storageKey,
        JSON.stringify(
          this.state,
        ),
      )
    } catch {
      return
    }
  }

  private isValidSave(
    value: unknown,
  ): value is QuestSaveData {
    if (
      typeof value !==
        'object' ||
      value === null
    ) {
      return false
    }

    const save =
      value as
        Partial<QuestSaveData>

    if (
      save.version !== 2 ||
      typeof save.quests !==
        'object' ||
      save.quests === null
    ) {
      return false
    }

    const quests =
      save.quests as
        Partial<
          Record<
            QuestId,
            QuestState
          >
        >

    return QUEST_ORDER.every(
      (questId) =>
        this.isValidQuestState(
          questId,
          quests[questId],
        ),
    )
  }

  private isValidQuestState(
    questId: QuestId,
    state:
      QuestState |
      undefined,
  ) {
    if (!state) {
      return false
    }

    const status =
      state.status

    const validStatus =
      status === 'locked' ||
      status ===
        'available' ||
      status === 'active' ||
      status === 'ready' ||
      status ===
        'completed'

    const maximum =
      QUEST_DEFINITIONS[
        questId
      ].requiredKills

    return (
      validStatus &&
      Number.isInteger(
        state.progress,
      ) &&
      state.progress >= 0 &&
      state.progress <=
        maximum
    )
  }

  private isValidLegacy(
    value: unknown,
  ): value is LegacyQuestSave {
    if (
      typeof value !==
        'object' ||
      value === null
    ) {
      return false
    }

    const save =
      value as
        Partial<LegacyQuestSave>

    const status =
      save.status

    const validStatus =
      status ===
        'available' ||
      status ===
        'active' ||
      status ===
        'ready' ||
      status ===
        'completed'

    return (
      save.version === 1 &&
      save.questId ===
        'meadow-menace' &&
      validStatus &&
      typeof save.progress ===
        'number' &&
      Number.isInteger(
        save.progress,
      )
    )
  }
}
