import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_GLOBAL_CHAR_TALK_LIMIT_INTERVAL_SECONDS,
  LOGRES_GLOBAL_CHAR_TALK_TIME_INTERVAL_SECONDS,
  LOGRES_RECONSTRUCTED_NPC_INTERACTION_PROVENANCE,
  ReconstructedLogresNpcInteractionAuthority,
} from '../src/game/logres/encounter/ReconstructedLogresNpcInteractionAuthority'

describe(
  'reconstructed Logres NPC interaction authority',
  () => {
    it(
      'preserves recovered Global talk timing facts without assigning them to an unproven phase',
      () => {
        expect(
          LOGRES_GLOBAL_CHAR_TALK_TIME_INTERVAL_SECONDS,
        ).toBe(1)

        expect(
          LOGRES_GLOBAL_CHAR_TALK_LIMIT_INTERVAL_SECONDS,
        ).toBe(5)
      },
    )

    it(
      'requires talkable and in-range state before creating a talk intent',
      () => {
        const authority =
          new ReconstructedLogresNpcInteractionAuthority()

        authority.setNpcState({
          npcKey:
            'opening-guide',
          characterRef:
            null,
          canTalk:
            false,
          inRange:
            true,
        })

        expect(
          () =>
            authority.createTalkIntent(),
        ).toThrow(
          'not currently talkable',
        )

        authority.setNpcState({
          npcKey:
            'opening-guide',
          characterRef:
            null,
          canTalk:
            true,
          inRange:
            false,
        })

        expect(
          () =>
            authority.createTalkIntent(),
        ).toThrow(
          'outside interaction range',
        )
      },
    )

    it(
      'creates a reconstructed intent while allowing original character identity to remain unresolved',
      () => {
        const authority =
          new ReconstructedLogresNpcInteractionAuthority()

        authority.setNpcState({
          npcKey:
            'opening-guide',
          characterRef:
            null,
          canTalk:
            true,
          inRange:
            true,
        })

        expect(
          authority.createTalkIntent(),
        ).toEqual({
          provenance:
            LOGRES_RECONSTRUCTED_NPC_INTERACTION_PROVENANCE,
          npcKey:
            'opening-guide',
          characterRef:
            null,
        })

        expect(
          authority.snapshot(),
        ).toMatchObject({
          requestPending:
            true,
          talkGateActive:
            true,
        })
      },
    )

    it(
      'keeps the talk gate active after a response until an external timer releases it',
      () => {
        const authority =
          new ReconstructedLogresNpcInteractionAuthority()

        authority.setNpcState({
          npcKey:
            'guide',
          characterRef:
            'cuid-1',
          canTalk:
            true,
          inRange:
            true,
        })

        authority.createTalkIntent()
        authority.recordTalkResponse(
          7,
        )

        expect(
          authority.snapshot(),
        ).toMatchObject({
          requestPending:
            false,
          talkGateActive:
            true,
          lastResponseCode:
            7,
        })

        expect(
          () =>
            authority.createTalkIntent(),
        ).toThrow(
          'talk gate is still active',
        )

        authority.releaseTalkGate()

        expect(
          authority.createTalkIntent()
            .characterRef,
        ).toBe(
          'cuid-1',
        )
      },
    )

    it(
      'rejects overlapping requests and malformed response codes',
      () => {
        const authority =
          new ReconstructedLogresNpcInteractionAuthority()

        authority.setNpcState({
          npcKey:
            'guide',
          characterRef:
            'cuid-1',
          canTalk:
            true,
          inRange:
            true,
        })

        authority.createTalkIntent()

        expect(
          () =>
            authority.setNpcState({
              npcKey:
                'other',
              characterRef:
                null,
              canTalk:
                true,
              inRange:
                true,
            }),
        ).toThrow(
          'while a talk request is pending',
        )

        expect(
          () =>
            authority.recordTalkResponse(
              Number.NaN,
            ),
        ).toThrow(
          'safe integer',
        )
      },
    )
  },
)
