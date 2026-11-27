# Checkpoint — Shelf-scoped Partial Build queue (2026-11-27)

## Decision
- Full Build remains a separate workflow (`cloudflare.yml`): scheduled daily at 21:21 UTC and manually runnable as Full. It snapshots the queue at start and ACKs that snapshot only after successful deployment and site-state save.
- Partial Build is a dedicated manual workflow (`partial-build.yml`); no shelf IDs are entered by a person.
- DrivePriorityV4 records completed changed shelves in a persistent queue inside `TANGTHU_DRIVE_PRIORITY_STATE_V2.json`.
- Only completed `CHANGED` and first usable `SNAPSHOT BOOTSTRAPPED` shelves enter the queue. `SKIP`, `UNCHANGED`, and `PARTIAL SNAPSHOT STAGED` do not.
- Partial Build snapshots queue rows `{shelf_id, version, detected_at}`, validates existing catalog/lifecycle identity, builds only those shelf IDs, deploys, saves site-state, then ACKs only matching versions.
- A changed shelf detected again during a build gets a higher version and is retained by conditional ACK. Failures before ACK retain the queue.
- DrivePriority no longer dispatches GitHub automatically.

## Required configuration
- Set Apps Script Script Property `TANGTHU_BUILD_SYNC_TOKEN` to a long random secret.
- Add the same value as GitHub Actions repository secret `TANGTHU_BUILD_SYNC_TOKEN`.
- Ensure repository variable `TANGTHU_APPS_SCRIPT_URL` points to the deployed Apps Script web app.
- Deploy updated Apps Script files `Code.gs` and `DrivePriorityV4.gs` together.
- Keep the existing `driveCheckPriority` 30-minute trigger. Do not rerun setup unless intentionally resetting scanner state.

## Operational behavior
- Run `Cloudflare Pages - Partial Build` manually when desired.
- Empty queue: workflow exits successfully without generation/deployment.
- Invalid/missing catalog or lifecycle state: workflow fails safely and retains queue; run Full Build first.
- ACK is after Cloudflare deployment and successful site-state save in both workflows. Full Build ACKs its start-of-run snapshot; changes arriving later remain queued.

## Scope
- The queue records scanner-confirmed shelf IDs directly. No Drive corpus inference, manual ID entry, or automatic Partial Build dispatch.
