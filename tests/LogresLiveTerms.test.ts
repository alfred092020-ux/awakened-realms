import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { expect, it } from 'vitest'

import {
  LOGRES_GLOBAL_3024_TERMS_GATE,
} from '../src/game/logres/onboarding/LogresGlobal3024BootEvidence'

it('scans live cache terms without exporting private strings or snippets', () => {
  const output = execFileSync(
    'python3',
    ['-B', 'scripts/logres/inspect_live_terms.py', '--self-test'],
    { encoding: 'utf8' },
  )
  expect(output).toContain('Logres live bounded term inspector self-test: PASS')
})

it('shows neutral player-facing copy without developer reconstruction wording', () => {
  const source = readFileSync(
    'src/game/scenes/LogresTermsScene.ts',
    'utf8',
  )

  const playerCopy = source.match(
    /export const LOGRES_TERMS_PLAYER_COPY =[\s\S]*?export class LogresTermsScene/,
  )?.[0]

  expect(playerCopy).toBeTruthy()
  expect(playerCopy).toContain(
    'The Terms of Use page is unavailable in this build.',
  )
  expect(playerCopy).toContain(
    'No legal text is reproduced on this screen.',
  )
  expect(playerCopy).toContain("action:\n      'Continue'")

  for (const forbidden of [
    'reconstruction',
    'unresolved',
    'evidence',
    'Original Global Terms',
    'hosted page',
  ]) {
    expect(playerCopy?.toLowerCase())
      .not.toContain(forbidden.toLowerCase())
  }
})

it('keeps the retired hosted terms payload unresolved behind the player boundary', () => {
  expect(LOGRES_GLOBAL_3024_TERMS_GATE.exactHostedPage)
    .toBe('UNRESOLVED')
  expect(LOGRES_GLOBAL_3024_TERMS_GATE.authOperation)
    .toBe('agree_to_terms')
  expect(LOGRES_GLOBAL_3024_TERMS_GATE.agreementScene)
    .toBe('AgreementWebView')
})
