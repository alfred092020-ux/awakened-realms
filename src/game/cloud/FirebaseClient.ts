import {
  getApps,
  initializeApp,
} from 'firebase/app'

import type {
  FirebaseApp,
  FirebaseOptions,
} from 'firebase/app'

import {
  getAuth,
  GoogleAuthProvider,
  onAuthStateChanged,
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

export interface FirebaseServices {
  app: FirebaseApp
  auth: Auth
  db: Firestore
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
