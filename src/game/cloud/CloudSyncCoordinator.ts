import {
  CloudSaveService,
} from './CloudSaveService'

import {
  MetaSaveSystem,
} from '../meta/MetaSaveSystem'

export type CloudSyncStatus =
  | 'guest'
  | 'uploaded'
  | 'downloaded'
  | 'unchanged'

export interface CloudSyncResult {
  status:
    CloudSyncStatus

  updatedAt:
    number
}

export class CloudSyncCoordinator {
  private readonly cloud:
    CloudSaveService

  private readonly saves:
    MetaSaveSystem

  constructor(
    cloud =
      new CloudSaveService(),

    saves =
      new MetaSaveSystem(),
  ) {
    this.cloud =
      cloud

    this.saves =
      saves
  }

  async sync():
    Promise<
      CloudSyncResult
    > {
    if (
      !this.cloud
        .getAccount()
    ) {
      return {
        status:
          'guest',

        updatedAt:
          this.saves
            .getUpdatedAt(),
      }
    }

    const local =
      this.saves.load()

    const localUpdatedAt =
      this.saves
        .getUpdatedAt()

    const remote =
      await this.cloud
        .loadMeta()

    if (!remote) {
      const updatedAt =
        Math.max(
          localUpdatedAt,
          Date.now(),
        )

      this.saves.save(
        local,
        updatedAt,
      )

      await this.cloud
        .saveMeta(
          local,
          updatedAt,
        )

      return {
        status:
          'uploaded',

        updatedAt,
      }
    }

    if (
      remote.updatedAt >
      localUpdatedAt
    ) {
      this.saves.save(
        remote.state,
        remote.updatedAt,
      )

      return {
        status:
          'downloaded',

        updatedAt:
          remote.updatedAt,
      }
    }

    if (
      localUpdatedAt >
      remote.updatedAt
    ) {
      await this.cloud
        .saveMeta(
          local,
          localUpdatedAt,
        )

      return {
        status:
          'uploaded',

        updatedAt:
          localUpdatedAt,
      }
    }

    return {
      status:
        'unchanged',

      updatedAt:
        localUpdatedAt,
    }
  }
}
