export const LOGRES_GLOBAL_3024_PRESENTATION_PROVENANCE =
  'CONFIRMED_ORIGINAL_GLOBAL_3_0_24_PRESENTATION_RENDER_AUDIO_SURFACE' as const

export const LOGRES_GLOBAL_3024_PRESENTATION_COUNTS =
  Object.freeze({
    flash: Object.freeze({ classes: 46, methods: 314 }),
    spine: Object.freeze({ classes: 5, methods: 55 }),
    animationCore: Object.freeze({ classes: 4, methods: 41 }),
    spriteTextureModel: Object.freeze({ classes: 19, methods: 156 }),
    shaderPostEffect: Object.freeze({ classes: 23, methods: 111 }),
    cameraIsometric: Object.freeze({ classes: 5, methods: 50 }),
    audioCore: Object.freeze({ classes: 6, methods: 63 }),
    battlePresentationActions: Object.freeze({ classes: 36, methods: 311 }),
    skitPresentationActions: Object.freeze({ classes: 28, methods: 187 }),
    font: Object.freeze({ classes: 2, methods: 53 }),
  } as const)

export const LOGRES_GLOBAL_3024_PRESENTATION_PIPELINES =
  Object.freeze({
    flash:
      'FlashResource -> FlashPlayer/FlashSequencer -> FlashRenderer with play, pause, resume, seek and set-time actions.',
    spine:
      'AnimationLoader loads SpineAtlasResource plus SpineSkeletonResource into SpinePlayer with event timeline data.',
    modelSprite:
      'AvatarModel and character::Model use Sprite/RenderSprite, SpriteSheetResource, TextureResource and DDS image decoding.',
    shader:
      'Vertex/fragment shader resources feed lfs::shader and post_effect renderers for bloom, grayscale, radial blur and sepia.',
    camera:
      'Camera, Isometric, LandscapeAccessor, DisplaySizeManager and SkyColorBlender provide field view presentation.',
    audio:
      'SoundManager owns music/effect playback, fades, volume, pause/resume, preload/unload and current-BGM MultiID state.',
  } as const)

export const LOGRES_GLOBAL_3024_AUDIO_CONVENTION =
  Object.freeze({
    backgroundMusic: Object.freeze({
      function: 'BackgroundMusicResource::createFilePath',
      address: '0x1f28a54',
      rule: 'remove existing extension, append .ogg',
    } as const),
    soundEffect: Object.freeze({
      function: 'SoundEffectResource::createFilePath',
      address: '0x1f2ebe4',
      rule: 'remove existing extension, append .wav',
    } as const),
    androidBridge: Object.freeze([
      'Java_com_aiming_lfs_audiocontroller_AudioController_fadeoutMusic',
      'Java_com_aiming_lfs_audiocontroller_AudioController_pauseBGM',
    ] as const),
  } as const)

export const LOGRES_GLOBAL_3024_BATTLE_PRESENTATION_PRIMITIVES =
  Object.freeze([
    'alpha',
    'effect',
    'loop',
    'motion transform',
    'approach/initialize/return movement',
    'play motion',
    'post effect',
    'sound',
    'trigger',
    'damage/guard/miss',
    'drop/gain',
    'lock-on',
    'battle-in/out/fade transitions',
  ] as const)

export const LOGRES_GLOBAL_3024_SKIT_PRESENTATION_PRIMITIVES =
  Object.freeze([
    'pop/move/delete image',
    'pop sprite',
    'pop/delete text',
    'pop/sync/stop effect',
    'play/reopen/stop BGM',
    'play/stop SE',
    'wait click',
    'wait time',
    'event start/finish',
  ] as const)

export const LOGRES_GLOBAL_3024_PRESENTATION_RESOURCE_PATHS =
  Object.freeze([
    'motion/<family>/... LFLA plus motionList.tbl',
    'gui/.../*.lfla for UI animation/effects',
    'shader/field_terrain.vert',
    'shader/field_terrain.frag',
    'shader/post_effect/*.fsh',
    'shader/post_effect/post_effect_base.vsh',
    'Spine atlas plus skeleton pairs through AnimationLoader',
  ] as const)

export const LOGRES_GLOBAL_3024_PRESENTATION_GUARDRAIL =
  'Presentation classes schedule and render visuals/audio. Gameplay authority remains in the recovered battle, field and protocol domains.' as const

export const LOGRES_GLOBAL_3024_PRESENTATION_UNRESOLVED =
  Object.freeze([
    'Exact device-specific GPU rasterization and shader output requires original runtime hardware and drivers.',
    'Most patch-delivered production audio bytes are not inside the bootstrap APK.',
    'Exact frame content for remote patch-delivered animations requires the matching historical patch asset.',
  ] as const)
