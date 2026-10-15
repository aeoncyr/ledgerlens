# LedgerLens web app

React, Vite and TypeScript, hosted on Firebase Hosting. `/api/**` is forwarded to the Cloud Run API.

## Run it locally

```bash
cd web
npm install
cp ../.env.example .env.development.local   # then fill in the VITE_FIREBASE_* values
npm run dev                                   # http://localhost:5173
```

Run the API on port 8080 alongside it (see [`../api/README.md`](../api/README.md)); Vite forwards `/api`
to it, just like Firebase Hosting does in production.

## Check and build

```bash
npm run lint
npm run build    # type-checks, then writes web/dist
```

## Deploy

From the repository root:

```bash
firebase deploy --only hosting,firestore:rules,firestore:indexes,storage
```

## Notes

- Visitors are signed in anonymously in the background, so there is no login wall. Every API call
  still carries a Firebase ID token.
- Pages that use Firebase are loaded on demand, so the landing page stays small and fast.
- `/status` shows whether the API is reachable and whether anonymous sign-in works.
