export const LOGRES_VIDEO_REFERENCE_SCHEMA =
  'logres-video-reference-v1' as const

export type LogresVideoReferenceAuthority =
  | 'CONFIRMED_GLOBAL_3_0_24'
  | 'VERSION_SENSITIVE_USER_VIDEO'
  | 'CURRENT_JP_CORROBORATION_ONLY'

export type LogresVideoReferenceDomain =
  | 'TITLE'
  | 'CHARACTER_CREATION'
  | 'FIELD_HUD'
  | 'NPC_DIALOGUE'
  | 'TUTORIAL_GUIDANCE'
  | 'BATTLE'
  | 'QUEST_BANNER'
  | 'TOWN_INTERIOR'
  | 'MENUS'
  | 'SYSTEM_CHROME'

export interface LogresVideoRecordingEvidence {
  readonly file: string
  readonly durationSeconds: number
  readonly width: number
  readonly height: number
  readonly fps: number
  readonly authority: LogresVideoReferenceAuthority
  readonly global3024Identity: 'UNPROVEN'
  readonly currentJpIdentity: 'UNPROVEN'
}

export interface LogresVideoObservation {
  readonly id: string
  readonly file: string
  readonly timestampSeconds: number
  readonly endTimestampSeconds?: number
  readonly domain: LogresVideoReferenceDomain
  readonly observation: string
  readonly authority: 'VERSION_SENSITIVE_USER_VIDEO'
  readonly historicalGlobalClaim: false
}

export const LOGRES_VIDEO_REFERENCE_AUTHORITY_POLICY =
  Object.freeze({
    global3024: Object.freeze({
      role: 'PRIMARY_HISTORICAL_AUTHORITY',
      mayConfirmHistoricalGlobal: true,
      requirement:
        'Requires evidence independently bound to recovered Global 3.0.24.',
    }),
    userSuppliedVideo: Object.freeze({
      role: 'VERSION_SENSITIVE_VISUAL_BEHAVIOR_REFERENCE',
      mayConfirmHistoricalGlobal: false,
      requirement:
        'Filename/timestamp observations are usable, but version/date must be independently proven before promotion to historical Global truth.',
    }),
    currentJp: Object.freeze({
      role: 'CORROBORATION_ONLY',
      mayConfirmHistoricalGlobal: false,
      requirement:
        'Current-JP similarity may support reconstruction choices but cannot replace missing Global evidence.',
    }),
  } as const)

export const LOGRES_VIDEO_REFERENCE_RECORDINGS =
  Object.freeze([
    Object.freeze({
      file: '1000027040.mp4',
      durationSeconds: 1183.57,
      width: 1280,
      height: 720,
      fps: 30,
      authority: 'VERSION_SENSITIVE_USER_VIDEO',
      global3024Identity: 'UNPROVEN',
      currentJpIdentity: 'UNPROVEN',
    }),
    Object.freeze({
      file: '1000027041.mp4',
      durationSeconds: 830.77,
      width: 608,
      height: 1080,
      fps: 30,
      authority: 'VERSION_SENSITIVE_USER_VIDEO',
      global3024Identity: 'UNPROVEN',
      currentJpIdentity: 'UNPROVEN',
    }),
    Object.freeze({
      file: '1000027042.mp4',
      durationSeconds: 1368.2,
      width: 1920,
      height: 1080,
      fps: 60,
      authority: 'VERSION_SENSITIVE_USER_VIDEO',
      global3024Identity: 'UNPROVEN',
      currentJpIdentity: 'UNPROVEN',
    }),
  ] as const satisfies readonly LogresVideoRecordingEvidence[])

