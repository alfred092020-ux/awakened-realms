import Phaser from 'phaser'

import {
  LOGRES_ASSETS,
  preloadLogresAssets,
} from '../logres/ui/LogresRuntimeAssets'

import {
  logresDevMs,
} from '../logres/LogresDevSettings'

interface WorldSelectStrings {
  world_select?: {
    world?: string
    open_date?: string
  }
}

interface LogresWorldEntry {
  id: number
  name: string
  openDate?: string
  group: number
}

/*
 * World identity and population are
 * server-owned in the original client.
 *
 * This one-world catalog is replacement
 * server data, not a claim about the
 * historical production world list.
 */
const RECONSTRUCTED_WORLDS:
  LogresWorldEntry[] = [
    {
      id: 1,
      name: '1',
      group: 0,
    },
  ]

const WORLD_GROUP_ASSETS = [
  LOGRES_ASSETS
    .worldSelect02,
  LOGRES_ASSETS
    .worldSelect03,
  LOGRES_ASSETS
    .worldSelect04,
  LOGRES_ASSETS
    .worldSelect05,
  LOGRES_ASSETS
    .worldSelect06,
  LOGRES_ASSETS
    .worldSelect07,
] as const

export class LogresWorldSelectScene
  extends Phaser.Scene {
  private selecting =
    false

  constructor() {
    super(
      'LogresWorldSelectScene',
    )
  }

  preload() {
    preloadLogresAssets(
      this,
    )

    this.load.json(
      'logres-world-select-en',
      '/__logres_ref/config/global/world_select_strings.json',
    )
  }

  create() {
    const strings =
      this.cache.json.get(
        'logres-world-select-en',
      ) as
        WorldSelectStrings |
        undefined

    const worldLabel =
      strings
        ?.world_select
        ?.world

    const openDateLabel =
      strings
        ?.world_select
        ?.open_date

    if (!worldLabel) {
      console.error(
        'Global Logres world label is missing',
      )

      return
    }

    if (
      RECONSTRUCTED_WORLDS.some(
        (world) =>
          Boolean(
            world.openDate,
          ),
      ) &&
      !openDateLabel
    ) {
      console.error(
        'Global Logres open-date label is missing',
      )

      return
    }

    /*
     * world_select01 is the original
     * 720 x 360 world-selection subject
     * artwork. Native
     * ReleaseScene_WorldSelector fades
     * this subject in over 0.2 seconds.
     */
    const subject =
      this.add
        .image(
          360,
          180,
          LOGRES_ASSETS
            .worldSelect
            .key,
        )
        .setAlpha(
          0,
        )

    this.tweens.add({
      targets:
        subject,

      alpha:
        1,

      duration:
        logresDevMs(
          200,
        ),

      onComplete:
        () => {
          this.openWorldViews(
            worldLabel,
            openDateLabel,
            subject,
          )
        },
    })

    this.registry.set(
      'logres.server.worldCatalogSource',
      'RECONSTRUCTED',
    )
  }

  private openWorldViews(
    worldLabel: string,
    openDateLabel: string | undefined,
    subject:
      Phaser.GameObjects.Image,
  ) {
    RECONSTRUCTED_WORLDS
      .forEach(
        (
          world,
          index,
        ) => {
          const asset =
            WORLD_GROUP_ASSETS[
              Math.min(
                world.group,
                WORLD_GROUP_ASSETS
                  .length -
                  1,
              )
            ]

          /*
           * Each native WorldView uses
           * the extracted 720 x 256
           * world-group artwork.
           *
           * The first view begins after
           * 0.25 sec; subsequent views
           * are staggered by 0.10 sec.
           */
          const cardY =
            360 +
            128 +
            index *
              256

          const card =
            this.add
              .container(
                360,
                cardY,
              )
              .setAlpha(
                0,
              )
              .setScale(
                0,
              )
              .setSize(
                720,
                256,
              )

          card.add(
            this.add.image(
              0,
              0,
              asset.key,
            ),
          )

          card.add(
            this.add
              .text(
                100,
                -35,
                `${worldLabel} ${world.name}`,
                {
                  fontFamily:
                    'sans-serif',

                  fontSize:
                    '56px',

                  color:
                    '#ffffff',

                  stroke:
                    '#222222',

                  strokeThickness:
                    5,
                },
              )
              .setOrigin(
                0.5,
              ),
          )

          if (
            world.openDate
          ) {
            card.add(
              this.add
                .text(
                  100,
                  45,
                  `${openDateLabel}: ${world.openDate}`,
                  {
                    fontFamily:
                      'sans-serif',

                    fontSize:
                      '28px',

                    color:
                      '#ffffff',
                  },
                )
                .setOrigin(
                  0.5,
                ),
            )
          }

          card
            .setInteractive(
              new Phaser.Geom.Rectangle(
                -360,
                -128,
                720,
                256,
              ),
              Phaser.Geom.Rectangle.Contains,
            )
            .on(
              'pointerdown',
              () => {
                this.selectWorld(
                  world,
                  card,
                  subject,
                )
              },
            )

          const delay =
            250 +
            index *
              100

          this.time.delayedCall(
            logresDevMs(
              delay,
            ),
            () => {
              /*
               * WorldView::open:
               * fade to visible over 0.10 sec,
               * scale to 1.3 with EaseSineIn,
               * then settle to 1.0 over 0.08 sec.
               */
              this.tweens.add({
                targets:
                  card,

                alpha:
                  1,

                scaleX:
                  1.3,

                scaleY:
                  1.3,

                duration:
                  logresDevMs(
                    100,
                  ),

                ease:
                  'Sine.easeIn',

                onComplete:
                  () => {
                    this.tweens.add({
                      targets:
                        card,

                      scaleX:
                        1,

                      scaleY:
                        1,

                      duration:
                        logresDevMs(
                          80,
                        ),

                      ease:
                        'Sine.easeInOut',
                    })
                  },
              })
            },
          )
        },
      )
  }

  private selectWorld(
    world:
      LogresWorldEntry,

    card:
      Phaser.GameObjects.Container,

    subject:
      Phaser.GameObjects.Image,
  ) {
    if (
      this.selecting
    ) {
      return
    }

    this.selecting =
      true

    this.registry.set(
      'logres.world.selectedId',
      world.id,
    )

    card
      .disableInteractive()

    /*
     * ReleaseScene_WorldSelector fades
     * the subject over 0.2 sec.
     */
    this.tweens.add({
      targets:
        subject,

      alpha:
        0,

      duration:
        logresDevMs(
          200,
        ),
    })

    /*
     * The selected WorldView closes after
     * a 0.5 sec delay. WorldView::close
     * then fades and scales to zero over
     * 0.15 sec before the callback.
     */
    this.time.delayedCall(
      logresDevMs(
        500,
      ),
      () => {
        this.tweens.add({
          targets:
            card,

          alpha:
            0,

          scaleX:
            0,

          scaleY:
            0,

          duration:
            logresDevMs(
              150,
            ),

          onComplete:
            () => {
              this.scene.start(
                'LogresCharacterCreateScene',
              )
            },
        })
      },
    )
  }
}
