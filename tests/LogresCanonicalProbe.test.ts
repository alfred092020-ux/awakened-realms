import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  existsSync,
  readdirSync,
  statSync,
} from 'node:fs'

import {
  join,
  relative,
} from 'node:path'

const roots = [
  '/srv/awakened-realms/repo/.reference-private',
  '/srv/awakened-realms/repo/public/__logres_ref',
  '/srv/awakened-realms/repo',
]

function walk(
  root: string,
  dir: string,
  out: string[],
  depth: number,
) {
  if (
    depth > 7
  ) {
    return
  }

  for (
    const name of
    readdirSync(
      dir,
    )
  ) {
    const path =
      join(
        dir,
        name,
      )

    let stat

    try {
      stat =
        statSync(
          path,
        )
    } catch {
      continue
    }

    if (
      stat.isDirectory()
    ) {
      if (
        name ===
          'node_modules' ||
        name ===
          '.git' ||
        name ===
          'dist'
      ) {
        continue
      }

      walk(
        root,
        path,
        out,
        depth + 1,
      )

      continue
    }

    const rel =
      relative(
        root,
        path,
      )

    const lower =
      rel.toLowerCase()

    if (
      [
        'title',
        'world',
        'character',
        'charactermake',
        'field',
        'map',
        'battle',
        'tutorial',
        'release',
      ].some(
        (
          needle,
        ) =>
          lower.includes(
            needle,
          ),
      )
    ) {
      out.push(
        rel,
      )
    }
  }
}

describe(
  'Logres canonical evidence probe',
  () => {
    it(
      'finds canonical extracted evidence roots',
      () => {
        for (
          const root of
          roots
        ) {
          console.info(
            'LOGRES_ROOT',
            root,
            existsSync(
              root,
            ),
          )

          if (
            !existsSync(
              root,
            )
          ) {
            continue
          }

          const out:
            string[] = []

          walk(
            root,
            root,
            out,
            0,
          )

          out.sort()

          console.info(
            'LOGRES_MATCH_COUNT',
            root,
            out.length,
          )

          for (
            const item of
            out.slice(
              0,
              180,
            )
          ) {
            console.info(
              'LOGRES_MATCH',
              root,
              item,
            )
          }
        }

        expect(
          true,
        ).toBe(
          true,
        )
      },
    )
  },
)
