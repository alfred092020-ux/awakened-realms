import {
  collection,
  deleteDoc,
  doc,
  getDoc,
  getDocs,
  limit,
  query,
  setDoc,
  updateDoc,
  where,
} from 'firebase/firestore'

import {
  getFirebaseServices,
  getFirebaseUser,
} from '../cloud/FirebaseClient'

import type {
  PublicPlayerProfile,
} from './LeaderboardService'

export type FriendRequestStatus =
  | 'pending'
  | 'accepted'
  | 'declined'

export type RelationshipState =
  | 'none'
  | 'outgoing'
  | 'incoming'
  | 'friends'

export interface FriendRequest {
  id: string
  fromUid: string
  toUid: string
  status: FriendRequestStatus
  createdAt: number
  updatedAt: number
}

export interface FriendRelationship {
  state: RelationshipState
  requestId?: string
}

export interface SocialOverview {
  friends:
    PublicPlayerProfile[]

  incoming:
    {
      request:
        FriendRequest

      profile:
        PublicPlayerProfile
    }[]

  outgoing:
    {
      request:
        FriendRequest

      profile:
        PublicPlayerProfile
    }[]
}

export function friendRequestDocumentId(
  fromUid: string,
  toUid: string,
) {
  return `${fromUid}__${toUid}`
}

