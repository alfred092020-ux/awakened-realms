import {
  describe,
  expect,
  it,
  vi,
} from 'vitest'

vi.mock(
  'phaser',
  () => ({
    default: {
      Scene:
        class {},
      Scenes: {
        Events: {
          SHUTDOWN:
            'shutdown',
        },
      },
      Math: {
        Clamp: (
          value: number,
          min: number,
          max: number,
        ) =>
          Math.max(
            min,
            Math.min(
              max,
              value,
            ),
          ),
      },
    },
  }),
)

import {
  LogresBattleScene,
} from '../src/game/scenes/LogresBattleScene'

describe(
  'LogresBattleScene playable completion',
  () => {
    it(
      'stores playable battle completion state after a normal attack command',
      () => {
        const values =
          new Map<string, unknown>([
            [
              'logres.playableBattle.battleStatus',
              'ACTIVE',
            ],
          ])

        const scene =
          new LogresBattleScene() as any

        scene.battleKit = {
          createNormalAttack: () => ({
            type:
              'normal-attack',
            weaponSlot:
              0,
            weaponRef:
              'weapon-1',
            skillRef:
              'normal-1',
          }),
        }

        scene.registry = {
          get: (key) =>
            values.get(
              key,
            ),
          set: (key, value) => {
            values.set(
              key,
              value,
            )
          },
        }

        scene.events = {
          emit: vi.fn(),
        }

        scene.demoStatusText = {
          setText: vi.fn(),
        }
        scene.demoReturnButton =
          {}

        scene.readPlayableBattleInventory =
          () =>
            undefined

        scene.storeCompletedBattle =
          LogresBattleScene.prototype[
            'storeCompletedBattle'
          ].bind(
            scene,
          )

        scene.emitNormalAttack =
          LogresBattleScene.prototype[
            'emitNormalAttack'
          ].bind(
            scene,
          )

        scene.emitNormalAttack()

        expect(
          scene.events.emit,
        ).toHaveBeenCalledWith(
          'logres-battle-command',
          expect.objectContaining({
            type:
              'normal-attack',
          }),
        )

        expect(
          values.get(
            'logres.playableBattle.battleStatus',
          ),
        ).toBe(
          'FIELD_RETURN_READY',
        )

        expect(
          values.get(
            'logres.playableBattle.rewardApplied',
          ),
        ).toBe(
          true,
        )
      },
    )

    it(
      'returns to Millennium Tree with movement marked ready',
      () => {
        const values =
          new Map<string, unknown>([
            [
              'logres.playableBattle.fieldReturn',
              {
                sceneKey:
                  'LogresFieldScene',
                fieldName:
                  'Millennium Tree',
                movementState:
                  'READY',
              },
            ],
          ])

        const setAlpha =
          vi.fn()
        const setInteractive =
          vi.fn()
        const setDepth =
          vi.fn()
        const setOrigin =
          vi.fn()

        let onPointerUp:
          (() => void) | null =
            null

        setAlpha.mockReturnThis()
        setInteractive.mockReturnThis()
        setDepth.mockReturnThis()
        setOrigin.mockReturnThis()

        const textObject = {
          setOrigin,
          setDepth,
          setInteractive,
          on: vi.fn(
            (
              event: string,
              handler: () => void,
            ) => {
              if (
                event ===
                'pointerup'
              ) {
                onPointerUp =
                  handler
              }

              return textObject
            },
          ),
          setAlpha,
        }

        const sceneStart =
          vi.fn()

        const scene =
          new LogresBattleScene() as any

        scene.scale = {
          width:
            720,
        }
        scene.add = {
          text: vi.fn(
            () =>
              textObject,
          ),
        }
        scene.registry = {
          get: (key) =>
            values.get(
              key,
            ),
          set: (key, value) => {
            values.set(
              key,
              value,
            )
          },
        }
        scene.scene = {
          start: sceneStart,
        }
        scene.demoStatusText = {
          setText: vi.fn(),
        }

        scene.storeCompletedBattle =
          LogresBattleScene.prototype[
            'storeCompletedBattle'
          ].bind(
            scene,
          )

        scene.storeCompletedBattle(
          {
            provenance:
              'RECONSTRUCTED',
            flow: {
              provenance:
                'RECONSTRUCTED',
              phase:
                'field-return-ready',
              battleSystemRef:
                null,
              result:
                null,
              reward:
                null,
              fieldOverlay:
                null,
            },
            inventory: {
              provenance:
                'RECONSTRUCTED',
              revision:
                0,
              entries:
                [],
              appliedGrantKeys:
                [],
            },
            rewardApplied:
              false,
            fieldReturn: {
              sceneKey:
                'LogresFieldScene',
              fieldName:
                'Millennium Tree',
              movementState:
                'READY',
            },
          },
          'PLAYABLE_COMMAND_NORMAL_ATTACK',
        )

        expect(
          onPointerUp,
        ).not.toBeNull()

        onPointerUp?.()

        expect(
          values.get(
            'logres.playableField.currentFieldName',
          ),
        ).toBe(
          'Millennium Tree',
        )
        expect(
          values.get(
            'logres.playableField.movementState',
          ),
        ).toBe(
          'READY',
        )
        expect(
          sceneStart,
        ).toHaveBeenCalledWith(
          'LogresFieldScene',
        )
      },
    )
  },
)
