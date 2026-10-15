// Firebase setup. Judges are signed in anonymously in the background, so there is no login wall,
// but every API call still carries a Firebase ID token.
import { initializeApp } from 'firebase/app'
import { getAuth, onAuthStateChanged, signInAnonymously, type User } from 'firebase/auth'
import { getFirestore } from 'firebase/firestore'
import { getStorage } from 'firebase/storage'

const app = initializeApp({
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
})

export const auth = getAuth(app)
export const db = getFirestore(app)
export const storage = getStorage(app)

let pending: Promise<User> | null = null

/** Resolve the current user, signing in anonymously the first time. */
export function ensureSignedIn(): Promise<User> {
  if (auth.currentUser) return Promise.resolve(auth.currentUser)
  pending ??= new Promise<User>((resolve, reject) => {
    const stop = onAuthStateChanged(auth, (user) => {
      if (user) {
        stop()
        resolve(user)
      }
    })
    signInAnonymously(auth).catch((error: unknown) => {
      stop()
      pending = null
      reject(error)
    })
  })
  return pending
}
