import Phaser from 'phaser'

import {
  ReconstructedLogresEncounterAuthority,
} from '../../encounter/ReconstructedLogresEncounterAuthority'

import {
  ReconstructedLogresBattleEntryBridge,
} from '../../encounter/ReconstructedLogresBattleEntryBridge'

import {
  findReconstructedLogresFieldPath,
} from '../LogresFieldPathfinder'

import type {
  LogresFieldNavigationTile,
} from '../LogresFieldNavigation'

import type {
  LogresFieldMovementController,
} from './LogresFieldMovementController'

export class LogresFieldEncounterController {
  private readonly scene:
    Phaser.Scene

  private readonly movement:
    LogresFieldMovementController

  private encounterTile:
    Readonly<LogresFieldNavigationTile> | null =
      null

  private approachActiveValue =
    false

  constructor(
    scene:
      Phaser.Scene,
    movement:
      LogresFieldMovementController,
  ) {
    this.scene =
      scene

    this.movement =
      movement
  }

  get isApproachActive() {
    return this.approachActiveValue
  }

  bindEncounterTile(
    tile:
      Readonly<LogresFieldNavigationTile> | null,
  ) {
    this.encounterTile =
      tile
  }

  approach() {
    const runtime =
      this.movement.runtime

    const currentTile =
      this.movement.currentTile

    if (
      this.approachActiveValue ||
      !runtime ||
      !currentTile ||
      !this.encounterTile
    ) {
      return
    }

    const path =
      findReconstructedLogresFieldPath(
        currentTile,
        this.encounterTile,
        runtime
          .movement
          .tileAt,
      )

    if (!path) {
      return
    }

    this.approachActiveValue =
      true

    this.movement.stop()

    this.movement.walkPath(
      path.coords,
      1,
      () => {
        this.launch()
      },
    )
  }

  private launch() {
    if (
      !this.encounterTile
    ) {
      this.approachActiveValue =
        false

      return
    }

    const encounter =
      new ReconstructedLogresEncounterAuthority({
        encounterKey:
          'reconstructed-tutorial-field-encounter',

        areaRef:
          null,

        symbolRef:
          null,

        mapPosition:
          null,

        rawEntryState:
          null,

        eligibility: {
          globalEncounterAllowed:
            true,

          encounterEnabled:
            true,

          entryStateEligible:
            true,

          questAllowsEncounter:
            true,

          distanceEligible:
            true,
        },
      })

    const bridge =
      new ReconstructedLogresBattleEntryBridge(
        encounter,
      )

    const intent =
      bridge.requestEntry()

    const launch =
      bridge.recordBattleInitialized({
        battleSystemRef:
          null,

        battleKit: {
          weaponPanels: [
            {
              unlocked:
                true,

              weaponRef:
                'reconstructed-tutorial-weapon',

              normalSkillRef:
                'reconstructed-normal-attack',

              specialSkillRef:
                null,

              specialEpCost:
                null,
            },
          ],

          selectedWeaponSlot:
            0,

          currentEp:
            0,

          epCap:
            null,
        },
      })

    this.scene.registry.set(
      'logres.playableField.encounterIntent',
      intent,
    )

    this.scene.registry.set(
      'logres.playableField.encounterAuthority',
      encounter.snapshot(),
    )

    this.scene.registry.set(
      'logres.playableField.battleLaunchProvenance',
      launch.provenance,
    )

    this.scene.registry.set(
      'logres.playableField.battleKitIdentityProvenance',
      'RECONSTRUCTED_LOCAL_IDENTIFIERS',
    )

    this.scene.scene.start(
      launch.sceneKey,
      launch.sceneData,
    )
  }
}
