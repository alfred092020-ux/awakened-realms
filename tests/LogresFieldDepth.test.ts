import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_FIELD_DEPTH_FORMULA_EVIDENCE,
  LOGRES_GLOBAL_FIELD_DEPTH_APPLICATION,
  logresDepthToTopZ,
  logresDepthToZ,
} from '../src/game/logres/field/LogresFieldDepth'

describe(
  'Logres native field depth formulas',
  () => {
    it(
      'retains explicit native and Global provenance labels',
      () => {
        expect(
          LOGRES_FIELD_DEPTH_FORMULA_EVIDENCE,
        ).toBe(
          'CONFIRMED_ORIGINAL_CURRENT_JP_NATIVE',
        )

        expect(
          LOGRES_GLOBAL_FIELD_DEPTH_APPLICATION,
        ).toBe(
          'SUPPORTED_INFERENCE',
        )
      },
    )
    it.each([
      [
        0,
        0,
      ],
      [
        1,
        0.05000000074505806,
      ],
      [
        2,
        0.10000000149011612,
      ],
      [
        7,
        0.3499999940395355,
      ],
      [
        100,
        5,
      ],
      [
        0xffffffff,
        214748368,
      ],
    ])(
      'matches recovered float32 depthToZ(%i)',
      (
        depth,
        expected,
      ) => {
        expect(
          logresDepthToZ(
            depth,
          ),
        ).toBe(
          expected,
        )
      },
    )
    it.each([
      [
        0,
        0.002500000176951289,
      ],
      [
        1,
        0.05250000208616257,
      ],
      [
        2,
        0.10249999910593033,
      ],
      [
        7,
        0.35249999165534973,
      ],
      [
        100,
        5.002500057220459,
      ],
      [
        0xffffffff,
        214748368,
      ],
    ])(
      'matches recovered top-depth FMADD result for %i',
      (
        depth,
        expected,
      ) => {
        expect(
          logresDepthToTopZ(
            depth,
          ),
        ).toBe(
          expected,
        )
      },
    )
    it.each([
      -1,
      1.5,
      Number.NaN,
      0x100000000,
    ])(
      'rejects values outside the native uint32 depth domain',
      (
        depth,
      ) => {
        expect(
          () =>
            logresDepthToZ(
              depth,
            ),
        ).toThrow(
          'native uint32',
        )

        expect(
          () =>
            logresDepthToTopZ(
              depth,
            ),
        ).toThrow(
          'native uint32',
        )
      },
    )
  },
)