export const LOGRES_VIDEO_REFERENCE_OBSERVATIONS =
  Object.freeze([
    {
      id: 'title-touch-start',
      file: '1000027040.mp4',
      timestampSeconds: 0,
      domain: 'TITLE',
      observation:
        'Logres title presentation shows Touch to start with small lower utility/account controls.',
    },
    {
      id: 'gender-selection',
      file: '1000027041.mp4',
      timestampSeconds: 37.9,
      domain: 'CHARACTER_CREATION',
      observation:
        'Select Gender uses a gold/orange framed header, large character art, male/female selection, arrows and a large red OK button.',
    },
    {
      id: 'npc-dialogue-akane',
      file: '1000027041.mp4',
      timestampSeconds: 55.8,
      domain: 'NPC_DIALOGUE',
      observation:
        'Dialogue overlays the field with a cream/gold framed box, gold Akane nameplate, large illustrated character presentation, Repeat at lower-left and Skip at lower-right.',
    },
    {
      id: 'field-hud-tutorial',
      file: '1000027041.mp4',
      timestampSeconds: 73.7,
      domain: 'FIELD_HUD',
      observation:
        'Portrait field shows gold top status HUD, black quest strip, compact actor/enemy sprites, World/Map/Clan/Group/Party/Direct shortcuts, Message and MENU controls.',
    },
    {
      id: 'tutorial-guidance-hand',
      file: '1000027041.mp4',
      timestampSeconds: 234.7,
      domain: 'TUTORIAL_GUIDANCE',
      observation:
        'A large tutorial hand pointer is shown above an interactable field target while multiple actors remain visible.',
    },
    {
      id: 'tutorial-guidance-combat-target',
      file: '1000027041.mp4',
      timestampSeconds: 252.6,
      domain: 'TUTORIAL_GUIDANCE',
      observation:
        'Field combat guidance uses a hand/target cue while the bottom field shortcut row remains visible.',
    },
    {
      id: 'battle-presentation',
      file: '1000027041.mp4',
      timestampSeconds: 91.6,
      endTimestampSeconds: 109.5,
      domain: 'BATTLE',
      observation:
        'Battle presentation places the enemy in the upper field and player in the lower field while retaining top quest/status presentation and bottom controls.',
    },
    {
      id: 'battle-result-congratulations',
      file: '1000027041.mp4',
      timestampSeconds: 288.4,
      endTimestampSeconds: 324.2,
      domain: 'BATTLE',
      observation:
        'Battle sequence visibly includes target/attack presentation and ends with a large Congratulations result overlay.',
    },
    {
      id: 'quest-cleared-overlay',
      file: '1000027041.mp4',
      timestampSeconds: 181.1,
      domain: 'QUEST_BANNER',
      observation:
        'A large blue-and-gold Quest Cleared overlay is centered over the field.',
    },
    {
      id: 'populated-town',
      file: '1000027042.mp4',
      timestampSeconds: 684,
      domain: 'TOWN_INTERIOR',
      observation:
        'Isometric town contains multiple named character/NPC sprites with a persistent gold top HUD and lower Message/MENU presentation.',
    },
    {
      id: 'interior-field',
      file: '1000027042.mp4',
      timestampSeconds: 748,
      domain: 'TOWN_INTERIOR',
      observation:
        'Interior/town field uses a blue floor with actor sprites while retaining the same general top/bottom presentation shell.',
    },
    {
      id: 'menu-family',
      file: '1000027040.mp4',
      timestampSeconds: 660,
      domain: 'MENUS',
      observation:
        'Crystal/store list uses a dedicated framed menu surface distinct from the field presentation.',
    },
    {
      id: 'event-menu-family',
      file: '1000027042.mp4',
      timestampSeconds: 1036,
      endTimestampSeconds: 1068,
      domain: 'MENUS',
      observation:
        'Event selection uses stacked colored promotional banners inside a dedicated menu surface.',
    },
    {
      id: 'visible-android-navigation-bar',
      file: '1000027041.mp4',
      timestampSeconds: 55.8,
      endTimestampSeconds: 73.7,
      domain: 'SYSTEM_CHROME',
      observation:
        'The portrait recording visibly includes a black Android navigation bar at the bottom with Back/Home/Recents-era controls; no Android status bar is visible above the game HUD in these sampled frames.',
    },
  ].map((entry) =>
    Object.freeze({
      ...entry,
      authority: 'VERSION_SENSITIVE_USER_VIDEO' as const,
      historicalGlobalClaim: false as const,
    }),
  ) as readonly LogresVideoObservation[])

export const LOGRES_VIDEO_REFERENCE_CONFLICTS =
  Object.freeze([
    Object.freeze({
      id: 'system-chrome-vs-current-immersive-reconstruction',
      videoEvidence:
        '1000027041.mp4 at 55.8s and 73.7s visibly shows an Android navigation bar.',
      globalApkEvidence:
        'Recovered Global 3.0.24 platform evidence identifies LFSActivity and Android lifecycle/JNI surfaces but currently does not establish a status/navigation-bar visibility policy.',
      reconstruction:
        'The current reconstruction intentionally uses immersive fullscreen presentation.',
      resolution:
        'Keep the video observation VERSION_SENSITIVE. It is a visible divergence from the current reconstruction, not proof that Global 3.0.24 historically required visible navigation chrome.',
    }),
    Object.freeze({
      id: 'video-lineage-unproven',
      videoEvidence:
        'The three user-supplied recordings visibly document Logres presentation and behavior.',
      globalApkEvidence:
        'No recovered Global APK/native identity currently binds these exact MP4 files to Global 3.0.24.',
      reconstruction:
        'Video-derived presentation may guide fidelity only at its version-sensitive ceiling.',
      resolution:
        'Do not relabel any observation as confirmed historical Global until an independent version/date predicate is established.',
    }),
  ] as const)

export const LOGRES_VIDEO_REFERENCE_UNRESOLVED =
  Object.freeze([
    'Exact build/version/date lineage of 1000027040.mp4, 1000027041.mp4 and 1000027042.mp4.',
    'Whether visible Android navigation chrome in the portrait recording reflects the historical Global client, a later client, device policy or recording environment.',
    'Any behavior between sampled timestamps that was not directly inspected.',
    'Exact historical Global identity/dialogue text for actors whose names appear only in version-sensitive footage.',
  ] as const)

export const LOGRES_VIDEO_REFERENCE_ARTIFACT =
  '/home/ubuntu/logres/artifacts/video-reference-canon/user-supplied-video-observations-20260925.md' as const

