import {
  expect,
  test,
} from '@playwright/test'
import {
  mkdir,
  writeFile,
} from 'node:fs/promises'
import path from 'node:path'

async function worldObjectPoint(page, propertyName) {
  const logical = await page.evaluate(name => {
    const game = window.__AWAKENED_REALMS_GAME__
    const scene = game.scene.getScene('LogresFieldScene')
    const object = scene[name]
    if (!object) return null
    const camera = scene.cameras.main
    return {
      x: camera.x + (object.x - camera.worldView.x) * camera.zoom,
      y: camera.y + (object.y - camera.worldView.y) * camera.zoom,
      width: game.scale.width,
      height: game.scale.height,
    }
  }, propertyName)

  if (!logical) {
    throw new Error('Required Logres field object is unavailable.')
  }

  const box = await page.locator('canvas').boundingBox()
  if (!box) throw new Error('Game canvas has no bounds.')

  return {
    x: box.x + logical.x / logical.width * box.width,
    y: box.y + logical.y / logical.height * box.height,
  }
}

async function logicalPoint(page, logical) {
  const box = await page.locator('canvas').boundingBox()
  if (!box) throw new Error('Game canvas has no bounds.')
  return {
    x: box.x + logical.x / logical.width * box.width,
    y: box.y + logical.y / logical.height * box.height,
  }
}

async function dialoguePoint(page) {
  const logical = await page.evaluate(() => {
    const game = window.__AWAKENED_REALMS_GAME__
    const scene = game.scene.getScene('LogresFieldScene')
    const surface = scene.playableNpcDialogueSurface
    if (!surface) return null
    const camera = scene.cameras.main
    return {
      x:
        camera.x +
        (surface.x - camera.worldView.x) *
          camera.zoom,
      y:
        camera.y +
        (surface.y - camera.worldView.y) *
          camera.zoom,
      width: game.scale.width,
      height: game.scale.height,
    }
  })
  if (!logical) throw new Error('NPC dialogue surface is unavailable.')
  return logicalPoint(page, logical)
}

async function tapSelectedWeaponCover(page) {
  const accepted = await page.evaluate(() => {
    const game = window.__AWAKENED_REALMS_GAME__
    const scene = game.scene.getScene('LogresBattleScene')
    const cover = scene?.weaponCover
    if (!cover?.visible) return null

    scene.weaponCoverPointerDown = Object.freeze({
      x: cover.x,
      y: cover.y,
    })
    scene.handleWeaponCoverPointerUp({
      x: cover.x,
      y: cover.y,
    })

    return game.registry.get(
      'logres.playableBattle.authority',
    )?.acceptedCommandCount ?? null
  })

  if (!Number.isInteger(accepted)) {
    throw new Error('Production battle command was not accepted.')
  }
  return accepted
}

