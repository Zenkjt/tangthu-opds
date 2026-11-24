# Checkpoint — Refresh priority and job status

Date: 2026-11-24

## Scope

This patch changes only:
- `apps-script/DrivePriorityV4.gs`
- `apps-script/Code.gs`
- `scripts/postprocess_shelf_reload.py`

The duplicate root-level `DrivePriorityV4.gs` is intentionally untouched. Apps Script source is maintained under `apps-script/`.

## Decisions implemented

1. Manual Refresh has priority over L3. The continuation worker selects the first Refresh job that is not `paused_error`; only when no runnable Refresh remains does it select an eligible L3 job.
2. Refresh is allowed for a shelf already present in the current L3 queue. The shared Drive scan checkpoint is retained; the single script lock prevents concurrent scan mutation. L3 resumes after Refresh.
3. A Refresh job receives a durable `job_id`. Its status is stored in `refresh_status` in the existing priority-state JSON file.
4. New Apps Script POST action `refresh_status` reports the job state to the UI.
5. The UI polls the job state every 10 seconds. It distinguishes queued/running/retry, scan completion, build dispatch, dispatch failure, and paused errors. It only waits for `catalog.json` after a changed scan has successfully dispatched a build.
6. Paused Refresh jobs no longer block L3 or later Refresh jobs. A manual retry of the same shelf re-queues the paused job.
7. Refresh status history is bounded to 100 retained records; active states are not pruned.

## Deployment

Replace the three source files above in GitHub, then deploy the updated Apps Script project from `apps-script/` as usual. The website build pipeline will run `scripts/postprocess_shelf_reload.py`.

No trigger setup/reset, state-file deletion, or production data migration is required. Existing priority-state JSON remains readable; `refresh_status` is initialized lazily.

## Validation performed

- Python syntax compilation: `postprocess_shelf_reload.py` passed.
- JavaScript syntax check: `DrivePriorityV4.gs` and `Code.gs` passed Node syntax checking.
- UI postprocessor was exercised against a minimal generated `docs/index.html` fixture; the generated inline JavaScript passed Node syntax checking and the Apps Script URL was inserted.
- Live Apps Script execution, Google Drive scanning, GitHub dispatch, and production deployment were not run in this environment.

## Operational note

If a process is interrupted after recording `dispatch_pending` but before completing the GitHub dispatch, the UI will continue to show that dispatch is pending until timeout. Re-issuing Refresh creates a new job and safely rechecks the shelf.
