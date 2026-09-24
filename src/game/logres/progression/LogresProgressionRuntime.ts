import {
  LOGRES_GLOBAL_3024_JOBS,
  LOGRES_GLOBAL_3024_SYSTEMS_UNRESOLVED,
} from '../systems/LogresGlobal3024SystemsEvidence'

export const LOGRES_PROGRESSION_RUNTIME_PROVENANCE =
  'RECONSTRUCTED_SERVER_AUTHORITY' as const
export const LOGRES_PROGRESSION_PARAMETER_PROVENANCE =
  'RECONSTRUCTED_EXPLICIT_PARAMETER' as const

export interface LogresProgressionSession {
  readonly accountId: string
  readonly sessionId: string
  readonly authenticated: boolean
}

export interface LogresLevelCurve {
  readonly provenance: typeof LOGRES_PROGRESSION_PARAMETER_PROVENANCE
  readonly curveKey: string
  readonly cumulativeXpByLevel: readonly number[]
}

export interface LogresProgressionRecord {
  readonly provenance: typeof LOGRES_PROGRESSION_RUNTIME_PROVENANCE
  readonly accountId: string
  readonly characterLevel: number
  readonly characterXp: number
  readonly activeJobId: string | null
  readonly jobs: Readonly<Record<string, Readonly<{ jobId: string; level: number; xp: number }>>>
  readonly appliedCommandIds: readonly string[]
  readonly revision: number
}

export interface LogresProgressionSeed {
  readonly characterLevel: number
  readonly characterXp: number
  readonly activeJobId: string | null
  readonly jobs: Readonly<Record<string, Readonly<{ level: number; xp: number }>>>
}

export interface LogresProgressionParameters {
  readonly characterCurve: LogresLevelCurve | null
  readonly jobCurves: Readonly<Record<string, LogresLevelCurve>>
}

export interface LogresProgressionPersistence {
  load(accountId: string): LogresProgressionRecord | null
  save(record: LogresProgressionRecord): void
}

export const LOGRES_PROGRESSION_EVIDENCE = Object.freeze({
  jobChangeRequest: LOGRES_GLOBAL_3024_JOBS.jobChange,
  jobChangeProjection: LOGRES_GLOBAL_3024_JOBS.jobChangeInfo,
  serverTables: LOGRES_GLOBAL_3024_JOBS.serverTables,
  authorityInterpretation: LOGRES_GLOBAL_3024_JOBS.authorityInterpretation,
  unresolvedServerFormulas: LOGRES_GLOBAL_3024_SYSTEMS_UNRESOLVED.filter(
    (value) => value.includes('server-side validation formulas'),
  ),
  formulaPolicy:
    'No historical XP/level threshold is guessed. Unknown curves fail closed until an explicit reconstructed parameter is supplied.',
} as const)

function requireIdentity(value: string, label: string): string {
  const normalized = value.trim()
  if (!normalized) throw new Error(`${label} must be non-empty`)
  return normalized
}

function requireNonNegativeInteger(value: number, label: string): number {
  if (!Number.isSafeInteger(value) || value < 0) {
    throw new Error(`${label} must be a non-negative safe integer`)
  }
  return value
}

function requireSession(session: LogresProgressionSession): string {
  if (!session.authenticated) {
    throw new Error('Progression mutation requires an authenticated session')
  }
  requireIdentity(session.sessionId, 'Progression sessionId')
  return requireIdentity(session.accountId, 'Progression accountId')
}

export function createLogresLevelCurve(
  curveKey: string,
  cumulativeXpByLevel: readonly number[],
): Readonly<LogresLevelCurve> {
  const key = requireIdentity(curveKey, 'Progression curveKey')
  if (cumulativeXpByLevel.length === 0 || cumulativeXpByLevel[0] !== 0) {
    throw new Error('Progression level curve must begin with level-1 threshold 0')
  }
  let previous = -1
  const values = cumulativeXpByLevel.map((value, index) => {
    const next = requireNonNegativeInteger(value, `Progression threshold level ${index + 1}`)
    if (index > 0 && next <= previous) {
      throw new Error('Progression level thresholds must be strictly increasing')
    }
    previous = next
    return next
  })
  return Object.freeze({
    provenance: LOGRES_PROGRESSION_PARAMETER_PROVENANCE,
    curveKey: key,
    cumulativeXpByLevel: Object.freeze(values),
  })
}

function levelForXp(curve: LogresLevelCurve, xp: number): number {
  let level = 1
  for (let index = 1; index < curve.cumulativeXpByLevel.length; index += 1) {
    if (xp < curve.cumulativeXpByLevel[index]) break
    level = index + 1
  }
  return level
}

function requireCurve(curve: LogresLevelCurve | null, label: string): LogresLevelCurve {
  if (curve === null) {
    throw new Error(
      `${label} XP curve is unresolved; refusing to invent historical progression formula`,
    )
  }
  return curve
}

function cloneRecord(record: LogresProgressionRecord): LogresProgressionRecord {
  const jobs: Record<string, Readonly<{ jobId: string; level: number; xp: number }>> = {}
  for (const [jobId, state] of Object.entries(record.jobs)) {
    jobs[jobId] = Object.freeze({ ...state })
  }
  return Object.freeze({
    ...record,
    jobs: Object.freeze(jobs),
    appliedCommandIds: Object.freeze([...record.appliedCommandIds]),
  })
}

export class InMemoryLogresProgressionPersistence
  implements LogresProgressionPersistence {
  private readonly records = new Map<string, LogresProgressionRecord>()

  load(accountId: string): LogresProgressionRecord | null {
    const record = this.records.get(accountId)
    return record ? cloneRecord(record) : null
  }

  save(record: LogresProgressionRecord): void {
    this.records.set(record.accountId, cloneRecord(record))
  }
}

