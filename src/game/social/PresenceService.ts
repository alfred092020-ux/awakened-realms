import {
  onDisconnect,
  onValue,
  ref,
  serverTimestamp,
  set,
} from 'firebase/database'

import {
  getFirebaseServices,
  getFirebaseUser,
} from '../cloud/FirebaseClient'

export interface PresenceState {
  uid: string
  online: boolean
  lastChanged: number
}

let activeUid:
  string | undefined

let stopConnection:
  (() => void) |
  undefined

export function normalizePresence(
  uid: string,
  value: unknown,
):
  PresenceState {
  if (
    typeof value !==
      'object' ||
    value === null
  ) {
    return {
      uid,
      online:
        false,
      lastChanged:
        0,
    }
  }

  const record =
    value as Record<
      string,
      unknown
    >

  return {
    uid,

    online:
      record.online ===
      true,

    lastChanged:
      typeof record.lastChanged ===
        'number'
        ? record.lastChanged
        : 0,
  }
}

export class PresenceService {
  async start() {
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

    if (
      activeUid ===
        user.uid &&
      stopConnection
    ) {
      return true
    }

    if (
      activeUid &&
      activeUid !==
        user.uid
    ) {
      await this.stop()
    }

    const connectedRef =
      ref(
        services.realtime,
        '.info/connected',
      )

    const statusRef =
      ref(
        services.realtime,
        `presence/${user.uid}`,
      )

    activeUid =
      user.uid

    stopConnection =
      onValue(
        connectedRef,
        (snapshot) => {
          if (
            snapshot.val() !==
            true
          ) {
            return
          }

          void onDisconnect(
            statusRef,
          )
            .set({
              online:
                false,

              lastChanged:
                serverTimestamp(),
            })
            .then(
              () =>
                set(
                  statusRef,
                  {
                    online:
                      true,

                    lastChanged:
                      serverTimestamp(),
                  },
                ),
            )
            .catch(
              () => undefined,
            )
        },
      )

    return true
  }

  async stop() {
    const services =
      getFirebaseServices()

    if (
      services &&
      activeUid
    ) {
      const statusRef =
        ref(
          services.realtime,
          `presence/${activeUid}`,
        )

      try {
        await onDisconnect(
          statusRef,
        ).cancel()

        await set(
          statusRef,
          {
            online:
              false,

            lastChanged:
              serverTimestamp(),
          },
        )
      } catch {
        // Best-effort presence cleanup.
      }
    }

    stopConnection?.()

    stopConnection =
      undefined

    activeUid =
      undefined
  }

  subscribe(
    uid: string,
    callback:
      (
        state:
          PresenceState,
      ) => void,
  ) {
    const services =
      getFirebaseServices()

    if (!services) {
      callback(
        normalizePresence(
          uid,
          undefined,
        ),
      )

      return () => {}
    }

    return onValue(
      ref(
        services.realtime,
        `presence/${uid}`,
      ),

      (snapshot) => {
        callback(
          normalizePresence(
            uid,
            snapshot.val(),
          ),
        )
      },
    )
  }
}
