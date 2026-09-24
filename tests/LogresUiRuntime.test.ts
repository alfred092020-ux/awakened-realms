import { describe, expect, it } from 'vitest'

import {
  LOGRES_UI_RUNTIME_EVIDENCE,
  LogresUiRuntime,
} from '../src/game/logres/ui/LogresUiRuntime'

describe('Logres UI runtime', () => {
  it('boots on the recovered field HUD surface', () => {
    const runtime = new LogresUiRuntime()

    expect(runtime.current).toEqual({
      surface: 'FIELD_HUD',
      zIndex: 0,
      linkedToRender: true,
      evidence: 'CONFIRMED_ORIGINAL',
    })
    expect(
      LOGRES_UI_RUNTIME_EVIDENCE
        .fieldMenuAsset.sourceEntry,
    ).toBe('field_menu.dds')
    expect(
      LOGRES_UI_RUNTIME_EVIDENCE
        .fieldMenuAsset.sourceLabel,
    ).toBe('CONFIRMED ORIGINAL')
  })

  it('opens and closes a field menu using recovered WindowManager semantics', () => {
    const runtime = new LogresUiRuntime()

    runtime.openFieldMenu()

    expect(runtime.stack.map((w) => w.surface))
      .toEqual(['FIELD_HUD', 'FIELD_MENU'])
    expect(runtime.current.zIndex).toBe(1)
    expect(runtime.current.linkedToRender).toBe(true)
    expect(runtime.current.evidence)
      .toBe('SUPPORTED_INFERENCE')

    runtime.closeTop()

    expect(runtime.stack.map((w) => w.surface))
      .toEqual(['FIELD_HUD'])
  })

  it('does not duplicate an already open field menu', () => {
    const runtime = new LogresUiRuntime()

    runtime.openFieldMenu()
    runtime.openFieldMenu()

    expect(runtime.stack).toHaveLength(2)
    expect(runtime.current.surface)
      .toBe('FIELD_MENU')
  })

  it('preserves explicit recovered WindowManager operations', () => {
    expect(
      LOGRES_UI_RUNTIME_EVIDENCE
        .windowManagerOperations,
    ).toEqual(
      expect.arrayContaining([
        'addWindow',
        'closeWindow',
        'bringToFront',
        'linkToRender',
        'terminateAllWindow',
      ]),
    )
  })

  it('keeps exact historical runtime-created window layout unresolved', () => {
    expect(
      LOGRES_UI_RUNTIME_EVIDENCE.unresolved,
    ).toContain(
      'Exact pixel placement for every runtime-created window is not derivable from native symbol names alone.',
    )
  })
})
