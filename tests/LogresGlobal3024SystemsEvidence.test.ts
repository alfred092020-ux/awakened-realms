import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_GLOBAL_3024_BUNDLED_SYSTEM_CONFIG,
  LOGRES_GLOBAL_3024_CHAT_MAIL,
  LOGRES_GLOBAL_3024_CHAT_RESULTS,
  LOGRES_GLOBAL_3024_CLAN,
  LOGRES_GLOBAL_3024_DAILY_MISSION_RESULTS,
  LOGRES_GLOBAL_3024_ECONOMY,
  LOGRES_GLOBAL_3024_FUSION_RESULTS,
  LOGRES_GLOBAL_3024_ITEM_RESULTS,
  LOGRES_GLOBAL_3024_ITEMS,
  LOGRES_GLOBAL_3024_JOBS,
  LOGRES_GLOBAL_3024_PARTY,
  LOGRES_GLOBAL_3024_QUESTS,
  LOGRES_GLOBAL_3024_SYSTEMS_SOURCE,
  LOGRES_GLOBAL_3024_SYSTEMS_SURFACE_COUNTS,
  LOGRES_GLOBAL_3024_SYSTEMS_UNRESOLVED,
} from '../src/game/logres/systems/LogresGlobal3024SystemsEvidence'

describe(
  'Global 3.0.24 gameplay systems evidence',
  () => {
    it(
      'anchors systems evidence to the original Global native client',
      () => {
        expect(
          LOGRES_GLOBAL_3024_SYSTEMS_SOURCE,
        ).toMatchObject({
          clientVersion: '3.0.24',
          numericFunctionIdCount: 631,
          numericEnumConstantCount: 507,
        })
        expect(
          LOGRES_GLOBAL_3024_SYSTEMS_SURFACE_COUNTS
            .overlappingKeywordSurface,
        ).toBe(true)
      },
    )

    it(
      'recovers exact item and fusion result enums',
      () => {
        expect(
          LOGRES_GLOBAL_3024_ITEM_RESULTS,
        ).toMatchObject({
          OK: 0,
          NO_SPACE_LEFT: 8,
          OUT_OF_DATE: 12,
          NOT_IMPLEMENTED: 13,
        })
        expect(
          LOGRES_GLOBAL_3024_FUSION_RESULTS,
        ).toEqual({
          OK: 0,
          BAD_REQUEST: 1,
          FORBIDDEN: 2,
          INTERNAL_SERVER_ERROR: 3,
          GONE: 4,
          NOT_SUPPORTED: 5,
        })
      },
    )

    it(
      'keeps inventory snapshots and mutation requests at server boundaries',
      () => {
        expect(
          LOGRES_GLOBAL_3024_ITEMS
            .requests.itemMove,
        ).toMatchObject({
          functionId: 683580635,
          moveParamCtor:
            't_ItemMoveParam(t_ItemUID, int, t_ItemUID, int)',
        })
        expect(
          LOGRES_GLOBAL_3024_ITEMS
            .serverProjection.itemInfo,
        ).toMatchObject({
          functionId: 4110668784,
        })
        expect(
          LOGRES_GLOBAL_3024_ITEMS
            .authorityInterpretation,
        ).toContain(
          'server-snapshot-and-result-authority',
        )
      },
    )

    it(
      'models quests as the recovered server-authored state sequence',
      () => {
        expect(
          LOGRES_GLOBAL_3024_QUESTS
            .requests.accept,
        ).toMatchObject({
          functionId: 2567234653,
          parameter:
            't_QuestAcceptRequestParam',
        })
        expect(
          LOGRES_GLOBAL_3024_QUESTS
            .statePushSequence,
        ).toEqual(
          expect.arrayContaining([
            'S_GMCL_QUEST_INFO_STATE_PROGRESS_START',
            'S_GMCL_QUEST_INFO_STATE_PROGRESS_UPDATE',
            'S_GMCL_QUEST_INFO_STATE_RESULT',
            'S_GMCL_QUEST_INFO_STATE_END',
          ]),
        )
        expect(
          LOGRES_GLOBAL_3024_QUESTS
            .resultStateFunctionId,
        ).toBe(1638040888)
      },
    )

    it(
      'recovers job and gacha protocol boundaries with exact IDs',
      () => {
        expect(
          LOGRES_GLOBAL_3024_JOBS
            .jobChange,
        ).toMatchObject({
          functionId: 3865175023,
        })
        expect(
          LOGRES_GLOBAL_3024_ECONOMY
            .gacha.draw,
        ).toMatchObject({
          functionId: 1353764312,
        })
        expect(
          LOGRES_GLOBAL_3024_ECONOMY
            .gacha.resultEnum,
        ).toEqual({
          SUCCESS: 0,
          FAILURE: 1,
        })
      },
    )

    it(
      'keeps party and clan membership server synchronized',
      () => {
        expect(
          LOGRES_GLOBAL_3024_PARTY
            .sync.functionId,
        ).toBe(3807449958)
        expect(
          LOGRES_GLOBAL_3024_CLAN
            .sync.functionId,
        ).toBe(2327358608)
        expect(
          LOGRES_GLOBAL_3024_PARTY
            .separateMercenarySystem,
        ).toBe(true)
      },
    )

    it(
      'recovers chat and mail function IDs and result semantics',
      () => {
        expect(
          LOGRES_GLOBAL_3024_CHAT_MAIL
            .chatSend.functionId,
        ).toBe(1865766449)
        expect(
          LOGRES_GLOBAL_3024_CHAT_MAIL
            .receiveMail.functionId,
        ).toBe(1729810893)
        expect(
          LOGRES_GLOBAL_3024_CHAT_MAIL
            .messagePush.functionId,
        ).toBe(3088420669)
        expect(
          LOGRES_GLOBAL_3024_CHAT_RESULTS,
        ).toMatchObject({
          OK: 0,
          NOT_A_MEMBER: 14,
          TOO_LONG_NAME: 19,
        })
      },
    )

    it(
      'preserves daily mission result values and bundled system configuration evidence',
      () => {
        expect(
          LOGRES_GLOBAL_3024_DAILY_MISSION_RESULTS,
        ).toEqual({
          UNKNOWN: 0,
          SUCCESS: 1,
          NOT_FOUND: 2,
          CAN_NOT_COMPLETE: 3,
          ALREADY_FINISHED: 4,
          EXPIRED: 5,
        })
        expect(
          LOGRES_GLOBAL_3024_BUNDLED_SYSTEM_CONFIG,
        ).toMatchObject({
          questScalars: 202,
          sixthSenseUiScalars: 149,
          eventSettingScalars: 190,
        })
      },
    )

    it(
      'keeps unknown historical server content explicit',
      () => {
        expect(
          LOGRES_GLOBAL_3024_SYSTEMS_UNRESOLVED,
        ).toEqual(
          expect.arrayContaining([
            'complete server-side validation formulas and database constraints',
            'historical production catalog contents for shops and gachas beyond bundled UI/config evidence',
            'historical item source payload corpus and exact inventory contents',
          ]),
        )
      },
    )
  },
)
