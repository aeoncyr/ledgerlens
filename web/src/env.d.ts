/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_FIREBASE_API_KEY: string
  readonly VITE_FIREBASE_AUTH_DOMAIN: string
  readonly VITE_FIREBASE_PROJECT_ID: string
  readonly VITE_FIREBASE_STORAGE_BUCKET: string
  readonly VITE_FIREBASE_APP_ID: string
  /** Optional absolute API origin. Empty means same origin, through the Firebase Hosting rewrite. */
  readonly VITE_API_BASE?: string
  /**
   * The Cloud Run URL, called directly for /analyze: an analysis runs inside its request for a
   * minute or more, longer than Firebase Hosting lets a request last.
   */
  readonly VITE_ANALYZE_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