function parseProfile(
  uid: string,
  data:
    Record<string, unknown>,
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

function parseRequest(
  id: string,
  data:
    Record<string, unknown>,
):
  FriendRequest |
  undefined {
  const status =
    data.status

  if (
    typeof data.fromUid !==
      'string' ||
    typeof data.toUid !==
      'string' ||
    (
      status !==
        'pending' &&
      status !==
        'accepted' &&
      status !==
        'declined'
    ) ||
    typeof data.createdAt !==
      'number' ||
    typeof data.updatedAt !==
      'number'
  ) {
    return undefined
  }

  return {
    id,

    fromUid:
      data.fromUid,

    toUid:
      data.toUid,

    status,

    createdAt:
      data.createdAt,

    updatedAt:
      data.updatedAt,
  }
}

export function relationshipFromRequests(
  currentUid: string,
  targetUid: string,
  requests:
    readonly FriendRequest[],
):
  FriendRelationship {
  const relevant =
    requests.filter(
      (request) =>
        (
          request.fromUid ===
            currentUid &&
          request.toUid ===
            targetUid
        ) ||
        (
          request.fromUid ===
            targetUid &&
          request.toUid ===
            currentUid
        ),
    )

  const accepted =
    relevant.find(
      (request) =>
        request.status ===
        'accepted',
    )

  if (accepted) {
    return {
      state:
        'friends',

      requestId:
        accepted.id,
    }
  }

  const incoming =
    relevant.find(
      (request) =>
        request.status ===
          'pending' &&
        request.toUid ===
          currentUid,
    )

  if (incoming) {
    return {
      state:
        'incoming',

      requestId:
        incoming.id,
    }
  }

  const outgoing =
    relevant.find(
      (request) =>
        request.status ===
          'pending' &&
        request.fromUid ===
          currentUid,
    )

  if (outgoing) {
    return {
      state:
        'outgoing',

      requestId:
        outgoing.id,
    }
  }

  return {
    state:
      'none',
  }
}

async function loadRequestsBetween(
  currentUid: string,
  targetUid: string,
):
  Promise<FriendRequest[]> {
  const services =
    getFirebaseServices()

  if (!services) {
    return []
  }

  const requests =
    collection(
      services.db,
      'friendRequests',
    )

  const [
    outgoing,
    incoming,
  ] =
    await Promise.all([
      getDocs(
        query(
          requests,

          where(
            'fromUid',
            '==',
            currentUid,
          ),

          where(
            'toUid',
            '==',
            targetUid,
          ),
        ),
      ),

      getDocs(
        query(
          requests,

          where(
            'fromUid',
            '==',
            targetUid,
          ),

          where(
            'toUid',
            '==',
            currentUid,
          ),
        ),
      ),
    ])

  const result:
    FriendRequest[] = []

  for (
    const snapshot of [
      outgoing,
      incoming,
    ]
  ) {
    snapshot.docs.forEach(
      (document) => {
        const request =
          parseRequest(
            document.id,
            document.data(),
          )

        if (request) {
          result.push(
            request,
          )
        }
      },
    )
  }

  return result
}

export class SocialService {
  async getProfile(
    uid: string,
  ) {
    const services =
      getFirebaseServices()

    if (!services) {
      return undefined
    }

    const snapshot =
      await getDoc(
        doc(
          services.db,
          'publicProfiles',
          uid,
        ),
      )

    if (!snapshot.exists()) {
      return undefined
    }

    return parseProfile(
      snapshot.id,
      snapshot.data(),
    )
  }

  async searchPlayers(
    displayName: string,
  ) {
    const services =
      getFirebaseServices()

    if (!services) {
      return []
    }

    const name =
      displayName
        .trim()
        .slice(
          0,
          40,
        )

    if (!name) {
      return []
    }

    const snapshot =
      await getDocs(
        query(
          collection(
            services.db,
            'publicProfiles',
          ),

          where(
            'displayName',
            '==',
            name,
          ),

          limit(
            10,
          ),
        ),
      )

    const profiles:
      PublicPlayerProfile[] =
      []

    snapshot.docs.forEach(
      (document) => {
        const profile =
          parseProfile(
            document.id,
            document.data(),
          )

        if (profile) {
          profiles.push(
            profile,
          )
        }
      },
    )

    return profiles
  }

  async getRelationship(
    targetUid: string,
  ):
    Promise<
      FriendRelationship
    > {
    const user =
      getFirebaseUser()

    if (
      !user ||
      user.uid === targetUid
    ) {
      return {
        state:
          'none',
      }
    }

    const requests =
      await loadRequestsBetween(
        user.uid,
        targetUid,
      )

    return relationshipFromRequests(
      user.uid,
      targetUid,
      requests,
    )
  }

  async sendFriendRequest(
    targetUid: string,
  ) {
    const services =
      getFirebaseServices()

    const user =
      getFirebaseUser()

    if (
      !services ||
      !user
    ) {
      throw new Error(
        'Sign in is required.',
      )
    }

    if (
      user.uid ===
      targetUid
    ) {
      throw new Error(
        'You cannot add yourself.',
      )
    }

    const existing =
      await loadRequestsBetween(
        user.uid,
        targetUid,
      )

    const current =
      relationshipFromRequests(
        user.uid,
        targetUid,
        existing,
      )

    if (
      current.state !==
      'none'
    ) {
      return current
    }

    const declined =
      existing.filter(
        (request) =>
          request.status ===
          'declined',
      )

    await Promise.all(
      declined.map(
        (request) =>
          deleteDoc(
            doc(
              services.db,
              'friendRequests',
              request.id,
            ),
          ),
      ),
    )

    const requestId =
      friendRequestDocumentId(
        user.uid,
        targetUid,
      )

    const now =
      Date.now()

    await setDoc(
      doc(
        services.db,
        'friendRequests',
        requestId,
      ),
      {
        fromUid:
          user.uid,

        toUid:
          targetUid,

        status:
          'pending',

        createdAt:
          now,

        updatedAt:
          now,
      },
    )

    return {
      state:
        'outgoing',

      requestId,
    } satisfies FriendRelationship
  }

  async respondToRequest(
    requestId: string,
    accept: boolean,
  ) {
    const services =
      getFirebaseServices()

    const user =
      getFirebaseUser()

    if (
      !services ||
      !user
    ) {
      throw new Error(
        'Sign in is required.',
      )
    }

    const reference =
      doc(
        services.db,
        'friendRequests',
        requestId,
      )

    const snapshot =
      await getDoc(
        reference,
      )

    if (!snapshot.exists()) {
      throw new Error(
        'Friend request not found.',
      )
    }

    const request =
      parseRequest(
        snapshot.id,
        snapshot.data(),
      )

    if (
      !request ||
      request.toUid !==
        user.uid ||
      request.status !==
        'pending'
    ) {
      throw new Error(
        'Friend request is not available.',
      )
    }

    await updateDoc(
      reference,
      {
        status:
          accept
            ? 'accepted'
            : 'declined',

        updatedAt:
          Date.now(),
      },
    )
  }

  async getOverview():
    Promise<
      SocialOverview
    > {
    const services =
      getFirebaseServices()

    const user =
      getFirebaseUser()

    if (
      !services ||
      !user
    ) {
      return {
        friends:
          [],

        incoming:
          [],

        outgoing:
          [],
      }
    }

    const requestsCollection =
      collection(
        services.db,
        'friendRequests',
      )

    const [
      sentSnapshot,
      receivedSnapshot,
    ] =
      await Promise.all([
        getDocs(
          query(
            requestsCollection,

            where(
              'fromUid',
              '==',
              user.uid,
            ),
          ),
        ),

        getDocs(
          query(
            requestsCollection,

            where(
              'toUid',
              '==',
              user.uid,
            ),
          ),
        ),
      ])

    const requests =
      new Map<
        string,
        FriendRequest
      >()

    for (
      const snapshot of [
        sentSnapshot,
        receivedSnapshot,
      ]
    ) {
      snapshot.docs.forEach(
        (document) => {
          const request =
            parseRequest(
              document.id,
              document.data(),
            )

          if (request) {
            requests.set(
              request.id,
              request,
            )
          }
        },
      )
    }

    const friendUids =
      new Set<string>()

    const incomingRequests:
      FriendRequest[] = []

    const outgoingRequests:
      FriendRequest[] = []

    for (
      const request of
      requests.values()
    ) {
      if (
        request.status ===
        'accepted'
      ) {
        friendUids.add(
          request.fromUid ===
            user.uid
            ? request.toUid
            : request.fromUid,
        )

        continue
      }

      if (
        request.status !==
        'pending'
      ) {
        continue
      }

      if (
        request.toUid ===
        user.uid
      ) {
        incomingRequests.push(
          request,
        )
      } else {
        outgoingRequests.push(
          request,
        )
      }
    }

    const profileCache =
      new Map<
        string,
        PublicPlayerProfile
      >()

    const neededUids =
      new Set<string>([
        ...friendUids,

        ...incomingRequests.map(
          (request) =>
            request.fromUid,
        ),

        ...outgoingRequests.map(
          (request) =>
            request.toUid,
        ),
      ])

    await Promise.all(
      Array.from(
        neededUids,
      ).map(
        async (uid) => {
          const profile =
            await this
              .getProfile(
                uid,
              )

          if (profile) {
            profileCache.set(
              uid,
              profile,
            )
          }
        },
      ),
    )

    const friends =
      Array.from(
        friendUids,
      )
        .map(
          (uid) =>
            profileCache.get(
              uid,
            ),
        )
        .filter(
          (
            profile,
          ): profile is
            PublicPlayerProfile =>
            Boolean(
              profile,
            ),
        )

    const incoming =
      incomingRequests
        .map(
          (request) => {
            const profile =
              profileCache.get(
                request.fromUid,
              )

            return profile
              ? {
                  request,
                  profile,
                }
              : undefined
          },
        )
        .filter(
          (
            value,
          ): value is {
            request:
              FriendRequest

            profile:
              PublicPlayerProfile
          } =>
            Boolean(
              value,
            ),
        )

    const outgoing =
      outgoingRequests
        .map(
          (request) => {
            const profile =
              profileCache.get(
                request.toUid,
              )

            return profile
              ? {
                  request,
                  profile,
                }
              : undefined
          },
        )
        .filter(
          (
            value,
          ): value is {
            request:
              FriendRequest

            profile:
              PublicPlayerProfile
          } =>
            Boolean(
              value,
            ),
        )

    return {
      friends,
      incoming,
      outgoing,
    }
  }
}
