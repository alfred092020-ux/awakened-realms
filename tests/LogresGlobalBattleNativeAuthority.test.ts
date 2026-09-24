import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_GLOBAL_3024_BATTLE_NATIVE_PROVENANCE,
  LOGRES_GLOBAL_3024_RESULT_DISPLAY_MODES,
  LogresGlobal3024BattleNativeAuthority,
} from '../src/game/logres/battle/LogresGlobalBattleNativeAuthority'

describe(
  'Global 3.0.24 native battle authority',
  () => {
    it(
      'preserves the BattleSystem -> BoutSystem -> BoutSequencer lifecycle boundary',
      () => {
        const authority =
          new LogresGlobal3024BattleNativeAuthority()

        expect(
          () =>
            authority.initializeBout(
              'bout-1',
            ),
        ).toThrow(
          'BattleSystem is not initialized',
        )

        authority.initializeBattle(
          'battle-1',
        )

        authority.initializeBout(
          'bout-1',
        )

        authority.beginSequence(
          'sequence-1',
        )

        expect(
          authority.snapshot(),
        ).toMatchObject({
          provenance:
            LOGRES_GLOBAL_3024_BATTLE_NATIVE_PROVENANCE,

          authorityModel:
            'server-authored-sequenced-events',

          battleSystemRef:
            'battle-1',

          boutSystemRef:
            'bout-1',

          activeSequenceRef:
            'sequence-1',
        })
      },
    )

    it(
      'keeps command-skill request intent separate from server-authored execution',
      () => {
        const authority =
          new LogresGlobal3024BattleNativeAuthority()

        authority.initializeBattle(
          'battle-1',
        )

        authority.initializeBout(
          'bout-1',
        )

        const intent =
          authority.requestCommandSkill({
            actorRef:
              'player-1',

            itemRef:
              'weapon-1',

            skillRef:
              'skill-1',

            targetRef:
              'enemy-1',
          })

        expect(
          intent,
        ).toEqual({
          actorRef:
            'player-1',

          itemRef:
            'weapon-1',

          skillRef:
            'skill-1',

          targetRef:
            'enemy-1',
        })

        expect(
          authority.snapshot(),
        ).toMatchObject({
          clientSkillIntents: [
            intent,
          ],

          skillRequestResponses: [],

          serverEvents: [],

          targetLocks: {},

          resultReceived:
            false,

          boutFinished:
            false,
        })

        authority.recordCommandSkillResponse({
          rawCode0:
            0,

          rawCode1:
            0,

          responseInfoRef:
            'skill-response-info',
        })

        expect(
          authority.snapshot(),
        ).toMatchObject({
          skillRequestResponses: [
            {
              rawCode0:
                0,

              rawCode1:
                0,

              responseInfoRef:
                'skill-response-info',
            },
          ],

          serverEvents: [],
        })

        authority.beginSequence(
          'sequence-1',
        )

        authority.receiveSequencedEvent({
          type:
            'EXECUTE_SKILL',

          actorRef:
            'player-1',

          targetRef:
            'enemy-1',

          skillRef:
            'skill-1',

          payloadRef:
            'server-execute-payload',
        })

        expect(
          authority.snapshot()
            .serverEvents,
        ).toEqual([
          {
            sequenceRef:
              'sequence-1',

            ordinal:
              0,

            type:
              'EXECUTE_SKILL',

            actorRef:
              'player-1',

            targetRef:
              'enemy-1',

            skillRef:
              'skill-1',

            payloadRef:
              'server-execute-payload',
          },
        ])

        /*
         * Native evidence does not expose a client-owned damage or EP
         * calculation here. The original request intent stays distinct from
         * the later server execution event.
         */
        expect(
          authority.snapshot()
            .clientSkillIntents,
        ).toEqual([
          intent,
        ])
      },
    )

    it(
      'projects target lock and unlock only from sequenced server events',
      () => {
        const authority =
          new LogresGlobal3024BattleNativeAuthority()

        authority.initializeBattle(
          'battle-1',
        )

        authority.initializeBout(
          'bout-1',
        )

        authority.beginSequence(
          'sequence-1',
        )

        authority.receiveSequencedEvent({
          type:
            'CHAR_TARGET_LOCK',

          actorRef:
            'player-1',

          targetRef:
            'enemy-1',
        })

        expect(
          authority.snapshot()
            .targetLocks,
        ).toEqual({
          'player-1':
            'enemy-1',
        })

        authority.receiveSequencedEvent({
          type:
            'CHAR_TARGET_UNLOCK',

          actorRef:
            'player-1',
        })

        expect(
          authority.snapshot()
            .targetLocks,
        ).toEqual({})
      },
    )

    it(
      'keeps sequenced result/finish events separate from native result display and finish-flow calls',
      () => {
        const authority =
          new LogresGlobal3024BattleNativeAuthority()

        authority.initializeBattle(
          'battle-1',
        )

        authority.initializeBout(
          'bout-1',
        )

        expect(
          LOGRES_GLOBAL_3024_RESULT_DISPLAY_MODES,
        ).toEqual([
          1,
          2,
        ])

        authority.displayResult({
          displayMode:
            1,

          resultPayloadRef:
            'result-payload-direct',
        })

        authority.requestFinishFlow(
          true,
        )

        expect(
          authority.snapshot(),
        ).toMatchObject({
          resultReceived:
            false,

          boutFinished:
            false,

          resultPresented:
            true,

          resultDisplayMode:
            1,

          finishFlowRequested:
            true,

          finishFlowFlag:
            true,
        })

        authority.beginSequence(
          'sequence-1',
        )

        authority.receiveSequencedEvent({
          type:
            'BOUT_RESULT',

          payloadRef:
            'result-payload',
        })

        authority.receiveSequencedEvent({
          type:
            'DROP',

          actorRef:
            'enemy-1',

          payloadRef:
            'drop-payload',
        })

        authority.receiveSequencedEvent({
          type:
            'BOUT_FINISH',
        })

        authority.endSequence(
          'sequence-1',
        )

        expect(
          authority.snapshot(),
        ).toMatchObject({
          resultReceived:
            true,

          boutFinished:
            true,

          resultPresented:
            true,

          resultDisplayMode:
            1,

          finishFlowRequested:
            true,

          finishFlowFlag:
            true,
        })

        expect(
          authority.snapshot()
            .serverEvents
            .map(
              event =>
                event.type,
            ),
        ).toEqual([
          'BOUT_RESULT',
          'DROP',
          'BOUT_FINISH',
        ])
      },
    )

    it(
      'rejects unresolved BattleSystem result display mode values',
      () => {
        const authority =
          new LogresGlobal3024BattleNativeAuthority()

        authority.initializeBattle(
          'battle-1',
        )

        expect(
          () =>
            authority.displayResult({
              displayMode:
                3 as 1,

              resultPayloadRef:
                'result-payload',
            }),
        ).toThrow(
          'mode must be 1 or 2',
        )
      },
    )

    it(
      'rejects server battle events outside an active sequencer boundary',
      () => {
        const authority =
          new LogresGlobal3024BattleNativeAuthority()

        authority.initializeBattle(
          'battle-1',
        )

        authority.initializeBout(
          'bout-1',
        )

        expect(
          () =>
            authority.receiveSequencedEvent({
              type:
                'STATUS_CHANGED',
            }),
        ).toThrow(
          'no active sequence',
        )

        authority.beginSequence(
          'sequence-1',
        )

        expect(
          () =>
            authority.endSequence(
              'sequence-2',
            ),
        ).toThrow(
          'does not match',
        )
      },
    )

    it(
      'does not infer target refs required by target-lock events',
      () => {
        const authority =
          new LogresGlobal3024BattleNativeAuthority()

        authority.initializeBattle(
          'battle-1',
        )

        authority.initializeBout(
          'bout-1',
        )

        authority.beginSequence(
          'sequence-1',
        )

        expect(
          () =>
            authority.receiveSequencedEvent({
              type:
                'CHAR_TARGET_LOCK',

              actorRef:
                'player-1',
            }),
        ).toThrow(
          'requires actor and target refs',
        )
      },
    )
  },
)
