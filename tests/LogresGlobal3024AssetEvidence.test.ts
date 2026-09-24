import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_GLOBAL_3024_ASSET_EVIDENCE,
  LOGRES_GLOBAL_3024_ASSET_PROVENANCE,
  LOGRES_GLOBAL_3024_BOOTSTRAP_ASSET_COUNTS,
  LOGRES_GLOBAL_3024_BOOTSTRAP_AUDIO_EVIDENCE,
  LOGRES_GLOBAL_3024_BSS_EVIDENCE,
  LOGRES_GLOBAL_3024_DDS_EVIDENCE,
  LOGRES_GLOBAL_3024_JSON_TABLE_EVIDENCE,
  LOGRES_GLOBAL_3024_LFLA_EVIDENCE,
  LOGRES_GLOBAL_3024_RESOURCE_LOADERS,
} from '../src/game/logres/assets/LogresGlobal3024AssetEvidence'

describe(
  'Global 3.0.24 packaged asset evidence',
  () => {
    it(
      'locks the complete bootstrap package/member counts',
      () => {
        expect(
          LOGRES_GLOBAL_3024_ASSET_PROVENANCE,
        ).toBe(
          'CONFIRMED_ORIGINAL_GLOBAL_3_0_24_PACKAGED_ASSET_METADATA',
        )

        expect(
          LOGRES_GLOBAL_3024_BOOTSTRAP_ASSET_COUNTS,
        ).toEqual({
          packages:
            23,

          members:
            461,

          packagePaths: [
            'graphicSettings/texture.mbn',
            'gui.mbn',
            'gui/characreate.mbn',
            'gui/characreate/slice.mbn',
            'gui/common_base.mbn',
            'gui/notify.mbn',
            'gui/patch.mbn',
            'gui/splash.mbn',
            'gui/system/indicator.mbn',
            'gui/system/loading.mbn',
            'gui/title.mbn',
            'gui/title/effect.mbn',
            'gui/title/effect/png.mbn',
            'gui/title/image9Slice.mbn',
            'gui/title/patchCharacter.mbn',
            'gui/title/patchCharacter/png.mbn',
            'gui/warning.mbn',
            'gui_CN/share.mbn',
            'json_resource.mbn',
            'motion/settings.mbn',
            'system/avatar_resource_tbl.mbn',
            'system/color.mbn',
            'text.mbn',
          ],

          memberTypes: {
            json:
              74,

            lua:
              22,

            png:
              193,

            dds:
              155,

            bss:
              2,

            lfla:
              15,
          },
        })
      },
    )

    it(
      'records complete LFLA decoder coverage without inventing animation semantics',
      () => {
        expect(
          LOGRES_GLOBAL_3024_LFLA_EVIDENCE,
        ).toMatchObject({
          files:
            15,

          decoderErrors:
            0,

          titleCanvas720x1280:
            11,

          patchCharacterCanvas152x128:
            4,

          nativeLoader:
            'lfs::FlashResource / lfla::data::Document',

          format:
            'PROTOBUF_WIRE_LFLA',
        })

        expect(
          LOGRES_GLOBAL_3024_LFLA_EVIDENCE
            .layoutFamilies,
        ).toEqual({
          title: {
            package:
              'gui/title/effect.mbn',

            canvas: [
              720,
              1280,
            ],

            entries: [
              'bg.lfla',
              'bg_a.lfla',
              'bg_b.lfla',
              'bg_c.lfla',
              'bg_d.lfla',
              'bg_e.lfla',
              'logo_a.lfla',
              'logo_b.lfla',
              'logo_c.lfla',
              'start_a.lfla',
              'start_b.lfla',
            ],
          },

          patchCharacter: {
            package:
              'gui/title/patchCharacter.mbn',

            canvas: [
              152,
              128,
            ],

            entries: [
              'kpo_000_000_000_m.lfla',
              'kpo_000_000_001_m.lfla',
              'mdr_000_000_000_m.lfla',
              'mdr_000_000_001_m.lfla',
            ],
          },
        })

        expect(
          LOGRES_GLOBAL_3024_LFLA_EVIDENCE
            .observedDurations,
        ).toEqual([
          30000,
          31000,
          45000,
          60000,
          80000,
          88000,
          120000,
          450000,
          480000,
          600000,
        ])
      },
    )

    it(
      'locks all packaged DDS formats and the two A1R5G5B5 exceptions',
      () => {
        expect(
          LOGRES_GLOBAL_3024_DDS_EVIDENCE,
        ).toEqual({
          files:
            155,

          decoderErrors:
            0,

          a4r4g4b4:
            153,

          a1r5g5b5:
            2,

          a1r5g5b5Entries: [
            'gui__common_base.mbn/checkbox01.dds',
            'gui__common_base.mbn/checkbox02.dds',
          ],

          otherFormats:
            0,

          largestObservedTexture: {
            package:
              'gui__title__effect__png.mbn',

            entry:
              'field00.dds',

            width:
              1810,

            height:
              1280,
          },
        })
      },
    )

    it(
      'classifies BSS as sprite-sheet metadata rather than audio',
      () => {
        expect(
          LOGRES_GLOBAL_3024_BSS_EVIDENCE,
        ).toEqual({
          files:
            2,

          entries: [
            'gui__system__indicator.mbn/indicator.bss',
            'gui__system__loading.mbn/loading.bss',
          ],

          nativeLoader:
            'lfs::SpriteSheetResource',

          classification:
            'SPRITE_SHEET_METADATA_NOT_AUDIO',
        })
      },
    )

    it(
      'keeps the no-audio finding scoped to the bootstrap MBN corpus',
      () => {
        expect(
          LOGRES_GLOBAL_3024_BOOTSTRAP_AUDIO_EVIDENCE,
        ).toEqual({
          packagedAudioFiles:
            0,

          finding:
            'NO_PACKAGED_AUDIO_IN_BOOTSTRAP_MBN_CORPUS',

          scope:
            'BOOTSTRAP_MBN_CORPUS_ONLY',
        })
      },
    )

    it(
      'locks native resource loader classes and decoded JSON-table counts',
      () => {
        expect(
          LOGRES_GLOBAL_3024_RESOURCE_LOADERS,
        ).toEqual({
          lfla:
            'lfs::FlashResource / lfla::data::Document',

          bss:
            'lfs::SpriteSheetResource',

          microbin:
            'lfs::MicroBinResource',

          json:
            'lfs::Json11Resource',

          resourceOrchestrator:
            'lfs::ResourceManager',

          patchStorage:
            'lfs::PatchStorage',
        })

        expect(
          LOGRES_GLOBAL_3024_JSON_TABLE_EVIDENCE,
        ).toEqual({
          avatarResourceTableItemsType:
            'list',

          avatarResourceTableItemsCount:
            4052,

          colorEntries:
            146,

          motionFlashMaskKeys:
            17,
        })

        expect(
          LOGRES_GLOBAL_3024_ASSET_EVIDENCE
            .source,
        ).toMatchObject({
          client:
            'Global 3.0.24',

          apkSha256:
            '7424aa5b84fc52358a955dd1bb6b6d0b31f50f6b58d58e592ece4257cec17943',

          evidenceArtifactSha256:
            '5ad0f8a5fbae361298a0cedab0b86e8d4946bdbdaadb400463fe56ad06adaa8d',

          bootstrapMemberManifestSha256:
            'a150957aaa9578fdac7914b3c6ff4fb464bcb89b11bfb6e60add07d0353976ca',
        })
      },
    )
  },
)
