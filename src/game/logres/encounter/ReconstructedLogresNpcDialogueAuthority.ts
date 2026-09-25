import {
  LOGRES_RECONSTRUCTED_NPC_INTERACTION_PROVENANCE,
  ReconstructedLogresNpcInteractionAuthority,
  type ReconstructedLogresNpcInteractionSnapshot,
  type ReconstructedLogresNpcTalkIntent,
} from './ReconstructedLogresNpcInteractionAuthority'

export const LOGRES_RECONSTRUCTED_NPC_DIALOGUE_PROVENANCE =
  'RECONSTRUCTED_SCRIPT' as const

export const LOGRES_RECONSTRUCTED_NPC_DIALOGUE_SERVER_STUB_PROVENANCE =
  'RECONSTRUCTED_SERVER_AUTHORITY_STUB' as const

export const LOGRES_GLOBAL_NPC_DIALOGUE_PAYLOAD_CONFIDENCE =
  'UNRESOLVED' as const

export type ReconstructedLogresNpcDialoguePhase =
  | 'READY'
  | 'REQUEST_PENDING'
  | 'DIALOGUE_OPEN'

export interface ReconstructedLogresNpcDialogueScript {
  provenance:
    typeof LOGRES_RECONSTRUCTED_NPC_DIALOGUE_PROVENANCE
  npcKey: string
  lines:
    readonly string[]
  historicalGlobalPayload:
    typeof LOGRES_GLOBAL_NPC_DIALOGUE_PAYLOAD_CONFIDENCE
}

export interface ReconstructedLogresNpcDialogueResponseStub {
  provenance:
    typeof LOGRES_RECONSTRUCTED_NPC_DIALOGUE_SERVER_STUB_PROVENANCE
  rawCode: number
  interpretation:
    'LOCAL_DIALOGUE_OPEN_STUB'
  historicalResponseCodeMeaning:
    typeof LOGRES_GLOBAL_NPC_DIALOGUE_PAYLOAD_CONFIDENCE
}

export interface ReconstructedLogresNpcDialogueSnapshot {
  provenance:
    typeof LOGRES_RECONSTRUCTED_NPC_DIALOGUE_PROVENANCE
  phase:
    ReconstructedLogresNpcDialoguePhase
  npcKey:
    string
  lineIndex:
    number | null
  currentLine:
    string | null
  lineCount:
    number
  completedSessions:
    number
  interaction:
    Readonly<ReconstructedLogresNpcInteractionSnapshot>
  historicalGlobalPayload:
    typeof LOGRES_GLOBAL_NPC_DIALOGUE_PAYLOAD_CONFIDENCE
  responseStub:
    Readonly<ReconstructedLogresNpcDialogueResponseStub> | null
}

function normalizeScript(
  script:
    Readonly<ReconstructedLogresNpcDialogueScript>,
): Readonly<ReconstructedLogresNpcDialogueScript> {
  const npcKey =
    script.npcKey.trim()

  if (!npcKey) {
    throw new Error(
      'NPC dialogue script npcKey must be non-empty',
    )
  }

  if (
    script.provenance !==
    LOGRES_RECONSTRUCTED_NPC_DIALOGUE_PROVENANCE
  ) {
    throw new Error(
      'NPC dialogue script must be explicitly reconstructed',
    )
  }

  if (
    script.historicalGlobalPayload !==
    LOGRES_GLOBAL_NPC_DIALOGUE_PAYLOAD_CONFIDENCE
  ) {
    throw new Error(
      'Historical Global dialogue payload must remain unresolved',
    )
  }

  const lines =
    script.lines.map(
      (
        line,
      ) =>
        line.trim(),
    )

  if (
    lines.length ===
      0 ||
    lines.some(
      (
        line,
      ) =>
        !line,
    )
  ) {
    throw new Error(
      'NPC dialogue script requires non-empty lines',
    )
  }

  return Object.freeze({
    provenance:
      LOGRES_RECONSTRUCTED_NPC_DIALOGUE_PROVENANCE,
    npcKey,
    lines:
      Object.freeze([
        ...lines,
      ]),
    historicalGlobalPayload:
      LOGRES_GLOBAL_NPC_DIALOGUE_PAYLOAD_CONFIDENCE,
  })
}

export class ReconstructedLogresNpcDialogueAuthority {
  private readonly interaction =
    new ReconstructedLogresNpcInteractionAuthority()

  private script:
    Readonly<ReconstructedLogresNpcDialogueScript>

  private phaseValue:
    ReconstructedLogresNpcDialoguePhase =
      'READY'

  private lineIndexValue:
    number | null =
      null

  private completedSessionsValue =
    0

  private responseStubValue:
    Readonly<ReconstructedLogresNpcDialogueResponseStub> | null =
      null

  constructor(
    script:
      Readonly<ReconstructedLogresNpcDialogueScript>,
  ) {
    this.script =
      normalizeScript(
        script,
      )
  }

  get phase() {
    return this.phaseValue
  }

