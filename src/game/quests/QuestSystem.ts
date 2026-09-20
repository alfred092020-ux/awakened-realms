import {
  MEADOW_MENACE,
} from './QuestCatalog'

import type {
  QuestInteractionResult,
  QuestProgressResult,
  QuestSaveData,
  QuestStatus,
} from './QuestTypes'

export class QuestSystem {
  private readonly storageKey =
    'awakened-realms.quests.v1'

  private state:
    QuestSaveData

  constructor() {
    this.state =
      this.load()
  }

  recordEnemyDefeat(
    enemyId: string,
  ): QuestProgressResult {
    if (
      this.state.status !==
        'active' ||
      enemyId !==
        MEADOW_MENACE
          .targetEnemyId
    ) {
      return {
        changed: false,
        becameReady: false,
      }
    }

    this.state.progress =
      Math.min(
        MEADOW_MENACE
          .requiredKills,
        this.state.progress + 1,
      )

    const becameReady =
      this.state.progress >=
      MEADOW_MENACE
        .requiredKills

    if (becameReady) {
      this.state.status =
        'ready'
    }

    this.save()

    return {
      changed: true,
      becameReady,
    }
  }

  interact():
    QuestInteractionResult {
    switch (
      this.state.status
    ) {
      case 'available':
        this.state.status =
          'active'

        this.state.progress =
          0

        this.save()

        return {
          message:
            'The meadow slimes are multiplying too quickly.\nDefeat 5 slimes and return to me.',
          accepted: true,
          claimed: false,
          rewardCoins: 0,
          rewardItems: [],
        }

      case 'active':
        return {
          message:
            `Keep going, Ranger.\nSlimes defeated: ${this.state.progress} / ${MEADOW_MENACE.requiredKills}`,
          accepted: false,
          claimed: false,
          rewardCoins: 0,
          rewardItems: [],
        }

      case 'ready':
        this.state.status =
          'completed'

        this.save()

        return {
          message:
            'Excellent work. Starfall Meadow is safer because of you.',
          accepted: false,
          claimed: true,
          rewardCoins:
            MEADOW_MENACE
              .rewardCoins,
          rewardItems:
            MEADOW_MENACE
              .rewardItems.map(
                (item) => ({
                  ...item,
                }),
              ),
        }

      case 'completed':
        return {
          message:
            'You handled those slimes well, Ranger.\nI will call on you when another threat appears.',
          accepted: false,
          claimed: false,
          rewardCoins: 0,
          rewardItems: [],
        }
    }
  }

  getStatus():
    QuestStatus {
    return this.state.status
  }

  getProgress() {
    return Math.min(
      this.state.progress,
      MEADOW_MENACE
        .requiredKills,
    )
  }

  getNpcLabel() {
    switch (
      this.state.status
    ) {
      case 'available':
        return 'LYRA • QUEST AVAILABLE'

      case 'active':
        return 'LYRA • QUEST IN PROGRESS'

      case 'ready':
        return 'LYRA • QUEST COMPLETE'

      case 'completed':
        return 'LYRA • STARFALL SCOUT'
    }
  }

  getTrackerText() {
    switch (
      this.state.status
    ) {
      case 'available':
        return [
          'MEADOW MENACE',
          'Talk to Lyra',
        ].join('\n')

      case 'active':
        return [
          'MEADOW MENACE',
          `Defeat slimes ${this.state.progress} / ${MEADOW_MENACE.requiredKills}`,
        ].join('\n')

      case 'ready':
        return [
          'MEADOW MENACE',
          'Return to Lyra',
        ].join('\n')

      case 'completed':
        return [
          'MEADOW MENACE',
          'Completed',
        ].join('\n')
    }
  }

  private createDefault():
    QuestSaveData {
    return {
      version: 1,
      questId:
        MEADOW_MENACE.id,
      status:
        'available',
      progress: 0,
    }
  }

  private load():
    QuestSaveData {
    try {
      const raw =
        localStorage.getItem(
          this.storageKey,
        )

      if (!raw) {
        return this.createDefault()
      }

      const parsed: unknown =
        JSON.parse(raw)

      if (
        !this.isValidSave(
          parsed,
        )
      ) {
        return this.createDefault()
      }

      return {
        ...parsed,
      }
    } catch {
      return this.createDefault()
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

    const validStatus =
      save.status ===
        'available' ||
      save.status ===
        'active' ||
      save.status ===
        'ready' ||
      save.status ===
        'completed'

    return (
      save.version === 1 &&
      save.questId ===
        MEADOW_MENACE.id &&
      validStatus &&
      typeof save.progress ===
        'number' &&
      Number.isInteger(
        save.progress,
      ) &&
      save.progress >= 0 &&
      save.progress <=
        MEADOW_MENACE
          .requiredKills
    )
  }
}
