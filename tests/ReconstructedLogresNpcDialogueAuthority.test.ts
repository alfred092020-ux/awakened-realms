import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_GLOBAL_NPC_DIALOGUE_PAYLOAD_CONFIDENCE,
  LOGRES_NPC_DIALOGUE_EVIDENCE_BOUNDARY,
  LOGRES_RECONSTRUCTED_FIELD_GUIDE_DIALOGUE,
  LOGRES_RECONSTRUCTED_NPC_DIALOGUE_PROVENANCE,
  LOGRES_RECONSTRUCTED_NPC_DIALOGUE_SERVER_STUB_PROVENANCE,
  ReconstructedLogresNpcDialogueAuthority,
} from '../src/game/logres/encounter/ReconstructedLogresNpcDialogueAuthority'

describe(
  'reconstructed Logres NPC dialogue authority',
  () => {
    it(
      'keeps recovered protocol evidence separate from reconstructed script content',
      () => {
        expect(
          LOGRES_NPC_DIALOGUE_EVIDENCE_BOUNDARY,
        ).toEqual({
          interactionProvenance:
            'RECONSTRUCTED',
          requestMessage:
            'C_GMCL_CHAR_TALK_REQ',
          responseHandler:
            'C_GMCL_CHAR_TALK_REQ_Response',
          dialogueWindow:
            'NpcDialogueWindow',
          exactHistoricalDialoguePayload:
            LOGRES_GLOBAL_NPC_DIALOGUE_PAYLOAD_CONFIDENCE,
        })

        expect(
          LOGRES_RECONSTRUCTED_FIELD_GUIDE_DIALOGUE
            .provenance,
        ).toBe(
          LOGRES_RECONSTRUCTED_NPC_DIALOGUE_PROVENANCE,
        )

        expect(
          LOGRES_RECONSTRUCTED_FIELD_GUIDE_DIALOGUE
            .historicalGlobalPayload,
        ).toBe(
          'UNRESOLVED',
        )


        expect(
          LOGRES_RECONSTRUCTED_FIELD_GUIDE_DIALOGUE
            .lines,
        ).toEqual([
          'Welcome to the Millennium Tree.',
        ])

        const playerDialogue =
          LOGRES_RECONSTRUCTED_FIELD_GUIDE_DIALOGUE
            .lines
            .join(
              ' ',
            )
            .toLowerCase()

        for (
          const forbidden of [
            'reconstructed',
            'unresolved',
            'evidence',
            'historical',
            'retired global',
          ]
        ) {
          expect(
            playerDialogue,
          ).not.toContain(
            forbidden,
          )
        }
      },
    )

    it(
      'requires field interaction authority before opening dialogue',
      () => {
        const authority =
          new ReconstructedLogresNpcDialogueAuthority(
            LOGRES_RECONSTRUCTED_FIELD_GUIDE_DIALOGUE,
          )

        authority.bindNpcState({
          characterRef:
            null,
          canTalk:
            true,
          inRange:
            false,
        })

        expect(
          () =>
            authority.requestTalk(),
        ).toThrow(
          'outside interaction range',
        )
      },
    )

    it(
      'transitions request -> reconstructed response -> dialogue without assigning historical response meaning',
      () => {
        const authority =
          new ReconstructedLogresNpcDialogueAuthority(
            LOGRES_RECONSTRUCTED_FIELD_GUIDE_DIALOGUE,
          )

        authority.bindNpcState({
          characterRef:
            null,
          canTalk:
            true,
          inRange:
            true,
        })

        const intent =
          authority.requestTalk()

        expect(
          intent,
        ).toMatchObject({
          provenance:
            'RECONSTRUCTED',
          npcKey:
            'reconstructed-millennium-tree-guide',
          characterRef:
            null,
        })

        expect(
          authority.snapshot()
            .phase,
        ).toBe(
          'REQUEST_PENDING',
        )

        const stub =
          authority
            .openFromReconstructedResponse(
              0,
            )

        expect(
          stub,
        ).toEqual({
          provenance:
            LOGRES_RECONSTRUCTED_NPC_DIALOGUE_SERVER_STUB_PROVENANCE,
          rawCode:
            0,
          interpretation:
            'LOCAL_DIALOGUE_OPEN_STUB',
          historicalResponseCodeMeaning:
            'UNRESOLVED',
        })

        expect(
          authority.snapshot(),
        ).toMatchObject({
          phase:
            'DIALOGUE_OPEN',
          lineIndex:
            0,
          completedSessions:
            0,
          historicalGlobalPayload:
            'UNRESOLVED',
          interaction: {
            requestPending:
              false,
            talkGateActive:
              true,
            lastResponseCode:
              0,
          },
        })
      },
    )

    it(
      'closes the single local guide line and releases the interaction gate',
      () => {
        const authority =
          new ReconstructedLogresNpcDialogueAuthority(
            LOGRES_RECONSTRUCTED_FIELD_GUIDE_DIALOGUE,
          )

        authority.bindNpcState({
          characterRef:
            null,
          canTalk:
            true,
          inRange:
            true,
        })

        authority.requestTalk()
        authority.openFromReconstructedResponse(
          0,
        )

        expect(
          authority.snapshot(),
        ).toMatchObject({
          phase:
            'DIALOGUE_OPEN',
          lineIndex:
            0,
          lineCount:
            1,
          currentLine:
            'Welcome to the Millennium Tree.',
          historicalGlobalPayload:
            'UNRESOLVED',
        })

        expect(
          authority.advance(),
        ).toBe(
          true,
        )

        expect(
          authority.snapshot(),
        ).toMatchObject({
          phase:
            'READY',
          lineIndex:
            null,
          currentLine:
            null,
          completedSessions:
            1,
          interaction: {
            requestPending:
              false,
            talkGateActive:
              false,
          },
        })
      },
    )

    it(
      'supports repeated sessions without overlapping requests or listener state',
      () => {
        const authority =
          new ReconstructedLogresNpcDialogueAuthority(
            LOGRES_RECONSTRUCTED_FIELD_GUIDE_DIALOGUE,
          )

        for (
          let session =
            1;
          session <=
          2;
          session +=
          1
        ) {
          authority.bindNpcState({
            characterRef:
              null,
            canTalk:
              true,
            inRange:
              true,
          })

          authority.requestTalk()

          expect(
            () =>
              authority.requestTalk(),
          ).toThrow(
            'already active',
          )

          authority
            .openFromReconstructedResponse(
              0,
            )

          while (
            authority
              .snapshot()
              .phase ===
            'DIALOGUE_OPEN'
          ) {
            authority.advance()
          }

          expect(
            authority.snapshot()
              .completedSessions,
          ).toBe(
            session,
          )
        }
      },
    )
  },
)
