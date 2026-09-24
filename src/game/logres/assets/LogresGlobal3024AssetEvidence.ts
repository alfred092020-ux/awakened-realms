export const LOGRES_GLOBAL_3024_ASSET_PROVENANCE =
  'CONFIRMED_ORIGINAL_GLOBAL_3_0_24_PACKAGED_ASSET_METADATA' as const

export const LOGRES_GLOBAL_3024_ASSET_SOURCE =
  Object.freeze({
    client:
      'Global 3.0.24',

    apkSha256:
      '7424aa5b84fc52358a955dd1bb6b6d0b31f50f6b58d58e592ece4257cec17943',

    evidenceArtifactSha256:
      '5ad0f8a5fbae361298a0cedab0b86e8d4946bdbdaadb400463fe56ad06adaa8d',

    bootstrapMemberManifestSha256:
      'a150957aaa9578fdac7914b3c6ff4fb464bcb89b11bfb6e60add07d0353976ca',
  } as const)

export const LOGRES_GLOBAL_3024_BOOTSTRAP_ASSET_COUNTS =
  Object.freeze({
    packages:
      23,

    members:
      461,

    packagePaths:
      Object.freeze([
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
      ] as const),

    memberTypes:
      Object.freeze({
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
      } as const),
  } as const)

export const LOGRES_GLOBAL_3024_LFLA_EVIDENCE =
  Object.freeze({
    files:
      15,

    decoderErrors:
      0,

    titleCanvas720x1280:
      11,

    patchCharacterCanvas152x128:
      4,

    observedDurations:
      Object.freeze([
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
      ] as const),

    nativeLoader:
      'lfs::FlashResource / lfla::data::Document',

    format:
      'PROTOBUF_WIRE_LFLA',

    layoutFamilies:
      Object.freeze({
        title: Object.freeze({
          package:
            'gui/title/effect.mbn',

          canvas:
            Object.freeze([
              720,
              1280,
            ] as const),

          entries:
            Object.freeze([
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
            ] as const),
        }),

        patchCharacter:
          Object.freeze({
            package:
              'gui/title/patchCharacter.mbn',

            canvas:
              Object.freeze([
                152,
                128,
              ] as const),

            entries:
              Object.freeze([
                'kpo_000_000_000_m.lfla',
                'kpo_000_000_001_m.lfla',
                'mdr_000_000_000_m.lfla',
                'mdr_000_000_001_m.lfla',
              ] as const),
          }),
      } as const),
  } as const)

export const LOGRES_GLOBAL_3024_DDS_EVIDENCE =
  Object.freeze({
    files:
      155,

    decoderErrors:
      0,

    a4r4g4b4:
      153,

    a1r5g5b5:
      2,

    a1r5g5b5Entries:
      Object.freeze([
        'gui__common_base.mbn/checkbox01.dds',
        'gui__common_base.mbn/checkbox02.dds',
      ] as const),

    otherFormats:
      0,

    largestObservedTexture:
      Object.freeze({
        package:
          'gui__title__effect__png.mbn',

        entry:
          'field00.dds',

        width:
          1810,

        height:
          1280,
      } as const),
  } as const)

export const LOGRES_GLOBAL_3024_BSS_EVIDENCE =
  Object.freeze({
    files:
      2,

    entries:
      Object.freeze([
        'gui__system__indicator.mbn/indicator.bss',
        'gui__system__loading.mbn/loading.bss',
      ] as const),

    nativeLoader:
      'lfs::SpriteSheetResource',

    classification:
      'SPRITE_SHEET_METADATA_NOT_AUDIO',
  } as const)

export const LOGRES_GLOBAL_3024_RESOURCE_LOADERS =
  Object.freeze({
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
  } as const)

export const LOGRES_GLOBAL_3024_JSON_TABLE_EVIDENCE =
  Object.freeze({
    avatarResourceTableItemsType:
      'list',

    avatarResourceTableItemsCount:
      4052,

    colorEntries:
      146,

    motionFlashMaskKeys:
      17,
  } as const)

export const LOGRES_GLOBAL_3024_BOOTSTRAP_AUDIO_EVIDENCE =
  Object.freeze({
    packagedAudioFiles:
      0,

    finding:
      'NO_PACKAGED_AUDIO_IN_BOOTSTRAP_MBN_CORPUS',

    /*
     * The absence is scoped deliberately: this proves there are no audio
     * payload members inside the 23 catalogued bootstrap MBN packages.
     * It does not claim the complete historical client never streamed or
     * patched audio through another resource path.
     */
    scope:
      'BOOTSTRAP_MBN_CORPUS_ONLY',
  } as const)

export const LOGRES_GLOBAL_3024_ASSET_EVIDENCE =
  Object.freeze({
    provenance:
      LOGRES_GLOBAL_3024_ASSET_PROVENANCE,

    source:
      LOGRES_GLOBAL_3024_ASSET_SOURCE,

    bootstrap:
      LOGRES_GLOBAL_3024_BOOTSTRAP_ASSET_COUNTS,

    lfla:
      LOGRES_GLOBAL_3024_LFLA_EVIDENCE,

    dds:
      LOGRES_GLOBAL_3024_DDS_EVIDENCE,

    bss:
      LOGRES_GLOBAL_3024_BSS_EVIDENCE,

    loaders:
      LOGRES_GLOBAL_3024_RESOURCE_LOADERS,

    jsonTables:
      LOGRES_GLOBAL_3024_JSON_TABLE_EVIDENCE,

    audio:
      LOGRES_GLOBAL_3024_BOOTSTRAP_AUDIO_EVIDENCE,
  } as const)
