import {
  collection,
  doc,
  getCountFromServer,
  getDocs,
  limit,
  orderBy,
  query,
  setDoc,
  where,
} from 'firebase/firestore'

import {
  getFirebaseServices,
  getFirebaseUser,
} from '../cloud/FirebaseClient'

import type {
  MetaState,
} from '../meta/MetaTypes'

export interface PublicPlayerProfile {
  uid: string
  displayName: string
  bestWave: number
  lifetimeRuns: number
  power: number
  updatedAt: number
}

export interface LeaderboardEntry
  extends PublicPlayerProfile {
  rank: number
}

export function calculateProfilePower(
  state: MetaState,
) {
  return (
    100 +
    state.upgrades[
      'attack-training'
    ] * 5 +
    state.upgrades[
      'vitality-training'
    ] * 6 +
    state.upgrades[
      'haste-training'
    ] * 3
  )
}

export function buildPublicProfile(
  uid: string,
  displayName: string,
  state: MetaState,
  updatedAt: number,
): PublicPlayerProfile {
  const safeName =
    displayName
      .trim()
      .slice(
        0,
        40,
      ) ||
    'Awakened Player'

  return {
    uid,

    displayName:
      safeName,

    bestWave:
      Math.max(
        0,
        Math.floor(
          state.bestWave,
        ),
      ),

    lifetimeRuns:
      Math.max(
        0,
        Math.floor(
          state.lifetimeRuns,
        ),
      ),

    power:
      calculateProfilePower(
        state,
      ),

    updatedAt:
      Math.max(
        0,
        Math.floor(
          updatedAt,
        ),
      ),
  }
}

function parseProfile(
  uid: string,
  data: Record<
    string,
    unknown
  >,
):
  PublicPlayerProfile |
  undefined {
  if (
    typeof data.displayName !==
      'string' ||
    typeof data.bestWave !==
      'number' ||
    typeof data.lifetimeRuns !==
      'number' ||
    typeof data.power !==
      'number' ||
    typeof data.updatedAt !==
      'number'
  ) {
    return undefined
  }

  return {
    uid,

    displayName:
      data.displayName,

    bestWave:
      data.bestWave,

    lifetimeRuns:
      data.lifetimeRuns,

    power:
      data.power,

    updatedAt:
      data.updatedAt,
  }
}

export class LeaderboardService {
  async publishIfSignedIn(
    state: MetaState,
    updatedAt = Date.now(),
  ) {
    const services =
      getFirebaseServices()

    const user =
      getFirebaseUser()

    if (
      !services ||
      !user
    ) {
      return false
    }

    const profile =
      buildPublicProfile(
        user.uid,

        user.displayName ??
          'Awakened Player',

        state,
        updatedAt,
      )

    await setDoc(
      doc(
        services.db,
        'publicProfiles',
        user.uid,
      ),
      profile,
    )

    return true
  }

  async getTopProfiles(
    requestedLimit = 20,
  ):
    Promise<
      LeaderboardEntry[]
    > {
    const services =
      getFirebaseServices()

    if (!services) {
      return []
    }

    const safeLimit =
      Math.min(
        50,
        Math.max(
          1,
          Math.floor(
            requestedLimit,
          ),
        ),
      )

    const snapshot =
      await getDocs(
        query(
          collection(
            services.db,
            'publicProfiles',
          ),

          orderBy(
            'bestWave',
            'desc',
          ),

          limit(
            safeLimit,
          ),
        ),
      )

    const result:
      LeaderboardEntry[] = []

    snapshot.docs.forEach(
      (
        document,
        index,
      ) => {
        const profile =
          parseProfile(
            document.id,
            document.data(),
          )

        if (!profile) {
          return
        }

        result.push({
          ...profile,

          rank:
            index + 1,
        })
      },
    )

    return result
  }

  async getMyRank(
    bestWave: number,
  ):
    Promise<
      number | null
    > {
    const services =
      getFirebaseServices()

    const user =
      getFirebaseUser()

    if (
      !services ||
      !user
    ) {
      return null
    }

    const higherScores =
      await getCountFromServer(
        query(
          collection(
            services.db,
            'publicProfiles',
          ),

          where(
            'bestWave',
            '>',
            Math.max(
              0,
              Math.floor(
                bestWave,
              ),
            ),
          ),
        ),
      )

    return (
      higherScores
        .data()
        .count +
      1
    )
  }
}
