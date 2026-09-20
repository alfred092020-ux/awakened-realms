import {
  onValue,
  push,
  ref,
  update,
} from 'firebase/database'

import {
  getFirebaseServices,
  getFirebaseUser,
} from '../cloud/FirebaseClient'

export type MultiplayerInviteStatus =
  | 'pending'
  | 'accepted'
  | 'declined'

export type MultiplayerRoomStatus =
  | 'invited'
  | 'ready'
  | 'closed'

export interface MultiplayerInvite {
  id: string
  fromUid: string
  toUid: string
  roomId: string
  status:
    MultiplayerInviteStatus
  createdAt: number
  updatedAt: number
}

export interface MultiplayerRoom {
  id: string
  hostUid: string
  guestUid: string
  status:
    MultiplayerRoomStatus
  createdAt: number
  updatedAt: number
}

export interface MultiplayerRoomDraft {
  hostUid: string
  guestUid: string
  status:
    MultiplayerRoomStatus
  createdAt: number
  updatedAt: number
}

export function buildMultiplayerRoomDraft(
  hostUid: string,
  guestUid: string,
  now: number,
):
  MultiplayerRoomDraft {
  return {
    hostUid,

    guestUid,

    status:
      'invited',

    createdAt:
      now,

    updatedAt:
      now,
  }
}

function toRecord(
  value: unknown,
):
  Record<string, unknown> |
  undefined {
  return (
    typeof value ===
      'object' &&
    value !== null
  )
    ? value as Record<
        string,
        unknown
      >
    : undefined
}

function parseInvite(
  id: string,
  value: unknown,
):
  MultiplayerInvite |
  undefined {
  const data =
    toRecord(
      value,
    )

  if (!data) {
    return undefined
  }

  const status =
    data.status

  if (
    typeof data.fromUid !==
      'string' ||
    typeof data.toUid !==
      'string' ||
    typeof data.roomId !==
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

    roomId:
      data.roomId,

    status,

    createdAt:
      data.createdAt,

    updatedAt:
      data.updatedAt,
  }
}

function parseRoom(
  id: string,
  value: unknown,
):
  MultiplayerRoom |
  undefined {
  const data =
    toRecord(
      value,
    )

  if (!data) {
    return undefined
  }

  const status =
    data.status

  if (
    typeof data.hostUid !==
      'string' ||
    typeof data.guestUid !==
      'string' ||
    (
      status !==
        'invited' &&
      status !==
        'ready' &&
      status !==
        'closed'
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

    hostUid:
      data.hostUid,

    guestUid:
      data.guestUid,

    status,

    createdAt:
      data.createdAt,

    updatedAt:
      data.updatedAt,
  }
}

export class MultiplayerService {
  async createInvite(
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
        'Cannot invite yourself.',
      )
    }

    const roomKey =
      push(
        ref(
          services.realtime,
          'multiplayerRooms',
        ),
      ).key

    const inviteKey =
      push(
        ref(
          services.realtime,
          `multiplayerInvites/${targetUid}`,
        ),
      ).key

    if (
      !roomKey ||
      !inviteKey
    ) {
      throw new Error(
        'Could not create multiplayer IDs.',
      )
    }

    const now =
      Date.now()

    const room =
      buildMultiplayerRoomDraft(
        user.uid,
        targetUid,
        now,
      )

    const invite = {
      fromUid:
        user.uid,

      toUid:
        targetUid,

      roomId:
        roomKey,

      status:
        'pending',

      createdAt:
        now,

      updatedAt:
        now,
    }

    await update(
      ref(
        services.realtime,
      ),
      {
        [`multiplayerRooms/${roomKey}`]:
          room,

        [`multiplayerInvites/${targetUid}/${inviteKey}`]:
          invite,
      },
    )

    return {
      roomId:
        roomKey,

      inviteId:
        inviteKey,
    }
  }

  subscribeIncomingInvites(
    callback:
      (
        invites:
          MultiplayerInvite[],
      ) => void,
  ) {
    const services =
      getFirebaseServices()

    const user =
      getFirebaseUser()

    if (
      !services ||
      !user
    ) {
      callback([])

      return () => {}
    }

    return onValue(
      ref(
        services.realtime,
        `multiplayerInvites/${user.uid}`,
      ),

      (snapshot) => {
        const invites:
          MultiplayerInvite[] =
          []

        snapshot.forEach(
          (child) => {
            const invite =
              parseInvite(
                child.key ??
                  '',
                child.val(),
              )

            if (
              invite &&
              invite.status ===
                'pending'
            ) {
              invites.push(
                invite,
              )
            }
          },
        )

        invites.sort(
          (
            first,
            second,
          ) =>
            second.createdAt -
            first.createdAt,
        )

        callback(
          invites,
        )
      },
    )
  }

  async acceptInvite(
    invite:
      MultiplayerInvite,
  ) {
    const services =
      getFirebaseServices()

    const user =
      getFirebaseUser()

    if (
      !services ||
      !user ||
      invite.toUid !==
        user.uid
    ) {
      throw new Error(
        'Invite cannot be accepted.',
      )
    }

    const now =
      Date.now()

    await update(
      ref(
        services.realtime,
      ),
      {
        [`multiplayerInvites/${user.uid}/${invite.id}/status`]:
          'accepted',

        [`multiplayerInvites/${user.uid}/${invite.id}/updatedAt`]:
          now,

        [`multiplayerRooms/${invite.roomId}/status`]:
          'ready',

        [`multiplayerRooms/${invite.roomId}/updatedAt`]:
          now,
      },
    )
  }

  async declineInvite(
    invite:
      MultiplayerInvite,
  ) {
    const services =
      getFirebaseServices()

    const user =
      getFirebaseUser()

    if (
      !services ||
      !user ||
      invite.toUid !==
        user.uid
    ) {
      return
    }

    const now =
      Date.now()

    await update(
      ref(
        services.realtime,
      ),
      {
        [`multiplayerInvites/${user.uid}/${invite.id}/status`]:
          'declined',

        [`multiplayerInvites/${user.uid}/${invite.id}/updatedAt`]:
          now,

        [`multiplayerRooms/${invite.roomId}/status`]:
          'closed',

        [`multiplayerRooms/${invite.roomId}/updatedAt`]:
          now,
      },
    )
  }

  subscribeRoom(
    roomId: string,
    callback:
      (
        room:
          MultiplayerRoom |
          undefined,
      ) => void,
  ) {
    const services =
      getFirebaseServices()

    if (!services) {
      callback(
        undefined,
      )

      return () => {}
    }

    return onValue(
      ref(
        services.realtime,
        `multiplayerRooms/${roomId}`,
      ),

      (snapshot) => {
        callback(
          snapshot.exists()
            ? parseRoom(
                roomId,
                snapshot.val(),
              )
            : undefined,
        )
      },
    )
  }

  async closeRoom(
    roomId: string,
  ) {
    const services =
      getFirebaseServices()

    if (!services) {
      return
    }

    await update(
      ref(
        services.realtime,
        `multiplayerRooms/${roomId}`,
      ),
      {
        status:
          'closed',

        updatedAt:
          Date.now(),
      },
    )
  }
}
