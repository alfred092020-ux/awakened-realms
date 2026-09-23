import {
  execFileSync,
} from 'node:child_process'

import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_PLAYER_ACTOR_PRESENTATION,
  logresPlayerMotionApplication,
  logresPlayerReferenceSex,
  readLogresPlayerGenderFromCharacterCreateRequest,
} from '../src/game/logres/field/LogresPlayerActorPresentation'

describe(
  'Logres player avatar resource evidence',
  () => {
    it(
      'keeps historical Global appearance identity unresolved',
      () => {
        expect(
          LOGRES_PLAYER_ACTOR_PRESENTATION,
        ).toMatchObject({
          source:
            'RECOVERED_CURRENT_JP_PRIVATE_DERIVATIVE',

          bodySelection:
            'RECONSTRUCTED_CURRENT_JP_REFERENCE_BOD_001',

          equipment:
            'NONE',

          historicalGlobalBodyId:
            'UNRESOLVED',

          historicalGlobalEquipmentIds:
            'UNRESOLVED',
        })
      },
    )

    it(
      'reads gender from the exact character-create request tuple without inventing a default',
      () => {
        expect(
          readLogresPlayerGenderFromCharacterCreateRequest([
            0,
            'Novice',
            0,
            1,
            1,
            1,
            2,
            4,
          ]),
        ).toBe(
          0,
        )

        expect(
          readLogresPlayerGenderFromCharacterCreateRequest([
            0,
            'Novice',
            1,
            1,
            1,
            1,
            3,
            5,
          ]),
        ).toBe(
          1,
        )

        expect(
          readLogresPlayerGenderFromCharacterCreateRequest(
            null,
          ),
        ).toBeNull()

        expect(
          readLogresPlayerGenderFromCharacterCreateRequest([
            0,
            'Novice',
            2,
          ]),
        ).toBeNull()
      },
    )

    it(
      'keeps male and female reference-motion evidence distinct',
      () => {
        expect(
          logresPlayerReferenceSex(
            0,
          ),
        ).toBe(
          'm',
        )

        expect(
          logresPlayerReferenceSex(
            1,
          ),
        ).toBe(
          'f',
        )

        expect(
          logresPlayerMotionApplication(
            0,
          ),
        ).toBe(
          'CONFIRMED_CURRENT_JP_RESOURCE',
        )

        expect(
          logresPlayerMotionApplication(
            1,
          ),
        ).toBe(
          'SUPPORTED_INFERENCE_SHARED_HUMANOID_SKELETON',
        )
      },
    )

    it(
      'passes the deterministic avatar hydrator self-test without private packages',
      () => {
        const output =
          execFileSync(
            'python3',
            [
              '-B',
              'scripts/logres/inspect_avatar_resource_paths.py',
              '--self-test',
            ],
            {
              encoding:
                'utf8',
            },
          )

        expect(
          JSON.parse(
            output,
          ),
        ).toMatchObject({
          ok:
            true,

          reference_body_id:
            'bod_001',

          motion_entry:
            'anm_001_m_wat_000.lfla',

          historical_global_appearance:
            'UNRESOLVED',
        })
      },
    )
  },
)
