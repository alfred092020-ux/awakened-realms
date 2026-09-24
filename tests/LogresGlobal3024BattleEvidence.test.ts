import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_GLOBAL_3024_BATTLE_ARCHITECTURE,
  LOGRES_GLOBAL_3024_BATTLE_CLIENT_RESPONSE_SURFACE,
  LOGRES_GLOBAL_3024_BATTLE_COMPONENTS,
  LOGRES_GLOBAL_3024_BATTLE_EVENT_FAMILIES,
  LOGRES_GLOBAL_3024_BATTLE_SERVER_MESSAGES,
  LOGRES_GLOBAL_3024_BATTLE_SOURCE,
  LOGRES_GLOBAL_3024_BATTLE_SURFACE_COUNTS,
  LOGRES_GLOBAL_3024_BATTLE_UNRESOLVED,
} from '../src/game/logres/battle/LogresGlobal3024BattleEvidence'

describe(
  'Global 3.0.24 native battle evidence',
  () => {
    it(
      'anchors the reconstruction to the original Global binary',
      () => {
        expect(
          LOGRES_GLOBAL_3024_BATTLE_SOURCE,
        ).toEqual({
          clientVersion: '3.0.24',
          libgameArm64Sha256:
            'bf777cfa413b95627152246e9048af5c5fbc9c53e3c49141421360d6e86c814f',
          provenance:
            'CONFIRMED_ORIGINAL_GLOBAL_3_0_24_SYMBOL_SURFACE',
        })

        expect(
          LOGRES_GLOBAL_3024_BATTLE_SURFACE_COUNTS,
        ).toEqual({
          networkBattleMethods: 79,
          sequencerEventReceivers: 42,
          boutSystemMethods: 65,
          battleSystemMethods: 41,
          epManagerAndBeadMethods: 36,
        })
      },
    )

    it(
      'preserves the native battle -> bout -> sequencer authority boundary',
      () => {
        expect(
          LOGRES_GLOBAL_3024_BATTLE_COMPONENTS,
        ).toEqual(
          expect.arrayContaining([
            'BattleSystem',
            'BattleProtocolProcessor',
            'BoutSystem',
            'BoutSequencer',
            'BoutEPManager',
          ]),
        )

        expect(
          LOGRES_GLOBAL_3024_BATTLE_ARCHITECTURE,
        ).toMatchObject({
          topLevelLifecycle:
            'BattleSystem',
          activeBoutLifecycle:
            'BoutSystem',
          eventOrdering:
            'BoutSequencer',
          authorityModel:
            'server-authored-sequenced-events',
        })
      },
    )

    it(
      'records skill requests separately from server-authored execution events',
      () => {
        expect(
          LOGRES_GLOBAL_3024_BATTLE_CLIENT_RESPONSE_SURFACE,
        ).toContain(
          'C_GMCL_BATTLE_USE_SKILL_REQ_Response',
        )

        expect(
          LOGRES_GLOBAL_3024_BATTLE_EVENT_FAMILIES
            .skills,
        ).toEqual(
          expect.arrayContaining([
            'CHARGE_SKILL',
            'EXECUTE_SKILL',
            'RECAST_SKILL',
            'SELECT_REACTION_SKILL',
            'EXECUTE_REACTION_SKILL',
          ]),
        )
      },
    )

    it(
      'keeps targeting, gauges, status effects, death/drop and result as sequenced server projections',
      () => {
        expect(
          LOGRES_GLOBAL_3024_BATTLE_EVENT_FAMILIES
            .targeting,
        ).toEqual([
          'CHAR_TARGET_LOCK',
          'CHAR_TARGET_UNLOCK',
        ])

        expect(
          LOGRES_GLOBAL_3024_BATTLE_EVENT_FAMILIES
            .gauges,
        ).toEqual([
          'GENERATE_GAUGE',
          'UPDATE_GAUGE',
          'DELETE_GAUGE',
        ])

        expect(
          LOGRES_GLOBAL_3024_BATTLE_EVENT_FAMILIES
            .lifeAndRewards,
        ).toEqual(
          expect.arrayContaining([
            'DEAD',
            'REVIVE',
            'DROP',
            'BOUT_RESULT',
            'BOUT_FINISH',
          ]),
        )

        expect(
          LOGRES_GLOBAL_3024_BATTLE_SERVER_MESSAGES,
        ).toContain(
          'S_GMCL_BATTLE_RESULT',
        )
      },
    )

    it(
      'does not turn unresolved server formulas into client facts',
      () => {
        expect(
          LOGRES_GLOBAL_3024_BATTLE_ARCHITECTURE
            .rewardModel,
        ).toBe(
          'server-payload-driven-drop-and-result-events',
        )

        expect(
          LOGRES_GLOBAL_3024_BATTLE_UNRESOLVED,
        ).toEqual(
          expect.arrayContaining([
            'server-side damage formulas',
            'exact cooldown and recast values',
            'exact reward quantities and roll tables',
          ]),
        )
      },
    )
  },
)
