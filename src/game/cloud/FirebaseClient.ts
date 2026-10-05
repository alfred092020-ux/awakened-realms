import {
  Capacitor,
} from '@capacitor/core'

import {
  FirebaseAuthentication,
} from '@capacitor-firebase/authentication'

import {
  getApps,
  initializeApp,
} from 'firebase/app'

import type {
  FirebaseApp,
  FirebaseOptions,
} from 'firebase/app'

import {
  createUserWithEmailAndPassword,
  EmailAuthProvider,
  getAuth,
  GoogleAuthProvider,
  linkWithCredential,
  linkWithPopup,
  onAuthStateChanged,
  signInWithCredential,
  signInAnonymously,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
} from 'firebase/auth'

import type {
  Auth,
  User,
} from 'firebase/auth'

import {
  getFirestore,
} from 'firebase/firestore'

import type {
  Firestore,
} from 'firebase/firestore'

import {
  getDatabase,
} from 'firebase/database'

import type {
  Database,
} from 'firebase/database'

export interface FirebaseServices {
  app: FirebaseApp
  auth: Auth
  db: Firestore
  realtime: Database
}

let cachedServices:
  FirebaseServices |
  null |
  undefined

function readFirebaseConfig():
  FirebaseOptions | null {
  const config:
    FirebaseOptions = {
    apiKey:
      (
        import.meta.env
          .VITE_FIREBASE_API_KEY ??
        ''
      ).trim(),

    authDomain:
      (
        import.meta.env
          .VITE_FIREBASE_AUTH_DOMAIN ??
        ''
      ).trim(),

    projectId:
      (
        import.meta.env
          .VITE_FIREBASE_PROJECT_ID ??
        ''
      ).trim(),

    storageBucket:
      (
        import.meta.env
          .VITE_FIREBASE_STORAGE_BUCKET ??
        ''
      ).trim(),

    messagingSenderId:
      (
        import.meta.env
          .VITE_FIREBASE_MESSAGING_SENDER_ID ??
        ''
      ).trim(),

    appId:
      (
        import.meta.env
          .VITE_FIREBASE_APP_ID ??
        ''
      ).trim(),

    databaseURL:
      (
        import.meta.env
          .VITE_FIREBASE_DATABASE_URL ??
        ''
      ).trim(),
  }

  const configured =
    Boolean(
      config.apiKey &&
      config.authDomain &&
      config.projectId &&
      config.appId,
    )

  return configured
    ? config
    : null
}

export function
getFirebaseServices():
  FirebaseServices | null {
  if (
    cachedServices !==
    undefined
  ) {
    return cachedServices
  }

  const config =
    readFirebaseConfig()

  if (!config) {
    cachedServices =
      null

    return null
  }

  const existing =
    getApps()[0]

  const app =
    existing ??
    initializeApp(
      config,
    )

  cachedServices = {
    app,

    auth:
      getAuth(app),

    db:
      getFirestore(app),

    realtime:
      getDatabase(
        app,
        config.databaseURL,
      ),
  }

  return cachedServices
}

export function
isFirebaseConfigured() {
  return (
    getFirebaseServices() !==
    null
  )
}

export function
getFirebaseUser():
  User | null {
  return (
    getFirebaseServices()
      ?.auth.currentUser ??
    null
  )
}

export async function
waitForFirebaseUser():
  Promise<User | null> {
  const services =
    getFirebaseServices()

  if (!services) {
    return null
  }

  return new Promise(
    (resolve) => {
      let unsubscribe =
        () => {}

      unsubscribe =
        onAuthStateChanged(
          services.auth,
          (user) => {
            unsubscribe()

            resolve(
              user,
            )
          },
        )
    },
  )
}

export async function
signInFirebaseGoogle() {
  const services =
    getFirebaseServices()

  if (!services) {
    throw new Error(
      'Firebase is not configured.',
    )
  }

  if (
    Capacitor.isNativePlatform()
  ) {
    const result =
      await FirebaseAuthentication
        .signInWithGoogle({
          useCredentialManager:
            false,
        })

    const idToken =
      result.credential
        ?.idToken

    const accessToken =
      result.credential
        ?.accessToken

    if (
      !idToken &&
      !accessToken
    ) {
      throw new Error(
        'Google did not return a usable credential.',
      )
    }

    const credential =
      GoogleAuthProvider
        .credential(
          idToken ??
            null,

          accessToken ??
            null,
        )

    const signedIn =
      await signInWithCredential(
        services.auth,
        credential,
      )

    return signedIn.user
  }

  const provider =
    new GoogleAuthProvider()

  provider
    .setCustomParameters({
      prompt:
        'select_account',
    })

  const credential =
    await signInWithPopup(
      services.auth,
      provider,
    )

  return credential.user
}

/**
 * Email/password sign-in for the game client.
 *
 * This authenticates the Firebase client session ONLY. It never grants game
 * authority: the production server verifies the ID token and re-derives the
 * session identity server-side (see LogresAuthSession).
 */