  get isOpen() {
    return (
      this.phaseValue ===
      'DIALOGUE_OPEN'
    )
  }

  bindNpcState(
    input: {
      characterRef:
        | string
        | null
      canTalk: boolean
      inRange: boolean
    },
  ): void {
    if (
      this.phaseValue !==
      'READY'
    ) {
      throw new Error(
        'Cannot replace NPC dialogue state while a session is active',
      )
    }

    this.interaction
      .setNpcState({
        npcKey:
          this.script
            .npcKey,
        characterRef:
          input.characterRef,
        canTalk:
          input.canTalk,
        inRange:
          input.inRange,
      })
  }

  requestTalk():
    Readonly<ReconstructedLogresNpcTalkIntent> {
    if (
      this.phaseValue !==
      'READY'
    ) {
      throw new Error(
        'NPC dialogue session is already active',
      )
    }

    const intent =
      this.interaction
        .createTalkIntent()

    this.phaseValue =
      'REQUEST_PENDING'

    this.responseStubValue =
      null

    return intent
  }

  openFromReconstructedResponse(
    rawCode:
      number,
  ): Readonly<ReconstructedLogresNpcDialogueResponseStub> {
    if (
      this.phaseValue !==
      'REQUEST_PENDING'
    ) {
      throw new Error(
        'NPC dialogue request is not pending',
      )
    }

    this.interaction
      .recordTalkResponse(
        rawCode,
      )

    this.responseStubValue =
      Object.freeze({
        provenance:
          LOGRES_RECONSTRUCTED_NPC_DIALOGUE_SERVER_STUB_PROVENANCE,
        rawCode,
        interpretation:
          'LOCAL_DIALOGUE_OPEN_STUB',
        historicalResponseCodeMeaning:
          LOGRES_GLOBAL_NPC_DIALOGUE_PAYLOAD_CONFIDENCE,
      })

    this.phaseValue =
      'DIALOGUE_OPEN'

    this.lineIndexValue =
      0

    return this.responseStubValue
  }

  advance(): boolean {
    if (
      this.phaseValue !==
        'DIALOGUE_OPEN' ||
      this.lineIndexValue ===
        null
    ) {
      throw new Error(
        'NPC dialogue is not open',
      )
    }

    const next =
      this.lineIndexValue +
      1

    if (
      next <
      this.script
        .lines
        .length
    ) {
      this.lineIndexValue =
        next

      return false
    }

    this.close()

    return true
  }

  close(): void {
    if (
      this.phaseValue !==
      'DIALOGUE_OPEN'
    ) {
      throw new Error(
        'NPC dialogue is not open',
      )
    }

    this.lineIndexValue =
      null

    this.phaseValue =
      'READY'

    this.completedSessionsValue +=
      1

    this.interaction
      .releaseTalkGate()
  }

  snapshot():
    Readonly<ReconstructedLogresNpcDialogueSnapshot> {
    const currentLine =
      this.phaseValue ===
        'DIALOGUE_OPEN' &&
      this.lineIndexValue !==
        null
        ? this.script
            .lines[
              this.lineIndexValue
            ] ??
          null
        : null

    return Object.freeze({
      provenance:
        LOGRES_RECONSTRUCTED_NPC_DIALOGUE_PROVENANCE,
      phase:
        this.phaseValue,
      npcKey:
        this.script
          .npcKey,
      lineIndex:
        this.lineIndexValue,
      currentLine,
      lineCount:
        this.script
          .lines
          .length,
      completedSessions:
        this.completedSessionsValue,
      interaction:
        this.interaction
          .snapshot(),
      historicalGlobalPayload:
        LOGRES_GLOBAL_NPC_DIALOGUE_PAYLOAD_CONFIDENCE,
      responseStub:
        this.responseStubValue,
    })
  }
}

export const LOGRES_RECONSTRUCTED_FIELD_GUIDE_DIALOGUE =
  Object.freeze({
    provenance:
      LOGRES_RECONSTRUCTED_NPC_DIALOGUE_PROVENANCE,
    npcKey:
      'reconstructed-millennium-tree-guide',
    lines:
      Object.freeze([
        'Welcome to the Millennium Tree.',
      ] as const),
    historicalGlobalPayload:
      LOGRES_GLOBAL_NPC_DIALOGUE_PAYLOAD_CONFIDENCE,
  } as const)

export const LOGRES_NPC_DIALOGUE_EVIDENCE_BOUNDARY =
  Object.freeze({
    interactionProvenance:
      LOGRES_RECONSTRUCTED_NPC_INTERACTION_PROVENANCE,
    requestMessage:
      'C_GMCL_CHAR_TALK_REQ',
    responseHandler:
      'C_GMCL_CHAR_TALK_REQ_Response',
    dialogueWindow:
      'NpcDialogueWindow',
    exactHistoricalDialoguePayload:
      LOGRES_GLOBAL_NPC_DIALOGUE_PAYLOAD_CONFIDENCE,
  } as const)
