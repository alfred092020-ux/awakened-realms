import {
  doc,
  getDoc,
  setDoc,
} from 'firebase/firestore'

import {
  getFirebaseServices,
  getFirebaseUser,
  isFirebaseConfigured,
  signInFirebaseGoogle,
  signOutFirebase,
  waitForFirebaseUser,
} from './FirebaseClient'

import type {
  User,
} from 'firebase/auth'

import type {
  MetaState,
} from '../meta/MetaTypes'

export interface CloudAccount {
  uid: string

  displayName:
    string | null

  email:
    string | null

  photoURL:
    string | null
}

export interface CloudMetaRecord {
  state:
    MetaState

  updatedAt:
    number
}

function toAccount(
  user: User,
): CloudAccount {
  return {
    uid:
      user.uid,

    displayName:
      user.displayName,

    email:
      user.email,

    photoURL:
      user.photoURL,
  }
}

function isMetaState(
  value: unknown,
): value is MetaState {
  if (
    typeof value !==
      'object' ||
    value === null
  ) {
    return false
  }

  const state =
    value as Partial<
      MetaState
    >

  return (
    state.version === 1 &&
    typeof state.essence ===
      'number' &&
    typeof state.lifetimeRuns ===
      'number' &&
    typeof state.bestWave ===
      'number' &&
    typeof state.lastSeenAt ===
      'number' &&
    typeof state.upgrades ===
      'object' &&
    state.upgrades !==
      null
  )
}

export class CloudSaveService {
  isConfigured() {
    return isFirebaseConfigured()
  }

  getAccount():
    CloudAccount | null {
    const user =
      getFirebaseUser()

    return user
      ? toAccount(user)
      : null
  }

  async waitForAccount():
    Promise<
      CloudAccount | null
    > {
    const user =
      await waitForFirebaseUser()

    return user
      ? toAccount(user)
      : null
  }

  async signInWithGoogle() {
    const user =
      await signInFirebaseGoogle()

    return toAccount(
      user,
    )
  }

  async signOut() {
    await signOutFirebase()
  }

  async loadMeta():
    Promise<
      CloudMetaRecord |
      undefined
    > {
    const services =
      getFirebaseServices()

    const user =
      getFirebaseUser()

    if (
      !services ||
      !user
    ) {
      return undefined
    }

    const reference =
      doc(
        services.db,
        'players',
        user.uid,
      )

    const snapshot =
      await getDoc(
        reference,
      )

    if (
      !snapshot.exists()
    ) {
      return undefined
    }

    const data =
      snapshot.data()

    if (
      !isMetaState(
        data.meta,
      )
    ) {
      return undefined
    }

    const updatedAt =
      typeof data.updatedAt ===
        'number'
        ? data.updatedAt
        : 0

    return {
      state:
        data.meta,

      updatedAt,
    }
  }

  async saveMeta(
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

    const reference =
      doc(
        services.db,
        'players',
        user.uid,
      )

    await setDoc(
      reference,
      {
        meta:
          state,

        updatedAt,
      },
      {
        merge:
          true,
      },
    )

    return true
  }

  async saveIfSignedIn(
    state: MetaState,
    updatedAt: number,
  ) {
    if (
      !this.getAccount()
    ) {
      return false
    }

    return this.saveMeta(
      state,
      updatedAt,
    )
  }
}
