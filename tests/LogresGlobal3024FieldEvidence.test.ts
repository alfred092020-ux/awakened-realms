import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_GLOBAL_3024_FIELD_ENCOUNTER,
  LOGRES_GLOBAL_3024_FIELD_ENTITIES,
  LOGRES_GLOBAL_3024_FIELD_MOVEMENT,
  LOGRES_GLOBAL_3024_FIELD_RENDERER,
  LOGRES_GLOBAL_3024_FIELD_SOURCE,
  LOGRES_GLOBAL_3024_FIELD_SURFACE_COUNTS,
  LOGRES_GLOBAL_3024_FIELD_UNRESOLVED,
  LOGRES_GLOBAL_3024_FIELD_WARP,
} from '../src/game/logres/field/LogresGlobal3024FieldEvidence'

describe(
  'Global 3.0.24 native field evidence',
  () => {
    it(
      'anchors field evidence to the original Global client',
      () => {
        expect(
          LOGRES_GLOBAL_3024_FIELD_SOURCE,
        ).toEqual({
          clientVersion: '3.0.24',
          libgameArm64Sha256:
            'bf777cfa413b95627152246e9048af5c5fbc9c53e3c49141421360d6e86c814f',
          provenance:
            'CONFIRMED_ORIGINAL_GLOBAL_3_0_24_SYMBOL_SURFACE',
        })

        expect(
          LOGRES_GLOBAL_3024_FIELD_SURFACE_COUNTS,
        ).toMatchObject({
          fieldConstantMethods: 23,
          gameFieldSceneMethods: 34,
          npcDialogueMethods: 37,
          warpMediatorMethods: 21,
        })
      },
    )

    it(
      'preserves the native layered map and coordinate/depth model',
      () => {
        expect(
          LOGRES_GLOBAL_3024_FIELD_RENDERER
            .resourceFamilies,
        ).toEqual(
          expect.arrayContaining([
            'MapTerrainResource',
            'MapInfoResource<InfoChipBin>',
            'MapInfoResource<InfoObjectBin>',
            'MapInfoResource<InfoBorderBin>',
            'MapInfoResource<InfoShadowBin>',
          ]),
        )

        expect(
          LOGRES_GLOBAL_3024_FIELD_RENDERER
            .coordinateSystem,
        ).toEqual(
          expect.arrayContaining([
            'FieldConstant::coordToScreen',
            'FieldConstant::positionToCoord',
            'FieldConstant::depthToZ',
            'FieldConstant::tileContains',
          ]),
        )
      },
    )

    it(
      'keeps local pathfinding separate from server movement projection',
      () => {
        expect(
          LOGRES_GLOBAL_3024_FIELD_MOVEMENT,
        ).toMatchObject({
          pathfinder:
            'pathfinding::SimpleAStar',
          outgoingRequest:
            'C_GMCL_CHAR_MOVE_REQ',
          serverProjection:
            'S_GMCL_CHAR_MOVE_REQ',
          authorityInterpretation:
            'client-computes-path-server-projects-movement',
        })

        expect(
          LOGRES_GLOBAL_3024_FIELD_MOVEMENT
            .outgoingRequestFields,
        ).toContain(
          'gridCoordPath',
        )
      },
    )

    it(
      'keeps NPC/enemy appearance and dialogue at server authority boundaries',
      () => {
        expect(
          LOGRES_GLOBAL_3024_FIELD_ENTITIES,
        ).toMatchObject({
          npcAppear:
            'S_GMCL_NPC_APPEAR',
          enemyAppear:
            'S_GMCL_ENEMY_APPEAR',
          dialogueWindow:
            'NpcDialogueWindow',
          authorityInterpretation:
            'server-projected-field-objects',
        })

        expect(
          LOGRES_GLOBAL_3024_FIELD_ENTITIES
            .npcServerFields,
        ).toEqual(
          expect.arrayContaining([
            'areaUID',
            'mapPos',
            'npcCanTalkRange',
          ]),
        )
      },
    )

    it(
      'models encounter detection as geometric but battle entry as server mediated',
      () => {
        expect(
          LOGRES_GLOBAL_3024_FIELD_ENCOUNTER
            .shapes,
        ).toEqual([
          'character::encounter::shape::Circle',
          'character::encounter::shape::Rect',
        ])

        expect(
          LOGRES_GLOBAL_3024_FIELD_ENCOUNTER,
        ).toMatchObject({
          characterUpdateHook:
            'character::Character::updateEncounter',
          battleEntryResponse:
            'C_GMCL_BATTLE_ENTRY_REQ_Response',
          authorityInterpretation:
            'geometric-client-detection-with-server-battle-entry-boundary',
        })
      },
    )

    it(
      'preserves warp as a server-mediated multi-stage transition',
      () => {
        expect(
          LOGRES_GLOBAL_3024_FIELD_WARP
            .serverSequence,
        ).toEqual([
          'S_GMCL_WARP',
          'S_GMCL_AREA_ENTER',
          'S_GMCL_WARP_FINISH',
        ])

        expect(
          LOGRES_GLOBAL_3024_FIELD_WARP
            .states,
        ).toEqual(
          expect.arrayContaining([
            'WarpInState',
            'WarpInfoReceivedState',
            'WarpOutState',
          ]),
        )

        expect(
          LOGRES_GLOBAL_3024_FIELD_UNRESOLVED,
        ).toContain(
          'exact server battle-entry eligibility formula',
        )
      },
    )
  },
)