export class LogresProgressionAuthority {
  private readonly persistence: LogresProgressionPersistence
  private readonly parameters: LogresProgressionParameters

  constructor(
    persistence: LogresProgressionPersistence,
    parameters: LogresProgressionParameters,
  ) {
    this.persistence = persistence
    this.parameters = parameters
  }

  initialize(
    session: LogresProgressionSession,
    seed: LogresProgressionSeed,
  ): LogresProgressionRecord {
    const accountId = requireSession(session)
    const existing = this.persistence.load(accountId)
    if (existing) return existing

    requireNonNegativeInteger(seed.characterXp, 'Character XP')
    if (!Number.isSafeInteger(seed.characterLevel) || seed.characterLevel < 1) {
      throw new Error('Character level must be a positive safe integer')
    }
    if (
      this.parameters.characterCurve !== null &&
      levelForXp(this.parameters.characterCurve, seed.characterXp) !== seed.characterLevel
    ) {
      throw new Error('Character level does not match the supplied explicit XP curve')
    }

    const jobs: Record<string, Readonly<{ jobId: string; level: number; xp: number }>> = {}
    for (const [rawJobId, state] of Object.entries(seed.jobs)) {
      const jobId = requireIdentity(rawJobId, 'Progression jobId')
      requireNonNegativeInteger(state.xp, `Job ${jobId} XP`)
      if (!Number.isSafeInteger(state.level) || state.level < 1) {
        throw new Error(`Job ${jobId} level must be a positive safe integer`)
      }
      const curve = this.parameters.jobCurves[jobId]
      if (curve && levelForXp(curve, state.xp) !== state.level) {
        throw new Error(`Job ${jobId} level does not match the supplied explicit XP curve`)
      }
      jobs[jobId] = Object.freeze({ jobId, level: state.level, xp: state.xp })
    }

    const activeJobId =
      seed.activeJobId === null
        ? null
        : requireIdentity(seed.activeJobId, 'Progression activeJobId')
    if (activeJobId !== null && !(activeJobId in jobs)) {
      throw new Error('Active job must exist in the explicit seed job state')
    }

    const record = cloneRecord({
      provenance: LOGRES_PROGRESSION_RUNTIME_PROVENANCE,
      accountId,
      characterLevel: seed.characterLevel,
      characterXp: seed.characterXp,
      activeJobId,
      jobs: Object.freeze(jobs),
      appliedCommandIds: Object.freeze([]),
      revision: 0,
    })
    this.persistence.save(record)
    return record
  }

  read(session: LogresProgressionSession): LogresProgressionRecord | null {
    return this.persistence.load(requireSession(session))
  }

  grantCharacterXp(
    session: LogresProgressionSession,
    amount: number,
    commandId: string,
  ): LogresProgressionRecord {
    const accountId = requireSession(session)
    const command = requireIdentity(commandId, 'Progression commandId')
    const delta = requireNonNegativeInteger(amount, 'Character XP grant')
    const current = this.persistence.load(accountId)
    if (!current) throw new Error('Progression state must be initialized before XP grant')
    if (current.appliedCommandIds.includes(command)) return current

    const curve = requireCurve(this.parameters.characterCurve, 'Character progression')
    const xp = current.characterXp + delta
    if (!Number.isSafeInteger(xp)) throw new Error('Character XP overflow')
    const next = cloneRecord({
      ...current,
      characterXp: xp,
      characterLevel: levelForXp(curve, xp),
      appliedCommandIds: [...current.appliedCommandIds, command],
      revision: current.revision + 1,
    })
    this.persistence.save(next)
    return next
  }

  changeJob(
    session: LogresProgressionSession,
    jobId: string,
    commandId: string,
  ): LogresProgressionRecord {
    const accountId = requireSession(session)
    const job = requireIdentity(jobId, 'Progression jobId')
    const command = requireIdentity(commandId, 'Progression commandId')
    const current = this.persistence.load(accountId)
    if (!current) throw new Error('Progression state must be initialized before job change')
    if (current.appliedCommandIds.includes(command)) return current
    if (!(job in current.jobs)) {
      throw new Error('Job change requires an explicitly known job state')
    }
    const next = cloneRecord({
      ...current,
      activeJobId: job,
      appliedCommandIds: [...current.appliedCommandIds, command],
      revision: current.revision + 1,
    })
    this.persistence.save(next)
    return next
  }

  grantJobXp(
    session: LogresProgressionSession,
    jobId: string,
    amount: number,
    commandId: string,
  ): LogresProgressionRecord {
    const accountId = requireSession(session)
    const job = requireIdentity(jobId, 'Progression jobId')
    const command = requireIdentity(commandId, 'Progression commandId')
    const delta = requireNonNegativeInteger(amount, 'Job XP grant')
    const current = this.persistence.load(accountId)
    if (!current) throw new Error('Progression state must be initialized before job XP grant')
    if (current.appliedCommandIds.includes(command)) return current

    const jobState = current.jobs[job]
    if (!jobState) {
      throw new Error('Job XP grant requires an explicitly known job state')
    }
    const curve = requireCurve(this.parameters.jobCurves[job] ?? null, `Job ${job}`)
    const xp = jobState.xp + delta
    if (!Number.isSafeInteger(xp)) throw new Error('Job XP overflow')
    const jobs = {
      ...current.jobs,
      [job]: Object.freeze({ jobId: job, xp, level: levelForXp(curve, xp) }),
    }
    const next = cloneRecord({
      ...current,
      jobs: Object.freeze(jobs),
      appliedCommandIds: [...current.appliedCommandIds, command],
      revision: current.revision + 1,
    })
    this.persistence.save(next)
    return next
  }
}