test(
  'exact-SHA critical behavior stays inside recovered Global evidence ceilings',
  async ({ page, request }, testInfo) => {
    const field = await request.get(
      '/__logres_ref/renderer-proof/002_000_00001/002_000_00001.map.bin',
    )

    test.skip(
      !field.ok() ||
        !(field.headers()['content-type'] ?? '').includes(
          'application/octet-stream',
        ),
      'Private recovered Global field runtime is not hydrated.',
    )

    await page.goto('/')
    await page.waitForFunction(
      () => Boolean(window.__AWAKENED_REALMS_GAME__?.scene),
    )

    await page.evaluate(() => {
      const game = window.__AWAKENED_REALMS_GAME__
      game.registry.set(
        'logres.protocol.C_GMCL_CHAR_CREATE_REQ',
        [0, 'Novice', 0, 1, 1, 1, 1, 1],
      )
      game.scene.start('LogresFieldScene')
    })

    await page.waitForFunction(
      () => {
        const registry = window.__AWAKENED_REALMS_GAME__.registry
        return (
          registry.get('logres.playableField.status') === 'READY' &&
          registry.get('logres.playableField.npcStatus') === 'READY' &&
          registry.get('logres.playableField.encounterStatus') === 'READY'
        )
      },
      undefined,
      { timeout: 20_000 },
    )

    const events = ['FIELD_READY']

    const npc = await worldObjectPoint(page, 'playableNpcMarker')
    await page.mouse.click(npc.x, npc.y)

    await page.waitForFunction(
      () =>
        window.__AWAKENED_REALMS_GAME__.registry.get(
          'logres.playableField.npcDialogue',
        )?.phase === 'DIALOGUE_OPEN',
      undefined,
      { timeout: 10_000 },
    )
    events.push('NPC_DIALOGUE_OPEN')

    const npcObservation = await page.evaluate(() => {
      const registry = window.__AWAKENED_REALMS_GAME__.registry
      return {
        intent: registry.get('logres.playableField.npcTalkIntent'),
        response: registry.get('logres.playableField.npcTalkResponseStub'),
        evidence: registry.get('logres.playableField.npcDialogueEvidence'),
        dialogue: registry.get('logres.playableField.npcDialogue'),
      }
    })

    for (let index = 0; index < 2; index += 1) {
      const point = await dialoguePoint(page)
      await page.mouse.click(point.x, point.y)
      if (index === 0) {
        await page.waitForFunction(
          () =>
            window.__AWAKENED_REALMS_GAME__.registry.get(
              'logres.playableField.npcDialogue',
            )?.lineIndex === 1,
        )
      }
    }

    await page.waitForFunction(
      () =>
        window.__AWAKENED_REALMS_GAME__.registry.get(
          'logres.playableField.npcStatus',
        ) === 'READY',
    )
    events.push('NPC_DIALOGUE_CLOSED')

    const encounter = await worldObjectPoint(
      page,
      'playableEncounterMarker',
    )
    await page.mouse.click(encounter.x, encounter.y)

    await page.waitForFunction(
      () => {
        const game = window.__AWAKENED_REALMS_GAME__
        return (
          game.scene.isActive('LogresBattleScene') &&
          game.registry.get('logres.playableBattle.status') === 'ACTIVE'
        )
      },
      undefined,
      { timeout: 10_000 },
    )
    events.push('BATTLE_ACTIVE')

    const entryObservation = await page.evaluate(() => {
      const registry = window.__AWAKENED_REALMS_GAME__.registry
      return {
        intent: registry.get('logres.playableField.encounterIntent'),
        authority: registry.get('logres.playableField.encounterAuthority'),
        responseStub: registry.get(
          'logres.playableField.battleEntryResponseStub',
        ),
        launchProvenance: registry.get(
          'logres.playableField.battleLaunchProvenance',
        ),
        kitIdentityProvenance: registry.get(
          'logres.playableField.battleKitIdentityProvenance',
        ),
      }
    })

    const battlePlan = await page.evaluate(() => {
      const authority = window.__AWAKENED_REALMS_GAME__.registry.get(
        'logres.playableBattle.authority',
      )
      return {
        accepted: authority?.acceptedCommandCount ?? 0,
        threshold: authority?.victoryThreshold ?? null,
      }
    })

    if (!Number.isInteger(battlePlan.threshold)) {
      throw new Error('Playable battle victory threshold is unavailable.')
    }

    for (
      let expected = battlePlan.accepted + 1;
      expected <= battlePlan.threshold;
      expected += 1
    ) {
      await tapSelectedWeaponCover(page)
      await page.waitForFunction(
        count => {
          const registry = window.__AWAKENED_REALMS_GAME__.registry
          const status = registry.get('logres.playableBattle.status')
          const authority = registry.get('logres.playableBattle.authority')
          return (
            status === 'FIELD_RETURN_READY' ||
            (Number.isInteger(authority?.acceptedCommandCount) &&
              authority.acceptedCommandCount >= count)
          )
        },
        expected,
        { timeout: 10_000 },
      )
    }

    await page.waitForFunction(
      () =>
        window.__AWAKENED_REALMS_GAME__.registry.get(
          'logres.playableBattle.status',
        ) === 'FIELD_RETURN_READY',
      undefined,
      { timeout: 10_000 },
    )
    events.push('BATTLE_VICTORY_READY', 'FIELD_RETURN_READY')

    const resolutionObservation = await page.evaluate(() => {
      const game = window.__AWAKENED_REALMS_GAME__
      const registry = game.registry
      const scene = game.scene.getScene('LogresBattleScene')
      const button = scene.demoReturnButton
      return {
        rewardApplied: registry.get('logres.playableBattle.rewardApplied'),
        resolutionPhase:
          registry.get('logres.playableBattle.resolution')?.phase ?? null,
        authorityPhase:
          registry.get('logres.playableBattle.authority')?.phase ?? null,
        inputProvenance: registry.get(
          'logres.playableBattle.inputProvenance',
        ),
        returnIntent: registry.get('logres.playableBattle.returnIntent'),
        returnPoint: button
          ? {
              x: button.x,
              y: button.y,
              width: game.scale.width,
              height: game.scale.height,
            }
          : null,
      }
    })

    if (!resolutionObservation.returnPoint) {
      throw new Error('Production field-return control is unavailable.')
    }

    const returnPoint = await logicalPoint(
      page,
      resolutionObservation.returnPoint,
    )
    await page.mouse.click(returnPoint.x, returnPoint.y)

    await page.waitForFunction(
      () => {
        const game = window.__AWAKENED_REALMS_GAME__
        return (
          game.scene.isActive('LogresFieldScene') &&
          game.registry.get('logres.playableField.status') === 'READY'
        )
      },
      undefined,
      { timeout: 20_000 },
    )
    events.push('FIELD_READY_RETURNED')

    const observed = {
      events,
      npc: {
        requestMessage: npcObservation.evidence?.requestMessage ?? null,
        responseHandler: npcObservation.evidence?.responseHandler ?? null,
        dialogueWindow: npcObservation.evidence?.dialogueWindow ?? null,
        exactHistoricalDialoguePayload:
          npcObservation.evidence?.exactHistoricalDialoguePayload ?? null,
        intentProvenance: npcObservation.intent?.provenance ?? null,
        responseProvenance: npcObservation.response?.provenance ?? null,
        historicalResponseCodeMeaning:
          npcObservation.response?.historicalResponseCodeMeaning ?? null,
        dialogueProvenance: npcObservation.dialogue?.provenance ?? null,
      },
      battleEntry: {
        intentProvenance: entryObservation.intent?.provenance ?? null,
        responseStubProvenance:
          entryObservation.responseStub?.provenance ?? null,
        responseCode: entryObservation.responseStub?.rawCode ?? null,
        lastResponseCode:
          entryObservation.authority?.lastResponseCode ?? null,
        entryAccepted: entryObservation.authority?.entryAccepted ?? null,
        battleInitialized:
          entryObservation.authority?.battleInitialized ?? null,
        launchProvenance: entryObservation.launchProvenance ?? null,
        kitIdentityProvenance:
          entryObservation.kitIdentityProvenance ?? null,
      },
      resolution: {
        rewardApplied: resolutionObservation.rewardApplied,
        resolutionPhase: resolutionObservation.resolutionPhase,
        authorityPhase: resolutionObservation.authorityPhase,
        inputProvenance: resolutionObservation.inputProvenance,
        returnIntent: resolutionObservation.returnIntent,
        returnScene: 'LogresFieldScene',
      },
    }

    const expected = {
      events: [
        'FIELD_READY',
        'NPC_DIALOGUE_OPEN',
        'NPC_DIALOGUE_CLOSED',
        'BATTLE_ACTIVE',
        'BATTLE_VICTORY_READY',
        'FIELD_RETURN_READY',
        'FIELD_READY_RETURNED',
      ],
      npc: {
        requestMessage: 'C_GMCL_CHAR_TALK_REQ',
        responseHandler: 'C_GMCL_CHAR_TALK_REQ_Response',
        dialogueWindow: 'NpcDialogueWindow',
        exactHistoricalDialoguePayload: 'UNRESOLVED',
        intentProvenance: 'RECONSTRUCTED',
        responseProvenance: 'RECONSTRUCTED_SERVER_AUTHORITY_STUB',
        historicalResponseCodeMeaning: 'UNRESOLVED',
        dialogueProvenance: 'RECONSTRUCTED_SCRIPT',
      },
      battleEntry: {
        intentProvenance: 'RECONSTRUCTED',
        responseStubProvenance: 'RECONSTRUCTED_SERVER_AUTHORITY_STUB',
        responseCode: 1,
        lastResponseCode: 1,
        entryAccepted: true,
        battleInitialized: true,
        launchProvenance: 'RECONSTRUCTED',
        kitIdentityProvenance: 'RECONSTRUCTED_LOCAL_IDENTIFIERS',
      },
      resolution: {
        rewardApplied: true,
        resolutionPhase: 'field-return-ready',
        authorityPhase: 'victory-ready',
        inputProvenance: 'RECONSTRUCTED_PLAYABILITY_FALLBACK',
        returnIntent: {
          provenance: 'RECONSTRUCTED',
          sceneKey: 'LogresFieldScene',
        },
        returnScene: 'LogresFieldScene',
      },
    }

    expect(observed).toEqual(expected)

    const rawSha = process.env.LOGRES_VERIFY_SHA
    const exactSha =
      rawSha && /^[0-9a-f]{40}$/i.test(rawSha)
        ? rawSha
        : 'LOCAL_WORKTREE'

    const artifact = {
      schema: 'logres-behavioral-fidelity-v1',
      sha: exactSha,
      verdict: 'PASS',
      expected,
      observed,
      evidenceCeilings: {
        retiredNpcDialoguePayload: 'UNRESOLVED',
        retiredNpcTalkResponseMeaning: 'UNRESOLVED',
        retiredBattleEntryServerOutcome:
          'RECONSTRUCTED_SERVER_AUTHORITY_STUB',
        retiredRewardPayload: 'RECONSTRUCTED_SERVER_AUTHORITY_STUB',
      },
    }

    const artifactPath =
      exactSha === 'LOCAL_WORKTREE'
        ? testInfo.outputPath('behavioral-fidelity.json')
        : path.join(
            '/home/ubuntu/logres/artifacts/behavioral-fidelity',
            exactSha + '.json',
          )

    await mkdir(path.dirname(artifactPath), { recursive: true })
    await writeFile(
      artifactPath,
      JSON.stringify(artifact, null, 2) + '\n',
    )
  },
)
