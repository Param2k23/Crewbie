# Crewbie Mission Control (web)

Next.js app for Campus Pulse and the 3D Negotiation Arena. Run/test instructions, architecture and integrator notes live in
[`../../docs/mission-control/`](../../docs/mission-control/README.md).

```bash
npm install && npm run dev      # http://localhost:3000, /arena
npm test                        # vitest
```

## Attach to an existing Discord session

Open `/arena?mode=live&view=2d`, enter `http://127.0.0.1:8787` and the
`session_…` identifier posted by the bot, then press **Connect**. Switch to 3D
using the view button. Connect only reads the existing snapshot and SSE stream;
the **Start** buttons create separate synthetic scenarios.

Both inputs trim surrounding copy/paste whitespace. Previously the session ID
was tested against the API route regex without trimming: a trailing space or
newline caused “Invalid URL or session id” before fetch or EventSource ran.
The exact unpadded URL and ID already passed validation. A network or CORS failure
cannot produce that validation message. The local API allows browser origins
`http://localhost:3000`, `http://127.0.0.1:3000`, and `http://localhost:3100`.
SSE replays existing `agent_event` frames and resumes with Last-Event-ID; reducer
deduplication handles replay. Both views derive approval state from those events.

Read-only browser verification with a running API and web server (PowerShell):

```powershell
$env:CREWBIE_SMOKE_SESSION = 'session_…' # existing identifier from Discord
node scripts/attach-smoke.mjs
```

The script opens 2D and 3D views, checks initial approvals, then waits 60 seconds
for a pending authorized member to send `I accept version N` in Discord. It checks
that both views and the snapshot advance on the same session and version, and
blocks all API writes. Set `CREWBIE_SMOKE_TIMEOUT` to extend the wait in milliseconds.

Verification on 2026-10-24: existing session `session_0ff1db590cb4` attached in both
browser views at v2, 2/4 approvals, including a working 3D canvas and successful
snapshot/SSE requests with CORS. No new Discord approval arrived during the wait,
so live approval propagation remains unverified. Automated adapter/hook tests
cover a later acceptance reaching the 2D rendering and shared 3D scene model.


## Public site (Vercel)

The landing page is deployed as the Vercel project `crewbie`:
`https://crewbie-sepia.vercel.app` (also `https://crewbie-devils-ghost.vercel.app`).
`/` redirects to `/unlocks`; the Mission Control demo is at `/demo` and `/arena`.

Deploy from this folder after `vercel login` (the repo owner has not installed Vercel's GitHub app, so
deployments are made from the command line, not on every push):

```bash
cd apps/web
npx vercel@65.2.0 deploy --prod --yes
```

No environment variables are needed for the landing page. `.vercel/` and `.env.local` are git-ignored.