export async function
signInFirebaseEmailPassword(
  email: string,
  password: string,
) {
  const services =
    getFirebaseServices()

  if (!services) {
    throw new Error(
      'Firebase is not configured.',
    )
  }

  if (
    typeof email !== 'string' ||
    !email.trim() ||
    typeof password !== 'string' ||
    password.length === 0
  ) {
    throw new Error(
      'Email and password are required.',
    )
  }

  const credential =
    await signInWithEmailAndPassword(
      services.auth,
      email,
      password,
    )

  return credential.user
}

/**
 * Creates a Firebase email/password account. This is still only a client
 * authentication channel; game state remains server-authoritative.
 */
export async function
createFirebaseEmailPasswordAccount(
  email: string,
  password: string,
) {
  const services =
    getFirebaseServices()

  if (!services) {
    throw new Error(
      'Firebase is not configured.',
    )
  }

  if (
    typeof email !== 'string' ||
    !email.trim() ||
    typeof password !== 'string' ||
    password.length < 6
  ) {
    throw new Error(
      'Email and a password of at least 6 characters are required.',
    )
  }

  const credential =
    await createUserWithEmailAndPassword(
      services.auth,
      email,
      password,
    )

  return credential.user
}

export async function
signOutFirebase() {
  const services =
    getFirebaseServices()

  if (!services) {
    return
  }

  await signOut(
    services.auth,
  )
}

/**
 * Guest sign-in via Firebase anonymous auth.
 *
 * This creates an anonymous Firebase user so onboarding and testing flows can
 * reach the backend without permanent credentials. It is still only a client
 * authentication channel: the server derives a `guest` session from a
 * verified token and remains the sole game authority.
 *
 * If a user is already signed in (including an existing anonymous guest), the
 * current user is returned so repeated calls are idempotent on the client.
 */
export async function
signInFirebaseGuest() {
  const services =
    getFirebaseServices()

  if (!services) {
    throw new Error(
      'Firebase is not configured.',
    )
  }

  const existing =
    services
      .auth
      .currentUser

  if (existing) {
    return existing
  }

  const credential =
    await signInAnonymously(
      services.auth,
    )

  return credential.user
}

function requireAnonymousUser(
  user: User | null,
): User {
  if (!user) {
    throw new Error(
      'No Firebase user is signed in to link.',
    )
  }

  if (!user.isAnonymous) {
    throw new Error(
      'Only anonymous guest users can be linked; sign in as a guest first.',
    )
  }

  return user
}

/**
 * Links the current anonymous guest user to a Google account.
 *
 * The Firebase user uid is preserved across linking, so the server-side guest
 * account keeps its progression when it is later bound to the verified Google
 * subject. On native platforms the Capacitor plugin produces the provider
 * credential which is then applied with `linkWithCredential`; on web the
 * `linkWithPopup` flow is used.
 */
export async function
linkFirebaseGuestWithGoogle() {
  const services =
    getFirebaseServices()

  if (!services) {
    throw new Error(
      'Firebase is not configured.',
    )
  }

  const user =
    requireAnonymousUser(
      services
        .auth
        .currentUser,
    )

  if (
    Capacitor.isNativePlatform()
  ) {
    const result =
      await FirebaseAuthentication
        .signInWithGoogle({
          skipNativeAuth:
            true,
        })

    const idToken =
      result.credential
        ?.idToken

    const accessToken =
      result.credential
        ?.accessToken

    if (
      !idToken &&
      !accessToken
    ) {
      throw new Error(
        'Google did not return a usable credential.',
      )
    }

    const credential =
      GoogleAuthProvider
        .credential(
          idToken ??
            null,

          accessToken ??
            null,
        )

    const linked =
      await linkWithCredential(
        user,
        credential,
      )

    return linked.user
  }

  const provider =
    new GoogleAuthProvider()

  provider
    .setCustomParameters({
      prompt:
        'select_account',
    })

  const linked =
    await linkWithPopup(
      user,
      provider,
    )

  return linked.user
}

/**
 * Links the current anonymous guest user to an email/password credential.
 *
 * The uid is preserved, so server-side guest progression survives the later
 * account binding. Firebase rejects the link with
 * `auth/email-already-in-use` / `auth/credential-already-in-use` when the
 * email is already owned by another account; the server-side binding
 * contract independently re-verifies that rejection.
 */
export async function
linkFirebaseGuestWithEmailPassword(
  email: string,
  password: string,
) {
  const services =
    getFirebaseServices()

  if (!services) {
    throw new Error(
      'Firebase is not configured.',
    )
  }

  if (
    typeof email !== 'string' ||
    !email.trim() ||
    typeof password !== 'string' ||
    password.length < 6
  ) {
    throw new Error(
      'Email and a password of at least 6 characters are required.',
    )
  }

  const user =
    requireAnonymousUser(
      services
        .auth
        .currentUser,
    )

  const credential =
    EmailAuthProvider.credential(
      email,
      password,
    )

  const linked =
    await linkWithCredential(
      user,
      credential,
    )

  return linked.user
}
